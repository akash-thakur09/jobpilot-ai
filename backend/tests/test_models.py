import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models import (
    CandidateProfile,
    CandidateSkill,
    JobSource,
    Job,
    Application,
    ApplicationStatus,
    ResumeVersion,
)


@pytest.mark.asyncio
async def test_database_models_and_relationships(db_session: AsyncSession):
    # Create Candidate
    candidate = CandidateProfile(
        full_name="Alex Mercer",
        email="alex.mercer@example.com",
        location="San Francisco, CA",
        work_authorization="US Citizen",
        summary="Senior Software Engineer with 7+ years of experience in distributed systems.",
        years_of_experience=7.5,
        target_titles=["Senior Software Engineer", "Backend Lead"],
        target_salary_min=160000,
        target_salary_max=200000,
    )
    db_session.add(candidate)
    await db_session.flush()

    skill = CandidateSkill(
        candidate_id=candidate.id,
        skill_name="Python",
        category="technical",
        years_experience=7.0,
        is_verified=True,
    )
    db_session.add(skill)

    # Create Job Source & Job
    source = JobSource(
        identifier="test_greenhouse",
        name="Greenhouse Test Source",
        base_url="https://boards.greenhouse.io",
    )
    db_session.add(source)
    await db_session.flush()

    job = Job(
        source_id=source.id,
        external_id="gh_101",
        title="Senior Python Backend Engineer",
        company="Tech Corp",
        canonical_url="https://boards.greenhouse.io/techcorp/jobs/101",
        description="Looking for an experienced Python engineer.",
        salary_min=170000,
        salary_max=210000,
    )
    db_session.add(job)
    await db_session.flush()

    # Create Resume Version
    resume = ResumeVersion(
        candidate_id=candidate.id,
        job_id=job.id,
        structured_content={"summary": "Tailored summary", "skills": ["Python"]},
        candidate_snapshot={"full_name": candidate.full_name},
        pdf_file_path="storage/resumes/test_resume.pdf",
        file_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        is_ats_valid=True,
        ats_extracted_text="Alex Mercer - Senior Python Backend Engineer",
    )
    db_session.add(resume)
    await db_session.flush()

    # Create Application
    app_record = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        resume_version_id=resume.id,
        status=ApplicationStatus.READY_FOR_REVIEW.value,
    )
    db_session.add(app_record)
    await db_session.commit()

    # Verify Query
    result = await db_session.execute(
        select(Application).where(Application.id == app_record.id)
    )
    fetched_app = result.scalar_one_or_none()
    assert fetched_app is not None
    assert fetched_app.status == ApplicationStatus.READY_FOR_REVIEW.value
    assert fetched_app.resume_version_id == resume.id
    assert fetched_app.job_id == job.id


@pytest.mark.asyncio
async def test_application_uniqueness_constraint_and_submission_attempts(db_session: AsyncSession):
    from sqlalchemy.exc import IntegrityError
    from backend.app.models import SubmissionAttempt, SubmissionOutcome

    # 1. Setup candidate & job
    candidate = CandidateProfile(
        full_name="Sarah Connor",
        email="sarah@example.com",
        location="Los Angeles, CA",
        work_authorization="US Citizen",
        summary="DevOps Engineer",
    )
    source = JobSource(identifier="test_src_p5", name="Test Source", base_url="https://example.com")
    db_session.add_all([candidate, source])
    await db_session.flush()

    job = Job(
        source_id=source.id,
        external_id="ext_999",
        title="Site Reliability Engineer",
        company="Cyberdyne",
        canonical_url="https://cyberdyne.example.com/jobs/999",
        description="Looking for SRE.",
    )
    db_session.add(job)
    await db_session.flush()

    resume = ResumeVersion(
        candidate_id=candidate.id,
        job_id=job.id,
        structured_content={"summary": "SRE Summary"},
        candidate_snapshot={"full_name": candidate.full_name},
        pdf_file_path="storage/resumes/sre.pdf",
        file_sha256="1111111111111111111111111111111111111111111111111111111111111111",
        is_ats_valid=True,
    )
    db_session.add(resume)
    await db_session.flush()

    # 2. Create Application with Phase 5 fields
    app = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        resume_version_id=resume.id,
        selected_resume_sha256=resume.file_sha256,
        status=ApplicationStatus.PREPARING.value,
        approval_fingerprint="abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
        approval_metadata={"policy_version": "1.0.0", "approved_by": "user"},
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)

    assert app.status == ApplicationStatus.PREPARING.value
    assert app.selected_resume_sha256 == resume.file_sha256
    assert app.approval_fingerprint is not None

    # 3. Create SubmissionAttempt linked to application
    attempt = SubmissionAttempt(
        application_id=app.id,
        attempt_number=1,
        adapter_identifier="synthetic_form_adapter",
        selected_resume_version_id=resume.id,
        uploaded_artifact_sha256=resume.file_sha256,
        outcome=SubmissionOutcome.SUCCESS.value,
        confirmation_reference="CONF-12345",
        confirmation_payload={"status": "confirmed", "receipt": "rec_001"},
        sanitized_diagnostics={"http_status": 200, "duration_ms": 420},
    )
    db_session.add(attempt)
    await db_session.commit()

    # Verify attempt retrieval and relation
    att_res = await db_session.execute(
        select(SubmissionAttempt).where(SubmissionAttempt.application_id == app.id)
    )
    fetched_attempts = att_res.scalars().all()
    assert len(fetched_attempts) == 1
    assert fetched_attempts[0].outcome == SubmissionOutcome.SUCCESS.value
    assert fetched_attempts[0].confirmation_reference == "CONF-12345"

    # 4. Verify Uniqueness Constraint: Duplicate (candidate_id, job_id) must fail
    dup_app = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        resume_version_id=resume.id,
        status=ApplicationStatus.READY_FOR_REVIEW.value,
    )
    db_session.add(dup_app)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
