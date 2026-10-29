from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from backend.app.models.enums import RemoteType


class RawJobData(BaseModel):
    """Raw payload returned directly from a job board or provider."""
    source_identifier: str
    external_id: str
    payload: Dict[str, Any]
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NormalizedJob(BaseModel):
    """Standardized representation of a job listing across all sources."""
    source_identifier: str
    external_id: str
    title: str
    company: str
    canonical_url: str
    location: str = "Remote"
    remote_type: RemoteType = RemoteType.REMOTE
    employment_type: str = "Full-time"
    description: str
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: Optional[str] = "USD"
    posted_at: Optional[datetime] = None
    raw_payload: Optional[Dict[str, Any]] = None


class SourceRateLimitException(Exception):
    """Raised when an external job board endpoint returns HTTP 429 Too Many Requests."""
    def __init__(self, message: str, retry_after_seconds: Optional[int] = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class BaseJobSourceAdapter(ABC):
    """
    Abstract base class for all job source adapters.
    
    Responsibilities:
    - Declares source identification and metadata
    - Enforces rate limits and failure backoff
    - Fetches raw job listings from public APIs, boards, or fixtures
    - Normalizes raw listings into a consistent NormalizedJob schema
    - Ensures no authenticated access or anti-bot circumvention is attempted
    """

    @property
    @abstractmethod
    def source_identifier(self) -> str:
        """Unique lowercase identifier, e.g. 'greenhouse', 'lever', 'synthetic'."""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name of the source."""
        pass

    @property
    @abstractmethod
    def rate_limit_rpm(self) -> int:
        """Maximum requests per minute allowed."""
        pass

    @abstractmethod
    async def fetch_jobs(self, **kwargs) -> List[RawJobData]:
        """Fetch raw listings from the source."""
        pass

    @abstractmethod
    def normalize(self, raw: RawJobData) -> NormalizedJob:
        """Transforms a raw provider payload into the normalized job schema."""
        pass

    async def check_job_status(self, external_id: str, **kwargs) -> Optional[str]:
        """
        Optional source-specific check for an individual job's status.
        Returns:
            'ACTIVE': Listing confirmed actively open by source.
            'CONFIRMED_CLOSED': Listing confirmed closed or not found (e.g. 404).
            None: Status cannot be verified due to network error, timeout, or rate limit.
        """
        return None

