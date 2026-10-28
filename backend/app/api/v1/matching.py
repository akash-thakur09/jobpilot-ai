from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.matching import MatchScore
from backend.app.matching.schemas import MatchScoreRead
from backend.app.services.matching_service import MatchingService
from backend.app.providers.ollama import OllamaProvider

router = APIRouter(prefix="/matching", tags=["Job Matching & Scoring"])


@router.post("/evaluate/{job_id}", response_model=MatchScoreRead, status_code=status.HTTP_200_OK)
async def evaluate_job(
    job_id: str,
    use_ai: bool = Query(True, description="Whether to include optional Ollama semantic analysis"),
    session: AsyncSession = Depends(get_db),
):
    """Evaluates a job against the candidate profile and returns the persisted match score."""
    service = MatchingService()
    return await service.evaluate_job(session=session, job_id=job_id, use_ai=use_ai)


@router.post("/evaluate-all", status_code=status.HTTP_200_OK)
async def evaluate_all_jobs(
    use_ai: bool = Query(False, description="Whether to include optional Ollama semantic analysis for batch"),
    session: AsyncSession = Depends(get_db),
):
    """Batch-evaluates all discovered jobs against the active candidate profile."""
    service = MatchingService()
    return await service.evaluate_all_jobs(session=session, use_ai=use_ai)


@router.get("/results", response_model=List[MatchScoreRead])
async def list_match_results(
    is_eligible: Optional[bool] = None,
    min_score: Optional[float] = Query(None, ge=0.0, le=100.0),
    is_latest: bool = Query(True, description="Filter for only the latest evaluation per job"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """Lists match evaluations with score and eligibility filtering."""
    query = select(MatchScore)

    if is_latest:
        query = query.where(MatchScore.is_latest == True)

    if is_eligible is not None:
        query = query.where(MatchScore.is_eligible == is_eligible)

    if min_score is not None:
        query = query.where(MatchScore.overall_score >= min_score)

    query = query.order_by(MatchScore.overall_score.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/results/{job_id}", response_model=MatchScoreRead)
async def get_match_result_for_job(job_id: str, session: AsyncSession = Depends(get_db)):
    """Retrieves the latest match evaluation for a specific job."""
    query = (
        select(MatchScore)
        .where(MatchScore.job_id == job_id, MatchScore.is_latest == True)
        .order_by(MatchScore.created_at.desc())
        .limit(1)
    )
    result = await session.execute(query)
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No match evaluation found for job '{job_id}'. Please evaluate it first.",
        )
    return score


@router.post("/evaluate-ranking", status_code=status.HTTP_200_OK)
async def run_ranking_evaluation():
    """
    Runs the offline ranking evaluation suite against labeled benchmark fixtures.
    Returns Precision@K, Recall@K, NDCG@K, duplicate detection, and freshness accuracy.
    """
    from backend.app.evaluation.runner import OfflineRankingEvaluator
    return OfflineRankingEvaluator.run_evaluation()


@router.get("/health")
async def check_matching_health():
    """Checks the health of the deterministic matching engine and Ollama AI provider."""
    ollama = OllamaProvider()
    ai_online = await ollama.is_available()
    return {
        "status": "healthy",
        "engine": "Deterministic Matching Engine v1.1.0",
        "scoring_policy_version": "1.1.0",
        "ai_provider": ollama.provider_name,
        "ai_model": ollama.model_name,
        "ai_available": ai_online,
        "policy": {
            "hard_constraints_enforced": True,
            "disqualified_override_allowed": False,
        },
    }
