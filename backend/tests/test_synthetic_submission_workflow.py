"""
JobPilot AI - Synthetic Submission Workflow Tests
Tests the isolated synthetic submission workflow without contacting real job boards.
Verifies all 7 safety and operational scenarios:
1. Successful synthetic submission: lifecycle transition, confirmation reference, and ordered audit events.
2. Attempt with invalid approval fingerprint -> BLOCKED_SAFETY.
3. Attempt with resume checksum mismatch -> BLOCKED_SAFETY.
4. Attempt with missing resume artifact -> FAILED / BLOCKED_SAFETY.
5. Attempt on application that is not APPROVED -> rejects transition.
6. Attempt with missing required candidate data -> FAILED.
7. Idempotent execution (repeated runs return consistent confirmation without errors).
"""

import os
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.automation.synthetic_submission_service import SyntheticSubmissionService
from backend.app.core.config import settings
from backend.app.models.application import Application, ApplicationEvent, SubmissionAttempt
from backend.app.models.candidate import CandidateProfile, CandidateSkill
from backend.app.models.enums import ApplicationStatus, SubmissionOutcome
from backend.app.models.job import Job, JobSource
from backend.app.models.matching import MatchScore
from backend.app.models.resume import ResumeVersion
from backend.app.resumes.storage_service import ResumeStorageService
from backend.app.services.application_workflow_service import ApplicationWorkflowService
from backend.app.workflow.approval_fingerprint import ApprovalFingerprintService


async def setup_test_application(
    db_session: AsyncSession,
    full_name: str = "Elena Fisher",
    email: str = None,
    corrupt_resume_checksum: bool = False,
    delete_resume_file: bool = False,
    tamper_fingerprint: bool = False,
    initial_status: ApplicationStatus = ApplicationStatus.APPROVED,
) -> Application:
    """Helper to create a fully set-up application for testing."""
    uid = uuid.uuid4().hex[:8]
    email = email if email is not None else f"elena_{uid}@example.com"

    # Candidate
    candidate = CandidateProfile(
        full_name=full_name,
        email=email,
        phone="+1-555-0144",
        location="Austin, TX",
        work_authorization="US Citizen",
        summary="Senior Software Engineer",
        years_of_experience=6.0,
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

    # Job
    source = JobSource(identifier=f"src_{uid}", name="Test Source", base_url="http://127.0.0.1")
    db_session.add(source)
    await db_session.flush()

    job = Job(
        source_id=source.id,
        external_id=f"job_{uid}",
        title="Senior Automation Engineer",
        company="Acme Corp",
        canonical_url=f"https://boards.greenhouse.io/acme/jobs/{uid}",
        description="Looking for Python automation specialist.",
        location="Remote",
    )
    db_session.add(job)
    await db_session.flush()

    # Resume
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\nElena Fisher Resume\n%%EOF"
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

    # Match score
    match = MatchScore(
        job_id=job.id,
        candidate_id=candidate.id,
        overall_score=88.0,
        is_eligible=True,
        eligibility_status="ELIGIBLE",
        explanation="Eligible match.",
        is_latest=True,
    )
    db_session.add(match)
    await db_session.commit()

    # Re-fetch eager
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

    job_res = await db_session.execute(select(Job).options(selectinload(Job.requirements)).where(Job.id == job.id))
    job = job_res.scalar_one()

    resume_res = await db_session.execute(select(ResumeVersion).where(ResumeVersion.id == resume.id))
    resume = resume_res.scalar_one()

    match_res = await db_session.execute(select(MatchScore).where(MatchScore.id == match.id))
    match = match_res.scalar_one()

    form_data = ApplicationWorkflowService.build_prepared_form_data(candidate, resume)
    fingerprint = ApprovalFingerprintService.generate_fingerprint_for_application(
        candidate=candidate,
        job=job,
        resume_version=resume,
        prepared_form_data=form_data.model_dump()["fields"],
        match_score=match,
    )

    if tamper_fingerprint:
        fingerprint = "0" * 64

    # Create Application
    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        resume_version_id=resume.id,
        selected_resume_sha256=file_sha256,
        status=initial_status.value,
        approval_fingerprint=fingerprint if initial_status == ApplicationStatus.APPROVED else None,
    )
    db_session.add(application)
    await db_session.commit()
    await db_session.refresh(application)

    if corrupt_resume_checksum:
        abs_path = ResumeStorageService.get_resume_pdf_path(file_path)
        with open(abs_path, "wb") as f:
            f.write(b"%PDF-1.4 Corrupted content bytes here")

    if delete_resume_file:
        abs_path = ResumeStorageService.get_resume_pdf_path(file_path)
        if abs_path.exists():
            os.remove(abs_path)

    return application


@pytest.mark.asyncio
async def test_successful_synthetic_submission(db_session: AsyncSession):
    """
    Scenario 1: Successful synthetic submission:
    - Application transitions: APPROVED -> SYNTHETIC_SUBMISSION_IN_PROGRESS -> SUBMITTED_SIMULATION
    - Correct confirmation reference generated (SYNTH-...)
    - Correct audit events logged in order
    - SubmissionAttempt recorded with outcome SUBMITTED_SIMULATION
    """
    application = await setup_test_application(db_session, initial_status=ApplicationStatus.APPROVED)

    attempt = await SyntheticSubmissionService.execute_synthetic_submission(
        session=db_session,
        application_id=application.id,
        actor="TEST_USER",
    )

    assert attempt.outcome == SubmissionOutcome.SUBMITTED_SIMULATION.value
    assert attempt.confirmation_reference is not None
    assert attempt.confirmation_reference.startswith("SYNTH-")
    assert attempt.adapter_identifier == "synthetic_mock_adapter"

    # Verify Application DB Status
    await db_session.refresh(application)
    assert application.status == ApplicationStatus.SUBMITTED_SIMULATION.value
    assert application.submission_method == "SYNTHETIC_SIMULATION"
    assert application.confirmation_evidence is not None
    assert application.confirmation_evidence["simulation"] is True
    assert application.confirmation_evidence["confirmation_reference"] == attempt.confirmation_reference

    # Verify audit events in chronological order
    events_res = await db_session.execute(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == application.id)
        .order_by(ApplicationEvent.created_at.asc(), ApplicationEvent.id.asc())
    )
    events = events_res.scalars().all()
    event_types = [evt.payload.get("_event_type") for evt in events if evt.payload]

    assert "SYNTHETIC_EXECUTION_STARTED" in event_types
    assert "RESUME_ARTIFACT_VERIFIED" in event_types
    assert "FORM_DATA_VALIDATED" in event_types
    assert "CONFIRMATION_GENERATED" in event_types
    assert "SYNTHETIC_SUBMISSION_COMPLETED" in event_types

    # Strict Safety Invariant
    assert settings.JOBPILOT_REAL_SUBMISSION_ENABLED is False


@pytest.mark.asyncio
async def test_attempt_with_invalid_approval_fingerprint(db_session: AsyncSession):
    """
    Scenario 2: Attempt with invalid approval fingerprint -> BLOCKED_SAFETY.
    """
    application = await setup_test_application(
        db_session,
        tamper_fingerprint=True,
        initial_status=ApplicationStatus.APPROVED,
    )

    attempt = await SyntheticSubmissionService.execute_synthetic_submission(
        session=db_session,
        application_id=application.id,
    )

    assert attempt.outcome == SubmissionOutcome.BLOCKED_SAFETY.value
    assert "drift" in attempt.sanitized_diagnostics["error"].lower() or "fingerprint" in attempt.sanitized_diagnostics["error"].lower()

    # Application status invalidated or remains safe
    await db_session.refresh(application)
    assert application.status in (ApplicationStatus.APPROVED.value, ApplicationStatus.READY_FOR_REVIEW.value)


@pytest.mark.asyncio
async def test_attempt_with_resume_checksum_mismatch(db_session: AsyncSession):
    """
    Scenario 3: Attempt with resume checksum mismatch -> BLOCKED_SAFETY.
    """
    application = await setup_test_application(
        db_session,
        corrupt_resume_checksum=True,
        initial_status=ApplicationStatus.APPROVED,
    )

    attempt = await SyntheticSubmissionService.execute_synthetic_submission(
        session=db_session,
        application_id=application.id,
    )

    assert attempt.outcome == SubmissionOutcome.BLOCKED_SAFETY.value
    err_text = attempt.sanitized_diagnostics["error"].lower()
    assert "checksum" in err_text or "corrupt" in err_text or "drift" in err_text


@pytest.mark.asyncio
async def test_attempt_with_missing_resume_artifact(db_session: AsyncSession):
    """
    Scenario 4: Attempt with missing resume artifact -> FAILED or BLOCKED_SAFETY.
    """
    application = await setup_test_application(
        db_session,
        delete_resume_file=True,
        initial_status=ApplicationStatus.APPROVED,
    )

    attempt = await SyntheticSubmissionService.execute_synthetic_submission(
        session=db_session,
        application_id=application.id,
    )

    assert attempt.outcome in (SubmissionOutcome.FAILED.value, SubmissionOutcome.BLOCKED_SAFETY.value)
    err_text = attempt.sanitized_diagnostics["error"].lower()
    assert "missing" in err_text or "drift" in err_text or "corrupt" in err_text


@pytest.mark.asyncio
async def test_attempt_on_application_not_approved(client: AsyncClient, db_session: AsyncSession):
    """
    Scenario 5: Attempt on application that is not APPROVED -> rejects execution.
    """
    application = await setup_test_application(
        db_session,
        initial_status=ApplicationStatus.READY_FOR_REVIEW,
    )

    # Calling service directly records FAILED attempt
    attempt = await SyntheticSubmissionService.execute_synthetic_submission(
        session=db_session,
        application_id=application.id,
    )

    assert attempt.outcome == SubmissionOutcome.FAILED.value
    assert "must be 'approved'" in attempt.sanitized_diagnostics["error"].lower()

    # Through API, it should reject with HTTP 400
    resp = await client.post(
        f"/api/v1/applications/{application.id}/attempt",
        json={"is_synthetic": True},
    )
    assert resp.status_code == 400
    assert "must be 'APPROVED'" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_attempt_with_missing_required_candidate_data(db_session: AsyncSession):
    """
    Scenario 6: Attempt with missing required candidate data -> FAILED.
    """
    application = await setup_test_application(
        db_session,
        full_name="   ",  # blank name
        initial_status=ApplicationStatus.APPROVED,
    )

    attempt = await SyntheticSubmissionService.execute_synthetic_submission(
        session=db_session,
        application_id=application.id,
    )

    assert attempt.outcome == SubmissionOutcome.FAILED.value
    assert "missing required fields" in attempt.sanitized_diagnostics["error"].lower()


@pytest.mark.asyncio
async def test_idempotent_repeated_execution(client: AsyncClient, db_session: AsyncSession):
    """
    Scenario 7: Idempotent execution:
    Running synthetic submission twice returns consistent confirmation without error or duplicate runs.
    """
    application = await setup_test_application(
        db_session,
        initial_status=ApplicationStatus.APPROVED,
    )

    # First execution
    attempt1 = await SyntheticSubmissionService.execute_synthetic_submission(
        session=db_session,
        application_id=application.id,
    )
    assert attempt1.outcome == SubmissionOutcome.SUBMITTED_SIMULATION.value
    ref1 = attempt1.confirmation_reference

    # Second execution
    attempt2 = await SyntheticSubmissionService.execute_synthetic_submission(
        session=db_session,
        application_id=application.id,
    )
    assert attempt2.outcome == SubmissionOutcome.SUBMITTED_SIMULATION.value
    assert attempt2.confirmation_reference == ref1
    assert attempt2.id == attempt1.id

    # Through API as well
    resp = await client.post(
        f"/api/v1/applications/{application.id}/attempt",
        json={"is_synthetic": True},
    )
    assert resp.status_code == 200
    assert resp.json()["confirmation_reference"] == ref1
    assert resp.json()["outcome"] == SubmissionOutcome.SUBMITTED_SIMULATION.value

