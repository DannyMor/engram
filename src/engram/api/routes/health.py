"""Health check endpoint."""

from fastapi import APIRouter

from engram.api.models import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(version="0.1.0")
