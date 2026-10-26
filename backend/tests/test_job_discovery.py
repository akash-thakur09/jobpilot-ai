import pytest
from httpx import AsyncClient
from backend.app.collectors.greenhouse import GreenhouseJobAdapter
from backend.app.collectors.lever import LeverJobAdapter
from backend.app.collectors.base import RawJobData
from backend.app.models.enums import RemoteType


@pytest.mark.asyncio
async def test_synthetic_job_discovery_end_to_end(client: AsyncClient):
    # 1. Trigger synthetic discovery
    payload = {"source_identifier": "synthetic", "count": 5}
    res = await client.post("/api/v1/jobs/discover", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "synthetic"
    assert data["items_processed"] == 5
    assert data["inserted"] == 5
    assert data["updated"] == 0
    assert data["unchanged"] == 0
    assert data["status"] == "COMPLETED"

    # 2. List jobs
    list_res = await client.get("/api/v1/jobs?limit=10")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 5
    assert len(list_data["items"]) == 5

    # Check first job attributes
    first_job = list_data["items"][0]
    assert first_job["company"] == "Acme Cloud Corp"
    assert first_job["status"] == "DISCOVERED"

    # 3. Test Detail
    detail_res = await client.get(f"/api/v1/jobs/{first_job['id']}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == first_job["id"]

    # 4. Test Filters
    filter_res = await client.get("/api/v1/jobs?remote_type=REMOTE")
    assert filter_res.status_code == 200
    remote_jobs = filter_res.json()["items"]
    assert all(j["remote_type"] == "REMOTE" for j in remote_jobs)

    # 5. Test Sources
    sources_res = await client.get("/api/v1/jobs/sources")
    assert sources_res.status_code == 200
    sources = sources_res.json()
    assert any(s["identifier"] == "synthetic" for s in sources)


@pytest.mark.asyncio
async def test_job_discovery_deduplication(client: AsyncClient):
    payload = {"source_identifier": "synthetic", "count": 3}

    # First run
    res1 = await client.post("/api/v1/jobs/discover", json=payload)
    assert res1.status_code == 200
    assert res1.json()["inserted"] == 3

    # Second run (exact same jobs)
    res2 = await client.post("/api/v1/jobs/discover", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["inserted"] == 0
    assert data2["unchanged"] == 3
    assert data2["updated"] == 0

    # Ensure total in DB is still exactly 3
    list_res = await client.get("/api/v1/jobs")
    assert list_res.json()["total"] == 3


@pytest.mark.asyncio
async def test_greenhouse_normalization_with_fixtures():
    adapter = GreenhouseJobAdapter()
    fixtures = [
        {
            "id": 998877,
            "title": "Principal Staff Engineer (Remote)",
            "absolute_url": "https://boards.greenhouse.io/stripe/jobs/998877",
            "location": {"name": "San Francisco / Remote"},
            "content": "&lt;p&gt;We are looking for a &lt;strong&gt;Principal Staff Engineer&lt;/strong&gt; to lead architecture.&lt;/p&gt;",
        },
        {
            "id": 998878,
            "title": "Office Operations Coordinator",
            "absolute_url": "https://boards.greenhouse.io/stripe/jobs/998878",
            "location": {"name": "Seattle, WA"},
            "content": "<p>On-site facility management coordinator.</p>",
        },
    ]

    raw_items = await adapter.fetch_jobs(board_token="stripe", fixtures=fixtures)
    assert len(raw_items) == 2

    # Verify first job normalization
    job1 = adapter.normalize(raw_items[0])
    assert job1.external_id == "998877"
    assert job1.company == "Stripe"
    assert job1.remote_type == RemoteType.REMOTE
    assert "Principal Staff Engineer" in job1.description
    assert "<p>" not in job1.description
    assert "&lt;" not in job1.description

    # Verify second job normalization
    job2 = adapter.normalize(raw_items[1])
    assert job2.external_id == "998878"
    assert job2.remote_type == RemoteType.ON_SITE
    assert job2.location == "Seattle, WA"


@pytest.mark.asyncio
async def test_lever_normalization_with_fixtures():
    adapter = LeverJobAdapter()
    fixtures = [
        {
            "id": "lev-uuid-1",
            "text": "Site Reliability Engineer",
            "hostedUrl": "https://jobs.lever.co/netflix/lev-uuid-1",
            "categories": {
                "location": "Remote, US",
                "commitment": "Full time",
                "team": "Platform",
            },
            "descriptionPlain": "Build chaos engineering tools and observability infrastructure.",
            "additionalPlain": "Competitive salary and benefits included.",
            "createdAt": 1700000000,
        },
        {
            "id": "lev-uuid-2",
            "text": "Hardware Lab Tech",
            "hostedUrl": "https://jobs.lever.co/netflix/lev-uuid-2",
            "categories": {
                "location": "Los Gatos, CA",
                "commitment": "Contract",
            },
            "descriptionPlain": "Hands-on testing in our device testing lab.",
            "additionalPlain": "",
        },
    ]

    raw_items = await adapter.fetch_jobs(site_token="netflix", fixtures=fixtures)
    assert len(raw_items) == 2

    job1 = adapter.normalize(raw_items[0])
    assert job1.external_id == "lev-uuid-1"
    assert job1.company == "Netflix"
    assert job1.remote_type == RemoteType.REMOTE
    assert job1.employment_type == "Full time"
    assert "chaos engineering" in job1.description

    job2 = adapter.normalize(raw_items[1])
    assert job2.external_id == "lev-uuid-2"
    assert job2.remote_type == RemoteType.ON_SITE
    assert job2.employment_type == "Contract"


@pytest.mark.asyncio
async def test_unsupported_discovery_source(client: AsyncClient):
    res = await client.post("/api/v1/jobs/discover", json={"source_identifier": "non_existent_source"})
    assert res.status_code == 400
    assert "unsupported" in res.json()["detail"].lower()
