import asyncio
import socket
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
import smtplib
from zoneinfo import ZoneInfo
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.main import app
from backend.app.models.candidate import CandidateProfile, CandidateSkill
from backend.app.models.enums import (
    NotificationChannel,
    NotificationStatus,
    NotificationType,
    RemoteType,
)
from backend.app.models.job import Job, JobSource
from backend.app.models.matching import MatchScore
from backend.app.models.notification import Notification
from backend.app.services.digest_service import DigestService
from backend.app.services.email_service import EmailDeliveryResult, EmailService
from backend.app.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_mock_and_console_status_semantics():
    """Verify that mock and console providers return SIMULATED status, never claiming real external delivery."""
    with patch.object(settings, "EMAIL_PROVIDER", "mock"):
        res_mock = await EmailService.send_email(
            to_email="test@example.com",
            subject="Test Mock Alert",
            body_text="Mock Body",
        )
        assert res_mock.success is True
        assert res_mock.status == NotificationStatus.SIMULATED
        assert res_mock.is_simulated is True
        assert "Simulated" in res_mock.status_detail

    with patch.object(settings, "EMAIL_PROVIDER", "console"):
        res_console = await EmailService.send_email(
            to_email="test@example.com",
            subject="Test Console Alert",
            body_text="Console Body",
        )
        assert res_console.success is True
        assert res_console.status == NotificationStatus.SIMULATED
        assert res_console.is_simulated is True


@pytest.mark.asyncio
async def test_successful_smtp_handoff_with_mocked_transport():
    """Verify that a successful SMTP transport handoff returns SENT, not DELIVERED (never overclaiming inbox delivery)."""
    with patch.object(settings, "EMAIL_PROVIDER", "smtp"), \
         patch.object(settings, "EMAIL_HOST", "smtp.testserver.local"), \
         patch.object(settings, "EMAIL_PORT", 587), \
         patch.object(settings, "EMAIL_USERNAME", "test_user"), \
         patch.object(settings, "EMAIL_PASSWORD", "secret"), \
         patch.object(settings, "EMAIL_USE_TLS", True):

        mock_smtp_inst = MagicMock()
        mock_smtp_inst.__enter__.return_value = mock_smtp_inst
        mock_smtp_inst.send_message.return_value = {}

        with patch("backend.app.services.email_service.smtplib.SMTP", return_value=mock_smtp_inst):
            res = await EmailService.send_email(
                to_email="recipient@domain.com",
                subject="SMTP Test",
                body_text="Testing SMTP Relay handoff",
            )
            assert res.success is True
            assert res.status == NotificationStatus.SENT
            assert res.is_simulated is False
            assert "Accepted by SMTP transport for relay" in res.status_detail
            mock_smtp_inst.starttls.assert_called_once()
            mock_smtp_inst.login.assert_called_once_with("test_user", "secret")
            mock_smtp_inst.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_transient_smtp_failure_bounded_retries():
    """Verify that transient SMTP failures trigger bounded retries with backoff and record attempt history."""
    with patch.object(settings, "EMAIL_PROVIDER", "smtp"), \
         patch.object(settings, "EMAIL_HOST", "smtp.testserver.local"), \
         patch.object(settings, "EMAIL_USERNAME", "test_user"), \
         patch.object(settings, "EMAIL_PASSWORD", "secret"):

        # Mock SMTP raising socket timeout on every attempt
        with patch("backend.app.services.email_service.smtplib.SMTP", side_effect=socket.timeout("Connection timed out")):
            res = await EmailService.send_email(
                to_email="recipient@domain.com",
                subject="Transient Error Test",
                body_text="Testing bounded retries",
                max_retries=2,
                backoff_base=0.01,  # fast test execution
            )
            assert res.success is False
            assert res.status == NotificationStatus.FAILED
            assert len(res.attempts) == 2  # Bounded to exactly 2 attempts
            assert all("Connection timed out" in a["error"] for a in res.attempts)
            assert all(a["is_transient"] is True for a in res.attempts)


@pytest.mark.asyncio
async def test_permanent_smtp_failure_no_retries():
    """Verify that permanent errors (e.g., authentication rejection) fail immediately without wasteful retries."""
    with patch.object(settings, "EMAIL_PROVIDER", "smtp"), \
         patch.object(settings, "EMAIL_HOST", "smtp.testserver.local"), \
         patch.object(settings, "EMAIL_USERNAME", "bad_user"), \
         patch.object(settings, "EMAIL_PASSWORD", "wrong_pass"):

        auth_error = smtplib.SMTPAuthenticationError(535, b"5.7.8 Error: authentication failed")
        with patch("backend.app.services.email_service.smtplib.SMTP", side_effect=auth_error):
            res = await EmailService.send_email(
                to_email="recipient@domain.com",
                subject="Permanent Error Test",
                body_text="Testing permanent error short-circuit",
                max_retries=3,
                backoff_base=0.01,
            )
            assert res.success is False
            assert res.status == NotificationStatus.FAILED
            assert len(res.attempts) == 1  # Exactly 1 attempt! No retries on permanent auth failure
            assert res.attempts[0]["is_transient"] is False
            assert "authentication" in res.error.lower() or "535" in res.error


@pytest.mark.asyncio
async def test_daily_digest_selection_and_coverage(db_session: AsyncSession):
    """Verify that daily digest selects eligible matches, filters by threshold, and links covered notifications."""
    cand = CandidateProfile(
        full_name="Alice Digest",
        email="alice@example.com",
        location="Remote",
        work_authorization="US Citizen",
        summary="Senior Backend Engineer",
        notification_preferences={
            "email_enabled": True,
            "notify_new_matches": True,
            "delivery_mode": "DAILY_DIGEST",
            "min_match_score": 70,
            "timezone": "UTC",
        },
    )
    db_session.add(cand)
    await db_session.flush()

    src = JobSource(identifier="src_digest_test", name="Digest Source", base_url="https://example.com")
    db_session.add(src)
    await db_session.commit()

    # Job 1: High match (85) -> should be included
    j1 = Job(
        source_id=src.id,
        external_id="djob_1",
        title="Python Architect",
        company="PyCorp",
        canonical_url="https://example.com/j1",
        location="Remote",
        remote_type=RemoteType.REMOTE.value,
        description="Python Architect",
    )
    # Job 2: Low match (60 < 70) -> should be excluded by threshold
    j2 = Job(
        source_id=src.id,
        external_id="djob_2",
        title="Junior Developer",
        company="DevCorp",
        canonical_url="https://example.com/j2",
        location="Remote",
        remote_type=RemoteType.REMOTE.value,
        description="Junior developer",
    )
    db_session.add_all([j1, j2])
    await db_session.commit()

    # Create in-app notifications
    notif1 = Notification(
        title="New Eligible Job Match: Python Architect",
        message="PyCorp is hiring",
        notification_type=NotificationType.NEW_MATCH.value,
        channel=NotificationChannel.IN_APP.value,
        status=NotificationStatus.PENDING.value,
        job_id=j1.id,
        dedup_key=f"match:{cand.id}:{j1.id}",
        metadata_json={"score": 85.0, "company": "PyCorp", "title": "Python Architect"},
    )
    notif2 = Notification(
        title="New Eligible Job Match: Junior Developer",
        message="DevCorp is hiring",
        notification_type=NotificationType.NEW_MATCH.value,
        channel=NotificationChannel.IN_APP.value,
        status=NotificationStatus.PENDING.value,
        job_id=j2.id,
        dedup_key=f"match:{cand.id}:{j2.id}",
        metadata_json={"score": 60.0, "company": "DevCorp", "title": "Junior Developer"},
    )
    db_session.add_all([notif1, notif2])
    await db_session.commit()

    # 1. Collect pending matches
    pending = await DigestService.collect_pending_digest_matches(db_session, cand)
    assert len(pending) == 1
    assert pending[0][0].id == j1.id

    # 2. Dispatch scheduled daily digest
    digest_notif = await DigestService.send_scheduled_digest_for_candidate(
        session=db_session,
        candidate=cand,
        period_override="daily",
        period_key_override="2026-10-28",
    )
    assert digest_notif is not None
    assert digest_notif.notification_type == NotificationType.DIGEST.value
    assert digest_notif.channel == NotificationChannel.EMAIL.value
    assert digest_notif.status == NotificationStatus.SIMULATED.value
    assert "Daily Digest" in digest_notif.title
    assert "PyCorp" in digest_notif.message

    # 3. Verify covered in-app notification is marked
    await db_session.refresh(notif1)
    assert notif1.digest_id == digest_notif.id
    assert notif1.digested_at is not None

    # Low-score notification was not covered
    await db_session.refresh(notif2)
    assert notif2.digest_id is None
    assert notif2.digested_at is None

    # 4. Verify exclusion: subsequent collect returns empty
    subsequent_pending = await DigestService.collect_pending_digest_matches(db_session, cand)
    assert len(subsequent_pending) == 0


@pytest.mark.asyncio
async def test_duplicate_digest_prevention_after_restart(db_session: AsyncSession):
    """Verify that repeated digest trigger attempts for the same period key do not re-send duplicate emails."""
    cand = CandidateProfile(
        full_name="Bob Restart",
        email="bob@example.com",
        location="Remote",
        work_authorization="US Citizen",
        summary="Backend Dev",
        notification_preferences={
            "email_enabled": True,
            "notify_new_matches": True,
            "delivery_mode": "DAILY_DIGEST",
            "min_match_score": 50,
        },
    )
    db_session.add(cand)
    await db_session.flush()

    src = JobSource(identifier="src_restart_test", name="Restart Source", base_url="https://example.com")
    db_session.add(src)
    await db_session.commit()

    job = Job(
        source_id=src.id,
        external_id="restart_job_1",
        title="Staff Engineer",
        company="SolidCorp",
        canonical_url="https://example.com/staff",
        location="Remote",
        remote_type=RemoteType.REMOTE.value,
        description="Staff Engineer",
    )
    db_session.add(job)
    await db_session.commit()

    notif = Notification(
        title="New Eligible Job Match: Staff Engineer",
        message="SolidCorp is hiring",
        notification_type=NotificationType.NEW_MATCH.value,
        channel=NotificationChannel.IN_APP.value,
        status=NotificationStatus.PENDING.value,
        job_id=job.id,
        dedup_key=f"match:{cand.id}:{job.id}",
        metadata_json={"score": 90.0},
    )
    db_session.add(notif)
    await db_session.commit()

    period_key = "2026-10-28"

    # First digest run
    d1 = await DigestService.send_scheduled_digest_for_candidate(
        session=db_session,
        candidate=cand,
        period_override="daily",
        period_key_override=period_key,
    )
    assert d1 is not None

    # Second digest run simulating server restart / catchup for the same period key
    d2 = await DigestService.send_scheduled_digest_for_candidate(
        session=db_session,
        candidate=cand,
        period_override="daily",
        period_key_override=period_key,
    )
    # Since notif is already digested, collect returns empty and returns None without re-sending
    assert d2 is None


@pytest.mark.asyncio
async def test_email_failure_preserves_in_app_notification_and_leaves_undigested(db_session: AsyncSession):
    """Verify that when email transport fails, in-app notifications remain uncorrupted and available for retry."""
    cand = CandidateProfile(
        full_name="Charlie Failure",
        email="charlie@example.com",
        location="Remote",
        work_authorization="US Citizen",
        summary="Backend Dev",
        notification_preferences={
            "email_enabled": True,
            "notify_new_matches": True,
            "delivery_mode": "DAILY_DIGEST",
            "min_match_score": 60,
        },
    )
    db_session.add(cand)
    await db_session.flush()

    src = JobSource(identifier="src_fail_test_digest", name="Fail Source", base_url="https://example.com")
    db_session.add(src)
    await db_session.commit()

    job = Job(
        source_id=src.id,
        external_id="fail_job_1",
        title="Cloud Architect",
        company="CloudyCorp",
        canonical_url="https://example.com/cloud",
        location="Remote",
        remote_type=RemoteType.REMOTE.value,
        description="Cloud Architect",
    )
    db_session.add(job)
    await db_session.commit()

    notif = Notification(
        title="New Eligible Job Match: Cloud Architect",
        message="CloudyCorp is hiring",
        notification_type=NotificationType.NEW_MATCH.value,
        channel=NotificationChannel.IN_APP.value,
        status=NotificationStatus.PENDING.value,
        job_id=job.id,
        dedup_key=f"match:{cand.id}:{job.id}",
        metadata_json={"score": 88.0},
    )
    db_session.add(notif)
    await db_session.commit()

    # Mock send_email to simulate transport failure
    failed_result = EmailDeliveryResult(
        success=False,
        status=NotificationStatus.FAILED,
        status_detail="SMTP connect error",
        error="SMTP connect error",
        is_simulated=False,
        attempts=[{"attempt": 1, "status": "FAILED", "detail": "SMTP connect error"}],
    )

    with patch.object(EmailService, "send_email", return_value=failed_result):
        d_res = await DigestService.send_scheduled_digest_for_candidate(
            session=db_session,
            candidate=cand,
            period_override="daily",
            period_key_override="2026-10-28",
        )
        assert d_res is not None
        assert d_res.status == NotificationStatus.FAILED.value

        # Crucial guarantee: In-app notification was NOT marked as digested!
        await db_session.refresh(notif)
        assert notif.digest_id is None
        assert notif.digested_at is None


@pytest.mark.asyncio
async def test_timezone_transition_and_dst_handling():
    """Verify timezone resolution and daylight saving time conversions for digest scheduling."""
    cand_ny = CandidateProfile(
        full_name="Dana Timezone",
        email="dana@example.com",
        location="New York",
        work_authorization="US Citizen",
        summary="Data Engineer",
        notification_preferences={
            "email_enabled": True,
            "delivery_mode": "DAILY_DIGEST",
            "timezone": "America/New_York",
        },
    )

    # 1. During Daylight Saving Time (e.g. July 15) -> UTC-4 (EDT)
    summer_ref = datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc)  # 04:00 AM EDT
    next_summer = DigestService.compute_next_digest_time(cand_ny, ref_time=summer_ref)
    assert next_summer is not None
    # 09:00 AM EDT is 13:00 UTC
    assert next_summer.hour == 13
    assert next_summer.minute == 0

    # 2. During Standard Time (e.g. January 15) -> UTC-5 (EST)
    winter_ref = datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)  # 03:00 AM EST
    next_winter = DigestService.compute_next_digest_time(cand_ny, ref_time=winter_ref)
    assert next_winter is not None
    # 09:00 AM EST is 14:00 UTC
    assert next_winter.hour == 14
    assert next_winter.minute == 0


@pytest.mark.asyncio
async def test_missed_digest_window_catchup_after_downtime(db_session: AsyncSession):
    """Verify that when backend recovers after a scheduled 09:00 window, it detects digest as due and catches up."""
    cand = CandidateProfile(
        full_name="Eve Catchup",
        email="eve@example.com",
        location="Remote",
        work_authorization="US Citizen",
        summary="DevOps Engineer",
        notification_preferences={
            "email_enabled": True,
            "delivery_mode": "DAILY_DIGEST",
            "timezone": "UTC",
        },
    )
    db_session.add(cand)
    await db_session.commit()

    # Time is 14:30 UTC, 09:00 has already passed while server was offline
    downtime_ref = datetime(2026, 10, 28, 14, 30, tzinfo=timezone.utc)

    is_due, period, key = await DigestService.is_digest_due_for_candidate(db_session, cand, ref_time=downtime_ref)
    assert is_due is True
    assert period == "daily"
    assert key == "2026-10-28"

    # Simulate sending digest for this catch-up window
    notif = Notification(
        title="Daily Job Digest",
        message="Catchup digest",
        notification_type=NotificationType.DIGEST.value,
        channel=NotificationChannel.EMAIL.value,
        status=NotificationStatus.SIMULATED.value,
        dedup_key=f"email_digest:{cand.id}:{period}:{key}",
    )
    db_session.add(notif)
    await db_session.commit()

    # Re-check: now that today's digest is recorded, it is no longer due!
    is_due_again, _, _ = await DigestService.is_digest_due_for_candidate(db_session, cand, ref_time=downtime_ref)
    assert is_due_again is False


@pytest.mark.asyncio
async def test_digest_and_delivery_history_api(client: AsyncClient, db_session: AsyncSession):
    """Verify REST API endpoints for digest status, manual trigger, and delivery history."""
    cand = CandidateProfile(
        full_name="Frank API",
        email="frank@example.com",
        location="Remote",
        work_authorization="US Citizen",
        summary="Fullstack Developer",
        notification_preferences={
            "email_enabled": True,
            "notify_new_matches": True,
            "delivery_mode": "DAILY_DIGEST",
            "min_match_score": 75,
            "timezone": "UTC",
        },
    )
    db_session.add(cand)
    await db_session.commit()

    # 1. GET /api/v1/notifications/digest/status
    res_status = await client.get("/api/v1/notifications/digest/status")
    assert res_status.status_code == 200
    st_data = res_status.json()
    assert st_data["email_enabled"] is True
    assert st_data["delivery_mode"] == "DAILY_DIGEST"
    assert st_data["timezone"] == "UTC"
    assert st_data["min_match_score"] == 75

    # 2. POST /api/v1/notifications/digest/trigger (no matches)
    res_trig_empty = await client.post("/api/v1/notifications/digest/trigger")
    assert res_trig_empty.status_code == 200
    assert res_trig_empty.json()["success"] is True

    # 3. Add eligible job and in-app notification
    src = JobSource(identifier="src_api_test", name="API Source", base_url="https://example.com")
    db_session.add(src)
    await db_session.commit()

    job = Job(
        source_id=src.id,
        external_id="api_job_1",
        title="React Developer",
        company="WebLabs",
        canonical_url="https://example.com/react",
        location="Remote",
        remote_type=RemoteType.REMOTE.value,
        description="React Developer",
    )
    db_session.add(job)
    await db_session.commit()

    in_app = Notification(
        title="New Eligible Job Match: React Developer",
        message="WebLabs is hiring",
        notification_type=NotificationType.NEW_MATCH.value,
        channel=NotificationChannel.IN_APP.value,
        status=NotificationStatus.PENDING.value,
        job_id=job.id,
        dedup_key=f"match:{cand.id}:{job.id}",
        metadata_json={"score": 82.0, "company": "WebLabs", "title": "React Developer"},
    )
    db_session.add(in_app)
    await db_session.commit()

    # 4. POST /api/v1/notifications/digest/trigger (with pending matches)
    res_trig = await client.post("/api/v1/notifications/digest/trigger?force=true")
    assert res_trig.status_code == 200
    trig_data = res_trig.json()
    assert trig_data["success"] is True
    assert trig_data["notification"] is not None
    assert trig_data["notification"]["status"] in {"SIMULATED", "SENT"}

    # 5. GET /api/v1/notifications/delivery-history
    res_hist = await client.get("/api/v1/notifications/delivery-history")
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert hist_data["total"] >= 1
    first_item = hist_data["items"][0]
    assert first_item["status"] in {"SIMULATED", "SENT"}
    assert first_item["channel"] == "EMAIL"
    assert first_item["is_simulated"] is True or first_item["status"] == "SENT"
