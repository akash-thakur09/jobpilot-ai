import re
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set, List, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.application import Application, ApplicationEvent
from backend.app.models.enums import ApplicationStatus
from backend.app.core.logging import logger


# ===========================================================================
# Domain Exceptions
# ===========================================================================
class WorkflowError(Exception):
    """Base exception for application workflow errors."""
    pass


class ApplicationNotFoundError(WorkflowError):
    """Raised when the specified application ID cannot be found."""
    pass


class InvalidStateTransitionError(WorkflowError):
    """Raised when an invalid status transition is requested."""
    def __init__(self, from_status: str, to_status: str, reason: Optional[str] = None):
        self.from_status = from_status
        self.to_status = to_status
        self.reason = reason
        msg = f"Invalid application state transition from '{from_status}' to '{to_status}'."
        if reason:
            msg += f" Reason: {reason}"
        super().__init__(msg)


class MissingSubmissionEvidenceError(WorkflowError):
    """Raised when transitioning to SUBMITTED without verified confirmation evidence."""
    pass


class InvalidApprovalFingerprintError(WorkflowError):
    """Raised when transitioning to APPROVED without a valid approval fingerprint."""
    pass


# ===========================================================================
# Event Sanitizer (Defensive Redaction)
# ===========================================================================
class EventSanitizer:
    """
    Sanitizes event metadata before database insertion to prevent leaking
    passwords, tokens, cookies, auth headers, or sensitive user data.
    """
    SECRET_KEY_PATTERNS = {
        "password",
        "passwd",
        "secret",
        "token",
        "auth",
        "authorization",
        "cookie",
        "session",
        "credential",
        "credentials",
        "api_key",
        "apikey",
        "private_key",
        "access_token",
        "refresh_token",
        "bearer",
        "ssn",
        "credit_card",
        "card_number",
        "cvv",
    }

    MAX_PAYLOAD_BYTES = 32768  # 32 KB safety cap
    MAX_STRING_LENGTH = 1000

    @classmethod
    def is_secret_key(cls, key: str) -> bool:
        lower_key = str(key).strip().lower()
        clean_key = re.sub(r"[_\-\s]+", "", lower_key)
        # Direct exact match or clean match against known keys
        if clean_key in cls.SECRET_KEY_PATTERNS:
            return True
        # Check tokenized parts
        tokens = set(re.split(r"[_\-\s\.]+", lower_key))
        if any(tok in cls.SECRET_KEY_PATTERNS for tok in tokens):
            return True
        # Check substrings for specific high-risk secret prefixes/stems
        for high_risk in ("password", "passwd", "secret", "apikey", "privatekey", "bearer"):
            if high_risk in clean_key:
                return True
        return False

    @classmethod
    def sanitize(cls, data: Any, max_depth: int = 10) -> Any:
        """Recursively sanitizes values, redacting known secret keys and normalizing types."""
        if max_depth <= 0:
            return "[REDACTED_MAX_DEPTH]"

        if data is None or isinstance(data, (int, float, bool)):
            return data

        if isinstance(data, str):
            # Check if string looks like an embedded secret or bearer token
            if re.search(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", data, re.IGNORECASE):
                return "[REDACTED_BEARER_TOKEN]"
            if len(data) > cls.MAX_STRING_LENGTH:
                return data[: cls.MAX_STRING_LENGTH] + "... [TRUNCATED]"
            return data

        if isinstance(data, datetime):
            if data.tzinfo is None:
                data = data.replace(tzinfo=timezone.utc)
            return data.astimezone(timezone.utc).isoformat()

        if isinstance(data, dict):
            sanitized_dict: Dict[str, Any] = {}
            for k, v in data.items():
                str_key = str(k)
                if isinstance(v, dict):
                    sanitized_dict[str_key] = cls.sanitize(v, max_depth - 1)
                elif isinstance(v, (list, tuple, set)):
                    if cls.is_secret_key(str_key):
                        sanitized_list = []
                        for item in v:
                            if isinstance(item, dict):
                                sanitized_list.append(cls.sanitize(item, max_depth - 1))
                            else:
                                sanitized_list.append("[REDACTED]")
                        sanitized_dict[str_key] = sanitized_list
                    else:
                        sanitized_dict[str_key] = cls.sanitize(v, max_depth - 1)
                elif isinstance(v, str) and re.search(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", v, re.IGNORECASE):
                    sanitized_dict[str_key] = "[REDACTED_BEARER_TOKEN]"
                elif cls.is_secret_key(str_key):
                    sanitized_dict[str_key] = "[REDACTED]"
                else:
                    sanitized_dict[str_key] = cls.sanitize(v, max_depth - 1)

            # Enforce size constraints
            try:
                encoded_bytes = len(json.dumps(sanitized_dict, default=str).encode("utf-8"))
                if encoded_bytes > cls.MAX_PAYLOAD_BYTES:
                    # Truncate values to fit within payload limits
                    trimmed = {}
                    for k, v in sanitized_dict.items():
                        if isinstance(v, str) and len(v) > 100:
                            trimmed[k] = v[:100] + "... [TRUNCATED_OVERSIZED]"
                        else:
                            trimmed[k] = v
                    trimmed["_oversized_payload_truncated"] = True
                    return trimmed
            except Exception:
                pass

            return sanitized_dict

        if isinstance(data, (list, tuple, set)):
            return [cls.sanitize(item, max_depth - 1) for item in data]

        # For arbitrary objects/exceptions, return string representation safely
        try:
            return repr(data)
        except Exception:
            return "[UNREPRESENTABLE_OBJECT]"


# ===========================================================================
# Application State Machine
# ===========================================================================
class ApplicationStateMachine:
    """
    Enforces the strict, validated application lifecycle state graph
    and records transactional, append-only application events.
    """

    # Explicit allowed transition graph
    VALID_TRANSITIONS: Dict[ApplicationStatus, Set[ApplicationStatus]] = {
        ApplicationStatus.PREPARING: {
            ApplicationStatus.READY_FOR_REVIEW,
            ApplicationStatus.NEEDS_HUMAN_ACTION,
            ApplicationStatus.FAILED,
            ApplicationStatus.WITHDRAWN,
        },
        ApplicationStatus.READY_FOR_REVIEW: {
            ApplicationStatus.APPROVED,
            ApplicationStatus.NEEDS_HUMAN_ACTION,
            ApplicationStatus.PREPARING,  # Re-evaluation / resume regeneration
            ApplicationStatus.WITHDRAWN,
        },
        ApplicationStatus.NEEDS_HUMAN_ACTION: {
            ApplicationStatus.READY_FOR_REVIEW,
            ApplicationStatus.PREPARING,
            ApplicationStatus.WITHDRAWN,
            ApplicationStatus.FAILED,
        },
        ApplicationStatus.APPROVED: {
            ApplicationStatus.IN_PROGRESS,
            ApplicationStatus.READY_FOR_REVIEW,  # Revoked / invalidated approval
            ApplicationStatus.WITHDRAWN,
        },
        ApplicationStatus.IN_PROGRESS: {
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.OUTCOME_UNKNOWN,
            ApplicationStatus.NEEDS_HUMAN_ACTION,  # Bot challenge / CAPTCHA / unknown field
            ApplicationStatus.FAILED,
        },
        ApplicationStatus.OUTCOME_UNKNOWN: {
            ApplicationStatus.SUBMITTED,  # Reconciled with verified proof
            ApplicationStatus.READY_FOR_REVIEW,  # Reconciled confirming no submission occurred
            ApplicationStatus.NEEDS_HUMAN_ACTION,
            ApplicationStatus.FAILED,
            # Note: Cannot transition directly to IN_PROGRESS (no blind resubmissions)
        },
        ApplicationStatus.SUBMITTED: {
            ApplicationStatus.SHORTLISTED,
            ApplicationStatus.INTERVIEW_SCHEDULED,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
        },
        ApplicationStatus.SHORTLISTED: {
            ApplicationStatus.INTERVIEW_SCHEDULED,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
        },
        ApplicationStatus.INTERVIEW_SCHEDULED: {
            ApplicationStatus.SHORTLISTED,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
        },
        ApplicationStatus.REJECTED: {
            ApplicationStatus.WITHDRAWN,
        },
        ApplicationStatus.WITHDRAWN: set(),  # Terminal state
        ApplicationStatus.FAILED: {
            ApplicationStatus.PREPARING,
            ApplicationStatus.READY_FOR_REVIEW,
            ApplicationStatus.WITHDRAWN,
        },
        # Legacy status backward-compatibility mappings
        ApplicationStatus.DISCOVERED: {
            ApplicationStatus.PREPARING,
            ApplicationStatus.READY_FOR_REVIEW,
            ApplicationStatus.WITHDRAWN,
        },
        ApplicationStatus.SCORED: {
            ApplicationStatus.PREPARING,
            ApplicationStatus.READY_FOR_REVIEW,
            ApplicationStatus.WITHDRAWN,
        },
        ApplicationStatus.RESUME_GENERATED: {
            ApplicationStatus.READY_FOR_REVIEW,
            ApplicationStatus.WITHDRAWN,
        },
        ApplicationStatus.SUBMISSION_PENDING: {
            ApplicationStatus.IN_PROGRESS,
            ApplicationStatus.READY_FOR_REVIEW,
            ApplicationStatus.WITHDRAWN,
        },
    }

    @classmethod
    def normalize_status(cls, status_val: Union[ApplicationStatus, str]) -> ApplicationStatus:
        """Normalizes a string or enum to an ApplicationStatus enum member."""
        if isinstance(status_val, ApplicationStatus):
            return status_val
        try:
            return ApplicationStatus(str(status_val).upper())
        except ValueError:
            # Check if legacy or case-mismatched
            clean_str = str(status_val).strip().upper()
            for s in ApplicationStatus:
                if s.value == clean_str:
                    return s
            raise InvalidStateTransitionError(
                from_status=str(status_val),
                to_status="UNKNOWN",
                reason=f"'{status_val}' is not a recognized ApplicationStatus."
            )

    @classmethod
    def can_transition(
        cls,
        from_status: Union[ApplicationStatus, str],
        to_status: Union[ApplicationStatus, str],
    ) -> bool:
        """Returns True if the transition is defined in the state graph."""
        try:
            norm_from = cls.normalize_status(from_status)
            norm_to = cls.normalize_status(to_status)
        except InvalidStateTransitionError:
            return False

        allowed_targets = cls.VALID_TRANSITIONS.get(norm_from, set())
        return norm_to in allowed_targets

    @classmethod
    def validate_transition_preconditions(
        cls,
        application: Application,
        to_status: ApplicationStatus,
        confirmation_reference: Optional[str] = None,
        confirmation_evidence: Optional[Dict[str, Any]] = None,
        approval_fingerprint: Optional[str] = None,
        reconciliation_evidence: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Validates domain-level safety preconditions for state transitions:
        - Transition to SUBMITTED requires verified confirmation evidence.
        - Transition from OUTCOME_UNKNOWN to SUBMITTED requires verified proof.
        - Transition from OUTCOME_UNKNOWN to READY_FOR_REVIEW requires proof that no submission occurred.
        - Transition to APPROVED requires a valid approval fingerprint.
        - Transition from OUTCOME_UNKNOWN directly to IN_PROGRESS is strictly forbidden.
        """
        current_status = cls.normalize_status(application.status)

        # 1. Submission Gate: SUBMITTED requires reliable external proof
        if to_status == ApplicationStatus.SUBMITTED:
            has_ref = bool(confirmation_reference and confirmation_reference.strip())
            has_evidence = bool(
                confirmation_evidence
                and (
                    confirmation_evidence.get("status") in ("confirmed", "SUBMITTED", "verified")
                    or confirmation_evidence.get("receipt")
                    or confirmation_evidence.get("confirmation_number")
                )
            )
            if not (has_ref or has_evidence):
                raise MissingSubmissionEvidenceError(
                    "Cannot transition application to SUBMITTED without verified confirmation evidence "
                    "(e.g., confirmation_reference or validated confirmation_evidence payload)."
                )

        # 2. Outcome Unknown Reconciliation Gate
        if current_status == ApplicationStatus.OUTCOME_UNKNOWN:
            if to_status == ApplicationStatus.IN_PROGRESS:
                raise InvalidStateTransitionError(
                    from_status=current_status.value,
                    to_status=to_status.value,
                    reason="Blind resubmission from OUTCOME_UNKNOWN is forbidden. "
                    "Must reconcile outcome first."
                )

            if to_status == ApplicationStatus.READY_FOR_REVIEW:
                # Requires reconciliation evidence confirming that no submission was executed
                no_sub = bool(
                    reconciliation_evidence
                    and (
                        reconciliation_evidence.get("submission_occurred") is False
                        or reconciliation_evidence.get("verified_no_submission") is True
                        or reconciliation_evidence.get("action") == "RESET_AFTER_CONFIRMED_NON_SUBMISSION"
                    )
                )
                if not no_sub:
                    raise InvalidStateTransitionError(
                        from_status=current_status.value,
                        to_status=to_status.value,
                        reason="Reconciliation to READY_FOR_REVIEW requires explicit evidence confirming "
                        "that no submission was executed by the portal or employer."
                    )

        # 3. Approval Gate: APPROVED requires a cryptographic approval fingerprint
        if to_status == ApplicationStatus.APPROVED:
            fingerprint = approval_fingerprint or application.approval_fingerprint
            if not fingerprint or len(fingerprint.strip()) < 32:
                raise InvalidApprovalFingerprintError(
                    "Cannot transition application to APPROVED without a valid cryptographic approval fingerprint."
                )

    @classmethod
    async def transition(
        cls,
        session: AsyncSession,
        application_id: str,
        to_status: Union[ApplicationStatus, str],
        actor: str = "SYSTEM",
        event_type: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        confirmation_reference: Optional[str] = None,
        confirmation_evidence: Optional[Dict[str, Any]] = None,
        approval_fingerprint: Optional[str] = None,
        approval_metadata: Optional[Dict[str, Any]] = None,
        reconciliation_evidence: Optional[Dict[str, Any]] = None,
        auto_commit: bool = True,
    ) -> Application:
        """
        Executes an atomic status transition and appends an ApplicationEvent record
        within the same database transaction.
        """
        # 1. Load Application
        query = select(Application).where(Application.id == application_id)
        if session.bind and session.bind.dialect.name == "postgresql":
            query = query.with_for_update()

        result = await session.execute(query)
        application = result.scalar_one_or_none()
        if not application:
            raise ApplicationNotFoundError(f"Application with ID '{application_id}' does not exist.")

        # 2. Validate Transition
        from_status = cls.normalize_status(application.status)
        target_status = cls.normalize_status(to_status)

        if not cls.can_transition(from_status, target_status):
            raise InvalidStateTransitionError(
                from_status=from_status.value,
                to_status=target_status.value,
                reason=f"Transition from {from_status.value} to {target_status.value} is not permitted by the state graph."
            )

        # 3. Validate Preconditions
        cls.validate_transition_preconditions(
            application=application,
            to_status=target_status,
            confirmation_reference=confirmation_reference,
            confirmation_evidence=confirmation_evidence,
            approval_fingerprint=approval_fingerprint,
            reconciliation_evidence=reconciliation_evidence,
        )

        # 4. Apply State Changes
        application.status = target_status.value
        now_utc = datetime.now(timezone.utc)

        if target_status == ApplicationStatus.SUBMITTED:
            application.submitted_at = now_utc
            if confirmation_reference:
                application.notes = f"{application.notes or ''} [Confirmation: {confirmation_reference}]".strip()
            if confirmation_evidence:
                application.confirmation_evidence = EventSanitizer.sanitize(confirmation_evidence)

        if target_status == ApplicationStatus.APPROVED:
            if approval_fingerprint:
                application.approval_fingerprint = approval_fingerprint
            application.approved_at = now_utc
            if approval_metadata:
                application.approval_metadata = EventSanitizer.sanitize(approval_metadata)

        # 5. Build and Sanitize Event Payload
        event_payload = payload.copy() if payload else {}
        if confirmation_reference:
            event_payload["confirmation_reference"] = confirmation_reference
        if reconciliation_evidence:
            event_payload["reconciliation"] = reconciliation_evidence
        sanitized_payload = EventSanitizer.sanitize(event_payload)

        # 6. Append Immutable Event
        event = ApplicationEvent(
            application_id=application.id,
            from_status=from_status.value,
            to_status=target_status.value,
            actor=actor,
            payload=sanitized_payload,
            created_at=now_utc,
        )
        session.add(event)

        # 7. Commit if requested
        if auto_commit:
            await session.commit()
            await session.refresh(application)

        logger.info(
            f"Application '{application.id}' transitioned from '{from_status.value}' "
            f"to '{target_status.value}' by actor '{actor}'."
        )
        return application

    @classmethod
    async def record_event(
        cls,
        session: AsyncSession,
        application_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        actor: str = "SYSTEM",
        auto_commit: bool = True,
    ) -> ApplicationEvent:
        """
        Appends an application event without changing the application's status
        (e.g., FORM_INSPECTED, FIELD_FILLED, ATTEMPT_STARTED).
        """
        query = select(Application).where(Application.id == application_id)
        result = await session.execute(query)
        application = result.scalar_one_or_none()
        if not application:
            raise ApplicationNotFoundError(f"Application with ID '{application_id}' does not exist.")

        now_utc = datetime.now(timezone.utc)
        sanitized_payload = EventSanitizer.sanitize(payload or {})
        sanitized_payload["_event_type"] = event_type

        event = ApplicationEvent(
            application_id=application.id,
            from_status=application.status,
            to_status=application.status,
            actor=actor,
            payload=sanitized_payload,
            created_at=now_utc,
        )
        session.add(event)

        if auto_commit:
            await session.commit()
            await session.refresh(event)

        return event
