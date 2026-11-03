import uuid
from typing import List, Optional
from sqlalchemy import String, Text, Integer, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin


class CandidateProfile(Base, TimestampMixin):
    __tablename__ = "candidate_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    work_authorization: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    years_of_experience: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    target_titles: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    target_salary_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_salary_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_package_min_lpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_package_max_lpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    remote_preference: Mapped[str] = mapped_column(String(50), nullable=False, default="REMOTE")
    notice_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    portfolio_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    search_preferences: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notification_preferences: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    skills: Mapped[List["CandidateSkill"]] = relationship(
        "CandidateSkill", back_populates="candidate", cascade="all, delete-orphan"
    )
    experiences: Mapped[List["CandidateExperience"]] = relationship(
        "CandidateExperience", back_populates="candidate", cascade="all, delete-orphan"
    )
    educations: Mapped[List["CandidateEducation"]] = relationship(
        "CandidateEducation", back_populates="candidate", cascade="all, delete-orphan"
    )
    projects: Mapped[List["CandidateProject"]] = relationship(
        "CandidateProject", back_populates="candidate", cascade="all, delete-orphan"
    )


class CandidateSkill(Base, TimestampMixin):
    __tablename__ = "candidate_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="technical")
    years_experience: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    candidate: Mapped["CandidateProfile"] = relationship("CandidateProfile", back_populates="skills")


class CandidateExperience(Base, TimestampMixin):
    __tablename__ = "candidate_experiences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_date: Mapped[str] = mapped_column(String(50), nullable=False)
    end_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_bullets: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)

    candidate: Mapped["CandidateProfile"] = relationship("CandidateProfile", back_populates="experiences")


class CandidateEducation(Base, TimestampMixin):
    __tablename__ = "candidate_educations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    institution: Mapped[str] = mapped_column(String(255), nullable=False)
    degree: Mapped[str] = mapped_column(String(255), nullable=False)
    field_of_study: Mapped[str] = mapped_column(String(255), nullable=False)
    graduation_year: Mapped[int] = mapped_column(Integer, nullable=False)

    candidate: Mapped["CandidateProfile"] = relationship("CandidateProfile", back_populates="educations")


class CandidateProject(Base, TimestampMixin):
    __tablename__ = "candidate_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    technologies: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    project_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verified_bullets: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)

    candidate: Mapped["CandidateProfile"] = relationship("CandidateProfile", back_populates="projects")
