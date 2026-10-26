from typing import List, Dict, Any, Optional
from backend.app.collectors.base import BaseJobSourceAdapter, RawJobData, NormalizedJob
from backend.app.models.enums import RemoteType


class SyntheticJobAdapter(BaseJobSourceAdapter):
    """
    Synthetic Job Adapter for deterministic testing, development, and offline validation.
    Generates well-formed job postings with varied skills, salaries, and remote types.
    """

    @property
    def source_identifier(self) -> str:
        return "synthetic"

    @property
    def source_name(self) -> str:
        return "Synthetic Test Job Generator"

    @property
    def rate_limit_rpm(self) -> int:
        return 120

    async def fetch_jobs(
        self,
        count: int = 5,
        company_name: str = "Acme Cloud Corp",
        custom_fixtures: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> List[RawJobData]:
        if custom_fixtures:
            return [
                RawJobData(
                    source_identifier=self.source_identifier,
                    external_id=item.get("id", f"syn_{idx+1}"),
                    payload=item,
                )
                for idx, item in enumerate(custom_fixtures)
            ]

        results: List[RawJobData] = []
        sample_roles = [
            ("syn_001", "Senior Python Backend Engineer", "Remote", RemoteType.REMOTE, 150000.0, 190000.0, "Experience with Python, FastAPI, Docker, and PostgreSQL."),
            ("syn_002", "Staff DevOps & Infrastructure Engineer", "San Francisco, CA", RemoteType.HYBRID, 180000.0, 230000.0, "Looking for deep Kubernetes, Terraform, and AWS expertise."),
            ("syn_003", "Full Stack Engineer (React/TypeScript)", "New York, NY", RemoteType.ON_SITE, 130000.0, 165000.0, "Must be proficient with React, TypeScript, and modern CSS."),
            ("syn_004", "Machine Learning Platform Engineer", "Remote - US", RemoteType.REMOTE, 170000.0, 215000.0, "Building distributed inference pipelines with PyTorch and Ray."),
            ("syn_005", "Junior Software Developer", "Austin, TX", RemoteType.HYBRID, 85000.0, 105000.0, "Entry level position requiring Python fundamentals and Git knowledge."),
        ]

        for i in range(min(count, len(sample_roles))):
            ext_id, title, loc, remote_type, s_min, s_max, desc = sample_roles[i]
            payload = {
                "id": ext_id,
                "title": title,
                "company": company_name,
                "url": f"https://jobs.example.com/{company_name.lower().replace(' ', '')}/{ext_id}",
                "location": loc,
                "remote_type": remote_type.value,
                "salary_min": s_min,
                "salary_max": s_max,
                "currency": "USD",
                "description": desc,
                "employment_type": "Full-time",
            }
            results.append(
                RawJobData(
                    source_identifier=self.source_identifier,
                    external_id=ext_id,
                    payload=payload,
                )
            )
        return results

    def normalize(self, raw: RawJobData) -> NormalizedJob:
        p = raw.payload
        remote_str = p.get("remote_type", RemoteType.REMOTE.value)
        try:
            remote_type = RemoteType(remote_str)
        except ValueError:
            remote_type = RemoteType.UNKNOWN

        return NormalizedJob(
            source_identifier=self.source_identifier,
            external_id=raw.external_id,
            title=p.get("title", "Untitled Role"),
            company=p.get("company", "Unknown Employer"),
            canonical_url=p.get("url", f"https://jobs.example.com/{raw.external_id}"),
            location=p.get("location", "Remote"),
            remote_type=remote_type,
            employment_type=p.get("employment_type", "Full-time"),
            description=p.get("description", ""),
            salary_min=p.get("salary_min"),
            salary_max=p.get("salary_max"),
            currency=p.get("currency", "USD"),
            raw_payload=p,
        )
