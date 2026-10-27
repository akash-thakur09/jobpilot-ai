"""
JobPilot AI - Application Workflow API Router
Exposes application preparation, review, cryptographic approval, synthetic browser execution attempts,
immutable event/attempt history, and outcome reconciliation.

SECURITY & ARCHITECTURAL NOTICE:
- Real job-board submissions are disabled (JOBPILOT_REAL_SUBMISSION_ENABLED=false).
- Target execution is strictly restricted to local synthetic test harnesses (127.0.0.1 / localhost).
- This API is designed for local-first single-user operation; candidate IDs represent profile contexts,
  not multi-tenant authentication boundaries.
"""

from typing import List, Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.session import get_db
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.models.application import Application, ApplicationEvent, SubmissionAttempt
from backend.app.models.job import Job
from backend.app.models.enums import ApplicationStatus
from backend.app.schemas.application import (
    ApplicationPrepareRequest,
    ApplicationRead,
    ApplicationListResponse,
    ApplicationEventRead,
    ApplicationEventListResponse,
    SubmissionAttemptRead,
    SubmissionAttemptListResponse,
    ApplicationAttemptRequest,
    ApplicationReconcileRequest,
)
from backend.app.workflow.schemas import (
    ApplicationReviewPayload,
    ApplicationApproveRequest,
)
from backend.app.services.application_workflow_service import ApplicationWorkflowService
from backend.app.automation.browser_runner import BrowserAutomationRunner
from backend.app.workflow.state_machine import ApplicationStateMachine, EventSanitizer
from backend.app.workflow.exceptions import (
    WorkflowError,
    ApplicationNotFoundError,
    ApplicationNotReviewableError,
    ApprovalFingerprintMismatchError,
    CandidateNotFoundError,
    AmbiguousCandidateError,
    CandidateProfileIncompleteError,
    JobNotFoundError,
    JobDisqualifiedError,
    EligibilityNeedsReviewError,
    ResumeIntegrityError,
    DuplicateApplicationConflictError,
    InvalidStateTransitionError,
    MissingSubmissionEvidenceError,
    StaleApprovalError,
)

router = APIRouter(prefix="/applications", tags=["Applications Workflow"])


def _to_application_read(app: Application) -> ApplicationRead:
    """Helper to convert Application ORM model to sanitized ApplicationRead schema."""
    return ApplicationRead(
        id=app.id,
        candidate_id=app.candidate_id,
        job_id=app.job_id,
        resume_version_id=app.resume_version_id,
        selected_resume_sha256=app.selected_resume_sha256,
        status=app.status,
        submission_method=app.submission_method,
        submitted_at=app.submitted_at,
        confirmation_evidence=EventSanitizer.sanitize(app.confirmation_evidence or {}),
        approval_fingerprint=app.approval_fingerprint,
        approved_at=app.approved_at,
        approval_metadata=EventSanitizer.sanitize(app.approval_metadata or {}),
        job_title=app.job.title if app.job else None,
        company=app.job.company if app.job else None,
        notes=app.notes,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


@router.post("/prepare", response_model=ApplicationReviewPayload, status_code=status.HTTP_201_CREATED)
async def prepare_application(
    request: ApplicationPrepareRequest, session: AsyncSession = Depends(get_db)
):
    """
    Prepares an application for human review:
    Evaluates eligibility, ensures a tailored ATS resume PDF exists, performs factual verification,
    computes canonical approval fingerprint, and returns the complete review payload.
    """
    try:
        return await ApplicationWorkflowService.prepare_application(
            session=session,
            job_id=request.job_id,
            candidate_id=request.candidate_id,
            force_regenerate_resume=request.force_regenerate_resume,
            actor="API_USER",
        )
    except JobNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CandidateNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CandidateProfileIncompleteError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except AmbiguousCandidateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except JobDisqualifiedError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DuplicateApplicationConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ResumeIntegrityError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error preparing application: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Application preparation failed.")


@router.get("", response_model=ApplicationListResponse)
async def list_applications(
    status_filter: Optional[str] = Query(None, alias="status"),
    candidate_id: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """
    Lists applications with pagination and optional filtering by status or candidate.
    """
    query = select(Application).options(selectinload(Application.job))
    count_query = select(func.count(Application.id))

    if status_filter:
        query = query.where(Application.status == status_filter.upper())
        count_query = count_query.where(Application.status == status_filter.upper())

    if candidate_id:
        query = query.where(Application.candidate_id == candidate_id)
        count_query = count_query.where(Application.candidate_id == candidate_id)

    total_res = await session.execute(count_query)
    total = total_res.scalar_one()

    query = query.order_by(Application.created_at.desc()).offset(offset).limit(limit)
    res = await session.execute(query)
    apps = res.scalars().all()

    return ApplicationListResponse(
        items=[_to_application_read(a) for a in apps],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{application_id}", response_model=ApplicationRead)
async def get_application(application_id: str, session: AsyncSession = Depends(get_db)):
    """Retrieves an application by ID."""
    res = await session.execute(
        select(Application).options(selectinload(Application.job)).where(Application.id == application_id)
    )
    app = res.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application '{application_id}' not found.")
    return _to_application_read(app)


@router.get("/{application_id}/review", response_model=ApplicationReviewPayload)
async def review_application(application_id: str, session: AsyncSession = Depends(get_db)):
    """
    Retrieves the complete server-generated review payload for an application,
    including candidate facts, job summary, tailored resume integrity, and canonical approval fingerprint.
    """
    try:
        return await ApplicationWorkflowService.review_application(session, application_id)
    except ApplicationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ResumeIntegrityError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{application_id}/approve", response_model=ApplicationRead)
async def approve_application(
    application_id: str,
    request: ApplicationApproveRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Approves an application for submission.
    Cryptographically verifies that the user-reviewed fingerprint exactly matches the server-computed fingerprint.
    """
    try:
        await ApplicationWorkflowService.approve_application(
            session=session,
            application_id=application_id,
            reviewed_fingerprint=request.reviewed_fingerprint,
            approval_metadata=request.approval_metadata,
            actor="CANDIDATE",
        )
        res = await session.execute(
            select(Application).options(selectinload(Application.job)).where(Application.id == application_id)
        )
        approved_app = res.scalar_one()
        return _to_application_read(approved_app)
    except ApplicationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ApplicationNotReviewableError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ApprovalFingerprintMismatchError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except JobDisqualifiedError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ResumeIntegrityError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{application_id}/attempt", response_model=SubmissionAttemptRead, status_code=status.HTTP_200_OK)
async def execute_submission_attempt(
    application_id: str,
    request: ApplicationAttemptRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Executes a synthetic submission attempt using Playwright browser automation.
    Requires the application to be in APPROVED state with fresh fingerprint and valid resume artifact.
    Rejects external URLs (JOBPILOT_REAL_SUBMISSION_ENABLED=false).
    """
    # 1. Origin validation
    if request.target_url:
        try:
            parsed = urlparse(request.target_url)
            if parsed.hostname not in {"127.0.0.1", "localhost"} and not settings.JOBPILOT_REAL_SUBMISSION_ENABLED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Real external submissions are disabled (JOBPILOT_REAL_SUBMISSION_ENABLED=False). Target URL must be local.",
                )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target URL.")

    # 2. Check application existence
    app_res = await session.execute(
        select(Application).where(Application.id == application_id)
    )
    application = app_res.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application '{application_id}' not found.")

    if application.status != ApplicationStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot execute automation: Application status is '{application.status}', must be 'APPROVED'.",
        )

    # 3. Execute automation runner
    try:
        attempt = await BrowserAutomationRunner.execute_application_automation(
            session=session,
            application_id=application_id,
            target_url=request.target_url,
            actor="AUTOMATION_RUNNER",
        )
        return SubmissionAttemptRead.model_validate(attempt)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.exception(f"Error during browser automation execution: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Browser automation failed.")


@router.get("/{application_id}/events", response_model=ApplicationEventListResponse)
async def list_application_events(
    application_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """
    Returns sanitized, append-only lifecycle event history for an application.
    """
    # Verify application exists
    app_res = await session.execute(select(Application.id).where(Application.id == application_id))
    if not app_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application '{application_id}' not found.")

    count_query = select(func.count(ApplicationEvent.id)).where(ApplicationEvent.application_id == application_id)
    total_res = await session.execute(count_query)
    total = total_res.scalar_one()

    query = (
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == application_id)
        .order_by(ApplicationEvent.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    res = await session.execute(query)
    events = res.scalars().all()

    # Redact / sanitize payloads
    sanitized_items = [
        ApplicationEventRead(
            id=ev.id,
            application_id=ev.application_id,
            from_status=ev.from_status,
            to_status=ev.to_status,
            actor=ev.actor,
            payload=EventSanitizer.sanitize(ev.payload or {}),
            created_at=ev.created_at,
        )
        for ev in events
    ]

    return ApplicationEventListResponse(
        items=sanitized_items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{application_id}/attempts", response_model=SubmissionAttemptListResponse)
async def list_submission_attempts(
    application_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """
    Returns execution history of all browser submission attempts for an application.
    """
    app_res = await session.execute(select(Application.id).where(Application.id == application_id))
    if not app_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application '{application_id}' not found.")

    count_query = select(func.count(SubmissionAttempt.id)).where(SubmissionAttempt.application_id == application_id)
    total_res = await session.execute(count_query)
    total = total_res.scalar_one()

    query = (
        select(SubmissionAttempt)
        .where(SubmissionAttempt.application_id == application_id)
        .order_by(SubmissionAttempt.attempt_number.asc())
        .offset(offset)
        .limit(limit)
    )
    res = await session.execute(query)
    attempts = res.scalars().all()

    sanitized_items = [
        SubmissionAttemptRead(
            id=att.id,
            application_id=att.application_id,
            attempt_number=att.attempt_number,
            adapter_identifier=att.adapter_identifier,
            selected_resume_version_id=att.selected_resume_version_id,
            uploaded_artifact_sha256=att.uploaded_artifact_sha256,
            outcome=att.outcome,
            started_at=att.started_at,
            completed_at=att.completed_at,
            confirmation_reference=att.confirmation_reference,
            confirmation_payload=EventSanitizer.sanitize(att.confirmation_payload or {}),
            sanitized_diagnostics=EventSanitizer.sanitize(att.sanitized_diagnostics or {}),
            reconciliation_metadata=EventSanitizer.sanitize(att.reconciliation_metadata or {}),
        )
        for att in attempts
    ]

    return SubmissionAttemptListResponse(
        items=sanitized_items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{application_id}/reconcile", response_model=ApplicationRead)
async def reconcile_application(
    application_id: str,
    request: ApplicationReconcileRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Reconciles an uncertain or blocked application (e.g. from OUTCOME_UNKNOWN).
    Requires explicit reconciliation evidence and enforces state machine transition guards.
    """
    app_res = await session.execute(
        select(Application).options(selectinload(Application.job)).where(Application.id == application_id)
    )
    application = app_res.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application '{application_id}' not found.")

    try:
        target_enum = ApplicationStatus(request.target_status.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target status '{request.target_status}'.",
        )

    try:
        if request.notes:
            application.notes = request.notes

        updated_app = await ApplicationStateMachine.transition(
            session=session,
            application_id=application_id,
            to_status=target_enum,
            actor="RECONCILIATION_AUDITOR",
            event_type="APPLICATION_RECONCILED",
            reconciliation_evidence=request.reconciliation_evidence,
            payload={
                "target_status": target_enum.value,
                "evidence": EventSanitizer.sanitize(request.reconciliation_evidence),
            },
        )
        return _to_application_read(updated_app)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except MissingSubmissionEvidenceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkflowError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
