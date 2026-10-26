from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from backend.app.db.session import check_db_health
from backend.app.core.config import settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", status_code=status.HTTP_200_OK)
async def health_check():
    """Basic service health check."""
    return {
        "status": "healthy",
        "service": "JobPilot AI Backend",
        "environment": settings.ENVIRONMENT,
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check():
    """Readiness check including database status."""
    db_ok = await check_db_health()
    overall_status = "ready" if db_ok else "degraded"

    content = {
        "status": overall_status,
        "database": "connected" if db_ok else "unreachable",
        "environment": settings.ENVIRONMENT,
        "ai_provider": settings.DEFAULT_AI_PROVIDER,
        "ai_model": settings.OLLAMA_MODEL,
    }

    if not db_ok:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=content)

    return content
