"""
Pipeline Worker - Background task execution for video processing

Orchestrates the SRP services to process videos.
"""

from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import JobStatus
from app.models.requests import JobRequest
from app.models.responses import JobResults, ClipInfo
from app.services.job_service import get_job_service
from app.services.transcription_service import TranscriptionService
from app.services.analysis_service import AnalysisService
from app.services.selection_service import SelectionService
from app.services.video_service import VideoService
from app.services.subtitle_service import SubtitleService
from app.services.download_service import DownloadService
from app.services.storage_service import StorageService

logger = get_logger("pipeline_worker")


async def run_pipeline(job_id: str, request: JobRequest) -> None:
    """
    Execute the complete video processing pipeline.

    This is the main background task that orchestrates all services.

    Args:
        job_id: Unique job identifier
        request: Job request with configuration
    """
    job_service = get_job_service()
    downloaded_video: Optional[Path] = None

    try:
        # Get values from request or fall back to settings
        num_clips = request.num_clips if request.num_clips is not None else settings.NUM_CLIPS
        min_duration = request.min_duration if request.min_duration is not None else settings.MIN_CLIP_DURATION
        max_duration = request.max_duration if request.max_duration is not None else settings.MAX_CLIP_DURATION
        add_subtitles = request.add_subtitles if request.add_subtitles is not None else settings.ADD_SUBTITLES
        vertical_mode = request.vertical_mode if request.vertical_mode is not None else settings.VERTICAL_MODE
        upload_to_drive = request.upload_to_drive if request.upload_to_drive is not None else settings.GOOGLE_DRIVE_ENABLED

        # Initialize services
        download_service = DownloadService(quality=request.video_quality)
        transcription_service = TranscriptionService()
        analysis_service = AnalysisService(
            provider=request.provider,
            model=request.model,
        )
        selection_service = SelectionService(
            num_clips=num_clips,
            min_duration=min_duration,
            max_duration=max_duration,
        )
        video_service = VideoService(vertical_mode=vertical_mode)
        subtitle_service = SubtitleService()
        storage_service = StorageService()

        # Determine input path
        input_source = request.input_source

        # =====================================================================
        # STEP 1: Download (if YouTube URL)
        # =====================================================================
        if download_service.is_youtube_url(input_source):
            job_service.update_status(
                job_id,
                JobStatus.DOWNLOADING,
                progress=0.05,
                current_step="Downloading from YouTube...",
            )

            video_path = await download_service.download(input_source)
            downloaded_video = video_path
        else:
            video_path = Path(input_source)

        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        video_stem = video_path.stem

        # Setup temp paths
        temp_dir = settings.TEMP_DIR
        temp_dir.mkdir(parents=True, exist_ok=True)
        transcription_path = temp_dir / f"{video_stem}_transcription.json"
        analysis_path = temp_dir / f"{video_stem}_analysis.json"
        clips_path = temp_dir / f"{video_stem}_clips.json"

        # =====================================================================
        # STEP 2: Transcription
        # =====================================================================
        job_service.update_status(
            job_id,
            JobStatus.TRANSCRIBING,
            progress=0.15,
            current_step="Transcribing audio with Whisper...",
        )

        transcription = await transcription_service.transcribe(
            video_path,
            output_path=transcription_path,
        )

        # =====================================================================
        # STEP 3: Analysis
        # =====================================================================
        job_service.update_status(
            job_id,
            JobStatus.ANALYZING,
            progress=0.35,
            current_step="Analyzing content with LLM...",
        )

        suggestions = await analysis_service.analyze(
            transcription,
            output_path=analysis_path,
        )

        if not suggestions:
            raise ValueError("LLM returned no clip suggestions")

        # =====================================================================
        # STEP 4: Selection
        # =====================================================================
        job_service.update_status(
            job_id,
            JobStatus.SELECTING,
            progress=0.45,
            current_step="Selecting best clips...",
        )

        final_clips = await selection_service.select_clips(
            suggestions,
            transcription,
            output_path=clips_path,
        )

        if not final_clips:
            raise ValueError("No clips met selection criteria")

        # =====================================================================
        # STEP 5: Video Cutting
        # =====================================================================
        job_service.update_status(
            job_id,
            JobStatus.CUTTING,
            progress=0.55,
            current_step=f"Cutting {len(final_clips)} clips...",
        )

        output_paths = await video_service.cut_clips(video_path, final_clips)

        # =====================================================================
        # STEP 6: Subtitles (Optional)
        # =====================================================================
        if add_subtitles:
            job_service.update_status(
                job_id,
                JobStatus.SUBTITLING,
                progress=0.70,
                current_step="Adding subtitles...",
            )

            srt_paths = await subtitle_service.generate_subtitles(
                transcription,
                final_clips,
                temp_dir,
            )

            # Burn subtitles into clips
            final_output_paths = []
            for clip, clip_path, srt_path in zip(final_clips, output_paths, srt_paths):
                if srt_path.exists():
                    try:
                        subtitled_path = await video_service.add_subtitles(
                            clip_path, srt_path
                        )
                        # Replace original with subtitled version
                        clip_path.unlink()
                        subtitled_path.rename(clip_path)
                        final_output_paths.append(clip_path)
                    except Exception as e:
                        logger.warning(f"Could not add subtitles: {e}")
                        final_output_paths.append(clip_path)
                else:
                    final_output_paths.append(clip_path)

            output_paths = final_output_paths

        # =====================================================================
        # STEP 7: Upload to Drive (Optional)
        # =====================================================================
        drive_result = None
        if upload_to_drive and storage_service.is_drive_available():
            job_service.update_status(
                job_id,
                JobStatus.UPLOADING,
                progress=0.85,
                current_step="Uploading to Google Drive...",
            )

            try:
                drive_result = await storage_service.upload_to_drive(
                    output_paths, video_stem
                )

                # Delete local clips after successful upload
                if drive_result and settings.DELETE_CLIPS_AFTER_UPLOAD:
                    for clip_path in output_paths:
                        try:
                            if clip_path.exists():
                                clip_path.unlink()
                                logger.info(f"Deleted local clip: {clip_path.name}")
                        except Exception as del_err:
                            logger.warning(f"Could not delete clip {clip_path}: {del_err}")

            except Exception as e:
                logger.warning(f"Drive upload failed: {e}")

        # =====================================================================
        # Build Results
        # =====================================================================
        clips_info = []
        for clip, path in zip(final_clips, output_paths):
            clip_info = ClipInfo(
                clip_number=clip["clip_number"],
                filename=path.name,
                start_seconds=clip["start_seconds"],
                end_seconds=clip["end_seconds"],
                duration=clip["duration"],
                hook=clip.get("hook"),
                score=clip.get("score"),
                drive_link=None,
            )
            clips_info.append(clip_info)

        total_duration = sum(c.duration for c in clips_info)

        results = JobResults(
            clips=clips_info,
            output_directory=str(settings.OUTPUTS_DIR),
            drive_folder_link=drive_result.get("folder_link") if drive_result else None,
            total_duration=total_duration,
        )

        # Mark job as completed
        job_service.set_results(job_id, results)

        # =====================================================================
        # Cleanup
        # =====================================================================
        if downloaded_video and settings.DELETE_DOWNLOADED_VIDEO:
            await download_service.delete_video(downloaded_video)

        if settings.CLEANUP_TEMP:
            await storage_service.cleanup_temp()

        logger.info(f"Pipeline complete for job {job_id}: {len(clips_info)} clips")

    except Exception as e:
        logger.error(f"Pipeline failed for job {job_id}: {e}")
        job_service.set_error(job_id, str(e))

        # Cleanup on failure
        if downloaded_video and settings.DELETE_DOWNLOADED_VIDEO:
            try:
                download_service = DownloadService()
                await download_service.delete_video(downloaded_video)
            except Exception:
                pass
