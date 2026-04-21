"""
Job management endpoints
"""

import json
import time
import asyncio
import aiofiles
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import JobStatus
from app.models.requests import JobRequest, ManualClip
from app.models.responses import JobResponse, JobListResponse, JobResults, ErrorResponse
from app.services.job_service import JobService, get_job_service
from app.workers.pipeline_worker import run_pipeline

logger = get_logger("jobs_api")

router = APIRouter()

# Allowed video extensions
ALLOWED_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB


@router.post(
    "",
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
            },
            "manual_mode": {
                "summary": "Manual timestamps",
                "description": "Provide exact timestamps - skips AI analysis",
                "value": {
                    "input_source": "https://youtube.com/watch?v=xxxxx",
                    "manual_clips": [
                        {"start": "00:30", "end": "01:45"},
                        {"start": "02:10", "end": "03:25"}
                    ]
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


@router.post(
    "/upload",
    response_model=JobResponse,
    status_code=201,
    summary="Upload video and create job",
    description="""Upload a video file directly and create a processing job.

Supports MP4, MKV, MOV, AVI, WebM formats up to 500MB.
This is the most reliable method - no YouTube download issues.""",
    responses={
        201: {"description": "Job created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid file"},
        413: {"model": ErrorResponse, "description": "File too large"},
    },
)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Video file to process"),
    num_clips: Optional[int] = Form(default=None, ge=1, le=20),
    min_duration: Optional[int] = Form(default=None, ge=15, le=120),
    max_duration: Optional[int] = Form(default=None, ge=30, le=180),
    add_subtitles: Optional[bool] = Form(default=None),
    vertical_mode: Optional[bool] = Form(default=None),
    video_quality: Optional[str] = Form(default=None),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    """
    Upload a video file and create a processing job.

    This endpoint accepts direct video file uploads, bypassing any YouTube
    download issues. It's the most reliable method for processing videos.

    Args:
        file: Video file (MP4, MKV, MOV, AVI, WebM)
        num_clips: Number of clips to extract (1-20)
        min_duration: Minimum clip duration in seconds
        max_duration: Maximum clip duration in seconds
        add_subtitles: Add subtitles to clips
        vertical_mode: Convert to vertical (9:16) format
        video_quality: Output quality setting

    Returns:
        JobResponse with job details
    """
    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file_ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check file size (read in chunks to avoid memory issues)
    file_size = 0
    chunk_size = 1024 * 1024  # 1MB chunks

    # Save file while checking size
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_filename = f"upload_{int(time.time())}_{file.filename.replace(' ', '_')}"
    file_path = settings.UPLOADS_DIR / safe_filename

    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            while chunk := await file.read(chunk_size):
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    # Clean up partial file
                    await out_file.close()
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
                    )
                await out_file.write(chunk)

        logger.info(f"Uploaded video saved: {file_path} ({file_size / (1024*1024):.1f}MB)")

        # Create job request with uploaded file path
        request = JobRequest(
            input_source=str(file_path),
            num_clips=num_clips,
            min_duration=min_duration,
            max_duration=max_duration,
            add_subtitles=add_subtitles,
            vertical_mode=vertical_mode,
            video_quality=video_quality,
        )

        # Create job in service
        job = job_service.create_job(request)

        # Schedule background processing
        background_tasks.add_task(run_pipeline, job.job_id, request)

        return job

    except HTTPException:
        raise
    except Exception as e:
        # Clean up on error
        file_path.unlink(missing_ok=True)
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post(
    "/upload/start",
    response_model=JobResponse,
    status_code=201,
    summary="Start upload job",
    description="""Create a job for file upload and return job_id immediately.

Use this to get a job_id first, then upload the file to /jobs/{job_id}/file.
This allows showing upload progress on the job status page.

For manual mode, provide manual_clips as JSON array: [{"start": "00:30", "end": "01:45"}]""",
)
async def start_upload_job(
    filename: str = Form(..., description="Original filename"),
    filesize: int = Form(..., description="File size in bytes"),
    num_clips: Optional[int] = Form(default=None, ge=1, le=20),
    min_duration: Optional[int] = Form(default=None, ge=15, le=120),
    max_duration: Optional[int] = Form(default=None, ge=30, le=180),
    add_subtitles: Optional[bool] = Form(default=None),
    vertical_mode: Optional[bool] = Form(default=None),
    video_quality: Optional[str] = Form(default=None),
    manual_clips: Optional[str] = Form(default=None, description="JSON array of manual timestamps"),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    """Create a job for upload - returns immediately so client can redirect to status page."""

    # Validate file extension
    file_ext = Path(filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file_ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    if filesize > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # Parse manual_clips JSON if provided
    parsed_manual_clips = None
    if manual_clips:
        try:
            clips_data = json.loads(manual_clips)
            parsed_manual_clips = [ManualClip(**clip) for clip in clips_data]
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid manual_clips format: {str(e)}"
            )

    # Create placeholder path (will be set when file is uploaded)
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_filename = f"upload_{int(time.time())}_{filename.replace(' ', '_')}"
    file_path = settings.UPLOADS_DIR / safe_filename

    # Create job request
    request = JobRequest(
        input_source=str(file_path),
        num_clips=num_clips,
        min_duration=min_duration,
        max_duration=max_duration,
        add_subtitles=add_subtitles,
        vertical_mode=vertical_mode,
        video_quality=video_quality,
        manual_clips=parsed_manual_clips,
    )

    # Create job
    job = job_service.create_job(request)

    # Store manual clips for later use in upload_job_file
    if parsed_manual_clips:
        manual_clips_file = settings.TEMP_DIR / f"{job.job_id}_manual_clips.json"
        settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        with open(manual_clips_file, "w") as f:
            json.dump([{"start": mc.start, "end": mc.end} for mc in parsed_manual_clips], f)

    # Update to uploading_video status
    job_service.update_status(
        job.job_id,
        JobStatus.UPLOADING_VIDEO,
        progress=0.0,
        current_step="Waiting for upload..."
    )

    is_manual = parsed_manual_clips is not None
    logger.info(f"Created upload job {job.job_id} for file: {filename} ({filesize} bytes), manual_mode={is_manual}")

    return job_service.get_job(job.job_id)


@router.post(
    "/{job_id}/file",
    response_model=JobResponse,
    summary="Upload file to job",
    description="Upload the video file for a job created with /upload/start",
)
async def upload_job_file(
    job_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Video file"),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    """Upload file to an existing job and start processing."""

    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status != JobStatus.UPLOADING_VIDEO:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not waiting for upload (status: {job.status.value})"
        )

    # Get the file path from job's input_source
    file_path = Path(job.input_source)

    try:
        # Read file size for progress calculation
        file.file.seek(0, 2)  # Seek to end
        total_size = file.file.tell()
        file.file.seek(0)  # Seek back to start

        if total_size == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        chunk_size = 1024 * 1024  # 1MB chunks
        bytes_written = 0

        async with aiofiles.open(file_path, 'wb') as out_file:
            while chunk := await file.read(chunk_size):
                await out_file.write(chunk)
                bytes_written += len(chunk)

                # Update progress
                progress = bytes_written / total_size
                job_service.update_step_progress(
                    job_id,
                    progress,
                    f"Uploading... {bytes_written // (1024*1024)}MB / {total_size // (1024*1024)}MB"
                )

        logger.info(f"Upload complete for job {job_id}: {file_path} ({bytes_written} bytes)")

        # Load manual clips if they exist
        manual_clips_list = None
        manual_clips_file = settings.TEMP_DIR / f"{job_id}_manual_clips.json"
        if manual_clips_file.exists():
            try:
                with open(manual_clips_file, "r") as f:
                    clips_data = json.load(f)
                manual_clips_list = [ManualClip(**clip) for clip in clips_data]
                logger.info(f"Loaded {len(manual_clips_list)} manual clips for job {job_id}")
            except Exception as e:
                logger.warning(f"Could not load manual clips: {e}")

        # Create request from job's stored values
        request = JobRequest(
            input_source=str(file_path),
            add_subtitles=job.add_subtitles,
            manual_clips=manual_clips_list,
        )

        # Start pipeline processing
        background_tasks.add_task(run_pipeline, job_id, request)

        return job_service.get_job(job_id)

    except HTTPException:
        raise
    except Exception as e:
        file_path.unlink(missing_ok=True)
        job_service.set_error(job_id, f"Upload failed: {str(e)}")
        logger.error(f"Upload failed for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get(
    "",
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
    "/{job_id}/stream",
    summary="Stream job progress (SSE)",
    description="Real-time job progress updates via Server-Sent Events",
)
async def stream_job_progress(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
):
    """
    Stream real-time job progress updates via Server-Sent Events (SSE).

    This endpoint provides live progress updates including:
    - Current step and overall progress
    - Step-level progress (e.g., "Cutting clip 3/5")
    - Elapsed and remaining time estimates
    - Step completion notifications

    Connect using EventSource in JavaScript:
    ```javascript
    const eventSource = new EventSource('/api/v1/jobs/{job_id}/stream');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log(data);
    };
    ```
    """
    async def event_generator():
        """Generate SSE events for job progress."""
        # Check if job exists
        job = job_service.get_job(job_id)
        if not job:
            yield {
                "event": "error",
                "data": json.dumps({"error": f"Job {job_id} not found"})
            }
            return

        step_order = ["uploading_video", "downloading", "transcribing", "analyzing", "selecting", "cutting", "subtitling", "uploading"]

        while True:
            job = job_service.get_job(job_id)
            if not job:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Job not found"})
                }
                break

            # Calculate elapsed time for current step
            elapsed = 0
            if job.step_started_at:
                elapsed = int((datetime.now() - job.step_started_at).total_seconds())

            # Calculate remaining time based on actual progress (not hardcoded estimates)
            step_remaining = 0
            if job.step_progress and job.step_progress > 0.05 and elapsed > 2:
                # Estimate remaining based on current progress rate
                estimated_total = elapsed / job.step_progress
                step_remaining = max(0, int(estimated_total - elapsed))

            # We don't estimate future steps anymore - just show current step timing
            total_remaining = step_remaining

            # Build event data
            event_data = {
                "job_id": job.job_id,
                "status": job.status.value,
                "progress": job.progress,
                "current_step": job.current_step,
                "step_progress": job.step_progress,
                "step_message": job.step_message,
                "elapsed": elapsed,
                "step_remaining": step_remaining,
                "total_remaining": total_remaining,
                "step_durations": job.step_durations,
                "add_subtitles": job.add_subtitles,
                "is_manual_mode": job.is_manual_mode,
            }

            # Add results summary if completed
            if job.status.value == "completed" and job.results:
                event_data["clips_count"] = len(job.results.clips)
                event_data["total_duration"] = job.results.total_duration

            # Add error if failed
            if job.status.value == "failed":
                event_data["error"] = job.error

            yield {
                "event": "progress",
                "data": json.dumps(event_data)
            }

            # Stop streaming if job is in terminal state
            if job.status.value in ["completed", "failed", "cancelled"]:
                break

            # Wait before next update
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


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


@router.get(
    "/{job_id}/clips/{clip_number}/download",
    summary="Download clip",
    description="Download a specific clip file",
    responses={
        200: {"description": "Clip file", "content": {"video/mp4": {}}},
        404: {"model": ErrorResponse, "description": "Clip not found"},
    },
)
async def download_clip(
    job_id: str,
    clip_number: int,
    job_service: JobService = Depends(get_job_service),
) -> FileResponse:
    """
    Download a clip file by job ID and clip number.

    Args:
        job_id: Unique job identifier
        clip_number: Clip number (1-based)
        job_service: Job service dependency

    Returns:
        FileResponse with the clip video file

    Raises:
        HTTPException: If job not found, not completed, or clip doesn't exist
    """
    logger.info(f"Download request: job={job_id}, clip={clip_number}")

    job = job_service.get_job(job_id)

    if not job:
        logger.warning(f"Job not found: {job_id}")
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if not job.results or not job.results.clips:
        logger.warning(f"Job has no results: {job_id}")
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} has no results yet"
        )

    logger.info(f"Job has {len(job.results.clips)} clips")

    # Find the clip
    clip = next(
        (c for c in job.results.clips if c.clip_number == clip_number),
        None
    )

    if not clip:
        logger.warning(f"Clip {clip_number} not found. Available: {[c.clip_number for c in job.results.clips]}")
        raise HTTPException(
            status_code=404,
            detail=f"Clip {clip_number} not found in job {job_id}"
        )

    # Find the file
    clip_path = settings.OUTPUTS_DIR / clip.filename
    logger.info(f"Looking for file: {clip_path}")

    if not clip_path.exists():
        logger.warning(f"File not found: {clip_path}")
        raise HTTPException(
            status_code=404,
            detail=f"Clip file not found: {clip.filename}. It may have been deleted."
        )

    logger.info(f"Serving file: {clip_path}")

    return FileResponse(
        path=clip_path,
        filename=clip.filename,
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'attachment; filename="{clip.filename}"'
        }
    )
