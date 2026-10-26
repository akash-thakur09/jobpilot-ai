from typing import List
from pathlib import Path
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.resumes.schemas import (
    ResumeGenerateRequest,
    ResumeVersionRead,
)
from backend.app.services.resume_version_service import ResumeVersionService
from backend.app.resumes.storage_service import ResumeStorageService

router = APIRouter(prefix="/resumes", tags=["Job-Specific Resumes"])


@router.post("/generate", response_model=ResumeVersionRead, status_code=status.HTTP_201_CREATED)
async def generate_tailored_resume(
    request: ResumeGenerateRequest, session: AsyncSession = Depends(get_db)
):
    """
    Generates a tailored, factually verified, ATS-compliant resume PDF for a specific job.
    Saves an immutable version record and file checksum.
    """
    return await ResumeVersionService.generate_tailored_resume(
        session=session,
        job_id=request.job_id,
        use_ai=request.use_ai,
        force_regenerate=request.force_regenerate,
    )


@router.get("/{version_id}", response_model=ResumeVersionRead)
async def get_resume_version(
    version_id: str, session: AsyncSession = Depends(get_db)
):
    """Retrieves metadata and validation reports for a specific resume version."""
    return await ResumeVersionService.get_version_by_id(session, version_id)


@router.get("/job/{job_id}", response_model=List[ResumeVersionRead])
async def list_resumes_for_job(
    job_id: str, session: AsyncSession = Depends(get_db)
):
    """Lists all historical resume versions generated for a job."""
    return await ResumeVersionService.list_versions_for_job(session, job_id)


@router.get("/{version_id}/download")
async def download_resume_pdf(
    version_id: str, session: AsyncSession = Depends(get_db)
):
    """Downloads the exact immutable PDF bytes associated with this resume version."""
    version = await ResumeVersionService.get_version_by_id(session, version_id)
    pdf_path = ResumeStorageService.get_resume_pdf_path(version.pdf_file_path)

    cand_name = version.candidate_snapshot.get("full_name", "Candidate").replace(" ", "_")
    filename = f"{cand_name}_Resume_v{version.version_number}.pdf"

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
    )


@router.get("/{version_id}/integrity")
async def verify_resume_integrity(
    version_id: str, session: AsyncSession = Depends(get_db)
):
    """Verifies that the stored PDF on disk matches its recorded SHA-256 checksum."""
    version = await ResumeVersionService.get_version_by_id(session, version_id)
    is_intact = ResumeStorageService.verify_file_integrity(
        version.pdf_file_path, version.file_sha256
    )
    return {
        "version_id": version.id,
        "is_intact": is_intact,
        "recorded_sha256": version.file_sha256,
        "file_path": version.pdf_file_path,
        "is_submission_ready": version.is_submission_ready,
    }
