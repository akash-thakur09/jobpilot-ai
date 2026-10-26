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

        # Weighted final score calculation
        raw_final = (
            (skills_score * weights.skills)
            + (title_score * weights.title)
            + (experience_score * weights.experience)
            + (project_score * weights.projects)
            + (location_score * weights.location_remote)
            + (salary_score * weights.salary)
        )
        final_score = round(max(0.0, min(100.0, raw_final)), 2)

        breakdown = ScoreBreakdown(
            skills_score=round(skills_score, 2),
            title_score=round(title_score, 2),
            experience_score=round(experience_score, 2),
            projects_score=round(project_score, 2),
            location_remote_score=round(location_score, 2),
            salary_score=round(salary_score, 2),
            final_score=final_score,
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
        cand_pref = candidate.remote_preference.upper()
        job_remote = job.remote_type.upper()

        if job_remote == RemoteType.REMOTE.value:
            return 100.0

        if cand_pref == job_remote:
            return 100.0

        # Partial compatibility for hybrid if in same location
        if job_remote == RemoteType.HYBRID.value:
            if candidate.location.lower() in job.location.lower():
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
