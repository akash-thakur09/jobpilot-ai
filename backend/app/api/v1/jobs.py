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
    JobSourceConfigUpdate,
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
    """List all registered job sources, configuration, and health diagnostics."""
    return await JobDiscoveryService.get_all_sources(session)


@router.get("/sources/{identifier}", response_model=JobSourceRead)
async def get_job_source(identifier: str, session: AsyncSession = Depends(get_db)):
    """Retrieve details and health of a specific discovery source."""
    try:
        source = await JobDiscoveryService.get_source_by_identifier(session, identifier)
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job source '{identifier}' not found.")
        return source
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.put("/sources/{identifier}", response_model=JobSourceRead)
async def update_job_source_config(
    identifier: str,
    update_data: JobSourceConfigUpdate,
    session: AsyncSession = Depends(get_db),
):
    """
    Configures board identifier and enabled state for a supported job source.
    Rejects arbitrary URLs and validates identifier format.
    """
    try:
        return await JobDiscoveryService.update_source_config(session, identifier, update_data)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


from backend.app.models.job import Job, JobSource, JobDuplicateCluster
from backend.app.models.candidate import CandidateProfile
from backend.app.models.feedback import JobFeedback
from backend.app.schemas.job import (
    JobRead,
    JobListResponse,
    JobSourceRead,
    JobSourceConfigUpdate,
    JobDiscoveryRequest,
    JobDiscoveryResponse,
    JobDuplicateClusterRead,
    DuplicateReviewRequest,
    JobFeedbackCreate,
    JobFeedbackRead,
    JobFreshnessRead,
)
from backend.app.services.job_discovery_service import JobDiscoveryService
from backend.app.services.duplicate_detection_service import DuplicateDetectionService
from backend.app.services.feedback_service import FeedbackService
from sqlalchemy.orm import selectinload


@router.get("/duplicates", response_model=list[JobDuplicateClusterRead])
async def list_duplicate_clusters(
    cluster_status: Optional[str] = Query(None, description="FILTER by DETECTED, CONFIRMED, DISMISSED"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """List cross-source duplicate clusters and their grouped listings."""
    stmt = (
        select(JobDuplicateCluster)
        .options(selectinload(JobDuplicateCluster.jobs))
        .offset(offset)
        .limit(limit)
        .order_by(JobDuplicateCluster.created_at.desc())
    )
    if cluster_status:
        stmt = stmt.where(JobDuplicateCluster.cluster_status == cluster_status.upper())

    res = await session.execute(stmt)
    return list(res.scalars().all())


@router.post("/duplicates/{cluster_id}/review", response_model=JobDuplicateClusterRead)
async def review_duplicate_cluster(
    cluster_id: str,
    request: DuplicateReviewRequest,
    session: AsyncSession = Depends(get_db),
):
    """Confirm or dismiss a detected duplicate cluster."""
    try:
        return await DuplicateDetectionService.review_cluster(
            session=session,
            cluster_id=cluster_id,
            action=request.action,
            notes=request.notes,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get("/{job_id}/freshness", response_model=JobFreshnessRead)
async def get_job_freshness(job_id: str, session: AsyncSession = Depends(get_db)):
    """Retrieve job verification history and freshness status."""
    res = await session.execute(select(Job).where(Job.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    return JobFreshnessRead(
        job_id=job.id,
        freshness_status=job.freshness_status,
        freshness_reason=job.freshness_reason,
        first_seen_at=job.first_seen_at,
        last_seen_at=job.last_seen_at,
        last_verified_at=job.last_verified_at,
        posted_at=job.posted_at,
    )


@router.post("/{job_id}/feedback", response_model=JobFeedbackRead)
async def submit_job_feedback(
    job_id: str,
    request: JobFeedbackCreate,
    candidate_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """Submit idempotent user feedback on a job recommendation."""
    if not candidate_id:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        candidate = cand_res.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found.")
        candidate_id = candidate.id

    try:
        feedback = await FeedbackService.record_feedback(
            session=session,
            candidate_id=candidate_id,
            job_id=job_id,
            feedback_type=request.feedback_type,
            reason=request.reason,
            structured_details=request.structured_details,
        )
        return feedback
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get("/{job_id}/feedback", response_model=Optional[JobFeedbackRead])
async def get_job_feedback(
    job_id: str,
    candidate_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """Retrieve existing user feedback for a job."""
    if not candidate_id:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        candidate = cand_res.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found.")
        candidate_id = candidate.id

    feedback = await FeedbackService.get_feedback(session, candidate_id, job_id)
    return feedback


@router.delete("/{job_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_feedback(
    job_id: str,
    candidate_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """Remove user feedback for a job."""
    if not candidate_id:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        candidate = cand_res.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found.")
        candidate_id = candidate.id

    await FeedbackService.delete_feedback(session, candidate_id, job_id)
    return None


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
