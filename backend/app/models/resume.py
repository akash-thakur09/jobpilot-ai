import uuid
from typing import Optional
from sqlalchemy import String, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin


class ResumeVersion(Base, TimestampMixin):
    __tablename__ = "resume_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    structured_content: Mapped[dict] = mapped_column(JSON, nullable=False)
    candidate_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    pdf_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_ats_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ats_extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ats_diagnostics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generator_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    job: Mapped["Job"] = relationship("Job", back_populates="resumes")
    applications: Mapped[list["Application"]] = relationship("Application", back_populates="resume_version")
