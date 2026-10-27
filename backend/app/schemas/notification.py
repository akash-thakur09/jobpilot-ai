from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: str
    notification_type: str
    title: str
    message: str
    channel: str
    status: str
    is_read: bool
    is_dismissed: bool
    job_id: Optional[str] = None
    application_id: Optional[str] = None
    run_id: Optional[str] = None
    dedup_key: Optional[str] = None
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    unread_count: int
    limit: int
    offset: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkReadResponse(BaseModel):
    success: bool
    notification: Optional[NotificationResponse] = None
    updated_count: Optional[int] = None
