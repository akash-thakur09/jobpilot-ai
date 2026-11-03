import re
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any, Set
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.logging import logger
from backend.app.models.job import Job, JobDuplicateCluster
from backend.app.models.enums import DuplicateConfidence, ClusterStatus


class DuplicateDetectionService:
    """
    Conservative cross-source duplicate detection service.
    
    Signals:
    - Canonicalized employer/company name
    - Normalized job title
    - Canonicalized job URL
    - Location and remote-work information
    - Description similarity
    
    Thresholds:
    - High confidence: >= 0.85
    - Possible duplicate: >= 0.65
    - Insufficient evidence: < 0.65
    """

    CORP_SUFFIX_PATTERN = re.compile(
        r"\b(inc|incorporated|llc|l\.l\.c\.|corp|corporation|ltd|limited|co|company|technologies|technology|tech|group|holdings|systems|software|solutions|services)\b\.?",
        re.IGNORECASE,
    )
    TITLE_CLEAN_PATTERN = re.compile(
        r"[\(\[\{].*?(remote|hybrid|onsite|full[- ]time|part[- ]time|contract|permanent|w/m/d|m/w/d|f/m/d|100%).*?[\)\]\}]",
        re.IGNORECASE,
    )
    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "ref", "source", "gh_src", "lever-source", "trk", "referral", "fbclid", "gclid"
    }

    @classmethod
    def canonicalize_company(cls, company: Optional[str]) -> str:
        if not company:
            return ""
        s = company.lower().strip()
        s = s.replace("&", " and ")
        s = cls.CORP_SUFFIX_PATTERN.sub("", s)
        s = re.sub(r"[^\w\s]", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @classmethod
    def canonicalize_title(cls, title: Optional[str]) -> str:
        if not title:
            return ""
        s = title.lower().strip()
        s = cls.TITLE_CLEAN_PATTERN.sub("", s)
        s = s.replace("sr.", "senior").replace("jr.", "junior")
        s = re.sub(r"[^\w\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @classmethod
    def canonicalize_url(cls, url: Optional[str]) -> str:
        if not url:
            return ""
        try:
            parsed = urllib.parse.urlparse(url.strip())
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            
            # Filter tracking query parameters
            query_pairs = urllib.parse.parse_qsl(parsed.query)
            clean_query = [
                (k, v) for k, v in query_pairs if k.lower() not in cls.TRACKING_PARAMS
            ]
            clean_query.sort()
            new_query = urllib.parse.urlencode(clean_query)

            # Clean trailing slash from path
            path = parsed.path.rstrip("/")
            return urllib.parse.urlunparse(("https", netloc, path, "", new_query, ""))
        except Exception:
            return url.strip()


    @classmethod
    def canonicalize_location(cls, location: Optional[str], remote_type: Optional[str]) -> Tuple[bool, str]:
        loc_str = (location or "").lower().strip()
        rem_str = (remote_type or "").upper().strip()
        is_remote = rem_str in ("REMOTE", "HYBRID") or "remote" in loc_str or "anywhere" in loc_str
        cleaned_loc = re.sub(r"[^\w\s]", " ", loc_str)
        cleaned_loc = re.sub(r"\s+", " ", cleaned_loc).strip()
        return is_remote, cleaned_loc

    @classmethod
    def _token_jaccard(cls, s1: str, s2: str) -> float:
        t1 = set(s1.split())
        t2 = set(s2.split())
        if not t1 or not t2:
            return 0.0
        intersection = t1.intersection(t2)
        union = t1.union(t2)
        return len(intersection) / len(union)

    @classmethod
    def compute_similarity(cls, job_a: Job, job_b: Job) -> Tuple[float, List[str], str]:
        """
        Compare two jobs conservatively across multiple signals.
        Returns: (confidence_score, match_reasons, confidence_classification)
        """
        if job_a.id == job_b.id:
            return 0.0, [], DuplicateConfidence.INSUFFICIENT_EVIDENCE.value

        reasons = []

        # Stage 1: Trustworthy canonical URL match
        url_a = cls.canonicalize_url(job_a.canonical_url)
        url_b = cls.canonicalize_url(job_b.canonical_url)
        if url_a and url_b and url_a == url_b:
            reasons.append("Identical canonical URL across postings")
            return 1.0, reasons, DuplicateConfidence.HIGH_CONFIDENCE.value

        # Stage 2: Company, Title, and Location matching
        comp_a = cls.canonicalize_company(job_a.company)
        comp_b = cls.canonicalize_company(job_b.company)
        
        # If companies are non-empty and completely different, reject immediately (conservatism)
        if comp_a and comp_b and comp_a != comp_b:
            comp_sim = cls._token_jaccard(comp_a, comp_b)
            if comp_sim < 0.6:
                return 0.0, [], DuplicateConfidence.INSUFFICIENT_EVIDENCE.value

        title_a = cls.canonicalize_title(job_a.title)
        title_b = cls.canonicalize_title(job_b.title)

        title_jaccard = cls._token_jaccard(title_a, title_b)
        # If titles share no meaningful tokens, not a duplicate
        if title_jaccard < 0.4:
            return 0.0, [], DuplicateConfidence.INSUFFICIENT_EVIDENCE.value

        # Location compatibility
        rem_a, loc_a = cls.canonicalize_location(job_a.location, job_a.remote_type)
        rem_b, loc_b = cls.canonicalize_location(job_b.location, job_b.remote_type)

        loc_compatible = False
        if rem_a and rem_b:
            loc_compatible = True
        elif loc_a and loc_b and (loc_a in loc_b or loc_b in loc_a or cls._token_jaccard(loc_a, loc_b) > 0.5):
            loc_compatible = True
        elif not loc_a or not loc_b:
            # Missing location data does not guarantee a match, but does not strictly refute
            loc_compatible = (rem_a == rem_b)

        # Description similarity
        desc_a_tokens = cls.canonicalize_title(job_a.description[:1000])
        desc_b_tokens = cls.canonicalize_title(job_b.description[:1000])
        desc_jaccard = cls._token_jaccard(desc_a_tokens, desc_b_tokens)

        # Conservative confidence calculation
        score = 0.0
        exact_company = (comp_a == comp_b and len(comp_a) > 2)
        exact_title = (title_a == title_b and len(title_a) > 3)

        if exact_company:
            score += 0.45
            reasons.append(f"Canonical employer matched: '{comp_a}'")
        else:
            score += 0.25 * cls._token_jaccard(comp_a, comp_b)
            reasons.append("Close employer name similarity")

        if exact_title:
            score += 0.35
            reasons.append(f"Normalized title matched: '{title_a}'")
        else:
            score += 0.30 * title_jaccard
            reasons.append(f"Title token overlap ({title_jaccard:.2f})")

        if loc_compatible:
            score += 0.10
            reasons.append("Compatible remote or geographical location")
        else:
            # Different explicit on-site locations indicate different vacancies
            score -= 0.35
            reasons.append("Conflicting physical locations indicate distinct vacancies")

        if desc_jaccard >= 0.40:
            score += 0.15 * min(desc_jaccard / 0.6, 1.0)
            reasons.append(f"Description vocabulary similarity ({desc_jaccard:.2f})")
        elif desc_jaccard < 0.20 and (desc_a_tokens and desc_b_tokens):
            score -= 0.25
            reasons.append(f"Divergent description vocabulary ({desc_jaccard:.2f}) indicates distinct vacancies")

        score = max(0.0, min(1.0, score))

        if score >= 0.85:
            classification = DuplicateConfidence.HIGH_CONFIDENCE.value
        elif score >= 0.65:
            classification = DuplicateConfidence.POSSIBLE_DUPLICATE.value
        else:
            classification = DuplicateConfidence.INSUFFICIENT_EVIDENCE.value

        return score, reasons, classification

    @classmethod
    async def find_duplicates_for_job(
        cls, session: AsyncSession, target_job: Job, max_candidates: int = 25
    ) -> List[Tuple[Job, float, List[str], str]]:
        """
        Uses bounded blocking to find candidate duplicates for target_job.
        Avoids all-vs-all comparisons.
        """
        norm_company = cls.canonicalize_company(target_job.company)
        title_tokens = cls.canonicalize_title(target_job.title).split()
        first_title_token = title_tokens[0] if title_tokens else ""

        # Blocking query: same normalized company substring OR shared source URL prefix
        filters = []
        if target_job.canonical_url:
            filters.append(Job.canonical_url == target_job.canonical_url)
        if target_job.company:
            filters.append(Job.company.ilike(f"%{target_job.company[:5]}%"))
        if first_title_token and len(first_title_token) >= 4:
            filters.append(Job.title.ilike(f"%{first_title_token}%"))


        if not filters:
            return []

        stmt = (
            select(Job)
            .where(Job.id != target_job.id, or_(*filters))
            .limit(max_candidates)
        )
        res = await session.execute(stmt)
        candidates = res.scalars().all()

        results = []
        for cand in candidates:
            score, reasons, conf = cls.compute_similarity(target_job, cand)
            if score >= 0.65:
                results.append((cand, score, reasons, conf))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    @classmethod
    async def cluster_job(
        cls, session: AsyncSession, job: Job
    ) -> Optional[JobDuplicateCluster]:
        """
        Evaluates a job against bounded candidate pool and assigns or creates a cluster if high/possible duplicate.
        Preserves original records, never deletes jobs, never transfers applications.
        """
        duplicates = await cls.find_duplicates_for_job(session, job)
        if not duplicates:
            return None

        best_match, best_score, best_reasons, best_conf = duplicates[0]

        # Case 1: Best match is already clustered
        if best_match.duplicate_cluster_id:
            cluster_stmt = (
                select(JobDuplicateCluster)
                .where(JobDuplicateCluster.id == best_match.duplicate_cluster_id)
            )
            cluster_res = await session.execute(cluster_stmt)
            cluster = cluster_res.scalar_one_or_none()

            if cluster and cluster.cluster_status != ClusterStatus.DISMISSED.value:
                job.duplicate_cluster_id = cluster.id
                # Update confidence if higher
                if best_score > cluster.confidence_score:
                    cluster.confidence_score = best_score
                    cluster.confidence = best_conf
                    cluster.match_reasons = best_reasons
                await session.flush()
                return cluster

        # Case 2: Target job already has a cluster
        if job.duplicate_cluster_id:
            cluster_stmt = (
                select(JobDuplicateCluster)
                .where(JobDuplicateCluster.id == job.duplicate_cluster_id)
            )
            cluster_res = await session.execute(cluster_stmt)
            cluster = cluster_res.scalar_one_or_none()
            if cluster and cluster.cluster_status != ClusterStatus.DISMISSED.value:
                best_match.duplicate_cluster_id = cluster.id
                await session.flush()
                return cluster

        # Case 3: Create a new cluster
        # Choose canonical job: prefer earlier first_seen_at / discovered_at, or longer description
        cand_time = best_match.first_seen_at or best_match.discovered_at
        job_time = job.first_seen_at or job.discovered_at

        def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

        cand_utc = _to_utc(cand_time)
        job_utc = _to_utc(job_time)

        if cand_utc and job_utc and cand_utc < job_utc:
            canonical_job_id = best_match.id
        elif len(best_match.description or "") > len(job.description or ""):
            canonical_job_id = best_match.id
        else:
            canonical_job_id = job.id


        new_cluster = JobDuplicateCluster(
            canonical_job_id=canonical_job_id,
            cluster_status=ClusterStatus.DETECTED.value,
            confidence=best_conf,
            confidence_score=best_score,
            match_reasons=best_reasons,
        )
        session.add(new_cluster)
        await session.flush()

        job.duplicate_cluster_id = new_cluster.id
        best_match.duplicate_cluster_id = new_cluster.id
        await session.flush()
        return new_cluster

    @classmethod
    async def review_cluster(
        cls, session: AsyncSession, cluster_id: str, action: str, notes: Optional[str] = None
    ) -> JobDuplicateCluster:
        """
        Confirm or dismiss a detected duplicate cluster safely.
        Action must be 'CONFIRM' or 'DISMISS'.
        """
        stmt = (
            select(JobDuplicateCluster)
            .options(selectinload(JobDuplicateCluster.jobs))
            .where(JobDuplicateCluster.id == cluster_id)
        )
        res = await session.execute(stmt)
        cluster = res.scalar_one_or_none()
        if not cluster:
            raise ValueError(f"Job duplicate cluster '{cluster_id}' not found.")

        if action.upper() == "CONFIRM":
            cluster.cluster_status = ClusterStatus.CONFIRMED.value
        elif action.upper() == "DISMISS":
            cluster.cluster_status = ClusterStatus.DISMISSED.value
        else:
            raise ValueError(f"Invalid review action '{action}'. Must be 'CONFIRM' or 'DISMISS'.")

        cluster.reviewed_at = datetime.now(timezone.utc)
        if notes:
            cluster.review_notes = notes

        await session.commit()
        await session.refresh(cluster)
        return cluster
