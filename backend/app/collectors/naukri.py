import re
import html
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from backend.app.collectors.base import BaseJobSourceAdapter, RawJobData, NormalizedJob
from backend.app.collectors.indian_parser_utils import (
    parse_inr_salary_text,
    parse_experience_text,
    parse_location_and_remote,
    parse_email_alert_jobs,
    strip_html_tags,
    sanitize_canonical_url,
)
from backend.app.models.enums import RemoteType, SourceIntegrationStatus
from backend.app.core.logging import logger


class NaukriJobAdapter(BaseJobSourceAdapter):
    """
    Naukri.com Job Adapter.

    Compliance & Integration Status:
    - Status: MANUAL_IMPORT_ONLY
    - Naukri does not provide a public candidate search API.
    - RMS (Recruiter Management System) is an enterprise-only service.
    - Web search scraping is strictly blocked by Akamai & Cloudflare Bot Management and prohibited by robots.txt.
    - Operates via inbound job alert email ingestion and structured manual JSON/text import.
    """

    @property
    def source_identifier(self) -> str:
        return "naukri"

    @property
    def source_name(self) -> str:
        return "Naukri.com"

    @property
    def source_type(self) -> str:
        return "job_board"

    @property
    def integration_status(self) -> SourceIntegrationStatus:
        return SourceIntegrationStatus.MANUAL_IMPORT_ONLY

    @property
    def rate_limit_rpm(self) -> int:
        return 15

    def is_available(self) -> bool:
        return False

    def validate_configuration(self, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        return True, None

    async def fetch_jobs(
        self,
        fixtures: Optional[List[Dict[str, Any]]] = None,
        manual_import_payload: Optional[Any] = None,
        email_payload: Optional[str] = None,
        **kwargs,
    ) -> List[RawJobData]:
        """
        Fetches or ingests jobs. In absence of manual imports or fixtures,
        returns empty list with explicit audit notice.
        """
        raw_items: List[RawJobData] = []

        if fixtures:
            for idx, item in enumerate(fixtures):
                ext_id = str(item.get("id") or item.get("job_id") or f"naukri_fix_{idx+1}")
                raw_items.append(RawJobData(
                    source_identifier=self.source_identifier,
                    external_id=ext_id,
                    payload=item,
                ))
            return raw_items

        if manual_import_payload:
            if isinstance(manual_import_payload, list):
                for idx, item in enumerate(manual_import_payload):
                    ext_id = str(item.get("id") or item.get("job_id") or f"naukri_import_{idx+1}")
                    raw_items.append(RawJobData(
                        source_identifier=self.source_identifier,
                        external_id=ext_id,
                        payload=item,
                    ))
                return raw_items
            elif isinstance(manual_import_payload, str):
                parsed_list = parse_email_alert_jobs(manual_import_payload, self.source_identifier)
                for item in parsed_list:
                    raw_items.append(RawJobData(
                        source_identifier=self.source_identifier,
                        external_id=str(item.get("id")),
                        payload=item,
                    ))
                return raw_items

        if email_payload:
            parsed_list = parse_email_alert_jobs(email_payload, self.source_identifier)
            for item in parsed_list:
                raw_items.append(RawJobData(
                    source_identifier=self.source_identifier,
                    external_id=str(item.get("id")),
                    payload=item,
                ))
            return raw_items

        logger.info(
            "[Naukri] Automated crawling is restricted by Akamai/Cloudflare protections. "
            "Ingest listings via Email Alerts or Manual Import."
        )
        return []

    def normalize(self, raw: RawJobData) -> NormalizedJob:
        p = raw.payload
        raw_title = p.get("title") or p.get("role") or p.get("designation")
        if not raw_title or not str(raw_title).strip() or str(raw_title).strip().lower() in ("none", "null"):
            raise ValueError("Job listing is missing required title or role.")
        title = strip_html_tags(str(raw_title).strip())

        raw_company = p.get("company") or p.get("company_name") or p.get("employer")
        if not raw_company or not str(raw_company).strip() or str(raw_company).strip().lower() in ("none", "null"):
            raise ValueError("Job listing is missing required company name.")
        company = strip_html_tags(str(raw_company).strip())
        canonical_url = str(p.get("url") or p.get("canonical_url") or p.get("apply_url") or f"https://www.naukri.com/job/{raw.external_id}").strip()

        # Location and remote
        loc_str = str(p.get("location") or p.get("city") or "India")
        location, remote_type = parse_location_and_remote(loc_str)
        if "remote_type" in p and isinstance(p["remote_type"], RemoteType):
            remote_type = p["remote_type"]

        # Compensation
        sal_min, sal_max, currency = parse_inr_salary_text(
            p.get("salary_text") or p.get("salary") or p.get("ctc")
        )
        if p.get("salary_min") is not None:
            sal_min = float(p["salary_min"])
        if p.get("salary_max") is not None:
            sal_max = float(p["salary_max"])
        if p.get("currency"):
            currency = p["currency"]

        # Experience
        exp_min, exp_max = parse_experience_text(p.get("experience_text") or p.get("experience") or p.get("exp"))
        if p.get("experience_min") is not None:
            exp_min = float(p["experience_min"])
        if p.get("experience_max") is not None:
            exp_max = float(p["experience_max"])

        # Description
        description = str(p.get("description") or p.get("job_description") or f"{title} at {company} in {location}").strip()
        skills = p.get("skills") or p.get("key_skills") or []
        if isinstance(skills, list) and skills:
            description += f"\n\nKey Skills: {', '.join(skills)}"

        return NormalizedJob(
            source_identifier=self.source_identifier,
            external_id=raw.external_id,
            title=title,
            company=company,
            canonical_url=canonical_url,
            location=location,
            remote_type=remote_type,
            employment_type=str(p.get("employment_type") or "Full-time"),
            description=description,
            salary_min=sal_min,
            salary_max=sal_max,
            currency=currency,
            country="India",
            workplace_type=remote_type.value,
            experience_min=exp_min,
            experience_max=exp_max,
            source_metadata={
                "source": "naukri",
                "experience_range": f"{exp_min or 0}-{exp_max or ''} Yrs",
                "raw_skills": skills,
            },
            posted_at=datetime.now(timezone.utc),
            raw_payload=p,
        )

