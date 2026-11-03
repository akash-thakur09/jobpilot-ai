import re
import html
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import httpx
from backend.app.collectors.base import BaseJobSourceAdapter, RawJobData, NormalizedJob, SourceRateLimitException
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
    def source_type(self) -> str:
        return "ats"

    @property
    def rate_limit_rpm(self) -> int:
        return 30

    async def fetch_jobs(
        self,
        board_token: Optional[str] = None,
        board_tokens: Optional[List[str]] = None,
        fixtures: Optional[List[Dict[str, Any]]] = None,
        timeout_seconds: float = 25.0,
        limit: Optional[int] = None,
        **kwargs,
    ) -> List[RawJobData]:
        """Fetches public postings for one or more Greenhouse board tokens."""
        # Determine tokens list
        tokens_to_fetch: List[str] = []
        if board_tokens and isinstance(board_tokens, list):
            tokens_to_fetch = [t.strip() for t in board_tokens if t and str(t).strip()]
        elif board_token:
            if "," in board_token:
                tokens_to_fetch = [t.strip() for t in board_token.split(",") if t.strip()]
            else:
                tokens_to_fetch = [board_token.strip()]
        
        if not tokens_to_fetch:
            tokens_to_fetch = ["canonical"]

        if fixtures is not None:
            items = fixtures[:limit] if limit else fixtures
            first_token = tokens_to_fetch[0] if tokens_to_fetch else "example"
            return [
                RawJobData(
                    source_identifier=self.source_identifier,
                    external_id=str(item.get("id")),
                    payload={**item, "_board_token": first_token},
                )
                for item in items
            ]

        all_raw_jobs: List[RawJobData] = []
        params = {"content": "true"}

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            for token in tokens_to_fetch:
                url = self.BASE_URL.format(board_token=token)
                try:
                    response = await client.get(url, params=params)
                    if response.status_code == 429:
                        retry_after_str = response.headers.get("Retry-After", "60")
                        try:
                            retry_sec = int(retry_after_str)
                        except ValueError:
                            retry_sec = 60
                        logger.warning(f"Greenhouse rate limit (429) hit for '{token}'. Retry-After: {retry_sec}s")
                        raise SourceRateLimitException(
                            f"Greenhouse rate limit exceeded for board '{token}'. Retry after {retry_sec}s.",
                            retry_after_seconds=retry_sec,
                        )
                    if response.status_code == 404:
                        logger.warning(f"Greenhouse board '{token}' not found (404).")
                        continue
                    response.raise_for_status()
                    try:
                        data = response.json()
                    except Exception as json_err:
                        logger.warning(f"Malformed JSON response from Greenhouse board '{token}': {json_err}")
                        if len(tokens_to_fetch) == 1:
                            raise ValueError(f"Malformed JSON response from Greenhouse board '{token}': {json_err}")
                        continue

                    jobs_list = data.get("jobs", [])
                    if limit and isinstance(limit, int):
                        remaining_quota = limit - len(all_raw_jobs)
                        if remaining_quota <= 0:
                            break
                        jobs_list = jobs_list[:remaining_quota]

                    for job in jobs_list:
                        all_raw_jobs.append(
                            RawJobData(
                                source_identifier=self.source_identifier,
                                external_id=str(job.get("id")),
                                payload={**job, "_board_token": token},
                            )
                        )

                    if limit and len(all_raw_jobs) >= limit:
                        break

                except SourceRateLimitException:
                    raise
                except Exception as exc:
                    logger.error(f"Error fetching from Greenhouse board '{token}': {exc}")
                    if len(tokens_to_fetch) == 1:
                        raise

        return all_raw_jobs

    async def check_job_status(
        self,
        external_id: str,
        board_token: str = "example",
        timeout_seconds: float = 5.0,
        **kwargs,
    ) -> Optional[str]:
        """Probes single job URL on Greenhouse to authoritatively verify if still active or closed."""
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{external_id}"
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
            logger.debug(f"Greenhouse status probe failed for {board_token}/{external_id}: {exc}")
            return None

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

        # Parse posted_at date from updated_at or created_at
        posted_at: Optional[datetime] = None
        date_str = p.get("updated_at") or p.get("created_at")
        if date_str and isinstance(date_str, str):
            try:
                posted_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=timezone.utc)
            except Exception:
                posted_at = None

        # Parse structured salary if available in metadata or text
        salary_min: Optional[float] = None
        salary_max: Optional[float] = None
        currency: str = "USD"
        metadata_list = p.get("metadata") or []
        if isinstance(metadata_list, list):
            for meta_item in metadata_list:
                if isinstance(meta_item, dict):
                    meta_name = str(meta_item.get("name", "")).lower()
                    if "salary" in meta_name or "compensation" in meta_name:
                        val = meta_item.get("value")
                        if val:
                            found = re.findall(r"\$?\s*([\d,]+(?:\.\d+)?)", str(val))
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
            employment_type="Full-time",
            description=cleaned_description or title,
            salary_min=salary_min,
            salary_max=salary_max,
            currency=currency,
            posted_at=posted_at,
            raw_payload=p,
        )

