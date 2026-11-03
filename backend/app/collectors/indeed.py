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


class IndeedJobAdapter(BaseJobSourceAdapter):
    """
    Indeed India Job Adapter.

    Compliance & Integration Status:
    - Status: MANUAL_IMPORT_ONLY
    - The legacy Indeed Publisher Job Search API (api.indeed.com/ads/apisearch) has been
      permanently shut down and decommissioned.
    - Public web scraping is strictly restricted by Cloudflare and IP throttling, and unauthorized
      automated extraction violates Indeed Terms of Service.
    - Operates via inbound job alerts (email text / HTML digests) and structured manual imports (JSON).
    - Preserves deterministic career relevance evaluation and cross-source duplicate detection.
    """

    @property
    def source_identifier(self) -> str:
        return "indeed"

    @property
    def source_name(self) -> str:
        return "Indeed India"

    @property
    def source_type(self) -> str:
        return "aggregator"

    @property
    def integration_status(self) -> SourceIntegrationStatus:
        return SourceIntegrationStatus.MANUAL_IMPORT_ONLY

    @property
    def rate_limit_rpm(self) -> int:
        return 30

    def is_available(self) -> bool:
        return False

    def validate_configuration(self, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        return False, "Indeed India operates via manual JSON import and inbound email alerts; automated background polling is not supported."

    async def fetch_jobs(
        self,
        fixtures: Optional[List[Dict[str, Any]]] = None,
        manual_import_payload: Optional[Any] = None,
        email_payload: Optional[str] = None,
        **kwargs,
    ) -> List[RawJobData]:
        raw_items: List[RawJobData] = []

        # 1. Custom Fixtures (Test / QA harnesses)
        if fixtures:
            for idx, item in enumerate(fixtures):
                ext_id = str(item.get("id") or item.get("job_id") or item.get("jobkey") or f"indeed_fix_{idx+1}")
                raw_items.append(RawJobData(
                    source_identifier=self.source_identifier,
                    external_id=ext_id,
                    payload=item,
                ))
            return raw_items

        # 2. Manual Import / Alert Digest
        if manual_import_payload:
            if isinstance(manual_import_payload, list):
                for idx, item in enumerate(manual_import_payload):
                    ext_id = str(item.get("id") or item.get("job_id") or item.get("jobkey") or f"indeed_import_{idx+1}")
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

        # 3. Inbound Email Payload
        if email_payload:
            parsed_list = parse_email_alert_jobs(email_payload, self.source_identifier)
            for item in parsed_list:
                raw_items.append(RawJobData(
                    source_identifier=self.source_identifier,
                    external_id=str(item.get("id")),
                    payload=item,
                ))
            return raw_items

        return []

    def normalize(self, raw: RawJobData) -> NormalizedJob:
        p = raw.payload
        raw_title = p.get("title") or p.get("jobtitle") or p.get("role")
        if not raw_title or not str(raw_title).strip() or str(raw_title).strip().lower() in ("none", "null"):
            raise ValueError("Job listing is missing required title or role.")

        raw_company = p.get("company") or p.get("company_name") or p.get("employer")
        if not raw_company or not str(raw_company).strip() or str(raw_company).strip().lower() in ("none", "null"):
            raise ValueError("Job listing is missing required company name.")
        title = strip_html_tags(raw_title)
        company = strip_html_tags(raw_company)

        raw_url = str(p.get("url") or p.get("canonical_url") or f"https://in.indeed.com/viewjob?jk={raw.external_id}").strip()
        canonical_url = sanitize_canonical_url(raw_url, "in.indeed.com", raw.external_id)

        # Location and remote
        loc_str = str(p.get("formattedLocation") or p.get("location") or p.get("city") or "India")
        norm_loc, remote_type = parse_location_and_remote(loc_str)

        # Salary parsing
        sal_text = str(
            p.get("salary_text")
            or p.get("salary")
            or p.get("formattedSalary")
            or p.get("estimatedSalary")
            or ""
        )
        sal_min, sal_max, currency = parse_inr_salary_text(sal_text)

        # Experience parsing
        exp_text = str(p.get("experience_text") or p.get("experience") or "")
        exp_min, exp_max = parse_experience_text(exp_text)

        # Description
        raw_desc = str(p.get("description") or p.get("snippet") or f"{title} opportunity at {company} in {norm_loc}.")
        desc = strip_html_tags(raw_desc)

        # Posted date
        posted_at = None
        if p.get("date") or p.get("formattedRelativeTime"):
            posted_at = datetime.now(timezone.utc)

        workplace_type = "Remote" if remote_type == RemoteType.REMOTE else "On-site"

        return NormalizedJob(
            source_identifier=self.source_identifier,
            external_id=raw.external_id,
            title=title,
            company=company,
            canonical_url=canonical_url,
            location=norm_loc,
            remote_type=remote_type,
            employment_type="Full-time",
            description=desc,
            salary_min=sal_min,
            salary_max=sal_max,
            currency=currency,
            country="India",
            workplace_type=workplace_type,
            experience_min=exp_min,
            experience_max=exp_max,
            source_metadata={
                "parsed_from": "manual_import",
                "original_location": loc_str,
                "original_salary_text": sal_text,
                "original_experience_text": exp_text,
            },
            posted_at=posted_at,
            raw_payload=p,
        )
