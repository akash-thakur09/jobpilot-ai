import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy import String, Text, Boolean, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin


class ResumeVersion(Base, TimestampMixin):
    __tablename__ = "resume_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    match_score_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("match_scores.id", ondelete="SET NULL"), nullable=True, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    structured_content: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    candidate_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    pdf_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_ats_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_submission_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ats_extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ats_diagnostics: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    factual_validation_result: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    keyword_coverage_result: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    generator_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    job_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tailoring_policy_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")

    job: Mapped["Job"] = relationship("Job", back_populates="resumes")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="resume_version")
