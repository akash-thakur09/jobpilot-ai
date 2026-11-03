import re
import html
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from backend.app.collectors.base import BaseJobSourceAdapter, RawJobData, NormalizedJob, SourceRateLimitException
from backend.app.collectors.indian_parser_utils import (
    parse_inr_salary_text,
    parse_experience_text,
    parse_location_and_remote,
    parse_email_alert_jobs,
    strip_html_tags,
    sanitize_canonical_url,
)
from backend.app.models.enums import RemoteType, SourceIntegrationStatus
from backend.app.core.network_security import SafeFeedFetcher, SSRFProtectionError, safe_parse_xml
from backend.app.core.logging import logger


class HiristJobAdapter(BaseJobSourceAdapter):
    """
    Hirist (Tech-focused vertical of Info Edge / iimjobs) Job Adapter.

    Compliance & Integration Status:
    - Status: CONFIGURATION_REQUIRED (requires configured RSS / XML feed URL)
    - Hirist web interface uses a JavaScript SPA without an active default public XML endpoint.
    - Operates via custom configured RSS feed URLs, inbound alert digests, and structured manual imports.
    - Protected against SSRF: feed URLs are restricted to HTTPS, validated against loopback, private IPs,
      and cloud metadata destinations with strict redirect revalidation.
    """

    DEFAULT_CATEGORY = "software-engineer"

    @property
    def source_identifier(self) -> str:
        return "hirist"

    @property
    def source_name(self) -> str:
        return "Hirist"

    @property
    def source_type(self) -> str:
        return "job_board"

    @property
    def integration_status(self) -> SourceIntegrationStatus:
        return SourceIntegrationStatus.CONFIGURATION_REQUIRED

    @property
    def rate_limit_rpm(self) -> int:
        return 30

    def is_available(self) -> bool:
        return False

    def validate_configuration(self, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        feed = config.get("rss_url") or config.get("feed_url")
        if not feed:
            return False, "Requires configured RSS/Atom feed URL or category alert feed"
        is_safe, reason = SafeFeedFetcher.validate_url(feed)
        if not is_safe:
            return False, f"Invalid feed URL: {reason}"
        return True, None

    async def fetch_jobs(
        self,
        rss_url: Optional[str] = None,
        feed_url: Optional[str] = None,
        category: Optional[str] = None,
        fixtures: Optional[List[Dict[str, Any]]] = None,
        manual_import_payload: Optional[Any] = None,
        email_payload: Optional[str] = None,
        timeout_seconds: float = 15.0,
        **kwargs,
    ) -> List[RawJobData]:
        raw_items: List[RawJobData] = []

        # 1. Custom Fixtures
        if fixtures:
            for idx, item in enumerate(fixtures):
                ext_id = str(item.get("id") or item.get("job_id") or f"hirist_fix_{idx+1}")
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
                    ext_id = str(item.get("id") or item.get("job_id") or f"hirist_import_{idx+1}")
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

        # 3. Live RSS / Atom Feed Fetching with SSRF protection
        target_feed = rss_url or feed_url
        if target_feed:
            try:
                content_type, body_text = await SafeFeedFetcher.fetch_text(
                    url=target_feed,
                    timeout_seconds=timeout_seconds,
                    headers={"User-Agent": "JobPilot-AI-Agent/2.0 (Candidate Job Assistant)"},
                )

                if "html" in content_type and not body_text.strip().startswith("<?xml"):
                    logger.warning(f"[Hirist] Feed endpoint '{target_feed}' returned HTML instead of XML.")
                    return []

                # Parse XML safely without DOCTYPE/ENTITY (XXE prevention)
                root = safe_parse_xml(body_text)
                items = root.findall(".//item")
                for idx, itm in enumerate(items):
                    title = itm.findtext("title", "Software Engineer")
                    link = itm.findtext("link", f"https://www.hirist.tech/job/{idx+1}")
                    desc = itm.findtext("description", "")
                    pub_date = itm.findtext("pubDate", "")
                    ext_id = link.rstrip("/").split("/")[-1] or f"hirist_rss_{idx+1}"

                    payload = {
                        "id": ext_id,
                        "title": title,
                        "url": link,
                        "description": desc,
                        "pub_date": pub_date,
                    }
                    raw_items.append(RawJobData(
                        source_identifier=self.source_identifier,
                        external_id=ext_id,
                        payload=payload,
                    ))
                return raw_items
            except SourceRateLimitException:
                raise
            except SSRFProtectionError as ssrf_err:
                logger.error(f"[Hirist] SSRF Protection blocked feed request: {ssrf_err}")
                raise
            except (ET.ParseError, ValueError) as pe:
                logger.warning(f"[Hirist] XML parsing or security failure from feed '{target_feed}': {pe}")
            except Exception as e:
                logger.warning(f"[Hirist] RSS feed fetch error from '{target_feed}': {e}")

        logger.info("[Hirist] No active RSS feed configured; use category feed URL or manual import.")
        return []

    def normalize(self, raw: RawJobData) -> NormalizedJob:
        p = raw.payload
        raw_title = str(p.get("title") or p.get("role") or "Software Engineer").strip()

        # Often RSS titles are formatted as: "Company - Job Title - Location" or "Job Title at Company"
        title = raw_title
        company = str(p.get("company") or p.get("company_name") or "Tech Co").strip()
        if " - " in raw_title and company == "Tech Co":
            parts = raw_title.split(" - ", 1)
            if len(parts) >= 2:
                company = parts[0].strip()
                title = parts[1].strip()

        title = strip_html_tags(title)
        company = strip_html_tags(company)

        raw_url = str(p.get("url") or p.get("link") or f"https://www.hirist.tech/job/{raw.external_id}").strip()
        canonical_url = sanitize_canonical_url(raw_url, "www.hirist.tech", raw.external_id)

        # Location and remote
        loc_str = str(p.get("location") or p.get("city") or "India")
        location, remote_type = parse_location_and_remote(loc_str)

        # Salary parsing
        sal_text = str(p.get("salary_text") or p.get("salary") or p.get("ctc") or "")
        sal_min, sal_max, currency = parse_inr_salary_text(sal_text)

        # Experience parsing
        exp_text = str(p.get("experience_text") or p.get("experience") or "")
        exp_min, exp_max = parse_experience_text(exp_text)

        raw_desc = str(p.get("description") or f"{title} opportunity at {company} in {location}.")
        desc = strip_html_tags(raw_desc)

        workplace_type = "Remote" if remote_type == RemoteType.REMOTE else "On-site"

        return NormalizedJob(
            source_identifier=self.source_identifier,
            external_id=raw.external_id,
            title=title,
            company=company,
            canonical_url=canonical_url,
            location=location,
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
                "parsed_from": "hirist_rss",
                "original_location": loc_str,
                "original_salary_text": sal_text,
                "original_experience_text": exp_text,
            },
            posted_at=None,
            raw_payload=p,
        )
