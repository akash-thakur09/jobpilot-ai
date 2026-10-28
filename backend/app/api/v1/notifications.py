from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.enums import NotificationChannel, NotificationType
from backend.app.models.notification import Notification
from backend.app.services.notification_service import NotificationService
from backend.app.services.email_service import EmailService
from backend.app.services.candidate_service import CandidateService
from backend.app.services.digest_service import DigestService
from backend.app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    UnreadCountResponse,
    MarkReadResponse,
    NotificationPreferences,
    NotificationPreferencesUpdate,
    EmailConfigStatusResponse,
    TestEmailRequest,
    TestEmailResponse,
    DigestStatusResponse,
    DeliveryHistoryItem,
    DeliveryHistoryResponse,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _to_response(n) -> NotificationResponse:
    return NotificationResponse(
        id=n.id,
        notification_type=n.notification_type,
        title=n.title,
        message=n.message,
        channel=n.channel,
        status=n.status,
        is_read=n.is_read,
        is_dismissed=n.is_dismissed,
        job_id=n.job_id,
        application_id=n.application_id,
        run_id=n.run_id,
        dedup_key=n.dedup_key,
        created_at=n.created_at.isoformat() if n.created_at else "",
        updated_at=n.updated_at.isoformat() if n.updated_at else "",
        metadata=n.metadata_json or {},
    )


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    is_read: Optional[bool] = Query(None),
    is_dismissed: Optional[bool] = Query(False),
    notification_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """Lists notifications with filtering and pagination."""
    items, total = await NotificationService.list_notifications(
        session=session,
        is_read=is_read,
        is_dismissed=is_dismissed,
        notification_type=notification_type,
        limit=limit,
        offset=offset,
    )
    unread_count = await NotificationService.get_unread_count(session)

    return NotificationListResponse(
        items=[_to_response(n) for n in items],
        total=total,
        unread_count=unread_count,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(session: AsyncSession = Depends(get_db)):
    """Returns the total number of unread, non-dismissed notifications."""
    count = await NotificationService.get_unread_count(session)
    return UnreadCountResponse(unread_count=count)


@router.post("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_as_read(
    notification_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Marks a single notification as read."""
    notification = await NotificationService.mark_as_read(session, notification_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found.",
        )
    return MarkReadResponse(success=True, notification=_to_response(notification))


@router.post("/read-all", response_model=MarkReadResponse)
async def mark_all_as_read(session: AsyncSession = Depends(get_db)):
    """Marks all unread notifications as read."""
    count = await NotificationService.mark_all_as_read(session)
    return MarkReadResponse(success=True, updated_count=count)


@router.post("/{notification_id}/dismiss", response_model=MarkReadResponse)
async def dismiss_notification(
    notification_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Dismisses a notification from the active view."""
    notification = await NotificationService.dismiss(session, notification_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found.",
        )
    return MarkReadResponse(success=True, notification=_to_response(notification))


# ---------------------------------------------------------------------------
# Notification Preferences & Email Status
# ---------------------------------------------------------------------------
@router.get("/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(session: AsyncSession = Depends(get_db)):
    """Retrieve candidate notification preferences."""
    profile = await CandidateService.get_profile(session)
    if not profile:
        return NotificationPreferences()
    prefs = dict(profile.notification_preferences or {})
    return NotificationPreferences(**prefs)


@router.put("/preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    preferences: NotificationPreferencesUpdate, session: AsyncSession = Depends(get_db)
):
    """Updates candidate notification preferences."""
    profile = await CandidateService.get_profile(session)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not found.",
        )
    current = dict(profile.notification_preferences or {})
    current.update(preferences.model_dump(exclude_unset=True))
    profile.notification_preferences = current
    await session.commit()
    await session.refresh(profile)
    return NotificationPreferences(**profile.notification_preferences)


@router.get("/email-status", response_model=EmailConfigStatusResponse)
async def get_email_status(session: AsyncSession = Depends(get_db)):
    """Returns email configuration status without exposing credentials."""
    profile = await CandidateService.get_profile(session)
    status_info = EmailService.get_email_config_status(profile)
    return EmailConfigStatusResponse(**status_info)


@router.post("/test-email", response_model=TestEmailResponse)
async def send_test_email(
    request: TestEmailRequest, session: AsyncSession = Depends(get_db)
):
    """Sends a safe test alert email verifying channel operation without contacting employers."""
    profile = await CandidateService.get_profile(session)
    recipient = request.recipient or (profile.email if profile else None)
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No recipient email address available.",
        )

    success, message, delivery_status = await EmailService.send_test_email(recipient)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message,
        )

    return TestEmailResponse(
        success=True,
        message=message,
        recipient=recipient,
        provider=EmailService.get_email_config_status(profile)["provider"],
        delivery_status=delivery_status.value if hasattr(delivery_status, "value") else str(delivery_status),
    )


@router.get("/digest/status", response_model=DigestStatusResponse)
async def get_digest_status(session: AsyncSession = Depends(get_db)):
    """Returns digest configuration status, next scheduled run, and pending matches count."""
    profile = await CandidateService.get_profile(session)
    prefs = dict(profile.notification_preferences or {}) if profile else {}
    email_cfg = EmailService.get_email_config_status(profile)

    pending_matches = []
    if profile:
        pending_matches = await DigestService.collect_pending_digest_matches(session, profile)

    next_time = DigestService.compute_next_digest_time(profile) if profile else None

    # Query last digest record
    last_digest_q = (
        select(Notification)
        .where(
            Notification.channel == NotificationChannel.EMAIL.value,
            Notification.notification_type == NotificationType.DIGEST.value,
        )
        .order_by(Notification.created_at.desc())
        .limit(1)
    )
    last_digest_res = await session.execute(last_digest_q)
    last_digest = last_digest_res.scalar_one_or_none()

    return DigestStatusResponse(
        email_enabled=prefs.get("email_enabled", False),
        delivery_mode=prefs.get("delivery_mode", "IMMEDIATE"),
        timezone=prefs.get("timezone") or settings.TIMEZONE,
        is_provider_configured=email_cfg["is_available"],
        provider=email_cfg["provider"],
        recipient=prefs.get("recipient_email") or email_cfg.get("recipient") or (profile.email if profile else None),
        min_match_score=prefs.get("min_match_score", settings.MATCH_NOTIFICATION_THRESHOLD),
        pending_matches_count=len(pending_matches),
        next_digest_at=next_time.isoformat() if next_time else None,
        last_digest_at=last_digest.created_at.isoformat() if last_digest and last_digest.created_at else None,
        last_digest_status=last_digest.status if last_digest else None,
    )


@router.post("/digest/trigger")
async def trigger_digest_now(
    force: bool = Query(False, description="Force send digest even if no new pending matches exist"),
    session: AsyncSession = Depends(get_db),
):
    """Manually triggers an immediate digest delivery for candidate testing or catch-up."""
    profile = await CandidateService.get_profile(session)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found.")

    notif = await DigestService.send_scheduled_digest_for_candidate(session, profile, force=force)
    if not notif:
        return {
            "success": True,
            "message": "No pending eligible matches met criteria. No digest email was required.",
            "notification": None,
        }

    return {
        "success": True,
        "message": f"Digest processed with status: {notif.status}",
        "notification": _to_response(notif),
    }


@router.get("/delivery-history", response_model=DeliveryHistoryResponse)
async def get_delivery_history(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """Retrieves recent email delivery history records including simulated, sent, and failed attempts."""
    query = (
        select(Notification)
        .where(Notification.channel == NotificationChannel.EMAIL.value)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    res = await session.execute(query)
    items = res.scalars().all()

    history_items = []
    for it in items:
        meta = it.metadata_json or {}
        history_items.append(
            DeliveryHistoryItem(
                id=it.id,
                title=it.title,
                channel=it.channel,
                status=it.status,
                status_detail=meta.get("status_detail"),
                provider=meta.get("provider", "unknown"),
                recipient=meta.get("recipient"),
                sent_at=meta.get("sent_at") or (it.created_at.isoformat() if it.created_at else None),
                created_at=it.created_at.isoformat() if it.created_at else "",
                attempt_count=meta.get("attempt_count", 1),
                attempts=meta.get("attempts", []),
                error=meta.get("error"),
                is_simulated=meta.get("is_simulated", False),
                digest_id=it.digest_id,
                matches_count=meta.get("matches_count"),
            )
        )

    return DeliveryHistoryResponse(items=history_items, total=len(history_items))


