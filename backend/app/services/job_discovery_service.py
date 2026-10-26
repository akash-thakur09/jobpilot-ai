from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.collectors import get_adapter
from backend.app.collectors.base import NormalizedJob
from backend.app.models.job import Job, JobSource
from backend.app.models.automation import AutomationRun
from backend.app.models.enums import AutomationRunStatus, JobStatus
from backend.app.core.logging import logger


class JobDiscoveryService:
    @classmethod
    async def get_or_create_source(
        cls, session: AsyncSession, identifier: str, name: str, base_url: str, rate_limit: int = 30
    ) -> JobSource:
        """Finds or creates a JobSource record by identifier."""
        result = await session.execute(
            select(JobSource).where(JobSource.identifier == identifier)
        )
        source = result.scalar_one_or_none()
        if not source:
            source = JobSource(
                identifier=identifier,
                name=name,
                base_url=base_url,
                rate_limit_rpm=rate_limit,
                is_enabled=True,
            )
            session.add(source)
            await session.commit()
            await session.refresh(source)
        return source

    @classmethod
    async def run_discovery(
        cls,
        session: AsyncSession,
        source_identifier: str,
        adapter_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a discovery run for the specified source.
        Ensures strict deduplication via database transaction and records an AutomationRun.
        """
        adapter_params = adapter_params or {}
        adapter = get_adapter(source_identifier)

        # 1. Initialize AutomationRun log
        run = AutomationRun(
            run_type="discovery",
            status=AutomationRunStatus.RUNNING.value,
            metadata_json={"source": source_identifier, "params": {k: v for k, v in adapter_params.items() if k != "fixtures"}},
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)

        # 2. Get JobSource record
        source = await cls.get_or_create_source(
            session=session,
            identifier=adapter.source_identifier,
            name=adapter.source_name,
            base_url="https://jobs.example.com",
            rate_limit=adapter.rate_limit_rpm,
        )

        inserted_count = 0
        updated_count = 0
        unchanged_count = 0
        failed_count = 0

        try:
            # 3. Fetch raw listings
            raw_listings = await adapter.fetch_jobs(**adapter_params)
            run.items_processed = len(raw_listings)

            # 4. Process and persist each listing atomically
            for raw_item in raw_listings:
                try:
                    normalized = adapter.normalize(raw_item)

                    # Check for existing job by (source_id, external_id)
                    existing_query = await session.execute(
                        select(Job).where(
                            Job.source_id == source.id,
                            Job.external_id == normalized.external_id,
                        )
                    )
                    existing_job = existing_query.scalar_one_or_none()

                    if existing_job:
                        # Check for updates in description or title
                        has_changes = False
                        if existing_job.title != normalized.title:
                            existing_job.title = normalized.title
                            has_changes = True
                        if existing_job.description != normalized.description:
                            existing_job.description = normalized.description
                            has_changes = True
                        if existing_job.location != normalized.location:
                            existing_job.location = normalized.location
                            has_changes = True

                        if has_changes:
                            existing_job.updated_at = datetime.now(timezone.utc)
                            updated_count += 1
                        else:
                            unchanged_count += 1
                    else:
                        # Insert brand new job
                        new_job = Job(
                            source_id=source.id,
                            external_id=normalized.external_id,
                            title=normalized.title,
                            company=normalized.company,
                            canonical_url=normalized.canonical_url,
                            location=normalized.location,
                            remote_type=normalized.remote_type.value,
                            employment_type=normalized.employment_type,
                            description=normalized.description,
                            salary_min=normalized.salary_min,
                            salary_max=normalized.salary_max,
                            currency=normalized.currency,
                            status=JobStatus.DISCOVERED.value,
                            raw_payload=normalized.raw_payload,
                        )
                        session.add(new_job)
                        inserted_count += 1

                except Exception as item_exc:
                    logger.error(f"Error processing item {raw_item.external_id}: {item_exc}")
                    failed_count += 1

            # Update source last_discovered_at
            source.last_discovered_at = datetime.now(timezone.utc)

            # Update and complete automation run
            run.items_succeeded = inserted_count + updated_count + unchanged_count
            run.items_failed = failed_count
            run.status = AutomationRunStatus.COMPLETED.value
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()

            return {
                "run_id": run.id,
                "source": source_identifier,
                "items_processed": len(raw_listings),
                "inserted": inserted_count,
                "updated": updated_count,
                "unchanged": unchanged_count,
                "failed": failed_count,
                "status": "COMPLETED",
            }

        except Exception as exc:
            await session.rollback()
            logger.error(f"Discovery run failed for source '{source_identifier}': {exc}", exc_info=True)
            # Log failure in run
            run.status = AutomationRunStatus.FAILED.value
            run.error_summary = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            session.add(run)
            await session.commit()
            raise
