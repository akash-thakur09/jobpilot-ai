from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.automation import AutomationRun
from backend.app.services.scheduler_service import SchedulerService
from backend.app.schemas.scheduler import (
    SchedulerStatusResponse,
    SchedulerConfigUpdate,
    SchedulerRunRequest,
    AutomationRunItem,
    AutomationRunListResponse,
)

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(session: AsyncSession = Depends(get_db)):
    """Returns current scheduler configuration, execution status, and latest discovery telemetry."""
    status_data = await SchedulerService.get_status(session=session)
    return SchedulerStatusResponse(**status_data)


@router.post("/config", response_model=SchedulerStatusResponse)
async def update_scheduler_config(
    config: SchedulerConfigUpdate,
    session: AsyncSession = Depends(get_db),
):
    """
    Safely updates scheduler configuration.
    Allows enabling/disabling and adjusting discovery interval in minutes.
    """
    try:
        if config.interval_minutes is not None:
            await SchedulerService.update_interval(config.interval_minutes)
        if config.enabled is not None:
            if config.enabled:
                await SchedulerService.enable()
            else:
                await SchedulerService.disable()

        status_data = await SchedulerService.get_status(session=session)
        return SchedulerStatusResponse(**status_data)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/run", status_code=status.HTTP_200_OK)
async def trigger_manual_discovery(
    request: Optional[SchedulerRunRequest] = None,
    session: AsyncSession = Depends(get_db),
):
    """
    Triggers an immediate manual discovery and matching run using the shared pipeline.
    Rejects overlapping executions if a run is already active.
    """
    req = request or SchedulerRunRequest()
    result = await SchedulerService.execute_discovery(
        trigger="manual",
        sources=req.sources,
        use_ai_matching=req.use_ai_matching,
        session=session,
    )
    if result.get("status") == "BUSY":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.get("message", "A discovery run is already in progress."),
        )
    return result


@router.get("/runs", response_model=AutomationRunListResponse)
async def list_discovery_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
    session: AsyncSession = Depends(get_db),
):
    """Lists history of discovery runs with pagination and status filtering."""
    filters = [AutomationRun.run_type.like("discovery%")]
    if status_filter:
        filters.append(AutomationRun.status == status_filter)

    # Count query
    count_stmt = select(func.count(AutomationRun.id)).where(and_(*filters))
    total_res = await session.execute(count_stmt)
    total = total_res.scalar() or 0

    # Data query
    data_stmt = (
        select(AutomationRun)
        .where(and_(*filters))
        .order_by(AutomationRun.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(data_stmt)
    runs = result.scalars().all()

    items = [
        AutomationRunItem(
            id=r.id,
            run_type=r.run_type,
            status=r.status,
            items_processed=r.items_processed,
            items_succeeded=r.items_succeeded,
            items_failed=r.items_failed,
            error_summary=r.error_summary,
            started_at=r.started_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
            metadata=r.metadata_json or {},
        )
        for r in runs
    ]

    return AutomationRunListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}", response_model=AutomationRunItem)
async def get_discovery_run(
    run_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Retrieves full details and sanitized source-level results for a specific discovery run."""
    stmt = select(AutomationRun).where(AutomationRun.id == run_id)
    res = await session.execute(stmt)
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Automation run '{run_id}' not found.",
        )

    return AutomationRunItem(
        id=run.id,
        run_type=run.run_type,
        status=run.status,
        items_processed=run.items_processed,
        items_succeeded=run.items_succeeded,
        items_failed=run.items_failed,
        error_summary=run.error_summary,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        metadata=run.metadata_json or {},
    )
