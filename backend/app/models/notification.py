import uuid
from typing import Optional
from sqlalchemy import String, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin
from backend.app.models.enums import NotificationChannel, NotificationStatus, NotificationType


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    notification_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=NotificationType.NEW_MATCH.value, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default=NotificationChannel.IN_APP.value)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=NotificationStatus.PENDING.value, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    # Optional references
    job_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    application_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("automation_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Unique deduplication key for idempotent creation across runs/retries
    dedup_key: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )

    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    job = relationship("Job", backref="notifications")
    application = relationship("Application", backref="notifications")
    run = relationship("AutomationRun", backref="notifications")

