from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobSourceConfigUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    board_token: Optional[str] = Field(
        None,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Employer token for Greenhouse (e.g. 'stripe')",
    )
    board_tokens: Optional[List[str]] = Field(
        None,
        description="Multiple employer tokens for Greenhouse",
    )
    site_token: Optional[str] = Field(
        None,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Employer token for Lever (e.g. 'netflix')",
    )
    site_tokens: Optional[List[str]] = Field(
        None,
        description="Multiple employer tokens for Lever",
    )
    count: Optional[int] = Field(None, ge=1, le=50, description="Item count for synthetic source")
    rss_url: Optional[str] = Field(None, description="Custom RSS/Atom feed URL")
    feed_url: Optional[str] = Field(None, description="Custom feed URL")
    publisher_id: Optional[str] = Field(None, description="Deprecated; Indeed operates via manual import")
    category: Optional[str] = Field(None, description="Category for Hirist / Indian sources")
    keywords: Optional[List[str]] = Field(None, description="Keywords for alert matching")
    location: Optional[str] = Field(None, description="Location preference for alert filter")
    model_config = ConfigDict(extra="allow")

    @field_validator("rss_url", "feed_url")
    @classmethod
    def validate_feed_url_ssrf(cls, v: Optional[str]) -> Optional[str]:
        if v:
            from backend.app.core.network_security import SafeFeedFetcher
            is_valid, reason = SafeFeedFetcher.validate_url(v)
            if not is_valid:
                raise ValueError(f"Disallowed feed URL: {reason}")
        return v


class JobSourceRead(BaseModel):
    id: str
    identifier: str
    name: str
    base_url: str
    rate_limit_rpm: int
    is_enabled: bool
    last_discovered_at: Optional[datetime] = None
    config_json: Dict[str, Any] = Field(default_factory=dict)
    last_status: Optional[str] = None
    last_error_summary: Optional[str] = None
    jobs_discovered_count: int = 0
    jobs_relevant_count: int = 0
    source_type: Optional[str] = "job_board"
    integration_status: Optional[str] = "AVAILABLE"
    model_config = ConfigDict(from_attributes=True)


class JobRead(BaseModel):
    id: str
    source_id: str
    external_id: str
    title: str
    company: str
    canonical_url: str
    location: str
    remote_type: str
    employment_type: str
    description: str
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: Optional[str] = None
    status: str
    relevance_score: Optional[float] = None
    relevance_classification: Optional[str] = None
    relevance_metadata: Optional[Dict[str, Any]] = None
    discovered_at: datetime
    posted_at: Optional[datetime] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    freshness_status: str = "ACTIVE"
    freshness_reason: Optional[str] = None
    last_verified_at: Optional[datetime] = None
    duplicate_cluster_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    items: List[JobRead]
    total: int
    limit: int
    offset: int


class JobDuplicateClusterRead(BaseModel):
    id: str
    canonical_job_id: Optional[str] = None
    cluster_status: str
    confidence: str
    confidence_score: float
    match_reasons: List[str] = Field(default_factory=list)
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime
    jobs: List[JobRead] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class DuplicateReviewRequest(BaseModel):
    action: str = Field(..., description="'CONFIRM' or 'DISMISS'")
    notes: Optional[str] = None


class JobFeedbackCreate(BaseModel):
    feedback_type: str = Field(..., description="RELEVANT, NOT_RELEVANT, ALREADY_APPLIED, NOT_INTERESTED, DUPLICATE_LISTING")
    reason: Optional[str] = None
    structured_details: Dict[str, Any] = Field(default_factory=dict)


class JobFeedbackRead(BaseModel):
    id: str
    candidate_id: str
    job_id: str
    feedback_type: str
    reason: Optional[str] = None
    structured_details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class JobFreshnessRead(BaseModel):
    job_id: str
    freshness_status: str
    freshness_reason: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    last_verified_at: Optional[datetime] = None
    posted_at: Optional[datetime] = None


class JobFreshnessVerifyResponse(BaseModel):
    job_id: str
    freshness_status: str
    freshness_reason: Optional[str] = None
    last_verified_at: Optional[datetime] = None
    verified_live: bool



class JobDiscoveryRequest(BaseModel):
    source_identifier: str = Field(..., description="e.g. 'synthetic', 'greenhouse', 'lever'")
    board_token: Optional[str] = Field(None, description="Employer token for Greenhouse (e.g. 'stripe')")
    board_tokens: Optional[List[str]] = Field(None, description="Multiple employer tokens for Greenhouse")
    site_token: Optional[str] = Field(None, description="Employer token for Lever (e.g. 'netflix')")
    site_tokens: Optional[List[str]] = Field(None, description="Multiple employer tokens for Lever")
    count: Optional[int] = Field(5, ge=1, le=50, description="For synthetic discovery")


class JobDiscoveryResponse(BaseModel):
    run_id: str
    source: str
    items_processed: int
    inserted: int
    updated: int
    unchanged: int
    failed: int
    status: str


class JobRelevanceRead(BaseModel):
    job_id: str
    relevance_score: float
    relevance_classification: str
    matched_roles: List[str] = Field(default_factory=list)
    matched_skills: List[str] = Field(default_factory=list)
    missing_priority_skills: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    component_scores: Dict[str, float] = Field(default_factory=dict)


class RelevanceReevaluationResponse(BaseModel):
    total_evaluated: int
    highly_relevant_count: int
    potentially_relevant_count: int
    low_relevance_count: int
    status: str = "COMPLETED"



class JobImportRequest(BaseModel):
    source_identifier: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        max_length=50,
        description="Target source identifier, e.g. 'naukri', 'instahyre', 'cutshort'",
    )
    format: str = Field(
        "json",
        pattern=r"^(json|email_text|html)$",
        description="Payload format: 'json' or 'email_text' or 'html'",
    )
    payload: Any = Field(..., description="JSON array of jobs (max 100), or raw email alert text/HTML string")

    @field_validator("payload")
    @classmethod
    def validate_payload_limits(cls, v: Any) -> Any:
        if isinstance(v, str):
            if len(v) > 500_000:
                raise ValueError("Payload exceeds maximum permitted size of 500,000 characters.")
        elif isinstance(v, list):
            if len(v) > 100:
                raise ValueError("Batch JSON import exceeds maximum limit of 100 items per request.")
        return v


class JobImportResponse(BaseModel):
    source_identifier: str
    items_received: int
    items_parsed: int
    items_saved: int
    items_relevant: int
    duplicates_detected: int
    errors: List[str] = Field(default_factory=list)
