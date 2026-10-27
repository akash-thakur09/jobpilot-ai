"""
JobPilot AI - Browser Automation Runner
Coordinates the browser automation workflow:
1. Validates application approval freshness and resume integrity.
2. Enforces safety gates (real submission disabled, allowed origins).
3. Drives Playwright browser automation using the appropriate adapter.
4. Records immutable SubmissionAttempt history.
5. Transitions the ApplicationStateMachine based on verified outcome.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import uuid

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.automation.base_adapter import BaseBrowserAdapter
from backend.app.automation.form_mapper import FormMapper
from backend.app.automation.synthetic_adapter import SyntheticBrowserAdapter
from backend.app.automation.types import (
    AutomationExecutionResult,
    SafetyBarrierType,
)
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.models.application import Application, SubmissionAttempt
from backend.app.models.enums import ApplicationStatus, SubmissionOutcome
from backend.app.models.job import Job
from backend.app.models.resume import ResumeVersion
from backend.app.services.application_workflow_service import ApplicationWorkflowService
from backend.app.resumes.storage_service import ResumeStorageService
from backend.app.workflow.state_machine import ApplicationStateMachine, EventSanitizer


class BrowserAutomationRunner:
    """
    Executes automated job application workflows within strict safety boundaries.
    """

    ALLOWED_LOCAL_HOSTS = {"127.0.0.1", "localhost"}

    @classmethod
    async def execute_application_automation(
        cls,
        session: AsyncSession,
        application_id: str,
        target_url: Optional[str] = None,
        adapter: Optional[BaseBrowserAdapter] = None,
        actor: str = "AUTOMATION_RUNNER",
    ) -> SubmissionAttempt:
        """
        Executes end-to-end browser automation for an APPROVED application.
        Never executes real external submission when JOBPILOT_REAL_SUBMISSION_ENABLED is False.
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
            raise ValueError(f"Application with ID '{application_id}' not found.")

        # Determine attempt number
        count_res = await session.execute(
            select(func.count(SubmissionAttempt.id)).where(SubmissionAttempt.application_id == application_id)
        )
        attempt_number = (count_res.scalar() or 0) + 1

        adapter_instance = adapter or SyntheticBrowserAdapter()
        adapter_identifier = adapter_instance.adapter_identifier

        # 2. Gate 1: State must be APPROVED
        if application.status != ApplicationStatus.APPROVED.value:
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=adapter_identifier,
                selected_resume_version_id=application.resume_version_id or "unknown",
                uploaded_artifact_sha256=application.selected_resume_sha256 or "unknown",
                outcome=SubmissionOutcome.BLOCKED_SAFETY.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={
                    "error": f"Application is in status '{application.status}', must be 'APPROVED' before execution."
                },
            )
            session.add(attempt)
            await session.commit()
            return attempt

        # 3. Gate 2: Approval Freshness & Drift Detection
        is_fresh, stale_reason = await ApplicationWorkflowService.verify_approval_freshness(
            session=session, application_id=application.id
        )
        if not is_fresh:
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=adapter_identifier,
                selected_resume_version_id=application.resume_version_id or "unknown",
                uploaded_artifact_sha256=application.selected_resume_sha256 or "unknown",
                outcome=SubmissionOutcome.BLOCKED_SAFETY.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={
                    "error": "Approval invalidated due to data or resume drift.",
                    "drift_reason": stale_reason,
                },
            )
            session.add(attempt)
            await session.commit()
            return attempt

        # 4. Gate 3: Resume Integrity Re-verification Immediately Before Upload
        resume_version = application.resume_version
        if not resume_version:
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=adapter_identifier,
                selected_resume_version_id="missing",
                uploaded_artifact_sha256="missing",
                outcome=SubmissionOutcome.FAILED.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={"error": "Application lacks associated resume version."},
            )
            session.add(attempt)
            await session.commit()
            return attempt

        # Verify candidate, job, and resume relationships
        if (
            resume_version.candidate_id != application.candidate_id
            or resume_version.job_id != application.job_id
        ):
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=adapter_identifier,
                selected_resume_version_id=resume_version.id,
                uploaded_artifact_sha256=resume_version.file_sha256,
                outcome=SubmissionOutcome.BLOCKED_SAFETY.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={"error": "Resume relationship mismatch (candidate or job ID mismatch)."},
            )
            session.add(attempt)
            await session.commit()
            return attempt

        # Confirm file exists and checksum matches
        resolved_pdf_path = ResumeStorageService.get_resume_pdf_path(resume_version.pdf_file_path)
        if not resolved_pdf_path.exists():
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=adapter_identifier,
                selected_resume_version_id=resume_version.id,
                uploaded_artifact_sha256=resume_version.file_sha256,
                outcome=SubmissionOutcome.FAILED.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={"error": "Resume PDF file missing from disk."},
            )
            session.add(attempt)
            await session.commit()
            return attempt

        computed_sha256 = ResumeStorageService.compute_sha256(resolved_pdf_path)
        if computed_sha256 != resume_version.file_sha256 or computed_sha256 != application.selected_resume_sha256:
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=adapter_identifier,
                selected_resume_version_id=resume_version.id,
                uploaded_artifact_sha256=computed_sha256,
                outcome=SubmissionOutcome.BLOCKED_SAFETY.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={
                    "error": "Resume checksum mismatch on disk. Possible tampering or corruption."
                },
            )
            session.add(attempt)
            await session.commit()
            return attempt

        # 5. Gate 4: Real Submission & Allowed Origin Policy
        dest_url = target_url or application.job.canonical_url
        parsed_dest = urlparse(dest_url)
        is_local_portal = parsed_dest.hostname in cls.ALLOWED_LOCAL_HOSTS

        if not is_local_portal and not settings.JOBPILOT_REAL_SUBMISSION_ENABLED:
            logger.warning(
                f"Blocked attempt to execute automation on external URL '{dest_url}' "
                "while JOBPILOT_REAL_SUBMISSION_ENABLED=False."
            )
            attempt = SubmissionAttempt(
                application_id=application.id,
                attempt_number=attempt_number,
                adapter_identifier=adapter_identifier,
                selected_resume_version_id=resume_version.id,
                uploaded_artifact_sha256=computed_sha256,
                outcome=SubmissionOutcome.BLOCKED_SAFETY.value,
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                sanitized_diagnostics={
                    "error": "Real external submissions are disabled (JOBPILOT_REAL_SUBMISSION_ENABLED=False).",
                    "target_host": parsed_dest.hostname,
                },
            )
            session.add(attempt)
            await session.commit()
            return attempt

        # 6. State Machine Transition: APPROVED -> IN_PROGRESS
        await ApplicationStateMachine.transition(
            session=session,
            application_id=application.id,
            to_status=ApplicationStatus.IN_PROGRESS,
            actor=actor,
            event_type="AUTOMATION_STARTED",
            payload={
                "adapter": adapter_identifier,
                "attempt_number": attempt_number,
                "target_url": dest_url,
            },
        )

        # 7. Resolve Candidate and Build Prepared Form Data
        candidate = await ApplicationWorkflowService.resolve_candidate(session, application.candidate_id)
        prepared_form_data = ApplicationWorkflowService.build_prepared_form_data(candidate, resume_version)

        # 8. Browser Automation Execution with Playwright
        execution_result: Optional[AutomationExecutionResult] = None
        screenshot_path: Optional[str] = None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=settings.BROWSER_HEADLESS,
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
                    timeout=settings.BROWSER_TIMEOUT_MS,
                )
                context = await browser.new_context()
                page = await context.new_page()

                try:
                    # Navigate to application page
                    await page.goto(dest_url, timeout=settings.BROWSER_NAVIGATION_TIMEOUT_MS)

                    # Step A: Form Inspection & Safety Barrier Detection
                    inspection = await adapter_instance.inspect_form(page)

                    if inspection.safety_barrier:
                        barrier_outcome = (
                            SubmissionOutcome.NEEDS_HUMAN_ACTION
                            if inspection.safety_barrier in (SafetyBarrierType.CAPTCHA, SafetyBarrierType.MFA)
                            else SubmissionOutcome.BLOCKED_SAFETY
                        )
                        execution_result = AutomationExecutionResult(
                            outcome=barrier_outcome,
                            adapter_identifier=adapter_identifier,
                            error_message=f"Safety barrier detected: {inspection.safety_barrier.value}",
                            diagnostics={"barrier": inspection.safety_barrier.value},
                        )
                    elif not inspection.form_detected:
                        execution_result = AutomationExecutionResult(
                            outcome=SubmissionOutcome.FAILED,
                            adapter_identifier=adapter_identifier,
                            error_message="Unsupported form: No application form element detected.",
                            diagnostics={"issues": inspection.issues},
                        )
                    else:
                        # Step B: Conservative Field Mapping
                        plan = FormMapper.build_mapping_plan(inspection, prepared_form_data)

                        if plan.requires_human_intervention:
                            execution_result = AutomationExecutionResult(
                                outcome=SubmissionOutcome.NEEDS_HUMAN_ACTION,
                                adapter_identifier=adapter_identifier,
                                error_message="Form requires human intervention: ambiguous, unmapped, or sensitive fields.",
                                diagnostics={
                                    "intervention_reasons": plan.intervention_reasons,
                                    "unmapped_required_fields": plan.unmapped_required_fields,
                                },
                            )
                        else:
                            # Step C: Fill Mapped Fields
                            fill_results = await adapter_instance.fill_fields(page, plan)
                            fill_failures = [r for r in fill_results if not r.success]

                            if fill_failures:
                                execution_result = AutomationExecutionResult(
                                    outcome=SubmissionOutcome.FAILED,
                                    adapter_identifier=adapter_identifier,
                                    error_message="Failed to fill required form fields.",
                                    diagnostics={"fill_failures": [f.model_dump() for f in fill_failures]},
                                )
                            else:
                                # Step D: Upload Verified Resume PDF
                                if plan.file_upload_selector:
                                    await adapter_instance.upload_resume(
                                        page, plan.file_upload_selector, str(resolved_pdf_path)
                                    )

                                # Step E: Validate Form Before Submit
                                is_valid, val_errors = await adapter_instance.validate_form(page)
                                if not is_valid:
                                    execution_result = AutomationExecutionResult(
                                        outcome=SubmissionOutcome.FAILED,
                                        adapter_identifier=adapter_identifier,
                                        error_message=f"Form validation failed before submit: {'; '.join(val_errors)}",
                                        diagnostics={"validation_errors": val_errors},
                                    )
                                else:
                                    # Step F: Submit and Verify Outcome
                                    execution_result = await adapter_instance.submit_and_verify(page)

                finally:
                    # Capture screenshot on non-success outcomes if possible
                    if execution_result and execution_result.outcome != SubmissionOutcome.SUCCESS:
                        try:
                            settings.SCREENSHOT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
                            s_path = settings.SCREENSHOT_STORAGE_DIR / f"{application.id}_{attempt_number}.png"
                            await page.screenshot(path=str(s_path), full_page=True)
                            screenshot_path = str(s_path)
                        except Exception:
                            pass

                    # Defensive teardown
                    await context.close()
                    await browser.close()

        except PlaywrightTimeoutError as e:
            logger.warning(f"Browser navigation or operation timeout: {e}")
            execution_result = AutomationExecutionResult(
                outcome=SubmissionOutcome.OUTCOME_UNKNOWN,
                adapter_identifier=adapter_identifier,
                error_message=f"Browser timeout during execution: {str(e)}",
                diagnostics={"timeout": True, "detail": str(e)},
            )
        except Exception as e:
            logger.exception(f"Unexpected browser automation failure: {e}")
            execution_result = AutomationExecutionResult(
                outcome=SubmissionOutcome.FAILED,
                adapter_identifier=adapter_identifier,
                error_message=f"Unexpected automation error: {str(e)}",
                diagnostics={"exception": str(e)},
            )

        # 9. Persist SubmissionAttempt
        completed_time = datetime.now(timezone.utc)
        safe_diagnostics = EventSanitizer.sanitize(execution_result.diagnostics if execution_result else {})
        if screenshot_path:
            safe_diagnostics["screenshot_saved"] = True

        attempt = SubmissionAttempt(
            application_id=application.id,
            attempt_number=attempt_number,
            adapter_identifier=adapter_identifier,
            selected_resume_version_id=resume_version.id,
            uploaded_artifact_sha256=computed_sha256,
            outcome=execution_result.outcome.value if execution_result else SubmissionOutcome.FAILED.value,
            started_at=start_time,
            completed_at=completed_time,
            confirmation_reference=execution_result.confirmation_reference if execution_result else None,
            confirmation_payload=EventSanitizer.sanitize(execution_result.confirmation_payload) if execution_result else {},
            sanitized_diagnostics=safe_diagnostics,
            reconciliation_metadata={"is_synthetic": True},
        )
        session.add(attempt)
        await session.commit()

        # 10. State Machine Post-Execution Transitions
        final_outcome = execution_result.outcome if execution_result else SubmissionOutcome.FAILED

        if final_outcome == SubmissionOutcome.SUCCESS:
            await ApplicationStateMachine.transition(
                session=session,
                application_id=application.id,
                to_status=ApplicationStatus.SUBMITTED,
                actor=actor,
                event_type="APPLICATION_SUBMITTED",
                confirmation_reference=execution_result.confirmation_reference,
                confirmation_evidence=execution_result.confirmation_payload,
                payload={
                    "adapter": adapter_identifier,
                    "attempt_number": attempt_number,
                    "receipt_id": execution_result.confirmation_reference,
                    "is_synthetic": True,
                },
            )
        elif final_outcome == SubmissionOutcome.OUTCOME_UNKNOWN:
            await ApplicationStateMachine.transition(
                session=session,
                application_id=application.id,
                to_status=ApplicationStatus.OUTCOME_UNKNOWN,
                actor=actor,
                event_type="SUBMISSION_OUTCOME_UNKNOWN",
                payload={
                    "adapter": adapter_identifier,
                    "attempt_number": attempt_number,
                    "reason": execution_result.error_message,
                },
            )
        elif final_outcome == SubmissionOutcome.NEEDS_HUMAN_ACTION:
            await ApplicationStateMachine.transition(
                session=session,
                application_id=application.id,
                to_status=ApplicationStatus.NEEDS_HUMAN_ACTION,
                actor=actor,
                event_type="SUBMISSION_NEEDS_HUMAN_ACTION",
                payload={
                    "adapter": adapter_identifier,
                    "attempt_number": attempt_number,
                    "reason": execution_result.error_message,
                    "diagnostics": execution_result.diagnostics,
                },
            )
        else:  # FAILED or BLOCKED_SAFETY
            await ApplicationStateMachine.transition(
                session=session,
                application_id=application.id,
                to_status=ApplicationStatus.FAILED,
                actor=actor,
                event_type="SUBMISSION_FAILED",
                payload={
                    "adapter": adapter_identifier,
                    "attempt_number": attempt_number,
                    "reason": execution_result.error_message,
                    "diagnostics": execution_result.diagnostics,
                },
            )

        return attempt
