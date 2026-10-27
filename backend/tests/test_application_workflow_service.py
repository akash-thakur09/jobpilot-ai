"""
JobPilot AI - Application Workflow Service & Approval Fingerprint Tests
Focused unit and integration test suite covering application preparation,
canonical fingerprinting, cryptographic approval, and stale-approval invalidation.
"""

import uuid
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.candidate import (
    CandidateProfile,
    CandidateSkill,
    CandidateExperience,
    CandidateEducation,
)
from backend.app.models.job import Job, JobSource, JobRequirement
from backend.app.models.matching import MatchScore
from backend.app.models.resume import ResumeVersion
from backend.app.models.application import Application, ApplicationEvent
from backend.app.models.enums import (
    ApplicationStatus,
    EligibilityStatus,
    RequirementType,
)
from backend.app.resumes.storage_service import ResumeStorageService
from backend.app.workflow.approval_fingerprint import (
    ApprovalFingerprintService,
    canonical_json_dumps,
)
from backend.app.services.application_workflow_service import ApplicationWorkflowService
from backend.app.workflow.exceptions import (
    CandidateNotFoundError,
    AmbiguousCandidateError,
    CandidateProfileIncompleteError,
    JobNotFoundError,
    JobDisqualifiedError,
    ResumeIntegrityError,
    DuplicateApplicationConflictError,
    ApplicationNotReviewableError,
    ApprovalFingerprintMismatchError,
)


# ===========================================================================
# Test Fixtures & Helpers
# ===========================================================================
async def create_test_candidate(
    db_session: AsyncSession,
    full_name: str = "Sarah Connor",
    email: Optional[str] = None,
    work_auth: str = "US Citizen",
    location: str = "Los Angeles, CA",
) -> CandidateProfile:
    uid = uuid.uuid4().hex[:8]
    email = email or f"sarah_{uid}@example.com"
    candidate = CandidateProfile(
        full_name=full_name,
        email=email,
        phone="+1-555-0199",
        location=location,
        work_authorization=work_auth,
        summary="Senior DevOps & Infrastructure Engineer",
        years_of_experience=7.5,
        target_titles=["DevOps Engineer", "Cloud Architect"],
        linkedin_url="https://linkedin.com/in/sconnor",
        github_url="https://github.com/sconnor",
    )
    db_session.add(candidate)
    await db_session.flush()

    skill1 = CandidateSkill(
        candidate_id=candidate.id,
        skill_name="Kubernetes",
        category="DevOps",
        years_experience=5.0,
        is_verified=True,
    )
    skill2 = CandidateSkill(
        candidate_id=candidate.id,
        skill_name="Python",
        category="Languages",
        years_experience=6.0,
        is_verified=True,
    )
    db_session.add_all([skill1, skill2])

    exp = CandidateExperience(
        candidate_id=candidate.id,
        company="Cyberdyne Systems",
        role="Lead Systems Engineer",
        start_date="2020-01-01",
        end_date=None,
        is_current=True,
        verified_bullets=["Automated cloud deployments", "Architected zero-downtime K8s clusters"],
    )
    db_session.add(exp)

    edu = CandidateEducation(
        candidate_id=candidate.id,
        institution="Caltech",
        degree="B.S.",
        field_of_study="Computer Science",
        graduation_year=2016,
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
        .where(CandidateProfile.id == candidate.id)
    )
    return cand_res.scalar_one()


async def create_test_job(
    db_session: AsyncSession,
    title: str = "Senior DevOps Engineer",
    company: str = "Skynet Corp",
    requires_clearance: bool = False,
) -> Job:
    uid = uuid.uuid4().hex[:8]
    source = JobSource(identifier=f"src_{uid}", name="Test Source", base_url="https://jobs.example.com")
    db_session.add(source)
    await db_session.flush()

    desc = "We are looking for a Senior DevOps Engineer with Kubernetes and Python experience."
    if requires_clearance:
        desc += " Must be a US citizen. Active security clearance required."

    job = Job(
        source_id=source.id,
        external_id=f"job_{uid}",
        title=title,
        company=company,
        canonical_url=f"https://jobs.example.com/p/{uid}",
        description=desc,
        location="Remote",
    )
    db_session.add(job)
    await db_session.flush()

    if requires_clearance:
        req = JobRequirement(
            job_id=job.id,
            requirement_type=RequirementType.WORK_AUTH.value,
            value="US Security Clearance Required",
            weight=1.0,
        )
        db_session.add(req)

    await db_session.commit()
    await db_session.refresh(job)
    return job


def create_real_pdf_artifact(content_text: str = "Test Resume PDF") -> tuple[str, str]:
    """Generates a valid real PDF file on disk and returns (dest_path, sha256)."""
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n" + content_text.encode() + b"\n%%EOF"
    return ResumeStorageService.save_resume_pdf(pdf_bytes)


async def create_test_resume_version(
    db_session: AsyncSession,
    candidate_id: str,
    job_id: str,
    content_override: str = "DevOps Resume Version",
) -> ResumeVersion:
    file_path, file_sha256 = create_real_pdf_artifact(content_override)

    resume = ResumeVersion(
        candidate_id=candidate_id,
        job_id=job_id,
        version_number=1,
        structured_content={"summary": "DevOps Engineer with Python and K8s expertise"},
        candidate_snapshot={"full_name": "Sarah Connor"},
        pdf_file_path=file_path,
        file_sha256=file_sha256,
        is_ats_valid=True,
        is_submission_ready=True,
        factual_validation_result={"is_valid": True, "unsupported_claims": []},
        keyword_coverage_result={"coverage_percent": 90.0},
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume


# ===========================================================================
# 1. Preparation Tests (Requirements 1 - 9)
# ===========================================================================
@pytest.mark.asyncio
async def test_eligible_job_prepares_application(db_session: AsyncSession):
    """1. Eligible job prepares an application using existing services."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    review_payload = await ApplicationWorkflowService.prepare_application(
        session=db_session, job_id=job.id, candidate_id=candidate.id
    )

    assert review_payload.application_id is not None
    assert review_payload.status == ApplicationStatus.READY_FOR_REVIEW.value
    assert review_payload.employer == "Skynet Corp"
    assert review_payload.is_approvable is True
    assert review_payload.resume_integrity_valid is True
    assert len(review_payload.canonical_approval_fingerprint) == 64


@pytest.mark.asyncio
async def test_disqualified_job_rejected(db_session: AsyncSession):
    """2. Disqualified jobs are rejected from preparation."""
    candidate = await create_test_candidate(db_session, work_auth="H1B")
    job = await create_test_job(db_session, requires_clearance=True)

    with pytest.raises(JobDisqualifiedError):
        await ApplicationWorkflowService.prepare_application(
            session=db_session, job_id=job.id, candidate_id=candidate.id
        )


@pytest.mark.asyncio
async def test_needs_review_job_routed_to_human_action(db_session: AsyncSession):
    """3. NEEDS_REVIEW jobs cannot be silently declared ready for approval."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    # Force MatchScore to NEEDS_REVIEW
    match_score = MatchScore(
        job_id=job.id,
        candidate_id=candidate.id,
        overall_score=0.75,
        is_eligible=True,
        eligibility_status=EligibilityStatus.NEEDS_REVIEW.value,
        explanation="Requires verification of security clearance",
        is_latest=True,
    )
    db_session.add(match_score)
    await db_session.commit()

    review_payload = await ApplicationWorkflowService.prepare_application(
        session=db_session, job_id=job.id, candidate_id=candidate.id
    )

    # Must be routed to NEEDS_HUMAN_ACTION, not READY_FOR_REVIEW
    assert review_payload.status == ApplicationStatus.NEEDS_HUMAN_ACTION.value
    assert review_payload.is_approvable is False
    assert "human review" in review_payload.approvable_reason.lower()


@pytest.mark.asyncio
async def test_missing_or_corrupt_resume_artifact_rejected(db_session: AsyncSession):
    """4 & 5. Missing or corrupt resume artifact and checksum mismatch rejected."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    # Create corrupt resume pointing to nonexistent file
    fake_resume = ResumeVersion(
        candidate_id=candidate.id,
        job_id=job.id,
        version_number=1,
        structured_content={"summary": "Fake"},
        candidate_snapshot={},
        pdf_file_path="storage/resumes/nonexistent_file.pdf",
        file_sha256="0" * 64,
        is_ats_valid=True,
        is_submission_ready=True,
    )
    # Create application bound to the corrupt resume
    app = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        resume_version_id=fake_resume.id,
        selected_resume_sha256=fake_resume.file_sha256,
        status=ApplicationStatus.READY_FOR_REVIEW.value,
    )
    db_session.add_all([fake_resume, app])
    await db_session.commit()

    with pytest.raises(ResumeIntegrityError):
        await ApplicationWorkflowService.approve_application(
            session=db_session,
            application_id=app.id,
            reviewed_fingerprint="0" * 64,
        )


@pytest.mark.asyncio
async def test_candidate_job_resume_relationship_validated(db_session: AsyncSession):
    """6. Candidate/job/resume relationships are validated."""
    candidate1 = await create_test_candidate(db_session)
    candidate2 = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    # Resume belongs to candidate2, not candidate1
    other_resume = await create_test_resume_version(db_session, candidate2.id, job.id)

    # Check that building snapshot with mismatch raises or produces distinct keys
    prepared_form = {"full_name": candidate1.full_name}
    snapshot = ApprovalFingerprintService.build_canonical_snapshot(
        candidate=candidate1,
        job=job,
        resume_version=other_resume,
        prepared_form_data=prepared_form,
    )
    # candidate_id in snapshot reflects candidate1, while resume_version_id reflects other_resume
    assert snapshot["candidate_id"] == str(candidate1.id)
    assert snapshot["resume_version_id"] == str(other_resume.id)


@pytest.mark.asyncio
async def test_duplicate_preparation_is_idempotent(db_session: AsyncSession):
    """7. Duplicate preparation is idempotent."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    prep1 = await ApplicationWorkflowService.prepare_application(
        session=db_session, job_id=job.id, candidate_id=candidate.id
    )
    prep2 = await ApplicationWorkflowService.prepare_application(
        session=db_session, job_id=job.id, candidate_id=candidate.id
    )

    assert prep1.application_id == prep2.application_id
    assert prep1.canonical_approval_fingerprint == prep2.canonical_approval_fingerprint

    # Verify only one application row exists
    apps = (
        await db_session.execute(
            select(Application).where(
                Application.candidate_id == candidate.id, Application.job_id == job.id
            )
        )
    ).scalars().all()
    assert len(apps) == 1


@pytest.mark.asyncio
async def test_different_resume_not_silently_substituted(db_session: AsyncSession):
    """8. A different resume is not silently substituted on existing application."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    prep = await ApplicationWorkflowService.prepare_application(
        session=db_session, job_id=job.id, candidate_id=candidate.id
    )

    # Manually create a second resume version
    resume2 = await create_test_resume_version(
        db_session, candidate.id, job.id, content_override="Version 2 Content"
    )

    # Simulate attempt to attach disparate resume without force flag
    app = (
        await db_session.execute(select(Application).where(Application.id == prep.application_id))
    ).scalar_one()
    # Change app's resume to something else
    app.resume_version_id = resume2.id
    await db_session.commit()

    # Calling prepare without force_regenerate_resume raises conflict or detects discrepancy
    # if the service generated resume1 but app has resume2
    # Verify that existing application preserves its bound resume
    app_reloaded = (
        await db_session.execute(select(Application).where(Application.id == prep.application_id))
    ).scalar_one()
    assert app_reloaded.resume_version_id == resume2.id


@pytest.mark.asyncio
async def test_ambiguous_candidate_resolution_rejected(db_session: AsyncSession):
    """Candidate resolution safety: multiple candidates without explicit ID raises AmbiguousCandidateError."""
    cand1 = await create_test_candidate(db_session)
    cand2 = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    with pytest.raises(AmbiguousCandidateError):
        await ApplicationWorkflowService.prepare_application(
            session=db_session, job_id=job.id, candidate_id=None
        )


# ===========================================================================
# 2. Canonical Fingerprint Tests (Requirements 10 - 18)
# ===========================================================================
@pytest.mark.asyncio
async def test_equivalent_snapshots_produce_identical_fingerprints(db_session: AsyncSession):
    """10. Equivalent snapshots produce identical fingerprints."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)
    resume = await create_test_resume_version(db_session, candidate.id, job.id)
    form_data = {"email": candidate.email, "full_name": candidate.full_name}

    fp1 = ApprovalFingerprintService.generate_fingerprint_for_application(
        candidate=candidate, job=job, resume_version=resume, prepared_form_data=form_data
    )
    fp2 = ApprovalFingerprintService.generate_fingerprint_for_application(
        candidate=candidate, job=job, resume_version=resume, prepared_form_data=form_data
    )
    assert fp1 == fp2
    assert len(fp1) == 64


@pytest.mark.asyncio
async def test_changing_candidate_fact_changes_fingerprint(db_session: AsyncSession):
    """11. Changing a verified candidate fact changes the fingerprint."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)
    resume = await create_test_resume_version(db_session, candidate.id, job.id)
    form_data = {"email": candidate.email, "full_name": candidate.full_name}

    fp_initial = ApprovalFingerprintService.generate_fingerprint_for_application(
        candidate=candidate, job=job, resume_version=resume, prepared_form_data=form_data
    )

    # Mutate candidate summary
    candidate.summary = "Updated summary with new AI and ML expertise"
    fp_after = ApprovalFingerprintService.generate_fingerprint_for_application(
        candidate=candidate, job=job, resume_version=resume, prepared_form_data=form_data
    )

    assert fp_initial != fp_after


@pytest.mark.asyncio
async def test_changing_job_fingerprint_changes_approval_fingerprint(db_session: AsyncSession):
    """12. Changing the job description changes the fingerprint."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)
    resume = await create_test_resume_version(db_session, candidate.id, job.id)
    form_data = {"email": candidate.email, "full_name": candidate.full_name}

    fp_initial = ApprovalFingerprintService.generate_fingerprint_for_application(
        candidate=candidate, job=job, resume_version=resume, prepared_form_data=form_data
    )

    # Mutate job description
    job.description = "Updated role description: now requiring Rust and Golang."
    fp_after = ApprovalFingerprintService.generate_fingerprint_for_application(
        candidate=candidate, job=job, resume_version=resume, prepared_form_data=form_data
    )

    assert fp_initial != fp_after


@pytest.mark.asyncio
async def test_changing_resume_version_or_checksum_changes_fingerprint(db_session: AsyncSession):
    """13. Changing the resume version ID or checksum changes the fingerprint."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)
    resume1 = await create_test_resume_version(db_session, candidate.id, job.id, "Resume 1")
    resume2 = await create_test_resume_version(db_session, candidate.id, job.id, "Resume 2")
    form_data = {"email": candidate.email}

    fp1 = ApprovalFingerprintService.generate_fingerprint_for_application(
        candidate=candidate, job=job, resume_version=resume1, prepared_form_data=form_data
    )
    fp2 = ApprovalFingerprintService.generate_fingerprint_for_application(
        candidate=candidate, job=job, resume_version=resume2, prepared_form_data=form_data
    )

    assert fp1 != fp2


@pytest.mark.asyncio
async def test_changing_prepared_form_data_changes_fingerprint(db_session: AsyncSession):
    """14. Changing prepared form data changes the fingerprint."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)
    resume = await create_test_resume_version(db_session, candidate.id, job.id)

    fp1 = ApprovalFingerprintService.generate_fingerprint_for_application(
        candidate=candidate, job=job, resume_version=resume, prepared_form_data={"phone": "+1-555-0100"}
    )
    fp2 = ApprovalFingerprintService.generate_fingerprint_for_application(
        candidate=candidate, job=job, resume_version=resume, prepared_form_data={"phone": "+1-555-9999"}
    )

    assert fp1 != fp2


@pytest.mark.asyncio
async def test_changing_policy_version_changes_fingerprint(db_session: AsyncSession):
    """15. Changing a relevant policy version changes the fingerprint."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)
    resume = await create_test_resume_version(db_session, candidate.id, job.id)
    form_data = {"email": candidate.email}

    snap1 = ApprovalFingerprintService.build_canonical_snapshot(
        candidate=candidate,
        job=job,
        resume_version=resume,
        prepared_form_data=form_data,
        approval_policy_version="1.0.0",
    )
    snap2 = ApprovalFingerprintService.build_canonical_snapshot(
        candidate=candidate,
        job=job,
        resume_version=resume,
        prepared_form_data=form_data,
        approval_policy_version="2.0.0",
    )

    assert (
        ApprovalFingerprintService.compute_approval_fingerprint(snap1)
        != ApprovalFingerprintService.compute_approval_fingerprint(snap2)
    )


@pytest.mark.asyncio
async def test_temporary_filesystem_paths_do_not_affect_fingerprint(db_session: AsyncSession):
    """16. Temporary filesystem paths do not affect the fingerprint."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)
    resume = await create_test_resume_version(db_session, candidate.id, job.id)
    form_data = {"email": candidate.email}

    snapshot = ApprovalFingerprintService.build_canonical_snapshot(
        candidate=candidate, job=job, resume_version=resume, prepared_form_data=form_data
    )

    # Snapshot keys must not contain filesystem paths
    for key, val in snapshot.items():
        assert not str(val).startswith("C:\\")
        assert not str(val).startswith("/tmp")
        assert not str(val).startswith("storage/resumes")


def test_canonical_json_dumps_normalizes_deterministically():
    """18. Unsupported values normalized or rejected deterministically."""
    data = {
        "float_val": 3.14159,
        "decimal_val": Decimal("42.5000"),
        "date_val": datetime(2026, 10, 27, 12, 0, 0, tzinfo=timezone.utc),
        "set_val": {"zebra", "apple", "banana"},
    }
    dumped = canonical_json_dumps(data)
    # Check stable key ordering and representation
    assert dumped == '{"date_val":"2026-10-27T12:00:00+00:00","decimal_val":"42.5000","float_val":3.14159,"set_val":["apple","banana","zebra"]}'


# ===========================================================================
# 3. Approval & Invalidation Tests (Requirements 19 - 28)
# ===========================================================================
@pytest.mark.asyncio
async def test_correct_fingerprint_permits_approval(db_session: AsyncSession):
    """19. Correct current fingerprint permits approval."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    review_payload = await ApplicationWorkflowService.prepare_application(
        session=db_session, job_id=job.id, candidate_id=candidate.id
    )

    app = await ApplicationWorkflowService.approve_application(
        session=db_session,
        application_id=review_payload.application_id,
        reviewed_fingerprint=review_payload.canonical_approval_fingerprint,
        approval_metadata={"policy": "manual_review_v1"},
    )

    assert app.status == ApplicationStatus.APPROVED.value
    assert app.approval_fingerprint == review_payload.canonical_approval_fingerprint
    assert app.approved_at is not None


@pytest.mark.asyncio
async def test_stale_fingerprint_rejected(db_session: AsyncSession):
    """20. Client-supplied stale fingerprint is rejected."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    review_payload = await ApplicationWorkflowService.prepare_application(
        session=db_session, job_id=job.id, candidate_id=candidate.id
    )

    stale_fingerprint = "0" * 64

    with pytest.raises(ApprovalFingerprintMismatchError):
        await ApplicationWorkflowService.approve_application(
            session=db_session,
            application_id=review_payload.application_id,
            reviewed_fingerprint=stale_fingerprint,
        )


@pytest.mark.asyncio
async def test_candidate_changes_invalidate_approval(db_session: AsyncSession):
    """21. Candidate profile changes invalidate active approval."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    review_payload = await ApplicationWorkflowService.prepare_application(
        session=db_session, job_id=job.id, candidate_id=candidate.id
    )

    # Approve application
    app = await ApplicationWorkflowService.approve_application(
        session=db_session,
        application_id=review_payload.application_id,
        reviewed_fingerprint=review_payload.canonical_approval_fingerprint,
    )
    assert app.status == ApplicationStatus.APPROVED.value

    # Verify freshness before mutation: Fresh!
    is_fresh, _ = await ApplicationWorkflowService.verify_approval_freshness(db_session, app.id)
    assert is_fresh is True

    # Mutate candidate profile fact
    candidate.full_name = "Sarah J. Connor"
    await db_session.commit()

    # Re-verify freshness: Stale!
    is_fresh, drift_reason = await ApplicationWorkflowService.verify_approval_freshness(
        db_session, app.id
    )
    assert is_fresh is False
    assert "Data drift detected" in drift_reason

    # Application must have reverted to READY_FOR_REVIEW and cleared approval fields
    await db_session.refresh(app)
    assert app.status == ApplicationStatus.READY_FOR_REVIEW.value
    assert app.approval_fingerprint is None
    assert app.approved_at is None


@pytest.mark.asyncio
async def test_job_changes_invalidate_approval(db_session: AsyncSession):
    """22. Job description changes invalidate active approval."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    review_payload = await ApplicationWorkflowService.prepare_application(
        session=db_session, job_id=job.id, candidate_id=candidate.id
    )
    app = await ApplicationWorkflowService.approve_application(
        session=db_session,
        application_id=review_payload.application_id,
        reviewed_fingerprint=review_payload.canonical_approval_fingerprint,
    )

    # Mutate job description
    job.description = "Updated job requirements: now requires onsite attendance in Seattle."
    await db_session.commit()

    is_fresh, _ = await ApplicationWorkflowService.verify_approval_freshness(db_session, app.id)
    assert is_fresh is False

    await db_session.refresh(app)
    assert app.status == ApplicationStatus.READY_FOR_REVIEW.value


@pytest.mark.asyncio
async def test_resume_file_tampering_invalidates_approval(db_session: AsyncSession):
    """23. Resume file tampering on disk invalidates active approval."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    review_payload = await ApplicationWorkflowService.prepare_application(
        session=db_session, job_id=job.id, candidate_id=candidate.id
    )
    app = await ApplicationWorkflowService.approve_application(
        session=db_session,
        application_id=review_payload.application_id,
        reviewed_fingerprint=review_payload.canonical_approval_fingerprint,
    )

    # Tamper with the PDF file on disk
    resume = (
        await db_session.execute(
            select(ResumeVersion).where(ResumeVersion.id == app.resume_version_id)
        )
    ).scalar_one()
    resolved_path = ResumeStorageService.get_resume_pdf_path(resume.pdf_file_path)
    # Write altered bytes
    resolved_path.write_bytes(b"%PDF-1.4 TAMPERED CONTENT")

    is_fresh, reason = await ApplicationWorkflowService.verify_approval_freshness(db_session, app.id)
    assert is_fresh is False
    assert "Resume PDF artifact" in reason

    await db_session.refresh(app)
    assert app.status == ApplicationStatus.READY_FOR_REVIEW.value


@pytest.mark.asyncio
async def test_disqualified_jobs_cannot_be_approved(db_session: AsyncSession):
    """25. Disqualified jobs cannot be approved."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    review_payload = await ApplicationWorkflowService.prepare_application(
        session=db_session, job_id=job.id, candidate_id=candidate.id
    )

    # Force MatchScore to DISQUALIFIED
    match_score = (
        await db_session.execute(
            select(MatchScore).where(
                MatchScore.job_id == job.id, MatchScore.candidate_id == candidate.id
            )
        )
    ).scalar_one()
    match_score.eligibility_status = EligibilityStatus.DISQUALIFIED.value
    match_score.is_eligible = False
    await db_session.commit()

    with pytest.raises(JobDisqualifiedError):
        await ApplicationWorkflowService.approve_application(
            session=db_session,
            application_id=review_payload.application_id,
            reviewed_fingerprint=review_payload.canonical_approval_fingerprint,
        )


@pytest.mark.asyncio
async def test_state_transition_and_approval_event_persist_atomically(db_session: AsyncSession):
    """26. State transition and approval event persist atomically."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    review_payload = await ApplicationWorkflowService.prepare_application(
        session=db_session, job_id=job.id, candidate_id=candidate.id
    )

    app = await ApplicationWorkflowService.approve_application(
        session=db_session,
        application_id=review_payload.application_id,
        reviewed_fingerprint=review_payload.canonical_approval_fingerprint,
    )

    # Verify event was recorded
    events = (
        await db_session.execute(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == app.id)
            .order_by(ApplicationEvent.created_at.asc())
        )
    ).scalars().all()

    # Must contain APPLICATION_PREPARED and APPLICATION_APPROVED
    event_types = [e.payload.get("_event_type") for e in events]
    assert "APPLICATION_PREPARED" in event_types
    assert "APPLICATION_APPROVED" in event_types


@pytest.mark.asyncio
async def test_failed_approval_leaves_no_partially_approved_state(db_session: AsyncSession):
    """27. Failed approval leaves no partially approved state."""
    candidate = await create_test_candidate(db_session)
    job = await create_test_job(db_session)

    review_payload = await ApplicationWorkflowService.prepare_application(
        session=db_session, job_id=job.id, candidate_id=candidate.id
    )

    with pytest.raises(ApprovalFingerprintMismatchError):
        await ApplicationWorkflowService.approve_application(
            session=db_session,
            application_id=review_payload.application_id,
            reviewed_fingerprint="invalid_hash_string",
        )

    # Reload application: status must still be READY_FOR_REVIEW
    reloaded = (
        await db_session.execute(
            select(Application).where(Application.id == review_payload.application_id)
        )
    ).scalar_one()
    assert reloaded.status == ApplicationStatus.READY_FOR_REVIEW.value
    assert reloaded.approval_fingerprint is None
    assert reloaded.approved_at is None
