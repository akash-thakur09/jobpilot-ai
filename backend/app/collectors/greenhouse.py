import re
import html
from typing import List, Dict, Any, Optional
import httpx
from backend.app.collectors.base import BaseJobSourceAdapter, RawJobData, NormalizedJob
from backend.app.models.enums import RemoteType
from backend.app.core.logging import logger


class GreenhouseJobAdapter(BaseJobSourceAdapter):
    """
    Greenhouse Job Board Adapter for publicly accessible employer job boards.
    
    API Reference:
    - Base URL: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
    - Auth: None (publicly accessible endpoints)
    - Rate Limit: Approximately 30 requests/min recommended
    - Limitations:
        - Only publicly listed jobs are accessible
        - Salary data is rarely provided in structured fields and may only appear in text
        - Requires an employer's board_token (e.g. 'stripe', 'github', 'canonical')
    """

    BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"

    @property
    def source_identifier(self) -> str:
        return "greenhouse"

    @property
    def source_name(self) -> str:
        return "Greenhouse Job Board"

    @property
    def rate_limit_rpm(self) -> int:
        return 30

    async def fetch_jobs(
        self,
        board_token: str = "example",
        fixtures: Optional[List[Dict[str, Any]]] = None,
        timeout_seconds: float = 10.0,
        **kwargs,
    ) -> List[RawJobData]:
        """Fetches public postings for a given Greenhouse board token."""
        if fixtures is not None:
            return [
                RawJobData(
                    source_identifier=self.source_identifier,
                    external_id=str(item.get("id")),
                    payload={**item, "_board_token": board_token},
                )
                for item in fixtures
            ]

        url = self.BASE_URL.format(board_token=board_token)
        params = {"content": "true"}

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.get(url, params=params)
                if response.status_code == 404:
                    logger.warning(f"Greenhouse board '{board_token}' not found (404).")
                    return []
                response.raise_for_status()
                data = response.json()
                jobs_list = data.get("jobs", [])

                return [
                    RawJobData(
                        source_identifier=self.source_identifier,
                        external_id=str(job.get("id")),
                        payload={**job, "_board_token": board_token},
                    )
                    for job in jobs_list
                ]
        except Exception as exc:
            logger.error(f"Error fetching from Greenhouse board '{board_token}': {exc}")
            raise

    def normalize(self, raw: RawJobData) -> NormalizedJob:
        p = raw.payload
        board_token = p.get("_board_token", "Greenhouse Company")
        company_name = board_token.replace("-", " ").title()

        title = p.get("title", "Untitled Role")
        canonical_url = p.get("absolute_url", f"https://boards.greenhouse.io/{board_token}/jobs/{raw.external_id}")

        # Location extraction
        loc_obj = p.get("location") or {}
        location_name = loc_obj.get("name") if isinstance(loc_obj, dict) else str(loc_obj)
        location_name = location_name.strip() if location_name else "Remote"

        # Remote type detection
        combined_text = f"{title} {location_name}".lower()
        if "remote" in combined_text or "anywhere" in combined_text:
            remote_type = RemoteType.REMOTE
        elif "hybrid" in combined_text:
            remote_type = RemoteType.HYBRID
        elif location_name and location_name.lower() != "remote":
            remote_type = RemoteType.ON_SITE
        else:
            remote_type = RemoteType.REMOTE

        # Description cleaning (HTML unescape and tag stripping)
        raw_content = p.get("content") or ""
        unescaped = html.unescape(raw_content)
        cleaned_description = re.sub(r"<[^>]+>", " ", unescaped)
        cleaned_description = re.sub(r"\s+", " ", cleaned_description).strip()

        return NormalizedJob(
            source_identifier=self.source_identifier,
            external_id=raw.external_id,
            title=title,
            company=company_name,
            canonical_url=canonical_url,
            location=location_name,
            remote_type=remote_type,
            employment_type="Full-time",
            description=cleaned_description or title,
            salary_min=None,
            salary_max=None,
            currency="USD",
            raw_payload=p,
        )
