from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from backend.app.models.candidate import (
    CandidateProfile,
    CandidateSkill,
    CandidateExperience,
    CandidateEducation,
    CandidateProject,
)
from backend.app.schemas.candidate import (
    CandidateProfileCreate,
    CandidateProfileUpdate,
    CandidateSkillCreate,
    CandidateExperienceCreate,
    CandidateEducationCreate,
    CandidateProjectCreate,
    JobSearchPreferences,
    JobSearchPreferencesUpdate,
)


class CandidateService:
    @staticmethod
    async def get_profile(session: AsyncSession) -> Optional[CandidateProfile]:
        """Retrieve the primary candidate profile with all related entities."""
        query = (
            select(CandidateProfile)
            .options(
                selectinload(CandidateProfile.skills),
                selectinload(CandidateProfile.experiences),
                selectinload(CandidateProfile.educations),
                selectinload(CandidateProfile.projects),
            )
            .limit(1)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_profile_by_id(session: AsyncSession, profile_id: str) -> Optional[CandidateProfile]:
        """Retrieve a candidate profile by its unique ID."""
        query = (
            select(CandidateProfile)
            .where(CandidateProfile.id == profile_id)
            .options(
                selectinload(CandidateProfile.skills),
                selectinload(CandidateProfile.experiences),
                selectinload(CandidateProfile.educations),
                selectinload(CandidateProfile.projects),
            )
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def create_profile(
        cls, session: AsyncSession, data: CandidateProfileCreate
    ) -> CandidateProfile:
        """Create a new candidate profile. Only one active candidate profile is allowed."""
        existing = await cls.get_profile(session)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A candidate profile already exists. Use PUT/PATCH to update it.",
            )

        # Check email uniqueness
        email_check = await session.execute(
            select(CandidateProfile).where(CandidateProfile.email == data.email)
        )
        if email_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Candidate email already registered.",
            )

        profile_data = data.model_dump(exclude={"skills", "experiences", "educations", "projects"})
        profile = CandidateProfile(**profile_data)
        session.add(profile)
        await session.flush()

        for s in data.skills:
            session.add(CandidateSkill(candidate_id=profile.id, **s.model_dump()))

        for e in data.experiences:
            session.add(CandidateExperience(candidate_id=profile.id, **e.model_dump()))

        for ed in data.educations:
            session.add(CandidateEducation(candidate_id=profile.id, **ed.model_dump()))

        for p in data.projects:
            session.add(CandidateProject(candidate_id=profile.id, **p.model_dump()))

        await session.commit()
        return await cls.get_profile_by_id(session, profile.id)

    @classmethod
    async def update_profile(
        cls, session: AsyncSession, data: CandidateProfileUpdate
    ) -> CandidateProfile:
        """Update fields on the existing candidate profile."""
        profile = await cls.get_profile(session)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate profile not found. Please create one first.",
            )

        update_dict = data.model_dump(exclude_unset=True)

        if "email" in update_dict and update_dict["email"] != profile.email:
            email_check = await session.execute(
                select(CandidateProfile).where(
                    CandidateProfile.email == update_dict["email"],
                    CandidateProfile.id != profile.id,
                )
            )
            if email_check.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email address already in use.",
                )

        for key, value in update_dict.items():
            setattr(profile, key, value)

        await session.commit()
        return await cls.get_profile_by_id(session, profile.id)

    @classmethod
    async def add_skill(
        cls, session: AsyncSession, skill_in: CandidateSkillCreate
    ) -> CandidateSkill:
        profile = await cls.get_profile(session)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate profile not found.",
            )

        skill = CandidateSkill(candidate_id=profile.id, **skill_in.model_dump())
        session.add(skill)
        await session.commit()
        await session.refresh(skill)
        return skill

    @classmethod
    async def delete_skill(cls, session: AsyncSession, skill_id: str) -> None:
        result = await session.execute(
            select(CandidateSkill).where(CandidateSkill.id == skill_id)
        )
        skill = result.scalar_one_or_none()
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Skill not found.",
            )
        await session.delete(skill)
        await session.commit()

    @classmethod
    async def add_experience(
        cls, session: AsyncSession, exp_in: CandidateExperienceCreate
    ) -> CandidateExperience:
        profile = await cls.get_profile(session)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate profile not found.",
            )

        exp = CandidateExperience(candidate_id=profile.id, **exp_in.model_dump())
        session.add(exp)
        await session.commit()
        await session.refresh(exp)
        return exp

    @classmethod
    async def delete_experience(cls, session: AsyncSession, exp_id: str) -> None:
        result = await session.execute(
            select(CandidateExperience).where(CandidateExperience.id == exp_id)
        )
        exp = result.scalar_one_or_none()
        if not exp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experience record not found.",
            )
        await session.delete(exp)
        await session.commit()

    @classmethod
    async def add_education(
        cls, session: AsyncSession, edu_in: CandidateEducationCreate
    ) -> CandidateEducation:
        profile = await cls.get_profile(session)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate profile not found.",
            )

        edu = CandidateEducation(candidate_id=profile.id, **edu_in.model_dump())
        session.add(edu)
        await session.commit()
        await session.refresh(edu)
        return edu

    @classmethod
    async def delete_education(cls, session: AsyncSession, edu_id: str) -> None:
        result = await session.execute(
            select(CandidateEducation).where(CandidateEducation.id == edu_id)
        )
        edu = result.scalar_one_or_none()
        if not edu:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Education record not found.",
            )
        await session.delete(edu)
        await session.commit()

    @classmethod
    async def add_project(
        cls, session: AsyncSession, proj_in: CandidateProjectCreate
    ) -> CandidateProject:
        profile = await cls.get_profile(session)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate profile not found.",
            )

        proj = CandidateProject(candidate_id=profile.id, **proj_in.model_dump())
        session.add(proj)
        await session.commit()
        await session.refresh(proj)
        return proj

    @classmethod
    async def delete_project(cls, session: AsyncSession, project_id: str) -> None:
        result = await session.execute(
            select(CandidateProject).where(CandidateProject.id == project_id)
        )
        proj = result.scalar_one_or_none()
        if not proj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project record not found.",
            )
        await session.delete(proj)
        await session.commit()

    @classmethod
    async def get_search_preferences(cls, session: AsyncSession) -> JobSearchPreferences:
        """Retrieves structured search preferences, falling back to top-level profile fields and smart defaults."""
        profile = await cls.get_profile(session)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate profile not found.",
            )
        prefs = dict(profile.search_preferences or {})

        # Bidirectional sync: target_roles <-> target_titles
        if not prefs.get("target_roles") and prefs.get("target_titles"):
            prefs["target_roles"] = list(prefs["target_titles"])
        elif not prefs.get("target_titles") and prefs.get("target_roles"):
            prefs["target_titles"] = list(prefs["target_roles"])
        elif not prefs.get("target_roles") and profile.target_titles:
            prefs["target_roles"] = list(profile.target_titles)
            prefs["target_titles"] = list(profile.target_titles)

        # Smart defaults for target roles
        if not prefs.get("target_roles"):
            prefs["target_roles"] = [
                "Full Stack Engineer",
                "Software Engineer",
                "AI Engineer",
                "Backend Engineer",
                "Full Stack Developer",
            ]
            prefs["target_titles"] = list(prefs["target_roles"])

        # Role aliases default
        if not prefs.get("role_aliases"):
            prefs["role_aliases"] = {
                "Full Stack Engineer": ["Full Stack Developer", "Full-Stack Engineer", "Fullstack Developer", "Web Developer"],
                "AI Engineer": ["Generative AI Engineer", "GenAI Engineer", "AI/ML Engineer", "LLM Engineer", "Machine Learning Engineer"],
                "Backend Engineer": ["Python Developer", "Python Engineer", "Backend Developer", "Software Development Engineer"],
                "Software Engineer": ["SDE", "Core Engineer", "Application Developer"],
            }

        # Bidirectional sync: must_have_skills <-> required_skills
        if not prefs.get("must_have_skills") and prefs.get("required_skills"):
            prefs["must_have_skills"] = list(prefs["required_skills"])
        elif not prefs.get("required_skills") and prefs.get("must_have_skills"):
            prefs["required_skills"] = list(prefs["must_have_skills"])

        # Default 3-tier priority skills
        if not prefs.get("must_have_skills"):
            prefs["must_have_skills"] = ["Python", "FastAPI", "React", "TypeScript", "SQL"]
            prefs["required_skills"] = list(prefs["must_have_skills"])

        if not prefs.get("preferred_skills"):
            prefs["preferred_skills"] = ["Docker", "PostgreSQL", "Redis", "AWS", "Git", "REST APIs"]

        # Bidirectional sync: ai_genai_focus_skills <-> ai_focus_skills
        ai_skills = prefs.get("ai_genai_focus_skills") or prefs.get("ai_focus_skills")
        if not ai_skills:
            ai_skills = [
                "LLM", "RAG", "Agentic AI", "Vector Database", "Embeddings",
                "LangChain", "LangGraph", "Semantic Search", "MCP", "OpenAI API", "Prompt Engineering"
            ]
        prefs["ai_genai_focus_skills"] = list(ai_skills)
        prefs["ai_focus_skills"] = list(ai_skills)

        # Locations and remote
        if not prefs.get("preferred_locations"):
            prefs["preferred_locations"] = ["Remote", "Bengaluru", "Bangalore", "Hyderabad", "Pune", "Gurgaon", "Noida", "Delhi NCR", "India"]

        allow_rem = (
            prefs.get("allow_remote_opportunities")
            if prefs.get("allow_remote_opportunities") is not None
            else prefs.get("allow_remote", True)
        )
        prefs["allow_remote_opportunities"] = bool(allow_rem)
        prefs["allow_remote"] = bool(allow_rem)

        if not prefs.get("remote_preference") and profile.remote_preference:
            prefs["remote_preference"] = profile.remote_preference

        # Experience range (Canonical: target_min_experience_years / target_max_experience_years)
        min_exp = (
            prefs.get("target_min_experience_years")
            if prefs.get("target_min_experience_years") is not None
            else prefs.get("preferred_min_years")
            if prefs.get("preferred_min_years") is not None
            else prefs.get("min_experience_years")
            if prefs.get("min_experience_years") is not None
            else prefs.get("min_years_experience")
        )
        if min_exp is None:
            min_exp = 0.0
        prefs["target_min_experience_years"] = float(min_exp)
        prefs["preferred_min_years"] = float(min_exp)
        prefs["min_experience_years"] = float(min_exp)
        prefs["min_years_experience"] = float(min_exp)

        max_exp = (
            prefs.get("target_max_experience_years")
            if prefs.get("target_max_experience_years") is not None
            else prefs.get("preferred_max_years")
            if prefs.get("preferred_max_years") is not None
            else prefs.get("max_experience_years")
            if prefs.get("max_experience_years") is not None
            else prefs.get("max_years_experience")
        )
        if max_exp is None:
            max_exp = 6.0
        prefs["target_max_experience_years"] = float(max_exp)
        prefs["preferred_max_years"] = float(max_exp)
        prefs["max_experience_years"] = float(max_exp)
        prefs["max_years_experience"] = float(max_exp)

        # Compensation in INR LPA
        pkg_lpa = (
            prefs.get("minimum_package_lpa")
            if prefs.get("minimum_package_lpa") is not None
            else profile.target_package_min_lpa
            if profile.target_package_min_lpa is not None
            else prefs.get("min_salary_lpa")
        )

        if pkg_lpa is not None:
            prefs["minimum_package_lpa"] = float(pkg_lpa)
            prefs["min_salary_lpa"] = float(pkg_lpa)
        else:
            # Handle legacy USD values safely without corrupting INR LPA
            old_sal = prefs.get("min_salary") or profile.target_salary_min
            if old_sal is not None:
                if old_sal < 200.0:
                    prefs["minimum_package_lpa"] = float(old_sal)
                    prefs["min_salary_lpa"] = float(old_sal)
                else:
                    prefs["legacy_min_salary_usd"] = float(old_sal)
                    prefs["minimum_package_lpa"] = None
                    prefs["min_salary_lpa"] = None

        return JobSearchPreferences(**prefs)

    @classmethod
    async def update_search_preferences(
        cls, session: AsyncSession, data: JobSearchPreferencesUpdate
    ) -> JobSearchPreferences:
        """Updates search preferences while preserving verified candidate facts."""
        profile = await cls.get_profile(session)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate profile not found.",
            )
        current = dict(profile.search_preferences or {})
        updates = data.model_dump(exclude_unset=True)

        # Sync target_roles and target_titles
        if "target_roles" in updates and updates["target_roles"] is not None:
            updates["target_titles"] = updates["target_roles"]
            profile.target_titles = updates["target_roles"]
        elif "target_titles" in updates and updates["target_titles"] is not None:
            updates["target_roles"] = updates["target_titles"]
            profile.target_titles = updates["target_titles"]

        # Sync must_have_skills and required_skills
        if "must_have_skills" in updates and updates["must_have_skills"] is not None:
            updates["required_skills"] = updates["must_have_skills"]
        elif "required_skills" in updates and updates["required_skills"] is not None:
            updates["must_have_skills"] = updates["required_skills"]

        # Sync ai_genai_focus_skills and ai_focus_skills
        if "ai_genai_focus_skills" in updates and updates["ai_genai_focus_skills"] is not None:
            updates["ai_focus_skills"] = updates["ai_genai_focus_skills"]
        elif "ai_focus_skills" in updates and updates["ai_focus_skills"] is not None:
            updates["ai_genai_focus_skills"] = updates["ai_focus_skills"]

        # Sync allow_remote_opportunities and allow_remote
        if "allow_remote_opportunities" in updates and updates["allow_remote_opportunities"] is not None:
            updates["allow_remote"] = updates["allow_remote_opportunities"]
        elif "allow_remote" in updates and updates["allow_remote"] is not None:
            updates["allow_remote_opportunities"] = updates["allow_remote"]

        # Sync min experience fields (including 0.0)
        min_exp = None
        for key in ["target_min_experience_years", "preferred_min_years", "min_experience_years", "min_years_experience"]:
            if key in updates and updates[key] is not None:
                min_exp = float(updates[key])
                break
        if min_exp is not None:
            updates["target_min_experience_years"] = min_exp
            updates["preferred_min_years"] = min_exp
            updates["min_experience_years"] = min_exp
            updates["min_years_experience"] = min_exp

        # Sync max experience fields
        max_exp = None
        for key in ["target_max_experience_years", "preferred_max_years", "max_experience_years", "max_years_experience"]:
            if key in updates and updates[key] is not None:
                max_exp = float(updates[key])
                break
        if max_exp is not None:
            updates["target_max_experience_years"] = max_exp
            updates["preferred_max_years"] = max_exp
            updates["max_experience_years"] = max_exp
            updates["max_years_experience"] = max_exp

        # Sync package LPA
        pkg_lpa = None
        for key in ["minimum_package_lpa", "min_salary_lpa"]:
            if key in updates and updates[key] is not None:
                pkg_lpa = float(updates[key])
                break
        if pkg_lpa is not None:
            updates["minimum_package_lpa"] = pkg_lpa
            updates["min_salary_lpa"] = pkg_lpa
            profile.target_package_min_lpa = pkg_lpa
        elif "minimum_package_lpa" in updates and updates["minimum_package_lpa"] is None:
            profile.target_package_min_lpa = None

        if "remote_preference" in updates and updates["remote_preference"] is not None:
            profile.remote_preference = updates["remote_preference"]
        if "min_salary" in updates and updates["min_salary"] is not None:
            if float(updates["min_salary"]) >= 1000.0:
                updates["legacy_min_salary_usd"] = float(updates["min_salary"])
                profile.target_salary_min = float(updates["min_salary"])
            else:
                # If a small number was entered into min_salary, treat as LPA
                updates["minimum_package_lpa"] = float(updates["min_salary"])
                updates["min_salary_lpa"] = float(updates["min_salary"])
                profile.target_package_min_lpa = float(updates["min_salary"])

        current.update(updates)
        profile.search_preferences = current
        flag_modified(profile, "search_preferences")
        await session.commit()
        await session.refresh(profile)
        return await cls.get_search_preferences(session)

