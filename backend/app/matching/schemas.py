import enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, model_validator


class EligibilityStatus(str, enum.Enum):
    ELIGIBLE = "ELIGIBLE"
    DISQUALIFIED = "DISQUALIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class RuleCheckStatus(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EligibilityCheckResult(BaseModel):
    rule_id: str
    status: RuleCheckStatus
    reason: str
    evidence: Optional[str] = None
    is_hard_constraint: bool = True


class ScoringWeights(BaseModel):
    skills: float = Field(0.40, ge=0.0, le=1.0)
    title: float = Field(0.20, ge=0.0, le=1.0)
    experience: float = Field(0.15, ge=0.0, le=1.0)
    projects: float = Field(0.10, ge=0.0, le=1.0)
    location_remote: float = Field(0.10, ge=0.0, le=1.0)
    salary: float = Field(0.05, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "ScoringWeights":
        total = round(
            self.skills
            + self.title
            + self.experience
            + self.projects
            + self.location_remote
            + self.salary,
            4,
        )
        if total != 1.0:
            raise ValueError(f"Scoring weights must sum to 1.0, current sum is {total}")
        return self


class ScoreBreakdown(BaseModel):
    skills_score: float = Field(..., ge=0.0, le=100.0)
    title_score: float = Field(..., ge=0.0, le=100.0)
    experience_score: float = Field(..., ge=0.0, le=100.0)
    projects_score: float = Field(..., ge=0.0, le=100.0)
    location_remote_score: float = Field(..., ge=0.0, le=100.0)
    salary_score: float = Field(..., ge=0.0, le=100.0)
    final_score: float = Field(..., ge=0.0, le=100.0)
    preference_contributions: Dict[str, Any] = Field(default_factory=dict)
    positive_contributions: List[str] = Field(default_factory=list)
    negative_contributions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    freshness_warning: Optional[str] = None
    duplicate_warning: Optional[str] = None
    feedback_adjustment: Optional[float] = None
    feedback_note: Optional[str] = None
    scoring_policy_version: str = "1.1.0"


class MatchEvaluationResult(BaseModel):
    job_id: str
    candidate_id: str
    candidate_profile_version: Optional[str] = None
    job_fingerprint: Optional[str] = None
    is_eligible: bool
    eligibility_status: EligibilityStatus
    eligibility_checks: List[EligibilityCheckResult] = Field(default_factory=list)
    overall_score: float = Field(..., ge=0.0, le=100.0)
    score_breakdown: ScoreBreakdown
    matched_required_skills: List[str] = Field(default_factory=list)
    matched_preferred_skills: List[str] = Field(default_factory=list)
    missing_required_skills: List[str] = Field(default_factory=list)
    missing_preferred_skills: List[str] = Field(default_factory=list)
    relevant_experience: List[str] = Field(default_factory=list)
    relevant_projects: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    explanation: str
    scoring_policy_version: str = "1.1.0"
    provider_metadata: Dict[str, Any] = Field(default_factory=dict)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MatchScoreRead(BaseModel):
    id: str
    job_id: str
    candidate_id: str
    overall_score: float
    is_eligible: bool
    eligibility_status: str
    eligibility_checks: List[Dict[str, Any]]
    scoring_breakdown: Dict[str, Any]
    matching_skills: List[str]
    missing_skills: List[str]
    matched_required_skills: List[str]
    matched_preferred_skills: List[str]
    missing_required_skills: List[str]
    missing_preferred_skills: List[str]
    uncertainties: List[str]
    warnings: List[str]
    explanation: str
    scoring_policy_version: str
    job_fingerprint: Optional[str] = None
    provider_metadata: Dict[str, Any]
    is_latest: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
