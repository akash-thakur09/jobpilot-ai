import uuid
from typing import Optional
from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base, TimestampMixin
from backend.app.models.enums import NotificationChannel, NotificationStatus


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default=NotificationChannel.IN_APP.value)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=NotificationStatus.PENDING.value, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
