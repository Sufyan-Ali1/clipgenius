"""
Job Service - Single Responsibility: Job state management

Handles creating, updating, and querying job states.
Does NOT handle actual processing - that's the worker's job.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional
from threading import Lock

from app.models.enums import JobStatus
from app.models.requests import JobRequest
from app.models.responses import JobResponse, JobResults
from app.core.logging import get_logger

logger = get_logger("job_service")


class JobService:
    """
    Single Responsibility: Manage job state.

    - Create jobs
    - Update job status/progress
    - Query jobs
    - Delete jobs

    Does NOT: Execute processing, handle files, call LLMs
    """

    def __init__(self):
        self._jobs: Dict[str, JobResponse] = {}
        self._lock = Lock()

    def create_job(self, request: JobRequest) -> JobResponse:
        """
        Create a new job in PENDING state.

        Args:
            request: Job request with input source and options

        Returns:
            Created job response
        """
        job_id = str(uuid.uuid4())
        now = datetime.now()

        job = JobResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            progress=0.0,
            current_step="Pending",
            created_at=now,
            updated_at=now,
            input_source=request.input_source,
            results=None,
            error=None,
        )

        with self._lock:
            self._jobs[job_id] = job

        logger.info(f"Created job {job_id} for source: {request.input_source}")
        return job

    def get_job(self, job_id: str) -> Optional[JobResponse]:
        """
        Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job response or None if not found
        """
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 100, offset: int = 0) -> List[JobResponse]:
        """
        List all jobs with pagination.

        Args:
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip

        Returns:
            List of job responses
        """
        with self._lock:
            jobs = list(self._jobs.values())
            # Sort by creation time, newest first
            jobs.sort(key=lambda j: j.created_at, reverse=True)
            return jobs[offset : offset + limit]

    def get_total_jobs(self) -> int:
        """Get total number of jobs."""
        with self._lock:
            return len(self._jobs)

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: Optional[float] = None,
        current_step: Optional[str] = None,
    ) -> Optional[JobResponse]:
        """
        Update job status and progress.

        Args:
            job_id: Job identifier
            status: New status
            progress: Progress value (0.0-1.0)
            current_step: Description of current step

        Returns:
            Updated job response or None if not found
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            # Create updated job (Pydantic models are immutable by default)
            update_data = {"status": status, "updated_at": datetime.now()}

            if progress is not None:
                update_data["progress"] = progress
            if current_step is not None:
                update_data["current_step"] = current_step

            updated_job = job.model_copy(update=update_data)
            self._jobs[job_id] = updated_job

            logger.info(f"Job {job_id}: {status.value} - {current_step or ''}")
            return updated_job

    def set_results(
        self, job_id: str, results: JobResults
    ) -> Optional[JobResponse]:
        """
        Set job results and mark as completed.

        Args:
            job_id: Job identifier
            results: Job results

        Returns:
            Updated job response or None if not found
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            updated_job = job.model_copy(
                update={
                    "status": JobStatus.COMPLETED,
                    "progress": 1.0,
                    "current_step": "Completed",
                    "results": results,
                    "updated_at": datetime.now(),
                }
            )
            self._jobs[job_id] = updated_job

            logger.info(f"Job {job_id} completed with {len(results.clips)} clips")
            return updated_job

    def set_error(self, job_id: str, error: str) -> Optional[JobResponse]:
        """
        Set job error and mark as failed.

        Args:
            job_id: Job identifier
            error: Error message

        Returns:
            Updated job response or None if not found
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            updated_job = job.model_copy(
                update={
                    "status": JobStatus.FAILED,
                    "current_step": "Failed",
                    "error": error,
                    "updated_at": datetime.now(),
                }
            )
            self._jobs[job_id] = updated_job

            logger.error(f"Job {job_id} failed: {error}")
            return updated_job

    def cancel_job(self, job_id: str) -> Optional[JobResponse]:
        """
        Cancel a job if it's not in a terminal state.

        Args:
            job_id: Job identifier

        Returns:
            Updated job response or None if not found/already terminal
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            if job.status.is_terminal:
                logger.warning(f"Cannot cancel job {job_id}: already {job.status.value}")
                return None

            updated_job = job.model_copy(
                update={
                    "status": JobStatus.CANCELLED,
                    "current_step": "Cancelled",
                    "updated_at": datetime.now(),
                }
            )
            self._jobs[job_id] = updated_job

            logger.info(f"Job {job_id} cancelled")
            return updated_job

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job.

        Args:
            job_id: Job identifier

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                logger.info(f"Job {job_id} deleted")
                return True
            return False


# Singleton instance
_job_service: Optional[JobService] = None


def get_job_service() -> JobService:
    """Get the singleton JobService instance."""
    global _job_service
    if _job_service is None:
        _job_service = JobService()
    return _job_service
