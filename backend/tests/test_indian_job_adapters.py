import pytest
from backend.app.collectors.base import RawJobData, NormalizedJob
from backend.app.collectors import get_adapter, ADAPTER_REGISTRY
from backend.app.collectors.naukri import NaukriJobAdapter
from backend.app.collectors.instahyre import InstahyreJobAdapter
from backend.app.collectors.cutshort import CutshortJobAdapter
from backend.app.collectors.hirist import HiristJobAdapter
from backend.app.collectors.foundit import FounditJobAdapter
from backend.app.collectors.linkedin import LinkedInJobAdapter
from backend.app.collectors.indeed import IndeedJobAdapter
from backend.app.collectors.indian_parser_utils import (
    parse_inr_salary_text,
    parse_experience_text,
    parse_location_and_remote,
    parse_email_alert_jobs,
)
from backend.app.models.enums import RemoteType, SourceIntegrationStatus


class TestIndianParserUtils:
    def test_parse_inr_salary_lpa(self):
        min_v, max_v, curr = parse_inr_salary_text("15 - 25 Lacs P.A.")
        assert min_v == 15.0
        assert max_v == 25.0
        assert curr == "INR"

        min_v2, max_v2, curr2 = parse_inr_salary_text("24 LPA")
        assert min_v2 == 24.0
        assert max_v2 == 24.0
        assert curr2 == "INR"

    def test_parse_inr_salary_full_inr(self):
        min_v, max_v, curr = parse_inr_salary_text("₹ 18,00,000 - ₹ 30,00,000 P.A.")
        assert min_v == 18.0
        assert max_v == 30.0
        assert curr == "INR"

    def test_parse_inr_salary_monthly(self):
        min_v, max_v, curr = parse_inr_salary_text("50,000 - 80,000 / month")
        assert min_v == 6.0
        assert max_v == 9.6
        assert curr == "INR"

    def test_parse_inr_salary_undisclosed(self):
        min_v, max_v, curr = parse_inr_salary_text("Not Disclosed by Recruiter")
        assert min_v is None
        assert max_v is None
        assert curr == "INR"

    def test_parse_inr_salary_usd(self):
        min_v, max_v, curr = parse_inr_salary_text("$120,000 - $160,000")
        assert min_v == 120000.0
        assert max_v == 160000.0
        assert curr == "USD"

    def test_parse_experience(self):
        min_e, max_e = parse_experience_text("3 - 6 Yrs")
        assert min_e == 3.0
        assert max_e == 6.0

        min_e2, max_e2 = parse_experience_text("5+ Years")
        assert min_e2 == 5.0
        assert max_e2 is None

    def test_parse_location_and_remote(self):
        loc, rem = parse_location_and_remote("Bengaluru (Hybrid)")
        assert "Bengaluru" in loc
        assert rem == RemoteType.HYBRID

        loc2, rem2 = parse_location_and_remote("Remote, India")
        assert rem2 == RemoteType.REMOTE

        loc3, rem3 = parse_location_and_remote("Pune, Maharashtra")
        assert "Pune" in loc3
        assert rem3 == RemoteType.ON_SITE

    def test_parse_email_alert_jobs_from_text(self):
        sample_email = """
Role: Senior Full Stack Developer (Python / React)
Company: Swiggy
Location: Bengaluru (Remote)
Experience: 4-8 Yrs
Salary: 28 - 42 LPA
URL: https://www.naukri.com/job/101
Skills: Python, FastAPI, React, PostgreSQL

---

Role: AI Systems Engineer (LLM / RAG)
Company: PhonePe
Location: Bengaluru
Experience: 3-6 Yrs
Salary: 30 - 45 LPA
URL: https://www.naukri.com/job/102
Skills: Python, LangChain, Vectors, Redis
"""
        jobs = parse_email_alert_jobs(sample_email, "naukri")
        assert len(jobs) == 2
        assert "Swiggy" in jobs[0]["company"]
        assert "PhonePe" in jobs[1]["company"]
        assert "28 - 42 LPA" in jobs[0]["salary_text"]


class TestNaukriJobAdapter:
    def test_properties(self):
        adapter = NaukriJobAdapter()
        assert adapter.source_identifier == "naukri"
        assert adapter.source_type == "job_board"
        assert adapter.integration_status == SourceIntegrationStatus.MANUAL_IMPORT_ONLY
        assert adapter.is_available() is False

    @pytest.mark.asyncio
    async def test_fetch_jobs_without_params(self):
        adapter = NaukriJobAdapter()
        items = await adapter.fetch_jobs()
        assert items == []

    @pytest.mark.asyncio
    async def test_fetch_jobs_with_fixtures(self):
        adapter = NaukriJobAdapter()
        fixtures = [
            {
                "id": "nk_1",
                "title": "Lead Full Stack Engineer",
                "company": "Razorpay",
                "location": "Bengaluru (Hybrid)",
                "salary": "32 - 48 LPA",
                "experience": "5-9 Yrs",
                "skills": ["Python", "FastAPI", "React"],
                "url": "https://www.naukri.com/job/razorpay-lead-1",
            }
        ]
        items = await adapter.fetch_jobs(fixtures=fixtures)
        assert len(items) == 1
        normalized = adapter.normalize(items[0])
        assert normalized.title == "Lead Full Stack Engineer"
        assert normalized.company == "Razorpay"
        assert normalized.salary_min == 32.0
        assert normalized.salary_max == 48.0
        assert normalized.currency == "INR"
        assert normalized.remote_type == RemoteType.HYBRID


class TestInstahyreJobAdapter:
    def test_properties(self):
        adapter = InstahyreJobAdapter()
        assert adapter.source_identifier == "instahyre"
        assert adapter.source_type == "job_board"
        assert adapter.integration_status == SourceIntegrationStatus.MANUAL_IMPORT_ONLY

    def test_normalize(self):
        adapter = InstahyreJobAdapter()
        raw = RawJobData(
            source_identifier="instahyre",
            external_id="insta_001",
            payload={
                "title": "Staff Backend Engineer",
                "company": "CRED",
                "location": "Bengaluru",
                "salary": "40 - 55 LPA",
                "equity": "0.1% ESOPs",
                "tech_stack": ["Python", "Kafka", "Distributed Systems"],
                "url": "https://www.instahyre.com/job/cred-staff-1",
            },
        )
        norm = adapter.normalize(raw)
        assert norm.company == "CRED"
        assert norm.salary_min == 40.0
        assert norm.salary_max == 55.0
        assert norm.currency == "INR"
        assert norm.source_metadata.get("equity") == "0.1% ESOPs"


class TestCutshortJobAdapter:
    def test_properties(self):
        adapter = CutshortJobAdapter()
        assert adapter.source_identifier == "cutshort"
        assert adapter.source_type == "job_board"
        assert adapter.integration_status == SourceIntegrationStatus.MANUAL_IMPORT_ONLY

    def test_normalize(self):
        adapter = CutshortJobAdapter()
        raw = RawJobData(
            source_identifier="cutshort",
            external_id="cs_101",
            payload={
                "title": "Senior AI Engineer",
                "company": "Sarvam AI",
                "location": "Remote",
                "salary": "35 - 50 LPA",
                "tags": ["GenAI", "LLMs", "PyTorch", "FastAPI"],
                "url": "https://cutshort.io/job/sarvam-ai-101",
            },
        )
        norm = adapter.normalize(raw)
        assert norm.company == "Sarvam AI"
        assert norm.salary_min == 35.0
        assert norm.salary_max == 50.0
        assert norm.remote_type == RemoteType.REMOTE


class TestHiristJobAdapter:
    def test_properties(self):
        adapter = HiristJobAdapter()
        assert adapter.source_identifier == "hirist"
        assert adapter.source_type == "job_board"
        assert adapter.integration_status == SourceIntegrationStatus.CONFIGURATION_REQUIRED
        assert adapter.is_available() is False
        assert adapter.validate_configuration({}) == (False, "Requires configured RSS/Atom feed URL or category alert feed")
        assert adapter.validate_configuration({"rss_url": "https://example.com/rss.xml"}) == (True, None)

    def test_validate_configuration_ssrf_rejection(self):
        adapter = HiristJobAdapter()
        # Loopback rejection
        is_val1, msg1 = adapter.validate_configuration({"rss_url": "http://127.0.0.1:8000/feed"})
        assert is_val1 is False
        assert "Disallowed URL scheme" in (msg1 or "") or "Loopback" in (msg1 or "")

        # Cloud metadata rejection
        is_val2, msg2 = adapter.validate_configuration({"rss_url": "https://169.254.169.254/latest/meta-data/"})
        assert is_val2 is False
        assert "Cloud metadata" in (msg2 or "") or "restricted IP" in (msg2 or "")

        # Private IP rejection
        is_val3, msg3 = adapter.validate_configuration({"rss_url": "https://192.168.1.1/feed"})
        assert is_val3 is False
        assert "Private network" in (msg3 or "") or "restricted IP" in (msg3 or "")

    def test_normalize(self):
        adapter = HiristJobAdapter()
        raw = RawJobData(
            source_identifier="hirist",
            external_id="hirist_99",
            payload={
                "title": "Krutrim - Principal Engineer - AI Infrastructure",
                "location": "Bengaluru",
                "salary_text": "45 - 65 LPA",
                "experience_text": "6-10 Yrs",
                "url": "https://www.hirist.tech/job/krutrim-99",
                "description": "High performance inference serving and RAG platforms.",
            },
        )
        norm = adapter.normalize(raw)
        assert norm.company == "Krutrim"
        assert norm.title == "Principal Engineer - AI Infrastructure"
        assert norm.salary_min == 45.0
        assert norm.salary_max == 65.0


class TestFounditJobAdapter:
    def test_properties(self):
        adapter = FounditJobAdapter()
        assert adapter.source_identifier == "foundit"
        assert adapter.source_type == "job_board"
        assert adapter.integration_status == SourceIntegrationStatus.MANUAL_IMPORT_ONLY

    def test_normalize(self):
        adapter = FounditJobAdapter()
        raw = RawJobData(
            source_identifier="foundit",
            external_id="foundit_12",
            payload={
                "title": "Full Stack Engineer",
                "company": "Infosys FinTech",
                "location": "Hyderabad",
                "salary": "16 - 26 LPA",
                "experience": "4-7 Yrs",
                "url": "https://www.foundit.in/job/12",
            },
        )
        norm = adapter.normalize(raw)
        assert norm.company == "Infosys FinTech"
        assert norm.salary_min == 16.0
        assert norm.salary_max == 26.0


class TestLinkedInJobAdapter:
    def test_properties(self):
        adapter = LinkedInJobAdapter()
        assert adapter.source_identifier == "linkedin"
        assert adapter.source_type == "aggregator"
        assert adapter.integration_status == SourceIntegrationStatus.AUTHORIZATION_REQUIRED
        assert adapter.is_available() is False

    def test_validate_configuration(self):
        adapter = LinkedInJobAdapter()
        is_valid, msg = adapter.validate_configuration({})
        assert is_valid is False
        assert "Requires LinkedIn" in (msg or "")

        is_valid2, _ = adapter.validate_configuration({"access_token": "mock_token"})
        assert is_valid2 is True


class TestIndeedJobAdapter:
    def test_properties(self):
        adapter = IndeedJobAdapter()
        assert adapter.source_identifier == "indeed"
        assert adapter.source_type == "aggregator"
        assert adapter.integration_status == SourceIntegrationStatus.MANUAL_IMPORT_ONLY
        assert adapter.is_available() is False

    def test_validate_configuration(self):
        adapter = IndeedJobAdapter()
        is_valid, msg = adapter.validate_configuration({})
        assert is_valid is False
        assert "automated background polling is not supported" in (msg or "")

    def test_fetch_jobs_manual_only(self):
        import asyncio
        adapter = IndeedJobAdapter()
        # Automated poll without payload must return empty
        res = asyncio.run(adapter.fetch_jobs())
        assert res == []

    def test_normalize_inr_range(self):
        adapter = IndeedJobAdapter()
        raw = RawJobData(
            source_identifier="indeed",
            external_id="indeed_jk123",
            payload={
                "title": "Software Development Engineer II",
                "company": "Amazon",
                "location": "Hyderabad, Telangana",
                "salary_text": "₹25,00,000 - ₹40,00,000 a year",
                "url": "https://in.indeed.com/viewjob?jk=indeed_jk123",
            },
        )
        norm = adapter.normalize(raw)
        assert norm.company == "Amazon"
        assert norm.salary_min == 25.0
        assert norm.salary_max == 40.0
        assert norm.currency == "INR"


def test_adapter_registry_contains_all_sources():
    expected_sources = {
        "synthetic",
        "greenhouse",
        "lever",
        "naukri",
        "instahyre",
        "cutshort",
        "hirist",
        "foundit",
        "linkedin",
        "indeed",
    }
    assert expected_sources.issubset(set(ADAPTER_REGISTRY.keys()))
    for src in expected_sources:
        adapter = get_adapter(src)
        assert adapter.source_identifier == src

