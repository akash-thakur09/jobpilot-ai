from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SchedulerStatusResponse(BaseModel):
    is_enabled: bool
    scheduler_running: bool
    is_active_run: bool
    interval_minutes: int
    next_run_time: Optional[str] = None
    last_run: Optional[Dict[str, Any]] = None


class SchedulerConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = Field(None, ge=5, le=10080, description="Discovery interval in minutes (5 to 10080)")


class SchedulerRunRequest(BaseModel):
    sources: Optional[List[str]] = Field(None, description="Specific sources to run (e.g. ['synthetic', 'greenhouse', 'lever'])")
    use_ai_matching: bool = Field(False, description="Whether to perform optional AI semantic analysis")


class AutomationRunItem(BaseModel):
    id: str
    run_type: str
    status: str
    items_processed: int
    items_succeeded: int
    items_failed: int
    error_summary: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AutomationRunListResponse(BaseModel):
    items: List[AutomationRunItem]
    total: int
    limit: int
    offset: int
