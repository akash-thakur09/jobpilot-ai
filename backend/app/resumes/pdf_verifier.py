import io
from typing import Tuple, Dict, Any, List
import pypdf
from backend.app.resumes.schemas import TailoredResumeContent


class ResumePdfVerifier:
    """
    Validates rendered ATS PDF text readability, section presence,
    and text selection integrity using pypdf.
    """

    @classmethod
    def verify_pdf_bytes(
        cls, pdf_bytes: bytes, expected_content: TailoredResumeContent
    ) -> Tuple[bool, str, Dict[str, Any]]:
        diagnostics: Dict[str, Any] = {
            "file_size_bytes": len(pdf_bytes),
            "checks_passed": [],
            "checks_failed": [],
        }

        if len(pdf_bytes) == 0:
            diagnostics["checks_failed"].append("PDF is empty (0 bytes)")
            return False, "", diagnostics

        if len(pdf_bytes) > 5 * 1024 * 1024:
            diagnostics["checks_failed"].append("PDF exceeds 5 MB limit")
            return False, "", diagnostics

        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            diagnostics["page_count"] = len(reader.pages)

            full_text = ""
            for idx, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                full_text += page_text + "\n"

            cleaned_text = full_text.strip()
            diagnostics["extracted_char_count"] = len(cleaned_text)

            if not cleaned_text:
                diagnostics["checks_failed"].append("No readable text extracted from PDF")
                return False, "", diagnostics

            # Check 1: Candidate Full Name
            if expected_content.full_name.lower() in cleaned_text.lower():
                diagnostics["checks_passed"].append("Candidate name verified in extracted text")
            else:
                diagnostics["checks_failed"].append("Candidate name missing from extracted text")

            # Check 2: Email
            if expected_content.email.lower() in cleaned_text.lower():
                diagnostics["checks_passed"].append("Candidate email verified in extracted text")
            else:
                diagnostics["checks_failed"].append("Candidate email missing from extracted text")

            # Check 3: Essential Section Headings (checked for sections populated in content)
            essential_headings = [
                "PROFESSIONAL SUMMARY",
                "TECHNICAL SKILLS",
            ]
            if getattr(expected_content, "experiences", None):
                essential_headings.append("PROFESSIONAL EXPERIENCE")
            if getattr(expected_content, "educations", None):
                essential_headings.append("EDUCATION")
            if getattr(expected_content, "projects", None):
                essential_headings.append("KEY PROJECTS")
            for heading in essential_headings:
                if heading.lower() in cleaned_text.lower():
                    diagnostics["checks_passed"].append(f"Section '{heading}' verified")
                else:
                    diagnostics["checks_failed"].append(f"Section '{heading}' missing from extracted text")

            is_ats_valid = len(diagnostics["checks_failed"]) == 0
            return is_ats_valid, cleaned_text, diagnostics

        except Exception as exc:
            diagnostics["checks_failed"].append(f"Exception during PDF verification: {str(exc)}")
            return False, "", diagnostics
