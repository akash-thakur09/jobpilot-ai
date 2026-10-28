import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.models.job import Job, JobSource
from backend.app.models.candidate import CandidateProfile
from backend.app.models.application import Application
from backend.app.models.enums import FreshnessStatus, JobStatus, ApplicationStatus
from backend.app.services.job_freshness_service import JobFreshnessService


@pytest.mark.asyncio
async def test_source_failure_does_not_mark_job_closed(db_session: AsyncSession):
    src = JobSource(identifier="src-fail-test", name="Failing Source", base_url="https://fail.example.com")
    db_session.add(src)
    await db_session.flush()

    job = Job(
        source_id=src.id,
        external_id="ext-live-01",
        title="Site Reliability Engineer",
        company="Reliability Inc",
        canonical_url="https://rel.example.com/jobs/1",
        freshness_status=FreshnessStatus.ACTIVE.value,
        last_seen_at=datetime.now(timezone.utc),
        description="Kubernetes, Python, Linux.",
    )
    db_session.add(job)
    await db_session.commit()

    # When source adapter fails, job should be marked UNKNOWN, NOT CONFIRMED_CLOSED
    await JobFreshnessService.mark_job_unknown(db_session, job, "HTTP 503 Provider Unavailable")
    assert job.freshness_status == FreshnessStatus.UNKNOWN.value
    assert job.status != JobStatus.EXPIRED.value
    assert "503" in (job.freshness_reason or "")


@pytest.mark.asyncio
async def test_staleness_and_reactivation_behavior(db_session: AsyncSession):
    src = JobSource(identifier="src-stale-test", name="Stale Source", base_url="https://stale.example.com")
    db_session.add(src)
    await db_session.flush()

    # Job unseen for 20 days
    old_time = datetime.now(timezone.utc) - timedelta(days=20)
    job_stale = Job(
        source_id=src.id,
        external_id="ext-old-01",
        title="Python Backend Developer",
        company="SlowCompany",
        canonical_url="https://slow.example.com/jobs/old",
        freshness_status=FreshnessStatus.ACTIVE.value,
        last_seen_at=old_time,
        description="Python services.",
    )
    # Job seen today
    job_active = Job(
        source_id=src.id,
        external_id="ext-new-01",
        title="Go Developer",
        company="FastCompany",
        canonical_url="https://fast.example.com/jobs/new",
        freshness_status=FreshnessStatus.ACTIVE.value,
        last_seen_at=datetime.now(timezone.utc),
        description="Go microservices.",
    )
    db_session.add_all([job_stale, job_active])
    await db_session.commit()

    # Discovery run finds only job_active
    res = await JobFreshnessService.evaluate_source_staleness(
        session=db_session,
        source_id=src.id,
        seen_job_ids=[job_active.id],
        staleness_days=14,
    )
    assert res["marked_stale"] == 1
    assert job_stale.freshness_status == FreshnessStatus.POTENTIALLY_STALE.value

    # Subsequent run sees job_stale again -> authoritatively reactivate
    await JobFreshnessService.mark_job_verified_active(db_session, job_stale)
    assert job_stale.freshness_status == FreshnessStatus.ACTIVE.value
    assert "Re-verified active" in (job_stale.freshness_reason or "")


@pytest.mark.asyncio
async def test_authoritative_closure_preserves_application_history(db_session: AsyncSession):
    src = JobSource(identifier="src-close-test", name="Closure Source", base_url="https://close.example.com")
    cand = CandidateProfile(
        full_name="Test Applicant",
        email="applicant@example.com",
        location="Remote",
        work_authorization="US_CITIZEN",
        summary="Experienced engineer",
    )
    db_session.add_all([src, cand])
    await db_session.flush()

    job = Job(
        source_id=src.id,
        external_id="ext-close-01",
        title="Full Stack Developer",
        company="Fintech Corp",
        canonical_url="https://fintech.example.com/jobs/close",
        description="React and Python.",
        freshness_status=FreshnessStatus.ACTIVE.value,
    )
    db_session.add(job)
    await db_session.flush()

    app = Application(
        candidate_id=cand.id,
        job_id=job.id,
        status=ApplicationStatus.APPROVED.value,
        submission_method="DIRECT",
        approval_fingerprint="fingerprint-immutable-123",
    )
    db_session.add(app)
    await db_session.commit()

    # Confirmed closure marks job closed, but does NOT mutate application or delete job
    await JobFreshnessService.mark_job_closed(db_session, job, "Job portal reported vacancy filled (HTTP 404)")
    assert job.freshness_status == FreshnessStatus.CONFIRMED_CLOSED.value

    # Application record remains intact with approval fingerprint
    app_check = await db_session.get(Application, app.id)
    assert app_check is not None
    assert app_check.status == ApplicationStatus.APPROVED.value
    assert app_check.approval_fingerprint == "fingerprint-immutable-123"
    assert app_check.job_id == job.id
