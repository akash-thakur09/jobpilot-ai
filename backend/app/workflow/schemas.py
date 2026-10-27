"""
JobPilot AI - Application Workflow Schemas
Pydantic schemas for prepared form data, review payload, and approval requests.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PreparedFormField(BaseModel):
    value: Any
    provenance: str
    is_verified: bool = True
    description: Optional[str] = None


class PreparedApplicationFormData(BaseModel):
    fields: Dict[str, PreparedFormField] = Field(default_factory=dict)
    unanswered_fields: List[str] = Field(default_factory=list)


class ApplicationReviewPayload(BaseModel):
    application_id: str
    candidate_id: str
    job_id: str
    status: str
    employer: str
    job_title: str
    job_url: str
    job_fingerprint: str
    eligibility_status: str
    eligibility_reason: str
    match_score: float
    match_explanation: str
    selected_resume_version_id: str
    resume_sha256: str
    resume_integrity_valid: bool
    resume_factual_validation_valid: bool
    keyword_coverage_summary: Dict[str, Any] = Field(default_factory=dict)
    canonical_approval_fingerprint: str
    prepared_form_data: Dict[str, Any] = Field(default_factory=dict)
    unanswered_questions: List[str] = Field(default_factory=list)
    review_warnings: List[str] = Field(default_factory=list)
    is_approvable: bool
    approvable_reason: str
    approved_at: Optional[datetime] = None
    approved_fingerprint: Optional[str] = None


class ApplicationApproveRequest(BaseModel):
    reviewed_fingerprint: str
    approval_metadata: Optional[Dict[str, Any]] = None
