import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.candidate import CandidateProfile, CandidateSkill
from backend.app.models.job import Job, JobSource
from backend.app.models.application import Application
from backend.app.models.notification import Notification
from backend.app.models.automation import AutomationRun
from backend.app.models.enums import AutomationRunStatus, NotificationType
from backend.app.services.discovery_pipeline import DiscoveryMatchingPipeline


@pytest.mark.asyncio
async def test_discovery_pipeline_end_to_end(db_session: AsyncSession):
    """
    Tests full 12-stage pipeline:
    - Runs synthetic discovery
    - Persists jobs and JobSource
    - Records AutomationRun
    - Evaluates matching when candidate exists
    - Never creates applications
    """
    # 1. Setup candidate profile
    cand = CandidateProfile(
        full_name="Alice Developer",
        email="alice@example.com",
        location="Remote",
        work_authorization="US Citizen",
        years_of_experience=6,
        summary="Experienced Full Stack Python and React Engineer",
    )
    db_session.add(cand)
    await db_session.commit()
    await db_session.refresh(cand)

    skill = CandidateSkill(
        candidate_id=cand.id,
        skill_name="Python",
        category="technical",
        years_experience=4.0,
        is_verified=True,
    )
    db_session.add(skill)
    await db_session.commit()

    # 2. Run pipeline for synthetic source
    result = await DiscoveryMatchingPipeline.execute(
        session=db_session,
        sources=["synthetic"],
        trigger="scheduled",
    )

    assert result["status"] == AutomationRunStatus.COMPLETED.value
    assert result["inserted"] >= 1
    assert result["jobs_evaluated"] >= 1
    assert "synthetic" in result["successful_sources"]

    # 3. Verify AutomationRun in DB
    run_res = await db_session.execute(
        select(AutomationRun).where(AutomationRun.id == result["run_id"])
    )
    run = run_res.scalar_one_or_none()
    assert run is not None
    assert run.status == AutomationRunStatus.COMPLETED.value
    assert run.run_type == "discovery_scheduled"

    # 4. Critical Safety Guard: Scheduled discovery must never prepare or create applications
    apps_res = await db_session.execute(select(Application))
    applications = apps_res.scalars().all()
    assert len(applications) == 0, "Scheduled discovery MUST NOT prepare or submit applications"


@pytest.mark.asyncio
async def test_discovery_pipeline_deduplication_and_notification_idempotency(db_session: AsyncSession):
    """Verifies that running pipeline multiple times is idempotent and deduplicates notifications."""
    # Setup candidate
    cand = CandidateProfile(
        full_name="Bob Engineer",
        email="bob@example.com",
        location="Remote",
        work_authorization="US Citizen",
        summary="Experienced Python and Cloud Backend Architect",
        years_of_experience=5,
    )
    db_session.add(cand)
    await db_session.commit()

    # First run
    run1 = await DiscoveryMatchingPipeline.execute(
        session=db_session,
        sources=["synthetic"],
        trigger="manual",
    )
    assert run1["inserted"] >= 1

    # Count notifications after run 1
    notif_res = await db_session.execute(select(Notification))
    notifs_after_run1 = len(notif_res.scalars().all())

    # Second run with exact same source
    run2 = await DiscoveryMatchingPipeline.execute(
        session=db_session,
        sources=["synthetic"],
        trigger="manual",
    )
    assert run2["inserted"] == 0
    assert run2["unchanged"] >= 1

    # Notifications count should not have duplicated
    notif_res2 = await db_session.execute(select(Notification))
    notifs_after_run2 = len(notif_res2.scalars().all())
    assert notifs_after_run2 == notifs_after_run1, "Match notifications must be idempotent across repeated runs"


@pytest.mark.asyncio
async def test_discovery_pipeline_partial_failure_handling(db_session: AsyncSession, monkeypatch):
    """Verifies that a failure in one source isolates errors and produces PARTIAL_SUCCESS without discarding valid data."""
    # Run with both a valid source ('synthetic') and an invalid source
    result = await DiscoveryMatchingPipeline.execute(
        session=db_session,
        sources=["synthetic", "unsupported_fake_source"],
        trigger="scheduled",
    )

    assert result["status"] == AutomationRunStatus.PARTIAL_SUCCESS.value
    assert "synthetic" in result["successful_sources"]
    assert "unsupported_fake_source" in result["failed_sources"]
    assert result["inserted"] >= 1

    # Partial failure notification must be created
    notif_res = await db_session.execute(
        select(Notification).where(Notification.notification_type == NotificationType.PARTIAL_FAILURE.value)
    )
    partial_notifs = notif_res.scalars().all()
    assert len(partial_notifs) >= 1


@pytest.mark.asyncio
async def test_discovery_pipeline_total_failure_handling(db_session: AsyncSession):
    """Verifies that if all sources fail, status is FAILED and a RUN_FAILED notification is stored."""
    result = await DiscoveryMatchingPipeline.execute(
        session=db_session,
        sources=["nonexistent_source_1", "nonexistent_source_2"],
        trigger="scheduled",
    )

    assert result["status"] == AutomationRunStatus.FAILED.value
    assert len(result["successful_sources"]) == 0

    notif_res = await db_session.execute(
        select(Notification).where(Notification.notification_type == NotificationType.RUN_FAILED.value)
    )
    failed_notifs = notif_res.scalars().all()
    assert len(failed_notifs) >= 1
