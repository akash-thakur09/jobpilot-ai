import pytest
from sqlalchemy import select
from backend.app.db.session import AsyncSessionLocal
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
async def test_database_models_and_relationships():
    async with AsyncSessionLocal() as session:
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
        session.add(candidate)
        await session.flush()

        skill = CandidateSkill(
            candidate_id=candidate.id,
            skill_name="Python",
            category="technical",
            years_experience=7.0,
            is_verified=True,
        )
        session.add(skill)

        # Create Job Source & Job
        source = JobSource(
            identifier="test_greenhouse",
            name="Greenhouse Test Source",
            base_url="https://boards.greenhouse.io",
        )
        session.add(source)
        await session.flush()

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
        session.add(job)
        await session.flush()

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
        session.add(resume)
        await session.flush()

        # Create Application
        app_record = Application(
            job_id=job.id,
            candidate_id=candidate.id,
            resume_version_id=resume.id,
            status=ApplicationStatus.READY_FOR_REVIEW.value,
        )
        session.add(app_record)
        await session.commit()

        # Verify Query
        result = await session.execute(
            select(Application).where(Application.id == app_record.id)
        )
        fetched_app = result.scalar_one_or_none()
        assert fetched_app is not None
        assert fetched_app.status == ApplicationStatus.READY_FOR_REVIEW.value
        assert fetched_app.resume_version_id == resume.id
        assert fetched_app.job_id == job.id
