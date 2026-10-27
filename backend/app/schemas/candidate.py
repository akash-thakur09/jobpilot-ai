from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------
class CandidateSkillBase(BaseModel):
    skill_name: str = Field(..., min_length=1, max_length=100)
    category: str = Field("technical", max_length=50)
    years_experience: float = Field(1.0, ge=0.0, le=70.0)
    is_verified: bool = True
    evidence: Optional[str] = None


class CandidateSkillCreate(CandidateSkillBase):
    pass


class CandidateSkillRead(CandidateSkillBase):
    id: str
    candidate_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------
class CandidateExperienceBase(BaseModel):
    company: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    start_date: str = Field(..., min_length=4, max_length=50)
    end_date: Optional[str] = Field(None, max_length=50)
    is_current: bool = False
    verified_bullets: List[str] = Field(default_factory=list)


class CandidateExperienceCreate(CandidateExperienceBase):
    pass


class CandidateExperienceRead(CandidateExperienceBase):
    id: str
    candidate_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------
class CandidateEducationBase(BaseModel):
    institution: str = Field(..., min_length=1, max_length=255)
    degree: str = Field(..., min_length=1, max_length=255)
    field_of_study: str = Field(..., min_length=1, max_length=255)
    graduation_year: int = Field(..., ge=1950, le=2100)


class CandidateEducationCreate(CandidateEducationBase):
    pass


class CandidateEducationRead(CandidateEducationBase):
    id: str
    candidate_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------
class CandidateProjectBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    technologies: List[str] = Field(default_factory=list)
    project_url: Optional[str] = Field(None, max_length=255)
    verified_bullets: List[str] = Field(default_factory=list)


class CandidateProjectCreate(CandidateProjectBase):
    pass


class CandidateProjectRead(CandidateProjectBase):
    id: str
    candidate_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Candidate Profile
# ---------------------------------------------------------------------------
class CandidateProfileBase(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=50)
    location: str = Field(..., min_length=1, max_length=255)
    work_authorization: str = Field(..., min_length=1, max_length=255)
    summary: str = Field(..., min_length=10)
    years_of_experience: float = Field(0.0, ge=0.0, le=70.0)
    target_titles: List[str] = Field(default_factory=list)
    target_salary_min: Optional[float] = Field(None, ge=0)
    target_salary_max: Optional[float] = Field(None, ge=0)
    remote_preference: str = Field("REMOTE", max_length=50)
    notice_period_days: int = Field(0, ge=0)
    linkedin_url: Optional[str] = Field(None, max_length=255)
    github_url: Optional[str] = Field(None, max_length=255)
    portfolio_url: Optional[str] = Field(None, max_length=255)


class CandidateProfileCreate(CandidateProfileBase):
    skills: List[CandidateSkillCreate] = Field(default_factory=list)
    experiences: List[CandidateExperienceCreate] = Field(default_factory=list)
    educations: List[CandidateEducationCreate] = Field(default_factory=list)
    projects: List[CandidateProjectCreate] = Field(default_factory=list)


class CandidateProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, min_length=1, max_length=255)
    work_authorization: Optional[str] = Field(None, min_length=1, max_length=255)
    summary: Optional[str] = Field(None, min_length=10)
    years_of_experience: Optional[float] = Field(None, ge=0.0, le=70.0)
    target_titles: Optional[List[str]] = None
    target_salary_min: Optional[float] = Field(None, ge=0)
    target_salary_max: Optional[float] = Field(None, ge=0)
    remote_preference: Optional[str] = Field(None, max_length=50)
    notice_period_days: Optional[int] = Field(None, ge=0)
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None


class JobSearchPreferences(BaseModel):
    target_titles: List[str] = Field(default_factory=list, description="Target job titles (e.g. ['Senior Software Engineer', 'Backend Lead'])")
    role_keywords: List[str] = Field(default_factory=list, description="Keywords to match against job descriptions (e.g. ['FastAPI', 'Distributed Systems'])")
    required_skills: List[str] = Field(default_factory=list, description="Desired skills candidate wants in target jobs")
    preferred_skills: List[str] = Field(default_factory=list, description="Bonus skills candidate desires in target jobs")
    min_experience_years: Optional[float] = Field(None, ge=0.0, le=50.0, description="Minimum years of experience")
    max_experience_years: Optional[float] = Field(None, ge=0.0, le=50.0, description="Maximum years of experience")
    preferred_locations: List[str] = Field(default_factory=list, description="Preferred locations/cities")
    remote_preference: str = Field("REMOTE", max_length=50, description="REMOTE, HYBRID, ON_SITE, or ANY")
    min_salary: Optional[float] = Field(None, ge=0.0, description="Desired minimum base salary")
    preferred_companies: List[str] = Field(default_factory=list, description="Companies candidate especially wants to work for")
    excluded_companies: List[str] = Field(default_factory=list, description="Companies to exclude or de-prioritize")


class JobSearchPreferencesUpdate(BaseModel):
    target_titles: Optional[List[str]] = None
    role_keywords: Optional[List[str]] = None
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    min_experience_years: Optional[float] = Field(None, ge=0.0, le=50.0)
    max_experience_years: Optional[float] = Field(None, ge=0.0, le=50.0)
    preferred_locations: Optional[List[str]] = None
    remote_preference: Optional[str] = Field(None, max_length=50)
    min_salary: Optional[float] = Field(None, ge=0.0)
    preferred_companies: Optional[List[str]] = None
    excluded_companies: Optional[List[str]] = None


class CandidateProfileRead(CandidateProfileBase):
    id: str
    search_preferences: dict = Field(default_factory=dict)
    notification_preferences: dict = Field(default_factory=dict)
    skills: List[CandidateSkillRead] = Field(default_factory=list)
    experiences: List[CandidateExperienceRead] = Field(default_factory=list)
    educations: List[CandidateEducationRead] = Field(default_factory=list)
    projects: List[CandidateProjectRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
