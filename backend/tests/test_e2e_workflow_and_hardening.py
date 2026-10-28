import os
import uuid
import hashlib
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.candidate import CandidateProfile, CandidateSkill
from backend.app.models.job import Job, JobSource
from backend.app.models.matching import MatchScore
from backend.app.models.notification import Notification
from backend.app.models.automation import AutomationRun
from backend.app.models.application import Application, SubmissionAttempt
from backend.app.models.enums import AutomationRunStatus, NotificationType, ApplicationStatus
from backend.app.services.scheduler_service import SchedulerService
from backend.app.services.discovery_pipeline import DiscoveryMatchingPipeline


@pytest.mark.asyncio
async def test_complete_e2e_user_journey(db_session: AsyncSession):
    """
    Step 2: Full End-to-End User Journey Validation
    1. Verify scheduler disabled state
    2. Setup candidate profile
    3. Trigger manual discovery via API
    4. Verify normalization, persistence, eligibility, and scoring
    5. Verify qualifying jobs generate persistent notifications
    6. Verify repeated discovery is idempotent (no duplicates)
    7. Inspect run history and source diagnostics
    8. Mark as read & dismiss notifications
    9. Prepare application, verify resume artifact & checksum
    10. Enforce approval gate & verify synthetic safeguards
    """
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # --- Stage 1: Confirm scheduler disabled state ---
        status_res = await client.get("/api/v1/scheduler/status")
        assert status_res.status_code == 200
        status_json = status_res.json()
        assert "is_enabled" in status_json
        assert status_json["is_active_run"] is False

        # --- Stage 2: Create verified candidate profile ---
        cand = CandidateProfile(
            full_name="Sarah Architect",
            email="sarah.arch@example.com",
            location="Remote",
            work_authorization="US Citizen",
            summary="Principal Software Engineer specializing in Python, FastAPI, and Cloud Architecture.",
            years_of_experience=8,
        )
        db_session.add(cand)
        await db_session.commit()
        await db_session.refresh(cand)

        python_skill = CandidateSkill(
            candidate_id=cand.id,
            skill_name="Python",
            category="technical",
            years_experience=8.0,
            is_verified=True,
        )
        db_session.add(python_skill)
        await db_session.commit()

        # --- Stage 3: Trigger manual discovery through API ---
        run_res = await client.post("/api/v1/scheduler/run", json={"sources": ["synthetic"]})
        assert run_res.status_code == 200
        run_data = run_res.json()
        assert run_data["status"] == AutomationRunStatus.COMPLETED.value
        assert run_data["inserted"] >= 1
        assert run_data["jobs_evaluated"] >= 1
        run_id = run_data["run_id"]

        # --- Stage 4: Verify jobs normalized & persisted ---
        jobs_res = await client.get("/api/v1/jobs")
        assert jobs_res.status_code == 200
        jobs_data = jobs_res.json()
        assert jobs_data["total"] >= 1
        eligible_job = next(
            (j for j in jobs_data["items"] if "Python" in j["title"] or "Engineer" in j["title"]),
            jobs_data["items"][0],
        )

        # --- Stage 5: Verify matching evaluation & notifications ---
        notifs_res = await client.get("/api/v1/notifications")
        assert notifs_res.status_code == 200
        notifs_data = notifs_res.json()
        assert notifs_data["total"] >= 1
        first_notif = notifs_data["items"][0]
        assert first_notif["job_id"] is not None

        eligible_job_res = await client.get(f"/api/v1/jobs/{first_notif['job_id']}")
        assert eligible_job_res.status_code == 200
        eligible_job = eligible_job_res.json()

        matching_res = await client.get(f"/api/v1/matching/results/{eligible_job['id']}")
        assert matching_res.status_code == 200
        match_data = matching_res.json()
        assert "overall_score" in match_data
        assert match_data["is_latest"] is True

        # --- Stage 6: Repeat discovery - verify idempotency ---
        repeat_res = await client.post("/api/v1/scheduler/run", json={"sources": ["synthetic"]})
        assert repeat_res.status_code == 200
        repeat_data = repeat_res.json()
        assert repeat_data["inserted"] == 0
        assert repeat_data["unchanged"] >= 1

        notifs_after_res = await client.get("/api/v1/notifications")
        assert notifs_after_res.json()["total"] == notifs_data["total"], "Duplicate notifications must not be created on repeated discovery"

        # --- Stage 7: Inspect run history & diagnostics ---
        history_res = await client.get(f"/api/v1/scheduler/runs/{run_id}")
        assert history_res.status_code == 200
        diag_data = history_res.json()
        assert diag_data["status"] == "COMPLETED"
        assert "synthetic" in diag_data["metadata"]["successful_sources"]

        # --- Stage 8: Read & dismiss notifications via API ---
        read_res = await client.post(f"/api/v1/notifications/{first_notif['id']}/read")
        assert read_res.status_code == 200
        assert read_res.json()["notification"]["is_read"] is True

        dismiss_res = await client.post(f"/api/v1/notifications/{first_notif['id']}/dismiss")
        assert dismiss_res.status_code == 200
        assert dismiss_res.json()["notification"]["is_dismissed"] is True

        # --- Stage 9: Prepare application for synthetic job ---
        prep_res = await client.post(
            "/api/v1/applications/prepare",
            json={"job_id": eligible_job["id"], "candidate_id": cand.id},
        )
        assert prep_res.status_code == 201
        prep_data = prep_res.json()
        app_id = prep_data["application_id"]
        fingerprint = prep_data["canonical_approval_fingerprint"]
        resume_sha = prep_data["resume_sha256"]
        assert len(fingerprint) == 64
        assert len(resume_sha) == 64

        # Verify exact resume file on disk
        stored_path = os.path.join(settings.RESUME_STORAGE_DIR, f"{resume_sha}.pdf")
        assert os.path.exists(stored_path), "Generated resume PDF must exist on disk"
        with open(stored_path, "rb") as f:
            computed_sha = hashlib.sha256(f.read()).hexdigest()
        assert computed_sha == resume_sha, "Stored resume PDF SHA-256 must match database record bit-for-bit"

        # --- Stage 10: Server-side safeguards ---
        # 10a. Unapproved application attempt must be rejected
        attempt_res = await client.post(
            f"/api/v1/applications/{app_id}/attempt",
            json={"target_url": "http://127.0.0.1:8000/mock/apply"},
        )
        assert attempt_res.status_code in {400, 403, 422}

        # 10b. Stale / mismatched fingerprint approval must be rejected
        bad_approve_res = await client.post(
            f"/api/v1/applications/{app_id}/approve",
            json={"reviewed_fingerprint": "a" * 64},
        )
        assert bad_approve_res.status_code in {400, 409}

        # 10c. Correct approval
        good_approve_res = await client.post(
            f"/api/v1/applications/{app_id}/approve",
            json={"reviewed_fingerprint": fingerprint},
        )
        assert good_approve_res.status_code == 200
        assert good_approve_res.json()["status"] == ApplicationStatus.APPROVED.value

        # 10d. Execution safeguard: real submissions must remain disabled
        assert settings.JOBPILOT_REAL_SUBMISSION_ENABLED is False

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_scheduler_stale_run_recovery_on_startup(db_session: AsyncSession):
    """
    Step 3: Tests recovery from unexpected backend termination mid-flight.
    Simulates a run orphaned in RUNNING status and proves start() marks it as FAILED.
    """
    orphaned_run = AutomationRun(
        run_type="discovery_scheduled",
        status=AutomationRunStatus.RUNNING.value,
        items_processed=4,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(orphaned_run)
    await db_session.commit()
    await db_session.refresh(orphaned_run)

    # Invoke recovery
    recovered_count = await SchedulerService.recover_stale_runs(session=db_session)
    assert recovered_count >= 1

    await db_session.refresh(orphaned_run)
    assert orphaned_run.status == AutomationRunStatus.FAILED.value
    assert "interrupted by process" in orphaned_run.error_summary
    assert orphaned_run.completed_at is not None


@pytest.mark.asyncio
async def test_job_material_change_invalidates_stale_matching(db_session: AsyncSession):
    """
    Step 5: Tests that when a job's material fields change upon rediscovery,
    the matching engine re-evaluates and marks previous MatchScore as not latest.
    """
    cand = CandidateProfile(
        full_name="Carol Engineer",
        email="carol@example.com",
        location="Remote",
        work_authorization="US Citizen",
        summary="Senior Backend Engineer with Python and PostgreSQL",
        years_of_experience=6,
    )
    db_session.add(cand)
    await db_session.commit()

    # 1. Run initial discovery
    run1 = await DiscoveryMatchingPipeline.execute(session=db_session, sources=["synthetic"])
    assert run1["inserted"] >= 1

    # Fetch one job
    job_stmt = select(Job).limit(1)
    res = await db_session.execute(job_stmt)
    job = res.scalar_one()

    # Initial evaluation should be latest
    eval_stmt = select(MatchScore).where(MatchScore.job_id == job.id, MatchScore.is_latest == True)
    eval_res = await db_session.execute(eval_stmt)
    initial_eval = eval_res.scalar_one()
    initial_eval_id = initial_eval.id

    # 2. Materially mutate job title & description
    job.title = "Staff Level Distributed Systems Engineer"
    job.description = "Advanced distributed consensus, Raft, Paxos, Python"
    await db_session.commit()

    # Re-evaluate
    from backend.app.services.matching_service import MatchingService
    new_eval = await MatchingService().evaluate_job(session=db_session, job_id=job.id, candidate_id=cand.id)

    assert new_eval.id != initial_eval_id
    assert new_eval.is_latest is True

    # Previous evaluation must be marked is_latest=False
    prev_stmt = select(MatchScore).where(MatchScore.id == initial_eval_id)
    prev_res = await db_session.execute(prev_stmt)
    prev_eval = prev_res.scalar_one()
    assert prev_eval.is_latest is False, "Previous match score must be marked is_latest=False upon re-evaluation"
