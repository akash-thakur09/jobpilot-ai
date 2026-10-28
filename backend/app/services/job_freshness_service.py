from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import logger
from backend.app.models.job import Job, JobSource
from backend.app.models.enums import FreshnessStatus, JobStatus


class JobFreshnessService:
    """
    Job Freshness & Staleness Management Service.
    
    States:
    - ACTIVE: Recently verified active within staleness threshold.
    - POTENTIALLY_STALE: Has not been observed across multiple discovery cycles or exceeded threshold.
    - CONFIRMED_CLOSED: Authoritatively confirmed closed/expired by source adapter (e.g. 404 or inactive flag).
    - UNKNOWN: Source cannot be queried or verification has failed.
    """

    DEFAULT_STALENESS_DAYS = 14
    EXPIRATION_DAYS = 45

    @classmethod
    async def mark_job_verified_active(
        cls, session: AsyncSession, job: Job, verified_at: Optional[datetime] = None
    ) -> Job:
        """
        Record that a job was authoritatively seen in a successful source scrape.
        Supports reactivation from POTENTIALLY_STALE or CONFIRMED_CLOSED if authoritatively re-seen.
        """
        now = verified_at or datetime.now(timezone.utc)
        prev_status = job.freshness_status
        job.last_seen_at = now
        job.last_verified_at = now
        job.freshness_status = FreshnessStatus.ACTIVE.value
        
        if prev_status in (FreshnessStatus.POTENTIALLY_STALE.value, FreshnessStatus.CONFIRMED_CLOSED.value):
            job.freshness_reason = f"Re-verified active during discovery run (previously {prev_status})"
            job.status = JobStatus.DISCOVERED.value  # un-archive if archived
            logger.info(f"Reactivated job '{job.id}' to ACTIVE (previously {prev_status})")
        else:
            job.freshness_reason = "Verified active in latest discovery run"

        await session.flush()
        return job

    @classmethod
    async def mark_job_closed(
        cls, session: AsyncSession, job: Job, reason: str = "Authoritatively confirmed closed by source"
    ) -> Job:
        """
        Mark a job as confirmed closed (e.g., job portal returned 404/closed for this specific requisition).
        Does NOT hard delete records or alter applications/resumes.
        """
        job.freshness_status = FreshnessStatus.CONFIRMED_CLOSED.value
        job.freshness_reason = reason
        job.status = JobStatus.EXPIRED.value
        job.last_verified_at = datetime.now(timezone.utc)
        await session.flush()
        logger.info(f"Marked job '{job.id}' as CONFIRMED_CLOSED. Reason: {reason}")
        return job

    @classmethod
    async def mark_job_unknown(
        cls, session: AsyncSession, job: Job, reason: str = "Source endpoint check failed or timed out"
    ) -> Job:
        """
        Source failure or timeout does NOT mean the job is closed or stale.
        It is tracked distinctly as UNKNOWN.
        """
        job.freshness_status = FreshnessStatus.UNKNOWN.value
        job.freshness_reason = reason
        await session.flush()
        return job

    @classmethod
    async def evaluate_source_staleness(
        cls,
        session: AsyncSession,
        source_id: str,
        seen_job_ids: List[str],
        staleness_days: int = DEFAULT_STALENESS_DAYS,
    ) -> Dict[str, int]:
        """
        After a successful discovery run for a specific source, evaluate jobs from that source.
        Only marks POTENTIALLY_STALE if the job was NOT seen in this run AND its last_seen_at exceeds staleness_days.
        Never marks CONFIRMED_CLOSED on mere omission.
        """
        now = datetime.now(timezone.utc)
        threshold_dt = now - timedelta(days=staleness_days)

        # Query all jobs from this source that are currently ACTIVE and were not seen in this run
        stmt = (
            select(Job)
            .where(
                Job.source_id == source_id,
                Job.freshness_status == FreshnessStatus.ACTIVE.value,
                Job.id.not_in(seen_job_ids) if seen_job_ids else True,
            )
        )
        res = await session.execute(stmt)
        candidates = res.scalars().all()

        stale_count = 0
        for job in candidates:
            last_seen = job.last_seen_at or job.discovered_at
            if last_seen and last_seen < threshold_dt:
                job.freshness_status = FreshnessStatus.POTENTIALLY_STALE.value
                days_unseen = (now - last_seen).days
                job.freshness_reason = f"Unseen for {days_unseen} days across completed discovery runs"
                stale_count += 1

        await session.flush()
        return {"evaluated": len(candidates), "marked_stale": stale_count}

    @classmethod
    def get_freshness_warning(cls, job: Job) -> Optional[str]:
        """
        Return a user-facing warning if listing freshness is degraded.
        """
        if job.freshness_status == FreshnessStatus.CONFIRMED_CLOSED.value:
            return f"Listing is confirmed closed ({job.freshness_reason or 'No longer active'})."
        if job.freshness_status == FreshnessStatus.POTENTIALLY_STALE.value:
            return f"Listing may be stale ({job.freshness_reason or 'Not seen in recent scrapes'})."
        if job.freshness_status == FreshnessStatus.UNKNOWN.value:
            return f"Freshness verification unknown ({job.freshness_reason or 'Source verification pending'})."
        return None
