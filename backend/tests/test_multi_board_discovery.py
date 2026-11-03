import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from backend.app.collectors.greenhouse import GreenhouseJobAdapter
from backend.app.collectors.lever import LeverJobAdapter
from backend.app.core.config import settings
from backend.app.services.discovery_pipeline import DiscoveryMatchingPipeline


@pytest.mark.asyncio
async def test_greenhouse_multi_board_fetch():
    adapter = GreenhouseJobAdapter()

    # Mock responses for board 1 ('canonical') and board 2 ('stripe')
    def mock_get(url, params=None, **kwargs):
        mock_resp = MagicMock(spec=httpx.Response)
        if "canonical" in url:
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "jobs": [
                    {"id": 101, "title": "Software Engineer", "location": {"name": "Remote"}}
                ]
            }
        elif "stripe" in url:
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "jobs": [
                    {"id": 201, "title": "Full Stack Engineer", "location": {"name": "Remote"}}
                ]
            }
        else:
            mock_resp.status_code = 404
        return mock_resp

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_client_get:
        mock_client_get.side_effect = mock_get
        jobs = await adapter.fetch_jobs(board_tokens=["canonical", "stripe"])

        assert len(jobs) == 2
        assert jobs[0].external_id == "101"
        assert jobs[0].payload["_board_token"] == "canonical"
        assert jobs[1].external_id == "201"
        assert jobs[1].payload["_board_token"] == "stripe"


@pytest.mark.asyncio
async def test_greenhouse_multi_board_error_isolation():
    adapter = GreenhouseJobAdapter()

    def mock_get(url, params=None, **kwargs):
        mock_resp = MagicMock(spec=httpx.Response)
        if "invalid_board" in url:
            mock_resp.status_code = 404
        elif "valid_board" in url:
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "jobs": [
                    {"id": 301, "title": "Backend Engineer", "location": {"name": "Remote"}}
                ]
            }
        return mock_resp

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_client_get:
        mock_client_get.side_effect = mock_get
        jobs = await adapter.fetch_jobs(board_tokens=["invalid_board", "valid_board"])

        # Even though invalid_board was 404, valid_board succeeded
        assert len(jobs) == 1
        assert jobs[0].external_id == "301"


@pytest.mark.asyncio
async def test_lever_multi_site_fetch():
    adapter = LeverJobAdapter()

    def mock_get(url, params=None, **kwargs):
        mock_resp = MagicMock(spec=httpx.Response)
        if "netflix" in url:
            mock_resp.status_code = 200
            mock_resp.json.return_value = [
                {"id": "lev_1", "text": "Senior Platform Engineer"}
            ]
        elif "spotify" in url:
            mock_resp.status_code = 200
            mock_resp.json.return_value = [
                {"id": "lev_2", "text": "Fullstack Engineer"}
            ]
        return mock_resp

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_client_get:
        mock_client_get.side_effect = mock_get
        jobs = await adapter.fetch_jobs(site_tokens=["netflix", "spotify"])

        assert len(jobs) == 2
        assert jobs[0].external_id == "lev_1"
        assert jobs[1].external_id == "lev_2"


def test_synthetic_isolation_setting():
    assert hasattr(settings, "JOBPILOT_SYNTHETIC_DISCOVERY_ENABLED")
    # By default, synthetic discovery is disabled
    assert settings.JOBPILOT_SYNTHETIC_DISCOVERY_ENABLED is False

