"""
JobPilot AI - Application Workflow API Schemas
Pydantic schemas for application preparation, review, approval, execution attempts,
events, and outcome reconciliation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ApplicationPrepareRequest(BaseModel):
    job_id: str = Field(..., description="Unique ID of the job listing to prepare application for.")
    candidate_id: Optional[str] = Field(None, description="Explicit candidate profile ID. Required if multiple profiles exist.")
    force_regenerate_resume: bool = Field(False, description="Forces regeneration of tailored resume version.")


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    job_id: str
    resume_version_id: Optional[str] = None
    selected_resume_sha256: Optional[str] = None
    status: str
    submission_method: str
    submitted_at: Optional[datetime] = None
    confirmation_evidence: Optional[Dict[str, Any]] = None
    approval_fingerprint: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_metadata: Dict[str, Any] = Field(default_factory=dict)
    job_title: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ApplicationListResponse(BaseModel):
    items: List[ApplicationRead]
    total: int
    limit: int
    offset: int


class ApplicationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    from_status: Optional[str] = None
    to_status: str
    actor: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ApplicationEventListResponse(BaseModel):
    items: List[ApplicationEventRead]
    total: int
    limit: int
    offset: int


class SubmissionAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    attempt_number: int
    adapter_identifier: str
    selected_resume_version_id: str
    uploaded_artifact_sha256: str
    outcome: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    confirmation_reference: Optional[str] = None
    confirmation_payload: Dict[str, Any] = Field(default_factory=dict)
    sanitized_diagnostics: Dict[str, Any] = Field(default_factory=dict)
    reconciliation_metadata: Dict[str, Any] = Field(default_factory=dict)


class SubmissionAttemptListResponse(BaseModel):
    items: List[SubmissionAttemptRead]
    total: int
    limit: int
    offset: int


class ApplicationAttemptRequest(BaseModel):
    target_url: Optional[str] = Field(None, description="Optional target URL for synthetic test execution. Must be local (127.0.0.1 or localhost).")
    is_synthetic: Optional[bool] = Field(None, description="Whether to execute an isolated synthetic submission simulation without external network calls.")


class ApplicationReconcileRequest(BaseModel):
    target_status: str = Field(..., description="Target status to reconcile to (e.g. SUBMITTED, READY_FOR_REVIEW, FAILED).")
    reconciliation_evidence: Dict[str, Any] = Field(default_factory=dict, description="Verified reconciliation evidence.")
    notes: Optional[str] = Field(None, description="Explanation or manual audit notes.")
