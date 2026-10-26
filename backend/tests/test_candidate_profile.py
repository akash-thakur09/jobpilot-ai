import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_candidate_profile_not_found(client: AsyncClient):
    response = await client.get("/api/v1/profile")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_and_get_candidate_profile(client: AsyncClient):
    payload = {
        "full_name": "Sarah Connor",
        "email": "sarah.connor@example.com",
        "phone": "+1-555-0199",
        "location": "Los Angeles, CA",
        "work_authorization": "US Citizen",
        "summary": "Seasoned Lead DevOps and Platform Engineer with 8+ years building resilient infrastructure.",
        "years_of_experience": 8.0,
        "target_titles": ["Staff Platform Engineer", "DevOps Architect"],
        "target_salary_min": 175000,
        "target_salary_max": 220000,
        "remote_preference": "REMOTE",
        "notice_period_days": 14,
        "skills": [
            {
                "skill_name": "Kubernetes",
                "category": "technical",
                "years_experience": 6.0,
                "is_verified": True,
            },
            {
                "skill_name": "Terraform",
                "category": "technical",
                "years_experience": 5.0,
                "is_verified": True,
            },
        ],
        "experiences": [
            {
                "company": "Cyberdyne Systems",
                "role": "Lead Infrastructure Engineer",
                "location": "Sunnyvale, CA",
                "start_date": "2020-01",
                "end_date": None,
                "is_current": True,
                "verified_bullets": [
                    "Architected multi-region Kubernetes clusters with 99.99% uptime.",
                    "Reduced cloud spend by 35% through automated instance right-sizing.",
                ],
            }
        ],
        "educations": [
            {
                "institution": "UCLA",
                "degree": "B.S.",
                "field_of_study": "Computer Science",
                "graduation_year": 2016,
            }
        ],
        "projects": [
            {
                "title": "GitOps AutoDeployer",
                "description": "Kubernetes controller for automated declarative deployments.",
                "technologies": ["Go", "Kubernetes", "Helm"],
                "project_url": "https://github.com/example/autodeployer",
                "verified_bullets": ["Over 500 GitHub stars and 10 production adopters."],
            }
        ],
    }

    # 1. Create Profile
    post_res = await client.post("/api/v1/profile", json=payload)
    assert post_res.status_code == 201
    created_data = post_res.json()
    assert created_data["full_name"] == "Sarah Connor"
    assert created_data["email"] == "sarah.connor@example.com"
    assert len(created_data["skills"]) == 2
    assert len(created_data["experiences"]) == 1
    assert len(created_data["educations"]) == 1
    assert len(created_data["projects"]) == 1

    # 2. Get Profile
    get_res = await client.get("/api/v1/profile")
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["id"] == created_data["id"]
    assert retrieved["target_titles"] == ["Staff Platform Engineer", "DevOps Architect"]

    # 3. Prevent duplicate profile creation
    dup_res = await client.post("/api/v1/profile", json=payload)
    assert dup_res.status_code == 409


@pytest.mark.asyncio
async def test_update_candidate_profile(client: AsyncClient):
    payload = {
        "full_name": "Jordan Bell",
        "email": "jordan.bell@example.com",
        "location": "Austin, TX",
        "work_authorization": "Permanent Resident",
        "summary": "Full Stack Engineer specializing in TypeScript and FastAPI applications.",
        "years_of_experience": 4.0,
    }
    create_res = await client.post("/api/v1/profile", json=payload)
    assert create_res.status_code == 201

    update_payload = {
        "years_of_experience": 5.0,
        "target_titles": ["Senior Full Stack Engineer"],
        "target_salary_min": 150000,
    }
    patch_res = await client.patch("/api/v1/profile", json=update_payload)
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["years_of_experience"] == 5.0
    assert updated["target_titles"] == ["Senior Full Stack Engineer"]
    assert updated["target_salary_min"] == 150000


@pytest.mark.asyncio
async def test_candidate_profile_validation_errors(client: AsyncClient):
    # Invalid email
    bad_email_payload = {
        "full_name": "Jane Doe",
        "email": "not-an-email",
        "location": "New York, NY",
        "work_authorization": "US Citizen",
        "summary": "Short",  # Min length 10
        "years_of_experience": -2.0,  # Negative
    }
    res = await client.post("/api/v1/profile", json=bad_email_payload)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_manage_nested_entities(client: AsyncClient):
    # Create base profile
    payload = {
        "full_name": "Test Candidate",
        "email": "nested@example.com",
        "location": "Seattle, WA",
        "work_authorization": "US Citizen",
        "summary": "Candidate for testing nested entities management.",
        "years_of_experience": 3.0,
    }
    res = await client.post("/api/v1/profile", json=payload)
    assert res.status_code == 201

    # Add skill
    skill_res = await client.post(
        "/api/v1/profile/skills",
        json={"skill_name": "PostgreSQL", "category": "database", "years_experience": 3.0},
    )
    assert skill_res.status_code == 201
    skill_data = skill_res.json()
    skill_id = skill_data["id"]

    # Add experience
    exp_res = await client.post(
        "/api/v1/profile/experiences",
        json={
            "company": "Cloud Corp",
            "role": "Backend Engineer",
            "start_date": "2021-03",
            "verified_bullets": ["Engineered ETL pipelines"],
        },
    )
    assert exp_res.status_code == 201
    exp_id = exp_res.json()["id"]

    # Add education
    edu_res = await client.post(
        "/api/v1/profile/educations",
        json={
            "institution": "University of Washington",
            "degree": "B.S.",
            "field_of_study": "Informatics",
            "graduation_year": 2021,
        },
    )
    assert edu_res.status_code == 201
    edu_id = edu_res.json()["id"]

    # Add project
    proj_res = await client.post(
        "/api/v1/profile/projects",
        json={
            "title": "Metrics Exporter",
            "description": "Exports database telemetry to Prometheus.",
            "technologies": ["Python", "Prometheus"],
        },
    )
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["id"]

    # Verify profile now has all items
    profile = (await client.get("/api/v1/profile")).json()
    assert len(profile["skills"]) == 1
    assert len(profile["experiences"]) == 1
    assert len(profile["educations"]) == 1
    assert len(profile["projects"]) == 1

    # Delete all items
    del_skill = await client.delete(f"/api/v1/profile/skills/{skill_id}")
    assert del_skill.status_code == 204

    del_exp = await client.delete(f"/api/v1/profile/experiences/{exp_id}")
    assert del_exp.status_code == 204

    del_edu = await client.delete(f"/api/v1/profile/educations/{edu_id}")
    assert del_edu.status_code == 204

    del_proj = await client.delete(f"/api/v1/profile/projects/{proj_id}")
    assert del_proj.status_code == 204

    # Verify profile is now empty of items
    refreshed = (await client.get("/api/v1/profile")).json()
    assert len(refreshed["skills"]) == 0
    assert len(refreshed["experiences"]) == 0
    assert len(refreshed["educations"]) == 0
    assert len(refreshed["projects"]) == 0
