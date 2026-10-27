import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.main import app
from backend.app.models.enums import NotificationType, NotificationChannel
from backend.app.services.notification_service import NotificationService
from backend.app.db.session import get_db


@pytest.mark.asyncio
async def test_notification_service_create_and_deduplication(db_session: AsyncSession):
    """Verifies that NotificationService creates notifications and deduplicates on dedup_key."""
    notif1 = await NotificationService.create_notification(
        session=db_session,
        title="New Job Match",
        message="A high match score was found for Senior Engineer.",
        notification_type=NotificationType.NEW_MATCH,
        dedup_key="unique_match_key_1",
    )
    assert notif1.id is not None
    assert notif1.title == "New Job Match"
    assert notif1.is_read is False
    assert notif1.is_dismissed is False

    # Second creation with identical dedup_key must return existing record
    notif2 = await NotificationService.create_notification(
        session=db_session,
        title="Duplicate Match Attempt",
        message="Different message.",
        notification_type=NotificationType.NEW_MATCH,
        dedup_key="unique_match_key_1",
    )
    assert notif2.id == notif1.id
    assert notif2.title == "New Job Match"  # Preserved original


@pytest.mark.asyncio
async def test_notification_service_sanitization():
    """Verifies that potential secrets and exception traces are masked."""
    secret_text = "Failed to connect: bearer sk_live_secret123456789 and token: my_secret_token_123"
    sanitized = NotificationService.sanitize_text(secret_text)
    assert "sk_live_secret123456789" not in sanitized
    assert "[REDACTED]" in sanitized

    traceback_text = "Traceback (most recent call last):\n  File 'app.py', line 10\nConnectionRefusedError: Host down"
    sanitized_tb = NotificationService.sanitize_text(traceback_text)
    assert "Traceback" not in sanitized_tb
    assert "ConnectionRefusedError: Host down" in sanitized_tb


@pytest.mark.asyncio
async def test_notification_service_read_and_dismiss_lifecycle(db_session: AsyncSession):
    """Tests mark_as_read, mark_all_as_read, and dismiss functionality."""
    n1 = await NotificationService.create_notification(
        session=db_session,
        title="Notification 1",
        message="Msg 1",
        dedup_key="test_lifecycle_1",
    )
    n2 = await NotificationService.create_notification(
        session=db_session,
        title="Notification 2",
        message="Msg 2",
        dedup_key="test_lifecycle_2",
    )

    # Initial unread count
    unread = await NotificationService.get_unread_count(db_session)
    assert unread >= 2

    # Mark n1 as read
    marked = await NotificationService.mark_as_read(db_session, n1.id)
    assert marked.is_read is True

    # Dismiss n2 (which also marks as read)
    dismissed = await NotificationService.dismiss(db_session, n2.id)
    assert dismissed.is_dismissed is True
    assert dismissed.is_read is True


@pytest.mark.asyncio
async def test_notifications_api_endpoints(db_session: AsyncSession):
    """Tests /api/v1/notifications endpoints using AsyncClient."""
    n = await NotificationService.create_notification(
        session=db_session,
        title="API Notification",
        message="Testing via HTTP",
        dedup_key="api_test_key_1",
    )

    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unread count
        res = await client.get("/api/v1/notifications/unread-count")
        assert res.status_code == 200
        assert res.json()["unread_count"] >= 1

        # 2. List notifications
        res = await client.get("/api/v1/notifications")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        assert any(item["id"] == n.id for item in data["items"])

        # 3. Mark single as read
        res = await client.post(f"/api/v1/notifications/{n.id}/read")
        assert res.status_code == 200
        assert res.json()["notification"]["is_read"] is True

        # 4. Mark all as read
        res = await client.post("/api/v1/notifications/read-all")
        assert res.status_code == 200
        assert res.json()["success"] is True

        # 5. Dismiss notification
        res = await client.post(f"/api/v1/notifications/{n.id}/dismiss")
        assert res.status_code == 200
        assert res.json()["notification"]["is_dismissed"] is True

    app.dependency_overrides.clear()
