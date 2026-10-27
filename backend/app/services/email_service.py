import asyncio
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.models.candidate import CandidateProfile
from backend.app.models.job import Job
from backend.app.models.matching import MatchScore
from backend.app.models.automation import AutomationRun
from backend.app.models.notification import Notification
from backend.app.models.enums import NotificationChannel, NotificationStatus, NotificationType
from backend.app.services.notification_service import NotificationService


class EmailService:
    """
    Optional email delivery service for JobPilot AI.
    Features:
    - Bounded retries
    - Mock, console, and SMTP delivery modes
    - Privacy protection: resumes or private profile data are never attached or included
    - Transactional in-app notification decoupling: provider failures never affect in-app notifications
    - Idempotent deduplication tracking in the notifications table
    """

    @classmethod
    def is_configured(cls) -> bool:
        """Returns True if email notifications are enabled and provider is configured."""
        if not settings.EMAIL_NOTIFICATIONS_ENABLED:
            return False
        if settings.EMAIL_PROVIDER in {"mock", "console"}:
            return True
        if settings.EMAIL_PROVIDER == "smtp" and settings.EMAIL_HOST:
            return True
        return False

    @classmethod
    def get_email_config_status(cls, candidate: Optional[CandidateProfile] = None) -> Dict[str, Any]:
        """Returns sanitized email configuration status without exposing credentials."""
        recipient = settings.EMAIL_TO or (candidate.email if candidate else None)
        return {
            "is_available": cls.is_configured(),
            "provider": settings.EMAIL_PROVIDER,
            "from_address": settings.EMAIL_FROM,
            "recipient": recipient,
            "email_notifications_enabled": settings.EMAIL_NOTIFICATIONS_ENABLED,
        }

    @classmethod
    async def send_email(
        cls,
        to_email: str,
        subject: str,
        body_text: str,
        max_retries: int = 2,
    ) -> Tuple[bool, Optional[str]]:
        """
        Sends an email using configured provider with bounded retries.
        Returns (success: bool, error_message: Optional[str]).
        """
        if not to_email:
            return False, "No recipient email address specified."

        provider = settings.EMAIL_PROVIDER.lower()
        clean_subject = NotificationService.sanitize_text(subject)

        # 1. Mock / Test provider
        if provider == "mock":
            logger.info(f"[MOCK EMAIL] To: {to_email} | Subject: {clean_subject} | Length: {len(body_text)} bytes")
            return True, None

        # 2. Console provider
        if provider == "console":
            print(f"\n===== [JOBPILOT EMAIL ALERT] =====\nTo: {to_email}\nSubject: {clean_subject}\n\n{body_text}\n==================================\n")
            return True, None

        # 3. SMTP provider with bounded retries
        if provider == "smtp":
            msg = EmailMessage()
            msg["Subject"] = clean_subject
            msg["From"] = settings.EMAIL_FROM
            msg["To"] = to_email
            msg.set_content(body_text)

            last_err = None
            for attempt in range(1, max_retries + 1):
                try:
                    def _sync_send():
                        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10) as server:
                            if settings.EMAIL_USE_TLS:
                                server.starttls()
                            if settings.EMAIL_USERNAME and settings.EMAIL_PASSWORD:
                                server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
                            server.send_message(msg)

                    await asyncio.to_thread(_sync_send)
                    logger.info(f"Successfully sent email to {to_email} on attempt {attempt}")
                    return True, None
                except Exception as exc:
                    sanitized_err = NotificationService.sanitize_text(str(exc))
                    last_err = sanitized_err
                    logger.warning(f"SMTP delivery attempt {attempt}/{max_retries} to {to_email} failed: {sanitized_err}")
                    if attempt < max_retries:
                        await asyncio.sleep(1.0 * attempt)

            return False, last_err or "SMTP delivery failed after retries."

        return False, f"Unsupported email provider '{provider}'."

    @classmethod
    async def send_match_notification(
        cls,
        session: AsyncSession,
        candidate: CandidateProfile,
        job: Job,
        match_score: MatchScore,
    ) -> Optional[Notification]:
        """
        Sends an immediate email alert for an eligible job match if enabled in candidate preferences.
        Guarantees:
        - Never sends repeated emails for the same candidate and job.
        - Never attaches resume or private profile data.
        - Records email notification record in database.
        """
        prefs = dict(candidate.notification_preferences or {})
        email_enabled = prefs.get("email_enabled", False)
        notify_matches = prefs.get("notify_new_matches", True)
        delivery_mode = prefs.get("delivery_mode", "IMMEDIATE").upper()
        min_score = prefs.get("min_match_score", 70)

        if not email_enabled or not notify_matches:
            logger.debug("Email notifications disabled or new matches alerts turned off in candidate preferences.")
            return None

        if delivery_mode != "IMMEDIATE":
            logger.debug(f"Delivery mode is {delivery_mode}; skipping immediate delivery.")
            return None

        if match_score.overall_score < min_score:
            logger.debug(f"Match score {match_score.overall_score} is below threshold {min_score}; skipping email.")
            return None

        recipient = prefs.get("recipient_email") or settings.EMAIL_TO or candidate.email
        if not recipient:
            logger.warning("No recipient email found for candidate.")
            return None

        # Deduplication check
        dedup_key = f"email_match:{candidate.id}:{job.id}"
        existing_stmt = select(Notification).where(Notification.dedup_key == dedup_key)
        existing_res = await session.execute(existing_stmt)
        if existing_res.scalar_one_or_none():
            logger.debug(f"Email match alert for job {job.id} already sent; skipping duplicate.")
            return None

        # Build privacy-preserving alert body
        subject = f"JobPilot Match: {job.title} at {job.company} ({match_score.overall_score:.0f}% Match)"
        body = (
            f"Hello {candidate.full_name},\n\n"
            f"JobPilot AI discovered a new eligible opportunity that aligns with your search preferences:\n\n"
            f"Role: {job.title}\n"
            f"Company: {job.company}\n"
            f"Location: {job.location} ({job.remote_type})\n"
            f"Match Score: {match_score.overall_score:.1f} / 100\n\n"
            f"Summary & Fit:\n{match_score.explanation}\n\n"
            f"To review details, generate a tailored ATS resume, and approve submission, open your local JobPilot dashboard:\n"
            f"http://localhost:5173/jobs\n\n"
            f"— JobPilot AI Local Agent"
        )

        success, err_msg = await cls.send_email(to_email=recipient, subject=subject, body_text=body)

        # Record in notifications table
        notif = Notification(
            title=subject,
            message=body,
            notification_type=NotificationType.NEW_MATCH.value,
            channel=NotificationChannel.EMAIL.value,
            status=NotificationStatus.DELIVERED.value if success else NotificationStatus.FAILED.value,
            is_read=True,
            is_dismissed=False,
            job_id=job.id,
            dedup_key=dedup_key,
            metadata_json={
                "recipient": recipient,
                "provider": settings.EMAIL_PROVIDER,
                "delivered": success,
                "error": err_msg,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        session.add(notif)
        await session.commit()
        await session.refresh(notif)
        return notif

    @classmethod
    async def send_digest(
        cls,
        session: AsyncSession,
        candidate: CandidateProfile,
        matches: List[Tuple[Job, MatchScore]],
    ) -> Optional[Notification]:
        """Sends a consolidated digest of relevant eligible matches."""
        if not matches:
            return None

        prefs = dict(candidate.notification_preferences or {})
        recipient = prefs.get("recipient_email") or settings.EMAIL_TO or candidate.email
        if not recipient:
            return None

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dedup_key = f"email_digest:{candidate.id}:{today_str}"
        existing_stmt = select(Notification).where(Notification.dedup_key == dedup_key)
        existing_res = await session.execute(existing_stmt)
        if existing_res.scalar_one_or_none():
            logger.debug(f"Daily digest for {today_str} already sent; skipping duplicate.")
            return None

        subject = f"JobPilot AI Digest: {len(matches)} New Eligible Job Matches ({today_str})"
        lines = [
            f"Hello {candidate.full_name},\n",
            f"Here is your JobPilot AI opportunity digest for {today_str}:\n",
        ]
        for idx, (job, score) in enumerate(matches[:10], start=1):
            lines.append(f"{idx}. {job.title} at {job.company} — {score.overall_score:.0f}% Match")
            lines.append(f"   Location: {job.location} | Remote: {job.remote_type}")
            lines.append(f"   Link: {job.canonical_url}\n")

        lines.append("Open your local JobPilot dashboard to prepare and review applications:")
        lines.append("http://localhost:5173/jobs\n\n— JobPilot AI")

        body = "\n".join(lines)
        success, err_msg = await cls.send_email(to_email=recipient, subject=subject, body_text=body)

        notif = Notification(
            title=subject,
            message=body,
            notification_type=NotificationType.NEW_MATCH.value,
            channel=NotificationChannel.EMAIL.value,
            status=NotificationStatus.DELIVERED.value if success else NotificationStatus.FAILED.value,
            is_read=True,
            is_dismissed=False,
            dedup_key=dedup_key,
            metadata_json={
                "recipient": recipient,
                "matches_count": len(matches),
                "delivered": success,
                "error": err_msg,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        session.add(notif)
        await session.commit()
        await session.refresh(notif)
        return notif

    @classmethod
    async def send_test_email(cls, recipient: str) -> Tuple[bool, str]:
        """Safe test-delivery workflow that does not contact real employers."""
        subject = "JobPilot AI: Test Alert Verification"
        body = (
            "This is a verification email from your local JobPilot AI instance.\n\n"
            "Email notification delivery is functioning properly.\n"
            "Real employer job application submissions remain disabled (JOBPILOT_REAL_SUBMISSION_ENABLED=False).\n\n"
            "— JobPilot AI"
        )
        success, err = await cls.send_email(to_email=recipient, subject=subject, body_text=body)
        if success:
            return True, f"Test email successfully dispatched to {recipient} via {settings.EMAIL_PROVIDER}."
        return False, f"Test email delivery failed: {err}"
