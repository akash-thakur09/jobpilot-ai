import hashlib
import io
import os
import shutil
from pathlib import Path
import pytest
from httpx import AsyncClient
import pypdf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.candidate import (
    CandidateProfile,
    CandidateSkill,
    CandidateExperience,
    CandidateEducation,
    CandidateProject,
)
from backend.app.models.job import Job, JobSource, JobRequirement
from backend.app.models.resume import ResumeVersion
from backend.app.models.enums import RemoteType
from backend.app.resumes.fact_validator import ResumeFactValidator
from backend.app.resumes.schemas import (
    TailoredResumeContent,
    TailoredExperience,
    TailoredEducation,
    TailoredProject,
)
from backend.app.resumes.storage_service import ResumeStorageService
from backend.app.services.resume_version_service import ResumeVersionService


# ===========================================================================
# Helper Fixtures & Setup
# ===========================================================================
async def create_candidate_fixture(client: AsyncClient) -> dict:
    cand_payload = {
        "full_name": "Alex Rivera",
        "email": "alex.rivera@example.com",
        "phone": "+1-555-0199",
        "location": "San Francisco, CA",
        "work_authorization": "US Citizen",
        "summary": "Full Stack Software Engineer with 5+ years experience building modern web apps with React, TypeScript, and Node.js.",
        "years_of_experience": 5.0,
        "remote_preference": "REMOTE",
        "skills": [
            {"skill_name": "React", "category": "technical", "years_experience": 5.0, "is_verified": True},
            {"skill_name": "TypeScript", "category": "technical", "years_experience": 4.0, "is_verified": True},
            {"skill_name": "JavaScript", "category": "technical", "years_experience": 5.0, "is_verified": True},
            {"skill_name": "Node.js", "category": "technical", "years_experience": 4.0, "is_verified": True},
            {"skill_name": "Express", "category": "technical", "years_experience": 3.0, "is_verified": True},
            {"skill_name": "PostgreSQL", "category": "technical", "years_experience": 4.0, "is_verified": True},
            {"skill_name": "Docker", "category": "technical", "years_experience": 3.0, "is_verified": True},
            {"skill_name": "Git", "category": "technical", "years_experience": 5.0, "is_verified": True},
        ],
        "experiences": [
            {
                "company": "Apex Solutions",
                "role": "Full Stack Engineer",
                "start_date": "2021-03",
                "is_current": True,
                "verified_bullets": [
                    "Engineered responsive client interfaces using React and TypeScript reducing page load times by 40%.",
                    "Architected RESTful backend microservices in Node.js, Express, and PostgreSQL serving 10k requests per second.",
                ],
            }
        ],
        "projects": [
            {
                "title": "Cloud Metrics Dashboard",
                "description": "Interactive metrics visualization dashboard built with React and TypeScript.",
                "technologies": ["React", "TypeScript", "PostgreSQL"],
                "verified_bullets": ["Designed scalable data visualization components using React."],
            }
        ],
        "educations": [
            {
                "institution": "University of California",
                "degree": "B.S. in Computer Science",
                "field_of_study": "Computer Science",
                "graduation_year": 2020,
            }
        ],
    }
    res = await client.post("/api/v1/profile", json=cand_payload)
    assert res.status_code == 201, f"Candidate creation failed: {res.text}"
    return res.json()


async def create_jobs_fixture(db_session: AsyncSession):
    source = JobSource(name="Synthetic Source", identifier="synthetic_acc", base_url="https://example.com", is_enabled=True)
    db_session.add(source)
    await db_session.flush()

    react_job = Job(
        source_id=source.id,
        external_id="react-dev-acc-001",
        title="Senior React Developer",
        company="Frontend Horizons",
        canonical_url="https://frontendhorizons.example.com/jobs/react-dev",
        description="Looking for a Senior React Developer proficient in React, TypeScript, and modern UI architectures to build responsive client web apps.",
        location="Remote",
        remote_type=RemoteType.REMOTE.value,
        requirements=[
            JobRequirement(requirement_type="MANDATORY_SKILL", value="React", weight=1.0),
            JobRequirement(requirement_type="PREFERRED_SKILL", value="TypeScript", weight=0.8),
        ],
    )

    node_job = Job(
        source_id=source.id,
        external_id="node-dev-acc-002",
        title="Senior Node.js Developer",
        company="Backend Systems Corp",
        canonical_url="https://backendsystems.example.com/jobs/node-dev",
        description="Seeking a Senior Node.js Developer with deep experience in Node.js, Express, and PostgreSQL to design robust APIs.",
        location="Remote",
        remote_type=RemoteType.REMOTE.value,
        requirements=[
            JobRequirement(requirement_type="MANDATORY_SKILL", value="Node.js", weight=1.0),
            JobRequirement(requirement_type="PREFERRED_SKILL", value="Express", weight=0.8),
            JobRequirement(requirement_type="PREFERRED_SKILL", value="PostgreSQL", weight=0.8),
        ],
    )

    db_session.add_all([react_job, node_job])
    await db_session.commit()
    await db_session.refresh(react_job)
    await db_session.refresh(node_job)
    return react_job, node_job


# ===========================================================================
# Test 1: Generate resumes for different jobs
# ===========================================================================
@pytest.mark.asyncio
async def test_generate_resumes_for_different_jobs(client: AsyncClient, db_session: AsyncSession):
    """
    Test 1:
    - Generates resumes for React Developer and Node.js Developer jobs.
    - Asserts both operations succeed, PDFs exist and are readable.
    - Asserts unique IDs and job-tailored content without unsupported qualifications.
    """
    await create_candidate_fixture(client)
    react_job, node_job = await create_jobs_fixture(db_session)

    # 1. Generate React resume
    gen_react_res = await client.post(
        "/api/v1/resumes/generate",
        json={"job_id": react_job.id, "use_ai": False},
    )
    assert gen_react_res.status_code == 201, gen_react_res.text
    react_version = gen_react_res.json()

    # 2. Generate Node.js resume
    gen_node_res = await client.post(
        "/api/v1/resumes/generate",
        json={"job_id": node_job.id, "use_ai": False},
    )
    assert gen_node_res.status_code == 201, gen_node_res.text
    node_version = gen_node_res.json()

    # Assert unique IDs
    assert react_version["id"] != node_version["id"]
    assert react_version["job_id"] == react_job.id
    assert node_version["job_id"] == node_job.id

    # Verify both PDFs exist on disk and are readable by pypdf
    for ver in [react_version, node_version]:
        pdf_path = Path(ver["pdf_file_path"])
        assert pdf_path.exists(), f"PDF does not exist on disk: {pdf_path}"
        assert pdf_path.stat().st_size > 0

        # pypdf readability check
        reader = pypdf.PdfReader(str(pdf_path))
        assert len(reader.pages) >= 1
        page_text = reader.pages[0].extract_text()
        assert "Alex Rivera" in page_text
        assert ver["is_ats_valid"] is True
        assert ver["is_submission_ready"] is True

    # Assert tailored content distinction
    react_core_skills = react_version["structured_content"]["skills_by_category"].get(
        "Core Technologies & Relevant Skills", []
    )
    node_core_skills = node_version["structured_content"]["skills_by_category"].get(
        "Core Technologies & Relevant Skills", []
    )

    assert "React" in react_core_skills
    assert "TypeScript" in react_core_skills
    assert "Node.js" in node_core_skills
    assert "Express" in node_core_skills
    assert "PostgreSQL" in node_core_skills

    # Assert unsupported qualifications are NOT introduced
    verified_candidate_skills = {"React", "TypeScript", "JavaScript", "Node.js", "Express", "PostgreSQL", "Docker", "Git"}
    all_react_claimed_skills = [
        s for skills in react_version["structured_content"]["skills_by_category"].values() for s in skills
    ]
    all_node_claimed_skills = [
        s for skills in node_version["structured_content"]["skills_by_category"].values() for s in skills
    ]

    for s in all_react_claimed_skills + all_node_claimed_skills:
        assert s in verified_candidate_skills, f"Unsupported skill found in resume: {s}"
    assert "Kubernetes" not in all_react_claimed_skills
    assert "Kubernetes" not in all_node_claimed_skills


# ===========================================================================
# Test 2: Verify PDF checksums independently
# ===========================================================================
@pytest.mark.asyncio
async def test_verify_pdf_checksums_independently(client: AsyncClient, db_session: AsyncSession):
    """
    Test 2:
    - Reads stored PDF bytes directly.
    - Independently calculates SHA-256 with Python's hashlib.
    - Compares with the persisted database checksum.
    """
    await create_candidate_fixture(client)
    react_job, node_job = await create_jobs_fixture(db_session)

    res_react = (await client.post("/api/v1/resumes/generate", json={"job_id": react_job.id, "use_ai": False})).json()
    res_node = (await client.post("/api/v1/resumes/generate", json={"job_id": node_job.id, "use_ai": False})).json()

    for ver in [res_react, res_node]:
        file_path = Path(ver["pdf_file_path"])
        assert file_path.exists()

        # 1. Read actual bytes directly from storage
        raw_bytes = file_path.read_bytes()

        # 2. Independent SHA-256 calculation
        calculated_sha256 = hashlib.sha256(raw_bytes).hexdigest()

        # 3. Assert match with database checksum
        assert calculated_sha256 == ver["file_sha256"]
        assert len(calculated_sha256) == 64
        # Verify filename convention uses the sha256
        assert file_path.name == f"{calculated_sha256}.pdf"


# ===========================================================================
# Test 3: Verify immutability
# ===========================================================================
@pytest.mark.asyncio
async def test_verify_immutability(client: AsyncClient, db_session: AsyncSession):
    """
    Test 3:
    1. Generate and persist resume for React job.
    2. Record version ID, PDF bytes, checksum, and database snapshot.
    3. Update candidate's master profile.
    4. Generate a new resume version (v2).
    5. Retrieve original version (v1) via API.
    6. Assert original PDF bytes, checksum, and candidate snapshot are strictly unchanged.
    """
    await create_candidate_fixture(client)
    react_job, _ = await create_jobs_fixture(db_session)

    # 1. Generate v1
    v1 = (await client.post("/api/v1/resumes/generate", json={"job_id": react_job.id, "use_ai": False})).json()
    v1_id = v1["id"]
    v1_sha256 = v1["file_sha256"]
    v1_bytes = Path(v1["pdf_file_path"]).read_bytes()
    v1_summary = v1["candidate_snapshot"]["summary"]

    # 2. Update candidate master profile
    patch_payload = {
        "summary": "MUTATED SUMMARY: Now an LLM and AI safety specialist.",
        "location": "Boston, MA",
    }
    patch_res = await client.patch("/api/v1/profile", json=patch_payload)
    assert patch_res.status_code == 200

    # 3. Force generate v2
    v2_res = await client.post(
        "/api/v1/resumes/generate",
        json={"job_id": react_job.id, "use_ai": False, "force_regenerate": True},
    )
    assert v2_res.status_code == 201
    v2 = v2_res.json()
    assert v2["id"] != v1_id
    assert v2["version_number"] == 2

    # 4. Re-fetch v1 through API
    re_fetched_v1_res = await client.get(f"/api/v1/resumes/{v1_id}")
    assert re_fetched_v1_res.status_code == 200
    re_fetched_v1 = re_fetched_v1_res.json()

    # 5. Assert immutability
    assert re_fetched_v1["id"] == v1_id
    assert re_fetched_v1["file_sha256"] == v1_sha256
    current_disk_bytes = Path(re_fetched_v1["pdf_file_path"]).read_bytes()
    assert current_disk_bytes == v1_bytes
    assert hashlib.sha256(current_disk_bytes).hexdigest() == v1_sha256

    # Candidate snapshot in v1 must retain the historical summary, not the mutated one
    assert re_fetched_v1["candidate_snapshot"]["summary"] == v1_summary
    assert "LLM and AI safety" not in re_fetched_v1["candidate_snapshot"]["summary"]
    assert "Boston, MA" not in re_fetched_v1["candidate_snapshot"]["location"]


# ===========================================================================
# Test 4: Verify database persistence
# ===========================================================================
@pytest.mark.asyncio
async def test_verify_database_persistence(client: AsyncClient, db_session: AsyncSession):
    """
    Test 4:
    - Confirm distinct database records per version.
    - Verify correct foreign keys, file existence, and validation metadata.
    - Confirm version is retrievable via an isolated direct query.
    """
    cand = await create_candidate_fixture(client)
    react_job, _ = await create_jobs_fixture(db_session)

    gen_res = await client.post("/api/v1/resumes/generate", json={"job_id": react_job.id, "use_ai": False})
    v1 = gen_res.json()

    # Direct database inspection
    query = select(ResumeVersion).where(ResumeVersion.id == v1["id"])
    db_res = await db_session.execute(query)
    record = db_res.scalar_one_or_none()

    assert record is not None
    assert record.id == v1["id"]
    assert record.candidate_id == cand["id"]
    assert record.job_id == react_job.id
    assert record.version_number == 1
    assert record.file_sha256 == v1["file_sha256"]
    assert record.is_submission_ready is True
    assert record.is_ats_valid is True

    # Check persistence of structured validation metadata
    assert isinstance(record.factual_validation_result, dict)
    assert record.factual_validation_result["is_valid"] is True
    assert isinstance(record.keyword_coverage_result, dict)
    assert record.keyword_coverage_result["coverage_score"] > 50.0

    # Ensure no application record is required at this stage
    from backend.app.models.application import Application
    app_query = select(Application).where(Application.resume_version_id == record.id)
    apps_res = await db_session.execute(app_query)
    assert apps_res.scalars().all() == []


# ===========================================================================
# Test 5: Verify API retrieval and download
# ===========================================================================
@pytest.mark.asyncio
async def test_verify_api_retrieval_and_download(client: AsyncClient, db_session: AsyncSession):
    """
    Test 5:
    - Verify GET /{version_id} returns metadata.
    - Verify GET /{version_id}/download streams exact bytes with application/pdf.
    - Verify 404 for unknown IDs.
    - Verify job isolation in GET /job/{job_id}.
    """
    await create_candidate_fixture(client)
    react_job, node_job = await create_jobs_fixture(db_session)

    res_react = (await client.post("/api/v1/resumes/generate", json={"job_id": react_job.id, "use_ai": False})).json()
    res_node = (await client.post("/api/v1/resumes/generate", json={"job_id": node_job.id, "use_ai": False})).json()

    # 1. Metadata retrieval
    meta_res = await client.get(f"/api/v1/resumes/{res_react['id']}")
    assert meta_res.status_code == 200
    assert meta_res.json()["id"] == res_react["id"]

    # 2. Download endpoint
    dl_res = await client.get(f"/api/v1/resumes/{res_react['id']}/download")
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/pdf"
    assert "Alex_Rivera" in dl_res.headers.get("content-disposition", "")

    # Assert exact byte match
    downloaded_bytes = dl_res.content
    assert hashlib.sha256(downloaded_bytes).hexdigest() == res_react["file_sha256"]

    # 3. Nonexistent ID handling
    bad_id = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"/api/v1/resumes/{bad_id}")).status_code == 404
    assert (await client.get(f"/api/v1/resumes/{bad_id}/download")).status_code == 404

    # 4. Job Isolation
    react_versions = (await client.get(f"/api/v1/resumes/job/{react_job.id}")).json()
    assert len(react_versions) == 1
    assert react_versions[0]["id"] == res_react["id"]

    node_versions = (await client.get(f"/api/v1/resumes/job/{node_job.id}")).json()
    assert len(node_versions) == 1
    assert node_versions[0]["id"] == res_node["id"]


# ===========================================================================
# Test 6: Verify factual validation (rejection of unverified facts & truthful paraphrase)
# ===========================================================================
@pytest.mark.asyncio
async def test_verify_factual_validation(client: AsyncClient, db_session: AsyncSession):
    """
    Test 6:
    - Candidate has verified React experience but NO verified Kubernetes.
    - Attempts to validate content with fabricated Kubernetes skill and 95% achievement metric.
    - Asserts claims are rejected/flagged.
    - Asserts truthful paraphrase of supported accomplishment is accepted.
    """
    candidate = CandidateProfile(
        full_name="Alex Rivera",
        email="alex.rivera@example.com",
        location="San Francisco, CA",
        summary="Frontend Engineer",
        skills=[
            CandidateSkill(skill_name="React", category="technical", years_experience=5.0, is_verified=True),
            CandidateSkill(skill_name="TypeScript", category="technical", years_experience=4.0, is_verified=True),
        ],
        experiences=[
            CandidateExperience(
                company="Apex Solutions",
                role="Frontend Developer",
                start_date="2021-03",
                is_current=True,
                verified_bullets=[
                    "Engineered responsive client interfaces using React reducing page load times by 40%."
                ],
            )
        ],
    )

    # 1. Fabricated Skill Claim ("Kubernetes") & Fabricated Metric ("95%")
    hallucinated_content = TailoredResumeContent(
        full_name="Alex Rivera",
        email="alex.rivera@example.com",
        location="San Francisco, CA",
        summary="Frontend Engineer with deep Kubernetes orchestration experience.",
        skills_by_category={
            "Frontend": ["React", "TypeScript"],
            "Cloud & DevOps": ["Kubernetes"],  # Fabricated skill!
        },
        experiences=[
            TailoredExperience(
                company="Apex Solutions",
                role="Frontend Developer",
                start_date="2021-03",
                is_current=True,
                bullet_points=[
                    "Engineered responsive client interfaces reducing page load times by 95% using Kubernetes."  # 95% and Kubernetes are fabricated!
                ],
            )
        ],
    )

    report = ResumeFactValidator.validate_content(candidate, hallucinated_content)
    assert report.is_valid is False
    assert len(report.unsupported_claims) >= 2
    claims_text = " ".join(report.unsupported_claims)
    assert "Kubernetes" in claims_text
    assert "95%" in claims_text

    # 2. Truthful Paraphrase of Supported Accomplishment
    # Verified: "Engineered responsive client interfaces using React reducing page load times by 40%."
    # Paraphrase: "Developed high performance client applications using React cutting page load times by 40%."
    truthful_content = TailoredResumeContent(
        full_name="Alex Rivera",
        email="alex.rivera@example.com",
        location="San Francisco, CA",
        summary="Frontend Engineer specializing in React.",
        skills_by_category={
            "Core Technologies": ["React", "TypeScript"],
        },
        experiences=[
            TailoredExperience(
                company="Apex Solutions",
                role="Frontend Developer",
                start_date="2021-03",
                is_current=True,
                bullet_points=[
                    "Developed high performance client applications using React cutting page load times by 40%."
                ],
            )
        ],
    )

    truthful_report = ResumeFactValidator.validate_content(candidate, truthful_content)
    assert truthful_report.is_valid is True
    assert len(truthful_report.unsupported_claims) == 0
    assert truthful_report.supported_claims_count > 0


# ===========================================================================
# Test 7: Test failure recovery
# ===========================================================================
@pytest.mark.asyncio
async def test_failure_recovery_and_integrity_detection(client: AsyncClient, db_session: AsyncSession):
    """
    Test 7:
    - Missing PDF file detection.
    - Checksum mismatch detection.
    - Disqualified job rejection.
    - Invalid version ID 404.
    """
    await create_candidate_fixture(client)
    react_job, _ = await create_jobs_fixture(db_session)

    gen_res = await client.post("/api/v1/resumes/generate", json={"job_id": react_job.id, "use_ai": False})
    v1 = gen_res.json()
    pdf_path = Path(v1["pdf_file_path"])
    original_bytes = pdf_path.read_bytes()

    # 1. Checksum mismatch detection: Corrupt file on disk
    corrupted_bytes = original_bytes + b"__TAMPERED_BYTES__"
    pdf_path.write_bytes(corrupted_bytes)

    integrity_res = await client.get(f"/api/v1/resumes/{v1['id']}/integrity")
    assert integrity_res.status_code == 200
    assert integrity_res.json()["is_intact"] is False

    # Restore original bytes
    pdf_path.write_bytes(original_bytes)
    assert (await client.get(f"/api/v1/resumes/{v1['id']}/integrity")).json()["is_intact"] is True

    # 2. Missing PDF file detection: Temporarily remove file
    temp_backup = pdf_path.with_suffix(".bak")
    shutil.move(pdf_path, temp_backup)

    try:
        # Integrity endpoint reports missing
        missing_integrity = await client.get(f"/api/v1/resumes/{v1['id']}/integrity")
        assert missing_integrity.status_code == 200
        assert missing_integrity.json()["is_intact"] is False

        # Download endpoint returns 404 when file missing
        missing_dl = await client.get(f"/api/v1/resumes/{v1['id']}/download")
        assert missing_dl.status_code == 404
    finally:
        # Restore file
        shutil.move(temp_backup, pdf_path)

    # 3. Disqualified job cannot generate resume
    disqualified_job = Job(
        source_id=react_job.source_id,
        external_id="disqualified-job-001",
        title="Onsite Defense Engineer",
        company="Strict Onsite Defense",
        canonical_url="https://jobs.example.com/onsite-defense",
        description="Requires full onsite presence in Anchorage, AK. Remote is strictly prohibited.",
        location="Anchorage, AK",
        remote_type=RemoteType.ON_SITE.value,
        requirements=[
            JobRequirement(requirement_type="MANDATORY_SKILL", value="Rust", weight=1.0)
        ],
    )
    db_session.add(disqualified_job)
    await db_session.commit()
    await db_session.refresh(disqualified_job)

    # Candidate has remote preference and lacks Rust
    disq_gen_res = await client.post(
        "/api/v1/resumes/generate",
        json={"job_id": disqualified_job.id, "use_ai": False},
    )
    assert disq_gen_res.status_code == 422
    assert "Cannot generate resume for disqualified job" in disq_gen_res.json()["detail"]

    # 4. Invalid resume-version ID returns 404
    bad_res = await client.get("/api/v1/resumes/non-existent-version-id")
    assert bad_res.status_code == 404
