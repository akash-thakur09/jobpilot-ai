import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from unittest.mock import patch

from backend.app.main import app
from backend.app.db.session import get_db
from backend.app.core.config import settings
from backend.app.models.candidate import CandidateProfile, CandidateSkill
from backend.app.models.job import Job, JobSource
from backend.app.models.matching import MatchScore
from backend.app.models.notification import Notification
from backend.app.models.enums import NotificationChannel, NotificationStatus, RemoteType
from backend.app.services.email_service import EmailService
from backend.app.services.matching_service import MatchingService
from backend.app.services.discovery_pipeline import DiscoveryMatchingPipeline


@pytest.mark.asyncio
async def test_email_preferences_api_and_status(db_session: AsyncSession):
    """
    Step 4 & 5: Tests notification preferences API and email config status (without credential leakage).
    """
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create candidate
        cand = CandidateProfile(
            full_name="Eva Notification",
            email="eva@example.com",
            location="Remote",
            work_authorization="US Citizen",
            summary="Engineer",
            years_of_experience=4,
        )
        db_session.add(cand)
        await db_session.commit()

        # 1. Fetch initial preferences
        get_res = await client.get("/api/v1/notifications/preferences")
        assert get_res.status_code == 200
        prefs = get_res.json()
        assert prefs["email_enabled"] is False  # Disabled by default
        assert prefs["min_match_score"] == 70

        # 2. Update preferences
        update_res = await client.put(
            "/api/v1/notifications/preferences",
            json={
                "email_enabled": True,
                "delivery_mode": "IMMEDIATE",
                "min_match_score": 80,
                "recipient_email": "alerts@eva.dev",
            },
        )
        assert update_res.status_code == 200
        updated = update_res.json()
        assert updated["email_enabled"] is True
        assert updated["min_match_score"] == 80
        assert updated["recipient_email"] == "alerts@eva.dev"

        # 3. Check email status endpoint (never exposes secrets/passwords)
        status_res = await client.get("/api/v1/notifications/email-status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert "password" not in status_data
        assert "username" not in status_data
        assert "provider" in status_data
        assert "from_address" in status_data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_test_email_workflow(db_session: AsyncSession):
    """
    Step 4: Tests safe test-delivery workflow without contacting external employers.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Post test email
        test_res = await client.post(
            "/api/v1/notifications/test-email",
            json={"recipient": "test_candidate@example.com"},
        )
        assert test_res.status_code == 200
        res_data = test_res.json()
        assert res_data["success"] is True
        assert "test_candidate@example.com" in res_data["recipient"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_email_match_alert_delivery_and_deduplication(db_session: AsyncSession):
    """
    Step 4 & 5: Tests that eligible matches generate email notifications when enabled,
    adhere to score threshold, and prevent duplicate email dispatch.
    """
    cand = CandidateProfile(
        full_name="Frank Engineer",
        email="frank@example.com",
        location="Remote",
        work_authorization="US Citizen",
        summary="Senior Backend Developer",
        years_of_experience=6,
        notification_preferences={
            "email_enabled": True,
            "notify_new_matches": True,
            "delivery_mode": "IMMEDIATE",
            "min_match_score": 75,
            "recipient_email": "frank@example.com",
        },
    )
    db_session.add(cand)
    await db_session.flush()

    skill = CandidateSkill(
        candidate_id=cand.id,
        skill_name="Python",
        category="technical",
        years_experience=6.0,
        is_verified=True,
    )
    db_session.add(skill)

    src = JobSource(identifier="test_src_email", name="Test Email Source", base_url="https://example.com")
    db_session.add(src)
    await db_session.commit()

    # Job A: Score >= 75
    job_high = Job(
        source_id=src.id,
        external_id="job_high_match",
        title="Senior Python Architect",
        company="TechCorp",
        canonical_url="https://example.com/high",
        location="Remote",
        remote_type=RemoteType.REMOTE.value,
        description="Senior Python developer needed.",
    )
    db_session.add(job_high)
    await db_session.commit()

    matching = MatchingService()
    score_high = await matching.evaluate_job(session=db_session, job_id=job_high.id, candidate_id=cand.id, use_ai=False)
    assert score_high.overall_score >= 75

    # 1. First dispatch: should succeed and create an EMAIL notification record
    notif1 = await EmailService.send_match_notification(
        session=db_session, candidate=cand, job=job_high, match_score=score_high
    )
    assert notif1 is not None
    assert notif1.channel == NotificationChannel.EMAIL.value
    assert notif1.status == NotificationStatus.DELIVERED.value
    assert "TechCorp" in notif1.title

    # 2. Second dispatch for the SAME match: deduplication prevents re-sending
    notif2 = await EmailService.send_match_notification(
        session=db_session, candidate=cand, job=job_high, match_score=score_high
    )
    assert notif2 is None, "Repeated email notification must be deduplicated"


@pytest.mark.asyncio
async def test_email_failure_preserves_in_app_notification(db_session: AsyncSession):
    """
    Step 4: Tests that provider failure (e.g. SMTP connection timeout)
    does NOT crash the pipeline or delete/lose the in-app notification.
    """
    cand = CandidateProfile(
        full_name="Grace Developer",
        email="grace@example.com",
        location="Remote",
        work_authorization="US Citizen",
        summary="Python Engineer",
        years_of_experience=5,
        notification_preferences={
            "email_enabled": True,
            "notify_new_matches": True,
            "delivery_mode": "IMMEDIATE",
            "min_match_score": 60,
        },
    )
    db_session.add(cand)
    await db_session.flush()

    skill = CandidateSkill(
        candidate_id=cand.id,
        skill_name="Python",
        category="technical",
        years_experience=5.0,
        is_verified=True,
    )
    db_session.add(skill)

    src = JobSource(identifier="src_fail_test", name="Fail Test", base_url="https://example.com")
    db_session.add(src)
    await db_session.commit()

    job = Job(
        source_id=src.id,
        external_id="job_fail_test_1",
        title="Python Engineer",
        company="RobustCorp",
        canonical_url="https://example.com/fail",
        location="Remote",
        remote_type=RemoteType.REMOTE.value,
        description="Python Engineer needed.",
    )
    db_session.add(job)
    await db_session.commit()

    matching = MatchingService()
    score = await matching.evaluate_job(session=db_session, job_id=job.id, candidate_id=cand.id, use_ai=False)

    # Mock send_email to simulate SMTP crash / network timeout
    with patch.object(EmailService, "send_email", return_value=(False, "SMTP Connection Timed Out")):
        notif = await EmailService.send_match_notification(
            session=db_session, candidate=cand, job=job, match_score=score
        )
        assert notif is not None
        assert notif.status == NotificationStatus.FAILED.value
        assert "SMTP Connection Timed Out" in notif.metadata_json["error"]
