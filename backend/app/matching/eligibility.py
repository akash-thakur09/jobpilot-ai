import re
from typing import List, Tuple, Set, Optional
from backend.app.models.candidate import CandidateProfile
from backend.app.models.job import Job
from backend.app.models.enums import RemoteType
from backend.app.matching.schemas import (
    EligibilityStatus,
    RuleCheckStatus,
    EligibilityCheckResult,
)
from backend.app.matching.skill_registry import SkillRegistry


class EligibilityService:
    @classmethod
    def evaluate_eligibility(
        cls, candidate: CandidateProfile, job: Job
    ) -> Tuple[bool, EligibilityStatus, List[EligibilityCheckResult]]:
        """
        Evaluates hard constraints deterministically.
        Returns:
            (is_eligible: bool, status: EligibilityStatus, checks: List[EligibilityCheckResult])
        """
        checks: List[EligibilityCheckResult] = []

        # 1. Work Authorization Rule
        work_auth_check = cls._check_work_authorization(candidate, job)
        checks.append(work_auth_check)

        # 2. Location & Remote Compatibility Rule
        location_check = cls._check_location_and_remote(candidate, job)
        checks.append(location_check)

        # 3. Minimum Experience Rule
        exp_check = cls._check_minimum_experience(candidate, job)
        checks.append(exp_check)

        # 4. Mandatory Skills Rule
        mandatory_skills_check = cls._check_mandatory_skills(candidate, job)
        checks.append(mandatory_skills_check)

        # Determine overall eligibility
        has_failure = any(
            c.status == RuleCheckStatus.FAIL and c.is_hard_constraint for c in checks
        )
        has_unknown = any(
            c.status == RuleCheckStatus.UNKNOWN and c.is_hard_constraint for c in checks
        )

        if has_failure:
            return False, EligibilityStatus.DISQUALIFIED, checks
        elif has_unknown:
            return True, EligibilityStatus.NEEDS_REVIEW, checks
        else:
            return True, EligibilityStatus.ELIGIBLE, checks

    @classmethod
    def _check_work_authorization(
        cls, candidate: CandidateProfile, job: Job
    ) -> EligibilityCheckResult:
        desc_lower = job.description.lower()
        candidate_auth = candidate.work_authorization.lower()

        us_citizen_patterns = [
            "must be a us citizen",
            "u.s. citizen only",
            "us citizenship required",
            "citizenship required",
            "active security clearance required",
            "must possess active secret clearance",
        ]

        demands_us_citizenship = any(p in desc_lower for p in us_citizen_patterns)
        is_candidate_us_citizen = "citizen" in candidate_auth or "us citizen" in candidate_auth

        if demands_us_citizenship:
            if not is_candidate_us_citizen:
                return EligibilityCheckResult(
                    rule_id="WORK_AUTH_CITIZENSHIP",
                    status=RuleCheckStatus.FAIL,
                    reason="Job explicitly requires US Citizenship / Security Clearance which is not verified in candidate profile.",
                    evidence=f"Candidate authorization: '{candidate.work_authorization}'",
                    is_hard_constraint=True,
                )
            else:
                return EligibilityCheckResult(
                    rule_id="WORK_AUTH_CITIZENSHIP",
                    status=RuleCheckStatus.PASS,
                    reason="Candidate satisfies explicit US Citizenship requirement.",
                    evidence=f"Candidate authorization: '{candidate.work_authorization}'",
                    is_hard_constraint=True,
                )

        no_sponsorship_patterns = [
            "no visa sponsorship",
            "unable to sponsor",
            "without sponsorship",
            "sponsorship is not available",
        ]
        no_sponsorship = any(p in desc_lower for p in no_sponsorship_patterns)
        if no_sponsorship and ("visa" in candidate_auth or "requires sponsorship" in candidate_auth):
            return EligibilityCheckResult(
                rule_id="WORK_AUTH_SPONSORSHIP",
                status=RuleCheckStatus.FAIL,
                reason="Job does not offer visa sponsorship, but candidate requires sponsorship.",
                evidence=f"Candidate authorization: '{candidate.work_authorization}'",
                is_hard_constraint=True,
            )

        return EligibilityCheckResult(
            rule_id="WORK_AUTH",
            status=RuleCheckStatus.NOT_APPLICABLE,
            reason="No restrictive work authorization constraints detected in job posting.",
            evidence=f"Candidate authorization: '{candidate.work_authorization}'",
            is_hard_constraint=False,
        )

    @classmethod
    def _check_location_and_remote(
        cls, candidate: CandidateProfile, job: Job
    ) -> EligibilityCheckResult:
        candidate_pref = candidate.remote_preference.upper()
        job_remote = job.remote_type.upper()

        if job_remote == RemoteType.REMOTE.value:
            return EligibilityCheckResult(
                rule_id="LOCATION_REMOTE",
                status=RuleCheckStatus.PASS,
                reason="Job is fully remote, satisfying candidate location preferences.",
                evidence=f"Job remote status: {job.remote_type}",
                is_hard_constraint=True,
            )

        # If job is strictly on-site or hybrid in another city
        if job_remote in (RemoteType.ON_SITE.value, RemoteType.HYBRID.value):
            if candidate_pref == RemoteType.REMOTE.value:
                # Check if location matches candidate city
                job_loc = (job.location or "").lower()
                cand_loc = (candidate.location or "").lower()

                # If locations are clearly different and candidate is remote-only
                if cand_loc not in job_loc and job_loc not in cand_loc:
                    return EligibilityCheckResult(
                        rule_id="LOCATION_REMOTE",
                        status=RuleCheckStatus.FAIL,
                        reason=f"Candidate requires 100% remote work, but role is {job.remote_type} in '{job.location}'.",
                        evidence=f"Candidate location: '{candidate.location}', preference: '{candidate.remote_preference}'",
                        is_hard_constraint=True,
                    )

        return EligibilityCheckResult(
            rule_id="LOCATION_REMOTE",
            status=RuleCheckStatus.PASS,
            reason="Job location and remote work policy align with candidate preferences.",
            evidence=f"Job location: '{job.location}', remote type: {job.remote_type}",
            is_hard_constraint=True,
        )

    @classmethod
    def _check_minimum_experience(
        cls, candidate: CandidateProfile, job: Job
    ) -> EligibilityCheckResult:
        """Checks for explicit minimum years of experience in job description."""
        desc = job.description
        # Match patterns like "8+ years", "minimum 5 years", "at least 10 years of experience"
        match = re.search(
            r"(?:minimum|at least|requires?)\s+(\d{1,2})\+?\s+years?(?:\s+of)?\s+experience",
            desc,
            re.IGNORECASE,
        )
        if not match:
            # Also check for "(\d{1,2})\+\s+years of experience"
            match = re.search(r"(\d{1,2})\+\s+years(?:\s+of)?\s+experience", desc, re.IGNORECASE)

        if match:
            required_years = float(match.group(1))
            candidate_years = candidate.years_of_experience

            # If job requires significantly more experience than candidate has (gap > 2 years)
            if required_years > candidate_years + 2.0:
                return EligibilityCheckResult(
                    rule_id="MIN_EXPERIENCE",
                    status=RuleCheckStatus.FAIL,
                    reason=f"Job explicitly requires {int(required_years)}+ years of experience; candidate has {candidate_years:.1f} years.",
                    evidence=f"Candidate years: {candidate_years}, required: {required_years}",
                    is_hard_constraint=True,
                )
            elif required_years > candidate_years:
                return EligibilityCheckResult(
                    rule_id="MIN_EXPERIENCE",
                    status=RuleCheckStatus.UNKNOWN,
                    reason=f"Job asks for {int(required_years)}+ years; candidate has {candidate_years:.1f} years (close to threshold).",
                    evidence=f"Candidate years: {candidate_years}, required: {required_years}",
                    is_hard_constraint=False,
                )
            else:
                return EligibilityCheckResult(
                    rule_id="MIN_EXPERIENCE",
                    status=RuleCheckStatus.PASS,
                    reason=f"Candidate has {candidate_years:.1f} years, meeting the {int(required_years)}+ years requirement.",
                    evidence=f"Candidate years: {candidate_years}, required: {required_years}",
                    is_hard_constraint=True,
                )

        return EligibilityCheckResult(
            rule_id="MIN_EXPERIENCE",
            status=RuleCheckStatus.NOT_APPLICABLE,
            reason="No explicit numerical minimum years requirement found in job description.",
            is_hard_constraint=False,
        )

    @classmethod
    def _check_mandatory_skills(
        cls, candidate: CandidateProfile, job: Job
    ) -> EligibilityCheckResult:
        """Checks if any hard mandatory skill requirement defined in JobRequirement is violated."""
        mandatory_reqs = [
            req.value for req in (job.requirements or [])
            if req.requirement_type == "MANDATORY_SKILL"
        ]

        if not mandatory_reqs:
            return EligibilityCheckResult(
                rule_id="MANDATORY_SKILLS",
                status=RuleCheckStatus.NOT_APPLICABLE,
                reason="No explicit mandatory skill constraints recorded for this job.",
                is_hard_constraint=False,
            )

        candidate_skills = {
            SkillRegistry.normalize_skill(s.skill_name)
            for s in candidate.skills
            if s.is_verified
        }

        missing_mandatory = []
        for req in mandatory_reqs:
            norm_req = SkillRegistry.normalize_skill(req)
            if norm_req not in candidate_skills:
                missing_mandatory.append(norm_req)

        if missing_mandatory:
            return EligibilityCheckResult(
                rule_id="MANDATORY_SKILLS",
                status=RuleCheckStatus.FAIL,
                reason=f"Candidate lacks verified evidence for mandatory skills: {', '.join(missing_mandatory)}",
                evidence=f"Missing: {missing_mandatory}",
                is_hard_constraint=True,
            )

        return EligibilityCheckResult(
            rule_id="MANDATORY_SKILLS",
            status=RuleCheckStatus.PASS,
            reason="All explicit mandatory skill constraints are verified in candidate profile.",
            evidence=f"Verified: {mandatory_reqs}",
            is_hard_constraint=True,
        )
