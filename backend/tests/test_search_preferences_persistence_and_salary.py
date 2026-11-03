import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.main import app
from backend.app.db.session import get_db
from backend.app.models.candidate import CandidateProfile
from backend.app.models.job import Job
from backend.app.models.enums import RemoteType, RelevanceClassification
from backend.app.services.relevance_engine import RelevanceEngine
from backend.app.services.salary_service import (
    normalize_job_salary_to_lpa,
    evaluate_salary_compatibility,
)
from backend.app.schemas.candidate import JobSearchPreferences


@pytest.mark.asyncio
async def test_full_search_preferences_persistence_lifecycle(db_session: AsyncSession):
    """
    Validates complete canonical contract persistence:
    Save -> API -> Database -> API Response -> GET Profile -> GET Preferences.
    Verifies experience (including 0), AI focus skills, and INR LPA package.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create initial candidate profile
        profile = CandidateProfile(
            full_name="Deepak AI Engineer",
            email="deepak.ai@example.com",
            location="Bengaluru, India",
            work_authorization="Citizen of India",
            summary="Full Stack Developer transitioning to AI/GenAI and Agentic workflows",
            years_of_experience=4.0,
            remote_preference="REMOTE",
        )
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)

        # 1. Save all canonical search preference fields
        canonical_payload = {
            "target_roles": ["Full Stack Engineer", "AI Engineer", "GenAI Developer"],
            "role_keywords": ["python", "rag", "langgraph", "fastapi"],
            "must_have_skills": ["Python", "FastAPI", "React", "TypeScript", "SQL"],
            "preferred_skills": ["Docker", "PostgreSQL", "Redis", "AWS"],
            "ai_genai_focus_skills": [
                "LLM",
                "RAG",
                "Agentic AI",
                "LangChain",
                "LangGraph",
                "Vector Database",
                "Embeddings",
            ],
            "remote_preference": "REMOTE",
            "allow_remote_opportunities": True,
            "target_min_experience_years": 2.0,
            "target_max_experience_years": 5.0,
            "preferred_locations": ["Bengaluru", "Hyderabad", "Remote"],
            "minimum_package_lpa": 12.5,
            "preferred_companies": ["Razorpay", "Swiggy", "Microsoft"],
            "excluded_companies": ["BadCorp"],
        }

        put_res = await client.put("/api/v1/profile/preferences", json=canonical_payload)
        assert put_res.status_code == 200, put_res.text
        saved = put_res.json()

        # 2. Verify all fields in PUT response
        assert saved["target_roles"] == canonical_payload["target_roles"]
        assert saved["role_keywords"] == canonical_payload["role_keywords"]
        assert saved["must_have_skills"] == canonical_payload["must_have_skills"]
        assert saved["preferred_skills"] == canonical_payload["preferred_skills"]
        assert saved["ai_genai_focus_skills"] == canonical_payload["ai_genai_focus_skills"]
        assert saved["ai_focus_skills"] == canonical_payload["ai_genai_focus_skills"]
        assert saved["target_min_experience_years"] == 2.0
        assert saved["target_max_experience_years"] == 5.0
        assert saved["preferred_min_years"] == 2.0
        assert saved["preferred_max_years"] == 5.0
        assert saved["minimum_package_lpa"] == 12.5
        assert saved["min_salary_lpa"] == 12.5
        assert saved["allow_remote_opportunities"] is True
        assert saved["preferred_locations"] == ["Bengaluru", "Hyderabad", "Remote"]

        # 3. Retrieve via GET /profile/preferences
        get_prefs_res = await client.get("/api/v1/profile/preferences")
        assert get_prefs_res.status_code == 200
        reloaded_prefs = get_prefs_res.json()
        assert reloaded_prefs["target_min_experience_years"] == 2.0
        assert reloaded_prefs["target_max_experience_years"] == 5.0
        assert reloaded_prefs["ai_genai_focus_skills"] == canonical_payload["ai_genai_focus_skills"]
        assert reloaded_prefs["minimum_package_lpa"] == 12.5

        # 4. Retrieve via GET /profile and verify search_preferences matches
        get_profile_res = await client.get("/api/v1/profile")
        assert get_profile_res.status_code == 200
        prof_data = get_profile_res.json()
        prof_prefs = prof_data["search_preferences"]
        assert prof_prefs["target_min_experience_years"] == 2.0
        assert prof_prefs["target_max_experience_years"] == 5.0
        assert prof_prefs["ai_genai_focus_skills"] == canonical_payload["ai_genai_focus_skills"]
        assert prof_prefs["minimum_package_lpa"] == 12.5
        assert prof_data["target_package_min_lpa"] == 12.5


@pytest.mark.asyncio
async def test_zero_experience_and_partial_updates(db_session: AsyncSession):
    """
    Verifies that target_min_experience_years=0 is preserved (not treated as falsy/missing)
    and that partial updates do not wipe out other fields.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        profile = CandidateProfile(
            full_name="Junior Dev",
            email="junior.dev@example.com",
            location="Pune, India",
            work_authorization="Citizen of India",
            summary="Junior Full Stack AI enthusiast",
            years_of_experience=0.5,
        )
        db_session.add(profile)
        await db_session.commit()

        # Set 0 experience and initial skills
        payload_1 = {
            "target_min_experience_years": 0.0,
            "target_max_experience_years": 2.0,
            "ai_genai_focus_skills": ["RAG", "LLM"],
            "minimum_package_lpa": 6.0,
            "must_have_skills": ["Python", "FastAPI"],
        }
        res1 = await client.put("/api/v1/profile/preferences", json=payload_1)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["target_min_experience_years"] == 0.0
        assert data1["preferred_min_years"] == 0.0
        assert data1["minimum_package_lpa"] == 6.0

        # Partial update: update ONLY package LPA and add an AI skill
        partial_payload = {
            "minimum_package_lpa": 8.0,
            "ai_genai_focus_skills": ["RAG", "LLM", "Agentic AI"],
        }
        res2 = await client.put("/api/v1/profile/preferences", json=partial_payload)
        assert res2.status_code == 200
        data2 = res2.json()

        # Experience must still be 0.0 and 2.0 (not wiped)
        assert data2["target_min_experience_years"] == 0.0
        assert data2["target_max_experience_years"] == 2.0
        # must_have_skills must still be present
        assert data2["must_have_skills"] == ["Python", "FastAPI"]
        # AI skills and package LPA updated
        assert data2["minimum_package_lpa"] == 8.0
        assert data2["ai_genai_focus_skills"] == ["RAG", "LLM", "Agentic AI"]


@pytest.mark.asyncio
async def test_legacy_preference_data_backward_compatibility(db_session: AsyncSession):
    """
    Verifies that old stored preferences containing legacy keys (e.g. min_salary in USD,
    preferred_min_years, required_skills, ai_focus_skills) load cleanly without crashes.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create profile with raw legacy search_preferences dict
        legacy_prefs = {
            "target_titles": ["Full Stack Engineer"],
            "required_skills": ["Python", "React"],
            "preferred_skills": ["Docker"],
            "ai_focus_skills": ["LLM", "RAG"],
            "preferred_min_years": 3.0,
            "preferred_max_years": 7.0,
            "min_salary": 140000.0,  # Legacy USD value
            "allow_remote": True,
        }
        profile = CandidateProfile(
            full_name="Legacy User",
            email="legacy.user@example.com",
            location="Remote, India",
            work_authorization="Citizen of India",
            summary="Experienced Engineer with legacy profile data",
            target_salary_min=140000.0,
            search_preferences=legacy_prefs,
        )
        db_session.add(profile)
        await db_session.commit()

        # Retrieve preferences via API
        res = await client.get("/api/v1/profile/preferences")
        assert res.status_code == 200
        data = res.json()

        # Aliases must resolve both ways
        assert data["target_roles"] == ["Full Stack Engineer"]
        assert data["target_titles"] == ["Full Stack Engineer"]
        assert data["must_have_skills"] == ["Python", "React"]
        assert data["required_skills"] == ["Python", "React"]
        assert data["ai_genai_focus_skills"] == ["LLM", "RAG"]
        assert data["ai_focus_skills"] == ["LLM", "RAG"]
        assert data["target_min_experience_years"] == 3.0
        assert data["target_max_experience_years"] == 7.0
        assert data["allow_remote_opportunities"] is True
        # Legacy USD salary preserved in legacy field, not falsely turned into 140,000 LPA
        assert data["legacy_min_salary_usd"] == 140000.0
        assert data["minimum_package_lpa"] is None


def test_salary_normalization_and_compatibility():
    """
    Tests INR LPA normalization and safe currency comparison rules.
    """
    # 1. INR Normalization
    assert normalize_job_salary_to_lpa(1200000.0, "INR") == 12.0
    assert normalize_job_salary_to_lpa(1850000.0, "INR") == 18.5
    assert normalize_job_salary_to_lpa(10.0, "INR") == 10.0
    # Monthly salary 75,000 INR -> 9.0 LPA
    assert normalize_job_salary_to_lpa(75000.0, "INR") == 9.0

    # 2. Foreign currency should return None to avoid false comparison
    assert normalize_job_salary_to_lpa(150000.0, "USD") is None
    assert normalize_job_salary_to_lpa(85000.0, "EUR") is None

    # 3. Missing salary -> UNDISCLOSED, neutral (never rejects)
    undisclosed = evaluate_salary_compatibility(
        job_salary_min=None,
        job_salary_max=None,
        job_currency="INR",
        candidate_min_lpa=10.0,
    )
    assert undisclosed["status"] == "UNDISCLOSED"
    assert undisclosed["is_compatible"] is True
    assert undisclosed["score"] == 75.0

    # 4. Foreign currency vs INR LPA target -> FOREIGN_CURRENCY, neutral (never false mismatch)
    foreign = evaluate_salary_compatibility(
        job_salary_min=130000.0,
        job_salary_max=160000.0,
        job_currency="USD",
        candidate_min_lpa=12.0,
    )
    assert foreign["status"] == "FOREIGN_CURRENCY"
    assert foreign["is_compatible"] is True
    assert foreign["score"] == 75.0

    # 5. INR Range satisfies target
    meets = evaluate_salary_compatibility(
        job_salary_min=1000000.0,  # 10 LPA
        job_salary_max=1600000.0,  # 16 LPA
        job_currency="INR",
        candidate_min_lpa=12.0,
    )
    assert meets["status"] == "MEETS_TARGET"
    assert meets["satisfies_target"] is True
    assert meets["score"] == 95.0

    # 6. INR Range below target
    below = evaluate_salary_compatibility(
        job_salary_min=500000.0,  # 5 LPA
        job_salary_max=800000.0,  # 8 LPA
        job_currency="INR",
        candidate_min_lpa=12.0,
    )
    assert below["status"] == "BELOW_TARGET"
    assert below["satisfies_target"] is False
    assert below["is_compatible"] is False
    assert below["score"] < 70.0


def test_relevance_engine_with_lpa_and_missing_salary():
    """
    Verifies that RelevanceEngine handles minimum_package_lpa safely:
    - Missing salary does not downgrade a relevant job to LOW_RELEVANCE.
    - Foreign currency does not cause false negative.
    - Meeting LPA package contributes positively.
    """
    prefs = JobSearchPreferences(
        target_roles=["AI Engineer", "Full Stack Developer"],
        must_have_skills=["Python", "React"],
        ai_genai_focus_skills=["LLM", "RAG"],
        target_min_experience_years=2.0,
        target_max_experience_years=5.0,
        minimum_package_lpa=10.0,
        preferred_locations=["Bengaluru", "Remote"],
    )

    # Job A: Relevant technical job with missing salary -> must still be HIGHLY_RELEVANT
    res_undisclosed = RelevanceEngine.evaluate_job(
        job_title="AI Engineer",
        job_description="Building cutting-edge Python, React, LLM, and RAG systems.",
        job_location="Bengaluru",
        remote_allowed=True,
        job_experience_min=3.0,
        job_experience_max=5.0,
        preferences=prefs,
        job_salary_min=None,
        job_salary_max=None,
        job_currency="INR",
    )
    assert res_undisclosed.classification == RelevanceClassification.HIGHLY_RELEVANT
    assert res_undisclosed.score >= 80.0

    # Job B: Disclosed INR package meeting target (14 LPA) -> bonus signal
    res_meets = RelevanceEngine.evaluate_job(
        job_title="AI Engineer",
        job_description="Building cutting-edge Python, React, LLM, and RAG systems.",
        job_location="Bengaluru",
        remote_allowed=True,
        job_experience_min=3.0,
        job_experience_max=5.0,
        preferences=prefs,
        job_salary_min=1200000.0,
        job_salary_max=1600000.0,
        job_currency="INR",
    )
    assert res_meets.classification == RelevanceClassification.HIGHLY_RELEVANT
    assert any("satisfies target package" in r.lower() or "meets minimum target" in r.lower() for r in res_meets.reasons)

