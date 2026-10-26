import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy import String, Text, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin
from backend.app.models.enums import EligibilityStatus


class MatchScore(Base, TimestampMixin):
    __tablename__ = "match_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    eligibility_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=EligibilityStatus.ELIGIBLE.value, index=True
    )
    eligibility_checks: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    scoring_breakdown: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    matching_skills: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_skills: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    matched_required_skills: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    matched_preferred_skills: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_required_skills: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_preferred_skills: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    uncertainties: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_policy_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    job_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    provider_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    job: Mapped["Job"] = relationship("Job", back_populates="match_scores")
