import asyncio
import logging
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.config import settings
from backend.app.db.session import AsyncSessionLocal
from backend.app.models.candidate import CandidateProfile
from backend.app.models.enums import NotificationChannel, NotificationStatus, NotificationType
from backend.app.models.job import Job
from backend.app.models.matching import MatchScore
from backend.app.models.notification import Notification
from backend.app.services.candidate_service import CandidateService
from backend.app.services.email_service import EmailService

logger = logging.getLogger("jobpilot.digest_service")

# Concurrency lock to avoid overlapping digest execution
_digest_lock = asyncio.Lock()


class DigestService:
    @staticmethod
    def resolve_candidate_timezone(candidate: Optional[CandidateProfile] = None) -> ZoneInfo:
        """Resolves the candidate's timezone or falls back to system configured timezone or UTC."""
        tz_name = settings.TIMEZONE
        if candidate and candidate.notification_preferences:
            cand_tz = candidate.notification_preferences.get("timezone")
            if cand_tz and isinstance(cand_tz, str):
                tz_name = cand_tz.strip()

        try:
            return ZoneInfo(tz_name)
        except Exception as e:
            logger.warning(f"Invalid timezone '{tz_name}', falling back to UTC: {e}")
            return ZoneInfo("UTC")

    @classmethod
    def compute_next_digest_time(
        cls, candidate: Optional[CandidateProfile] = None, ref_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Computes the next scheduled digest run in candidate's local timezone.
        Returns a timezone-aware UTC datetime.
        """
        if not candidate:
            return None

        prefs = dict(candidate.notification_preferences or {})
        if not prefs.get("email_enabled", False):
            return None

        delivery_mode = prefs.get("delivery_mode", "IMMEDIATE").upper()
        if delivery_mode not in {"DAILY_DIGEST", "WEEKLY_DIGEST"}:
            return None

        tz = cls.resolve_candidate_timezone(candidate)
        base_now = ref_time or datetime.now(timezone.utc)
        local_now = base_now.astimezone(tz)

        # Parse daily target time (HH:MM)
        daily_time_str = settings.DIGEST_DAILY_TIME
        try:
            parts = daily_time_str.split(":")
            target_hour, target_minute = int(parts[0]), int(parts[1])
        except Exception:
            target_hour, target_minute = 9, 0

        target_time = time(hour=target_hour, minute=target_minute)

        if delivery_mode == "DAILY_DIGEST":
            candidate_today = datetime.combine(local_now.date(), target_time, tzinfo=tz)
            if local_now < candidate_today:
                next_local = candidate_today
            else:
                next_local = candidate_today + timedelta(days=1)
            return next_local.astimezone(timezone.utc)

        if delivery_mode == "WEEKLY_DIGEST":
            target_weekday = settings.DIGEST_WEEKLY_DAY  # 0 = Monday
            days_until = (target_weekday - local_now.weekday()) % 7
            candidate_target = datetime.combine(local_now.date() + timedelta(days=days_until), target_time, tzinfo=tz)

            if days_until == 0 and local_now >= candidate_target:
                candidate_target += timedelta(days=7)

            return candidate_target.astimezone(timezone.utc)

        return None

    @classmethod
    def get_current_period_key(
        cls, candidate: CandidateProfile, period: str, ref_time: Optional[datetime] = None
    ) -> str:
        """Generates deterministic period key (e.g. 2026-10-28 or 2026-W44) in candidate local timezone."""
        tz = cls.resolve_candidate_timezone(candidate)
        base_now = ref_time or datetime.now(timezone.utc)
        local_now = base_now.astimezone(tz)

        if period.lower() == "daily":
            return local_now.strftime("%Y-%m-%d")
        else:
            return local_now.strftime("%Y-W%W")

    @classmethod
    async def collect_pending_digest_matches(
        cls, session: AsyncSession, candidate: CandidateProfile
    ) -> List[Tuple[Job, MatchScore, Notification]]:
        """
        Collects eligible in-app notifications that:
        - Have NOT already been included in a digest (digest_id is None, digested_at is None)
        - Belong to channel IN_APP and type NEW_MATCH
        - Meet candidate's min_match_score threshold
        """
        prefs = dict(candidate.notification_preferences or {})
        min_score = prefs.get("min_match_score", settings.MATCH_NOTIFICATION_THRESHOLD)
        notify_matches = prefs.get("notify_new_matches", True)

        if not notify_matches:
            return []

        # Query undigested notifications
        query = (
            select(Notification)
            .where(
                and_(
                    Notification.channel == NotificationChannel.IN_APP.value,
                    Notification.notification_type == NotificationType.NEW_MATCH.value,
                    Notification.digest_id.is_(None),
                    Notification.digested_at.is_(None),
                    Notification.job_id.is_not(None),
                )
            )
            .order_by(Notification.created_at.desc())
        )

        res = await session.execute(query)
        in_app_notifs = res.scalars().all()

        if not in_app_notifs:
            return []

        # Filter by score and load associated jobs
        job_ids = [n.job_id for n in in_app_notifs if n.job_id]
        job_query = select(Job).where(Job.id.in_(job_ids))
        job_res = await session.execute(job_query)
        jobs_by_id = {j.id: j for j in job_res.scalars().all()}

        collected: List[Tuple[Job, MatchScore, Notification]] = []
        for notif in in_app_notifs:
            meta = notif.metadata_json or {}
            score_val = meta.get("score")

            if score_val is not None:
                try:
                    score_num = float(score_val)
                    if score_num < min_score:
                        continue
                except (ValueError, TypeError):
                    pass

            job = jobs_by_id.get(notif.job_id)
            if not job:
                continue

            # Synthesize or extract MatchScore for digest presentation
            mock_score = MatchScore(
                job_id=job.id,
                candidate_id=candidate.id,
                overall_score=float(score_val) if score_val is not None else 80.0,
                is_eligible=True,
                explanation=meta.get("explanation") or notif.message,
            )
            collected.append((job, mock_score, notif))

        return collected

    @classmethod
    async def is_digest_due_for_candidate(
        cls, session: AsyncSession, candidate: CandidateProfile, ref_time: Optional[datetime] = None
    ) -> Tuple[bool, str, str]:
        """
        Determines whether a scheduled digest is due for candidate based on local time and schedule.
        Returns: (is_due, period_name, period_key)
        """
        prefs = dict(candidate.notification_preferences or {})
        if not prefs.get("email_enabled", False):
            return False, "", ""

        delivery_mode = prefs.get("delivery_mode", "IMMEDIATE").upper()
        if delivery_mode not in {"DAILY_DIGEST", "WEEKLY_DIGEST"}:
            return False, "", ""

        tz = cls.resolve_candidate_timezone(candidate)
        base_now = ref_time or datetime.now(timezone.utc)
        local_now = base_now.astimezone(tz)

        # Parse target daily time
        daily_time_str = settings.DIGEST_DAILY_TIME
        try:
            parts = daily_time_str.split(":")
            target_hour, target_minute = int(parts[0]), int(parts[1])
        except Exception:
            target_hour, target_minute = 9, 0

        target_time = time(hour=target_hour, minute=target_minute)

        if delivery_mode == "DAILY_DIGEST":
            period = "daily"
            period_key = cls.get_current_period_key(candidate, period, ref_time)

            # Due if local time is past target time
            if local_now.time() < target_time:
                return False, period, period_key

            # Check if already delivered for this period
            dedup_key = f"email_digest:{candidate.id}:{period}:{period_key}"
            check_q = select(Notification).where(
                and_(
                    Notification.dedup_key == dedup_key,
                    Notification.status.in_([
                        NotificationStatus.SENT.value,
                        NotificationStatus.SIMULATED.value,
                        NotificationStatus.DELIVERED.value,
                    ]),
                )
            )
            res = await session.execute(check_q)
            if res.scalar_one_or_none():
                return False, period, period_key

            return True, period, period_key

        if delivery_mode == "WEEKLY_DIGEST":
            period = "weekly"
            period_key = cls.get_current_period_key(candidate, period, ref_time)
            target_weekday = settings.DIGEST_WEEKLY_DAY  # 0 = Monday

            # Due if today is on or after target weekday and past target time
            if local_now.weekday() < target_weekday or (
                local_now.weekday() == target_weekday and local_now.time() < target_time
            ):
                return False, period, period_key

            dedup_key = f"email_digest:{candidate.id}:{period}:{period_key}"
            check_q = select(Notification).where(
                and_(
                    Notification.dedup_key == dedup_key,
                    Notification.status.in_([
                        NotificationStatus.SENT.value,
                        NotificationStatus.SIMULATED.value,
                        NotificationStatus.DELIVERED.value,
                    ]),
                )
            )
            res = await session.execute(check_q)
            if res.scalar_one_or_none():
                return False, period, period_key

            return True, period, period_key

        return False, "", ""

    @classmethod
    async def send_scheduled_digest_for_candidate(
        cls,
        session: AsyncSession,
        candidate: CandidateProfile,
        force: bool = False,
        period_override: Optional[str] = None,
        period_key_override: Optional[str] = None,
    ) -> Optional[Notification]:
        """
        Processes and sends a scheduled digest for the candidate:
        1. Identifies pending undigested job notifications meeting criteria.
        2. Dispatches consolidated digest via EmailService with accurate status semantics.
        3. Idempotently marks covered in-app notifications with digest_id and digested_at.
        4. Handles failures cleanly without deleting notifications or corrupting state.
        """
        period = period_override or (
            "daily"
            if (candidate.notification_preferences or {}).get("delivery_mode") == "DAILY_DIGEST"
            else "weekly"
        )
        period_key = period_key_override or cls.get_current_period_key(candidate, period)

        pending = await cls.collect_pending_digest_matches(session, candidate)

        if not pending:
            logger.info(f"No pending eligible matches found for candidate {candidate.id} digest.")
            if not force:
                return None

        # Build list of (Job, MatchScore)
        matches_payload = [(j, s) for j, s, _ in pending]
        covered_in_app_notifs = [n for _, _, n in pending]

        # Send digest through EmailService
        digest_notif = await EmailService.send_digest(
            session=session,
            candidate=candidate,
            matches=matches_payload,
            period=period,
            period_key=period_key,
        )

        if not digest_notif:
            return None

        # If delivery was accepted (SIMULATED or SENT), record covered notifications
        if digest_notif.status in {
            NotificationStatus.SENT.value,
            NotificationStatus.SIMULATED.value,
            NotificationStatus.DELIVERED.value,
        }:
            now_utc = datetime.now(timezone.utc)
            for in_app in covered_in_app_notifs:
                in_app.digest_id = digest_notif.id
                in_app.digested_at = now_utc

            await session.commit()
            logger.info(
                f"Successfully processed digest '{digest_notif.id}' ({digest_notif.status}) covering {len(covered_in_app_notifs)} notifications."
            )
        else:
            logger.warning(
                f"Digest delivery ended with status '{digest_notif.status}'. Pending notifications will remain available for retry."
            )

        return digest_notif

    @classmethod
    async def process_all_scheduled_digests(cls) -> Dict[str, Any]:
        """
        Background scheduler job to check and process due digests for all candidates.
        Ensures concurrency protection and error isolation.
        """
        if _digest_lock.locked():
            logger.debug("Digest processing is already in progress. Skipping overlapping run.")
            return {"status": "SKIPPED", "reason": "Already running"}

        async with _digest_lock:
            async with AsyncSessionLocal() as session:
                candidates_res = await session.execute(select(CandidateProfile))
                candidates = candidates_res.scalars().all()

                processed_count = 0
                errors_count = 0

                for candidate in candidates:
                    try:
                        is_due, period, period_key = await cls.is_digest_due_for_candidate(session, candidate)
                        if is_due:
                            logger.info(
                                f"Digest is due for candidate {candidate.id} (period: {period}, key: {period_key}). Executing..."
                            )
                            result = await cls.send_scheduled_digest_for_candidate(
                                session=session,
                                candidate=candidate,
                                period_override=period,
                                period_key_override=period_key,
                            )
                            if result:
                                processed_count += 1
                    except Exception as exc:
                        errors_count += 1
                        logger.error(f"Error processing scheduled digest for candidate {candidate.id}: {exc}", exc_info=True)

                return {
                    "status": "COMPLETED",
                    "processed_count": processed_count,
                    "errors_count": errors_count,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
