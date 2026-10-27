import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from backend.app.models.candidate import CandidateProfile
from backend.app.models.job import Job
from backend.app.models.matching import MatchScore
from backend.app.models.enums import EligibilityStatus
from backend.app.matching.schemas import (
    MatchEvaluationResult,
    ScoringWeights,
    ScoreBreakdown,
)
from backend.app.matching.eligibility import EligibilityService
from backend.app.matching.scoring import DeterministicScoringService
from backend.app.providers.ollama import OllamaProvider
from backend.app.providers.base import BaseAIProvider
from backend.app.core.logging import logger


class MatchingService:
    def __init__(self, ai_provider: Optional[BaseAIProvider] = None):
        self.ai_provider = ai_provider or OllamaProvider()

    async def evaluate_job(
        self,
        session: AsyncSession,
        job_id: str,
        candidate_id: Optional[str] = None,
        weights: Optional[ScoringWeights] = None,
        use_ai: bool = True,
    ) -> MatchScore:
        """Evaluates a single job against the candidate profile and persists the result."""
        # 1. Fetch Candidate Profile with relations
        cand_query = (
            select(CandidateProfile)
            .options(
                selectinload(CandidateProfile.skills),
                selectinload(CandidateProfile.experiences),
                selectinload(CandidateProfile.educations),
                selectinload(CandidateProfile.projects),
            )
        )
        if candidate_id:
            cand_query = cand_query.where(CandidateProfile.id == candidate_id)
        else:
            cand_query = cand_query.limit(1)

        cand_res = await session.execute(cand_query)
        candidate = cand_res.scalar_one_or_none()
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate profile not found. Please create a profile first.",
            )

        # 2. Fetch Job
        job_res = await session.execute(
            select(Job).options(selectinload(Job.requirements)).where(Job.id == job_id)
        )
        job = job_res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID '{job_id}' not found.",
            )

        # 3. Deterministic Eligibility Check
        is_eligible, eligibility_status, checks = EligibilityService.evaluate_eligibility(candidate, job)

        # 4. Deterministic Weighted Scoring
        (
            breakdown,
            matched_req,
            matched_pref,
            missing_req,
            missing_pref,
        ) = DeterministicScoringService.calculate_score(candidate, job, weights)

        # 5. Optional Semantic Analysis via Ollama
        provider_meta: Dict[str, Any] = {"ai_enabled": use_ai, "ai_provider": "none"}
        semantic_summary = None
        if use_ai and await self.ai_provider.is_available():
            try:
                candidate_bullets = []
                for exp in candidate.experiences:
                    candidate_bullets.extend(exp.verified_bullets or [])

                semantic_res = await self.ai_provider.analyze_semantic_match(
                    job_title=job.title,
                    job_description=job.description,
                    candidate_summary=candidate.summary,
                    candidate_bullets=candidate_bullets,
                )
                if semantic_res:
                    semantic_summary = semantic_res.relevance_summary
                    provider_meta = {
                        "ai_enabled": True,
                        "ai_provider": semantic_res.provider,
                        "model": semantic_res.model,
                        "confidence": semantic_res.confidence,
                        "conceptually_similar_skills": semantic_res.conceptually_similar_skills,
                    }
            except Exception as e:
                logger.warning(f"Semantic analysis failed gracefully: {e}")
                provider_meta["ai_error"] = str(e)
        else:
            provider_meta["skipped_reason"] = "AI provider unavailable or disabled"

        # 6. Synthesize Explanation & Warnings
        explanation = self._build_explanation(
            job=job,
            eligibility_status=eligibility_status,
            checks=checks,
            breakdown=breakdown,
            matched_req=matched_req,
            missing_req=missing_req,
            semantic_summary=semantic_summary,
        )

        warnings = []
        if eligibility_status == EligibilityStatus.DISQUALIFIED:
            failed_rules = [c.reason for c in checks if c.status.value == "FAIL"]
            warnings.append(f"Hard constraint disqualified: {'; '.join(failed_rules)}")
        elif eligibility_status == EligibilityStatus.NEEDS_REVIEW:
            unknown_rules = [c.reason for c in checks if c.status.value == "UNKNOWN"]
            warnings.append(f"Needs candidate review: {'; '.join(unknown_rules)}")

        uncertainties = [c.reason for c in checks if c.status.value == "UNKNOWN"]

        job_fingerprint = hashlib.sha256(
            f"{job.title}:{job.company}:{job.description}".encode()
        ).hexdigest()

        # 7. Persist to Database with version preservation
        # Mark previous evaluations as not latest
        await session.execute(
            update(MatchScore)
            .where(MatchScore.job_id == job.id, MatchScore.candidate_id == candidate.id)
            .values(is_latest=False)
        )

        match_record = MatchScore(
            job_id=job.id,
            candidate_id=candidate.id,
            overall_score=breakdown.final_score,
            is_eligible=is_eligible,
            eligibility_status=eligibility_status.value,
            eligibility_checks=[c.model_dump() for c in checks],
            scoring_breakdown=breakdown.model_dump(),
            matching_skills=matched_req + matched_pref,
            missing_skills=missing_req + missing_pref,
            matched_required_skills=matched_req,
            matched_preferred_skills=matched_pref,
            missing_required_skills=missing_req,
            missing_preferred_skills=missing_pref,
            uncertainties=uncertainties,
            warnings=warnings,
            explanation=explanation,
            scoring_policy_version="1.0.0",
            job_fingerprint=job_fingerprint,
            provider_metadata=provider_meta,
            is_latest=True,
        )

        session.add(match_record)
        await session.commit()
        await session.refresh(match_record)
        return match_record

    async def evaluate_all_jobs(
        self, session: AsyncSession, use_ai: bool = False
    ) -> Dict[str, Any]:
        """Evaluates all discovered jobs that lack a current evaluation."""
        jobs_res = await session.execute(select(Job.id))
        job_ids = jobs_res.scalars().all()

        evaluated = 0
        disqualified = 0
        eligible = 0

        for j_id in job_ids:
            try:
                record = await self.evaluate_job(session, j_id, use_ai=use_ai)
                evaluated += 1
                if record.is_eligible:
                    eligible += 1
                else:
                    disqualified += 1
            except Exception as exc:
                logger.error(f"Failed to evaluate job {j_id}: {exc}")

        return {
            "total_jobs_evaluated": evaluated,
            "eligible_jobs": eligible,
            "disqualified_jobs": disqualified,
        }

    @staticmethod
    def _build_explanation(
        job: Job,
        eligibility_status: EligibilityStatus,
        checks: list,
        breakdown: ScoreBreakdown,
        matched_req: list,
        missing_req: list,
        semantic_summary: Optional[str],
    ) -> str:
        parts = []
        if eligibility_status == EligibilityStatus.DISQUALIFIED:
            parts.append(f"DISQUALIFIED: Job does not meet non-negotiable eligibility criteria.")
            for c in checks:
                if c.status.value == "FAIL":
                    parts.append(f"- {c.reason}")
        elif eligibility_status == EligibilityStatus.NEEDS_REVIEW:
            parts.append("NEEDS HUMAN REVIEW: Candidate satisfies baseline checks, but requires manual confirmation.")
        else:
            parts.append("ELIGIBLE: Candidate satisfies all verified hard constraints.")

        parts.append(
            f"Overall Match Score: {breakdown.final_score}/100. "
            f"[Skills: {breakdown.skills_score}%, Title: {breakdown.title_score}%, "
            f"Experience: {breakdown.experience_score}%, Projects: {breakdown.projects_score}%, "
            f"Location: {breakdown.location_remote_score}%, Salary: {breakdown.salary_score}%]."
        )

        if matched_req:
            parts.append(f"Matching core skills: {', '.join(matched_req)}.")
        if missing_req:
            parts.append(f"Missing core skills: {', '.join(missing_req)}.")

        if breakdown.preference_contributions and breakdown.preference_contributions.get("explanation"):
            parts.append(f"Preference Alignment: {breakdown.preference_contributions['explanation']}")

        if semantic_summary:
            parts.append(f"AI Interpretation: {semantic_summary}")

        return " ".join(parts)
