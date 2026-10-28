import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.session import AsyncSessionLocal
from backend.app.models.automation import AutomationRun
from backend.app.models.enums import AutomationRunStatus
from backend.app.services.discovery_pipeline import DiscoveryMatchingPipeline


class SchedulerService:
    """
    Manages background scheduled discovery execution using APScheduler.
    Enforces process-level non-overlapping runs, dynamic interval reconfiguration,
    and safe lifecycle management for FastAPI lifespan.
    """

    _scheduler: Optional[AsyncIOScheduler] = None
    _run_lock = asyncio.Lock()
    _is_running_discovery: bool = False
    _is_enabled: bool = settings.SCHEDULER_ENABLED
    _interval_minutes: int = settings.DISCOVERY_INTERVAL_MINUTES
    _job_id: str = "scheduled_job_discovery"
    _digest_job_id: str = "scheduled_job_digest"

    @classmethod
    def get_scheduler(cls) -> AsyncIOScheduler:
        """Returns or creates the underlying AsyncIOScheduler instance bound to the current event loop."""
        current_loop = None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if cls._scheduler is None or (
            current_loop is not None and getattr(cls._scheduler, "_eventloop", None) != current_loop
        ):
            if cls._scheduler and cls._scheduler.running:
                try:
                    cls._scheduler.shutdown(wait=False)
                except Exception:
                    pass
            cls._scheduler = AsyncIOScheduler(event_loop=current_loop)
        return cls._scheduler

    @classmethod
    async def scheduled_discovery_job(cls):
        """Job function executed on schedule by APScheduler."""
        logger.info("Scheduler triggered automated job discovery.")
        try:
            await cls.execute_discovery(trigger="scheduled")
        except Exception as exc:
            logger.error(f"Error during scheduled job discovery: {exc}", exc_info=True)

    @classmethod
    async def scheduled_digest_job(cls):
        """Job function executed periodically by APScheduler to process scheduled digests."""
        logger.info("Scheduler triggered automated digest processing.")
        try:
            from backend.app.services.digest_service import DigestService
            await DigestService.process_all_scheduled_digests()
        except Exception as exc:
            logger.error(f"Error during scheduled digest processing: {exc}", exc_info=True)

    @classmethod
    async def recover_stale_runs(cls, session: Optional[Any] = None) -> int:
        """
        Recovers from unexpected process termination or crash by marking any orphaned
        'RUNNING' discovery runs as 'FAILED' with an interrupted error summary.
        Returns the number of recovered runs.
        """
        async def _recover(s):
            stmt = select(AutomationRun).where(
                AutomationRun.run_type.like("discovery%"),
                AutomationRun.status == AutomationRunStatus.RUNNING.value,
            )
            res = await s.execute(stmt)
            stale_runs = res.scalars().all()
            for r in stale_runs:
                r.status = AutomationRunStatus.FAILED.value
                r.error_summary = "Discovery run interrupted by process termination or unexpected restart."
                r.completed_at = datetime.now(timezone.utc)
            if stale_runs:
                await s.commit()
                logger.warning(f"Recovered {len(stale_runs)} orphaned discovery run(s) left in RUNNING state.")
            return len(stale_runs)

        try:
            if session is not None:
                return await _recover(session)
            else:
                async with AsyncSessionLocal() as new_session:
                    return await _recover(new_session)
        except Exception as e:
            logger.error(f"Error recovering stale discovery runs: {e}")
            return 0

    @classmethod
    async def start(cls, session: Optional[Any] = None):
        """Initializes and starts the scheduler according to configuration."""
        # 1. Recover any runs interrupted by prior process termination
        await cls.recover_stale_runs(session=session)

        # 2. Reset running status
        cls._is_running_discovery = False

        scheduler = cls.get_scheduler()

        # Add or replace the scheduled job
        if scheduler.get_job(cls._job_id):
            scheduler.remove_job(cls._job_id)

        scheduler.add_job(
            cls.scheduled_discovery_job,
            trigger=IntervalTrigger(minutes=cls._interval_minutes),
            id=cls._job_id,
            name="JobPilot Scheduled Discovery",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        if scheduler.get_job(cls._digest_job_id):
            scheduler.remove_job(cls._digest_job_id)

        scheduler.add_job(
            cls.scheduled_digest_job,
            trigger=IntervalTrigger(minutes=15),
            id=cls._digest_job_id,
            name="JobPilot Scheduled Digest",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        if cls._is_enabled:
            if not scheduler.running:
                scheduler.start()
                logger.info(f"Scheduler started (enabled=True, interval={cls._interval_minutes}m).")
        else:
            logger.info(f"Scheduler initialized in disabled state (interval={cls._interval_minutes}m).")


    @classmethod
    async def shutdown(cls):
        """Safely shuts down the scheduler during FastAPI shutdown."""
        if cls._scheduler and cls._scheduler.running:
            logger.info("Shutting down scheduler...")
            cls._scheduler.shutdown(wait=False)
            logger.info("Scheduler shutdown complete.")

    @classmethod
    async def enable(cls) -> Dict[str, Any]:
        """Enables the background scheduler."""
        cls._is_enabled = True
        scheduler = cls.get_scheduler()

        if not scheduler.running:
            scheduler.start()
        else:
            job = scheduler.get_job(cls._job_id)
            if job and job.next_run_time is None:
                job.resume()
            d_job = scheduler.get_job(cls._digest_job_id)
            if d_job and d_job.next_run_time is None:
                d_job.resume()

        logger.info("Scheduler enabled.")
        return await cls.get_status()

    @classmethod
    async def disable(cls) -> Dict[str, Any]:
        """Disables the background scheduler."""
        cls._is_enabled = False
        scheduler = cls.get_scheduler()

        job = scheduler.get_job(cls._job_id)
        if job and scheduler.running:
            job.pause()
        d_job = scheduler.get_job(cls._digest_job_id)
        if d_job and scheduler.running:
            d_job.pause()

        logger.info("Scheduler disabled.")
        return await cls.get_status()

    @classmethod
    async def update_interval(cls, interval_minutes: int) -> Dict[str, Any]:
        """Updates discovery interval in minutes with strict range validation."""
        if interval_minutes < 5 or interval_minutes > 10080:  # 5 min to 7 days
            raise ValueError("Discovery interval must be between 5 and 10080 minutes (7 days).")

        cls._interval_minutes = interval_minutes
        scheduler = cls.get_scheduler()

        job = scheduler.get_job(cls._job_id)
        if job and scheduler.running:
            try:
                job.reschedule(trigger=IntervalTrigger(minutes=interval_minutes))
            except Exception as err:
                logger.warning(f"Could not reschedule job immediately: {err}")
        logger.info(f"Discovery interval updated to {interval_minutes} minutes.")

        return await cls.get_status()

    @classmethod
    async def execute_discovery(
        cls,
        trigger: str = "manual",
        sources: Optional[list] = None,
        source_params: Optional[dict] = None,
        use_ai_matching: bool = False,
        session: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Executes discovery using the shared pipeline under a process-level concurrency lock.
        Guarantees that manual and scheduled runs never overlap.
        """
        if cls._run_lock.locked():
            logger.warning("Discovery execution skipped: another discovery run is already in progress.")
            return {
                "status": "BUSY",
                "message": "A discovery run is already actively running. Overlapping runs are prohibited.",
            }

        async with cls._run_lock:
            cls._is_running_discovery = True
            try:
                if session is not None:
                    return await DiscoveryMatchingPipeline.execute(
                        session=session,
                        sources=sources,
                        source_params=source_params,
                        trigger=trigger,
                        use_ai_matching=use_ai_matching,
                    )
                else:
                    async with AsyncSessionLocal() as new_session:
                        return await DiscoveryMatchingPipeline.execute(
                            session=new_session,
                            sources=sources,
                            source_params=source_params,
                            trigger=trigger,
                            use_ai_matching=use_ai_matching,
                        )
            finally:
                cls._is_running_discovery = False

    @classmethod
    async def get_status(cls, session: Optional[Any] = None) -> Dict[str, Any]:
        """Returns comprehensive scheduler health, configuration, and latest run telemetry."""
        scheduler = cls._scheduler
        is_running = scheduler.running if scheduler else False
        next_run_iso = None

        if scheduler and is_running:
            job = scheduler.get_job(cls._job_id)
            if job and job.next_run_time:
                next_run_iso = job.next_run_time.isoformat()

        # Query latest discovery run from DB
        last_run_summary = None
        try:
            async def _query_last_run(s):
                query = (
                    select(AutomationRun)
                    .where(AutomationRun.run_type.like("discovery%"))
                    .order_by(AutomationRun.started_at.desc())
                    .limit(1)
                )
                res = await s.execute(query)
                return res.scalar_one_or_none()

            last_run = None
            if session is not None:
                last_run = await _query_last_run(session)
            else:
                async with AsyncSessionLocal() as new_session:
                    last_run = await _query_last_run(new_session)

            if last_run:
                last_run_summary = {
                    "id": last_run.id,
                    "run_type": last_run.run_type,
                    "status": last_run.status,
                    "items_processed": last_run.items_processed,
                    "items_succeeded": last_run.items_succeeded,
                    "items_failed": last_run.items_failed,
                    "error_summary": last_run.error_summary,
                    "started_at": last_run.started_at.isoformat() if last_run.started_at else None,
                    "completed_at": last_run.completed_at.isoformat() if last_run.completed_at else None,
                    "metadata": last_run.metadata_json,
                }
        except Exception as e:
            logger.warning(f"Could not load latest run telemetry: {e}")

        return {
            "is_enabled": cls._is_enabled,
            "scheduler_running": is_running,
            "is_active_run": cls._is_running_discovery,
            "interval_minutes": cls._interval_minutes,
            "next_run_time": next_run_iso,
            "last_run": last_run_summary,
        }

