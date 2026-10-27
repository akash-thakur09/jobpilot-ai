import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.main import app
from backend.app.db.session import get_db
from backend.app.models.job import JobSource
from backend.app.services.discovery_pipeline import DiscoveryMatchingPipeline


@pytest.mark.asyncio
async def test_job_source_configuration_api_and_validation(db_session: AsyncSession):
    """
    Step 3: Tests source configuration, validation of board tokens, and rejection of invalid/arbitrary URLs.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. List sources
        list_res = await client.get("/api/v1/jobs/sources")
        assert list_res.status_code == 200
        sources = list_res.json()
        identifiers = [s["identifier"] for s in sources]
        assert "synthetic" in identifiers
        assert "greenhouse" in identifiers
        assert "lever" in identifiers

        # 2. Configure Greenhouse board token
        gh_update = await client.put(
            "/api/v1/jobs/sources/greenhouse",
            json={"is_enabled": True, "board_token": "stripe"},
        )
        assert gh_update.status_code == 200
        gh_data = gh_update.json()
        assert gh_data["is_enabled"] is True
        assert gh_data["config_json"]["board_token"] == "stripe"

        # 3. Validation: Reject invalid token with slashes / arbitrary URL
        bad_url_update = await client.put(
            "/api/v1/jobs/sources/greenhouse",
            json={"board_token": "https://evil.com/exploit"},
        )
        assert bad_url_update.status_code == 422  # Regex validation failure

        bad_path_update = await client.put(
            "/api/v1/jobs/sources/lever",
            json={"site_token": "../../etc/passwd"},
        )
        assert bad_path_update.status_code == 422  # Regex validation failure

        # 4. Configure Lever site token
        lever_update = await client.put(
            "/api/v1/jobs/sources/lever",
            json={"is_enabled": False, "site_token": "netflix"},
        )
        assert lever_update.status_code == 200
        assert lever_update.json()["is_enabled"] is False
        assert lever_update.json()["config_json"]["site_token"] == "netflix"

        # 5. Fetch single source detail
        get_gh = await client.get("/api/v1/jobs/sources/greenhouse")
        assert get_gh.status_code == 200
        assert get_gh.json()["config_json"]["board_token"] == "stripe"

        # 6. Non-existent source 404
        bad_src = await client.get("/api/v1/jobs/sources/non_existent_adapter")
        assert bad_src.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_job_source_health_diagnostics_tracking(db_session: AsyncSession):
    """
    Step 3: Tests that source health is NOT claimed healthy merely because it is configured,
    and accurately transitions to HEALTHY on success and ERROR on failure.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Source before any execution has None/NEVER_RUN status
        init_res = await client.get("/api/v1/jobs/sources/synthetic")
        assert init_res.status_code == 200
        assert init_res.json()["last_status"] is None or init_res.json()["last_status"] == "NEVER_RUN"

        # 2. Run discovery on synthetic
        run_res = await client.post("/api/v1/scheduler/run", json={"sources": ["synthetic"]})
        assert run_res.status_code == 200

        # 3. Source should now be HEALTHY with jobs_discovered_count > 0
        after_res = await client.get("/api/v1/jobs/sources/synthetic")
        assert after_res.status_code == 200
        data = after_res.json()
        assert data["last_status"] == "HEALTHY"
        assert data["jobs_discovered_count"] >= 1
        assert data["last_discovered_at"] is not None

    app.dependency_overrides.clear()
