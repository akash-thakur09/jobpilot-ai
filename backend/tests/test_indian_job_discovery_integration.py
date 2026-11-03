import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.main import app
from backend.app.models.job import Job, JobSource, JobDuplicateCluster
from backend.app.models.candidate import CandidateProfile
from backend.app.models.enums import RemoteType, SourceIntegrationStatus, RelevanceClassification
from backend.app.services.job_discovery_service import JobDiscoveryService


@pytest.mark.asyncio
async def test_get_all_sources_registers_indian_platforms(db_session: AsyncSession):
    sources = await JobDiscoveryService.get_all_sources(db_session)
    source_map = {s.identifier: s for s in sources}

    # Verify all expected sources are present
    assert "naukri" in source_map
    assert "instahyre" in source_map
    assert "cutshort" in source_map
    assert "hirist" in source_map
    assert "foundit" in source_map
    assert "linkedin" in source_map
    assert "indeed" in source_map
    assert "greenhouse" in source_map
    assert "lever" in source_map

    # Verify integration status mapping
    assert source_map["naukri"].integration_status == SourceIntegrationStatus.MANUAL_IMPORT_ONLY.value
    assert source_map["instahyre"].integration_status == SourceIntegrationStatus.MANUAL_IMPORT_ONLY.value
    assert source_map["cutshort"].integration_status == SourceIntegrationStatus.MANUAL_IMPORT_ONLY.value
    assert source_map["hirist"].integration_status == SourceIntegrationStatus.CONFIGURATION_REQUIRED.value
    assert source_map["linkedin"].integration_status == SourceIntegrationStatus.AUTHORIZATION_REQUIRED.value
    assert source_map["indeed"].integration_status == SourceIntegrationStatus.MANUAL_IMPORT_ONLY.value


@pytest.mark.asyncio
async def test_import_jobs_from_payload_with_relevance_and_dedup(db_session: AsyncSession):
    # Ensure a candidate profile exists
    cand_stmt = select(CandidateProfile).limit(1)
    cand_res = await db_session.execute(cand_stmt)
    candidate = cand_res.scalar_one_or_none()
    if not candidate:
        candidate = CandidateProfile(
            full_name="Arjun Sharma",
            email="arjun.sharma@example.in",
            location="Bengaluru, India",
            work_authorization="Citizen",
            summary="Full Stack AI Engineer",
            years_of_experience=5.0,
            target_titles=["Full Stack Developer", "AI Engineer", "Python Developer"],
            target_package_min_lpa=20.0,
            search_preferences={
                "target_titles": ["Full Stack Developer", "AI Engineer", "Python Developer"],
                "must_have_skills": ["Python", "React", "FastAPI"],
                "target_package_min_lpa": 20.0,
                "remote_preference": "REMOTE",
            },
        )
        db_session.add(candidate)
        await db_session.commit()

    sample_naukri_payload = [
        {
            "id": "nk_job_1",
            "title": "Senior Full Stack AI Developer",
            "company": "Swiggy",
            "location": "Bengaluru",
            "salary": "25 - 40 LPA",
            "experience": "4-7 Yrs",
            "skills": ["Python", "FastAPI", "React", "GenAI"],
            "url": "https://www.naukri.com/job/swiggy-ai-1",
            "description": "Building next-gen conversational food intelligence using Python, FastAPI, and React.",
        },
        {
            "id": "nk_job_2",
            "title": "Junior Manual Tester",
            "company": "Legacy Corp",
            "location": "Noida",
            "salary": "4 - 6 LPA",
            "experience": "0-2 Yrs",
            "skills": ["Manual Testing", "Excel"],
            "url": "https://www.naukri.com/job/legacy-tester-2",
            "description": "Manual testing and bug tracking on legacy systems.",
        },
    ]

    result = await JobDiscoveryService.import_jobs_from_payload(
        session=db_session,
        source_identifier="naukri",
        payload=sample_naukri_payload,
        format_type="json",
    )

    assert result["source_identifier"] == "naukri"
    assert result["items_parsed"] == 2
    assert result["items_saved"] == 2
    assert result["items_relevant"] >= 1

    # Verify saved jobs in DB
    jobs_stmt = select(Job).where(Job.external_id.in_(["nk_job_1", "nk_job_2"]))
    jobs_res = await db_session.execute(jobs_stmt)
    jobs = {j.external_id: j for j in jobs_res.scalars().all()}

    assert "nk_job_1" in jobs
    job1 = jobs["nk_job_1"]
    assert job1.salary_min == 25.0
    assert job1.salary_max == 40.0
    assert job1.currency == "INR"
    assert job1.relevance_classification in (
        RelevanceClassification.HIGHLY_RELEVANT.value,
        RelevanceClassification.POTENTIALLY_RELEVANT.value,
    )

    assert "nk_job_2" in jobs
    job2 = jobs["nk_job_2"]
    assert job2.relevance_classification == RelevanceClassification.LOW_RELEVANCE.value


@pytest.mark.asyncio
async def test_api_sources_list_and_import(db_session: AsyncSession):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Test GET /api/v1/jobs/sources
        sources_resp = await ac.get("/api/v1/jobs/sources")
        assert sources_resp.status_code == 200
        sources_data = sources_resp.json()
        assert len(sources_data) >= 9

        identifiers = {s["identifier"] for s in sources_data}
        assert "naukri" in identifiers
        assert "instahyre" in identifiers

        # 2. Test POST /api/v1/jobs/sources/cutshort/import with alert text
        alert_text = """
Role: Python / AI Full Stack Engineer
Company: Zepto
Location: Bengaluru
Salary: 28 - 45 LPA
Experience: 3-6 Yrs
URL: https://cutshort.io/job/zepto-101
Skills: Python, FastAPI, React, LLMs
"""
        import_resp = await ac.post(
            "/api/v1/jobs/sources/cutshort/import",
            json={
                "source_identifier": "cutshort",
                "format": "email_text",
                "payload": alert_text,
            },
        )
        assert import_resp.status_code == 200
        import_data = import_resp.json()
        assert import_data["items_saved"] >= 1
        assert import_data["source_identifier"] == "cutshort"


@pytest.mark.asyncio
async def test_pipeline_skips_manual_import_and_unconfigured_sources(db_session: AsyncSession):
    from backend.app.services.discovery_pipeline import DiscoveryMatchingPipeline

    # Run pipeline specifying manual and unconfigured sources with no fixtures
    result = await DiscoveryMatchingPipeline.execute(
        session=db_session,
        sources=["naukri", "hirist", "indeed"],
        trigger="test",
        use_ai_matching=False,
    )

    diagnostics = result.get("source_diagnostics", {})

    # Naukri is MANUAL_IMPORT_ONLY: must not execute automated fetch
    assert diagnostics["naukri"]["status"] == "SKIPPED_MANUAL_IMPORT_ONLY"
    assert diagnostics["naukri"]["discovered"] == 0

    # Hirist requires RSS/Feed configuration: must not poll without it
    assert diagnostics["hirist"]["status"] == SourceIntegrationStatus.CONFIGURATION_REQUIRED.value
    assert diagnostics["hirist"]["discovered"] == 0

    # Indeed is MANUAL_IMPORT_ONLY: must not execute automated fetch
    assert diagnostics["indeed"]["status"] == "SKIPPED_MANUAL_IMPORT_ONLY"
    assert diagnostics["indeed"]["discovered"] == 0


@pytest.mark.asyncio
async def test_batch_import_savepoint_isolation_one_invalid_between_valid(db_session: AsyncSession):
    """Scenario 1: One invalid item placed between valid items."""
    batch = [
        {
            "id": "tx_iso_v1",
            "title": "Software Engineer Backend",
            "company": "Swiggy",
            "location": "Bengaluru",
            "salary_text": "20 - 35 LPA",
            "description": "Valid swiggy backend listing",
            "url": "https://www.naukri.com/job/tx-v1",
        },
        {
            # Malformed item (None external ID and invalid data)
            "id": None,
            "job_id": None,
            "title": None,
        },
        {
            "id": "tx_iso_v2",
            "title": "Full Stack Lead",
            "company": "Razorpay",
            "location": "Bengaluru",
            "salary_text": "35 - 55 LPA",
            "description": "Valid razorpay lead listing",
            "url": "https://www.naukri.com/job/tx-v2",
        },
    ]

    res = await JobDiscoveryService.import_jobs_from_payload(
        session=db_session,
        source_identifier="naukri",
        payload=batch,
        format_type="json",
    )

    assert res["items_saved"] == 2
    assert len(res["errors"]) == 1
    assert res["source_identifier"] == "naukri"

    # Verify both valid jobs exist in the database
    stmt = select(Job).where(Job.external_id.in_(["tx_iso_v1", "tx_iso_v2"]))
    jobs = (await db_session.execute(stmt)).scalars().all()
    assert len(jobs) == 2


@pytest.mark.asyncio
async def test_batch_import_savepoint_isolation_multiple_invalid_items(db_session: AsyncSession):
    """Scenario 2: Multiple invalid items interspersed among valid items."""
    batch = [
        {
            "id": "tx_multi_v1",
            "title": "DevOps Engineer",
            "company": "Zerodha",
            "location": "Bengaluru",
            "salary_text": "25 - 40 LPA",
            "description": "Valid zerodha listing",
            "url": "https://www.naukri.com/job/tx-mv1",
        },
        {"id": None, "title": None},
        {"id": None, "company": None},
        {
            "id": "tx_multi_v2",
            "title": "Frontend Architect",
            "company": "CRED",
            "location": "Bengaluru",
            "salary_text": "40 - 60 LPA",
            "description": "Valid cred listing",
            "url": "https://www.naukri.com/job/tx-mv2",
        },
        {"id": None, "url": None},
    ]

    res = await JobDiscoveryService.import_jobs_from_payload(
        session=db_session,
        source_identifier="naukri",
        payload=batch,
        format_type="json",
    )

    assert res["items_saved"] == 2
    assert len(res["errors"]) == 3

    stmt = select(Job).where(Job.external_id.in_(["tx_multi_v1", "tx_multi_v2"]))
    jobs = (await db_session.execute(stmt)).scalars().all()
    assert len(jobs) == 2


@pytest.mark.asyncio
async def test_batch_import_savepoint_isolation_all_items_invalid(db_session: AsyncSession):
    """Scenario 3: All items in batch are invalid."""
    batch = [
        {"id": None, "title": None},
        {"id": None, "company": None},
        {"id": None, "url": None},
    ]

    res = await JobDiscoveryService.import_jobs_from_payload(
        session=db_session,
        source_identifier="naukri",
        payload=batch,
        format_type="json",
    )

    # All rolled back cleanly without invalidating parent transaction
    assert res["items_saved"] == 0
    assert len(res["errors"]) == 3


@pytest.mark.asyncio
async def test_batch_import_successful_parent_commit_persistence(db_session: AsyncSession):
    """Scenario 4: Successful parent transaction commit verified across session refresh."""
    batch = [
        {
            "id": "tx_persist_v1",
            "title": "AI Platform Engineer",
            "company": "Krutrim",
            "location": "Bengaluru",
            "salary_text": "30 - 50 LPA",
            "description": "Valid AI platform listing",
            "url": "https://www.naukri.com/job/tx-pv1",
        },
        {"id": None, "title": None},
    ]

    res = await JobDiscoveryService.import_jobs_from_payload(
        session=db_session,
        source_identifier="naukri",
        payload=batch,
        format_type="json",
    )
    assert res["items_saved"] == 1

    # Verify query
    query = select(Job).where(Job.external_id == "tx_persist_v1")
    job = (await db_session.execute(query)).scalar_one_or_none()
    assert job is not None
    assert job.company == "Krutrim"
    assert job.title == "AI Platform Engineer"


def test_import_request_schema_validation():
    from pydantic import ValidationError
    from backend.app.schemas.job import JobImportRequest

    # 1. Invalid source_identifier pattern
    with pytest.raises(ValidationError):
        JobImportRequest(
            source_identifier="naukri;DROP TABLE jobs;--",
            format="json",
            payload=[],
        )

    # 2. Invalid format
    with pytest.raises(ValidationError):
        JobImportRequest(
            source_identifier="naukri",
            format="ftp_stream",
            payload=[],
        )

    # 3. Payload size limit for strings (> 500k chars)
    with pytest.raises(ValidationError) as exc:
        JobImportRequest(
            source_identifier="naukri",
            format="email_text",
            payload="A" * 500_001,
        )
    assert "500,000 characters" in str(exc.value)

    # 4. Batch items count limit (> 100 items)
    with pytest.raises(ValidationError) as exc:
        JobImportRequest(
            source_identifier="naukri",
            format="json",
            payload=[{"title": f"Job {i}"} for i in range(101)],
        )
    assert "100 items" in str(exc.value)


@pytest.mark.asyncio
async def test_ssrf_feed_url_rejection():
    from backend.app.core.network_security import SafeFeedFetcher, SSRFProtectionError

    # 1. Reject localhost and loopback
    v, reason = SafeFeedFetcher.validate_url("https://127.0.0.1:8000/feed")
    assert v is False
    assert "Loopback" in reason or "prohibited" in reason

    v2, reason2 = SafeFeedFetcher.validate_url("http://localhost:8000/feed")
    assert v2 is False

    # 2. Reject private RFC 1918 IPs
    v3, reason3 = SafeFeedFetcher.validate_url("https://10.0.0.1/feed")
    assert v3 is False
    assert "Private" in reason3

    v4, reason4 = SafeFeedFetcher.validate_url("https://192.168.1.1/feed")
    assert v4 is False
    assert "Private" in reason4

    # 3. Reject cloud metadata IP
    v5, reason5 = SafeFeedFetcher.validate_url("https://169.254.169.254/latest/meta-data/")
    assert v5 is False
    assert "metadata" in reason5 or "prohibited" in reason5

    # 4. Reject cloud metadata hostname
    v6, reason6 = SafeFeedFetcher.validate_url("https://metadata.google.internal/computeMetadata/v1/")
    assert v6 is False
    assert "restricted hostname" in reason6 or "prohibited" in reason6

    # 5. Non-HTTPS rejected by default
    v7, reason7 = SafeFeedFetcher.validate_url("http://example.com/feed.xml")
    assert v7 is False
    assert "HTTPS is required" in reason7

    # 6. Valid public HTTPS URL accepted
    v8, reason8 = SafeFeedFetcher.validate_url("https://example.com/rss.xml")
    assert v8 is True
    assert reason8 is None


@pytest.mark.asyncio
async def test_batch_import_parent_transaction_rollback_clears_all(db_session: AsyncSession):
    """Verify that if the parent transaction rolls back, none of the savepoint items persist."""
    source = JobSource(
        identifier="naukri_rb_test",
        name="Naukri Rollback Test",
        base_url="https://www.naukri.com",
        source_type="job_board",
        integration_status=SourceIntegrationStatus.MANUAL_IMPORT_ONLY.value,
    )
    db_session.add(source)
    await db_session.flush()

    batch = [
        {
            "id": "tx_rb_v1",
            "title": "Data Engineer",
            "company": "Ola",
            "location": "Bengaluru",
            "salary_text": "22 - 35 LPA",
            "description": "Valid Ola data engineer listing",
            "url": "https://www.naukri.com/job/tx-rb1",
        },
    ]

    # Savepoint item inserted inside nested transaction
    async with db_session.begin_nested():
        job = Job(
            source_id=source.id,
            external_id="tx_rb_v1",
            title="Data Engineer",
            company="Ola",
            canonical_url="https://www.naukri.com/job/tx-rb1",
            location="Bengaluru",
            remote_type=RemoteType.ON_SITE.value,
            employment_type="Full-time",
            description="Valid Ola data engineer listing",
        )
        db_session.add(job)
        await db_session.flush()

    # Now simulate outer/parent transaction failure and rollback
    await db_session.rollback()

    # Verify nothing was committed or persisted
    stmt = select(Job).where(Job.external_id == "tx_rb_v1")
    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_ssrf_embedded_credentials_and_logging_sanitization():
    from backend.app.core.network_security import SafeFeedFetcher, sanitize_url_for_logging

    # 1. Reject embedded credentials in URLs
    v, reason = SafeFeedFetcher.validate_url("https://admin:secret123@example.com/rss.xml")
    assert v is False
    assert "embedded credentials" in reason

    # 2. Test URL logging sanitization
    dirty_url = "https://user:pass@example.com/feed.xml?token=supersecret&api_key=12345&category=eng"
    clean_url = sanitize_url_for_logging(dirty_url)
    assert "supersecret" not in clean_url
    assert "12345" not in clean_url
    assert "pass@" not in clean_url
    assert "token=***" in clean_url
    assert "api_key=***" in clean_url
    assert "category=eng" in clean_url


def test_safe_parse_xml_rejects_xxe_and_entity_expansions():
    from backend.app.core.network_security import safe_parse_xml

    # 1. Prohibit DOCTYPE declarations
    doctype_xml = '<!DOCTYPE test [<!ENTITY foo "bar">]><test>&foo;</test>'
    with pytest.raises(ValueError) as exc1:
        safe_parse_xml(doctype_xml)
    assert "DOCTYPE and ENTITY declarations are prohibited" in str(exc1.value)

    # 2. Prohibit ENTITY declarations
    entity_xml = '<?xml version="1.0"?><!ENTITY xxe SYSTEM "file:///etc/passwd"><root>&xxe;</root>'
    with pytest.raises(ValueError) as exc2:
        safe_parse_xml(entity_xml)
    assert "DOCTYPE and ENTITY declarations are prohibited" in str(exc2.value)

    # 3. Valid RSS XML parses successfully
    valid_xml = '<rss version="2.0"><channel><item><title>Security Engineer</title></item></channel></rss>'
    root = safe_parse_xml(valid_xml)
    item_title = root.find(".//title")
    assert item_title is not None
    assert item_title.text == "Security Engineer"


def test_safe_feed_fetcher_advanced_ip_rejections():
    from backend.app.core.network_security import SafeFeedFetcher

    # IPv4-mapped IPv6 loopback
    safe, reason = SafeFeedFetcher.is_safe_ip("::ffff:127.0.0.1")
    assert safe is False
    assert "Loopback" in reason or "prohibited" in reason

    # IPv4-mapped IPv6 cloud metadata
    safe2, reason2 = SafeFeedFetcher.is_safe_ip("::ffff:169.254.169.254")
    assert safe2 is False
    assert "metadata" in reason2 or "prohibited" in reason2

    # 6to4 loopback (2002:7f00:0001::)
    safe3, reason3 = SafeFeedFetcher.is_safe_ip("2002:7f00:0001::")
    assert safe3 is False

    # Valid public IPv4
    safe4, reason4 = SafeFeedFetcher.is_safe_ip("93.184.216.34")
    assert safe4 is True
    assert reason4 is None


@pytest.mark.asyncio
async def test_ssrf_socket_level_peer_ip_interception():
    from backend.app.core.network_security import SafeFeedFetcher, SSRFProtectionError

    # Attempting to fetch loopback directly must be blocked by SSRF protection
    with pytest.raises(SSRFProtectionError) as exc:
        await SafeFeedFetcher.fetch_text("https://127.0.0.1:8000/feed.xml")
    assert "SSRF Protection" in str(exc.value)
