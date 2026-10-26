import hashlib
import io
import re
from pathlib import Path
from typing import List, Tuple
from fastapi import HTTPException, status
import pypdf
from pypdf.errors import PdfReadError

from backend.app.core.config import settings
from backend.app.schemas.candidate import (
    CandidateProfileCreate,
    CandidateSkillCreate,
    CandidateExperienceCreate,
    CandidateEducationCreate,
)
from backend.app.schemas.resume_import import ResumeImportResult

MAX_RESUME_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

COMMON_SKILLS_DICTIONARY = [
    "Python", "JavaScript", "TypeScript", "React", "Node.js", "FastAPI",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure", "SQL", "PostgreSQL",
    "MongoDB", "Redis", "Linux", "Git", "CI/CD", "Terraform", "Go", "Java",
    "C++", "Rust", "GraphQL", "REST", "HTML", "CSS", "Tailwind CSS",
]


class ResumeParserService:
    @classmethod
    def parse_pdf_bytes(
        cls, file_bytes: bytes, filename: str
    ) -> ResumeImportResult:
        """Validates and parses a PDF master resume into structured draft data."""
        # 1. Size validation
        if len(file_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes).",
            )
        if len(file_bytes) > MAX_RESUME_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {MAX_RESUME_SIZE_BYTES // (1024 * 1024)} MB.",
            )

        # 2. Extension validation
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file format. Only PDF files are supported.",
            )

        # 3. Compute SHA-256
        sha256 = hashlib.sha256(file_bytes).hexdigest()

        # 4. Save original master resume atomically to disk (never overwrite)
        settings.MASTER_RESUME_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        dest_path = settings.MASTER_RESUME_STORAGE_DIR / f"{sha256}.pdf"
        if not dest_path.exists():
            temp_path = settings.MASTER_RESUME_STORAGE_DIR / f"{sha256}.tmp"
            temp_path.write_bytes(file_bytes)
            temp_path.replace(dest_path)

        # 5. Extract text using PyPDF
        stream = io.BytesIO(file_bytes)
        try:
            reader = pypdf.PdfReader(stream)
            if reader.is_encrypted:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="PDF is encrypted or password-protected. Please provide an unencrypted PDF.",
                )

            extracted_text = ""
            for page in reader.pages:
                text = page.extract_text() or ""
                extracted_text += text + "\n"

        except PdfReadError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Malformed or corrupt PDF file: {str(exc)}",
            )
        except Exception as exc:
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unable to read PDF file: {str(exc)}",
            )

        cleaned_text = extracted_text.strip()
        if not cleaned_text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="PDF contains no readable text. Scanned images or OCR-only PDFs require selectable text.",
            )

        # 6. Extract structured draft fields from text
        draft_profile, warnings = cls._extract_draft_profile(cleaned_text)

        return ResumeImportResult(
            original_filename=filename,
            file_size_bytes=len(file_bytes),
            file_sha256=sha256,
            page_count=len(reader.pages),
            extracted_text_length=len(cleaned_text),
            extracted_text_preview=cleaned_text[:500] + ("..." if len(cleaned_text) > 500 else ""),
            draft_profile=draft_profile,
            requires_confirmation=True,
            warnings=warnings,
        )

    @classmethod
    def _extract_draft_profile(
        cls, text: str
    ) -> Tuple[CandidateProfileCreate, List[str]]:
        """Extracts candidate profile fields into a draft representation."""
        warnings: List[str] = []

        # Email extraction
        email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
        email = email_match.group(0) if email_match else "unknown@candidate.local"
        if not email_match:
            warnings.append("Could not reliably detect email address from resume.")

        # Phone extraction
        phone_match = re.search(
            r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text
        )
        phone = phone_match.group(0) if phone_match else None

        # Candidate name heuristics (usually first clean line)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        candidate_name = lines[0] if lines else "Imported Candidate"
        if len(candidate_name) > 80 or "@" in candidate_name or len(candidate_name) < 2:
            candidate_name = "Imported Candidate"
            warnings.append("Could not reliably detect full name from resume header.")

        # Skills detection via dictionary match
        detected_skills: List[CandidateSkillCreate] = []
        lower_text = text.lower()
        for skill in COMMON_SKILLS_DICTIONARY:
            # Match word boundary
            pattern = r"\b" + re.escape(skill.lower()) + r"\b"
            if re.search(pattern, lower_text):
                detected_skills.append(
                    CandidateSkillCreate(
                        skill_name=skill,
                        category="technical",
                        years_experience=1.0,
                        is_verified=False,  # Unverified draft
                        evidence=f"Extracted from master resume '{skill}'",
                    )
                )

        # Basic summary extraction (takes lines from the beginning before experience)
        summary = ""
        for line in lines[1:6]:
            if any(h in line.lower() for h in ["experience", "education", "skills"]):
                break
            summary += line + " "
        summary = summary.strip()
        if len(summary) < 10:
            summary = "Professional candidate summary imported from master resume."

        draft = CandidateProfileCreate(
            full_name=candidate_name,
            email=email,
            phone=phone,
            location="To be confirmed",
            work_authorization="To be confirmed",
            summary=summary,
            years_of_experience=0.0,
            target_titles=[],
            skills=detected_skills,
            experiences=[],
            educations=[],
            projects=[],
        )

        return draft, warnings
