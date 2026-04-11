"""
Health check endpoints
"""

from datetime import datetime
from fastapi import APIRouter

from app.models.responses import HealthResponse
from app.core.config import settings

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check if the API is running and healthy",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns service status, version, and timestamp.
    """
    return HealthResponse(
        status="healthy",
        version=settings.API_VERSION,
        timestamp=datetime.now(),
    )


@router.get(
    "/",
    response_model=dict,
    summary="Root endpoint",
    description="API information",
)
async def root() -> dict:
    """
    Root endpoint with API information.
    """
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "docs": "/docs",
        "health": "/health",
    }
