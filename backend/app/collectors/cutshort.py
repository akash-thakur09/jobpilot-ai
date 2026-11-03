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


class CutshortJobAdapter(BaseJobSourceAdapter):
    """
    Cutshort Job Adapter.

    Compliance & Integration Status:
    - Status: MANUAL_IMPORT_ONLY
    - Developer-first talent network (Voila AI).
    - Internal APIs require browser session fingerprinting and CSRF authentication.
    - Operates via inbound opportunity alert digests and structured manual imports.
    """

    @property
    def source_identifier(self) -> str:
        return "cutshort"

    @property
    def source_name(self) -> str:
        return "Cutshort"

    @property
    def source_type(self) -> str:
        return "job_board"

    @property
    def integration_status(self) -> SourceIntegrationStatus:
        return SourceIntegrationStatus.MANUAL_IMPORT_ONLY

    @property
    def rate_limit_rpm(self) -> int:
        return 20

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
        raw_items: List[RawJobData] = []

        if fixtures:
            for idx, item in enumerate(fixtures):
                ext_id = str(item.get("id") or item.get("job_id") or f"cutshort_fix_{idx+1}")
                raw_items.append(RawJobData(
                    source_identifier=self.source_identifier,
                    external_id=ext_id,
                    payload=item,
                ))
            return raw_items

        if manual_import_payload:
            if isinstance(manual_import_payload, list):
                for idx, item in enumerate(manual_import_payload):
                    ext_id = str(item.get("id") or item.get("job_id") or f"cutshort_import_{idx+1}")
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
            "[Cutshort] Platform restricts direct automated scraping. "
            "Ingest listings via Fast-Track Opportunity Alerts or Manual Import."
        )
        return []

    def normalize(self, raw: RawJobData) -> NormalizedJob:
        p = raw.payload
        title = str(p.get("title") or p.get("role") or "Full Stack Developer").strip()
        company = str(p.get("company") or p.get("company_name") or "Product Co").strip()
        canonical_url = str(p.get("url") or p.get("canonical_url") or f"https://cutshort.io/job/{raw.external_id}").strip()

        # Location and remote
        loc_str = str(p.get("location") or p.get("city") or "Remote")
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
        description = str(p.get("description") or f"{title} at {company} in {location}").strip()
        skills = p.get("skills") or p.get("tags") or []
        if isinstance(skills, list) and skills:
            description += f"\n\nSkills: {', '.join(skills)}"

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
                "source": "cutshort",
                "skills": skills,
            },
            posted_at=datetime.now(timezone.utc),
            raw_payload=p,
        )

