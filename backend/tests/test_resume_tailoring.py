import hashlib
import io
import pytest
from httpx import AsyncClient
from backend.app.models.candidate import CandidateProfile, CandidateSkill, CandidateExperience, CandidateEducation, CandidateProject
from backend.app.resumes.schemas import TailoredResumeContent, TailoredExperience, TailoredEducation, TailoredProject
from backend.app.resumes.fact_validator import ResumeFactValidator
from backend.app.resumes.pdf_renderer import ResumePdfRenderer
from backend.app.resumes.pdf_verifier import ResumePdfVerifier


# ---------------------------------------------------------------------------
# Unit Tests: Factual Consistency Validator
# ---------------------------------------------------------------------------
def test_factual_validator_rejects_unverified_skill():
    candidate = CandidateProfile(
        full_name="Alice Wang",
        email="alice@example.com",
        location="Seattle, WA",
        work_authorization="US Citizen",
        summary="Senior Cloud Engineer",
        skills=[
            CandidateSkill(skill_name="Python", category="technical", years_experience=5.0, is_verified=True),
            CandidateSkill(skill_name="Docker", category="technical", years_experience=3.0, is_verified=True),
            CandidateSkill(skill_name="Rust", category="technical", years_experience=1.0, is_verified=False),  # Not verified!
        ],
    )

    # Content contains "Rust" which is unverified, and "Kubernetes" which is completely unlisted
    content = TailoredResumeContent(
        full_name="Alice Wang",
        email="alice@example.com",
        location="Seattle, WA",
        summary="Senior Cloud Engineer with deep expertise.",
        skills_by_category={"Languages": ["Python", "Rust", "Kubernetes"]},
    )

    report = ResumeFactValidator.validate_content(candidate, content)
    assert report.is_valid is False
    assert len(report.unsupported_claims) >= 2
    claims_text = " ".join(report.unsupported_claims)
    assert "Rust" in claims_text
    assert "Kubernetes" in claims_text


def test_factual_validator_rejects_invented_employer_and_dates():
    candidate = CandidateProfile(
        full_name="Alice Wang",
        email="alice@example.com",
        location="Seattle, WA",
        work_authorization="US Citizen",
        summary="Senior Cloud Engineer",
        experiences=[
            CandidateExperience(
                company="Amazon",
                role="Cloud Support Engineer",
                start_date="2019-06",
                end_date="2022-08",
                is_current=False,
            )
        ],
    )

    # Content with fake company "Google" and wrong dates
    content = TailoredResumeContent(
        full_name="Alice Wang",
        email="alice@example.com",
        location="Seattle, WA",
        summary="Senior Cloud Engineer",
        experiences=[
            TailoredExperience(
                company="Google",  # Invented!
                role="Staff Engineer",
                start_date="2022-09",
                end_date=None,
                is_current=True,
            )
        ],
    )

    report = ResumeFactValidator.validate_content(candidate, content)
    assert report.is_valid is False
    assert any("Google" in c for c in report.unsupported_claims)


def test_pdf_renderer_and_verifier_roundtrip():
    content = TailoredResumeContent(
        full_name="Marcus Vance",
        email="marcus@example.com",
        phone="+1-555-0100",
        location="San Francisco, CA",
        summary="Seasoned backend engineer with proven track record in distributed services.",
        skills_by_category={"Technologies": ["Python", "Docker", "PostgreSQL"]},
        experiences=[
            TailoredExperience(
                company="TechCorp",
                role="Senior Backend Engineer",
                start_date="2020-01",
                is_current=True,
                bullet_points=["Architected distributed message broker using Python and Redis."],
            )
        ],
        educations=[
            TailoredEducation(
                institution="UC Berkeley",
                degree="B.S.",
                field_of_study="Computer Science",
                graduation_year=2018,
            )
        ],
    )

    pdf_bytes = ResumePdfRenderer.render_to_bytes(content)
    assert len(pdf_bytes) > 1000  # Non-trivial PDF generated

    is_ats_valid, extracted_text, diagnostics = ResumePdfVerifier.verify_pdf_bytes(pdf_bytes, content)
    assert is_ats_valid is True
    assert "Marcus Vance" in extracted_text
    assert "marcus@example.com" in extracted_text
    assert "PROFESSIONAL SUMMARY" in extracted_text
    assert "TECHNICAL SKILLS" in extracted_text
    assert "PROFESSIONAL EXPERIENCE" in extracted_text
    assert "EDUCATION" in extracted_text


# ---------------------------------------------------------------------------
# Integration Tests: Resume Generation, Retrieval, Immutability & Download
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_resume_generation_and_immutability(client: AsyncClient):
    # 1. Create Verified Candidate Profile
    cand_payload = {
        "full_name": "Devin Brooks",
        "email": "devin.brooks@example.com",
        "phone": "+1-555-9001",
        "location": "Denver, CO",
        "work_authorization": "US Citizen",
        "summary": "Senior Software Architect specializing in resilient microservices and distributed systems.",
        "years_of_experience": 8.0,
        "target_titles": ["Senior Backend Engineer", "Staff Software Engineer"],
        "target_salary_min": 165000,
        "remote_preference": "REMOTE",
        "skills": [
            {"skill_name": "Python", "category": "technical", "years_experience": 8.0, "is_verified": True},
            {"skill_name": "FastAPI", "category": "technical", "years_experience": 4.0, "is_verified": True},
            {"skill_name": "Docker", "category": "technical", "years_experience": 6.0, "is_verified": True},
            {"skill_name": "PostgreSQL", "category": "technical", "years_experience": 7.0, "is_verified": True},
        ],
        "experiences": [
            {
                "company": "Apex Digital",
                "role": "Lead Backend Engineer",
                "start_date": "2020-01",
                "is_current": True,
                "verified_bullets": [
                    "Engineered asynchronous processing pipelines using FastAPI and PostgreSQL.",
                    "Improved API latency by 45% through connection pooling and query optimization.",
                ],
            }
        ],
        "educations": [
            {
                "institution": "Colorado State University",
                "degree": "B.S.",
                "field_of_study": "Software Engineering",
                "graduation_year": 2016,
            }
        ],
        "projects": [
            {
                "title": "Async Job Dispatcher",
                "description": "High throughput task worker pool built with Python.",
                "technologies": ["Python", "FastAPI"],
            }
        ],
    }
    create_cand_res = await client.post("/api/v1/profile", json=cand_payload)
    assert create_cand_res.status_code == 201

    # 2. Discover Jobs
    await client.post("/api/v1/jobs/discover", json={"source_identifier": "synthetic", "count": 3})
    jobs = (await client.get("/api/v1/jobs")).json()["items"]
    target_job = next(j for j in jobs if "Python" in j["title"])
    job_id = target_job["id"]

    # 3. Generate Job-Specific Tailored Resume
    gen_res = await client.post(
        "/api/v1/resumes/generate",
        json={"job_id": job_id, "use_ai": False},
    )
    assert gen_res.status_code == 201
    version_1 = gen_res.json()

    assert version_1["job_id"] == job_id
    assert version_1["version_number"] == 1
    assert version_1["is_ats_valid"] is True
    assert version_1["is_submission_ready"] is True
    assert version_1["file_sha256"] is not None
    assert version_1["factual_validation_result"]["is_valid"] is True
    assert version_1["keyword_coverage_result"]["coverage_score"] > 50.0

    # 4. Verify Download Returns Exact Matching Bytes
    download_res = await client.get(f"/api/v1/resumes/{version_1['id']}/download")
    assert download_res.status_code == 200
    assert download_res.headers["content-type"] == "application/pdf"
    downloaded_bytes = download_res.content

    downloaded_hash = hashlib.sha256(downloaded_bytes).hexdigest()
    assert downloaded_hash == version_1["file_sha256"]

    # 5. Verify File Integrity Endpoint
    integrity_res = await client.get(f"/api/v1/resumes/{version_1['id']}/integrity")
    assert integrity_res.status_code == 200
    assert integrity_res.json()["is_intact"] is True

    # 6. Force Regenerate: creates version 2 without overwriting version 1
    gen_res_2 = await client.post(
        "/api/v1/resumes/generate",
        json={"job_id": job_id, "use_ai": False, "force_regenerate": True},
    )
    assert gen_res_2.status_code == 201
    version_2 = gen_res_2.json()
    assert version_2["version_number"] == 2
    assert version_2["id"] != version_1["id"]

    # 7. Immutability Check: Update the Candidate Profile
    # Proves that updating master profile DOES NOT mutate previous resume snapshot
    patch_res = await client.patch(
        "/api/v1/profile",
        json={"summary": "Completely new altered summary that should NOT affect historical resumes."},
    )
    assert patch_res.status_code == 200

    # Fetch version 1 again
    re_fetched_v1 = (await client.get(f"/api/v1/resumes/{version_1['id']}")).json()
    assert re_fetched_v1["candidate_snapshot"]["summary"] != patch_res.json()["summary"]
    assert "Senior Software Architect" in re_fetched_v1["candidate_snapshot"]["summary"]


@pytest.mark.asyncio
async def test_cannot_generate_resume_for_disqualified_job(client: AsyncClient):
    # Candidate strictly remote
    cand_payload = {
        "full_name": "Remote Candidate",
        "email": "remotecand@example.com",
        "location": "Portland, OR",
        "work_authorization": "H-1B Visa",
        "summary": "Developer with remote preferences.",
        "years_of_experience": 2.0,
        "remote_preference": "REMOTE",
        "skills": [
            {"skill_name": "Python", "category": "technical", "years_experience": 2.0, "is_verified": True},
        ],
    }
    await client.post("/api/v1/profile", json=cand_payload)

    # Discover jobs (including on-site jobs)
    await client.post("/api/v1/jobs/discover", json={"source_identifier": "synthetic", "count": 5})
    jobs = (await client.get("/api/v1/jobs")).json()["items"]
    # Find on-site role in New York
    onsite_job = next(j for j in jobs if j["remote_type"] == "ON_SITE")

    # Attempting to generate resume for an ineligible job raises 422 Unprocessable Entity
    res = await client.post(
        "/api/v1/resumes/generate",
        json={"job_id": onsite_job["id"], "use_ai": False},
    )
    assert res.status_code == 422
    assert "disqualified" in str(res.json()["detail"]).lower()
