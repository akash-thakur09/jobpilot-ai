import uuid
from typing import List, Optional
from sqlalchemy import String, Text, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin


class MatchScore(Base, TimestampMixin):
    __tablename__ = "match_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    matching_skills: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_skills: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_breakdown: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    job: Mapped["Job"] = relationship("Job", back_populates="match_scores")
