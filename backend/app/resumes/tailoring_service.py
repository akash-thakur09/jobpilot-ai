import re
from typing import List, Dict, Any, Optional
from backend.app.models.candidate import CandidateProfile
from backend.app.models.job import Job
from backend.app.models.matching import MatchScore
from backend.app.matching.skill_registry import SkillRegistry
from backend.app.resumes.schemas import (
    TailoredResumeContent,
    TailoredExperience,
    TailoredProject,
    TailoredEducation,
)
from backend.app.providers.ollama import OllamaProvider
from backend.app.core.logging import logger


class ResumeTailoringService:
    """
    Constructs job-specific, ATS-optimized tailored resume content
    strictly derived from verified candidate facts.
    """

    @classmethod
    def build_deterministic_content(
        cls, candidate: CandidateProfile, job: Job, match_score: Optional[MatchScore] = None
    ) -> TailoredResumeContent:
        # 1. Contact Info & Links
        links = []
        if candidate.linkedin_url:
            links.append(f"LinkedIn: {candidate.linkedin_url}")
        if candidate.github_url:
            links.append(f"GitHub: {candidate.github_url}")
        if candidate.portfolio_url:
            links.append(f"Portfolio: {candidate.portfolio_url}")

        # 2. Tailored Summary
        summary = candidate.summary
        target_role = job.title
        if target_role.lower() not in summary.lower():
            summary = f"Results-driven professional aligned with {job.title} roles at {job.company}. {candidate.summary}"

        # 3. Categorized & Prioritized Verified Skills
        job_skills = set(SkillRegistry.extract_skills_from_text(f"{job.title} {job.description}"))
        verified_skills = [s for s in (candidate.skills or []) if s.is_verified]

        # Prioritize skills that match the job
        matching_skills = []
        other_skills = []
        for s in verified_skills:
            norm = SkillRegistry.normalize_skill(s.skill_name)
            if norm in job_skills:
                matching_skills.append(norm)
            else:
                other_skills.append(norm)

        skills_by_category: Dict[str, List[str]] = {}
        if matching_skills:
            skills_by_category["Core Technologies & Relevant Skills"] = sorted(list(set(matching_skills)))
        if other_skills:
            skills_by_category["Additional Technical Skills"] = sorted(list(set(other_skills)))

        # 4. Experiences (Prioritizing relevant bullets)
        tailored_experiences = []
        for exp in candidate.experiences or []:
            bullets = list(exp.verified_bullets or [])
            # Sort bullets so bullets mentioning job technologies appear first
            def bullet_relevance(b: str) -> int:
                b_skills = SkillRegistry.extract_skills_from_text(b)
                return len(set(b_skills).intersection(job_skills))

            sorted_bullets = sorted(bullets, key=bullet_relevance, reverse=True)

            tailored_experiences.append(
                TailoredExperience(
                    company=exp.company,
                    role=exp.role,
                    location=exp.location,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    is_current=exp.is_current,
                    bullet_points=sorted_bullets,
                )
            )

        # 5. Projects (Prioritizing projects with matching technologies)
        tailored_projects = []
        projects = list(candidate.projects or [])

        def project_relevance(p) -> int:
            p_techs = {SkillRegistry.normalize_skill(t) for t in (p.technologies or [])}
            return len(p_techs.intersection(job_skills))

        sorted_projects = sorted(projects, key=project_relevance, reverse=True)
        for proj in sorted_projects:
            tailored_projects.append(
                TailoredProject(
                    title=proj.title,
                    technologies=proj.technologies or [],
                    description=proj.description,
                    bullet_points=proj.verified_bullets or [],
                    url=proj.project_url,
                )
            )

        # 6. Educations
        tailored_educations = [
            TailoredEducation(
                institution=ed.institution,
                degree=ed.degree,
                field_of_study=ed.field_of_study,
                graduation_year=ed.graduation_year,
            )
            for ed in (candidate.educations or [])
        ]

        return TailoredResumeContent(
            full_name=candidate.full_name,
            email=candidate.email,
            phone=candidate.phone,
            location=candidate.location,
            links=links,
            summary=summary,
            skills_by_category=skills_by_category,
            experiences=tailored_experiences,
            projects=tailored_projects,
            educations=tailored_educations,
        )
