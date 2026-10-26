from typing import Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.job import Job, JobSource
from backend.app.schemas.job import (
    JobRead,
    JobListResponse,
    JobSourceRead,
    JobDiscoveryRequest,
    JobDiscoveryResponse,
)
from backend.app.services.job_discovery_service import JobDiscoveryService

router = APIRouter(prefix="/jobs", tags=["Jobs & Discovery"])


@router.get("", response_model=JobListResponse)
async def list_jobs(
    company: Optional[str] = None,
    remote_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve discovered jobs with filtering, full-text keyword search, and pagination."""
    query = select(Job)
    count_query = select(func.count(Job.id))

    if company:
        query = query.where(Job.company.ilike(f"%{company}%"))
        count_query = count_query.where(Job.company.ilike(f"%{company}%"))

    if remote_type:
        query = query.where(Job.remote_type == remote_type.upper())
        count_query = count_query.where(Job.remote_type == remote_type.upper())

    if search:
        search_filter = Job.title.ilike(f"%{search}%") | Job.description.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(Job.discovered_at.desc()).offset(offset).limit(limit)
    jobs_result = await session.execute(query)
    items = jobs_result.scalars().all()

    return JobListResponse(
        items=list(items),
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sources", response_model=list[JobSourceRead])
async def list_job_sources(session: AsyncSession = Depends(get_db)):
    """List all registered job sources and their discovery status."""
    result = await session.execute(select(JobSource).order_by(JobSource.identifier))
    return list(result.scalars().all())


@router.get("/{job_id}", response_model=JobRead)
async def get_job_detail(job_id: str, session: AsyncSession = Depends(get_db)):
    """Retrieve details of a specific job listing."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


@router.post("/discover", response_model=JobDiscoveryResponse, status_code=status.HTTP_200_OK)
async def trigger_job_discovery(
    request: JobDiscoveryRequest, session: AsyncSession = Depends(get_db)
):
    """
    Triggers an immediate discovery run for a specific job source.
    Normalizes listings and enforces deduplication.
    """
    params = {}
    if request.board_token:
        params["board_token"] = request.board_token
    if request.site_token:
        params["site_token"] = request.site_token
    if request.count:
        params["count"] = request.count

    try:
        discovery_result = await JobDiscoveryService.run_discovery(
            session=session,
            source_identifier=request.source_identifier,
            adapter_params=params,
        )
        return discovery_result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job discovery failed: {str(exc)}",
        )
