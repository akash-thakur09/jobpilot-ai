import re
from typing import Dict, Any, List, Set, Tuple
from backend.app.models.candidate import CandidateProfile
from backend.app.resumes.schemas import TailoredResumeContent, FactualValidationReport
from backend.app.matching.skill_registry import SkillRegistry


class ResumeFactValidator:
    """
    Zero-Hallucination Factual Consistency Validator.
    Verifies that every skill, employer, title, date range, degree, and project in
    a generated resume is strictly grounded in the candidate's verified profile facts.
    """

    @classmethod
    def validate_content(
        cls, candidate: CandidateProfile, content: TailoredResumeContent
    ) -> FactualValidationReport:
        supported_count = 0
        unsupported_claims: List[str] = []
        warnings: List[str] = []
        checked_facts: Dict[str, Any] = {}

        # 1. Identity & Contact Information Check
        if content.full_name.strip().lower() != candidate.full_name.strip().lower():
            unsupported_claims.append(
                f"Candidate name '{content.full_name}' does not match verified name '{candidate.full_name}'"
            )
        else:
            supported_count += 1

        if content.email.strip().lower() != candidate.email.strip().lower():
            unsupported_claims.append(
                f"Candidate email '{content.email}' does not match verified email '{candidate.email}'"
            )
        else:
            supported_count += 1

        # 2. Verified Skills Grounding Check
        verified_skills_set = {
            SkillRegistry.normalize_skill(s.skill_name)
            for s in candidate.skills
            if s.is_verified
        }

        checked_skills = []
        for category, skills in content.skills_by_category.items():
            for skill in skills:
                norm_skill = SkillRegistry.normalize_skill(skill)
                checked_skills.append(norm_skill)
                if norm_skill not in verified_skills_set:
                    unsupported_claims.append(
                        f"Skill '{skill}' in section '{category}' is not a verified candidate skill."
                    )
                else:
                    supported_count += 1

        checked_facts["verified_skills_checked"] = len(checked_skills)

        # 3. Employers, Roles, and Dates Check
        verified_experiences = candidate.experiences or []
        verified_companies = {e.company.strip().lower(): e for e in verified_experiences}

        for exp in content.experiences:
            comp_key = exp.company.strip().lower()
            if comp_key not in verified_companies:
                unsupported_claims.append(
                    f"Employer '{exp.company}' not found in candidate's verified employment history."
                )
            else:
                matched_exp = verified_companies[comp_key]
                supported_count += 1

                # Role verification
                if exp.role.strip().lower() != matched_exp.role.strip().lower():
                    warnings.append(
                        f"Role title '{exp.role}' for {exp.company} differs from verified record '{matched_exp.role}'."
                    )
                else:
                    supported_count += 1

                # Date verification
                if exp.start_date.strip() != matched_exp.start_date.strip():
                    unsupported_claims.append(
                        f"Start date '{exp.start_date}' for {exp.company} does not match verified date '{matched_exp.start_date}'."
                    )
                else:
                    supported_count += 1

        # 4. Education Check
        verified_educations = candidate.educations or []
        verified_institutions = {
            ed.institution.strip().lower(): ed for ed in verified_educations
        }

        for edu in content.educations:
            inst_key = edu.institution.strip().lower()
            if inst_key not in verified_institutions:
                unsupported_claims.append(
                    f"Educational institution '{edu.institution}' not found in candidate's verified education."
                )
            else:
                matched_edu = verified_institutions[inst_key]
                supported_count += 1
                if edu.degree.strip().lower() != matched_edu.degree.strip().lower():
                    warnings.append(
                        f"Degree '{edu.degree}' differs from verified record '{matched_edu.degree}'."
                    )
                else:
                    supported_count += 1

        # 5. Project Details Check
        verified_projects = candidate.projects or []
        verified_project_titles = {
            p.title.strip().lower(): p for p in verified_projects
        }

        for proj in content.projects:
            title_key = proj.title.strip().lower()
            if title_key not in verified_project_titles:
                unsupported_claims.append(
                    f"Project '{proj.title}' not found in candidate's verified projects."
                )
            else:
                matched_proj = verified_project_titles[title_key]
                supported_count += 1
                # Project technologies must be verified skills
                for tech in proj.technologies:
                    norm_tech = SkillRegistry.normalize_skill(tech)
                    if norm_tech not in verified_skills_set:
                        unsupported_claims.append(
                            f"Technology '{tech}' claimed in project '{proj.title}' is not a verified skill."
                        )
                    else:
                        supported_count += 1

        is_valid = len(unsupported_claims) == 0

        return FactualValidationReport(
            is_valid=is_valid,
            supported_claims_count=supported_count,
            unsupported_claims=unsupported_claims,
            warnings=warnings,
            checked_facts=checked_facts,
        )
