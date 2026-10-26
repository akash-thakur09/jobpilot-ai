import re
from typing import List, Dict, Any, Optional
import httpx
from backend.app.collectors.base import BaseJobSourceAdapter, RawJobData, NormalizedJob
from backend.app.models.enums import RemoteType
from backend.app.core.logging import logger


class LeverJobAdapter(BaseJobSourceAdapter):
    """
    Lever Job Board Adapter for publicly accessible employer job postings.
    
    API Reference:
    - Base URL: https://api.lever.co/v0/postings/{site_token}?mode=json
    - Auth: None (publicly accessible endpoints)
    - Rate Limit: Approximately 30 requests/min recommended
    - Limitations:
        - Only active published postings are returned
        - Salary details are usually embedded in description plain text rather than structured keys
        - Requires an employer's site_token (e.g. 'netflix', 'spotify', 'figma')
    """

    BASE_URL = "https://api.lever.co/v0/postings/{site_token}"

    @property
    def source_identifier(self) -> str:
        return "lever"

    @property
    def source_name(self) -> str:
        return "Lever Job Board"

    @property
    def rate_limit_rpm(self) -> int:
        return 30

    async def fetch_jobs(
        self,
        site_token: str = "example",
        fixtures: Optional[List[Dict[str, Any]]] = None,
        timeout_seconds: float = 10.0,
        **kwargs,
    ) -> List[RawJobData]:
        """Fetches public postings for a given Lever site token."""
        if fixtures is not None:
            return [
                RawJobData(
                    source_identifier=self.source_identifier,
                    external_id=str(item.get("id")),
                    payload={**item, "_site_token": site_token},
                )
                for item in fixtures
            ]

        url = self.BASE_URL.format(site_token=site_token)
        params = {"mode": "json"}

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.get(url, params=params)
                if response.status_code == 404:
                    logger.warning(f"Lever site '{site_token}' not found (404).")
                    return []
                response.raise_for_status()
                postings = response.json()
                if not isinstance(postings, list):
                    return []

                return [
                    RawJobData(
                        source_identifier=self.source_identifier,
                        external_id=str(post.get("id")),
                        payload={**post, "_site_token": site_token},
                    )
                    for post in postings
                ]
        except Exception as exc:
            logger.error(f"Error fetching from Lever site '{site_token}': {exc}")
            raise

    def normalize(self, raw: RawJobData) -> NormalizedJob:
        p = raw.payload
        site_token = p.get("_site_token", "Lever Company")
        company_name = site_token.replace("-", " ").title()

        title = p.get("text", "Untitled Role")
        canonical_url = p.get("hostedUrl", f"https://jobs.lever.co/{site_token}/{raw.external_id}")

        cats = p.get("categories") or {}
        location_name = cats.get("location") or "Remote"
        commitment = cats.get("commitment") or "Full-time"

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

        # Description assembly
        desc_plain = p.get("descriptionPlain") or ""
        additional_plain = p.get("additionalPlain") or ""
        full_description = f"{desc_plain}\n\n{additional_plain}".strip()
        full_description = re.sub(r"\s+", " ", full_description).strip()

        return NormalizedJob(
            source_identifier=self.source_identifier,
            external_id=raw.external_id,
            title=title,
            company=company_name,
            canonical_url=canonical_url,
            location=location_name,
            remote_type=remote_type,
            employment_type=commitment,
            description=full_description or title,
            salary_min=None,
            salary_max=None,
            currency="USD",
            raw_payload=p,
        )
