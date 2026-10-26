from typing import List, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.candidate import CandidateProfileCreate


class ResumeImportResult(BaseModel):
    original_filename: str
    file_size_bytes: int
    file_sha256: str
    page_count: int
    extracted_text_length: int
    extracted_text_preview: str
    draft_profile: CandidateProfileCreate
    requires_confirmation: bool = True
    warnings: List[str] = Field(default_factory=list)


class ResumeImportConfirmRequest(BaseModel):
    file_sha256: str
    confirmed_profile: CandidateProfileCreate
