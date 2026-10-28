import re
from typing import List, Tuple, Set, Dict, Any, Optional
from backend.app.models.candidate import CandidateProfile
from backend.app.models.job import Job
from backend.app.models.enums import RemoteType
from backend.app.matching.schemas import ScoringWeights, ScoreBreakdown
from backend.app.matching.skill_registry import SkillRegistry


class DeterministicScoringService:
    @classmethod
    def calculate_score(
        cls,
        candidate: CandidateProfile,
        job: Job,
        weights: Optional[ScoringWeights] = None,
        feedback: Optional[Any] = None,
    ) -> Tuple[ScoreBreakdown, List[str], List[str], List[str], List[str]]:
        """
        Calculates explainable, deterministic component scores from 0 to 100.
        Returns:
            (breakdown: ScoreBreakdown, matched_req, matched_pref, missing_req, missing_pref)
        """
        weights = weights or ScoringWeights()

        # 1. Skills Scoring (40%)
        (
            skills_score,
            matched_req,
            matched_pref,
            missing_req,
            missing_pref,
        ) = cls._score_skills(candidate, job)

        # 2. Title Relevance Scoring (20%)
        title_score = cls._score_title(candidate, job)

        # 3. Experience Scoring (15%)
        experience_score = cls._score_experience(candidate, job)

        # 4. Project Relevance Scoring (10%)
        project_score = cls._score_projects(candidate, job)

        # 5. Location and Remote Scoring (10%)
        location_score = cls._score_location(candidate, job)

        # 6. Salary & Employment Scoring (5%)
        salary_score = cls._score_salary(candidate, job)

        # 7. Evaluate Search Preferences Contributions
        search_prefs = getattr(candidate, "search_preferences", {}) or {}
        pref_contributions: Dict[str, Any] = {}
        pref_explanation_parts = []

        # Role keywords
        role_keywords = search_prefs.get("role_keywords", [])
        matched_keywords = []
        if role_keywords:
            job_text_lower = f"{job.title} {job.description}".lower()
            for kw in role_keywords:
                if kw.lower() in job_text_lower:
                    matched_keywords.append(kw)
            pref_contributions["matched_role_keywords"] = matched_keywords
            if matched_keywords:
                title_score = min(100.0, title_score + 10.0 * (len(matched_keywords) / len(role_keywords)))
                pref_explanation_parts.append(f"Matched role keywords: {', '.join(matched_keywords)}")

        # Company preferences
        preferred_companies = [c.lower() for c in search_prefs.get("preferred_companies", [])]
        excluded_companies = [c.lower() for c in search_prefs.get("excluded_companies", [])]
        job_company_lower = job.company.lower()

        if any(exc in job_company_lower for exc in excluded_companies):
            pref_contributions["is_excluded_company"] = True
            title_score = max(0.0, title_score - 50.0)
            pref_explanation_parts.append(f"Company '{job.company}' is in candidate excluded companies list")
        elif any(pref in job_company_lower for pref in preferred_companies):
            pref_contributions["matched_preferred_company"] = True
            title_score = min(100.0, title_score + 15.0)
            pref_explanation_parts.append(f"Company '{job.company}' is in candidate preferred companies list")

        # Location preferences
        preferred_locations = [loc.lower() for loc in search_prefs.get("preferred_locations", [])]
        if preferred_locations:
            if any(pl in job.location.lower() for pl in preferred_locations):
                location_score = 100.0
                pref_contributions["matched_preferred_location"] = True
                pref_explanation_parts.append(f"Job location '{job.location}' satisfies preferred location")
            elif job.remote_type == RemoteType.REMOTE.value:
                pref_contributions["matched_preferred_location"] = True
                pref_explanation_parts.append("Fully remote job satisfies location preferences")

        # Salary preferences
        target_min_sal = search_prefs.get("min_salary") or candidate.target_salary_min
        if target_min_sal:
            if job.salary_min or job.salary_max:
                if (job.salary_max and job.salary_max >= target_min_sal) or (job.salary_min and job.salary_min >= target_min_sal):
                    pref_contributions["salary_satisfies_target"] = True
                    pref_explanation_parts.append(f"Salary meets minimum requirement of ${target_min_sal:,.0f}")
                else:
                    pref_contributions["salary_satisfies_target"] = False
                    pref_explanation_parts.append(f"Disclosed salary is below target minimum of ${target_min_sal:,.0f}")
            else:
                pref_contributions["salary_satisfies_target"] = None  # Undisclosed: do not assume satisfied

        pref_contributions["explanation"] = "; ".join(pref_explanation_parts) if pref_explanation_parts else "Standard evaluation."

        # Weighted baseline score calculation
        raw_final = (
            (skills_score * weights.skills)
            + (title_score * weights.title)
            + (experience_score * weights.experience)
            + (project_score * weights.projects)
            + (location_score * weights.location_remote)
            + (salary_score * weights.salary)
        )

        # Freshness adjustments and warnings
        freshness_warning = None
        freshness_adj = 0.0
        job_freshness = getattr(job, "freshness_status", "ACTIVE")
        if job_freshness == "CONFIRMED_CLOSED":
            freshness_adj = -40.0
            freshness_warning = f"Listing confirmed closed by source ({getattr(job, 'freshness_reason', '') or 'Inactive'})."
        elif job_freshness == "POTENTIALLY_STALE":
            freshness_adj = -10.0
            freshness_warning = f"Listing may be stale ({getattr(job, 'freshness_reason', '') or 'Not seen recently'})."
        elif job_freshness == "UNKNOWN":
            freshness_warning = "Listing verification status is currently unknown."

        # Duplicate cluster status
        duplicate_warning = None
        if getattr(job, "duplicate_cluster_id", None):
            duplicate_warning = "Listing is part of a cross-source duplicate cluster."

        # Feedback adjustments
        feedback_adj = 0.0
        feedback_note = None
        if feedback:
            fb_type = getattr(feedback, "feedback_type", None)
            from backend.app.services.feedback_service import FeedbackService
            mod, note = FeedbackService.get_score_modifier(fb_type)
            feedback_adj = mod * 100.0
            feedback_note = note

        final_score = round(max(0.0, min(100.0, raw_final + feedback_adj + freshness_adj)), 2)

        # Build explicit positive, negative, and missing contributions
        positive_contributions: List[str] = []
        negative_contributions: List[str] = []
        missing_information: List[str] = []

        if matched_req:
            positive_contributions.append(f"Matched {len(matched_req)} core required skills ({', '.join(matched_req)})")
        if matched_pref:
            positive_contributions.append(f"Matched {len(matched_pref)} preferred skills ({', '.join(matched_pref)})")
        if title_score >= 70.0:
            positive_contributions.append(f"Strong title relevance ({title_score:.0f}%)")
        if experience_score >= 80.0:
            positive_contributions.append("Verified professional experience matches requirements")
        if location_score >= 80.0:
            positive_contributions.append("Location and work arrangement aligns with candidate profile")
        if salary_score >= 80.0:
            positive_contributions.append("Disclosed compensation satisfies salary criteria")
        if feedback_adj > 0:
            positive_contributions.append(feedback_note or "User positive feedback applied")

        if missing_req:
            negative_contributions.append(f"Missing {len(missing_req)} required skills ({', '.join(missing_req)})")
        if freshness_adj < 0:
            negative_contributions.append(freshness_warning or "Listing staleness penalty applied")
        if feedback_adj < 0:
            negative_contributions.append(feedback_note or "User negative feedback penalty applied")
        if pref_contributions.get("is_excluded_company"):
            negative_contributions.append(f"Employer '{job.company}' is in candidate excluded companies list")

        if not job.salary_min and not job.salary_max:
            missing_information.append("Compensation details not disclosed in vacancy posting")
        if not job.location or job.location.lower() == "unknown":
            missing_information.append("Geographical location unspecified")
        if missing_pref:
            missing_information.append(f"Unverified or missing preferred skills ({', '.join(missing_pref)})")
        if job_freshness == "UNKNOWN":
            missing_information.append("Freshness verification status is unknown")

        breakdown = ScoreBreakdown(
            skills_score=round(skills_score, 2),
            title_score=round(title_score, 2),
            experience_score=round(experience_score, 2),
            projects_score=round(project_score, 2),
            location_remote_score=round(location_score, 2),
            salary_score=round(salary_score, 2),
            final_score=final_score,
            preference_contributions=pref_contributions,
            positive_contributions=positive_contributions,
            negative_contributions=negative_contributions,
            missing_information=missing_information,
            freshness_warning=freshness_warning,
            duplicate_warning=duplicate_warning,
            feedback_adjustment=round(feedback_adj, 2) if feedback_adj else None,
            feedback_note=feedback_note,
            scoring_policy_version="1.1.0",
        )

        return (
            breakdown,
            matched_req,
            matched_pref,
            missing_req,
            missing_pref,
        )

    @classmethod
    def _score_skills(
        cls, candidate: CandidateProfile, job: Job
    ) -> Tuple[float, List[str], List[str], List[str], List[str]]:
        """Extracts skills from job and evaluates candidate's verified skills."""
        job_skills = SkillRegistry.extract_skills_from_text(f"{job.title} {job.description}")
        if not job_skills:
            return 80.0, [], [], [], []  # Default neutral score if no specific tech skills listed

        candidate_verified_skills = {
            SkillRegistry.normalize_skill(s.skill_name): s
            for s in candidate.skills
            if s.is_verified
        }

        # Divide job skills into required (appearing in title or first section) vs preferred
        required_skills = []
        preferred_skills = []

        title_skills = SkillRegistry.extract_skills_from_text(job.title)
        for s in job_skills:
            if s in title_skills:
                required_skills.append(s)
            else:
                preferred_skills.append(s)

        # If no skills were specifically in title, treat all detected as required
        if not required_skills:
            required_skills = preferred_skills
            preferred_skills = []

        matched_req = [s for s in required_skills if s in candidate_verified_skills]
        missing_req = [s for s in required_skills if s not in candidate_verified_skills]

        matched_pref = [s for s in preferred_skills if s in candidate_verified_skills]
        missing_pref = [s for s in preferred_skills if s not in candidate_verified_skills]

        # Calculate ratio
        req_ratio = len(matched_req) / len(required_skills) if required_skills else 1.0
        pref_ratio = len(matched_pref) / len(preferred_skills) if preferred_skills else 1.0

        # Required skills are weighted 75%, preferred 25% within the skills component
        if preferred_skills:
            skill_pct = (req_ratio * 75.0) + (pref_ratio * 25.0)
        else:
            skill_pct = req_ratio * 100.0

        return skill_pct, matched_req, matched_pref, missing_req, missing_pref

    @classmethod
    def _score_title(cls, candidate: CandidateProfile, job: Job) -> float:
        """Evaluates similarity between candidate target titles and job title."""
        target_titles = candidate.target_titles or []
        if not target_titles:
            return 60.0  # Neutral baseline if no targets configured

        job_tokens = set(re.findall(r"\w+", job.title.lower()))
        # Remove generic fluff words
        stop_words = {"a", "an", "the", "and", "or", "for", "in", "at", "of", "to"}
        job_tokens = job_tokens - stop_words

        best_score = 0.0
        for target in target_titles:
            target_tokens = set(re.findall(r"\w+", target.lower())) - stop_words
            if not target_tokens or not job_tokens:
                continue

            intersection = job_tokens.intersection(target_tokens)
            union = job_tokens.union(target_tokens)
            jaccard = len(intersection) / len(union)

            # Bonus for exact or key seniority match (Senior, Staff, Lead, Architect)
            seniority_keywords = {"senior", "staff", "lead", "principal", "architect"}
            target_seniority = target_tokens.intersection(seniority_keywords)
            job_seniority = job_tokens.intersection(seniority_keywords)
            seniority_matched = target_seniority == job_seniority

            score = jaccard * 100.0
            if seniority_matched and jaccard > 0.3:
                score += 15.0

            best_score = max(best_score, score)

        return min(100.0, best_score)

    @classmethod
    def _score_experience(cls, candidate: CandidateProfile, job: Job) -> float:
        """Scores candidate experience years against role requirements."""
        cand_years = candidate.years_of_experience
        match = re.search(r"(\d{1,2})\+?\s+years?(?:\s+of)?\s+experience", job.description, re.IGNORECASE)
        if match:
            target_years = float(match.group(1))
            if cand_years >= target_years:
                return 100.0
            elif cand_years >= target_years * 0.7:
                return 80.0
            elif cand_years >= target_years * 0.5:
                return 50.0
            else:
                return 25.0

        # If no explicit years mentioned in job description, evaluate by candidate maturity
        if cand_years >= 5.0:
            return 90.0
        elif cand_years >= 2.0:
            return 75.0
        else:
            return 60.0

    @classmethod
    def _score_projects(cls, candidate: CandidateProfile, job: Job) -> float:
        """Scores candidate demonstrable projects against technologies demanded by job."""
        if not candidate.projects:
            return 50.0  # Neutral baseline if candidate has not added portfolio projects yet

        job_skills = set(SkillRegistry.extract_skills_from_text(job.description))
        if not job_skills:
            return 80.0

        all_project_techs = set()
        for p in candidate.projects:
            for t in p.technologies:
                all_project_techs.add(SkillRegistry.normalize_skill(t))

        overlap = job_skills.intersection(all_project_techs)
        if len(overlap) >= 3:
            return 100.0
        elif len(overlap) == 2:
            return 85.0
        elif len(overlap) == 1:
            return 70.0
        else:
            return 40.0

    @classmethod
    def _score_location(cls, candidate: CandidateProfile, job: Job) -> float:
        """Scores location and remote preference match."""
        cand_pref = (candidate.remote_preference or "REMOTE").upper()
        job_remote = (job.remote_type or "REMOTE").upper()

        if job_remote == RemoteType.REMOTE.value:
            return 100.0

        if cand_pref == job_remote:
            return 100.0

        cand_loc = (candidate.location or "").lower()
        job_loc = (job.location or "").lower()

        # Partial compatibility for hybrid if in same location
        if job_remote == RemoteType.HYBRID.value:
            if cand_loc and job_loc and cand_loc in job_loc:
                return 80.0
            return 40.0

        # On-site in same location
        if candidate.location.lower() in job.location.lower():
            return 75.0

        return 20.0

    @classmethod
    def _score_salary(cls, candidate: CandidateProfile, job: Job) -> float:
        """Scores salary alignment. Missing salary is treated as neutral (75%)."""
        if not job.salary_min and not job.salary_max:
            return 75.0  # Neutral when undisclosed

        if not candidate.target_salary_min:
            return 85.0

        # If job max is below candidate min -> lower score
        if job.salary_max and job.salary_max < candidate.target_salary_min:
            deficit_pct = (candidate.target_salary_min - job.salary_max) / candidate.target_salary_min
            if deficit_pct > 0.20:
                return 20.0
            return 50.0

        # If job min or max covers candidate min -> 100%
        if (job.salary_max and job.salary_max >= candidate.target_salary_min) or (
            job.salary_min and job.salary_min >= candidate.target_salary_min
        ):
            return 100.0

        return 75.0
