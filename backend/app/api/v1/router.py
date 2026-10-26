from fastapi import APIRouter
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.profile import router as profile_router
from backend.app.api.v1.jobs import router as jobs_router
from backend.app.api.v1.matching import router as matching_router
from backend.app.api.v1.resumes import router as resumes_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(profile_router)
api_v1_router.include_router(jobs_router)
api_v1_router.include_router(matching_router)
api_v1_router.include_router(resumes_router)
