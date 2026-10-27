import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.main import app
from backend.app.services.scheduler_service import SchedulerService
from backend.app.db.session import get_db


@pytest.mark.asyncio
async def test_scheduler_service_status_and_lifecycle():
    """Tests scheduler lifecycle methods: start, enable, disable, update_interval."""
    await SchedulerService.start()
    status = await SchedulerService.get_status()
    assert "is_enabled" in status
    assert "interval_minutes" in status
    assert "is_active_run" in status

    # Enable scheduler
    status_enabled = await SchedulerService.enable()
    assert status_enabled["is_enabled"] is True

    # Disable scheduler
    status_disabled = await SchedulerService.disable()
    assert status_disabled["is_enabled"] is False

    # Interval update with valid value
    status_updated = await SchedulerService.update_interval(120)
    assert status_updated["interval_minutes"] == 120

    # Interval update with invalid value must raise ValueError
    with pytest.raises(ValueError):
        await SchedulerService.update_interval(2)  # Below 5 minutes minimum

    with pytest.raises(ValueError):
        await SchedulerService.update_interval(20000)  # Exceeds 10080 minutes maximum


@pytest.mark.asyncio
async def test_scheduler_prevents_overlapping_runs(monkeypatch):
    """Verifies that SchedulerService rejects duplicate runs while a discovery is in progress."""
    # Simulate a slow discovery run by holding the lock
    async with SchedulerService._run_lock:
        SchedulerService._is_running_discovery = True
        result = await SchedulerService.execute_discovery(trigger="manual")
        assert result.get("status") == "BUSY"
        assert "Overlapping runs are prohibited" in result.get("message", "")
    SchedulerService._is_running_discovery = False


@pytest.mark.asyncio
async def test_scheduler_api_routes(db_session: AsyncSession):
    """Tests the /api/v1/scheduler routes using FastAPI test client."""
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Get status
        res = await client.get("/api/v1/scheduler/status")
        assert res.status_code == 200
        data = res.json()
        assert "is_enabled" in data
        assert "interval_minutes" in data

        # 2. Update config
        res = await client.post("/api/v1/scheduler/config", json={"enabled": True, "interval_minutes": 60})
        assert res.status_code == 200
        data = res.json()
        assert data["is_enabled"] is True
        assert data["interval_minutes"] == 60

        # 3. Invalid config rejected
        res = await client.post("/api/v1/scheduler/config", json={"interval_minutes": 1})
        assert res.status_code == 422 or res.status_code == 400

        # 4. Trigger manual run with synthetic source
        res = await client.post("/api/v1/scheduler/run", json={"sources": ["synthetic"]})
        assert res.status_code == 200
        run_data = res.json()
        assert "run_id" in run_data
        run_id = run_data["run_id"]

        # 5. List runs
        res = await client.get("/api/v1/scheduler/runs")
        assert res.status_code == 200
        runs_list = res.json()
        assert runs_list["total"] >= 1
        assert any(r["id"] == run_id for r in runs_list["items"])

        # 6. Get single run detail
        res = await client.get(f"/api/v1/scheduler/runs/{run_id}")
        assert res.status_code == 200
        single_run = res.json()
        assert single_run["id"] == run_id
        assert "metadata" in single_run

    app.dependency_overrides.clear()
