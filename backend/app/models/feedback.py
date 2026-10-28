import uuid
from typing import Optional, Dict, Any
from sqlalchemy import String, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin
from backend.app.models.enums import FeedbackType


class JobFeedback(Base, TimestampMixin):
    __tablename__ = "job_feedbacks"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_candidate_job_feedback"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    feedback_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=FeedbackType.RELEVANT.value, index=True
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    structured_details: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    job: Mapped["Job"] = relationship("Job", back_populates="feedbacks")
    candidate: Mapped["CandidateProfile"] = relationship("CandidateProfile")
