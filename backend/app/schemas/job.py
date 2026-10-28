from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class JobSourceConfigUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    board_token: Optional[str] = Field(
        None,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Employer token for Greenhouse (e.g. 'stripe')",
    )
    site_token: Optional[str] = Field(
        None,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Employer token for Lever (e.g. 'netflix')",
    )
    count: Optional[int] = Field(None, ge=1, le=50, description="Item count for synthetic source")


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


class JobDiscoveryRequest(BaseModel):
    source_identifier: str = Field(..., description="e.g. 'synthetic', 'greenhouse', 'lever'")
    board_token: Optional[str] = Field(None, description="Employer token for Greenhouse (e.g. 'stripe')")
    site_token: Optional[str] = Field(None, description="Employer token for Lever (e.g. 'netflix')")
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
