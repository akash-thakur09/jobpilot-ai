import hashlib
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from backend.app.models.candidate import CandidateProfile
from backend.app.models.job import Job
from backend.app.models.matching import MatchScore
from backend.app.models.resume import ResumeVersion
from backend.app.models.enums import EligibilityStatus
from backend.app.resumes.schemas import (
    TailoredResumeContent,
    FactualValidationReport,
    KeywordCoverageReport,
    ResumeVersionRead,
)
from backend.app.resumes.fact_validator import ResumeFactValidator
from backend.app.resumes.keyword_coverage import KeywordCoverageValidator
from backend.app.resumes.tailoring_service import ResumeTailoringService
from backend.app.resumes.pdf_renderer import ResumePdfRenderer
from backend.app.resumes.pdf_verifier import ResumePdfVerifier
from backend.app.resumes.storage_service import ResumeStorageService
from backend.app.services.matching_service import MatchingService
from backend.app.core.logging import logger


class ResumeVersionService:
    @classmethod
    async def generate_tailored_resume(
        cls,
        session: AsyncSession,
        job_id: str,
        use_ai: bool = True,
        force_regenerate: bool = False,
    ) -> ResumeVersion:
        """
        Executes the full resume generation pipeline:
        Validation -> Context -> Tailoring -> Fact Check -> Coverage -> PDF Render -> Verification -> Storage -> DB Record
        """
        # 1. Fetch Candidate Profile with all relations
        cand_query = (
            select(CandidateProfile)
            .options(
                selectinload(CandidateProfile.skills),
                selectinload(CandidateProfile.experiences),
                selectinload(CandidateProfile.educations),
                selectinload(CandidateProfile.projects),
            )
            .limit(1)
        )
        cand_res = await session.execute(cand_query)
        candidate = cand_res.scalar_one_or_none()
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate profile does not exist. Please create and verify a profile first.",
            )

        # 2. Fetch Job with requirements
        job_res = await session.execute(
            select(Job).options(selectinload(Job.requirements)).where(Job.id == job_id)
        )
        job = job_res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID '{job_id}' not found.",
            )

        # 3. Retrieve or Execute Match Score Evaluation
        match_query = (
            select(MatchScore)
            .where(MatchScore.job_id == job.id, MatchScore.candidate_id == candidate.id, MatchScore.is_latest == True)
            .limit(1)
        )
        match_res = await session.execute(match_query)
        match_score = match_res.scalar_one_or_none()
        if not match_score:
            # Run matching evaluation automatically
            matching_service = MatchingService()
            match_score = await matching_service.evaluate_job(session=session, job_id=job.id, use_ai=False)

        # Hard constraint check: Disqualified jobs cannot receive resumes
        if not match_score.is_eligible or match_score.eligibility_status == EligibilityStatus.DISQUALIFIED.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Cannot generate resume for disqualified job: {match_score.explanation}",
            )

        # Check existing version if not forcing regeneration
        if not force_regenerate:
            existing_ver_res = await session.execute(
                select(ResumeVersion)
                .where(ResumeVersion.job_id == job.id, ResumeVersion.candidate_id == candidate.id)
                .order_by(ResumeVersion.version_number.desc())
                .limit(1)
            )
            existing_ver = existing_ver_res.scalar_one_or_none()
            if existing_ver and existing_ver.is_submission_ready:
                # Verify file still exists on disk
                if ResumeStorageService.verify_file_integrity(existing_ver.pdf_file_path, existing_ver.file_sha256):
                    return existing_ver

        # 4. Tailoring & Structuring
        tailored_content = ResumeTailoringService.build_deterministic_content(
            candidate=candidate, job=job, match_score=match_score
        )

        # 5. Factual Consistency Validation Gate
        fact_report = ResumeFactValidator.validate_content(candidate, tailored_content)
        if not fact_report.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "message": "Factual validation failed. Unsupported claims detected.",
                    "unsupported_claims": fact_report.unsupported_claims,
                },
            )

        # 6. Keyword Coverage Analysis
        coverage_report = KeywordCoverageValidator.evaluate_coverage(candidate, job)

        # 7. PDF Rendering (ReportLab)
        pdf_bytes = ResumePdfRenderer.render_to_bytes(tailored_content)

        # 8. Post-Render Verification (pypdf)
        is_ats_valid, extracted_text, diagnostics = ResumePdfVerifier.verify_pdf_bytes(
            pdf_bytes, tailored_content
        )

        # 9. Atomic Storage & SHA-256 Checksum
        file_path, file_sha256 = ResumeStorageService.save_resume_pdf(pdf_bytes)

        # 10. Compute Version Number
        count_query = select(func.count(ResumeVersion.id)).where(
            ResumeVersion.job_id == job.id, ResumeVersion.candidate_id == candidate.id
        )
        count_res = await session.execute(count_query)
        prior_versions_count = count_res.scalar_one()
        version_number = prior_versions_count + 1

        # 11. Immutable Candidate Profile Snapshot
        candidate_snapshot = {
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "location": candidate.location,
            "summary": candidate.summary,
            "years_of_experience": candidate.years_of_experience,
            "verified_skills": [s.skill_name for s in candidate.skills if s.is_verified],
        }

        job_fingerprint = hashlib.sha256(
            f"{job.title}:{job.company}:{job.description}".encode()
        ).hexdigest()

        # 12. Persist Immutable Database Record
        resume_version = ResumeVersion(
            candidate_id=candidate.id,
            job_id=job.id,
            match_score_id=match_score.id,
            version_number=version_number,
            structured_content=tailored_content.model_dump(),
            candidate_snapshot=candidate_snapshot,
            pdf_file_path=file_path,
            file_sha256=file_sha256,
            is_ats_valid=is_ats_valid,
            is_submission_ready=is_ats_valid and fact_report.is_valid,
            ats_extracted_text=extracted_text,
            ats_diagnostics=diagnostics,
            factual_validation_result=fact_report.model_dump(),
            keyword_coverage_result=coverage_report.model_dump(),
            generator_metadata={
                "pipeline": "ResumeTailoringService_v1",
                "renderer": "ReportLab",
                "verifier": "pypdf",
                "use_ai": use_ai,
            },
            job_fingerprint=job_fingerprint,
            tailoring_policy_version="1.0.0",
        )

        session.add(resume_version)
        await session.commit()
        await session.refresh(resume_version)
        return resume_version

    @classmethod
    async def get_version_by_id(
        cls, session: AsyncSession, version_id: str
    ) -> ResumeVersion:
        result = await session.execute(
            select(ResumeVersion).where(ResumeVersion.id == version_id)
        )
        version = result.scalar_one_or_none()
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume version '{version_id}' not found.",
            )
        return version

    @classmethod
    async def list_versions_for_job(
        cls, session: AsyncSession, job_id: str
    ) -> List[ResumeVersion]:
        result = await session.execute(
            select(ResumeVersion)
            .where(ResumeVersion.job_id == job_id)
            .order_by(ResumeVersion.version_number.desc())
        )
        return list(result.scalars().all())
