"""
JobPilot AI - Application Workflow Service
Orchestrates candidate resolution, job matching/eligibility validation,
resume artifact verification, prepared form data extraction, canonical review payloads,
cryptographic approval gates, and stale-approval invalidation.
"""

from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.candidate import CandidateProfile
from backend.app.models.job import Job
from backend.app.models.resume import ResumeVersion
from backend.app.models.matching import MatchScore
from backend.app.models.application import Application
from backend.app.models.enums import ApplicationStatus, EligibilityStatus
from backend.app.services.matching_service import MatchingService
from backend.app.services.resume_version_service import ResumeVersionService
from backend.app.resumes.storage_service import ResumeStorageService
from backend.app.workflow.state_machine import ApplicationStateMachine
from backend.app.workflow.approval_fingerprint import ApprovalFingerprintService
from backend.app.workflow.schemas import (
    PreparedFormField,
    PreparedApplicationFormData,
    ApplicationReviewPayload,
)
from backend.app.workflow.exceptions import (
    ApplicationNotFoundError,
    CandidateNotFoundError,
    AmbiguousCandidateError,
    CandidateProfileIncompleteError,
    JobNotFoundError,
    JobDisqualifiedError,
    ResumeIntegrityError,
    DuplicateApplicationConflictError,
    ApplicationNotReviewableError,
    ApprovalFingerprintMismatchError,
)
from backend.app.core.logging import logger


class ApplicationWorkflowService:
    """
    Coordinates application preparation, review, and approval before browser automation.
    """

    @classmethod
    def build_prepared_form_data(
        cls, candidate: CandidateProfile, resume_version: ResumeVersion
    ) -> PreparedApplicationFormData:
        """
        Builds a conservative, typed representation of application form fields
        derived exclusively from verified candidate facts.
        """
        fields: Dict[str, PreparedFormField] = {}
        unanswered: List[str] = []

        # 1. Identity & Contact
        fields["full_name"] = PreparedFormField(
            value=candidate.full_name,
            provenance="candidate_profiles.full_name",
            is_verified=True,
            description="Legal full name",
        )
        fields["email"] = PreparedFormField(
            value=candidate.email,
            provenance="candidate_profiles.email",
            is_verified=True,
            description="Primary contact email",
        )

        if candidate.phone:
            fields["phone"] = PreparedFormField(
                value=candidate.phone,
                provenance="candidate_profiles.phone",
                is_verified=True,
                description="Contact phone number",
            )
        else:
            unanswered.append("phone")

        fields["location"] = PreparedFormField(
            value=candidate.location,
            provenance="candidate_profiles.location",
            is_verified=True,
            description="Primary residence / city and state",
        )
        fields["work_authorization"] = PreparedFormField(
            value=candidate.work_authorization,
            provenance="candidate_profiles.work_authorization",
            is_verified=True,
            description="Work authorization status",
        )

        # 2. Online Profiles
        if candidate.linkedin_url:
            fields["linkedin_url"] = PreparedFormField(
                value=candidate.linkedin_url,
                provenance="candidate_profiles.linkedin_url",
                is_verified=True,
                description="LinkedIn Profile URL",
            )
        else:
            unanswered.append("linkedin_url")

        if candidate.github_url:
            fields["github_url"] = PreparedFormField(
                value=candidate.github_url,
                provenance="candidate_profiles.github_url",
                is_verified=True,
                description="GitHub Profile URL",
            )

        if candidate.portfolio_url:
            fields["portfolio_url"] = PreparedFormField(
                value=candidate.portfolio_url,
                provenance="candidate_profiles.portfolio_url",
                is_verified=True,
                description="Portfolio URL",
            )

        # 3. Professional Experience & Verified Skills
        fields["years_of_experience"] = PreparedFormField(
            value=candidate.years_of_experience,
            provenance="candidate_profiles.years_of_experience",
            is_verified=True,
            description="Total verified years of professional experience",
        )

        verified_skills = [s.skill_name for s in (candidate.skills or []) if s.is_verified]
        fields["verified_skills"] = PreparedFormField(
            value=sorted(verified_skills),
            provenance="candidate_skills[is_verified=True]",
            is_verified=True,
            description="List of verified skills",
        )

        # 4. Resume Artifact Provenance
        fields["selected_resume_version_id"] = PreparedFormField(
            value=str(resume_version.id),
            provenance="resume_versions.id",
            is_verified=True,
            description="Tailored Resume Version ID",
        )
        fields["selected_resume_sha256"] = PreparedFormField(
            value=str(resume_version.file_sha256),
            provenance="resume_versions.file_sha256",
            is_verified=True,
            description="Cryptographic checksum of submitted resume PDF",
        )

        return PreparedApplicationFormData(fields=fields, unanswered_fields=unanswered)

    @classmethod
    async def resolve_candidate(
        cls, session: AsyncSession, candidate_id: Optional[str] = None
    ) -> CandidateProfile:
        """
        Resolves the candidate profile. Disallows ambiguous candidate selection
        when multiple profiles exist.
        """
        if candidate_id:
            query = (
                select(CandidateProfile)
                .options(
                    selectinload(CandidateProfile.skills),
                    selectinload(CandidateProfile.experiences),
                    selectinload(CandidateProfile.educations),
                    selectinload(CandidateProfile.projects),
                )
                .where(CandidateProfile.id == candidate_id)
            )
            result = await session.execute(query)
            candidate = result.scalar_one_or_none()
            if not candidate:
                raise CandidateNotFoundError(f"Candidate profile with ID '{candidate_id}' not found.")
            return candidate

        # Discover all candidate profiles
        query = select(CandidateProfile).options(
            selectinload(CandidateProfile.skills),
            selectinload(CandidateProfile.experiences),
            selectinload(CandidateProfile.educations),
            selectinload(CandidateProfile.projects),
        )
        result = await session.execute(query)
        candidates = list(result.scalars().all())

        if len(candidates) == 0:
            raise CandidateNotFoundError("No candidate profiles exist. Please create a candidate profile first.")
        if len(candidates) > 1:
            raise AmbiguousCandidateError(
                f"Multiple candidate profiles found ({len(candidates)}). "
                "Explicit candidate_id must be provided to avoid ambiguous candidate resolution."
            )

        return candidates[0]

    @classmethod
    async def prepare_application(
        cls,
        session: AsyncSession,
        job_id: str,
        candidate_id: Optional[str] = None,
        force_regenerate_resume: bool = False,
        actor: str = "SYSTEM",
    ) -> ApplicationReviewPayload:
        """
        Executes end-to-end application preparation:
        Resolves candidate -> loads job -> checks eligibility -> obtains tailored resume ->
        persists application -> transitions to READY_FOR_REVIEW (or NEEDS_HUMAN_ACTION) ->
        returns review payload.
        """
        # 1. Resolve Candidate
        candidate = await cls.resolve_candidate(session, candidate_id)

        # 2. Load Job
        job_res = await session.execute(
            select(Job).options(selectinload(Job.requirements)).where(Job.id == job_id)
        )
        job = job_res.scalar_one_or_none()
        if not job:
            raise JobNotFoundError(f"Job with ID '{job_id}' not found.")

        # 3. Validate Candidate Profile completeness
        if not candidate.full_name or not candidate.email or not candidate.work_authorization:
            raise CandidateProfileIncompleteError(
                "Candidate profile lacks required fields (full_name, email, or work_authorization)."
            )

        # 4. Check or execute Job Matching & Eligibility
        match_query = (
            select(MatchScore)
            .where(MatchScore.job_id == job.id, MatchScore.candidate_id == candidate.id, MatchScore.is_latest == True)
            .limit(1)
        )
        match_res = await session.execute(match_query)
        match_score = match_res.scalar_one_or_none()
        if not match_score:
            matching_service = MatchingService()
            match_score = await matching_service.evaluate_job(
                session=session, job_id=job.id, candidate_id=candidate.id, use_ai=False
            )

        # 5. Deterministic Eligibility Gate
        if not match_score.is_eligible or match_score.eligibility_status == EligibilityStatus.DISQUALIFIED.value:
            raise JobDisqualifiedError(
                f"Cannot prepare application for disqualified job: {match_score.explanation}"
            )

        is_needs_review = match_score.eligibility_status == EligibilityStatus.NEEDS_REVIEW.value

        # 6. Obtain or generate tailored resume
        resume_version = await ResumeVersionService.generate_tailored_resume(
            session=session,
            job_id=job.id,
            candidate_id=candidate.id,
            use_ai=False,
            force_regenerate=force_regenerate_resume,
        )

        # Verify resume ownership and disk artifact integrity
        if resume_version.candidate_id != candidate.id or resume_version.job_id != job.id:
            raise ResumeIntegrityError("Resume version candidate or job relationship mismatch.")

        if not ResumeStorageService.verify_file_integrity(
            resume_version.pdf_file_path, resume_version.file_sha256
        ):
            raise ResumeIntegrityError(
                f"Resume PDF file missing or checksum mismatch on disk: {resume_version.pdf_file_path}"
            )

        # 7. Check for Existing Application (Idempotency Control)
        app_res = await session.execute(
            select(Application)
            .options(
                selectinload(Application.job),
                selectinload(Application.resume_version),
            )
            .where(Application.candidate_id == candidate.id, Application.job_id == job.id)
        )
        existing_app = app_res.scalar_one_or_none()

        if existing_app:
            # Check terminal states
            if existing_app.status in (ApplicationStatus.WITHDRAWN.value, ApplicationStatus.REJECTED.value):
                raise DuplicateApplicationConflictError(
                    f"Application is in terminal state '{existing_app.status}'. Cannot re-prepare."
                )

            # If existing application has different resume version and not forcing regeneration
            if (
                existing_app.resume_version_id
                and existing_app.resume_version_id != resume_version.id
                and not force_regenerate_resume
            ):
                raise DuplicateApplicationConflictError(
                    f"Application already exists with a different resume version '{existing_app.resume_version_id}'."
                )

            # Update resume reference if regenerated
            if existing_app.resume_version_id != resume_version.id:
                existing_app.resume_version_id = resume_version.id
                existing_app.selected_resume_sha256 = resume_version.file_sha256
                # Invalidate any old approval
                existing_app.approval_fingerprint = None
                existing_app.approved_at = None
                await session.commit()

            return await cls.review_application(session, existing_app.id)

        # 8. Create Application
        new_app = Application(
            candidate_id=candidate.id,
            job_id=job.id,
            resume_version_id=resume_version.id,
            selected_resume_sha256=resume_version.file_sha256,
            status=ApplicationStatus.PREPARING.value,
        )

        try:
            session.add(new_app)
            await session.flush()
        except IntegrityError:
            await session.rollback()
            # Concurrent insert: reload existing
            reloaded = (
                await session.execute(
                    select(Application).where(
                        Application.candidate_id == candidate.id, Application.job_id == job.id
                    )
                )
            ).scalar_one()
            return await cls.review_application(session, reloaded.id)

        # 9. Initial State Transition
        target_status = (
            ApplicationStatus.NEEDS_HUMAN_ACTION
            if is_needs_review
            else ApplicationStatus.READY_FOR_REVIEW
        )
        await ApplicationStateMachine.transition(
            session=session,
            application_id=new_app.id,
            to_status=target_status,
            actor=actor,
            event_type="APPLICATION_PREPARED",
            payload={
                "match_score": match_score.overall_score,
                "eligibility_status": match_score.eligibility_status,
                "resume_version_id": resume_version.id,
            },
        )

        return await cls.review_application(session, new_app.id)

    @classmethod
    async def review_application(
        cls, session: AsyncSession, application_id: str
    ) -> ApplicationReviewPayload:
        """
        Constructs the complete application review payload including canonical
        approval fingerprint, prepared form fields, and approval eligibility.
        """
        # Load application with job and resume relations
        app_res = await session.execute(
            select(Application)
            .options(
                selectinload(Application.job).selectinload(Job.requirements),
                selectinload(Application.resume_version),
            )
            .where(Application.id == application_id)
        )
        application = app_res.scalar_one_or_none()
        if not application:
            raise ApplicationNotFoundError(f"Application with ID '{application_id}' not found.")

        candidate = await cls.resolve_candidate(session, application.candidate_id)
        job = application.job
        resume_version = application.resume_version

        if not resume_version:
            raise ResumeIntegrityError(f"Application '{application_id}' is missing a resume version reference.")

        # Check resume file integrity on disk
        is_resume_valid = ResumeStorageService.verify_file_integrity(
            resume_version.pdf_file_path, resume_version.file_sha256
        )

        # Build prepared form data
        form_data = cls.build_prepared_form_data(candidate, resume_version)

        # Fetch latest match score
        match_res = await session.execute(
            select(MatchScore)
            .where(
                MatchScore.job_id == job.id,
                MatchScore.candidate_id == candidate.id,
                MatchScore.is_latest == True,
            )
            .limit(1)
        )
        match_score = match_res.scalar_one_or_none()

        job_fp = ApprovalFingerprintService.compute_job_fingerprint(job)

        # Compute canonical approval fingerprint
        try:
            canonical_fingerprint = ApprovalFingerprintService.generate_fingerprint_for_application(
                candidate=candidate,
                job=job,
                resume_version=resume_version,
                prepared_form_data=form_data.model_dump()["fields"],
                match_score=match_score,
            )
        except Exception as e:
            logger.warning(f"Could not compute canonical fingerprint during review: {e}")
            canonical_fingerprint = ""

        # Determine if application is approvable
        is_approvable = True
        approvable_reasons = []

        if application.status != ApplicationStatus.READY_FOR_REVIEW.value:
            is_approvable = False
            approvable_reasons.append(f"Status is '{application.status}', must be 'READY_FOR_REVIEW'")

        if not is_resume_valid:
            is_approvable = False
            approvable_reasons.append("Resume PDF file on disk is invalid or corrupt")

        if match_score and match_score.eligibility_status == EligibilityStatus.DISQUALIFIED.value:
            is_approvable = False
            approvable_reasons.append("Job is disqualified by eligibility constraints")

        if match_score and match_score.eligibility_status == EligibilityStatus.NEEDS_REVIEW.value:
            is_approvable = False
            approvable_reasons.append("Job eligibility requires human review")

        if not canonical_fingerprint:
            is_approvable = False
            approvable_reasons.append("Canonical approval fingerprint could not be computed")

        approvable_reason = "Application is ready for approval." if is_approvable else "; ".join(approvable_reasons)

        eligibility_status_val = match_score.eligibility_status if match_score else "UNKNOWN"
        eligibility_reason_val = match_score.explanation if match_score else "No matching score evaluated"
        overall_score_val = float(match_score.overall_score) if match_score else 0.0
        explanation_val = match_score.explanation if match_score else ""

        fact_valid = (
            resume_version.factual_validation_result.get("is_valid", True)
            if resume_version.factual_validation_result
            else True
        )
        coverage_summary = resume_version.keyword_coverage_result or {}

        return ApplicationReviewPayload(
            application_id=str(application.id),
            candidate_id=str(candidate.id),
            job_id=str(job.id),
            status=application.status,
            employer=job.company,
            job_title=job.title,
            job_url=job.canonical_url,
            job_fingerprint=job_fp,
            eligibility_status=eligibility_status_val,
            eligibility_reason=eligibility_reason_val,
            match_score=overall_score_val,
            match_explanation=explanation_val,
            selected_resume_version_id=str(resume_version.id),
            resume_sha256=resume_version.file_sha256,
            resume_integrity_valid=is_resume_valid,
            resume_factual_validation_valid=fact_valid,
            keyword_coverage_summary=coverage_summary,
            canonical_approval_fingerprint=canonical_fingerprint,
            prepared_form_data={k: v.model_dump() for k, v in form_data.fields.items()},
            unanswered_questions=form_data.unanswered_fields,
            review_warnings=match_score.warnings if match_score else [],
            is_approvable=is_approvable,
            approvable_reason=approvable_reason,
            approved_at=application.approved_at,
            approved_fingerprint=application.approval_fingerprint,
        )

    @classmethod
    async def approve_application(
        cls,
        session: AsyncSession,
        application_id: str,
        reviewed_fingerprint: str,
        approval_metadata: Optional[Dict[str, Any]] = None,
        actor: str = "CANDIDATE",
    ) -> Application:
        """
        Approves an application after cryptographically verifying that the
        user-reviewed fingerprint exactly matches the server-computed fingerprint.
        """
        app_res = await session.execute(
            select(Application)
            .options(
                selectinload(Application.job).selectinload(Job.requirements),
                selectinload(Application.resume_version),
            )
            .where(Application.id == application_id)
        )
        application = app_res.scalar_one_or_none()
        if not application:
            raise ApplicationNotFoundError(f"Application with ID '{application_id}' not found.")

        # Status Check: Application must be in READY_FOR_REVIEW
        if application.status != ApplicationStatus.READY_FOR_REVIEW.value:
            raise ApplicationNotReviewableError(
                f"Cannot approve application in status '{application.status}'. "
                "Must be in 'READY_FOR_REVIEW'."
            )

        candidate = await cls.resolve_candidate(session, application.candidate_id)
        job = application.job
        resume_version = application.resume_version
        if not resume_version:
            raise ResumeIntegrityError(f"Application '{application_id}' is missing a resume version reference.")

        # Verify disk artifact integrity
        if not ResumeStorageService.verify_file_integrity(
            resume_version.pdf_file_path, resume_version.file_sha256
        ):
            raise ResumeIntegrityError(
                f"Resume PDF on disk is invalid or corrupt: {resume_version.pdf_file_path}"
            )

        # Build prepared form data
        form_data = cls.build_prepared_form_data(candidate, resume_version)

        # Fetch latest match score
        match_res = await session.execute(
            select(MatchScore)
            .where(
                MatchScore.job_id == job.id,
                MatchScore.candidate_id == candidate.id,
                MatchScore.is_latest == True,
            )
            .limit(1)
        )
        match_score = match_res.scalar_one_or_none()

        if match_score and match_score.eligibility_status == EligibilityStatus.DISQUALIFIED.value:
            raise JobDisqualifiedError("Disqualified job cannot be approved.")

        # Recompute server-side canonical fingerprint
        server_fingerprint = ApprovalFingerprintService.generate_fingerprint_for_application(
            candidate=candidate,
            job=job,
            resume_version=resume_version,
            prepared_form_data=form_data.model_dump()["fields"],
            match_score=match_score,
        )

        # Fingerprint Match Verification
        if not reviewed_fingerprint or reviewed_fingerprint.strip() != server_fingerprint:
            raise ApprovalFingerprintMismatchError(
                f"Approval rejected: reviewed fingerprint ('{reviewed_fingerprint}') "
                f"does not match current server-computed fingerprint ('{server_fingerprint}'). "
                "The application data, resume, or job facts have changed since review."
            )

        safe_metadata = approval_metadata or {}
        safe_metadata["approval_method"] = "USER_REVIEWED_FINGERPRINT"

        # Execute state machine transition to APPROVED
        updated_app = await ApplicationStateMachine.transition(
            session=session,
            application_id=application.id,
            to_status=ApplicationStatus.APPROVED,
            actor=actor,
            event_type="APPLICATION_APPROVED",
            approval_fingerprint=server_fingerprint,
            approval_metadata=safe_metadata,
            payload={
                "fingerprint": server_fingerprint,
                "resume_version_id": resume_version.id,
                "job_title": job.title,
                "company": job.company,
            },
        )

        return updated_app

    @classmethod
    async def verify_approval_freshness(
        cls, session: AsyncSession, application_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verifies whether an existing APPROVED application remains valid against
        current candidate facts, job description, resume artifact, and form data.
        If stale, invalidates the approval, transitions to READY_FOR_REVIEW,
        and logs the invalidation event.
        """
        app_res = await session.execute(
            select(Application)
            .options(
                selectinload(Application.job).selectinload(Job.requirements),
                selectinload(Application.resume_version),
            )
            .where(Application.id == application_id)
        )
        application = app_res.scalar_one_or_none()
        if not application:
            raise ApplicationNotFoundError(f"Application with ID '{application_id}' not found.")

        # Only APPROVED applications can be checked for approval freshness
        if application.status != ApplicationStatus.APPROVED.value:
            return True, None

        if not application.approval_fingerprint:
            drift_reason = "Application is in APPROVED state but lacks an approval fingerprint."
            await cls._invalidate_approval(session, application, drift_reason)
            return False, drift_reason

        candidate = await cls.resolve_candidate(session, application.candidate_id)
        job = application.job
        resume_version = application.resume_version

        # 1. Check resume file integrity on disk
        if not ResumeStorageService.verify_file_integrity(
            resume_version.pdf_file_path, resume_version.file_sha256
        ):
            drift_reason = "Resume PDF artifact missing, modified, or corrupt on disk."
            await cls._invalidate_approval(session, application, drift_reason)
            return False, drift_reason

        # 2. Check match score
        match_res = await session.execute(
            select(MatchScore)
            .where(
                MatchScore.job_id == job.id,
                MatchScore.candidate_id == candidate.id,
                MatchScore.is_latest == True,
            )
            .limit(1)
        )
        match_score = match_res.scalar_one_or_none()
        if match_score and match_score.eligibility_status == EligibilityStatus.DISQUALIFIED.value:
            drift_reason = "Job was evaluated as DISQUALIFIED."
            await cls._invalidate_approval(session, application, drift_reason)
            return False, drift_reason

        # 3. Build current prepared form data
        form_data = cls.build_prepared_form_data(candidate, resume_version)

        # 4. Recompute current canonical fingerprint
        try:
            current_fingerprint = ApprovalFingerprintService.generate_fingerprint_for_application(
                candidate=candidate,
                job=job,
                resume_version=resume_version,
                prepared_form_data=form_data.model_dump()["fields"],
                match_score=match_score,
            )
        except Exception as e:
            drift_reason = f"Failed to compute canonical snapshot: {str(e)}"
            await cls._invalidate_approval(session, application, drift_reason)
            return False, drift_reason

        # 5. Check if stored fingerprint matches current fingerprint
        if current_fingerprint != application.approval_fingerprint:
            drift_reason = (
                f"Data drift detected: stored fingerprint ({application.approval_fingerprint}) "
                f"differs from current facts fingerprint ({current_fingerprint})."
            )
            await cls._invalidate_approval(session, application, drift_reason)
            return False, drift_reason

        return True, None

    @classmethod
    async def _invalidate_approval(
        cls, session: AsyncSession, application: Application, reason: str
    ) -> None:
        """
        Transitions stale APPROVED application back to READY_FOR_REVIEW and clears approval fields.
        """
        old_fingerprint = application.approval_fingerprint

        # Transition to READY_FOR_REVIEW
        await ApplicationStateMachine.transition(
            session=session,
            application_id=application.id,
            to_status=ApplicationStatus.READY_FOR_REVIEW,
            actor="APPROVAL_MONITOR",
            event_type="APPROVAL_INVALIDATED",
            payload={"reason": reason, "previous_fingerprint": old_fingerprint},
            auto_commit=False,
        )

        application.approval_fingerprint = None
        application.approved_at = None
        await session.commit()
        await session.refresh(application)
