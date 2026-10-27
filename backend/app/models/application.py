import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import String, Text, Integer, ForeignKey, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin
from backend.app.models.enums import ApplicationStatus


class Application(Base, TimestampMixin):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_candidate_job_application"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    resume_version_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("resume_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    selected_resume_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ApplicationStatus.PREPARING.value, index=True
    )
    submission_method: Mapped[str] = mapped_column(String(50), nullable=False, default="BROWSER_AUTOMATION")
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Cryptographic Approval Gate
    approval_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    job: Mapped["Job"] = relationship("Job", back_populates="applications")
    resume_version: Mapped[Optional["ResumeVersion"]] = relationship("ResumeVersion", back_populates="applications")
    events: Mapped[List["ApplicationEvent"]] = relationship(
        "ApplicationEvent", back_populates="application", cascade="all, delete-orphan", order_by="ApplicationEvent.created_at"
    )
    attempts: Mapped[List["SubmissionAttempt"]] = relationship(
        "SubmissionAttempt", back_populates="application", cascade="all, delete-orphan", order_by="SubmissionAttempt.attempt_number"
    )


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str] = mapped_column(String(50), nullable=False, default="SYSTEM")
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    application: Mapped["Application"] = relationship("Application", back_populates="events")


class SubmissionAttempt(Base, TimestampMixin):
    __tablename__ = "submission_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    adapter_identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    selected_resume_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("resume_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    uploaded_artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    confirmation_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    sanitized_diagnostics: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    reconciliation_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    application: Mapped["Application"] = relationship("Application", back_populates="attempts")
    selected_resume: Mapped["ResumeVersion"] = relationship("ResumeVersion")
