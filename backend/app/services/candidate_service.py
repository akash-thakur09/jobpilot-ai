from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
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
