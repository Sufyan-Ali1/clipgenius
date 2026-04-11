"""
API module - FastAPI routes
"""

from fastapi import APIRouter

from .routes import health, jobs, config

# Main API router
api_router = APIRouter()

# Include route modules
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(config.router, prefix="/config", tags=["Configuration"])

__all__ = ["api_router"]
