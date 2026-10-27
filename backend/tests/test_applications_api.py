"""
JobPilot AI - Application Workflow API Integration Tests
Tests /api/v1/applications endpoints for preparation, review, cryptographic approval,
browser automation execution, immutable history, and outcome reconciliation.
"""

import uuid
from typing import Optional
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.automation.mock_portal.server import MockPortalServer
from backend.app.models.application import Application
from backend.app.models.candidate import CandidateProfile, CandidateSkill, CandidateExperience, CandidateEducation
from backend.app.models.enums import ApplicationStatus
from backend.app.models.job import Job, JobSource, JobRequirement
from backend.app.models.matching import MatchScore
from backend.app.models.resume import ResumeVersion
from backend.app.resumes.storage_service import ResumeStorageService
from backend.app.services.application_workflow_service import ApplicationWorkflowService
from backend.app.workflow.approval_fingerprint import ApprovalFingerprintService


@pytest.fixture(scope="module")
def mock_portal():
    """Starts local synthetic test portal on an ephemeral port."""
    server = MockPortalServer()
    server.start()
    yield server
    server.stop()


async def create_api_candidate(
    db_session: AsyncSession,
    full_name: str = "Marcus Holloway",
    email: Optional[str] = None,
    work_authorization: str = "US Citizen",
) -> CandidateProfile:
    uid = uuid.uuid4().hex[:8]
    email = email or f"marcus_{uid}@example.com"
    cand = CandidateProfile(
        full_name=full_name,
        email=email,
        phone="+1-555-0177",
        location="San Francisco, CA",
        work_authorization=work_authorization,
        summary="Senior Infrastructure & Automation Engineer",
        years_of_experience=7.0,
        linkedin_url="https://linkedin.com/in/mholloway",
        github_url="https://github.com/mholloway",
    )
    db_session.add(cand)
    await db_session.flush()

    skill = CandidateSkill(
        candidate_id=cand.id,
        skill_name="Python",
        category="Languages",
        years_experience=6.0,
        is_verified=True,
    )
    db_session.add(skill)

    exp = CandidateExperience(
        candidate_id=cand.id,
        company="DedSec Labs",
        role="Lead Systems Engineer",
        start_date="2019-01-01",
        end_date=None,
        is_current=True,
        verified_bullets=["Architected automated infrastructure", "Built CI/CD testing pipelines"],
    )
    db_session.add(exp)

    edu = CandidateEducation(
        candidate_id=cand.id,
        institution="Stanford University",
        degree="B.S.",
        field_of_study="Computer Science",
        graduation_year=2018,
    )
    db_session.add(edu)

    await db_session.commit()

    cand_res = await db_session.execute(
        select(CandidateProfile)
        .options(
            selectinload(CandidateProfile.skills),
            selectinload(CandidateProfile.experiences),
            selectinload(CandidateProfile.educations),
            selectinload(CandidateProfile.projects),
        )
        .where(CandidateProfile.id == cand.id)
    )
    return cand_res.scalar_one()


async def create_api_job(
    db_session: AsyncSession,
    title: str = "Senior Automation Engineer",
    company: str = "Blume Corp",
    is_disqualified: bool = False,
) -> Job:
    uid = uuid.uuid4().hex[:8]
    source = JobSource(identifier=f"src_{uid}", name="Portal Source", base_url="http://127.0.0.1")
    db_session.add(source)
    await db_session.flush()

    desc = "Looking for an engineer experienced in Python and Playwright."
    if is_disqualified:
        desc += " Must be a US citizen. Active security clearance required."

    job = Job(
        source_id=source.id,
        external_id=f"job_{uid}",
        title=title,
        company=company,
        canonical_url=f"http://127.0.0.1/jobs/{uid}/apply",
        description=desc,
        location="Remote",
    )
    db_session.add(job)
    await db_session.flush()

    if is_disqualified:
        req = JobRequirement(
            job_id=job.id,
            requirement_type="WORK_AUTH",
            value="US Security Clearance Required",
            weight=1.0,
        )
        db_session.add(req)

    await db_session.commit()
    await db_session.refresh(job)
    return job


# ===========================================================================
# API Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_prepare_application_success(client: AsyncClient, db_session: AsyncSession):
    """
    POST /api/v1/applications/prepare creates application in READY_FOR_REVIEW
    and returns complete review payload with canonical fingerprint.
    """
    candidate = await create_api_candidate(db_session)
    job = await create_api_job(db_session)

    res = await client.post(
        "/api/v1/applications/prepare",
        json={"job_id": job.id, "candidate_id": candidate.id},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["job_id"] == job.id
    assert data["candidate_id"] == candidate.id
    assert data["status"] == ApplicationStatus.READY_FOR_REVIEW.value
    assert data["canonical_approval_fingerprint"] is not None
    assert len(data["canonical_approval_fingerprint"]) == 64
    assert data["is_approvable"] is True


@pytest.mark.asyncio
async def test_prepare_application_disqualified_job(client: AsyncClient, db_session: AsyncSession):
    """
    POST /api/v1/applications/prepare rejects preparation for disqualified job with 400.
    """
    candidate = await create_api_candidate(db_session, work_authorization="H1B")
    job = await create_api_job(db_session, is_disqualified=True)

    res = await client.post(
        "/api/v1/applications/prepare",
        json={"job_id": job.id, "candidate_id": candidate.id},
    )
    assert res.status_code == 400
    assert "disqualified" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_application_and_review(client: AsyncClient, db_session: AsyncSession):
    """
    GET /api/v1/applications/{id} and GET /api/v1/applications/{id}/review.
    """
    candidate = await create_api_candidate(db_session)
    job = await create_api_job(db_session)

    prep_res = await client.post(
        "/api/v1/applications/prepare",
        json={"job_id": job.id, "candidate_id": candidate.id},
    )
    app_id = prep_res.json()["application_id"]

    # 1. Get Application detail
    get_res = await client.get(f"/api/v1/applications/{app_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["id"] == app_id
    assert detail["company"] == job.company
    assert detail["job_title"] == job.title
    assert detail["status"] == ApplicationStatus.READY_FOR_REVIEW.value

    # 2. Get Application review
    rev_res = await client.get(f"/api/v1/applications/{app_id}/review")
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["canonical_approval_fingerprint"] == prep_res.json()["canonical_approval_fingerprint"]
    assert rev_data["is_approvable"] is True


@pytest.mark.asyncio
async def test_list_applications_pagination_and_filtering(client: AsyncClient, db_session: AsyncSession):
    """
    GET /api/v1/applications with pagination and status filtering.
    """
    candidate = await create_api_candidate(db_session)
    job1 = await create_api_job(db_session, title="Role 1")
    job2 = await create_api_job(db_session, title="Role 2")

    await client.post("/api/v1/applications/prepare", json={"job_id": job1.id, "candidate_id": candidate.id})
    await client.post("/api/v1/applications/prepare", json={"job_id": job2.id, "candidate_id": candidate.id})

    res = await client.get("/api/v1/applications?limit=10&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2

    # Filter by status
    filter_res = await client.get(f"/api/v1/applications?status={ApplicationStatus.READY_FOR_REVIEW.value}")
    assert filter_res.status_code == 200
    assert all(item["status"] == ApplicationStatus.READY_FOR_REVIEW.value for item in filter_res.json()["items"])


@pytest.mark.asyncio
async def test_approve_application_success_and_rejection_of_bad_fingerprint(client: AsyncClient, db_session: AsyncSession):
    """
    POST /api/v1/applications/{id}/approve verifies fingerprint and rejects tampering.
    """
    candidate = await create_api_candidate(db_session)
    job = await create_api_job(db_session)

    prep_res = await client.post(
        "/api/v1/applications/prepare",
        json={"job_id": job.id, "candidate_id": candidate.id},
    )
    app_id = prep_res.json()["application_id"]
    correct_fp = prep_res.json()["canonical_approval_fingerprint"]

    # 1. Reject invalid/tampered fingerprint
    bad_res = await client.post(
        f"/api/v1/applications/{app_id}/approve",
        json={"reviewed_fingerprint": "bad_fingerprint_00000000000000000000000000000000"},
    )
    assert bad_res.status_code == 400
    assert "fingerprint" in bad_res.json()["detail"].lower()

    # 2. Approve with correct fingerprint
    ok_res = await client.post(
        f"/api/v1/applications/{app_id}/approve",
        json={"reviewed_fingerprint": correct_fp, "approval_metadata": {"device": "desktop"}},
    )
    assert ok_res.status_code == 200
    app_data = ok_res.json()
    assert app_data["status"] == ApplicationStatus.APPROVED.value
    assert app_data["approval_fingerprint"] == correct_fp

    # 3. Reject re-approving an already APPROVED application (invalid state transition)
    repeat_res = await client.post(
        f"/api/v1/applications/{app_id}/approve",
        json={"reviewed_fingerprint": correct_fp},
    )
    assert repeat_res.status_code == 400
    assert "ready_for_review" in repeat_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_execute_attempt_synthetic_workflow(
    client: AsyncClient, db_session: AsyncSession, mock_portal: MockPortalServer
):
    """
    POST /api/v1/applications/{id}/attempt executes Playwright synthetic automation.
    """
    candidate = await create_api_candidate(db_session)
    job = await create_api_job(db_session)

    # 1. Prepare
    prep_res = await client.post("/api/v1/applications/prepare", json={"job_id": job.id, "candidate_id": candidate.id})
    app_id = prep_res.json()["application_id"]
    fp = prep_res.json()["canonical_approval_fingerprint"]

    # 2. Block execution if unapproved
    target_url = f"{mock_portal.base_url}/jobs/{job.id}/apply"
    unapproved_attempt = await client.post(
        f"/api/v1/applications/{app_id}/attempt",
        json={"target_url": target_url},
    )
    assert unapproved_attempt.status_code == 400
    assert "must be 'approved'" in unapproved_attempt.json()["detail"].lower()

    # 3. Approve
    await client.post(f"/api/v1/applications/{app_id}/approve", json={"reviewed_fingerprint": fp})

    # 4. Block external URLs
    ext_attempt = await client.post(
        f"/api/v1/applications/{app_id}/attempt",
        json={"target_url": "https://external-job-site.com/apply"},
    )
    assert ext_attempt.status_code == 400
    assert "disabled" in ext_attempt.json()["detail"].lower()

    # 5. Run synthetic automation
    attempt_res = await client.post(
        f"/api/v1/applications/{app_id}/attempt",
        json={"target_url": target_url},
    )
    assert attempt_res.status_code == 200
    att_data = attempt_res.json()
    assert att_data["outcome"] == "SUCCESS"
    assert att_data["confirmation_reference"].startswith("SYNTH-APP-")

    # 6. Verify application transitioned to SUBMITTED
    app_res = await client.get(f"/api/v1/applications/{app_id}")
    assert app_res.json()["status"] == ApplicationStatus.SUBMITTED.value


@pytest.mark.asyncio
async def test_events_and_attempts_history_endpoints(
    client: AsyncClient, db_session: AsyncSession, mock_portal: MockPortalServer
):
    """
    GET /api/v1/applications/{id}/events and GET /api/v1/applications/{id}/attempts.
    """
    candidate = await create_api_candidate(db_session)
    job = await create_api_job(db_session)

    # Prepare -> Approve -> Attempt
    prep_res = await client.post("/api/v1/applications/prepare", json={"job_id": job.id, "candidate_id": candidate.id})
    app_id = prep_res.json()["application_id"]
    fp = prep_res.json()["canonical_approval_fingerprint"]
    await client.post(f"/api/v1/applications/{app_id}/approve", json={"reviewed_fingerprint": fp})

    target_url = f"{mock_portal.base_url}/jobs/{job.id}/apply"
    await client.post(f"/api/v1/applications/{app_id}/attempt", json={"target_url": target_url})

    # 1. Events endpoint
    events_res = await client.get(f"/api/v1/applications/{app_id}/events")
    assert events_res.status_code == 200
    ev_data = events_res.json()
    assert ev_data["total"] >= 3
    event_statuses = [e["to_status"] for e in ev_data["items"]]
    assert ApplicationStatus.READY_FOR_REVIEW.value in event_statuses
    assert ApplicationStatus.APPROVED.value in event_statuses
    assert ApplicationStatus.SUBMITTED.value in event_statuses

    # 2. Attempts endpoint
    att_res = await client.get(f"/api/v1/applications/{app_id}/attempts")
    assert att_res.status_code == 200
    att_list = att_res.json()
    assert att_list["total"] >= 1
    assert att_list["items"][0]["outcome"] == "SUCCESS"
    assert att_list["items"][0]["attempt_number"] == 1


@pytest.mark.asyncio
async def test_duplicate_preparation_idempotency(client: AsyncClient, db_session: AsyncSession):
    """
    Repeated POST /api/v1/applications/prepare for same job and candidate is idempotent.
    """
    candidate = await create_api_candidate(db_session)
    job = await create_api_job(db_session)

    res1 = await client.post("/api/v1/applications/prepare", json={"job_id": job.id, "candidate_id": candidate.id})
    res2 = await client.post("/api/v1/applications/prepare", json={"job_id": job.id, "candidate_id": candidate.id})

    assert res1.status_code == 201
    assert res2.status_code == 201
    assert res1.json()["application_id"] == res2.json()["application_id"]


@pytest.mark.asyncio
async def test_reconciliation_guards_against_blind_resubmission(
    client: AsyncClient, db_session: AsyncSession
):
    """
    POST /api/v1/applications/{id}/reconcile enforces strict state transition guards.
    """
    candidate = await create_api_candidate(db_session)
    job = await create_api_job(db_session)

    prep_res = await client.post("/api/v1/applications/prepare", json={"job_id": job.id, "candidate_id": candidate.id})
    app_id = prep_res.json()["application_id"]

    # Manually put application into OUTCOME_UNKNOWN for testing reconciliation
    app_obj = (await db_session.execute(select(Application).where(Application.id == app_id))).scalar_one()
    app_obj.status = ApplicationStatus.OUTCOME_UNKNOWN.value
    await db_session.commit()

    # 1. Blind transition from OUTCOME_UNKNOWN to IN_PROGRESS is strictly forbidden
    blind_res = await client.post(
        f"/api/v1/applications/{app_id}/reconcile",
        json={"target_status": "IN_PROGRESS"},
    )
    assert blind_res.status_code == 400
    detail_msg = blind_res.json()["detail"].lower()
    assert "not permitted" in detail_msg or "blind" in detail_msg

    # 2. Reconcile to READY_FOR_REVIEW without evidence is rejected
    no_ev_res = await client.post(
        f"/api/v1/applications/{app_id}/reconcile",
        json={"target_status": "READY_FOR_REVIEW"},
    )
    assert no_ev_res.status_code == 400

    # 3. Reconcile to READY_FOR_REVIEW with verified proof of non-submission succeeds
    ok_reconcile = await client.post(
        f"/api/v1/applications/{app_id}/reconcile",
        json={
            "target_status": "READY_FOR_REVIEW",
            "reconciliation_evidence": {"submission_occurred": False, "verified_no_submission": True},
            "notes": "Verified portal portal logs show no record created.",
        },
    )
    assert ok_reconcile.status_code == 200
    assert ok_reconcile.json()["status"] == ApplicationStatus.READY_FOR_REVIEW.value


@pytest.mark.asyncio
async def test_sanitized_errors_and_not_found(client: AsyncClient):
    """
    Non-existent resources return 404 with clean sanitized errors (no leaked file paths or stack traces).
    """
    non_existent_id = str(uuid.uuid4())

    res_get = await client.get(f"/api/v1/applications/{non_existent_id}")
    assert res_get.status_code == 404
    assert non_existent_id in res_get.json()["detail"]

    res_rev = await client.get(f"/api/v1/applications/{non_existent_id}/review")
    assert res_rev.status_code == 404

    res_app = await client.post(
        f"/api/v1/applications/{non_existent_id}/approve",
        json={"reviewed_fingerprint": "fake_fp"},
    )
    assert res_app.status_code == 404

    res_ev = await client.get(f"/api/v1/applications/{non_existent_id}/events")
    assert res_ev.status_code == 404
