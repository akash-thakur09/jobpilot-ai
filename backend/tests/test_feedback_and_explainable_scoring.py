import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.candidate import CandidateProfile, CandidateSkill
from backend.app.models.job import Job, JobSource
from backend.app.models.enums import FeedbackType, EligibilityStatus, FreshnessStatus
from backend.app.services.feedback_service import FeedbackService
from backend.app.services.matching_service import MatchingService
from backend.app.matching.scoring import DeterministicScoringService
from backend.app.matching.schemas import ScoringWeights


@pytest.mark.asyncio
async def test_feedback_idempotent_upsert_and_deletion(db_session: AsyncSession):
    src = JobSource(identifier="src-fb", name="Feedback Source", base_url="https://fb.example.com")
    cand = CandidateProfile(
        full_name="Feedback Tester",
        email="fb.tester@example.com",
        location="Remote",
        work_authorization="US_CITIZEN",
        summary="Software Developer",
    )
    db_session.add_all([src, cand])
    await db_session.flush()

    job = Job(
        source_id=src.id,
        external_id="job-fb-01",
        title="Python Developer",
        company="TechCorp",
        canonical_url="https://tech.example.com/jobs/1",
        description="FastAPI role.",
    )
    db_session.add(job)
    await db_session.commit()

    # 1. Record new feedback
    fb1 = await FeedbackService.record_feedback(
        db_session, cand.id, job.id, FeedbackType.RELEVANT.value, reason="Matches my tech stack"
    )
    assert fb1.feedback_type == FeedbackType.RELEVANT.value
    assert fb1.reason == "Matches my tech stack"

    # 2. Idempotent update (upsert)
    fb2 = await FeedbackService.record_feedback(
        db_session, cand.id, job.id, FeedbackType.NOT_INTERESTED.value, reason="Too far away"
    )
    assert fb2.id == fb1.id
    assert fb2.feedback_type == FeedbackType.NOT_INTERESTED.value
    assert fb2.reason == "Too far away"

    # 3. Retrieve
    retrieved = await FeedbackService.get_feedback(db_session, cand.id, job.id)
    assert retrieved is not None
    assert retrieved.feedback_type == FeedbackType.NOT_INTERESTED.value

    # 4. Delete
    deleted = await FeedbackService.delete_feedback(db_session, cand.id, job.id)
    assert deleted is True

    # 5. Verify deleted
    post_delete = await FeedbackService.get_feedback(db_session, cand.id, job.id)
    assert post_delete is None


@pytest.mark.asyncio
async def test_feedback_effects_on_scoring(db_session: AsyncSession):
    cand = CandidateProfile(
        id="cand-score-test",
        full_name="Scoring Tester",
        email="scoring@example.com",
        location="San Francisco, CA",
        work_authorization="US_CITIZEN",
        years_of_experience=5.0,
        target_titles=["Backend Engineer"],
        summary="Backend developer",
    )
    cand.skills = [
        CandidateSkill(skill_name="Python", is_verified=True, years_experience=5.0),
        CandidateSkill(skill_name="PostgreSQL", is_verified=True, years_experience=4.0),
    ]
    cand.experiences = []
    cand.projects = []
    cand.educations = []

    job = Job(
        id="job-score-test",
        title="Backend Engineer",
        company="Acme Corp",
        canonical_url="https://acme.example.com/jobs/1",
        location="Remote",
        remote_type="REMOTE",
        description="Backend Engineer skilled in Python and PostgreSQL.",
        freshness_status=FreshnessStatus.ACTIVE.value,
    )

    # Baseline score with no feedback
    b_base, _, _, _, _ = DeterministicScoringService.calculate_score(cand, job)
    assert b_base.scoring_policy_version == "1.1.0"
    base_score = b_base.final_score

    # Score with positive RELEVANT feedback
    from backend.app.models.feedback import JobFeedback
    fb_pos = JobFeedback(
        candidate_id=cand.id,
        job_id=job.id,
        feedback_type=FeedbackType.RELEVANT.value,
    )
    b_pos, _, _, _, _ = DeterministicScoringService.calculate_score(cand, job, feedback=fb_pos)
    assert b_pos.final_score == min(100.0, round(base_score + 10.0, 2))
    assert b_pos.feedback_adjustment == 10.0
    assert any("relevant" in c.lower() for c in b_pos.positive_contributions)

    # Score with negative NOT_RELEVANT feedback (-25 points)
    fb_neg = JobFeedback(
        candidate_id=cand.id,
        job_id=job.id,
        feedback_type=FeedbackType.NOT_RELEVANT.value,
    )
    b_neg, _, _, _, _ = DeterministicScoringService.calculate_score(cand, job, feedback=fb_neg)
    assert b_neg.final_score == max(0.0, round(base_score - 25.0, 2))
    assert b_neg.feedback_adjustment == -25.0
    assert any("not relevant" in c.lower().replace("_", " ") for c in b_neg.negative_contributions)


@pytest.mark.asyncio
async def test_deterministic_eligibility_gate_never_overridden(db_session: AsyncSession):
    src = JobSource(identifier="src-gate", name="Gate Source", base_url="https://gate.example.com")
    cand = CandidateProfile(
        full_name="Visa Holder",
        email="visaholder@example.com",
        location="San Francisco, CA",
        work_authorization="H1B_VISA",  # Ineligible for US_CITIZEN_ONLY
        summary="Senior engineer",
    )
    cand.skills = [
        CandidateSkill(skill_name="Python", is_verified=True, years_experience=8.0),
    ]
    cand.experiences = []
    cand.projects = []
    cand.educations = []
    db_session.add_all([src, cand])
    await db_session.flush()

    job = Job(
        source_id=src.id,
        external_id="job-defense-01",
        title="Python Security Engineer - US Citizenship Required",
        company="DefenseTech",
        canonical_url="https://defense.example.com/jobs/1",
        description="Must be a US Citizen. Security clearance required.",
        location="Remote",
        remote_type="REMOTE",
    )
    db_session.add(job)
    await db_session.commit()

    # Even with RELEVANT positive user feedback recorded:
    await FeedbackService.record_feedback(
        db_session, cand.id, job.id, FeedbackType.RELEVANT.value
    )

    matching_service = MatchingService()
    match_record = await matching_service.evaluate_job(db_session, job.id, candidate_id=cand.id, use_ai=False)

    # Hard constraint gate MUST remain DISQUALIFIED
    assert match_record.is_eligible is False
    assert match_record.eligibility_status == EligibilityStatus.DISQUALIFIED.value
    assert match_record.scoring_policy_version == "1.1.0"
    assert any("Hard constraint disqualified" in w for w in match_record.warnings)
