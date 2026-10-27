import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.candidate import CandidateProfile
from backend.app.models.job import Job, JobSource
from backend.app.models.resume import ResumeVersion
from backend.app.models.application import Application, ApplicationEvent
from backend.app.models.enums import ApplicationStatus
from backend.app.workflow.state_machine import (
    ApplicationStateMachine,
    EventSanitizer,
    InvalidStateTransitionError,
    MissingSubmissionEvidenceError,
    InvalidApprovalFingerprintError,
    ApplicationNotFoundError,
)


import uuid


# ===========================================================================
# Fixture Helper
# ===========================================================================
async def create_app_fixture(
    db_session: AsyncSession,
    status: ApplicationStatus = ApplicationStatus.PREPARING,
    approval_fingerprint: str = None,
) -> Application:
    uid = uuid.uuid4().hex[:8]
    candidate = CandidateProfile(
        full_name=f"John Connor {uid}",
        email=f"john_{uid}@example.com",
        location="Omaha, NE",
        work_authorization="US Citizen",
        summary="Security Specialist",
    )
    source = JobSource(identifier=f"test_src_sm_{uid}", name=f"Test Source {uid}", base_url="https://example.com")
    db_session.add_all([candidate, source])
    await db_session.flush()

    job = Job(
        source_id=source.id,
        external_id=f"job_sm_{uid}",
        title="Security Analyst",
        company="Defense Core",
        canonical_url=f"https://example.com/jobs/{uid}",
        description="Cybersecurity role.",
    )
    db_session.add(job)
    await db_session.flush()

    resume = ResumeVersion(
        candidate_id=candidate.id,
        job_id=job.id,
        structured_content={"summary": "Security Analyst resume"},
        candidate_snapshot={"full_name": candidate.full_name},
        pdf_file_path=f"storage/resumes/sec_{uid}.pdf",
        file_sha256="2" * 64,
        is_ats_valid=True,
    )
    db_session.add(resume)
    await db_session.flush()

    app = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        resume_version_id=resume.id,
        selected_resume_sha256=resume.file_sha256,
        status=status.value,
        approval_fingerprint=approval_fingerprint,
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)
    return app


# ===========================================================================
# 1. Permitted Transitions Across Documented Graph
# ===========================================================================
@pytest.mark.asyncio
async def test_permitted_transitions_full_lifecycle(db_session: AsyncSession):
    app = await create_app_fixture(db_session, status=ApplicationStatus.PREPARING)
    valid_fingerprint = "a" * 64

    # PREPARING -> READY_FOR_REVIEW
    app = await ApplicationStateMachine.transition(
        db_session, app.id, ApplicationStatus.READY_FOR_REVIEW, actor="PREPARATION_SERVICE"
    )
    assert app.status == ApplicationStatus.READY_FOR_REVIEW.value

    # READY_FOR_REVIEW -> APPROVED (with valid fingerprint)
    app = await ApplicationStateMachine.transition(
        db_session,
        app.id,
        ApplicationStatus.APPROVED,
        actor="CANDIDATE",
        approval_fingerprint=valid_fingerprint,
        approval_metadata={"policy_version": "1.0.0"},
    )
    assert app.status == ApplicationStatus.APPROVED.value
    assert app.approval_fingerprint == valid_fingerprint
    assert app.approved_at is not None

    # APPROVED -> IN_PROGRESS
    app = await ApplicationStateMachine.transition(
        db_session, app.id, ApplicationStatus.IN_PROGRESS, actor="PLAYWRIGHT_ADAPTER"
    )
    assert app.status == ApplicationStatus.IN_PROGRESS.value

    # IN_PROGRESS -> SUBMITTED (with verified evidence)
    app = await ApplicationStateMachine.transition(
        db_session,
        app.id,
        ApplicationStatus.SUBMITTED,
        actor="PLAYWRIGHT_ADAPTER",
        confirmation_reference="RECEIPT-9988",
        confirmation_evidence={"status": "confirmed", "receipt": "RECEIPT-9988"},
    )
    assert app.status == ApplicationStatus.SUBMITTED.value
    assert app.submitted_at is not None
    assert "RECEIPT-9988" in app.notes

    # SUBMITTED -> SHORTLISTED
    app = await ApplicationStateMachine.transition(
        db_session, app.id, ApplicationStatus.SHORTLISTED, actor="USER"
    )
    assert app.status == ApplicationStatus.SHORTLISTED.value

    # SHORTLISTED -> INTERVIEW_SCHEDULED
    app = await ApplicationStateMachine.transition(
        db_session, app.id, ApplicationStatus.INTERVIEW_SCHEDULED, actor="USER"
    )
    assert app.status == ApplicationStatus.INTERVIEW_SCHEDULED.value

    # INTERVIEW_SCHEDULED -> REJECTED
    app = await ApplicationStateMachine.transition(
        db_session, app.id, ApplicationStatus.REJECTED, actor="USER"
    )
    assert app.status == ApplicationStatus.REJECTED.value

    # REJECTED -> WITHDRAWN
    app = await ApplicationStateMachine.transition(
        db_session, app.id, ApplicationStatus.WITHDRAWN, actor="USER"
    )
    assert app.status == ApplicationStatus.WITHDRAWN.value


# ===========================================================================
# 2. Representative Invalid Transitions
# ===========================================================================
@pytest.mark.asyncio
async def test_representative_invalid_transitions(db_session: AsyncSession):
    app = await create_app_fixture(db_session, status=ApplicationStatus.PREPARING)

    # Cannot skip review and approval: PREPARING -> SUBMITTED is forbidden
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        await ApplicationStateMachine.transition(
            db_session,
            app.id,
            ApplicationStatus.SUBMITTED,
            confirmation_reference="FAKE-REF",
        )
    assert "Invalid application state transition" in str(exc_info.value)

    # Cannot jump to IN_PROGRESS without approval
    with pytest.raises(InvalidStateTransitionError):
        await ApplicationStateMachine.transition(db_session, app.id, ApplicationStatus.IN_PROGRESS)

    # Transition to terminal state WITHDRAWN
    app = await ApplicationStateMachine.transition(db_session, app.id, ApplicationStatus.WITHDRAWN)
    assert app.status == ApplicationStatus.WITHDRAWN.value

    # Cannot transition out of terminal WITHDRAWN state
    with pytest.raises(InvalidStateTransitionError):
        await ApplicationStateMachine.transition(db_session, app.id, ApplicationStatus.APPROVED)


# ===========================================================================
# 3. Invalid Current Status Handling
# ===========================================================================
def test_invalid_current_status_handling():
    assert ApplicationStateMachine.can_transition("NON_EXISTENT_STATUS", ApplicationStatus.APPROVED) is False
    with pytest.raises(InvalidStateTransitionError):
        ApplicationStateMachine.normalize_status("GARBAGE_STATUS_XYZ")


# ===========================================================================
# 4. Submission Blocked Without Verified Evidence
# ===========================================================================
@pytest.mark.asyncio
async def test_submission_blocked_without_verified_evidence(db_session: AsyncSession):
    app = await create_app_fixture(db_session, status=ApplicationStatus.IN_PROGRESS)

    # Attempt transition without confirmation reference or evidence
    with pytest.raises(MissingSubmissionEvidenceError):
        await ApplicationStateMachine.transition(
            db_session, app.id, ApplicationStatus.SUBMITTED
        )

    # Attempt with empty/whitespace confirmation reference
    with pytest.raises(MissingSubmissionEvidenceError):
        await ApplicationStateMachine.transition(
            db_session, app.id, ApplicationStatus.SUBMITTED, confirmation_reference="   "
        )


# ===========================================================================
# 5. Unknown Outcome Cannot Be Blindly Resubmitted
# ===========================================================================
@pytest.mark.asyncio
async def test_outcome_unknown_cannot_blindly_resubmit(db_session: AsyncSession):
    app = await create_app_fixture(db_session, status=ApplicationStatus.OUTCOME_UNKNOWN)

    # Must NOT be permitted to transition directly into IN_PROGRESS
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        await ApplicationStateMachine.transition(db_session, app.id, ApplicationStatus.IN_PROGRESS)
    assert "OUTCOME_UNKNOWN" in str(exc_info.value)
    assert "IN_PROGRESS" in str(exc_info.value)


# ===========================================================================
# 6. Reconciliation Does Not Falsely Mark Submitted
# ===========================================================================
@pytest.mark.asyncio
async def test_reconciliation_safeguards(db_session: AsyncSession):
    app = await create_app_fixture(db_session, status=ApplicationStatus.OUTCOME_UNKNOWN)

    # Transition to READY_FOR_REVIEW without evidence that NO submission occurred is rejected
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        await ApplicationStateMachine.transition(db_session, app.id, ApplicationStatus.READY_FOR_REVIEW)
    assert "Reconciliation to READY_FOR_REVIEW requires explicit evidence" in str(exc_info.value)

    # Transition to READY_FOR_REVIEW with verified non-submission proof succeeds
    app = await ApplicationStateMachine.transition(
        db_session,
        app.id,
        ApplicationStatus.READY_FOR_REVIEW,
        reconciliation_evidence={"verified_no_submission": True, "method": "manual_employer_portal_check"},
    )
    assert app.status == ApplicationStatus.READY_FOR_REVIEW.value


# ===========================================================================
# 7. Approval Requires Valid Fingerprint
# ===========================================================================
@pytest.mark.asyncio
async def test_approval_requires_fingerprint(db_session: AsyncSession):
    app = await create_app_fixture(db_session, status=ApplicationStatus.READY_FOR_REVIEW)

    # Missing fingerprint
    with pytest.raises(InvalidApprovalFingerprintError):
        await ApplicationStateMachine.transition(
            db_session, app.id, ApplicationStatus.APPROVED, approval_fingerprint=None
        )

    # Short/invalid fingerprint
    with pytest.raises(InvalidApprovalFingerprintError):
        await ApplicationStateMachine.transition(
            db_session, app.id, ApplicationStatus.APPROVED, approval_fingerprint="too_short"
        )


# ===========================================================================
# 8 & 9. Atomic Status Change, Event Insertion, and Rollback
# ===========================================================================
@pytest.mark.asyncio
async def test_atomic_transition_and_rollback(db_session: AsyncSession):
    app = await create_app_fixture(db_session, status=ApplicationStatus.PREPARING)
    app_id = str(app.id)

    # Execute transition with auto_commit=False, then roll back
    await ApplicationStateMachine.transition(
        db_session,
        app_id,
        ApplicationStatus.READY_FOR_REVIEW,
        payload={"note": "tentative transition"},
        auto_commit=False,
    )
    # Rollback session
    await db_session.rollback()

    # Verify neither status change nor event persisted
    reloaded = (await db_session.execute(select(Application).where(Application.id == app_id))).scalar_one()
    assert reloaded.status == ApplicationStatus.PREPARING.value

    events = (
        await db_session.execute(select(ApplicationEvent).where(ApplicationEvent.application_id == app_id))
    ).scalars().all()
    assert len(events) == 0


# ===========================================================================
# 10. Event History is Append-Only and Immutable
# ===========================================================================
@pytest.mark.asyncio
async def test_event_history_append_only(db_session: AsyncSession):
    app = await create_app_fixture(db_session, status=ApplicationStatus.PREPARING)

    # 1. First transition
    await ApplicationStateMachine.transition(db_session, app.id, ApplicationStatus.READY_FOR_REVIEW)
    # 2. Non-transition event
    await ApplicationStateMachine.record_event(
        db_session, app.id, event_type="FORM_INSPECTED", payload={"fields_detected": 5}
    )
    # 3. Second transition
    await ApplicationStateMachine.transition(
        db_session,
        app.id,
        ApplicationStatus.APPROVED,
        approval_fingerprint="f" * 64,
    )

    events_res = await db_session.execute(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == app.id)
        .order_by(ApplicationEvent.created_at.asc())
    )
    events = events_res.scalars().all()

    assert len(events) == 3
    # Check first event
    assert events[0].from_status == ApplicationStatus.PREPARING.value
    assert events[0].to_status == ApplicationStatus.READY_FOR_REVIEW.value
    # Check non-transition event
    assert events[1].from_status == ApplicationStatus.READY_FOR_REVIEW.value
    assert events[1].to_status == ApplicationStatus.READY_FOR_REVIEW.value
    assert events[1].payload["_event_type"] == "FORM_INSPECTED"
    # Check third event
    assert events[2].from_status == ApplicationStatus.READY_FOR_REVIEW.value
    assert events[2].to_status == ApplicationStatus.APPROVED.value


# ===========================================================================
# 11 & 12. Defensive Metadata Sanitization (Secrets Redacted in Nested Dicts/Lists)
# ===========================================================================
def test_event_sanitizer_redacts_secrets():
    raw_payload = {
        "job_title": "Software Engineer",
        "candidate_email": "user@example.com",
        "auth_credentials": {
            "password": "SuperSecretPassword123!",
            "API_KEY": "sk_live_1234567890",
            "access_token": "token_abc_xyz",
        },
        "session_cookies": [
            {"cookie": "session_id=999888"},
            {"name": "theme", "value": "dark"},
        ],
        "headers": {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secretpayload",
        },
    }

    sanitized = EventSanitizer.sanitize(raw_payload)

    # Non-sensitive keys preserved
    assert sanitized["job_title"] == "Software Engineer"
    assert sanitized["candidate_email"] == "user@example.com"
    assert sanitized["session_cookies"][1]["value"] == "dark"

    # Secrets strictly redacted
    assert sanitized["auth_credentials"]["password"] == "[REDACTED]"
    assert sanitized["auth_credentials"]["API_KEY"] == "[REDACTED]"
    assert sanitized["auth_credentials"]["access_token"] == "[REDACTED]"
    assert sanitized["session_cookies"][0]["cookie"] == "[REDACTED]"
    assert sanitized["headers"]["Authorization"] == "[REDACTED_BEARER_TOKEN]"


# ===========================================================================
# 13 & 14. Oversized Metadata & Unsupported Object Types
# ===========================================================================
def test_event_sanitizer_oversized_and_unsupported_types():
    # Long string truncation
    huge_string = "A" * 5000
    sanitized_str = EventSanitizer.sanitize(huge_string)
    assert len(sanitized_str) <= 1020
    assert "[TRUNCATED]" in sanitized_str

    # Unsupported custom object / exception
    class CustomPortalError(Exception):
        pass

    err = CustomPortalError("Connection refused by host")
    sanitized_err = EventSanitizer.sanitize({"error": err})
    assert "CustomPortalError" in sanitized_err["error"]

    # Oversized payload truncation
    large_payload = {f"key_{i}": "X" * 500 for i in range(100)}
    sanitized_large = EventSanitizer.sanitize(large_payload)
    assert sanitized_large.get("_oversized_payload_truncated") is True


# ===========================================================================
# 15. UTC Timestamps Consistency
# ===========================================================================
@pytest.mark.asyncio
async def test_utc_timestamps_consistency(db_session: AsyncSession):
    app = await create_app_fixture(db_session, status=ApplicationStatus.PREPARING)
    app = await ApplicationStateMachine.transition(
        db_session,
        app.id,
        ApplicationStatus.READY_FOR_REVIEW,
        payload={"event_time": datetime.now(timezone.utc)},
    )

    events_res = await db_session.execute(
        select(ApplicationEvent).where(ApplicationEvent.application_id == app.id)
    )
    event = events_res.scalar_one()

    assert event.created_at is not None
    # Ensure event time was normalized to UTC
    iso_time = event.payload["event_time"]
    assert "+00:00" in iso_time or "Z" in iso_time


# ===========================================================================
# 16. Existing Legacy Statuses Compatibility
# ===========================================================================
@pytest.mark.asyncio
async def test_legacy_statuses_compatibility(db_session: AsyncSession):
    # Test DISCOVERED -> PREPARING
    app_disc = await create_app_fixture(db_session, status=ApplicationStatus.DISCOVERED)
    app_disc = await ApplicationStateMachine.transition(
        db_session, app_disc.id, ApplicationStatus.PREPARING
    )
    assert app_disc.status == ApplicationStatus.PREPARING.value

    # Test SCORED -> READY_FOR_REVIEW
    app_scored = await create_app_fixture(db_session, status=ApplicationStatus.SCORED)
    app_scored = await ApplicationStateMachine.transition(
        db_session, app_scored.id, ApplicationStatus.READY_FOR_REVIEW
    )
    assert app_scored.status == ApplicationStatus.READY_FOR_REVIEW.value

    # Test RESUME_GENERATED -> READY_FOR_REVIEW
    app_res = await create_app_fixture(db_session, status=ApplicationStatus.RESUME_GENERATED)
    app_res = await ApplicationStateMachine.transition(
        db_session, app_res.id, ApplicationStatus.READY_FOR_REVIEW
    )
    assert app_res.status == ApplicationStatus.READY_FOR_REVIEW.value


# ===========================================================================
# 17. Human Intervention, Failure, and Reconciliation to Submitted
# ===========================================================================
@pytest.mark.asyncio
async def test_human_action_failure_and_reconciliation_to_submitted(db_session: AsyncSession):
    app = await create_app_fixture(db_session, status=ApplicationStatus.PREPARING)

    # PREPARING -> NEEDS_HUMAN_ACTION (e.g. missing mandatory field)
    app = await ApplicationStateMachine.transition(
        db_session, app.id, ApplicationStatus.NEEDS_HUMAN_ACTION, actor="PREPARATION_SERVICE"
    )
    assert app.status == ApplicationStatus.NEEDS_HUMAN_ACTION.value

    # NEEDS_HUMAN_ACTION -> READY_FOR_REVIEW (user resolved issue)
    app = await ApplicationStateMachine.transition(
        db_session, app.id, ApplicationStatus.READY_FOR_REVIEW, actor="USER"
    )
    assert app.status == ApplicationStatus.READY_FOR_REVIEW.value

    # Approve with fingerprint
    app = await ApplicationStateMachine.transition(
        db_session, app.id, ApplicationStatus.APPROVED, approval_fingerprint="b" * 64
    )
    # IN_PROGRESS
    app = await ApplicationStateMachine.transition(
        db_session, app.id, ApplicationStatus.IN_PROGRESS, actor="PLAYWRIGHT_ADAPTER"
    )

    # IN_PROGRESS -> OUTCOME_UNKNOWN (timeout during submission click)
    app = await ApplicationStateMachine.transition(
        db_session, app.id, ApplicationStatus.OUTCOME_UNKNOWN, actor="PLAYWRIGHT_ADAPTER"
    )
    assert app.status == ApplicationStatus.OUTCOME_UNKNOWN.value

    # OUTCOME_UNKNOWN -> SUBMITTED with verified confirmation proof
    app = await ApplicationStateMachine.transition(
        db_session,
        app.id,
        ApplicationStatus.SUBMITTED,
        actor="RECONCILIATION_SERVICE",
        confirmation_reference="PORTAL-REC-777",
        confirmation_evidence={"status": "confirmed", "receipt": "PORTAL-REC-777"},
    )
    assert app.status == ApplicationStatus.SUBMITTED.value
