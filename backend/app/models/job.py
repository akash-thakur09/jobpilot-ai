import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Text, Float, Boolean, Integer, ForeignKey, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin
from backend.app.models.enums import (
    RemoteType,
    JobStatus,
    RequirementType,
    FreshnessStatus,
    DuplicateConfidence,
    ClusterStatus,
)


class JobDuplicateCluster(Base, TimestampMixin):
    __tablename__ = "job_duplicate_clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_job_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="SET NULL", use_alter=True), nullable=True, index=True
    )
    cluster_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ClusterStatus.DETECTED.value, index=True
    )
    confidence: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DuplicateConfidence.POSSIBLE_DUPLICATE.value
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    match_reasons: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    jobs: Mapped[List["Job"]] = relationship(
        "Job", back_populates="duplicate_cluster", foreign_keys="Job.duplicate_cluster_id"
    )
    canonical_job: Mapped[Optional["Job"]] = relationship("Job", foreign_keys=[canonical_job_id])


class JobSource(Base, TimestampMixin):
    __tablename__ = "job_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    identifier: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_discovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jobs_discovered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="source", cascade="all, delete-orphan")


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_source_external_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_sources.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    canonical_url: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(255), nullable=False, default="Remote")
    remote_type: Mapped[str] = mapped_column(String(50), nullable=False, default=RemoteType.REMOTE.value)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    employment_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Full-time")
    salary_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="USD")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=JobStatus.DISCOVERED.value)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Freshness & lifecycle
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    freshness_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=FreshnessStatus.ACTIVE.value, index=True
    )
    freshness_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Duplicate management
    duplicate_cluster_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("job_duplicate_clusters.id", ondelete="SET NULL"), nullable=True, index=True
    )

    source: Mapped["JobSource"] = relationship("JobSource", back_populates="jobs")
    duplicate_cluster: Mapped[Optional["JobDuplicateCluster"]] = relationship(
        "JobDuplicateCluster", back_populates="jobs", foreign_keys=[duplicate_cluster_id]
    )
    requirements: Mapped[List["JobRequirement"]] = relationship(
        "JobRequirement", back_populates="job", cascade="all, delete-orphan"
    )
    match_scores: Mapped[List["MatchScore"]] = relationship(
        "MatchScore", back_populates="job", cascade="all, delete-orphan"
    )
    resumes: Mapped[List["ResumeVersion"]] = relationship(
        "ResumeVersion", back_populates="job", cascade="all, delete-orphan"
    )
    applications: Mapped[List["Application"]] = relationship(
        "Application", back_populates="job", cascade="all, delete-orphan"
    )
    feedbacks: Mapped[List["JobFeedback"]] = relationship(
        "JobFeedback", back_populates="job", cascade="all, delete-orphan"
    )


class JobRequirement(Base, TimestampMixin):
    __tablename__ = "job_requirements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    requirement_type: Mapped[str] = mapped_column(String(50), nullable=False, default=RequirementType.MANDATORY_SKILL.value)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    job: Mapped["Job"] = relationship("Job", back_populates="requirements")
