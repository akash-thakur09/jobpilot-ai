import os
from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine repository root reliably: backend/app/core/config.py -> 4 levels up
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "development-secret-key-please-change-in-production"

    # Base Paths
    ROOT_DIR: Path = REPO_ROOT
    STORAGE_DIR: Path = REPO_ROOT / "storage"
    RESUME_STORAGE_DIR: Path = REPO_ROOT / "storage" / "resumes"
    SCREENSHOT_STORAGE_DIR: Path = REPO_ROOT / "storage" / "screenshots"

    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{REPO_ROOT.as_posix()}/storage/jobpilot.db"
    DATABASE_SYNC_URL: str = f"sqlite:///{REPO_ROOT.as_posix()}/storage/jobpilot.db"

    # AI Configuration
    DEFAULT_AI_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:latest"
    AI_REQUEST_TIMEOUT_SECONDS: int = 60
    AI_MAX_RETRIES: int = 3

    # Scheduler & Automation
    SCHEDULER_ENABLED: bool = False
    DISCOVERY_CRON: str = "0 */4 * * *"
    DISCOVERY_CONCURRENCY_LIMIT: int = 3
    REQUIRE_HUMAN_APPROVAL_BEFORE_SUBMISSION: bool = True
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT_MS: int = 30000

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    def setup_directories(self) -> None:
        """Ensure necessary storage directories exist on disk."""
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.RESUME_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.SCREENSHOT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.setup_directories()
