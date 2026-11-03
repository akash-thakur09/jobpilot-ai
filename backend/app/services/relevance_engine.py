import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Union
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.job import Job
from backend.app.models.enums import RelevanceClassification
from backend.app.schemas.candidate import JobSearchPreferences
from backend.app.services.candidate_service import CandidateService
from backend.app.services.salary_service import evaluate_salary_compatibility
from backend.app.core.logging import logger


NON_TECHNICAL_TITLES = [
    "legal", "counsel", "paralegal", "attorney", "lawyer",
    "human resources", "talent acquisition", "recruiter", "people partner", "people operations",
    "sales", "account executive", "business development", "inside sales",
    "marketing", "content writer", "copywriter", "seo specialist",
    "finance", "accounting", "accountant", "payroll", "financial analyst",
    "facilities", "office manager", "administrative assistant", "executive assistant", "receptionist",
    "nurse", "physician", "pharmacist", "supply chain", "logistics coordinator",
    "customer support", "customer service representative", "telemarketing", "cook", "chef"
]

TECHNICAL_EXEMPTIONS = [
    "software", "engineer", "developer", "architect", "programmer", "data", "ml", "ai", "machine learning", "devops", "cloud"
]


@dataclass
class RelevanceResult:
    score: float
    classification: RelevanceClassification
    matched_roles: List[str] = field(default_factory=list)
    matched_skills: List[str] = field(default_factory=list)
    missing_priority_skills: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    component_scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relevance_score": self.score,
            "relevance_classification": self.classification.value if hasattr(self.classification, "value") else str(self.classification),
            "matched_roles": self.matched_roles,
            "matched_skills": self.matched_skills,
            "missing_priority_skills": self.missing_priority_skills,
            "reasons": self.reasons,
            "component_scores": self.component_scores,
        }


class RelevanceEngine:
    """
    Deterministic scoring and classification engine to evaluate whether a discovered
    job matches a candidate's target career trajectory, skill set, and location preferences.
    """

    @classmethod
    def evaluate_job(
        cls,
        job_title: str,
        job_description: str,
        job_location: Optional[str] = None,
        remote_allowed: bool = False,
        job_work_mode: Optional[str] = None,
        job_experience_min: Optional[float] = None,
        job_experience_max: Optional[float] = None,
        preferences: Optional[JobSearchPreferences] = None,
        job_salary_min: Optional[float] = None,
        job_salary_max: Optional[float] = None,
        job_currency: Optional[str] = "USD",
    ) -> RelevanceResult:
        if preferences is None:
            preferences = JobSearchPreferences()

        title_lower = (job_title or "").lower().strip()
        desc_lower = (job_description or "").lower()
        full_text = f"{title_lower} {desc_lower}"
        loc_lower = (job_location or "").lower().strip()

        matched_roles: List[str] = []
        matched_skills: List[str] = []
        missing_priority: List[str] = []
        reasons: List[str] = []

        # ---------------------------------------------------------
        # 1. Non-Technical / Out-of-Scope Penalty Check
        # ---------------------------------------------------------
        is_strictly_non_tech = False
        penalty = 0.0

        for non_tech in NON_TECHNICAL_TITLES:
            pattern = rf"\b{re.escape(non_tech)}\b"
            if re.search(pattern, title_lower):
                # Check if there is an explicit technical exemption in the title
                has_tech_exemption = any(
                    re.search(rf"\b{re.escape(t)}\b", title_lower) for t in TECHNICAL_EXEMPTIONS
                )
                if not has_tech_exemption:
                    is_strictly_non_tech = True
                    penalty = 65.0
                    reasons.append(f"Non-technical role detected in title ('{non_tech}')")
                    break

        # ---------------------------------------------------------
        # 2. Title & Role Family Matching (Max 40 points)
        # ---------------------------------------------------------
        title_score = 0.0
        target_roles = preferences.target_roles or preferences.target_titles or []
        role_aliases = preferences.role_aliases or {}

        # Collect all role terms to check
        all_role_targets: List[str] = list(target_roles)
        for target, aliases in role_aliases.items():
            for alias in aliases:
                if alias not in all_role_targets:
                    all_role_targets.append(alias)

        best_title_match: Optional[str] = None
        exact_target_match = False

        for role in all_role_targets:
            role_clean = role.lower().strip()
            if not role_clean:
                continue
            # Exact or phrase match in title
            pattern = rf"\b{re.escape(role_clean)}\b"
            if re.search(pattern, title_lower):
                matched_roles.append(role)
                if not best_title_match:
                    best_title_match = role
                if role in target_roles:
                    exact_target_match = True

        if exact_target_match:
            title_score = 40.0
            reasons.append(f"Direct match for target role: '{best_title_match}'")
        elif matched_roles:
            title_score = 35.0
            reasons.append(f"Matched role alias: '{matched_roles[0]}'")
        else:
            # Partial keyword match in title
            core_tech_terms = ["full stack", "fullstack", "software", "developer", "engineer", "backend", "frontend", "ai", "python"]
            matched_terms = [t for t in core_tech_terms if re.search(rf"\b{re.escape(t)}\b", title_lower)]
            if matched_terms:
                title_score = min(25.0, 10.0 + (len(matched_terms) * 5.0))
                reasons.append(f"Contains relevant engineering keywords: {', '.join(matched_terms)}")
            else:
                title_score = 0.0
                reasons.append("Title does not match target roles or technical keywords")

        # ---------------------------------------------------------
        # 3. Skills Alignment (Max 35 points)
        # ---------------------------------------------------------
        skills_score = 0.0

        # A. Must-Have Skills (15 points)
        must_haves = preferences.must_have_skills or preferences.required_skills or []
        must_have_matched = 0
        for skill in must_haves:
            skill_clean = skill.lower().strip()
            if not skill_clean:
                continue
            pattern = rf"\b{re.escape(skill_clean)}\b"
            if re.search(pattern, full_text):
                matched_skills.append(skill)
                must_have_matched += 1
            else:
                missing_priority.append(skill)

        if must_haves:
            must_have_pct = must_have_matched / len(must_haves)
            must_have_score = round(must_have_pct * 15.0, 1)
            skills_score += must_have_score
            if must_have_matched > 0:
                reasons.append(f"Matched {must_have_matched}/{len(must_haves)} must-have skills")
        else:
            skills_score += 15.0  # No constraints specified

        # B. Preferred Skills (10 points)
        preferred = preferences.preferred_skills or []
        preferred_matched = 0
        for skill in preferred:
            skill_clean = skill.lower().strip()
            if not skill_clean:
                continue
            pattern = rf"\b{re.escape(skill_clean)}\b"
            if re.search(pattern, full_text):
                matched_skills.append(skill)
                preferred_matched += 1

        if preferred:
            preferred_pct = preferred_matched / len(preferred)
            preferred_score = round(min(1.0, preferred_pct * 1.5) * 10.0, 1)
            skills_score += preferred_score
            if preferred_matched > 0:
                reasons.append(f"Matched {preferred_matched} preferred skills")
        else:
            skills_score += 10.0

        # C. AI/GenAI Focus Skills (10 points)
        ai_skills = preferences.ai_genai_focus_skills or preferences.ai_focus_skills or []
        ai_matched = 0
        for skill in ai_skills:
            skill_clean = skill.lower().strip()
            if not skill_clean:
                continue
            pattern = rf"\b{re.escape(skill_clean)}\b"
            if re.search(pattern, full_text):
                if skill not in matched_skills:
                    matched_skills.append(skill)
                ai_matched += 1

        if ai_skills:
            ai_pct = ai_matched / len(ai_skills)
            ai_score = round(min(1.0, ai_pct * 2.0) * 10.0, 1)
            skills_score += ai_score
            if ai_matched > 0:
                reasons.append(f"Matched AI/GenAI specialization skills ({ai_matched})")
        else:
            skills_score += 10.0

        # ---------------------------------------------------------
        # 4. Location & Remote Compatibility (Max 15 points)
        # ---------------------------------------------------------
        location_score = 0.0
        is_remote_job = (
            remote_allowed
            or "remote" in loc_lower
            or "anywhere" in loc_lower
            or "distributed" in loc_lower
            or "work from home" in loc_lower
            or "worldwide" in loc_lower
        )

        candidate_wants_remote = (
            preferences.allow_remote_opportunities
            or preferences.allow_remote
            or "remote" in [l.lower() for l in preferences.preferred_locations]
        )

        # Check location match
        matched_loc = None
        for pref_loc in preferences.preferred_locations:
            pref_clean = pref_loc.lower().strip()
            if pref_clean and pref_clean != "remote" and pref_clean in loc_lower:
                matched_loc = pref_loc
                break

        if is_remote_job and candidate_wants_remote:
            location_score = 15.0
            reasons.append("Remote job matching candidate remote preference")
        elif matched_loc:
            location_score = 15.0
            reasons.append(f"Matches preferred location: '{matched_loc}'")
        elif not loc_lower or "unspecified" in loc_lower:
            location_score = 8.0
            reasons.append("Location unspecified; partial compatibility credit")
        elif is_remote_job:
            location_score = 12.0
            reasons.append("Remote position")
        else:
            # Job is on-site in a non-matching location
            location_score = 0.0
            reasons.append(f"Location '{job_location}' does not match preferred locations")

        # ---------------------------------------------------------
        # 5. Work Mode & Experience Alignment (Max 10 points)
        # ---------------------------------------------------------
        work_mode_score = 5.0
        if job_work_mode and preferences.work_modes:
            mode_matches = any(
                m.lower() in (job_work_mode or "").lower() for m in preferences.work_modes
            )
            if not mode_matches:
                work_mode_score = 2.0
                reasons.append(f"Work arrangement '{job_work_mode}' differs from preferences")

        experience_score = 5.0
        pref_min = (
            preferences.target_min_experience_years
            if preferences.target_min_experience_years is not None
            else preferences.preferred_min_years
        )
        pref_max = (
            preferences.target_max_experience_years
            if preferences.target_max_experience_years is not None
            else preferences.preferred_max_years
        )

        if job_experience_min is not None and pref_max is not None:
            if job_experience_min > (pref_max + 2.0):
                experience_score = 1.0
                reasons.append(f"Requires {job_experience_min}+ yrs experience (above target max {pref_max})")

        total_work_exp_score = round(work_mode_score + experience_score, 1)

        # ---------------------------------------------------------
        # 6. Salary / Compensation Preference Signal
        # ---------------------------------------------------------
        salary_delta = 0.0
        target_min_lpa = preferences.minimum_package_lpa
        target_min_usd = getattr(preferences, "legacy_min_salary_usd", None)

        salary_eval = evaluate_salary_compatibility(
            job_salary_min=job_salary_min,
            job_salary_max=job_salary_max,
            job_currency=job_currency,
            candidate_min_lpa=target_min_lpa,
            candidate_min_usd=target_min_usd if not target_min_lpa else None,
        )

        if salary_eval["status"] == "MEETS_TARGET":
            salary_delta = 2.0
            reasons.append(salary_eval["explanation"])
        elif salary_eval["status"] == "BELOW_TARGET":
            salary_delta = -5.0
            reasons.append(salary_eval["explanation"])
        # UNDISCLOSED, FOREIGN_CURRENCY, and NO_PREFERENCE apply 0 delta (neutral)

        # ---------------------------------------------------------
        # Final Score & Classification
        # ---------------------------------------------------------
        raw_score = title_score + skills_score + location_score + total_work_exp_score + salary_delta - penalty
        final_score = max(0.0, min(100.0, round(raw_score, 1)))

        if final_score >= 75.0:
            classification = RelevanceClassification.HIGHLY_RELEVANT
        elif final_score >= 45.0:
            classification = RelevanceClassification.POTENTIALLY_RELEVANT
        else:
            classification = RelevanceClassification.LOW_RELEVANCE

        component_scores = {
            "title_score": title_score,
            "skills_score": skills_score,
            "location_score": location_score,
            "work_mode_and_exp_score": total_work_exp_score,
            "salary_delta": salary_delta,
            "penalty": penalty,
        }

        return RelevanceResult(
            score=final_score,
            classification=classification,
            matched_roles=matched_roles,
            matched_skills=matched_skills,
            missing_priority_skills=missing_priority,
            reasons=reasons,
            component_scores=component_scores,
        )

    @classmethod
    def evaluate_job_instance(
        cls,
        job: Union[Job, Dict[str, Any]],
        preferences: Optional[JobSearchPreferences] = None,
    ) -> RelevanceResult:
        """Evaluates relevance for either a Job ORM instance or a raw dictionary."""
        if isinstance(job, dict):
            remote_val = job.get("remote_allowed", False) or job.get("remote_type") == "REMOTE"
            return cls.evaluate_job(
                job_title=job.get("title", ""),
                job_description=job.get("description", "") or "",
                job_location=job.get("location"),
                remote_allowed=bool(remote_val),
                job_work_mode=job.get("employment_type") or job.get("work_mode"),
                job_experience_min=job.get("experience_years_min"),
                job_experience_max=job.get("experience_years_max"),
                preferences=preferences,
                job_salary_min=job.get("salary_min"),
                job_salary_max=job.get("salary_max"),
                job_currency=job.get("currency", "USD"),
            )

        return cls.evaluate_job(
            job_title=job.title,
            job_description=job.description or "",
            job_location=job.location,
            remote_allowed=(job.remote_type == "REMOTE"),
            job_work_mode=job.employment_type,
            preferences=preferences,
            job_salary_min=job.salary_min,
            job_salary_max=job.salary_max,
            job_currency=job.currency or "USD",
        )

    @classmethod
    async def re_evaluate_stored_jobs(
        cls, session: AsyncSession, candidate_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Re-scores all stored jobs in the database against the candidate's current search preferences.
        Updates job records in-place and returns an audit breakdown.
        """
        preferences = await CandidateService.get_search_preferences(session)
        jobs_res = await session.execute(select(Job))
        all_jobs = jobs_res.scalars().all()

        total = len(all_jobs)
        highly_relevant = 0
        potentially_relevant = 0
        low_relevance = 0

        for job in all_jobs:
            result = cls.evaluate_job_instance(job, preferences)
            job.relevance_score = result.score
            job.relevance_classification = result.classification.value
            job.relevance_metadata = result.to_dict()

            if result.classification == RelevanceClassification.HIGHLY_RELEVANT:
                highly_relevant += 1
            elif result.classification == RelevanceClassification.POTENTIALLY_RELEVANT:
                potentially_relevant += 1
            else:
                low_relevance += 1

        await session.commit()

        logger.info(
            "Re-evaluated %d stored jobs: %d HIGHLY_RELEVANT, %d POTENTIALLY_RELEVANT, %d LOW_RELEVANCE",
            total,
            highly_relevant,
            potentially_relevant,
            low_relevance,
        )

        return {
            "total_evaluated": total,
            "highly_relevant_count": highly_relevant,
            "potentially_relevant_count": potentially_relevant,
            "low_relevance_count": low_relevance,
        }
