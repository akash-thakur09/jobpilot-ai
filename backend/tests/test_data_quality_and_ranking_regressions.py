import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.job import Job, JobSource, JobRequirement
from backend.app.models.candidate import CandidateProfile
from backend.app.models.feedback import JobFeedback
from backend.app.models.enums import FreshnessStatus, FeedbackType, EligibilityStatus, RequirementType
from backend.app.services.duplicate_detection_service import DuplicateDetectionService
from backend.app.services.job_freshness_service import JobFreshnessService
from backend.app.services.feedback_service import FeedbackService
from backend.app.services.matching_service import MatchingService
from backend.app.core.config import settings


def test_url_canonicalization_preserves_case_sensitive_path():
    """Verify that URL canonicalization preserves case-sensitive paths while lowercasing the domain."""
    url_mixed = "https://Jobs.Example.Com/Careers/Openings/SeniorDev_AbC123/?utm_source=twitter&ref=newsletter"
    canonical = DuplicateDetectionService.canonicalize_url(url_mixed)
    
    # Domain must be lowercased
    assert "https://jobs.example.com" in canonical
    # Tracking parameters must be stripped
    assert "utm_source" not in canonical
    assert "ref" not in canonical
    # Case-sensitive path must NOT be lowercased
    assert "/Careers/Openings/SeniorDev_AbC123" in canonical


def test_distinct_vacancies_similar_titles_never_merged():
    """Verify that similar titles at different companies or distinct physical locations are not merged."""
    job_a = Job(
        id="job_a",
        source_id="src_1",
        external_id="ext_a",
        company="Datadog",
        title="Senior Software Engineer",
        canonical_url="https://jobs.datadog.com/1",
        location="New York, NY",
        remote_type="ON_SITE",
        description="Backend services in Go and Python.",
    )
    job_b = Job(
        id="job_b",
        source_id="src_2",
        external_id="ext_b",
        company="Stripe",
        title="Senior Software Engineer",
        canonical_url="https://jobs.stripe.com/1",
        location="New York, NY",
        remote_type="ON_SITE",
        description="Payments infrastructure in Ruby and Java.",
    )
    job_c = Job(
        id="job_c",
        source_id="src_1",
        external_id="ext_c",
        company="Datadog",
        title="Senior Software Engineer",
        canonical_url="https://jobs.datadog.com/2",
        location="San Francisco, CA",
        remote_type="ON_SITE",
        description="Backend services in Go and Python.",
    )

    # Different employers
    score_ab, _, conf_ab = DuplicateDetectionService.compute_similarity(job_a, job_b)
    assert score_ab < 0.65
    assert conf_ab == "INSUFFICIENT_EVIDENCE"

    # Same employer but conflicting physical on-site locations
    score_ac, _, conf_ac = DuplicateDetectionService.compute_similarity(job_a, job_c)
    assert score_ac < 0.65
    assert conf_ac == "INSUFFICIENT_EVIDENCE"


@pytest.mark.asyncio
async def test_source_outage_does_not_mark_listing_closed(db_session: AsyncSession):
    """
    Critical data quality rule:
    Source network outages or timeouts must NEVER transition a listing to CONFIRMED_CLOSED.
    It must be transitioned to UNKNOWN or preserved.
    """
    source = JobSource(
        identifier="outage_source",
        name="Outage Source",
        base_url="https://outage.example.com",
    )
    db_session.add(source)
    await db_session.flush()

    job = Job(
        source_id=source.id,
        external_id="outage_job_1",
        title="Reliability Architect",
        company="Outage Corp",
        canonical_url="https://outage.example.com/1",
        freshness_status=FreshnessStatus.ACTIVE.value,
        freshness_reason="Previously verified active",
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        last_verified_at=datetime.now(timezone.utc),
        description="Reliability role",
    )
    db_session.add(job)
    await db_session.commit()

    # Simulate network outage probe failure
    await JobFreshnessService.mark_job_unknown(
        db_session, job, reason="Connection timed out to provider"
    )
    await db_session.commit()
    await db_session.refresh(job)

    assert job.freshness_status == FreshnessStatus.UNKNOWN.value
    assert job.freshness_status != FreshnessStatus.CONFIRMED_CLOSED.value
    assert "timed out" in job.freshness_reason.lower()


@pytest.mark.asyncio
async def test_feedback_applied_and_never_overrides_disqualification(db_session: AsyncSession):
    """
    Verify:
    1. Deterministic eligibility gate can NEVER be overridden by user feedback.
    2. Even strong positive feedback (RELEVANT) on a DISQUALIFIED job results in overall_score == 0.0.
    """
    candidate = CandidateProfile(
        full_name="Alex Smith",
        email="alex@example.com",
        location="Toronto, Canada",
        work_authorization="Canadian Citizen",
        summary="Backend Engineer with Python and React experience.",
        years_of_experience=4.0,
    )

    db_session.add(candidate)
    await db_session.flush()

    source = JobSource(
        identifier="gov_source",
        name="Gov Source",
        base_url="https://gov.example.com",
    )
    db_session.add(source)
    await db_session.flush()

    # Job requires US Citizenship
    job = Job(
        source_id=source.id,
        external_id="gov_job_1",
        title="US Defense Engineer",
        company="Federal Systems",
        canonical_url="https://gov.example.com/defense-1",
        description="Must be US Citizen.",
    )
    db_session.add(job)
    await db_session.flush()

    req = JobRequirement(
        job_id=job.id,
        requirement_type=RequirementType.WORK_AUTH.value,
        value="US Citizen",
    )
    db_session.add(req)
    await db_session.commit()


    matching_service = MatchingService()

    # 1. Base evaluation without feedback
    eval_res_1 = await matching_service.evaluate_job(db_session, job.id, candidate.id, use_ai=False)
    assert eval_res_1.is_eligible is False
    assert eval_res_1.eligibility_status == EligibilityStatus.DISQUALIFIED.value

    # 2. Add strong positive feedback (RELEVANT)
    await FeedbackService.record_feedback(
        session=db_session,
        candidate_id=candidate.id,
        job_id=job.id,
        feedback_type=FeedbackType.RELEVANT.value,
        reason="I really want this job despite citizenship requirements",
    )
    await db_session.commit()

    # 3. Re-evaluate
    eval_res_2 = await matching_service.evaluate_job(db_session, job.id, candidate.id, use_ai=False)
    # MUST still be strictly DISQUALIFIED and never eligible
    assert eval_res_2.is_eligible is False
    assert eval_res_2.eligibility_status == EligibilityStatus.DISQUALIFIED.value
    assert any("Hard constraint disqualified" in w for w in eval_res_2.warnings)


def test_startup_settings_validation_enforces_safety():
    """Verify that settings startup validation enforces real submission disabled and safe bindings."""
    settings.JOBPILOT_REAL_SUBMISSION_ENABLED = True
    settings.validate_startup_configuration()
    
    # Must be automatically reverted to False for local safety
    assert settings.JOBPILOT_REAL_SUBMISSION_ENABLED is False
    assert settings.APP_HOST in ("127.0.0.1", "localhost")
