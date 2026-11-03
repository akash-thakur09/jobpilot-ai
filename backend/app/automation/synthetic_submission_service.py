"""
JobPilot AI - Isolated Synthetic Submission Engine
Executes an entirely local, isolated mock submission simulation for APPROVED applications
without making any network requests or contacting real job boards.

Safety Boundaries:
- Never makes HTTP requests to external career boards.
- Strictly validates approval fingerprint, resume artifact integrity, and candidate facts.
- Enforces append-only audit trail and lifecycle transitions:
  APPROVED -> SYNTHETIC_SUBMISSION_IN_PROGRESS -> SUBMITTED_SIMULATION
"""

import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.logging import logger
from backend.app.models.application import Application, SubmissionAttempt
from backend.app.models.enums import ApplicationStatus, SubmissionOutcome
from backend.app.models.resume import ResumeVersion
from backend.app.resumes.storage_service import ResumeStorageService
from backend.app.services.application_workflow_service import ApplicationWorkflowService
from backend.app.workflow.state_machine import ApplicationStateMachine, EventSanitizer
from backend.app.workflow.exceptions import (
    WorkflowError,
    ApplicationNotFoundError,
    InvalidStateTransitionError,
    ResumeIntegrityError,
)


class SyntheticSubmissionService:
    """
    Isolated synthetic submission service that simulates end-to-end application
    submission workflows locally without contacting real external endpoints.
    """

    ADAPTER_IDENTIFIER = "synthetic_mock_adapter"

    @classmethod
    async def execute_synthetic_submission(
        cls,
        session: AsyncSession,
        application_id: str,
        actor: str = "SYNTHETIC_RUNNER",
    ) -> SubmissionAttempt:
        """
        Executes complete isolated synthetic submission simulation:
        1. Validates application approval state & fingerprint freshness.
        2. Validates resume artifact presence and SHA-256 integrity.
        3. Validates required candidate profile fields & form mapping.
        4. Simulates resume upload and confirms artifact checksum match.
        5. Generates deterministic synthetic confirmation reference.
        6. Records append-only audit events and transitions lifecycle:
           APPROVED -> SYNTHETIC_SUBMISSION_IN_PROGRESS -> SUBMITTED_SIMULATION.
        """
        start_time = datetime.now(timezone.utc)

        # 1. Load application with relations
        app_res = await session.execute(
            select(Application)
            .options(
                selectinload(Application.job),
                selectinload(Application.resume_version),
            )
            .where(Application.id == application_id)
        )
        application = app_res.scalar_one_or_none()
        if not application:
            raise ApplicationNotFoundError(f"Application with ID '{application_id}' does not exist.")

        # Determine attempt number
        count_res = await session.execute(
            select(func.count(SubmissionAttempt.id)).where(SubmissionAttempt.application_id == application_id)
        )
        attempt_number = (count_res.scalar() or 0) + 1

        # Check for Idempotent Execution:
        # If application is already in SUBMITTED_SIMULATION state, return existing confirmation
        if application.status == ApplicationStatus.SUBMITTED_SIMULATION.value:
            existing_attempt_res = await session.execute(
                select(SubmissionAttempt)
                .where(
                    SubmissionAttempt.application_id == application.id,
                    SubmissionAttempt.outcome == SubmissionOutcome.SUBMITTED_SIMULATION.value,
                )
                .order_by(SubmissionAttempt.attempt_number.desc())
            )
            existing_attempt = existing_attempt_res.scalars().first()
            if existing_attempt:
                logger.info(f"Idempotent synthetic submission check: Application {application.id} already submitted.")
                return existing_attempt

        # Step A: Validate Application is APPROVED
        if application.status != ApplicationStatus.APPROVED.value:
            logger.warning(
                f"Cannot execute synthetic submission: Application {application.id} "
                f"status is '{application.status}', must be 'APPROVED'."
            )
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=cls.ADAPTER_IDENTIFIER,
                selected_resume_version_id=application.resume_version_id or "unknown",
                uploaded_artifact_sha256="none",
                outcome=SubmissionOutcome.FAILED.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={
                    "error": f"Cannot execute synthetic submission: Application status is '{application.status}', must be 'APPROVED'."
                },
                reconciliation_metadata={"is_synthetic": True, "simulation": True},
            )
            session.add(attempt)
            await session.commit()
            return attempt

        # Step B: Validate Approval Fingerprint & Freshness
        if not application.approval_fingerprint:
            logger.warning(f"Application {application.id} is APPROVED but lacks approval_fingerprint.")
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=cls.ADAPTER_IDENTIFIER,
                selected_resume_version_id=application.resume_version_id or "unknown",
                uploaded_artifact_sha256="none",
                outcome=SubmissionOutcome.BLOCKED_SAFETY.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={"error": "Application is in APPROVED state but lacks an approval fingerprint."},
                reconciliation_metadata={"is_synthetic": True, "simulation": True},
            )
            session.add(attempt)
            await session.commit()
            return attempt

        is_fresh, drift_reason = await ApplicationWorkflowService.verify_approval_freshness(session, application.id)
        if not is_fresh:
            logger.warning(f"Approval fingerprint invalid or data drift detected for {application.id}: {drift_reason}")
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=cls.ADAPTER_IDENTIFIER,
                selected_resume_version_id=application.resume_version_id or "unknown",
                uploaded_artifact_sha256="none",
                outcome=SubmissionOutcome.BLOCKED_SAFETY.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={"error": f"Invalid approval fingerprint or data drift: {drift_reason}"},
                reconciliation_metadata={"is_synthetic": True, "simulation": True},
            )
            session.add(attempt)
            await session.commit()
            return attempt

        # Step C: Validate Resume Version Artifact
        if not application.resume_version_id:
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=cls.ADAPTER_IDENTIFIER,
                selected_resume_version_id="missing",
                uploaded_artifact_sha256="none",
                outcome=SubmissionOutcome.FAILED.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={"error": "No resume version linked to application."},
                reconciliation_metadata={"is_synthetic": True, "simulation": True},
            )
            session.add(attempt)
            await session.commit()
            return attempt

        resume_res = await session.execute(
            select(ResumeVersion).where(ResumeVersion.id == application.resume_version_id)
        )
        resume_version = resume_res.scalar_one_or_none()
        if not resume_version:
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=cls.ADAPTER_IDENTIFIER,
                selected_resume_version_id=application.resume_version_id,
                uploaded_artifact_sha256="none",
                outcome=SubmissionOutcome.FAILED.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={"error": f"ResumeVersion '{application.resume_version_id}' not found in database."},
                reconciliation_metadata={"is_synthetic": True, "simulation": True},
            )
            session.add(attempt)
            await session.commit()
            return attempt

        # Verify candidate and job relationship
        if resume_version.candidate_id != application.candidate_id or resume_version.job_id != application.job_id:
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=cls.ADAPTER_IDENTIFIER,
                selected_resume_version_id=resume_version.id,
                uploaded_artifact_sha256=resume_version.file_sha256 or "none",
                outcome=SubmissionOutcome.BLOCKED_SAFETY.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={"error": "Resume relationship mismatch (candidate or job ID mismatch)."},
                reconciliation_metadata={"is_synthetic": True, "simulation": True},
            )
            session.add(attempt)
            await session.commit()
            return attempt

        # Step D: Confirm Resume PDF Exists on Disk and Verify SHA-256
        resolved_pdf_path = ResumeStorageService.get_resume_pdf_path(resume_version.pdf_file_path)
        if not resolved_pdf_path.exists():
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=cls.ADAPTER_IDENTIFIER,
                selected_resume_version_id=resume_version.id,
                uploaded_artifact_sha256=resume_version.file_sha256 or "none",
                outcome=SubmissionOutcome.FAILED.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={"error": f"Resume PDF file missing from disk: {resume_version.pdf_file_path}"},
                reconciliation_metadata={"is_synthetic": True, "simulation": True},
            )
            session.add(attempt)
            await session.commit()
            return attempt

        computed_sha256 = ResumeStorageService.compute_sha256(resolved_pdf_path)
        if (
            computed_sha256 != resume_version.file_sha256
            or (application.selected_resume_sha256 and computed_sha256 != application.selected_resume_sha256)
        ):
            logger.warning(f"Resume checksum mismatch on disk for application {application.id}")
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=cls.ADAPTER_IDENTIFIER,
                selected_resume_version_id=resume_version.id,
                uploaded_artifact_sha256=computed_sha256,
                outcome=SubmissionOutcome.BLOCKED_SAFETY.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={"error": "Resume checksum mismatch on disk. Possible tampering or corruption."},
                reconciliation_metadata={"is_synthetic": True, "simulation": True},
            )
            session.add(attempt)
            await session.commit()
            return attempt

        # Step E: Validate Candidate Profile & Required Fields
        candidate = await ApplicationWorkflowService.resolve_candidate(session, application.candidate_id)
        if not candidate.full_name or not candidate.full_name.strip() or not candidate.email or not candidate.email.strip():
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=cls.ADAPTER_IDENTIFIER,
                selected_resume_version_id=resume_version.id,
                uploaded_artifact_sha256=computed_sha256,
                outcome=SubmissionOutcome.FAILED.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={"error": "Candidate profile missing required fields: full_name and email are mandatory."},
                reconciliation_metadata={"is_synthetic": True, "simulation": True},
            )
            session.add(attempt)
            await session.commit()
            return attempt

        prepared_form = ApplicationWorkflowService.build_prepared_form_data(candidate, resume_version)
        required_field_keys = ["full_name", "email"]
        missing_required_fields = [
            k for k in required_field_keys
            if not prepared_form.fields.get(k) or not str(prepared_form.fields[k].value).strip()
        ]
        if missing_required_fields:
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=cls.ADAPTER_IDENTIFIER,
                selected_resume_version_id=resume_version.id,
                uploaded_artifact_sha256=computed_sha256,
                outcome=SubmissionOutcome.FAILED.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={
                    "error": f"Required form fields missing values: {', '.join(missing_required_fields)}"
                },
                reconciliation_metadata={"is_synthetic": True, "simulation": True},
            )
            session.add(attempt)
            await session.commit()
            return attempt

        # Step F: Lifecycle Transition: APPROVED -> SYNTHETIC_SUBMISSION_IN_PROGRESS
        await ApplicationStateMachine.transition(
            session=session,
            application_id=application.id,
            to_status=ApplicationStatus.SYNTHETIC_SUBMISSION_IN_PROGRESS,
            actor=actor,
            event_type="SYNTHETIC_EXECUTION_STARTED",
            payload={
                "adapter": cls.ADAPTER_IDENTIFIER,
                "attempt_number": attempt_number,
                "is_synthetic": True,
                "simulation": True,
                "target_mode": "ISOLATED_SIMULATION",
                "message": "Isolated synthetic submission simulation initiated.",
            },
            auto_commit=False,
        )

        # Step G: Append-only Audit Trail Events
        # 1. Resume artifact verified
        await ApplicationStateMachine.record_event(
            session=session,
            application_id=application.id,
            event_type="RESUME_ARTIFACT_VERIFIED",
            payload={
                "selected_resume_version_id": resume_version.id,
                "version_number": resume_version.version_number,
                "uploaded_artifact_sha256": computed_sha256,
                "expected_sha256": resume_version.file_sha256,
                "artifact_validation_result": "VALID_MATCH",
                "is_synthetic": True,
            },
            actor=actor,
            auto_commit=False,
        )

        # 2. Form data validated
        await ApplicationStateMachine.record_event(
            session=session,
            application_id=application.id,
            event_type="FORM_DATA_VALIDATED",
            payload={
                "candidate_name": candidate.full_name,
                "candidate_email": candidate.email,
                "fields_validated_count": len(prepared_form.fields),
                "unanswered_required_questions": len(prepared_form.unanswered_fields),
                "validation_status": "ALL_REQUIRED_FIELDS_SATISFIED",
                "is_synthetic": True,
            },
            actor=actor,
            auto_commit=False,
        )

        # Step H: Generate Synthetic Confirmation Reference
        short_app_id = application.id[:8].upper()
        timestamp_int = int(time.time())
        confirmation_ref = f"SYNTH-{short_app_id}-{timestamp_int}"

        # 3. Confirmation generated
        await ApplicationStateMachine.record_event(
            session=session,
            application_id=application.id,
            event_type="CONFIRMATION_GENERATED",
            payload={
                "confirmation_reference": confirmation_ref,
                "is_synthetic": True,
                "simulation": True,
            },
            actor=actor,
            auto_commit=False,
        )

        # Step I: Build Confirmation Payload
        confirmation_payload = {
            "simulation": True,
            "simulated": True,
            "is_synthetic": True,
            "message": "Synthetic application submission completed successfully",
            "confirmation_reference": confirmation_ref,
            "receipt_timestamp": datetime.now(timezone.utc).isoformat(),
            "submission_method": "SYNTHETIC_SIMULATION",
            "uploaded_artifact_sha256": computed_sha256,
            "selected_resume_version_id": resume_version.id,
            "target_job_title": application.job.title if application.job else "Unknown",
            "target_company": application.job.company if application.job else "Unknown",
            "disclaimer": "This was a local synthetic simulation. No real external job board or employer was contacted.",
        }

        # Step J: Lifecycle Transition: SYNTHETIC_SUBMISSION_IN_PROGRESS -> SUBMITTED_SIMULATION
        await ApplicationStateMachine.transition(
            session=session,
            application_id=application.id,
            to_status=ApplicationStatus.SUBMITTED_SIMULATION,
            actor=actor,
            event_type="SYNTHETIC_SUBMISSION_COMPLETED",
            confirmation_reference=confirmation_ref,
            confirmation_evidence=confirmation_payload,
            payload={
                "adapter": cls.ADAPTER_IDENTIFIER,
                "attempt_number": attempt_number,
                "confirmation_reference": confirmation_ref,
                "is_synthetic": True,
                "simulation": True,
            },
            auto_commit=False,
        )

        # Step K: Record Final SubmissionAttempt
        attempt = SubmissionAttempt(
            application_id=application.id,
            attempt_number=attempt_number,
            adapter_identifier=cls.ADAPTER_IDENTIFIER,
            selected_resume_version_id=resume_version.id,
            uploaded_artifact_sha256=computed_sha256,
            outcome=SubmissionOutcome.SUBMITTED_SIMULATION.value,
            started_at=start_time,
            completed_at=datetime.now(timezone.utc),
            confirmation_reference=confirmation_ref,
            confirmation_payload=EventSanitizer.sanitize(confirmation_payload),
            sanitized_diagnostics={
                "is_synthetic": True,
                "simulation": True,
                "external_request_made": False,
                "artifact_verified": True,
                "form_validated": True,
            },
            reconciliation_metadata={"is_synthetic": True, "simulation": True},
        )
        session.add(attempt)
        await session.commit()
        await session.refresh(attempt)

        logger.info(
            f"Synthetic submission completed for application {application.id}: "
            f"Reference={confirmation_ref}, Outcome={attempt.outcome}"
        )
        return attempt
