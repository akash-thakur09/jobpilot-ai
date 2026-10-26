import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_health(client: AsyncClient):
    """Test /health root endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "JobPilot AI"


@pytest.mark.asyncio
async def test_api_v1_health(client: AsyncClient):
    """Test /api/v1/health endpoint."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "JobPilot" in data["service"]


@pytest.mark.asyncio
async def test_api_v1_readiness(client: AsyncClient):
    """Test /api/v1/health/ready endpoint."""
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
