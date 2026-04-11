"""
FastAPI Application - Main entry point

Video Clips Extractor REST API
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.api import api_router

# Setup logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="""
Video Clips Extractor API

Automatically extract engaging 60-90 second clips from long videos
for TikTok and YouTube Shorts.

## Features

- **YouTube Download**: Download videos directly from YouTube URLs
- **Whisper Transcription**: AI-powered speech-to-text with timestamps
- **LLM Analysis**: Identify most engaging segments using AI
- **Smart Selection**: Automatically select best clips based on virality score
- **Video Cutting**: FFmpeg-powered precise video cutting
- **Vertical Mode**: Convert to 9:16 format with blur padding
- **Subtitles**: Auto-generate and burn subtitles into clips
- **Google Drive Upload**: Upload clips directly to Google Drive

## Usage

1. Create a job with `POST /api/v1/jobs`
2. Monitor progress with `GET /api/v1/jobs/{job_id}`
3. Get results with `GET /api/v1/jobs/{job_id}/results`
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix=settings.API_PREFIX)

# Also include health at root level
from app.api.routes.health import router as health_router
app.include_router(health_router)


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    settings.ensure_directories()
    print(f"\n{'='*60}")
    print(f"  {settings.API_TITLE} v{settings.API_VERSION}")
    print(f"  Running on http://{settings.HOST}:{settings.PORT}")
    print(f"  Docs: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"{'='*60}\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("\nShutting down Video Clips Extractor API...")
