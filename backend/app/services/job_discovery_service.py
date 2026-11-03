from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.collectors import get_adapter, ADAPTER_REGISTRY
from backend.app.collectors.base import NormalizedJob
from backend.app.models.job import Job, JobSource
from backend.app.models.automation import AutomationRun
from backend.app.models.enums import AutomationRunStatus, JobStatus, RemoteType, RelevanceClassification, FreshnessStatus
from backend.app.schemas.job import JobSourceConfigUpdate
from backend.app.core.logging import logger


class JobDiscoveryService:
    @classmethod
    async def get_or_create_source(
        cls,
        session: AsyncSession,
        identifier: str,
        name: str,
        base_url: str,
        rate_limit: int = 30,
        source_type: str = "job_board",
        integration_status: str = "AVAILABLE",
    ) -> JobSource:
        """Finds or creates a JobSource record by identifier and syncs metadata."""
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
                config_json={},
                jobs_discovered_count=0,
                jobs_relevant_count=0,
                source_type=source_type,
                integration_status=integration_status,
            )
            session.add(source)
            await session.commit()
            await session.refresh(source)
        else:
            changed = False
            if source_type and source.source_type != source_type:
                source.source_type = source_type
                changed = True
            if integration_status and source.integration_status != integration_status:
                source.integration_status = integration_status
                changed = True
            if changed:
                await session.commit()
                await session.refresh(source)
        return source

    @classmethod
    async def get_all_sources(cls, session: AsyncSession) -> List[JobSource]:
        """Ensures all supported adapters are registered in DB and returns them."""
        for ident, adapter_cls in ADAPTER_REGISTRY.items():
            adapter = adapter_cls()
            await cls.get_or_create_source(
                session=session,
                identifier=adapter.source_identifier,
                name=adapter.source_name,
                base_url="https://jobs.example.com",
                rate_limit=adapter.rate_limit_rpm,
                source_type=adapter.source_type,
                integration_status=adapter.integration_status.value,
            )
        result = await session.execute(select(JobSource).order_by(JobSource.identifier))
        return list(result.scalars().all())

    @classmethod
    async def get_source_by_identifier(cls, session: AsyncSession, identifier: str) -> Optional[JobSource]:
        """Gets a source record by its identifier, creating it if it is a valid adapter."""
        adapter = get_adapter(identifier)
        return await cls.get_or_create_source(
            session=session,
            identifier=adapter.source_identifier,
            name=adapter.source_name,
            base_url="https://jobs.example.com",
            rate_limit=adapter.rate_limit_rpm,
            source_type=adapter.source_type,
            integration_status=adapter.integration_status.value,
        )

    @classmethod
    async def update_source_config(
        cls, session: AsyncSession, identifier: str, update_data: JobSourceConfigUpdate
    ) -> JobSource:
        """Updates board token, count, and enabled state for a supported source."""
        adapter = get_adapter(identifier)
        source = await cls.get_or_create_source(
            session=session,
            identifier=adapter.source_identifier,
            name=adapter.source_name,
            base_url="https://jobs.example.com",
            rate_limit=adapter.rate_limit_rpm,
            source_type=adapter.source_type,
            integration_status=adapter.integration_status.value,
        )

        current_config = dict(source.config_json or {})
        if update_data.is_enabled is not None:
            source.is_enabled = update_data.is_enabled

        if identifier.lower() == "greenhouse":
            if update_data.board_tokens is not None:
                cleaned = [t.strip() for t in update_data.board_tokens if t and str(t).strip()]
                current_config["board_tokens"] = cleaned
                if cleaned:
                    current_config["board_token"] = cleaned[0]
            elif update_data.board_token is not None:
                token_val = update_data.board_token.strip()
                current_config["board_token"] = token_val
                current_config["board_tokens"] = [t.strip() for t in token_val.split(",") if t.strip()]
        elif identifier.lower() == "lever":
            if update_data.site_tokens is not None:
                cleaned = [t.strip() for t in update_data.site_tokens if t and str(t).strip()]
                current_config["site_tokens"] = cleaned
                if cleaned:
                    current_config["site_token"] = cleaned[0]
            elif update_data.site_token is not None:
                token_val = update_data.site_token.strip()
                current_config["site_token"] = token_val
                current_config["site_tokens"] = [t.strip() for t in token_val.split(",") if t.strip()]
        elif identifier.lower() == "synthetic" and update_data.count is not None:
            current_config["count"] = update_data.count

        # Additional configuration for Indian sources & RSS/publishers
        for key in ["rss_url", "feed_url", "publisher_id", "category", "keywords", "location"]:
            val = getattr(update_data, key, None)
            if val is not None:
                current_config[key] = val

        source.config_json = current_config
        await session.commit()
        await session.refresh(source)
        return source

    @classmethod
    async def import_jobs_from_payload(
        cls,
        session: AsyncSession,
        source_identifier: str,
        payload: Any,
        format_type: str = "json",
    ) -> Dict[str, Any]:
        """
        Ingests manual jobs or email alerts for any source (Naukri, Instahyre, Cutshort, etc.).
        Evaluates relevance, checks duplicates, and persists valid listings.
        """
        adapter = get_adapter(source_identifier)
        source = await cls.get_or_create_source(
            session=session,
            identifier=adapter.source_identifier,
            name=adapter.source_name,
            base_url="https://jobs.example.com",
            rate_limit=adapter.rate_limit_rpm,
            source_type=adapter.source_type,
            integration_status=adapter.integration_status.value,
        )

        from backend.app.services.relevance_engine import RelevanceEngine
        from backend.app.services.candidate_service import CandidateService
        from backend.app.services.duplicate_detection_service import DuplicateDetectionService

        candidate_prefs = None
        try:
            candidate_prefs = await CandidateService.get_search_preferences(session)
        except Exception:
            pass

        # Fetch using manual import payload
        raw_items = await adapter.fetch_jobs(manual_import_payload=payload)

        saved_count = 0
        relevant_count = 0
        duplicates_count = 0
        errors: List[str] = []
        newly_saved: List[Job] = []

        for raw in raw_items:
            try:
                async with session.begin_nested():
                    normalized = adapter.normalize(raw)
                    relevance_res = RelevanceEngine.evaluate_job(
                        job_title=normalized.title,
                        job_description=normalized.description,
                        job_location=normalized.location,
                        remote_allowed=(normalized.remote_type == RemoteType.REMOTE),
                        job_work_mode=normalized.employment_type,
                        preferences=candidate_prefs,
                        job_salary_min=normalized.salary_min,
                        job_salary_max=normalized.salary_max,
                        job_currency=normalized.currency,
                    )
                    if relevance_res.classification in (
                        RelevanceClassification.HIGHLY_RELEVANT,
                        RelevanceClassification.POTENTIALLY_RELEVANT,
                    ):
                        relevant_count += 1

                    # Check if exists by source + external_id
                    stmt = select(Job).where(
                        Job.source_id == source.id,
                        Job.external_id == normalized.external_id,
                    )
                    res = await session.execute(stmt)
                    existing = res.scalar_one_or_none()

                    now_dt = datetime.now(timezone.utc)
                    if existing:
                        existing.title = normalized.title
                        existing.description = normalized.description
                        existing.location = normalized.location
                        existing.salary_min = normalized.salary_min
                        existing.salary_max = normalized.salary_max
                        existing.currency = normalized.currency
                        existing.relevance_score = relevance_res.score
                        existing.relevance_classification = relevance_res.classification.value
                        existing.relevance_metadata = relevance_res.to_dict()
                        existing.updated_at = now_dt
                        newly_saved.append(existing)
                        saved_count += 1
                    else:
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
                            relevance_score=relevance_res.score,
                            relevance_classification=relevance_res.classification.value,
                            relevance_metadata=relevance_res.to_dict(),
                            posted_at=getattr(normalized, "posted_at", None),
                            first_seen_at=now_dt,
                            last_seen_at=now_dt,
                            last_verified_at=now_dt,
                            freshness_status=FreshnessStatus.ACTIVE.value,
                            freshness_reason="Manual import ingestion",
                        )
                        session.add(new_job)
                        await session.flush()
                        newly_saved.append(new_job)
                        saved_count += 1

            except Exception as item_err:
                errors.append(f"Item {getattr(raw, 'external_id', 'unknown')}: {str(item_err)}")

        # Cross-source duplicate detection
        for j in newly_saved:
            try:
                cluster = await DuplicateDetectionService.cluster_job(session, j)
                if cluster and cluster.canonical_job_id != j.id:
                    duplicates_count += 1
            except Exception as dup_err:
                logger.warning(f"Duplicate clustering failed for {j.id}: {dup_err}")

        source.jobs_discovered_count = (source.jobs_discovered_count or 0) + len(raw_items)
        source.jobs_relevant_count = (source.jobs_relevant_count or 0) + relevant_count
        source.last_discovered_at = datetime.now(timezone.utc)
        source.last_status = "HEALTHY"
        await session.commit()

        return {
            "source_identifier": source_identifier,
            "items_received": len(payload) if isinstance(payload, list) else 1,
            "items_parsed": len(raw_items),
            "items_saved": saved_count,
            "items_relevant": relevant_count,
            "duplicates_detected": duplicates_count,
            "errors": errors,
        }

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
        run_id = str(run.id)

        # 2. Get JobSource record
        source = await cls.get_or_create_source(
            session=session,
            identifier=adapter.source_identifier,
            name=adapter.source_name,
            base_url="https://jobs.example.com",
            rate_limit=adapter.rate_limit_rpm,
            source_type=adapter.source_type,
            integration_status=adapter.integration_status.value,
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
            # Log failure in run - reload instance to avoid MissingGreenlet after rollback
            run_instance = await session.get(AutomationRun, run_id)
            if run_instance:
                run_instance.status = AutomationRunStatus.FAILED.value
                run_instance.error_summary = str(exc)
                run_instance.completed_at = datetime.now(timezone.utc)
                session.add(run_instance)
                await session.commit()
            raise
