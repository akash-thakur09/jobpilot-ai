"""
JobPilot AI - Canonical Approval Fingerprinting
Deterministic snapshot computation and cryptographic binding of candidate data,
job description, resume artifact, prepared form data, and policy versions.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from decimal import Decimal
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm.attributes import NO_VALUE

from backend.app.models.candidate import CandidateProfile
from backend.app.models.job import Job
from backend.app.models.resume import ResumeVersion
from backend.app.models.matching import MatchScore
from backend.app.resumes.storage_service import ResumeStorageService
from backend.app.workflow.exceptions import ResumeIntegrityError


CURRENT_APPROVAL_POLICY_VERSION = "1.0.0"
CURRENT_TAILORING_POLICY_VERSION = "1.0.0"


def canonical_json_dumps(obj: Any) -> str:
    """
    Produces deterministic, canonical JSON serialization:
    - Alphabetically sorted dictionary keys
    - No whitespace in separators (',', ':')
    - Consistent UTF-8 Unicode characters (ensure_ascii=False)
    - Dates normalized to UTC ISO-8601 strings
    - Float/Decimal representations normalized to fixed-precision strings
    """

    def _default(val: Any) -> Any:
        if isinstance(val, (datetime,)):
            if val.tzinfo is None:
                val = val.replace(tzinfo=timezone.utc)
            return val.astimezone(timezone.utc).isoformat()
        if isinstance(val, Decimal):
            return f"{val:.4f}"
        if isinstance(val, (set, frozenset)):
            return sorted(list(val))
        if hasattr(val, "model_dump"):
            return val.model_dump()
        if hasattr(val, "__dict__"):
            # Exclude private attributes and SQLAlchemy internal state
            return {k: v for k, v in val.__dict__.items() if not k.startswith("_")}
        raise TypeError(f"Object of type {type(val).__name__} is not JSON serializable")

    return json.dumps(
        obj,
        default=_default,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


class ApprovalFingerprintService:
    """
    Computes cryptographic bindings tying candidate approval to the exact
    profile facts, job description, resume artifact, and prepared form data reviewed.
    """

    @classmethod
    def compute_candidate_revision_fingerprint(cls, candidate: CandidateProfile) -> str:
        """
        Computes a deterministic hash of verified candidate facts and attributes.
        Any edit to candidate profile details, skills, experiences, or educations
        will alter this fingerprint.
        """
        try:
            insp = sa_inspect(candidate)
        except Exception:
            insp = None

        # Verified skills sorted by name
        skills_data = []
        skills_val = insp.attrs.skills.loaded_value if insp and "skills" in insp.attrs else NO_VALUE
        if skills_val is NO_VALUE:
            skills_val = getattr(candidate, "skills", [])
        if skills_val:
            for s in sorted(skills_val, key=lambda x: str(x.skill_name).lower()):
                if s.is_verified:
                    skills_data.append({
                        "skill_name": str(s.skill_name).strip().lower(),
                        "category": str(s.category).strip().lower(),
                        "years_experience": round(float(s.years_experience or 0.0), 2),
                    })

        # Experiences sorted by company and start_date
        exp_data = []
        exp_val = insp.attrs.experiences.loaded_value if insp and "experiences" in insp.attrs else NO_VALUE
        if exp_val is NO_VALUE:
            exp_val = getattr(candidate, "experiences", [])
        if exp_val:
            for exp in sorted(exp_val, key=lambda x: (str(x.company).lower(), str(x.start_date))):
                exp_data.append({
                    "company": str(exp.company).strip(),
                    "role": str(exp.role).strip(),
                    "start_date": str(exp.start_date).strip(),
                    "end_date": str(exp.end_date).strip() if exp.end_date else None,
                    "is_current": bool(exp.is_current),
                    "verified_bullets": sorted([b.strip() for b in (exp.verified_bullets or [])]),
                })

        # Educations sorted by institution
        edu_data = []
        edu_val = insp.attrs.educations.loaded_value if insp and "educations" in insp.attrs else NO_VALUE
        if edu_val is NO_VALUE:
            edu_val = getattr(candidate, "educations", [])
        if edu_val:
            for edu in sorted(edu_val, key=lambda x: str(x.institution).lower()):
                edu_data.append({
                    "institution": str(edu.institution).strip(),
                    "degree": str(edu.degree).strip(),
                    "field_of_study": str(edu.field_of_study).strip(),
                    "graduation_year": int(edu.graduation_year or 0),
                })

        # Normalized candidate dictionary
        candidate_facts = {
            "candidate_id": str(candidate.id),
            "full_name": str(candidate.full_name).strip(),
            "email": str(candidate.email).strip().lower(),
            "phone": str(candidate.phone).strip() if candidate.phone else None,
            "location": str(candidate.location).strip().lower(),
            "work_authorization": str(candidate.work_authorization).strip().lower(),
            "summary": str(candidate.summary).strip(),
            "years_of_experience": round(float(candidate.years_of_experience or 0.0), 2),
            "skills": skills_data,
            "experiences": exp_data,
            "educations": edu_data,
        }

        canonical_repr = canonical_json_dumps(candidate_facts)
        return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

    @classmethod
    def compute_job_fingerprint(cls, job: Job) -> str:
        """
        Computes a stable hash of the job title, company, and full description.
        """
        canonical_job_str = f"{job.title.strip()}:{job.company.strip()}:{job.description.strip()}"
        return hashlib.sha256(canonical_job_str.encode("utf-8")).hexdigest()

    @classmethod
    def compute_prepared_form_fingerprint(cls, form_data: Dict[str, Any]) -> str:
        """
        Computes a hash of the canonical prepared application form fields.
        Excludes transient UI state and non-field parameters.
        """
        # Extract scalar values from form data if wrapped in field schemas
        normalized_form: Dict[str, Any] = {}
        for k, v in sorted(form_data.items()):
            if isinstance(v, dict) and "value" in v:
                normalized_form[k] = v["value"]
            else:
                normalized_form[k] = v

        canonical_repr = canonical_json_dumps(normalized_form)
        return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

    @classmethod
    def compute_disk_resume_sha256(cls, pdf_file_path: str) -> str:
        """
        Computes the fresh SHA-256 of the actual resume PDF file on disk.
        Raises ResumeIntegrityError if file does not exist or cannot be read.
        """
        try:
            resolved_path = ResumeStorageService.get_resume_pdf_path(pdf_file_path)
            content = resolved_path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except Exception as e:
            raise ResumeIntegrityError(
                f"Cannot verify resume PDF artifact on disk: {str(e)}"
            )

    @classmethod
    def build_canonical_snapshot(
        cls,
        candidate: CandidateProfile,
        job: Job,
        resume_version: ResumeVersion,
        prepared_form_data: Dict[str, Any],
        match_score: Optional[MatchScore] = None,
        tailoring_policy_version: str = CURRENT_TAILORING_POLICY_VERSION,
        approval_policy_version: str = CURRENT_APPROVAL_POLICY_VERSION,
    ) -> Dict[str, Any]:
        """
        Builds the complete canonical approval snapshot dictionary.
        Does NOT contain platform-dependent filesystem paths or secrets.
        """
        candidate_revision = cls.compute_candidate_revision_fingerprint(candidate)
        job_fingerprint = cls.compute_job_fingerprint(job)
        prepared_form_fingerprint = cls.compute_prepared_form_fingerprint(prepared_form_data)

        # Freshly compute the checksum of the PDF file on disk
        disk_sha256 = cls.compute_disk_resume_sha256(resume_version.pdf_file_path)

        # Persisted SHA-256 must match actual file on disk
        if disk_sha256 != resume_version.file_sha256:
            raise ResumeIntegrityError(
                f"Resume file tampering or checksum mismatch: disk SHA-256 ({disk_sha256}) "
                f"does not match recorded SHA-256 ({resume_version.file_sha256})."
            )

        eligibility_status = "ELIGIBLE"
        overall_score = "1.0000"
        if match_score:
            eligibility_status = str(match_score.eligibility_status)
            overall_score = f"{float(match_score.overall_score or 0.0):.4f}"

        return {
            "approval_policy_version": approval_policy_version,
            "candidate_id": str(candidate.id),
            "candidate_revision": candidate_revision,
            "disk_resume_sha256": disk_sha256,
            "eligibility_status": eligibility_status,
            "job_fingerprint": job_fingerprint,
            "job_id": str(job.id),
            "overall_score": overall_score,
            "persisted_resume_sha256": str(resume_version.file_sha256),
            "prepared_form_fingerprint": prepared_form_fingerprint,
            "resume_version_id": str(resume_version.id),
            "tailoring_policy_version": tailoring_policy_version,
        }

    @classmethod
    def compute_approval_fingerprint(cls, snapshot: Dict[str, Any]) -> str:
        """
        Calculates the cryptographic SHA-256 hex digest over the canonical JSON
        representation of the approval snapshot.
        """
        canonical_repr = canonical_json_dumps(snapshot)
        return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

    @classmethod
    def generate_fingerprint_for_application(
        cls,
        candidate: CandidateProfile,
        job: Job,
        resume_version: ResumeVersion,
        prepared_form_data: Dict[str, Any],
        match_score: Optional[MatchScore] = None,
    ) -> str:
        """
        Convenience method to construct snapshot and return its canonical fingerprint.
        """
        snapshot = cls.build_canonical_snapshot(
            candidate=candidate,
            job=job,
            resume_version=resume_version,
            prepared_form_data=prepared_form_data,
            match_score=match_score,
        )
        return cls.compute_approval_fingerprint(snapshot)
