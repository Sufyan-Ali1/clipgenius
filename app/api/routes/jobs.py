"""
Job management endpoints
"""

from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query

from app.models.requests import JobRequest
from app.models.responses import JobResponse, JobListResponse, JobResults, ErrorResponse
from app.services.job_service import JobService, get_job_service
from app.workers.pipeline_worker import run_pipeline

router = APIRouter()


@router.post(
    "/",
    response_model=JobResponse,
    status_code=201,
    summary="Create processing job",
    description="""Create a new video processing job.

Only `input_source` is required. All other settings come from .env file.

Optional overrides: num_clips, min_duration, max_duration, add_subtitles,
vertical_mode, upload_to_drive, provider, model, video_quality""",
    responses={
        201: {"description": "Job created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
    },
)
async def create_job(
    background_tasks: BackgroundTasks,
    job_service: JobService = Depends(get_job_service),
    request: JobRequest = Body(
        openapi_examples={
            "youtube_url": {
                "summary": "YouTube URL (simple)",
                "description": "Just provide a YouTube URL - all settings from .env",
                "value": {
                    "input_source": "https://youtube.com/watch?v=xxxxx"
                }
            },
            "with_options": {
                "summary": "With custom options",
                "description": "Override specific settings",
                "value": {
                    "input_source": "https://youtube.com/watch?v=xxxxx",
                    "num_clips": 3,
                    "video_quality": "4k"
                }
            },
            "local_file": {
                "summary": "Local file",
                "description": "Process a local video file",
                "value": {
                    "input_source": "C:/Videos/my_video.mp4"
                }
            }
        }
    ),
) -> JobResponse:
    """
    Create a new video processing job.

    The job will be processed in the background. Use GET /jobs/{job_id}
    to check progress and GET /jobs/{job_id}/results to get results.
    """
    # Create job in service
    job = job_service.create_job(request)

    # Schedule background processing
    background_tasks.add_task(run_pipeline, job.job_id, request)

    return job


@router.get(
    "/",
    response_model=JobListResponse,
    summary="List all jobs",
    description="Get a list of all processing jobs",
)
async def list_jobs(
    limit: int = Query(default=100, ge=1, le=1000, description="Max jobs to return"),
    offset: int = Query(default=0, ge=0, description="Number of jobs to skip"),
    job_service: JobService = Depends(get_job_service),
) -> JobListResponse:
    """
    List all jobs with pagination.

    Jobs are sorted by creation time (newest first).

    Args:
        limit: Maximum number of jobs to return
        offset: Number of jobs to skip
        job_service: Job service dependency

    Returns:
        List of jobs with total count
    """
    jobs = job_service.list_jobs(limit=limit, offset=offset)
    total = job_service.get_total_jobs()

    return JobListResponse(jobs=jobs, total=total)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job status",
    description="Get the status of a specific job",
    responses={
        200: {"description": "Job found"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
async def get_job(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    """
    Get job status by ID.

    Args:
        job_id: Unique job identifier
        job_service: Job service dependency

    Returns:
        Job status and details

    Raises:
        HTTPException: If job not found
    """
    job = job_service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return job


@router.get(
    "/{job_id}/results",
    response_model=JobResults,
    summary="Get job results",
    description="Get the results of a completed job",
    responses={
        200: {"description": "Results found"},
        404: {"model": ErrorResponse, "description": "Job not found"},
        400: {"model": ErrorResponse, "description": "Job not completed"},
    },
)
async def get_job_results(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
) -> JobResults:
    """
    Get results for a completed job.

    Args:
        job_id: Unique job identifier
        job_service: Job service dependency

    Returns:
        Job results with clip information

    Raises:
        HTTPException: If job not found or not completed
    """
    job = job_service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if not job.status.is_terminal:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is still processing ({job.status.value})"
        )

    if job.results is None:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} has no results (status: {job.status.value})"
        )

    return job.results


@router.delete(
    "/{job_id}",
    response_model=JobResponse,
    summary="Cancel job",
    description="Cancel a running job",
    responses={
        200: {"description": "Job cancelled"},
        404: {"model": ErrorResponse, "description": "Job not found"},
        400: {"model": ErrorResponse, "description": "Job cannot be cancelled"},
    },
)
async def cancel_job(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    """
    Cancel a job if it's not in a terminal state.

    Args:
        job_id: Unique job identifier
        job_service: Job service dependency

    Returns:
        Cancelled job

    Raises:
        HTTPException: If job not found or already completed
    """
    job = job_service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status.is_terminal:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} cannot be cancelled (status: {job.status.value})"
        )

    cancelled_job = job_service.cancel_job(job_id)

    if not cancelled_job:
        raise HTTPException(status_code=400, detail=f"Failed to cancel job {job_id}")

    return cancelled_job
