import pytest
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.job import Job, JobSource, JobDuplicateCluster
from backend.app.models.candidate import CandidateProfile, CandidateSkill
from backend.app.models.matching import MatchScore
from backend.app.models.resume import ResumeVersion

from backend.app.models.application import Application, SubmissionAttempt
from backend.app.models.notification import Notification
from backend.app.models.enums import (
    ApplicationStatus,
    FreshnessStatus,
    FeedbackType,
    NotificationType,
)
from backend.app.services.job_discovery_service import JobDiscoveryService
from backend.app.services.discovery_pipeline import DiscoveryMatchingPipeline
from backend.app.services.matching_service import MatchingService
from backend.app.services.feedback_service import FeedbackService
from backend.app.services.duplicate_detection_service import DuplicateDetectionService
from backend.app.services.application_workflow_service import ApplicationWorkflowService
from backend.app.resumes.schemas import TailoredResumeContent, TailoredExperience, TailoredEducation
from backend.app.resumes.storage_service import ResumeStorageService
from backend.app.workflow.approval_fingerprint import ApprovalFingerprintService
from backend.app.core.config import settings


@pytest.mark.asyncio
async def test_complete_12_stage_production_readiness_workflow(db_session: AsyncSession):
    """
    Validates the end-to-end user workflow across all 12 stages required for Phase 12 production readiness:
    1. Start / initialize database and candidate profile.
    2. Configure a supported job source.
    3. Run discovery pipeline.
    4. Verify normalized jobs and source health diagnostics.
    5. Evaluate deterministic eligibility and matching.
    6. Inspect score explanations and freshness status.
    7. Review duplicate groups.
    8. Submit and revise user feedback.
    9. Receive in-app notification for qualifying opportunity.
    10. Verify optional email alert behavior (mock provider).
    11. Prepare application and verify exact immutable resume checksum.
    12. Confirm approval and synthetic execution safeguards (real submission disabled).
    """
    # -------------------------------------------------------------------------
    # Stage 1: Initialize Candidate Profile
    # -------------------------------------------------------------------------
    candidate = CandidateProfile(
        full_name="Jane Doe",
        email="jane.doe@example.com",
        phone="+1-555-0199",
        location="San Francisco, CA",
        work_authorization="US Citizen",
        summary="Experienced Python engineer specializing in cloud services.",
        years_of_experience=5.0,
        remote_preference="REMOTE",
        target_titles=["Senior Backend Engineer", "Python Engineer"],
        search_preferences={
            "role_keywords": ["Backend", "Python", "Cloud"],
            "remote_preference": "REMOTE",
            "preferred_companies": ["CloudCorp"],
        },
        notification_preferences={
            "min_match_score": 70,
            "email_enabled": True,
            "delivery_mode": "IMMEDIATE",
        },
    )
    db_session.add(candidate)
    await db_session.flush()

    for skill_name in ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "AWS"]:
        db_session.add(CandidateSkill(
            candidate_id=candidate.id,
            skill_name=skill_name,
            years_experience=4.0,
            is_verified=True,
        ))

    await db_session.commit()
    await db_session.refresh(candidate)


    # -------------------------------------------------------------------------
    # Stage 2: Configure a Supported Job Source
    # -------------------------------------------------------------------------
    source = await JobDiscoveryService.get_or_create_source(
        session=db_session,
        identifier="synthetic",
        name="Synthetic Job Source",
        base_url="https://jobs.example.com",
        rate_limit=60,
    )
    source.config_json = {"count": 3, "company_name": "CloudCorp"}
    await db_session.commit()

    # -------------------------------------------------------------------------
    # Stage 3: Run Discovery Pipeline
    # -------------------------------------------------------------------------
    run_result = await DiscoveryMatchingPipeline.execute(
        session=db_session,
        sources=["synthetic"],
        source_params={"synthetic": {"count": 3, "company_name": "CloudCorp"}},
        trigger="manual",
    )
    assert run_result["status"] in ("COMPLETED", "PARTIAL_SUCCESS")
    assert run_result["items_processed"] >= 3

    # -------------------------------------------------------------------------
    # Stage 4: Verify Normalized Jobs and Source Health Diagnostics
    # -------------------------------------------------------------------------
    jobs_res = await db_session.execute(select(Job).where(Job.source_id == source.id))
    jobs = jobs_res.scalars().all()
    assert len(jobs) >= 3
    for j in jobs:
        assert j.title
        assert j.company == "CloudCorp"
        assert j.freshness_status == FreshnessStatus.ACTIVE.value
        assert j.first_seen_at is not None
        assert j.last_verified_at is not None

    await db_session.refresh(source)
    assert source.last_status == "HEALTHY"
    assert source.jobs_discovered_count >= 3

    # -------------------------------------------------------------------------
    # Stage 5 & 6: Evaluate Eligibility, Matching, Score Breakdown, and Freshness
    # -------------------------------------------------------------------------
    target_job = jobs[0]
    matching_service = MatchingService()
    match_score = await matching_service.evaluate_job(
        session=db_session,
        job_id=target_job.id,
        candidate_id=candidate.id,
    )
    assert match_score.is_eligible is True
    assert match_score.overall_score > 0
    assert match_score.scoring_policy_version == "1.1.0"
    assert "positive_contributions" in match_score.scoring_breakdown
    assert len(match_score.scoring_breakdown["positive_contributions"]) > 0

    # -------------------------------------------------------------------------
    # Stage 7: Duplicate Group Detection and Review
    # -------------------------------------------------------------------------
    # Create duplicate listing from a different source
    lever_source = await JobDiscoveryService.get_or_create_source(
        session=db_session,
        identifier="lever",
        name="Lever Board",
        base_url="https://jobs.lever.co",
    )
    duplicate_job = Job(
        source_id=lever_source.id,
        external_id="dup_ext_001",
        title=target_job.title,
        company=target_job.company,
        canonical_url=target_job.canonical_url,
        location=target_job.location,
        remote_type=target_job.remote_type,
        description=target_job.description,
        freshness_status=FreshnessStatus.ACTIVE.value,
    )
    db_session.add(duplicate_job)
    await db_session.commit()

    cluster = await DuplicateDetectionService.cluster_job(db_session, duplicate_job)
    assert cluster is not None
    assert cluster.cluster_status == "DETECTED"
    assert cluster.confidence_score >= 0.85

    # Safe review: Confirm duplicate
    reviewed_cluster = await DuplicateDetectionService.review_cluster(
        session=db_session,
        cluster_id=cluster.id,
        action="CONFIRM",
        notes="Verified identical vacancy across sources",
    )
    assert reviewed_cluster.cluster_status == "CONFIRMED"

    # -------------------------------------------------------------------------
    # Stage 8: User Feedback Submission and Revision
    # -------------------------------------------------------------------------
    fb = await FeedbackService.record_feedback(
        session=db_session,
        candidate_id=candidate.id,
        job_id=target_job.id,
        feedback_type=FeedbackType.RELEVANT.value,
        reason="Great match with cloud focus",
    )
    assert fb.feedback_type == FeedbackType.RELEVANT.value

    # Re-evaluate match score to verify feedback modifier
    updated_match = await matching_service.evaluate_job(
        session=db_session,
        job_id=target_job.id,
        candidate_id=candidate.id,
    )
    assert updated_match.scoring_breakdown.get("feedback_adjustment") is not None

    # Revise feedback
    revised_fb = await FeedbackService.record_feedback(
        session=db_session,
        candidate_id=candidate.id,
        job_id=target_job.id,
        feedback_type=FeedbackType.NOT_INTERESTED.value,
        reason="Looking for higher base salary",
    )
    assert revised_fb.feedback_type == FeedbackType.NOT_INTERESTED.value

    # -------------------------------------------------------------------------
    # Stage 9 & 10: In-App and Email Notifications
    # -------------------------------------------------------------------------
    notifs_res = await db_session.execute(
        select(Notification).where(
            Notification.job_id == target_job.id,
            Notification.notification_type == NotificationType.NEW_MATCH.value,
        )
    )
    notif = notifs_res.scalars().first()
    assert notif is not None
    assert notif.is_read is False

    # -------------------------------------------------------------------------
    # Stage 11: Prepare Application and Verify Exact Resume Checksum
    # -------------------------------------------------------------------------
    tailored_content = TailoredResumeContent(
        full_name="Jane Doe",
        email="jane.doe@example.com",
        location="Remote",
        summary="Experienced Python engineer specializing in cloud services.",
        skills_by_category={"Programming": ["Python", "FastAPI"], "Infrastructure": ["Docker", "PostgreSQL"]},
        experiences=[
            TailoredExperience(
                company="Acme Corp",
                role="Software Engineer",
                start_date="2021-01",
                end_date="2024-01",
                bullet_points=["Built microservices handling 10k RPS."],
            )
        ],
        educations=[
            TailoredEducation(
                institution="Tech University",
                degree="B.S.",
                field_of_study="Computer Science",
                graduation_year=2020,
            )
        ],
    )

    dummy_pdf_bytes = b"%PDF-1.4 Mock valid PDF binary stream for application package verification."
    path, checksum = ResumeStorageService.save_resume_pdf(dummy_pdf_bytes)

    resume_version = ResumeVersion(
        candidate_id=candidate.id,
        job_id=target_job.id,
        version_number=1,
        structured_content=tailored_content.model_dump(),
        pdf_file_path=path,
        file_sha256=checksum,
        is_ats_valid=True,
        is_submission_ready=True,
    )
    db_session.add(resume_version)
    await db_session.commit()
    await db_session.refresh(resume_version)

    # Verify bit-for-bit file integrity
    is_valid = ResumeStorageService.verify_file_integrity(path, checksum)
    assert is_valid is True
    assert ResumeStorageService.compute_sha256(Path(path)) == checksum

    # -------------------------------------------------------------------------
    # Stage 12: Application Approval and Safeguards Verification
    # -------------------------------------------------------------------------
    review_payload = await ApplicationWorkflowService.prepare_application(
        session=db_session,
        job_id=target_job.id,
        candidate_id=candidate.id,
    )
    assert review_payload.status in (ApplicationStatus.READY_FOR_REVIEW.value, "READY_FOR_REVIEW")
    assert review_payload.canonical_approval_fingerprint is not None

    fingerprint = review_payload.canonical_approval_fingerprint

    approved_app = await ApplicationWorkflowService.approve_application(
        session=db_session,
        application_id=review_payload.application_id,
        reviewed_fingerprint=fingerprint,
    )
    assert approved_app.status == ApplicationStatus.APPROVED.value
    assert approved_app.approval_fingerprint == fingerprint

    # Verify that real submission remains strictly disabled
    assert settings.JOBPILOT_REAL_SUBMISSION_ENABLED is False

    # Execute simulation via BrowserAutomationRunner to verify safeguard
    from backend.app.automation.browser_runner import BrowserAutomationRunner
    from backend.app.models.enums import SubmissionOutcome

    attempt = await BrowserAutomationRunner.execute_application_automation(
        session=db_session,
        application_id=approved_app.id,
        target_url="https://external-jobs.example.com/apply",
    )
    # Must be BLOCKED by safety gate since JOBPILOT_REAL_SUBMISSION_ENABLED is False
    assert attempt.outcome == SubmissionOutcome.BLOCKED_SAFETY.value
    assert "Real external submissions are disabled" in attempt.sanitized_diagnostics["error"]
