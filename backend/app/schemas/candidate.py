from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


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
    target_package_min_lpa: Optional[float] = Field(None, ge=0, description="Minimum expected package in INR LPA")
    target_package_max_lpa: Optional[float] = Field(None, ge=0, description="Maximum expected package in INR LPA")
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
    target_package_min_lpa: Optional[float] = Field(None, ge=0)
    target_package_max_lpa: Optional[float] = Field(None, ge=0)
    remote_preference: Optional[str] = Field(None, max_length=50)
    notice_period_days: Optional[int] = Field(None, ge=0)
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None


class JobSearchPreferences(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    # Canonical Phase 2 Contract:
    target_roles: List[str] = Field(default_factory=list, description="Target job roles / families")
    role_keywords: List[str] = Field(default_factory=list, description="Keywords to match against job descriptions")

    must_have_skills: List[str] = Field(default_factory=list, description="Non-negotiable priority technical skills")
    preferred_skills: List[str] = Field(default_factory=list, description="Desirable bonus technical skills")
    ai_genai_focus_skills: List[str] = Field(default_factory=list, description="AI/GenAI, RAG, and Agentic specialization skills")

    remote_preference: str = Field("REMOTE", max_length=50, description="REMOTE, HYBRID, ON_SITE, or ANY")
    allow_remote_opportunities: bool = Field(default=True, description="Whether remote opportunities are acceptable regardless of city")

    target_min_experience_years: Optional[float] = Field(None, ge=0.0, le=50.0, description="Minimum years of experience")
    target_max_experience_years: Optional[float] = Field(None, ge=0.0, le=50.0, description="Maximum years of experience")

    preferred_locations: List[str] = Field(default_factory=list, description="Preferred locations/cities (India, Remote, etc.)")

    minimum_package_lpa: Optional[float] = Field(None, ge=0.0, description="Expected minimum annual package in INR LPA")

    preferred_companies: List[str] = Field(default_factory=list, description="Companies candidate especially wants to work for")
    excluded_companies: List[str] = Field(default_factory=list, description="Companies to exclude or de-prioritize")

    # Aliases and backward compatibility
    role_aliases: Dict[str, List[str]] = Field(default_factory=dict, description="Configured role aliases for title matching")
    target_titles: List[str] = Field(default_factory=list, description="Legacy alias for target_roles")
    required_skills: List[str] = Field(default_factory=list, description="Legacy alias for must_have_skills")
    ai_focus_skills: List[str] = Field(default_factory=list, description="Alias for ai_genai_focus_skills")
    allow_remote: bool = Field(default=True, description="Alias for allow_remote_opportunities")
    preferred_min_years: Optional[float] = Field(None, ge=0.0, le=50.0, description="Alias for target_min_experience_years")
    preferred_max_years: Optional[float] = Field(None, ge=0.0, le=50.0, description="Alias for target_max_experience_years")
    min_experience_years: Optional[float] = Field(None, ge=0.0, le=50.0, description="Alias for target_min_experience_years")
    max_experience_years: Optional[float] = Field(None, ge=0.0, le=50.0, description="Alias for target_max_experience_years")
    min_years_experience: Optional[float] = Field(None, ge=0.0, le=50.0, description="Alias for target_min_experience_years")
    max_years_experience: Optional[float] = Field(None, ge=0.0, le=50.0, description="Alias for target_max_experience_years")
    min_salary_lpa: Optional[float] = Field(None, ge=0.0, description="Alias for minimum_package_lpa")
    min_salary: Optional[float] = Field(None, ge=0.0, description="Legacy field")
    legacy_min_salary_usd: Optional[float] = Field(None, ge=0.0, description="Preserved legacy USD salary")
    work_modes: List[str] = Field(default_factory=lambda: ["Full-time", "Remote", "Hybrid", "On-site"])
    employment_types: List[str] = Field(default_factory=lambda: ["Full-time"])

    @model_validator(mode="before")
    @classmethod
    def sync_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)

        # target_roles <-> target_titles
        if not d.get("target_roles") and d.get("target_titles"):
            d["target_roles"] = list(d["target_titles"])
        elif not d.get("target_titles") and d.get("target_roles"):
            d["target_titles"] = list(d["target_roles"])

        # must_have_skills <-> required_skills
        if not d.get("must_have_skills") and d.get("required_skills"):
            d["must_have_skills"] = list(d["required_skills"])
        elif not d.get("required_skills") and d.get("must_have_skills"):
            d["required_skills"] = list(d["must_have_skills"])

        # ai_genai_focus_skills <-> ai_focus_skills
        if not d.get("ai_genai_focus_skills") and d.get("ai_focus_skills"):
            d["ai_genai_focus_skills"] = list(d["ai_focus_skills"])
        elif not d.get("ai_focus_skills") and d.get("ai_genai_focus_skills"):
            d["ai_focus_skills"] = list(d["ai_genai_focus_skills"])

        # allow_remote_opportunities <-> allow_remote
        if "allow_remote_opportunities" in d and "allow_remote" not in d:
            d["allow_remote"] = d["allow_remote_opportunities"]
        elif "allow_remote" in d and "allow_remote_opportunities" not in d:
            d["allow_remote_opportunities"] = d["allow_remote"]

        # min experience
        min_exp = (
            d.get("target_min_experience_years")
            if d.get("target_min_experience_years") is not None
            else d.get("preferred_min_years")
            if d.get("preferred_min_years") is not None
            else d.get("min_experience_years")
            if d.get("min_experience_years") is not None
            else d.get("min_years_experience")
        )
        if min_exp is not None:
            try:
                min_exp_float = float(min_exp)
                d["target_min_experience_years"] = min_exp_float
                d["preferred_min_years"] = min_exp_float
                d["min_experience_years"] = min_exp_float
                d["min_years_experience"] = min_exp_float
            except (ValueError, TypeError):
                pass

        # max experience
        max_exp = (
            d.get("target_max_experience_years")
            if d.get("target_max_experience_years") is not None
            else d.get("preferred_max_years")
            if d.get("preferred_max_years") is not None
            else d.get("max_experience_years")
            if d.get("max_experience_years") is not None
            else d.get("max_years_experience")
        )
        if max_exp is not None:
            try:
                max_exp_float = float(max_exp)
                d["target_max_experience_years"] = max_exp_float
                d["preferred_max_years"] = max_exp_float
                d["max_experience_years"] = max_exp_float
                d["max_years_experience"] = max_exp_float
            except (ValueError, TypeError):
                pass

        # salary / package LPA
        pkg_lpa = (
            d.get("minimum_package_lpa")
            if d.get("minimum_package_lpa") is not None
            else d.get("min_salary_lpa")
        )
        if pkg_lpa is not None:
            try:
                pkg_lpa_float = float(pkg_lpa)
                d["minimum_package_lpa"] = pkg_lpa_float
                d["min_salary_lpa"] = pkg_lpa_float
            except (ValueError, TypeError):
                pass

        return d


class JobSearchPreferencesUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    target_roles: Optional[List[str]] = None
    role_keywords: Optional[List[str]] = None
    must_have_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    ai_genai_focus_skills: Optional[List[str]] = None
    remote_preference: Optional[str] = Field(None, max_length=50)
    allow_remote_opportunities: Optional[bool] = None
    target_min_experience_years: Optional[float] = Field(None, ge=0.0, le=50.0)
    target_max_experience_years: Optional[float] = Field(None, ge=0.0, le=50.0)
    preferred_locations: Optional[List[str]] = None
    minimum_package_lpa: Optional[float] = Field(None, ge=0.0)
    preferred_companies: Optional[List[str]] = None
    excluded_companies: Optional[List[str]] = None

    # Aliases
    role_aliases: Optional[Dict[str, List[str]]] = None
    target_titles: Optional[List[str]] = None
    required_skills: Optional[List[str]] = None
    ai_focus_skills: Optional[List[str]] = None
    allow_remote: Optional[bool] = None
    preferred_min_years: Optional[float] = Field(None, ge=0.0, le=50.0)
    preferred_max_years: Optional[float] = Field(None, ge=0.0, le=50.0)
    min_experience_years: Optional[float] = Field(None, ge=0.0, le=50.0)
    max_experience_years: Optional[float] = Field(None, ge=0.0, le=50.0)
    min_years_experience: Optional[float] = Field(None, ge=0.0, le=50.0)
    max_years_experience: Optional[float] = Field(None, ge=0.0, le=50.0)
    min_salary_lpa: Optional[float] = Field(None, ge=0.0)
    min_salary: Optional[float] = Field(None, ge=0.0)
    legacy_min_salary_usd: Optional[float] = Field(None, ge=0.0)
    work_modes: Optional[List[str]] = None
    employment_types: Optional[List[str]] = None

    @model_validator(mode="before")
    @classmethod
    def sync_aliases_update(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)

        # target_roles <-> target_titles
        if d.get("target_roles") is not None and d.get("target_titles") is None:
            d["target_titles"] = list(d["target_roles"])
        elif d.get("target_titles") is not None and d.get("target_roles") is None:
            d["target_roles"] = list(d["target_titles"])

        # must_have_skills <-> required_skills
        if d.get("must_have_skills") is not None and d.get("required_skills") is None:
            d["required_skills"] = list(d["must_have_skills"])
        elif d.get("required_skills") is not None and d.get("must_have_skills") is None:
            d["must_have_skills"] = list(d["required_skills"])

        # ai_genai_focus_skills <-> ai_focus_skills
        if d.get("ai_genai_focus_skills") is not None and d.get("ai_focus_skills") is None:
            d["ai_focus_skills"] = list(d["ai_genai_focus_skills"])
        elif d.get("ai_focus_skills") is not None and d.get("ai_genai_focus_skills") is None:
            d["ai_genai_focus_skills"] = list(d["ai_focus_skills"])

        # allow_remote_opportunities <-> allow_remote
        if d.get("allow_remote_opportunities") is not None and d.get("allow_remote") is None:
            d["allow_remote"] = d["allow_remote_opportunities"]
        elif d.get("allow_remote") is not None and d.get("allow_remote_opportunities") is None:
            d["allow_remote_opportunities"] = d["allow_remote"]

        # min experience
        min_exp = (
            d.get("target_min_experience_years")
            if d.get("target_min_experience_years") is not None
            else d.get("preferred_min_years")
            if d.get("preferred_min_years") is not None
            else d.get("min_experience_years")
            if d.get("min_experience_years") is not None
            else d.get("min_years_experience")
        )
        if min_exp is not None:
            try:
                min_exp_float = float(min_exp)
                d["target_min_experience_years"] = min_exp_float
                d["preferred_min_years"] = min_exp_float
                d["min_experience_years"] = min_exp_float
                d["min_years_experience"] = min_exp_float
            except (ValueError, TypeError):
                pass

        # max experience
        max_exp = (
            d.get("target_max_experience_years")
            if d.get("target_max_experience_years") is not None
            else d.get("preferred_max_years")
            if d.get("preferred_max_years") is not None
            else d.get("max_experience_years")
            if d.get("max_experience_years") is not None
            else d.get("max_years_experience")
        )
        if max_exp is not None:
            try:
                max_exp_float = float(max_exp)
                d["target_max_experience_years"] = max_exp_float
                d["preferred_max_years"] = max_exp_float
                d["max_experience_years"] = max_exp_float
                d["max_years_experience"] = max_exp_float
            except (ValueError, TypeError):
                pass

        # salary / package LPA
        pkg_lpa = (
            d.get("minimum_package_lpa")
            if d.get("minimum_package_lpa") is not None
            else d.get("min_salary_lpa")
        )
        if pkg_lpa is not None:
            try:
                pkg_lpa_float = float(pkg_lpa)
                d["minimum_package_lpa"] = pkg_lpa_float
                d["min_salary_lpa"] = pkg_lpa_float
            except (ValueError, TypeError):
                pass

        return d


class CandidateProfileRead(CandidateProfileBase):
    id: str
    target_package_min_lpa: Optional[float] = None
    target_package_max_lpa: Optional[float] = None
    search_preferences: JobSearchPreferences = Field(default_factory=JobSearchPreferences)
    notification_preferences: dict = Field(default_factory=dict)
    skills: List[CandidateSkillRead] = Field(default_factory=list)
    experiences: List[CandidateExperienceRead] = Field(default_factory=list)
    educations: List[CandidateEducationRead] = Field(default_factory=list)
    projects: List[CandidateProjectRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
