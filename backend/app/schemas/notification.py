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
    digest_id: Optional[str] = None
    digested_at: Optional[str] = None
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


class NotificationPreferences(BaseModel):
    email_enabled: bool = Field(False, description="Whether to send email alerts")
    notify_new_matches: bool = Field(True, description="Send alert for new eligible matches")
    notify_run_failures: bool = Field(True, description="Send alert for complete or partial discovery failures")
    notify_workflow_blockers: bool = Field(True, description="Send alert when application needs human action")
    delivery_mode: str = Field("IMMEDIATE", description="'IMMEDIATE', 'DAILY_DIGEST', or 'WEEKLY_DIGEST'")
    min_match_score: int = Field(70, ge=0, le=100, description="Minimum match score required for match notifications")
    recipient_email: Optional[str] = Field(None, description="Explicit recipient email override")
    timezone: str = Field("UTC", description="Configured candidate timezone e.g. UTC, America/New_York")


class NotificationPreferencesUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    notify_new_matches: Optional[bool] = None
    notify_run_failures: Optional[bool] = None
    notify_workflow_blockers: Optional[bool] = None
    delivery_mode: Optional[str] = Field(None, pattern=r"^(IMMEDIATE|DIGEST|DAILY_DIGEST|WEEKLY_DIGEST)$")
    min_match_score: Optional[int] = Field(None, ge=0, le=100)
    recipient_email: Optional[str] = None
    timezone: Optional[str] = None


class EmailConfigStatusResponse(BaseModel):
    is_available: bool
    provider: str
    from_address: str
    recipient: Optional[str] = None
    email_notifications_enabled: bool
    timezone: str = "UTC"


class TestEmailRequest(BaseModel):
    recipient: Optional[str] = None


class TestEmailResponse(BaseModel):
    success: bool
    message: str
    recipient: str
    provider: str
    delivery_status: str = "SIMULATED"


class DigestStatusResponse(BaseModel):
    email_enabled: bool
    delivery_mode: str
    timezone: str
    is_provider_configured: bool
    provider: str
    recipient: Optional[str] = None
    min_match_score: int
    pending_matches_count: int
    next_digest_at: Optional[str] = None
    last_digest_at: Optional[str] = None
    last_digest_status: Optional[str] = None


class DeliveryHistoryItem(BaseModel):
    id: str
    title: str
    channel: str
    status: str
    status_detail: Optional[str] = None
    provider: str
    recipient: Optional[str] = None
    sent_at: Optional[str] = None
    created_at: str
    attempt_count: int = 1
    attempts: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    is_simulated: bool = False
    digest_id: Optional[str] = None
    matches_count: Optional[int] = None


class DeliveryHistoryResponse(BaseModel):
    items: List[DeliveryHistoryItem]
    total: int


