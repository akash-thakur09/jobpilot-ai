from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.services.notification_service import NotificationService
from backend.app.services.email_service import EmailService
from backend.app.services.candidate_service import CandidateService
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

    success, message = await EmailService.send_test_email(recipient)
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
    )

