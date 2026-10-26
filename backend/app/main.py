from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.api.v1.router import api_v1_router
from backend.app.db.base import Base
from backend.app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Initializing JobPilot AI Backend...")
    settings.setup_directories()

    # Create tables if using SQLite or test engine
    if "sqlite" in settings.DATABASE_URL:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLite storage initialized.")

    logger.info("JobPilot AI Backend startup complete.")
    yield
    logger.info("Shutting down JobPilot AI Backend...")
    await engine.dispose()
    logger.info("Engine disposed.")


def create_app() -> FastAPI:
    """Factory function for FastAPI application."""
    app = FastAPI(
        title="JobPilot AI",
        description="Local-first, privacy-focused personal AI job-hunting agent API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred.", "path": str(request.url.path)},
        )

    # Include Routers
    app.include_router(api_v1_router)

    # Root health redirect/check
    @app.get("/health", tags=["Root"], status_code=status.HTTP_200_OK)
    async def root_health():
        return {"status": "ok", "app": "JobPilot AI"}

    return app


app = create_app()
