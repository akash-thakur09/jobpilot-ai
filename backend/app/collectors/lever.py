import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import httpx
from backend.app.collectors.base import BaseJobSourceAdapter, RawJobData, NormalizedJob, SourceRateLimitException
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
    def source_type(self) -> str:
        return "ats"

    @property
    def rate_limit_rpm(self) -> int:
        return 30

    async def fetch_jobs(
        self,
        site_token: Optional[str] = None,
        site_tokens: Optional[List[str]] = None,
        fixtures: Optional[List[Dict[str, Any]]] = None,
        timeout_seconds: float = 25.0,
        limit: Optional[int] = None,
        **kwargs,
    ) -> List[RawJobData]:
        """Fetches public postings for one or more Lever site tokens."""
        tokens_to_fetch: List[str] = []
        if site_tokens and isinstance(site_tokens, list):
            tokens_to_fetch = [t.strip() for t in site_tokens if t and str(t).strip()]
        elif site_token:
            if "," in site_token:
                tokens_to_fetch = [t.strip() for t in site_token.split(",") if t.strip()]
            else:
                tokens_to_fetch = [site_token.strip()]

        if not tokens_to_fetch:
            tokens_to_fetch = ["example"]

        if fixtures is not None:
            items = fixtures[:limit] if limit else fixtures
            first_token = tokens_to_fetch[0] if tokens_to_fetch else "example"
            return [
                RawJobData(
                    source_identifier=self.source_identifier,
                    external_id=str(item.get("id")),
                    payload={**item, "_site_token": first_token},
                )
                for item in items
            ]

        all_raw_jobs: List[RawJobData] = []
        params = {"mode": "json"}

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            for token in tokens_to_fetch:
                url = self.BASE_URL.format(site_token=token)
                try:
                    req_params = dict(params)
                    if limit and isinstance(limit, int):
                        remaining_quota = limit - len(all_raw_jobs)
                        if remaining_quota <= 0:
                            break
                        req_params["limit"] = str(remaining_quota)

                    response = await client.get(url, params=req_params)
                    if response.status_code == 429:
                        retry_after_str = response.headers.get("Retry-After", "60")
                        try:
                            retry_sec = int(retry_after_str)
                        except ValueError:
                            retry_sec = 60
                        logger.warning(f"Lever rate limit (429) hit for '{token}'. Retry-After: {retry_sec}s")
                        raise SourceRateLimitException(
                            f"Lever rate limit exceeded for site '{token}'. Retry after {retry_sec}s.",
                            retry_after_seconds=retry_sec,
                        )
                    if response.status_code == 404:
                        logger.warning(f"Lever site '{token}' not found (404).")
                        continue
                    response.raise_for_status()
                    try:
                        postings = response.json()
                    except Exception as json_err:
                        logger.warning(f"Malformed JSON response from Lever site '{token}': {json_err}")
                        if len(tokens_to_fetch) == 1:
                            raise ValueError(f"Malformed JSON response from Lever site '{token}': {json_err}")
                        continue

                    if not isinstance(postings, list):
                        continue

                    if limit and isinstance(limit, int):
                        remaining_quota = limit - len(all_raw_jobs)
                        if remaining_quota <= 0:
                            break
                        postings = postings[:remaining_quota]

                    for post in postings:
                        all_raw_jobs.append(
                            RawJobData(
                                source_identifier=self.source_identifier,
                                external_id=str(post.get("id")),
                                payload={**post, "_site_token": token},
                            )
                        )

                    if limit and len(all_raw_jobs) >= limit:
                        break

                except SourceRateLimitException:
                    raise
                except Exception as exc:
                    logger.error(f"Error fetching from Lever site '{token}': {exc}")
                    if len(tokens_to_fetch) == 1:
                        raise

        return all_raw_jobs

    async def check_job_status(
        self,
        external_id: str,
        site_token: str = "example",
        timeout_seconds: float = 5.0,
        **kwargs,
    ) -> Optional[str]:
        """Probes single posting URL on Lever to authoritatively verify if still active or closed."""
        url = f"https://api.lever.co/v0/postings/{site_token}/{external_id}"
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return "ACTIVE"
                elif response.status_code == 404:
                    return "CONFIRMED_CLOSED"
                else:
                    return None
        except Exception as exc:
            logger.debug(f"Lever status probe failed for {site_token}/{external_id}: {exc}")
            return None

    def normalize(self, raw: RawJobData) -> NormalizedJob:
        p = raw.payload
        site_token = p.get("_site_token", "Lever Company")
        company_name = site_token.replace("-", " ").title()

        title = p.get("text", "Untitled Role")
        canonical_url = p.get("hostedUrl", f"https://jobs.lever.co/{site_token}/{raw.external_id}")

        cats = p.get("categories") or {}
        location_name = cats.get("location") or "Remote"
        commitment = cats.get("commitment") or "Full-time"

        # Remote type detection with workplaceType support
        workplace_type = str(p.get("workplaceType", "")).lower()
        combined_text = f"{title} {location_name} {workplace_type}".lower()
        if workplace_type == "remote" or "remote" in combined_text or "anywhere" in combined_text:
            remote_type = RemoteType.REMOTE
        elif workplace_type == "hybrid" or "hybrid" in combined_text:
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

        # Parse posted_at date from createdAt (timestamp in ms)
        posted_at: Optional[datetime] = None
        created_at_val = p.get("createdAt")
        if created_at_val is not None:
            try:
                if isinstance(created_at_val, (int, float)):
                    posted_at = datetime.fromtimestamp(created_at_val / 1000.0, tz=timezone.utc)
                elif isinstance(created_at_val, str) and created_at_val.isdigit():
                    posted_at = datetime.fromtimestamp(float(created_at_val) / 1000.0, tz=timezone.utc)
                elif isinstance(created_at_val, str):
                    posted_at = datetime.fromisoformat(created_at_val.replace("Z", "+00:00"))
                    if posted_at.tzinfo is None:
                        posted_at = posted_at.replace(tzinfo=timezone.utc)
            except Exception:
                posted_at = None

        # Parse salary if structured range or description is provided
        salary_min: Optional[float] = None
        salary_max: Optional[float] = None
        currency: str = "USD"
        sal_range = p.get("salaryRange")
        if isinstance(sal_range, dict):
            salary_min = float(sal_range.get("min")) if sal_range.get("min") is not None else None
            salary_max = float(sal_range.get("max")) if sal_range.get("max") is not None else None
            currency = sal_range.get("currency") or "USD"
        else:
            sal_desc = cats.get("salaryDescription") or p.get("salaryDescription")
            if sal_desc:
                found = re.findall(r"\$?\s*([\d,]+(?:\.\d+)?)", str(sal_desc))
                if found:
                    nums = [float(n.replace(",", "")) for n in found if float(n.replace(",", "")) >= 1000]
                    if len(nums) == 1:
                        salary_min = nums[0]
                    elif len(nums) >= 2:
                        salary_min = min(nums)
                        salary_max = max(nums)

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
            salary_min=salary_min,
            salary_max=salary_max,
            currency=currency,
            posted_at=posted_at,
            raw_payload=p,
        )

