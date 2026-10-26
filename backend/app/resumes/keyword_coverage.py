from typing import List, Set
from backend.app.models.candidate import CandidateProfile
from backend.app.models.job import Job
from backend.app.matching.skill_registry import SkillRegistry
from backend.app.resumes.schemas import KeywordCoverageReport


class KeywordCoverageValidator:
    """
    Evaluates keyword coverage between job requirements and candidate profile/resume.
    Accurately highlights gaps without fabricating missing qualifications.
    """

    @classmethod
    def evaluate_coverage(
        cls, candidate: CandidateProfile, job: Job
    ) -> KeywordCoverageReport:
        # Extract skills from job description and title
        job_skills = SkillRegistry.extract_skills_from_text(f"{job.title} {job.description}")
        title_skills = set(SkillRegistry.extract_skills_from_text(job.title))

        # Explicit requirements from JobRequirement if available
        explicit_mandatory = {
            SkillRegistry.normalize_skill(req.value)
            for req in (job.requirements or [])
            if req.requirement_type == "MANDATORY_SKILL"
        }

        required_keywords = list(explicit_mandatory.union(title_skills))
        preferred_keywords = [s for s in job_skills if s not in required_keywords]

        candidate_verified_skills = {
            SkillRegistry.normalize_skill(s.skill_name)
            for s in candidate.skills
            if s.is_verified
        }

        matched_req = [k for k in required_keywords if k in candidate_verified_skills]
        missing_req = [k for k in required_keywords if k not in candidate_verified_skills]
        matched_pref = [k for k in preferred_keywords if k in candidate_verified_skills]

        # Calculate coverage score
        total_targets = len(required_keywords) + len(preferred_keywords)
        if total_targets == 0:
            coverage_score = 100.0
        else:
            # Required keywords have 2x weight of preferred
            req_weight = 2.0
            pref_weight = 1.0
            max_points = (len(required_keywords) * req_weight) + (len(preferred_keywords) * pref_weight)
            earned_points = (len(matched_req) * req_weight) + (len(matched_pref) * pref_weight)
            coverage_score = round((earned_points / max_points) * 100.0, 1)

        return KeywordCoverageReport(
            matched_required_keywords=matched_req,
            matched_preferred_keywords=matched_pref,
            missing_required_keywords=missing_req,
            coverage_score=coverage_score,
        )
