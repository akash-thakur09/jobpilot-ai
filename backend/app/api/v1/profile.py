from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db.session import get_db
from backend.app.schemas.candidate import (
    CandidateProfileCreate,
    CandidateProfileUpdate,
    CandidateProfileRead,
    CandidateSkillCreate,
    CandidateSkillRead,
    CandidateExperienceCreate,
    CandidateExperienceRead,
    CandidateEducationCreate,
    CandidateEducationRead,
    CandidateProjectCreate,
    CandidateProjectRead,
    JobSearchPreferences,
    JobSearchPreferencesUpdate,
)
from backend.app.schemas.resume_import import (
    ResumeImportResult,
    ResumeImportConfirmRequest,
)
from backend.app.services.candidate_service import CandidateService
from backend.app.services.resume_parser import ResumeParserService
from backend.app.services.relevance_engine import RelevanceEngine
from backend.app.core.logging import logger

router = APIRouter(prefix="/profile", tags=["Candidate Profile"])


@router.get("", response_model=CandidateProfileRead)
async def get_candidate_profile(session: AsyncSession = Depends(get_db)):
    """Retrieve the candidate profile."""
    profile = await CandidateService.get_profile(session)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile does not exist yet.",
        )
    prefs = await CandidateService.get_search_preferences(session)
    read_profile = CandidateProfileRead.model_validate(profile)
    read_profile.search_preferences = prefs
    return read_profile


@router.post("", response_model=CandidateProfileRead, status_code=status.HTTP_201_CREATED)
async def create_candidate_profile(
    data: CandidateProfileCreate, session: AsyncSession = Depends(get_db)
):
    """Create the candidate profile."""
    profile = await CandidateService.create_profile(session, data)
    prefs = await CandidateService.get_search_preferences(session)
    read_profile = CandidateProfileRead.model_validate(profile)
    read_profile.search_preferences = prefs
    return read_profile


@router.patch("", response_model=CandidateProfileRead)
async def update_candidate_profile(
    data: CandidateProfileUpdate, session: AsyncSession = Depends(get_db)
):
    """Update profile details."""
    profile = await CandidateService.update_profile(session, data)
    prefs = await CandidateService.get_search_preferences(session)
    read_profile = CandidateProfileRead.model_validate(profile)
    read_profile.search_preferences = prefs
    return read_profile


# ---------------------------------------------------------------------------
# Search Preferences endpoints
# ---------------------------------------------------------------------------
@router.get("/preferences", response_model=JobSearchPreferences)
async def get_search_preferences(session: AsyncSession = Depends(get_db)):
    """Retrieve structured job search preferences."""
    return await CandidateService.get_search_preferences(session)


@router.put("/preferences", response_model=JobSearchPreferences)
async def update_search_preferences(
    preferences: JobSearchPreferencesUpdate, session: AsyncSession = Depends(get_db)
):
    """Update job search preferences and re-evaluate stored jobs against the new preferences."""
    updated = await CandidateService.update_search_preferences(session, preferences)
    try:
        await RelevanceEngine.re_evaluate_stored_jobs(session)
    except Exception as re_err:
        logger.warning(f"Relevance re-evaluation after preferences update warning: {re_err}")
    return updated


# ---------------------------------------------------------------------------
# Skills endpoints
# ---------------------------------------------------------------------------
@router.post("/skills", response_model=CandidateSkillRead, status_code=status.HTTP_201_CREATED)
async def add_candidate_skill(
    skill: CandidateSkillCreate, session: AsyncSession = Depends(get_db)
):
    """Add a new verified skill to candidate profile."""
    return await CandidateService.add_skill(session, skill)


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate_skill(
    skill_id: str, session: AsyncSession = Depends(get_db)
):
    """Delete a skill by ID."""
    await CandidateService.delete_skill(session, skill_id)


# ---------------------------------------------------------------------------
# Experience endpoints
# ---------------------------------------------------------------------------
@router.post("/experiences", response_model=CandidateExperienceRead, status_code=status.HTTP_201_CREATED)
async def add_candidate_experience(
    exp: CandidateExperienceCreate, session: AsyncSession = Depends(get_db)
):
    """Add a work experience item to candidate profile."""
    return await CandidateService.add_experience(session, exp)


@router.delete("/experiences/{exp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate_experience(
    exp_id: str, session: AsyncSession = Depends(get_db)
):
    """Delete an experience item by ID."""
    await CandidateService.delete_experience(session, exp_id)


# ---------------------------------------------------------------------------
# Education endpoints
# ---------------------------------------------------------------------------
@router.post("/educations", response_model=CandidateEducationRead, status_code=status.HTTP_201_CREATED)
async def add_candidate_education(
    edu: CandidateEducationCreate, session: AsyncSession = Depends(get_db)
):
    """Add an education record to candidate profile."""
    return await CandidateService.add_education(session, edu)


@router.delete("/educations/{edu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate_education(
    edu_id: str, session: AsyncSession = Depends(get_db)
):
    """Delete an education record by ID."""
    await CandidateService.delete_education(session, edu_id)


# ---------------------------------------------------------------------------
# Project endpoints
# ---------------------------------------------------------------------------
@router.post("/projects", response_model=CandidateProjectRead, status_code=status.HTTP_201_CREATED)
async def add_candidate_project(
    proj: CandidateProjectCreate, session: AsyncSession = Depends(get_db)
):
    """Add a demonstrable project to candidate profile."""
    return await CandidateService.add_project(session, proj)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate_project(
    project_id: str, session: AsyncSession = Depends(get_db)
):
    """Delete a project by ID."""
    await CandidateService.delete_project(session, project_id)


# ---------------------------------------------------------------------------
# Master Resume Import endpoints
# ---------------------------------------------------------------------------
@router.post("/import-resume", response_model=ResumeImportResult)
async def import_master_resume(file: UploadFile = File(...)):
    """Upload and extract a draft candidate profile from a master PDF resume."""
    file_bytes = await file.read()
    return ResumeParserService.parse_pdf_bytes(file_bytes, file.filename or "resume.pdf")


@router.post(
    "/import-resume/confirm",
    response_model=CandidateProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_imported_resume(
    request: ResumeImportConfirmRequest, session: AsyncSession = Depends(get_db)
):
    """Confirm and save extracted draft profile into verified candidate profile."""
    for skill in request.confirmed_profile.skills:
        skill.is_verified = True
    return await CandidateService.create_profile(session, request.confirmed_profile)
