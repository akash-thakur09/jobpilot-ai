from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import logger
from backend.app.models.feedback import JobFeedback
from backend.app.models.job import Job
from backend.app.models.candidate import CandidateProfile
from backend.app.models.enums import FeedbackType


class FeedbackService:
    """
    Manages explicit user feedback on job recommendations.
    Provides idempotent upsert, removal, and retrieval.
    """

    FEEDBACK_SCORE_MODIFIERS: Dict[str, float] = {
        FeedbackType.RELEVANT.value: 0.10,
        FeedbackType.NOT_RELEVANT.value: -0.25,
        FeedbackType.NOT_INTERESTED.value: -0.50,
        FeedbackType.ALREADY_APPLIED.value: -0.40,
        FeedbackType.DUPLICATE_LISTING.value: -0.30,
    }

    @classmethod
    async def record_feedback(
        cls,
        session: AsyncSession,
        candidate_id: str,
        job_id: str,
        feedback_type: str,
        reason: Optional[str] = None,
        structured_details: Optional[Dict[str, Any]] = None,
    ) -> JobFeedback:
        """
        Idempotent upsert of candidate feedback for a job.
        """
        valid_types = {ft.value for ft in FeedbackType}
        if feedback_type not in valid_types:
            raise ValueError(f"Invalid feedback_type '{feedback_type}'. Allowed: {sorted(list(valid_types))}")

        # Verify job and candidate exist
        job = await session.get(Job, job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")
        cand = await session.get(CandidateProfile, candidate_id)
        if not cand:
            raise ValueError(f"Candidate '{candidate_id}' not found.")

        stmt = select(JobFeedback).where(
            JobFeedback.candidate_id == candidate_id,
            JobFeedback.job_id == job_id,
        )
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.feedback_type = feedback_type
            existing.reason = reason
            existing.structured_details = structured_details or {}
            existing.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(existing)
            logger.info(f"Updated feedback on job {job_id} for candidate {candidate_id}: {feedback_type}")
            return existing

        feedback = JobFeedback(
            candidate_id=candidate_id,
            job_id=job_id,
            feedback_type=feedback_type,
            reason=reason,
            structured_details=structured_details or {},
        )
        session.add(feedback)
        await session.commit()
        await session.refresh(feedback)
        logger.info(f"Recorded new feedback on job {job_id} for candidate {candidate_id}: {feedback_type}")
        return feedback

    @classmethod
    async def get_feedback(
        cls, session: AsyncSession, candidate_id: str, job_id: str
    ) -> Optional[JobFeedback]:
        stmt = select(JobFeedback).where(
            JobFeedback.candidate_id == candidate_id,
            JobFeedback.job_id == job_id,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def delete_feedback(
        cls, session: AsyncSession, candidate_id: str, job_id: str
    ) -> bool:
        stmt = select(JobFeedback).where(
            JobFeedback.candidate_id == candidate_id,
            JobFeedback.job_id == job_id,
        )
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if not existing:
            return False

        await session.delete(existing)
        await session.commit()
        logger.info(f"Removed feedback on job {job_id} for candidate {candidate_id}")
        return True

    @classmethod
    async def get_candidate_feedbacks(
        cls, session: AsyncSession, candidate_id: str, limit: int = 100
    ) -> List[JobFeedback]:
        stmt = (
            select(JobFeedback)
            .where(JobFeedback.candidate_id == candidate_id)
            .order_by(JobFeedback.updated_at.desc())
            .limit(limit)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    def get_score_modifier(cls, feedback_type: Optional[str]) -> Tuple[float, Optional[str]]:
        """
        Calculate score contribution from feedback.
        Returns (delta, explanation_note).
        """
        if not feedback_type:
            return 0.0, None
        mod = cls.FEEDBACK_SCORE_MODIFIERS.get(feedback_type, 0.0)
        if mod > 0:
            return mod, f"User marked recommendation as {feedback_type} (+{int(mod*100)}%)"
        elif mod < 0:
            return mod, f"User marked recommendation as {feedback_type} ({int(mod*100)}%)"
        return 0.0, None
