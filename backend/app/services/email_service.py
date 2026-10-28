import asyncio
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.models.candidate import CandidateProfile
from backend.app.models.job import Job
from backend.app.models.matching import MatchScore
from backend.app.models.notification import Notification
from backend.app.models.enums import NotificationChannel, NotificationStatus, NotificationType
from backend.app.services.notification_service import NotificationService


@dataclass
class EmailDeliveryResult:
    success: bool
    status: NotificationStatus
    status_detail: str
    error: Optional[str] = None
    is_simulated: bool = False
    attempts: List[Dict[str, Any]] = field(default_factory=list)


def is_permanent_smtp_error(exc: Exception) -> bool:
    """Identifies permanent SMTP errors that should not be retried."""
    if isinstance(
        exc,
        (
            smtplib.SMTPAuthenticationError,
            smtplib.SMTPSenderRefused,
            smtplib.SMTPRecipientsRefused,
            smtplib.SMTPNotSupportedError,
        ),
    ):
        return True
    if isinstance(exc, smtplib.SMTPDataError):
        code = getattr(exc, "smtp_code", None)
        if code and code >= 500:
            return True
    if isinstance(exc, smtplib.SMTPResponseException):
        if getattr(exc, "smtp_code", 0) >= 500:
            return True
    return False


class EmailService:
    """
    Robust email delivery service for JobPilot AI.
    Guarantees:
    - Accurate delivery semantics: SIMULATED (mock/console), SENT (accepted by SMTP), FAILED.
    - Bounded retries with exponential backoff for transient errors only; zero retry on permanent errors.
    - Privacy protection: resumes or private profile data are never attached or exposed.
    - Transactional in-app notification decoupling: email failures never delete or corrupt in-app notifications.
    - Idempotent deduplication tracking in the notifications table.
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
        prefs = dict(candidate.notification_preferences or {}) if candidate else {}
        tz = prefs.get("timezone", settings.TIMEZONE)
        return {
            "is_available": cls.is_configured(),
            "provider": settings.EMAIL_PROVIDER,
            "from_address": settings.EMAIL_FROM,
            "recipient": recipient,
            "email_notifications_enabled": settings.EMAIL_NOTIFICATIONS_ENABLED,
            "timezone": tz,
            "is_simulated": settings.EMAIL_PROVIDER in {"mock", "console"},
        }

    @classmethod
    async def send_email(
        cls,
        to_email: str,
        subject: str,
        body_text: str,
        max_retries: Optional[int] = None,
        backoff_base: Optional[float] = None,
    ) -> EmailDeliveryResult:
        """
        Sends an email using configured provider with bounded retries and status classification.
        Does not report mock output as real delivered email.
        Does not claim SMTP acceptance guarantees inbox delivery.
        """
        retries = max_retries if max_retries is not None else settings.EMAIL_MAX_RETRIES
        backoff = backoff_base if backoff_base is not None else settings.EMAIL_RETRY_BACKOFF_SECONDS

        if not to_email or "@" not in to_email:
            return EmailDeliveryResult(
                success=False,
                status=NotificationStatus.FAILED,
                status_detail="No valid recipient email address specified.",
                error="Invalid recipient email address.",
                is_simulated=False,
                attempts=[],
            )

        provider = settings.EMAIL_PROVIDER.lower()
        clean_subject = NotificationService.sanitize_text(subject)

        # 1. Mock provider
        if provider == "mock":
            logger.info(f"[MOCK EMAIL] To: {to_email} | Subject: {clean_subject} | Length: {len(body_text)} bytes")
            return EmailDeliveryResult(
                success=True,
                status=NotificationStatus.SIMULATED,
                status_detail="Simulated delivery via mock provider (no network transmission)",
                error=None,
                is_simulated=True,
                attempts=[
                    {
                        "attempt": 1,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status": NotificationStatus.SIMULATED.value,
                        "detail": "Mock transmission accepted",
                    }
                ],
            )

        # 2. Console provider
        if provider == "console":
            print(f"\n===== [JOBPILOT EMAIL ALERT] =====\nTo: {to_email}\nSubject: {clean_subject}\n\n{body_text}\n==================================\n")
            return EmailDeliveryResult(
                success=True,
                status=NotificationStatus.SIMULATED,
                status_detail="Simulated delivery via console stdout",
                error=None,
                is_simulated=True,
                attempts=[
                    {
                        "attempt": 1,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status": NotificationStatus.SIMULATED.value,
                        "detail": "Console print completed",
                    }
                ],
            )

        # 3. SMTP provider with transient/permanent error handling and bounded retries
        if provider == "smtp":
            if not settings.EMAIL_HOST:
                return EmailDeliveryResult(
                    success=False,
                    status=NotificationStatus.FAILED,
                    status_detail="SMTP host is not configured.",
                    error="EMAIL_HOST setting is empty.",
                    is_simulated=False,
                    attempts=[],
                )

            msg = EmailMessage()
            msg["Subject"] = clean_subject
            msg["From"] = settings.EMAIL_FROM
            msg["To"] = to_email
            msg.set_content(body_text)

            attempts: List[Dict[str, Any]] = []
            last_err: Optional[str] = None

            for attempt in range(1, retries + 1):
                attempt_ts = datetime.now(timezone.utc).isoformat()
                try:
                    def _sync_send():
                        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=10) as server:
                            if settings.EMAIL_USE_TLS:
                                server.starttls()
                            if settings.EMAIL_USERNAME and settings.EMAIL_PASSWORD:
                                server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
                            server.send_message(msg)

                    await asyncio.to_thread(_sync_send)
                    logger.info(f"Successfully handed off email to SMTP relay for {to_email} on attempt {attempt}")
                    attempts.append({
                        "attempt": attempt,
                        "timestamp": attempt_ts,
                        "status": NotificationStatus.SENT.value,
                        "detail": "Accepted by remote SMTP server for relay",
                    })
                    return EmailDeliveryResult(
                        success=True,
                        status=NotificationStatus.SENT,
                        status_detail="Accepted by SMTP transport for relay (inbox delivery depends on recipient server)",
                        error=None,
                        is_simulated=False,
                        attempts=attempts,
                    )
                except Exception as exc:
                    sanitized_err = NotificationService.sanitize_text(str(exc))
                    is_perm = is_permanent_smtp_error(exc)
                    last_err = sanitized_err
                    attempts.append({
                        "attempt": attempt,
                        "timestamp": attempt_ts,
                        "status": NotificationStatus.FAILED.value,
                        "error": sanitized_err,
                        "is_transient": not is_perm,
                    })
                    logger.warning(
                        f"SMTP delivery attempt {attempt}/{retries} to {to_email} failed: {sanitized_err} (permanent={is_perm})"
                    )

                    if is_perm:
                        logger.warning(f"Aborting retries due to permanent SMTP error: {sanitized_err}")
                        break

                    if attempt < retries:
                        sleep_time = backoff * (2 ** (attempt - 1))
                        await asyncio.sleep(sleep_time)

            return EmailDeliveryResult(
                success=False,
                status=NotificationStatus.FAILED,
                status_detail=f"SMTP handoff failed after {len(attempts)} attempt(s)",
                error=last_err or "SMTP delivery failed after retries.",
                is_simulated=False,
                attempts=attempts,
            )

        return EmailDeliveryResult(
            success=False,
            status=NotificationStatus.FAILED,
            status_detail=f"Unsupported email provider '{provider}'.",
            error=f"Unsupported email provider '{provider}'.",
            is_simulated=False,
            attempts=[],
        )

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
        - Records email notification record in database with accurate status (SIMULATED / SENT / FAILED).
        """
        prefs = dict(candidate.notification_preferences or {})
        email_enabled = prefs.get("email_enabled", False)
        notify_matches = prefs.get("notify_new_matches", True)
        delivery_mode = prefs.get("delivery_mode", "IMMEDIATE").upper()
        min_score = prefs.get("min_match_score", 70)

        if not email_enabled or not notify_matches:
            logger.debug("Email notifications disabled or new matches alerts turned off in candidate preferences.")
            return None

        if delivery_mode not in {"IMMEDIATE"}:
            logger.debug(f"Delivery mode is {delivery_mode}; skipping immediate delivery in favor of digest.")
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
        existing_notif = existing_res.scalar_one_or_none()
        if existing_notif:
            if existing_notif.status in {
                NotificationStatus.SENT.value,
                NotificationStatus.SIMULATED.value,
                NotificationStatus.DELIVERED.value,
            }:
                logger.debug(f"Email match alert for job {job.id} already sent/simulated; skipping duplicate.")
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

        delivery_res = await cls.send_email(to_email=recipient, subject=subject, body_text=body)
        if isinstance(delivery_res, tuple):
            s_ok, s_msg = delivery_res
            delivery_res = EmailDeliveryResult(
                success=s_ok,
                status=NotificationStatus.SENT if s_ok else NotificationStatus.FAILED,
                status_detail=str(s_msg),
                error=None if s_ok else str(s_msg),
                is_simulated=False,
                attempts=[{"attempt": 1, "timestamp": datetime.now(timezone.utc).isoformat(), "status": "SENT" if s_ok else "FAILED", "detail": str(s_msg)}],
            )

        notif = existing_notif or Notification(
            title=subject,
            message=body,
            notification_type=NotificationType.NEW_MATCH.value,
            channel=NotificationChannel.EMAIL.value,
            status=delivery_res.status.value,
            is_read=True,
            is_dismissed=False,
            job_id=job.id,
            dedup_key=dedup_key,
            metadata_json={},
        )

        notif.status = delivery_res.status.value
        notif.metadata_json = {
            "recipient": recipient,
            "provider": settings.EMAIL_PROVIDER,
            "delivery_status": delivery_res.status.value,
            "status_detail": delivery_res.status_detail,
            "is_simulated": delivery_res.is_simulated,
            "attempts": delivery_res.attempts,
            "attempt_count": len(delivery_res.attempts),
            "error": delivery_res.error,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

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
        period: str = "daily",
        period_key: Optional[str] = None,
        recipient_override: Optional[str] = None,
    ) -> Optional[Notification]:
        """
        Sends a consolidated digest of relevant eligible matches with accurate status semantics.
        """
        if not matches:
            return None

        prefs = dict(candidate.notification_preferences or {})
        recipient = recipient_override or prefs.get("recipient_email") or settings.EMAIL_TO or candidate.email
        if not recipient:
            return None

        key_str = period_key or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dedup_key = f"email_digest:{candidate.id}:{period}:{key_str}"
        existing_stmt = select(Notification).where(Notification.dedup_key == dedup_key)
        existing_res = await session.execute(existing_stmt)
        existing_notif = existing_res.scalar_one_or_none()
        if existing_notif:
            if existing_notif.status in {
                NotificationStatus.SENT.value,
                NotificationStatus.SIMULATED.value,
                NotificationStatus.DELIVERED.value,
            }:
                logger.debug(f"{period.capitalize()} digest for {key_str} already sent/simulated; skipping duplicate.")
                return None

        subject = f"JobPilot AI {period.capitalize()} Digest: {len(matches)} New Eligible Job Matches ({key_str})"
        lines = [
            f"Hello {candidate.full_name},\n",
            f"Here is your JobPilot AI {period} opportunity digest for {key_str}:\n",
        ]
        for idx, (job, score) in enumerate(matches[:15], start=1):
            lines.append(f"{idx}. {job.title} at {job.company} — {score.overall_score:.0f}% Match")
            lines.append(f"   Location: {job.location} | Remote: {job.remote_type}")
            lines.append(f"   Link: {job.canonical_url}\n")

        lines.append("Open your local JobPilot dashboard to prepare, review, and approve applications:")
        lines.append("http://localhost:5173/jobs\n\n— JobPilot AI")

        body = "\n".join(lines)
        delivery_res = await cls.send_email(to_email=recipient, subject=subject, body_text=body)
        if isinstance(delivery_res, tuple):
            s_ok, s_msg = delivery_res
            delivery_res = EmailDeliveryResult(
                success=s_ok,
                status=NotificationStatus.SENT if s_ok else NotificationStatus.FAILED,
                status_detail=str(s_msg),
                error=None if s_ok else str(s_msg),
                is_simulated=False,
                attempts=[{"attempt": 1, "timestamp": datetime.now(timezone.utc).isoformat(), "status": "SENT" if s_ok else "FAILED", "detail": str(s_msg)}],
            )

        notif = existing_notif or Notification(
            title=subject,
            message=body,
            notification_type=NotificationType.DIGEST.value,
            channel=NotificationChannel.EMAIL.value,
            status=delivery_res.status.value,
            is_read=True,
            is_dismissed=False,
            dedup_key=dedup_key,
            metadata_json={},
        )

        notif.status = delivery_res.status.value
        notif.metadata_json = {
            "recipient": recipient,
            "period": period,
            "period_key": key_str,
            "matches_count": len(matches),
            "job_ids": [j.id for j, _ in matches],
            "provider": settings.EMAIL_PROVIDER,
            "delivery_status": delivery_res.status.value,
            "status_detail": delivery_res.status_detail,
            "is_simulated": delivery_res.is_simulated,
            "attempts": delivery_res.attempts,
            "attempt_count": len(delivery_res.attempts),
            "error": delivery_res.error,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

        session.add(notif)
        await session.commit()
        await session.refresh(notif)
        return notif

    @classmethod
    async def send_test_email(cls, recipient: str) -> Tuple[bool, str, NotificationStatus]:
        """Safe test-delivery workflow that does not contact real employers."""
        subject = "JobPilot AI: Test Alert Verification"
        body = (
            "This is a verification email from your local JobPilot AI instance.\n\n"
            "Email notification delivery is functioning properly.\n"
            "Real employer job application submissions remain disabled (JOBPILOT_REAL_SUBMISSION_ENABLED=False).\n\n"
            "— JobPilot AI"
        )
        res = await cls.send_email(to_email=recipient, subject=subject, body_text=body)
        if res.success:
            return True, f"Test alert successfully processed: {res.status_detail} via {settings.EMAIL_PROVIDER}.", res.status
        return False, f"Test email delivery failed: {res.error}", res.status
