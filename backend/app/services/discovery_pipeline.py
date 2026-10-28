import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.collectors import get_adapter, ADAPTER_REGISTRY
from backend.app.collectors.base import BaseJobSourceAdapter, RawJobData, NormalizedJob
from backend.app.models.job import Job, JobSource
from backend.app.models.automation import AutomationRun
from backend.app.models.candidate import CandidateProfile
from backend.app.models.matching import MatchScore
from backend.app.models.enums import AutomationRunStatus, JobStatus, NotificationType, NotificationChannel
from backend.app.services.job_discovery_service import JobDiscoveryService
from backend.app.services.matching_service import MatchingService
from backend.app.services.notification_service import NotificationService
from backend.app.services.email_service import EmailService
from backend.app.core.config import settings
from backend.app.core.logging import logger


class DiscoveryMatchingPipeline:
    """
    Reusable, reliable job discovery, automated matching, and notification pipeline.
    Invoked both by manual API triggers and the background scheduler.
    """

    @classmethod
    async def execute(
        cls,
        session: AsyncSession,
        sources: Optional[List[str]] = None,
        source_params: Optional[Dict[str, Dict[str, Any]]] = None,
        trigger: str = "manual",
        use_ai_matching: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes the end-to-end 12-stage discovery, matching, and notification pipeline.
        
        Args:
            session: AsyncSession database session
            sources: List of source identifiers to run. If None, runs all supported sources.
            source_params: Optional dictionary of adapter parameters per source.
            trigger: 'manual' or 'scheduled'
            use_ai_matching: Whether to run optional AI semantic matching
        """
        target_sources = sources or list(ADAPTER_REGISTRY.keys())
        source_params = source_params or {}

        # Stage 1: Create persistent AutomationRun record
        run = AutomationRun(
            run_type=f"discovery_{trigger}",
            status=AutomationRunStatus.RUNNING.value,
            items_processed=0,
            items_succeeded=0,
            items_failed=0,
            metadata_json={
                "trigger": trigger,
                "sources_requested": target_sources,
                "sources_attempted": [],
                "source_diagnostics": {},
                "jobs_discovered": 0,
                "jobs_inserted": 0,
                "jobs_updated": 0,
                "jobs_evaluated": 0,
                "jobs_eligible": 0,
                "notifications_created": 0,
            },
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)

        logger.info(f"Started DiscoveryRun '{run.id}' triggered by '{trigger}' for sources: {target_sources}")

        # Metrics trackers
        total_discovered = 0
        total_inserted = 0
        total_updated = 0
        total_unchanged = 0
        total_source_failures = 0
        newly_saved_jobs: List[Job] = []
        source_diagnostics: Dict[str, Any] = {}
        successful_sources: List[str] = []
        failed_sources: List[str] = []

        semaphore = asyncio.Semaphore(settings.DISCOVERY_CONCURRENCY_LIMIT)

        # Stage 2 to 6: Fetch, normalize, deduplicate, and persist jobs per source
        for src_id in target_sources:
            async with semaphore:
                try:
                    adapter: BaseJobSourceAdapter = get_adapter(src_id)
                except ValueError as err:
                    logger.warning(f"Unsupported source '{src_id}': {err}")
                    failed_sources.append(src_id)
                    source_diagnostics[src_id] = {
                        "status": "FAILED",
                        "error": NotificationService.sanitize_text(str(err)),
                    }
                    continue

                params = source_params.get(src_id, {})
                try:
                    # Get or create source record in DB
                    source_record = await JobDiscoveryService.get_or_create_source(
                        session=session,
                        identifier=adapter.source_identifier,
                        name=adapter.source_name,
                        base_url="https://jobs.example.com",
                        rate_limit=adapter.rate_limit_rpm,
                    )

                    # Check if disabled (if sources list was not explicitly provided, respect is_enabled)
                    if not source_record.is_enabled and sources is None:
                        logger.info(f"Source '{src_id}' is disabled in configuration; skipping.")
                        continue

                    effective_params = dict(source_record.config_json or {})
                    effective_params.update(source_params.get(src_id, {}))

                    # Stage 3: Fetch jobs using adapter
                    raw_items = await adapter.fetch_jobs(**effective_params)
                    total_discovered += len(raw_items)

                    src_inserted = 0
                    src_updated = 0
                    src_unchanged = 0
                    src_failed = 0
                    seen_source_job_ids: List[str] = []

                    from backend.app.services.job_freshness_service import JobFreshnessService
                    from backend.app.models.enums import FreshnessStatus

                    # Stage 4 & 5: Normalize and deduplicate
                    for raw in raw_items:
                        try:
                            normalized = adapter.normalize(raw)

                            # Query existing by (source_id, external_id)
                            existing_stmt = select(Job).where(
                                Job.source_id == source_record.id,
                                Job.external_id == normalized.external_id,
                            )
                            existing_res = await session.execute(existing_stmt)
                            existing_job = existing_res.scalar_one_or_none()

                            if existing_job:
                                seen_source_job_ids.append(existing_job.id)
                                await JobFreshnessService.mark_job_verified_active(session, existing_job)

                                # Stage 6: Update existing job only if material fields changed
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
                                    src_updated += 1
                                    newly_saved_jobs.append(existing_job)
                                else:
                                    src_unchanged += 1
                            else:
                                now_dt = datetime.now(timezone.utc)
                                # Insert brand new job
                                new_job = Job(
                                    source_id=source_record.id,
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
                                    posted_at=getattr(normalized, "posted_at", None),
                                    first_seen_at=now_dt,
                                    last_seen_at=now_dt,
                                    last_verified_at=now_dt,
                                    freshness_status=FreshnessStatus.ACTIVE.value,
                                    freshness_reason="Initial discovery",
                                )
                                session.add(new_job)
                                await session.flush()
                                seen_source_job_ids.append(new_job.id)
                                src_inserted += 1
                                newly_saved_jobs.append(new_job)

                        except Exception as item_err:
                            logger.error(f"Error normalizing item {getattr(raw, 'external_id', 'unknown')} from {src_id}: {item_err}")
                            src_failed += 1

                    # Evaluate staleness for jobs from this source not seen in this run
                    try:
                        await JobFreshnessService.evaluate_source_staleness(
                            session=session,
                            source_id=source_record.id,
                            seen_job_ids=seen_source_job_ids,
                        )
                    except Exception as stale_err:
                        logger.warning(f"Staleness evaluation warning for source {src_id}: {stale_err}")

                    # Commit saved batch for this source
                    source_record.last_discovered_at = datetime.now(timezone.utc)
                    source_record.last_status = "HEALTHY"
                    source_record.last_error_summary = None
                    source_record.jobs_discovered_count = (source_record.jobs_discovered_count or 0) + len(raw_items)
                    await session.commit()

                    total_inserted += src_inserted
                    total_updated += src_updated
                    total_unchanged += src_unchanged

                    successful_sources.append(src_id)
                    source_diagnostics[src_id] = {
                        "status": "SUCCESS",
                        "discovered": len(raw_items),
                        "inserted": src_inserted,
                        "updated": src_updated,
                        "unchanged": src_unchanged,
                        "failed_items": src_failed,
                    }

                except Exception as src_exc:
                    await session.rollback()
                    total_source_failures += 1
                    failed_sources.append(src_id)
                    sanitized_err = NotificationService.sanitize_text(str(src_exc))
                    logger.error(f"Source '{src_id}' failed in pipeline: {sanitized_err}", exc_info=True)
                    source_diagnostics[src_id] = {
                        "status": "FAILED",
                        "error": sanitized_err,
                    }
                    try:
                        err_src = await JobDiscoveryService.get_or_create_source(
                            session=session,
                            identifier=src_id,
                            name=src_id.title(),
                            base_url="https://jobs.example.com",
                        )
                        err_src.last_status = "ERROR"
                        err_src.last_error_summary = sanitized_err
                        await session.commit()
                    except Exception:
                        await session.rollback()

        # Stage 6b: Cross-source duplicate detection and clustering
        if newly_saved_jobs:
            from backend.app.services.duplicate_detection_service import DuplicateDetectionService
            for j in newly_saved_jobs:
                try:
                    await DuplicateDetectionService.cluster_job(session, j)
                except Exception as dup_err:
                    logger.warning(f"Duplicate clustering failed gracefully for job {j.id}: {dup_err}")
            await session.commit()

        # Stage 7 to 9: Deterministic eligibility and scoring evaluation for new/updated jobs
        matching_service = MatchingService()
        candidate_res = await session.execute(select(CandidateProfile).limit(1))
        candidate = candidate_res.scalar_one_or_none()

        jobs_evaluated = 0
        jobs_eligible = 0
        new_relevant_matches: List[Tuple[Job, MatchScore]] = []

        if candidate and newly_saved_jobs:
            candidate_min_threshold = (candidate.notification_preferences or {}).get(
                "min_match_score", settings.MATCH_NOTIFICATION_THRESHOLD
            )
            for job in newly_saved_jobs:
                try:
                    match_record = await matching_service.evaluate_job(
                        session=session,
                        job_id=job.id,
                        candidate_id=candidate.id,
                        use_ai=use_ai_matching,
                    )
                    jobs_evaluated += 1
                    if match_record.is_eligible:
                        jobs_eligible += 1
                        # Stage 10: Identify newly relevant matches meeting candidate score threshold
                        if match_record.overall_score >= candidate_min_threshold:
                            new_relevant_matches.append((job, match_record))
                except Exception as match_err:
                    logger.warning(f"Could not evaluate matching for job {job.id}: {match_err}")
        else:
            if not candidate:
                logger.info("No candidate profile found. Skipping matching evaluation stage.")

        # Stage 11: Create notifications idempotently
        notifications_created = 0

        # In-app and optional email notifications for newly relevant eligible matches
        if candidate and new_relevant_matches:
            for rel_job, rel_match in new_relevant_matches:
                dedup_key = f"match:{candidate.id}:{rel_job.id}"
                try:
                    notif = await NotificationService.create_notification(
                        session=session,
                        title=f"New Eligible Job Match: {rel_job.title}",
                        message=f"{rel_job.company} is hiring for '{rel_job.title}' ({rel_job.location}). Passed all deterministic eligibility requirements.",
                        notification_type=NotificationType.NEW_MATCH,
                        channel=NotificationChannel.IN_APP,
                        job_id=rel_job.id,
                        run_id=run.id,
                        dedup_key=dedup_key,
                        metadata_json={
                            "company": rel_job.company,
                            "title": rel_job.title,
                            "job_id": rel_job.id,
                            "run_id": run.id,
                            "score": rel_match.overall_score,
                        },
                    )
                    if notif:
                        notifications_created += 1
                except Exception as notif_err:
                    logger.warning(f"Failed to create match notification: {notif_err}")

                # Optional email notification (provider failure does not affect in-app notification)
                try:
                    email_notif = await EmailService.send_match_notification(
                        session=session,
                        candidate=candidate,
                        job=rel_job,
                        match_score=rel_match,
                    )
                    if email_notif:
                        notifications_created += 1
                except Exception as email_err:
                    logger.warning(f"Email alert dispatch failed gracefully: {email_err}")

        # Stage 12: Finalize the run record with status, counts, and diagnostics
        if len(failed_sources) == 0 and len(successful_sources) > 0:
            final_status = AutomationRunStatus.COMPLETED.value
            error_summary = None
        elif len(successful_sources) > 0 and len(failed_sources) > 0:
            final_status = AutomationRunStatus.PARTIAL_SUCCESS.value
            failed_msgs = [f"{s}: {source_diagnostics[s].get('error')}" for s in failed_sources]
            error_summary = f"Partial failure: {'; '.join(failed_msgs)}"
        else:
            final_status = AutomationRunStatus.FAILED.value
            failed_msgs = [f"{s}: {source_diagnostics.get(s, {}).get('error', 'Unknown')}" for s in failed_sources]
            error_summary = f"Discovery run failed for all sources: {'; '.join(failed_msgs)}"

        # Failure & partial failure notifications
        if final_status == AutomationRunStatus.FAILED.value:
            await NotificationService.create_notification(
                session=session,
                title="Discovery Run Failed",
                message=f"Scheduled discovery failed completely for sources: {', '.join(failed_sources)}. Error: {error_summary}",
                notification_type=NotificationType.RUN_FAILED,
                channel=NotificationChannel.IN_APP,
                run_id=run.id,
                dedup_key=f"run_failed:{run.id}",
                metadata_json={"failed_sources": failed_sources, "error_summary": error_summary},
            )
            notifications_created += 1
        elif final_status == AutomationRunStatus.PARTIAL_SUCCESS.value:
            await NotificationService.create_notification(
                session=session,
                title="Discovery Run Partial Failure",
                message=f"Sources {', '.join(failed_sources)} failed during discovery, but {', '.join(successful_sources)} completed.",
                notification_type=NotificationType.PARTIAL_FAILURE,
                channel=NotificationChannel.IN_APP,
                run_id=run.id,
                dedup_key=f"run_partial:{run.id}",
                metadata_json={
                    "successful_sources": successful_sources,
                    "failed_sources": failed_sources,
                    "error_summary": error_summary,
                },
            )
            notifications_created += 1

        run.status = final_status
        run.items_processed = total_discovered
        run.items_succeeded = total_inserted + total_updated + total_unchanged
        run.items_failed = total_source_failures
        run.error_summary = error_summary
        run.completed_at = datetime.now(timezone.utc)
        run.metadata_json = {
            "trigger": trigger,
            "sources_requested": target_sources,
            "sources_attempted": successful_sources + failed_sources,
            "successful_sources": successful_sources,
            "failed_sources": failed_sources,
            "source_diagnostics": source_diagnostics,
            "jobs_discovered": total_discovered,
            "jobs_inserted": total_inserted,
            "jobs_updated": total_updated,
            "jobs_unchanged": total_unchanged,
            "jobs_evaluated": jobs_evaluated,
            "jobs_eligible": jobs_eligible,
            "new_relevant_matches": len(new_relevant_matches),
            "notifications_created": notifications_created,
        }

        session.add(run)
        await session.commit()
        await session.refresh(run)

        logger.info(
            f"Finalized DiscoveryRun '{run.id}' ({final_status}): Discovered={total_discovered}, "
            f"Inserted={total_inserted}, Evaluated={jobs_evaluated}, Eligible={jobs_eligible}"
        )

        return {
            "run_id": run.id,
            "status": final_status,
            "trigger": trigger,
            "items_processed": total_discovered,
            "inserted": total_inserted,
            "updated": total_updated,
            "unchanged": total_unchanged,
            "jobs_evaluated": jobs_evaluated,
            "jobs_eligible": jobs_eligible,
            "new_relevant_matches": len(new_relevant_matches),
            "notifications_created": notifications_created,
            "successful_sources": successful_sources,
            "failed_sources": failed_sources,
            "source_diagnostics": source_diagnostics,
            "error_summary": error_summary,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
