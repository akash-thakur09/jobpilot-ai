import pytest
from backend.app.services.relevance_engine import RelevanceEngine, RelevanceResult
from backend.app.models.enums import RelevanceClassification
from backend.app.schemas.candidate import JobSearchPreferences


def test_relevance_engine_high_relevance_fullstack_ai():
    prefs = JobSearchPreferences(
        target_roles=["Full Stack Engineer", "AI Engineer"],
        must_have_skills=["Python", "FastAPI", "React", "TypeScript"],
        preferred_skills=["Docker", "PostgreSQL"],
        ai_focus_skills=["RAG", "LLM", "Agentic AI"],
        preferred_locations=["Remote", "Bengaluru"],
        allow_remote=True,
    )

    result = RelevanceEngine.evaluate_job(
        job_title="Senior Full Stack Engineer - Generative AI & Agents",
        job_description="We are seeking a Full Stack Engineer experienced in Python, FastAPI, React, and TypeScript. You will build Agentic AI workflows using LLMs, RAG architectures, and PostgreSQL. Docker experience is a plus. Fully remote role.",
        job_location="Remote",
        remote_allowed=True,
        job_work_mode="Full-time",
        preferences=prefs,
    )

    assert result.classification == RelevanceClassification.HIGHLY_RELEVANT
    assert result.score >= 75.0
    assert "Full Stack Engineer" in result.matched_roles
    assert "Python" in result.matched_skills
    assert "React" in result.matched_skills
    assert "RAG" in result.matched_skills or "LLM" in result.matched_skills
    assert any("Remote" in r or "remote" in r for r in result.reasons)
    assert result.component_scores["title_score"] == 40.0
    assert result.component_scores["penalty"] == 0.0


def test_relevance_engine_non_technical_penalty():
    prefs = JobSearchPreferences(
        target_roles=["Full Stack Engineer", "Software Engineer"],
        must_have_skills=["Python", "React"],
        preferred_locations=["Remote"],
    )

    # Legal Counsel role
    result_legal = RelevanceEngine.evaluate_job(
        job_title="Senior Corporate Legal Counsel",
        job_description="Handling commercial contracts, regulatory compliance, and employment law matters.",
        job_location="Remote",
        remote_allowed=True,
        preferences=prefs,
    )
    assert result_legal.classification == RelevanceClassification.LOW_RELEVANCE
    assert result_legal.score < 45.0
    assert result_legal.component_scores["penalty"] > 0
    assert any("Non-technical role detected" in r for r in result_legal.reasons)

    # Talent Acquisition role
    result_hr = RelevanceEngine.evaluate_job(
        job_title="Talent Acquisition Partner - Technical Recruiting",
        job_description="Recruiting engineering talent, managing candidate pipelines.",
        job_location="Remote",
        remote_allowed=True,
        preferences=prefs,
    )
    assert result_hr.classification == RelevanceClassification.LOW_RELEVANCE
    assert result_hr.score < 45.0


def test_relevance_engine_potentially_relevant():
    prefs = JobSearchPreferences(
        target_roles=["Full Stack Engineer"],
        must_have_skills=["Python", "React", "TypeScript", "FastAPI"],
        preferred_skills=["Docker", "PostgreSQL"],
        ai_focus_skills=["LLM", "RAG"],
        preferred_locations=["Bengaluru"],
        allow_remote=False,
    )

    # General developer with some overlapping keywords but not exact target role and partial skills
    result = RelevanceEngine.evaluate_job(
        job_title="Software Developer",
        job_description="Developing web services using Python, Docker, and MySQL.",
        job_location="Bengaluru",
        remote_allowed=False,
        preferences=prefs,
    )

    assert result.classification in (
        RelevanceClassification.POTENTIALLY_RELEVANT,
        RelevanceClassification.HIGHLY_RELEVANT,
    )
    assert result.score >= 45.0
    assert "Python" in result.matched_skills


def test_relevance_engine_location_mismatch_penalty():
    prefs = JobSearchPreferences(
        target_roles=["Full Stack Engineer"],
        must_have_skills=["Python"],
        preferred_locations=["Bengaluru", "Pune"],
        allow_remote=False,
    )

    result = RelevanceEngine.evaluate_job(
        job_title="Full Stack Engineer",
        job_description="Building Python applications.",
        job_location="London, UK",
        remote_allowed=False,
        preferences=prefs,
    )

    # Title matches (40) + skills partial + location is 0
    assert result.component_scores["location_score"] == 0.0
    assert any("does not match preferred locations" in r for r in result.reasons)


def test_relevance_result_to_dict():
    result = RelevanceResult(
        score=82.5,
        classification=RelevanceClassification.HIGHLY_RELEVANT,
        matched_roles=["Full Stack Engineer"],
        matched_skills=["Python", "React"],
        missing_priority_skills=["TypeScript"],
        reasons=["Direct match for target role"],
        component_scores={"title_score": 40.0, "skills_score": 25.0},
    )

    d = result.to_dict()
    assert d["relevance_score"] == 82.5
    assert d["relevance_classification"] == "HIGHLY_RELEVANT"
    assert "Full Stack Engineer" in d["matched_roles"]
    assert "TypeScript" in d["missing_priority_skills"]

