"""
JobPilot AI - Browser Automation Integration Tests
Tests Playwright browser automation adapter, mock portal harness,
resume integrity checks, conservative form mapping, safety barriers, and SubmissionAttempt persistence.
"""

import uuid
from typing import Optional
import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.automation.browser_runner import BrowserAutomationRunner
from backend.app.automation.mock_portal.server import MockPortalServer
from backend.app.automation.synthetic_adapter import SyntheticBrowserAdapter
from backend.app.core.config import settings
from backend.app.models.application import Application, SubmissionAttempt
from backend.app.models.candidate import CandidateProfile, CandidateSkill
from backend.app.models.enums import ApplicationStatus, SubmissionOutcome
from backend.app.models.job import Job, JobSource
from backend.app.models.matching import MatchScore
from backend.app.models.resume import ResumeVersion
from backend.app.resumes.storage_service import ResumeStorageService
from backend.app.services.application_workflow_service import ApplicationWorkflowService
from backend.app.workflow.approval_fingerprint import ApprovalFingerprintService
from backend.app.workflow.state_machine import ApplicationStateMachine, InvalidStateTransitionError


@pytest.fixture(scope="module")
def mock_portal():
    """Starts local synthetic test portal on an ephemeral port."""
    server = MockPortalServer()
    server.start()
    yield server
    server.stop()


async def create_approved_test_application(
    db_session: AsyncSession,
    full_name: str = "Elena Fisher",
    email: Optional[str] = None,
    phone: str = "+1-555-0144",
    location: str = "Austin, TX",
) -> Application:
    """Helper to create a fully approved application with valid fingerprint and resume."""
    uid = uuid.uuid4().hex[:8]
    email = email or f"elena_{uid}@example.com"

    # 1. Candidate
    candidate = CandidateProfile(
        full_name=full_name,
        email=email,
        phone=phone,
        location=location,
        work_authorization="US Citizen",
        summary="Senior Software Automation Engineer",
        years_of_experience=6.0,
        linkedin_url=f"https://linkedin.com/in/{uid}",
    )
    db_session.add(candidate)
    await db_session.flush()

    skill = CandidateSkill(
        candidate_id=candidate.id,
        skill_name="Python",
        category="Languages",
        years_experience=5.0,
        is_verified=True,
    )
    db_session.add(skill)

    # 2. Job
    source = JobSource(identifier=f"src_{uid}", name="Portal Source", base_url="http://127.0.0.1")
    db_session.add(source)
    await db_session.flush()

    job = Job(
        source_id=source.id,
        external_id=f"job_{uid}",
        title="Automation Test Engineer",
        company="Naughty Dog",
        canonical_url=f"http://127.0.0.1/jobs/{uid}/apply",
        description="Looking for an Automation Engineer experienced in Python and Playwright.",
        location="Remote",
    )
    db_session.add(job)
    await db_session.flush()

    # 3. Resume Version with real PDF on disk
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"Elena Fisher Resume - Automation Engineer\n%%EOF"
    )
    file_path, file_sha256 = ResumeStorageService.save_resume_pdf(pdf_bytes)

    resume = ResumeVersion(
        candidate_id=candidate.id,
        job_id=job.id,
        version_number=1,
        structured_content={"summary": "Experienced Automation Engineer"},
        candidate_snapshot={"full_name": full_name},
        pdf_file_path=file_path,
        file_sha256=file_sha256,
        is_ats_valid=True,
        is_submission_ready=True,
    )
    db_session.add(resume)
    await db_session.flush()

    # 4. Match Score
    match = MatchScore(
        job_id=job.id,
        candidate_id=candidate.id,
        overall_score=88.0,
        is_eligible=True,
        eligibility_status="ELIGIBLE",
        explanation="Candidate meets all verified requirements.",
        is_latest=True,
    )
    db_session.add(match)
    await db_session.commit()

    # Re-fetch with eager loading
    cand_res = await db_session.execute(
        select(CandidateProfile)
        .options(
            selectinload(CandidateProfile.skills),
            selectinload(CandidateProfile.experiences),
            selectinload(CandidateProfile.educations),
            selectinload(CandidateProfile.projects),
        )
        .where(CandidateProfile.id == candidate.id)
    )
    candidate = cand_res.scalar_one()

    job_res = await db_session.execute(
        select(Job).options(selectinload(Job.requirements)).where(Job.id == job.id)
    )
    job = job_res.scalar_one()

    resume_res = await db_session.execute(
        select(ResumeVersion).where(ResumeVersion.id == resume.id)
    )
    resume = resume_res.scalar_one()

    match_res = await db_session.execute(
        select(MatchScore).where(MatchScore.id == match.id)
    )
    match = match_res.scalar_one()

    # 5. Form data and canonical fingerprint
    form_data = ApplicationWorkflowService.build_prepared_form_data(candidate, resume)
    fingerprint = ApprovalFingerprintService.generate_fingerprint_for_application(
        candidate=candidate,
        job=job,
        resume_version=resume,
        prepared_form_data=form_data.model_dump()["fields"],
        match_score=match,
    )

    # 6. Application
    app = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        resume_version_id=resume.id,
        selected_resume_sha256=file_sha256,
        status=ApplicationStatus.READY_FOR_REVIEW.value,
    )
    db_session.add(app)
    await db_session.commit()

    # Approve application via workflow service
    approved_app = await ApplicationWorkflowService.approve_application(
        session=db_session,
        application_id=app.id,
        reviewed_fingerprint=fingerprint,
    )
    return approved_app


# ===========================================================================
# Test Cases
# ===========================================================================

@pytest.mark.asyncio
async def test_playwright_opens_form_and_submits_successfully(db_session: AsyncSession, mock_portal: MockPortalServer):
    """
    Playwright opens local synthetic form, fills fields, uploads resume,
    submits, and verifies synthetic confirmation receipt.
    """
    app = await create_approved_test_application(db_session)
    target_url = f"{mock_portal.base_url}/jobs/{app.job_id}/apply"

    attempt = await BrowserAutomationRunner.execute_application_automation(
        session=db_session,
        application_id=app.id,
        target_url=target_url,
    )

    # Verify attempt record
    assert attempt.outcome == SubmissionOutcome.SUCCESS.value
    assert attempt.confirmation_reference is not None
    assert attempt.confirmation_reference.startswith("SYNTH-APP-")
    assert attempt.uploaded_artifact_sha256 == app.selected_resume_sha256
    assert attempt.confirmation_payload.get("status") == "confirmed"

    # Verify application state
    await db_session.refresh(app)
    assert app.status == ApplicationStatus.SUBMITTED.value


@pytest.mark.asyncio
async def test_unapproved_application_blocked(db_session: AsyncSession, mock_portal: MockPortalServer):
    """
    Unapproved application in READY_FOR_REVIEW cannot execute submission automation.
    """
    app = await create_approved_test_application(db_session)
    # Manually revert status to READY_FOR_REVIEW
    app.status = ApplicationStatus.READY_FOR_REVIEW.value
    await db_session.commit()

    target_url = f"{mock_portal.base_url}/jobs/{app.job_id}/apply"
    attempt = await BrowserAutomationRunner.execute_application_automation(
        session=db_session,
        application_id=app.id,
        target_url=target_url,
    )

    assert attempt.outcome == SubmissionOutcome.BLOCKED_SAFETY.value
    assert "must be 'APPROVED'" in attempt.sanitized_diagnostics["error"]

    await db_session.refresh(app)
    assert app.status == ApplicationStatus.READY_FOR_REVIEW.value


@pytest.mark.asyncio
async def test_stale_approval_rejected(db_session: AsyncSession, mock_portal: MockPortalServer):
    """
    If candidate profile changes after approval, drift is detected, approval is invalidated,
    and submission is blocked.
    """
    app = await create_approved_test_application(db_session)

    # Candidate profile changes (data drift)
    candidate_res = await db_session.execute(
        select(CandidateProfile).where(CandidateProfile.id == app.candidate_id)
    )
    candidate = candidate_res.scalar_one()
    candidate.full_name = "Elena Fisher Modified"
    await db_session.commit()

    target_url = f"{mock_portal.base_url}/jobs/{app.job_id}/apply"
    attempt = await BrowserAutomationRunner.execute_application_automation(
        session=db_session,
        application_id=app.id,
        target_url=target_url,
    )

    assert attempt.outcome == SubmissionOutcome.BLOCKED_SAFETY.value
    assert "Approval invalidated" in attempt.sanitized_diagnostics["error"]

    await db_session.refresh(app)
    assert app.status == ApplicationStatus.READY_FOR_REVIEW.value


@pytest.mark.asyncio
async def test_resume_tampering_prevents_upload_and_submission(db_session: AsyncSession, mock_portal: MockPortalServer):
    """
    If resume file on disk is modified or corrupted, checksum mismatch halts submission.
    """
    app = await create_approved_test_application(db_session)

    # Tamper with the resume version checksum record
    resume_res = await db_session.execute(
        select(ResumeVersion).where(ResumeVersion.id == app.resume_version_id)
    )
    resume = resume_res.scalar_one()
    # Resolve file and overwrite with different content
    pdf_path = ResumeStorageService.get_resume_pdf_path(resume.pdf_file_path)
    pdf_path.write_bytes(b"%PDF-1.4 Tampered Bytes %%EOF")

    target_url = f"{mock_portal.base_url}/jobs/{app.job_id}/apply"
    attempt = await BrowserAutomationRunner.execute_application_automation(
        session=db_session,
        application_id=app.id,
        target_url=target_url,
    )

    assert attempt.outcome == SubmissionOutcome.BLOCKED_SAFETY.value
    drift_reason = attempt.sanitized_diagnostics.get("drift_reason", "").lower()
    error_desc = attempt.sanitized_diagnostics.get("error", "").lower()
    assert "modified" in drift_reason or "corrupt" in drift_reason or "tampering" in error_desc or "drift" in error_desc


@pytest.mark.asyncio
async def test_captcha_detection_stops_automation(db_session: AsyncSession, mock_portal: MockPortalServer):
    """
    CAPTCHA barrier detected on page stops automation and requires human action.
    """
    app = await create_approved_test_application(db_session)
    target_url = f"{mock_portal.base_url}/jobs/{app.job_id}/apply?scenario=captcha"

    attempt = await BrowserAutomationRunner.execute_application_automation(
        session=db_session,
        application_id=app.id,
        target_url=target_url,
    )

    assert attempt.outcome == SubmissionOutcome.NEEDS_HUMAN_ACTION.value
    assert attempt.sanitized_diagnostics.get("barrier") == "CAPTCHA"

    await db_session.refresh(app)
    assert app.status == ApplicationStatus.NEEDS_HUMAN_ACTION.value


@pytest.mark.asyncio
async def test_mfa_or_access_restriction_detection(db_session: AsyncSession, mock_portal: MockPortalServer):
    """
    MFA prompt halts automation and marks workflow for human action.
    """
    app = await create_approved_test_application(db_session)
    target_url = f"{mock_portal.base_url}/jobs/{app.job_id}/apply?scenario=mfa"

    attempt = await BrowserAutomationRunner.execute_application_automation(
        session=db_session,
        application_id=app.id,
        target_url=target_url,
    )

    assert attempt.outcome == SubmissionOutcome.NEEDS_HUMAN_ACTION.value
    assert attempt.sanitized_diagnostics.get("barrier") == "MFA"

    await db_session.refresh(app)
    assert app.status == ApplicationStatus.NEEDS_HUMAN_ACTION.value


@pytest.mark.asyncio
async def test_access_denied_safety_block(db_session: AsyncSession, mock_portal: MockPortalServer):
    """
    Access denied / Cloudflare challenge page produces BLOCKED_SAFETY.
    """
    app = await create_approved_test_application(db_session)
    target_url = f"{mock_portal.base_url}/jobs/{app.job_id}/apply?scenario=access_denied"

    attempt = await BrowserAutomationRunner.execute_application_automation(
        session=db_session,
        application_id=app.id,
        target_url=target_url,
    )

    assert attempt.outcome == SubmissionOutcome.BLOCKED_SAFETY.value
    await db_session.refresh(app)
    assert app.status == ApplicationStatus.FAILED.value


@pytest.mark.asyncio
async def test_ambiguous_question_requires_human_action(db_session: AsyncSession, mock_portal: MockPortalServer):
    """
    Ambiguous employer question requires human response and does not guess.
    """
    app = await create_approved_test_application(db_session)
    target_url = f"{mock_portal.base_url}/jobs/{app.job_id}/apply?scenario=ambiguous"

    attempt = await BrowserAutomationRunner.execute_application_automation(
        session=db_session,
        application_id=app.id,
        target_url=target_url,
    )

    assert attempt.outcome == SubmissionOutcome.NEEDS_HUMAN_ACTION.value
    assert "why_hire" in str(attempt.sanitized_diagnostics)

    await db_session.refresh(app)
    assert app.status == ApplicationStatus.NEEDS_HUMAN_ACTION.value


@pytest.mark.asyncio
async def test_validation_error_detected(db_session: AsyncSession, mock_portal: MockPortalServer):
    """
    Portal validation failure produces FAILED outcome and does not produce SUBMITTED.
    """
    app = await create_approved_test_application(db_session)
    target_url = f"{mock_portal.base_url}/jobs/{app.job_id}/apply?scenario=validation_error"

    attempt = await BrowserAutomationRunner.execute_application_automation(
        session=db_session,
        application_id=app.id,
        target_url=target_url,
    )

    assert attempt.outcome == SubmissionOutcome.FAILED.value
    await db_session.refresh(app)
    assert app.status == ApplicationStatus.FAILED.value


@pytest.mark.asyncio
async def test_unsupported_form_stops_safely(db_session: AsyncSession, mock_portal: MockPortalServer):
    """
    Opening a page without an application form element stops safely.
    """
    app = await create_approved_test_application(db_session)
    target_url = f"{mock_portal.base_url}/health"

    attempt = await BrowserAutomationRunner.execute_application_automation(
        session=db_session,
        application_id=app.id,
        target_url=target_url,
    )

    assert attempt.outcome == SubmissionOutcome.FAILED.value
    assert "No application form" in str(attempt.sanitized_diagnostics) or "issues" in attempt.sanitized_diagnostics

    await db_session.refresh(app)
    assert app.status == ApplicationStatus.FAILED.value


@pytest.mark.asyncio
async def test_uncertain_outcome_becomes_outcome_unknown_no_blind_retry(db_session: AsyncSession, mock_portal: MockPortalServer):
    """
    If submit occurs but no receipt or error is provided, outcome is OUTCOME_UNKNOWN.
    Attempting blind re-submission from OUTCOME_UNKNOWN is strictly rejected by the state machine.
    """
    app = await create_approved_test_application(db_session)
    target_url = f"{mock_portal.base_url}/jobs/{app.job_id}/apply?scenario=unknown_outcome"

    attempt = await BrowserAutomationRunner.execute_application_automation(
        session=db_session,
        application_id=app.id,
        target_url=target_url,
    )

    assert attempt.outcome == SubmissionOutcome.OUTCOME_UNKNOWN.value
    await db_session.refresh(app)
    assert app.status == ApplicationStatus.OUTCOME_UNKNOWN.value

    # Blind re-execution must be rejected
    with pytest.raises(InvalidStateTransitionError):
        await ApplicationStateMachine.transition(
            session=db_session,
            application_id=app.id,
            to_status=ApplicationStatus.IN_PROGRESS,
            actor="AUTOMATION_RUNNER",
        )


@pytest.mark.asyncio
async def test_real_external_submissions_remain_disabled(db_session: AsyncSession):
    """
    External URLs are blocked when JOBPILOT_REAL_SUBMISSION_ENABLED=False.
    """
    assert settings.JOBPILOT_REAL_SUBMISSION_ENABLED is False

    app = await create_approved_test_application(db_session)
    external_url = "https://careers.example.com/apply/12345"

    attempt = await BrowserAutomationRunner.execute_application_automation(
        session=db_session,
        application_id=app.id,
        target_url=external_url,
    )

    assert attempt.outcome == SubmissionOutcome.BLOCKED_SAFETY.value
    assert "Real external submissions are disabled" in attempt.sanitized_diagnostics["error"]

    await db_session.refresh(app)
    # State should remain APPROVED because automation was halted before entering IN_PROGRESS
    assert app.status == ApplicationStatus.APPROVED.value


@pytest.mark.asyncio
async def test_synthetic_adapter_origin_whitelist():
    """
    Verifies that the synthetic adapter strictly rejects external navigation.
    """
    adapter = SyntheticBrowserAdapter()
    assert adapter._verify_origin_safety("http://127.0.0.1:8000/apply") is True
    assert adapter._verify_origin_safety("http://localhost:3000/apply") is True
    assert adapter._verify_origin_safety("https://linkedin.com/jobs/apply") is False
    assert adapter._verify_origin_safety("https://greenhouse.io/job") is False
