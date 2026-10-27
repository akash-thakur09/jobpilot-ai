import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.main import app
from backend.app.db.session import get_db
from backend.app.models.candidate import CandidateProfile, CandidateSkill
from backend.app.models.job import Job, JobSource
from backend.app.models.enums import RemoteType, EligibilityStatus
from backend.app.services.matching_service import MatchingService
from backend.app.matching.scoring import DeterministicScoringService


@pytest.mark.asyncio
async def test_search_preferences_api_and_separation_from_facts(db_session: AsyncSession):
    """
    Step 2: Tests validation, persistence, and strict separation of preferences from verified candidate facts.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Create candidate profile with 1 verified skill
        cand = CandidateProfile(
            full_name="Alice Architect",
            email="alice.arch@example.com",
            location="New York, NY",
            work_authorization="US Citizen",
            summary="Senior Python Engineer with Cloud experience",
            years_of_experience=6,
            target_titles=["Senior Python Engineer"],
            remote_preference="REMOTE",
        )
        db_session.add(cand)
        await db_session.commit()
        await db_session.refresh(cand)

        skill = CandidateSkill(
            candidate_id=cand.id,
            skill_name="Python",
            category="technical",
            years_experience=6.0,
            is_verified=True,
        )
        db_session.add(skill)
        await db_session.commit()

        # 2. Get initial search preferences (should reflect defaults and top-level profile fields)
        get_res = await client.get("/api/v1/profile/preferences")
        assert get_res.status_code == 200
        prefs = get_res.json()
        assert prefs["target_titles"] == ["Senior Python Engineer"]
        assert prefs["remote_preference"] == "REMOTE"

        # 3. Update search preferences with desired skills, role keywords, company preferences, and salary
        update_payload = {
            "target_titles": ["Staff Backend Engineer"],
            "role_keywords": ["FastAPI", "PostgreSQL", "Distributed"],
            "required_skills": ["Docker", "Kubernetes"],  # Desired in jobs, NOT verified facts of candidate!
            "preferred_skills": ["Rust", "GraphQL"],
            "preferred_companies": ["Acme Corp", "Stripe"],
            "excluded_companies": ["SpamCo"],
            "preferred_locations": ["Remote", "New York"],
            "remote_preference": "REMOTE",
            "min_salary": 160000.0,
        }
        put_res = await client.put("/api/v1/profile/preferences", json=update_payload)
        assert put_res.status_code == 200
        saved_prefs = put_res.json()
        assert saved_prefs["role_keywords"] == ["FastAPI", "PostgreSQL", "Distributed"]
        assert saved_prefs["preferred_companies"] == ["Acme Corp", "Stripe"]
        assert saved_prefs["min_salary"] == 160000.0

        # 4. Strict Fact Separation Verification:
        # The desired skills ("Docker", "Kubernetes", "Rust") must NEVER appear as candidate's verified skills!
        profile_res = await client.get("/api/v1/profile")
        assert profile_res.status_code == 200
        profile_data = profile_res.json()
        verified_skill_names = [s["skill_name"] for s in profile_data["skills"]]
        assert verified_skill_names == ["Python"], "Preferred skills must NOT be added to candidate's verified facts"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_preferences_influence_scoring_and_explanation(db_session: AsyncSession):
    """
    Tests that search preferences (role keywords, preferred company, excluded company, salary)
    influence scoring and generate explainable preference contributions.
    """
    cand = CandidateProfile(
        full_name="Bob Developer",
        email="bob.dev@example.com",
        location="San Francisco, CA",
        work_authorization="US Citizen",
        summary="Backend engineer skilled in Python",
        years_of_experience=5,
        search_preferences={
            "role_keywords": ["FastAPI", "High Throughput"],
            "preferred_companies": ["GoodCorp"],
            "excluded_companies": ["BadCorp"],
            "preferred_locations": ["San Francisco"],
            "min_salary": 150000.0,
        },
    )
    db_session.add(cand)
    await db_session.flush()

    skill = CandidateSkill(
        candidate_id=cand.id,
        skill_name="Python",
        category="technical",
        years_experience=5.0,
        is_verified=True,
    )
    db_session.add(skill)

    src = JobSource(identifier="test_src", name="Test Source", base_url="https://example.com")
    db_session.add(src)
    await db_session.commit()
    await db_session.refresh(src)

    # Job 1: At GoodCorp (preferred), has role keyword "FastAPI", disclosed salary >= min_salary
    job_good = Job(
        source_id=src.id,
        external_id="job_good_1",
        title="Senior Python Engineer",
        company="GoodCorp",
        canonical_url="https://example.com/job1",
        location="San Francisco, CA",
        remote_type=RemoteType.REMOTE.value,
        description="We need a Python developer experienced in FastAPI for our backend.",
        salary_min=160000.0,
        salary_max=180000.0,
    )
    db_session.add(job_good)

    # Job 2: At BadCorp (excluded), same role
    job_bad = Job(
        source_id=src.id,
        external_id="job_bad_1",
        title="Senior Python Engineer",
        company="BadCorp Technologies",
        canonical_url="https://example.com/job2",
        location="San Francisco, CA",
        remote_type=RemoteType.REMOTE.value,
        description="We need a Python developer experienced in FastAPI for our backend.",
        salary_min=160000.0,
        salary_max=180000.0,
    )
    db_session.add(job_bad)

    # Job 3: Undisclosed salary
    job_undisclosed = Job(
        source_id=src.id,
        external_id="job_undisclosed_1",
        title="Python Developer",
        company="NeutralCorp",
        canonical_url="https://example.com/job3",
        location="Remote",
        remote_type=RemoteType.REMOTE.value,
        description="General Python developer role.",
        salary_min=None,
        salary_max=None,
    )
    db_session.add(job_undisclosed)
    await db_session.commit()

    matching = MatchingService()

    # 1. Evaluate Job 1 (GoodCorp)
    eval_good = await matching.evaluate_job(session=db_session, job_id=job_good.id, candidate_id=cand.id, use_ai=False)
    assert eval_good.is_eligible is True
    breakdown_good = eval_good.scoring_breakdown
    assert "preference_contributions" in breakdown_good
    prefs_good = breakdown_good["preference_contributions"]
    assert prefs_good.get("matched_preferred_company") is True
    assert "FastAPI" in prefs_good.get("matched_role_keywords", [])
    assert prefs_good.get("salary_satisfies_target") is True
    assert "GoodCorp" in eval_good.explanation
    assert "Preference Alignment" in eval_good.explanation

    # 2. Evaluate Job 2 (BadCorp - Excluded)
    eval_bad = await matching.evaluate_job(session=db_session, job_id=job_bad.id, candidate_id=cand.id, use_ai=False)
    assert eval_bad.is_eligible is True  # Preferences do not alter deterministic legal eligibility
    prefs_bad = eval_bad.scoring_breakdown["preference_contributions"]
    assert prefs_bad.get("is_excluded_company") is True
    # Overall score should be lower than good job due to excluded company penalty
    assert eval_bad.overall_score < eval_good.overall_score

    # 3. Evaluate Job 3 (Undisclosed salary - must not assume satisfied)
    eval_undisclosed = await matching.evaluate_job(session=db_session, job_id=job_undisclosed.id, candidate_id=cand.id, use_ai=False)
    prefs_undisclosed = eval_undisclosed.scoring_breakdown["preference_contributions"]
    assert prefs_undisclosed.get("salary_satisfies_target") is None, "Missing salary must not be assumed to satisfy target"


@pytest.mark.asyncio
async def test_preferences_cannot_override_disqualification(db_session: AsyncSession):
    """
    Tests that a job with high preference alignment CANNOT override hard eligibility disqualification
    (e.g. candidate requires visa sponsorship but job forbids it).
    """
    cand = CandidateProfile(
        full_name="Dave Engineer",
        email="dave@example.com",
        location="London, UK",
        work_authorization="Requires Sponsorship",
        summary="Backend dev",
        years_of_experience=4,
        search_preferences={
            "preferred_companies": ["DreamCompany"],
            "role_keywords": ["Python"],
        },
    )
    db_session.add(cand)
    await db_session.flush()

    src = JobSource(identifier="test_src_2", name="Test Source 2", base_url="https://example.com")
    db_session.add(src)
    await db_session.commit()

    # Job requires US Citizen only -> hard disqualification
    disqualified_job = Job(
        source_id=src.id,
        external_id="disq_job_1",
        title="Python Engineer",
        company="DreamCompany",  # Matches preferred company!
        canonical_url="https://example.com/disq",
        location="Remote",
        remote_type=RemoteType.REMOTE.value,
        description="US Citizenship required. No visa sponsorship provided. Python role.",
    )
    db_session.add(disqualified_job)
    await db_session.commit()

    matching = MatchingService()
    eval_res = await matching.evaluate_job(session=db_session, job_id=disqualified_job.id, candidate_id=cand.id, use_ai=False)

    assert eval_res.is_eligible is False
    assert eval_res.eligibility_status == EligibilityStatus.DISQUALIFIED.value
    assert "DISQUALIFIED" in eval_res.explanation
