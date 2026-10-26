from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class TailoredExperience(BaseModel):
    company: str
    role: str
    location: Optional[str] = None
    start_date: str
    end_date: Optional[str] = None
    is_current: bool = False
    bullet_points: List[str] = Field(default_factory=list)


class TailoredProject(BaseModel):
    title: str
    technologies: List[str] = Field(default_factory=list)
    description: str
    bullet_points: List[str] = Field(default_factory=list)
    url: Optional[str] = None


class TailoredEducation(BaseModel):
    institution: str
    degree: str
    field_of_study: str
    graduation_year: int


class TailoredResumeContent(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    location: str
    links: List[str] = Field(default_factory=list)
    summary: str
    skills_by_category: Dict[str, List[str]] = Field(default_factory=dict)
    experiences: List[TailoredExperience] = Field(default_factory=list)
    projects: List[TailoredProject] = Field(default_factory=list)
    educations: List[TailoredEducation] = Field(default_factory=list)


class FactualValidationReport(BaseModel):
    is_valid: bool
    supported_claims_count: int
    unsupported_claims: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    checked_facts: Dict[str, Any] = Field(default_factory=dict)


class KeywordCoverageReport(BaseModel):
    matched_required_keywords: List[str] = Field(default_factory=list)
    matched_preferred_keywords: List[str] = Field(default_factory=list)
    missing_required_keywords: List[str] = Field(default_factory=list)
    coverage_score: float = Field(..., ge=0.0, le=100.0)


class ResumeGenerateRequest(BaseModel):
    job_id: str
    use_ai: bool = True
    force_regenerate: bool = False


class ResumeVersionRead(BaseModel):
    id: str
    candidate_id: str
    job_id: str
    match_score_id: Optional[str] = None
    version_number: int
    file_sha256: str
    pdf_file_path: str
    is_ats_valid: bool
    is_submission_ready: bool
    ats_extracted_text: Optional[str] = None
    structured_content: Dict[str, Any]
    candidate_snapshot: Dict[str, Any]
    factual_validation_result: Dict[str, Any]
    keyword_coverage_result: Dict[str, Any]
    generator_metadata: Dict[str, Any]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
