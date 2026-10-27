import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.app.models.notification import Notification
from backend.app.models.enums import NotificationChannel, NotificationStatus, NotificationType
from backend.app.core.logging import logger


class NotificationService:
    """
    Persistent notification service providing in-app notifications with
    database-backed transactional deduplication, sanitization, and read/dismiss management.
    """

    @staticmethod
    def sanitize_text(text: str) -> str:
        """Sanitizes text by masking potential secrets, tokens, credentials, or file paths."""
        if not text:
            return ""
        # Redact potential authorization tokens / bearer / api keys
        sanitized = re.sub(r"(?i)(bearer|token|key|secret|password|credential)[\s:=]+([a-zA-Z0-9_\-\.]{8,})", r"\1: [REDACTED]", text)
        # Redact full stack traces if any
        if "Traceback (most recent call last):" in sanitized:
            lines = sanitized.splitlines()
            last_line = lines[-1] if lines else "Internal execution error"
            sanitized = f"Error occurred: {last_line}"
        return sanitized

    @classmethod
    async def create_notification(
        cls,
        session: AsyncSession,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.NEW_MATCH,
        channel: NotificationChannel = NotificationChannel.IN_APP,
        job_id: Optional[str] = None,
        application_id: Optional[str] = None,
        run_id: Optional[str] = None,
        dedup_key: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """
        Creates a notification idempotently using database-backed deduplication.
        If dedup_key is supplied and already exists, returns the existing record.
        """
        sanitized_title = cls.sanitize_text(title)
        sanitized_message = cls.sanitize_text(message)
        metadata = metadata_json or {}

        # 1. If dedup_key provided, check if it already exists
        if dedup_key:
            stmt = select(Notification).where(Notification.dedup_key == dedup_key)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                logger.debug(f"Notification with dedup_key '{dedup_key}' already exists; returning existing.")
                return existing

        notification = Notification(
            title=sanitized_title,
            message=sanitized_message,
            notification_type=notification_type.value,
            channel=channel.value,
            status=NotificationStatus.DELIVERED.value if channel == NotificationChannel.IN_APP else NotificationStatus.PENDING.value,
            is_read=False,
            is_dismissed=False,
            job_id=job_id,
            application_id=application_id,
            run_id=run_id,
            dedup_key=dedup_key,
            metadata_json=metadata,
        )

        session.add(notification)
        try:
            await session.commit()
            await session.refresh(notification)
            logger.info(f"Created notification '{notification.id}' of type '{notification.notification_type}'")
            return notification
        except IntegrityError:
            await session.rollback()
            # Concurrent insert with same dedup_key
            if dedup_key:
                stmt = select(Notification).where(Notification.dedup_key == dedup_key)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                if existing:
                    return existing
            raise

    @classmethod
    async def list_notifications(
        cls,
        session: AsyncSession,
        is_read: Optional[bool] = None,
        is_dismissed: Optional[bool] = False,
        notification_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Notification], int]:
        """
        Lists notifications with pagination and filtering.
        Returns (list_of_notifications, total_count).
        """
        filters = []
        if is_read is not None:
            filters.append(Notification.is_read == is_read)
        if is_dismissed is not None:
            filters.append(Notification.is_dismissed == is_dismissed)
        if notification_type is not None:
            filters.append(Notification.notification_type == notification_type)

        # Count total
        count_query = select(func.count(Notification.id))
        if filters:
            count_query = count_query.where(and_(*filters))
        total_count_res = await session.execute(count_query)
        total_count = total_count_res.scalar() or 0

        # Fetch records
        query = select(Notification)
        if filters:
            query = query.where(and_(*filters))
        query = query.order_by(Notification.created_at.desc()).limit(limit).offset(offset)

        result = await session.execute(query)
        items = list(result.scalars().all())
        return items, total_count

    @classmethod
    async def get_unread_count(cls, session: AsyncSession) -> int:
        """Returns the count of unread, non-dismissed notifications."""
        query = select(func.count(Notification.id)).where(
            Notification.is_read == False,
            Notification.is_dismissed == False,
        )
        result = await session.execute(query)
        return result.scalar() or 0

    @classmethod
    async def mark_as_read(cls, session: AsyncSession, notification_id: str) -> Optional[Notification]:
        """Marks a single notification as read."""
        stmt = select(Notification).where(Notification.id == notification_id)
        result = await session.execute(stmt)
        notification = result.scalar_one_or_none()
        if not notification:
            return None

        notification.is_read = True
        await session.commit()
        await session.refresh(notification)
        return notification

    @classmethod
    async def mark_all_as_read(cls, session: AsyncSession) -> int:
        """Marks all notifications as read. Returns count of modified records."""
        stmt = (
            update(Notification)
            .where(Notification.is_read == False)
            .values(is_read=True)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount or 0

    @classmethod
    async def dismiss(cls, session: AsyncSession, notification_id: str) -> Optional[Notification]:
        """Dismisses a notification (hides from active view)."""
        stmt = select(Notification).where(Notification.id == notification_id)
        result = await session.execute(stmt)
        notification = result.scalar_one_or_none()
        if not notification:
            return None

        notification.is_dismissed = True
        notification.is_read = True
        await session.commit()
        await session.refresh(notification)
        return notification
