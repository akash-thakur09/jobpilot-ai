from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class SemanticAnalysisResult(BaseModel):
    relevance_summary: str
    conceptually_similar_skills: List[str] = Field(default_factory=list)
    relevant_experience_highlights: List[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    provider: str
    model: str


class BaseAIProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Checks if the model provider daemon and configured model are reachable."""
        pass

    @abstractmethod
    async def analyze_semantic_match(
        self,
        job_title: str,
        job_description: str,
        candidate_summary: str,
        candidate_bullets: List[str],
    ) -> Optional[SemanticAnalysisResult]:
        """Provides optional semantic interpretation of fit and highlights."""
        pass
