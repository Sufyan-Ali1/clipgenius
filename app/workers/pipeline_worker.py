"""
Pipeline Worker - Background task execution for video processing

Orchestrates the SRP services to process videos.
"""

import asyncio
from pathlib import Path
from typing import Callable, List, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import JobStatus
from app.models.requests import JobRequest, ManualClip
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


def parse_timestamp(ts: str) -> float:
    """Parse MM:SS or HH:MM:SS timestamp to seconds."""
    parts = ts.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    else:
        raise ValueError(f"Invalid timestamp format: {ts}")


def convert_manual_clips(manual_clips: List[ManualClip]) -> List[dict]:
    """
    Convert user-provided timestamps to clip format for video cutting.

    Args:
        manual_clips: List of ManualClip with start/end timestamps

    Returns:
        List of clip dictionaries compatible with video_service
    """
    clips = []
    for i, mc in enumerate(manual_clips, 1):
        start_seconds = parse_timestamp(mc.start)
        end_seconds = parse_timestamp(mc.end)

        clips.append({
            "clip_number": i,
            "start_seconds": start_seconds,
            "end_seconds": end_seconds,
            "duration": end_seconds - start_seconds,
            "filename": f"clip_{i:03d}.mp4",
            "hook": f"Manual clip {i}",
            "score": 10,  # Manual clips are always "perfect"
        })
    return clips


def create_progress_callback(job_id: str) -> Callable[[float, str], None]:
    """
    Create a progress callback for SSE streaming.

    Args:
        job_id: Job identifier

    Returns:
        Callback function that updates step progress
    """
    job_service = get_job_service()

    def callback(progress: float, message: str) -> None:
        job_service.update_step_progress(job_id, progress, message)

    return callback


async def enrich_manual_clips_parallel(
    final_clips: List[dict],
    output_paths: List[Path],
    temp_dir: Path,
    transcription_service: TranscriptionService,
    analysis_service: AnalysisService,
    subtitle_service: SubtitleService,
    write_srt: bool,
) -> List[Optional[Path]]:
    """
    For each cut clip: transcribe it, ask the LLM for hook+hashtags, and
    optionally write a per-clip SRT. Runs all clips concurrently.

    Mutates each entry in `final_clips` in place to add `hook` and `hashtags`.
    Returns a list (clip-aligned) of SRT paths, or None when SRT not written
    or generation failed.
    """
    async def _process(index: int, clip: dict, clip_path: Path) -> Optional[Path]:
        clip_num = clip.get("clip_number", index + 1)
        try:
            transcript = await transcription_service.transcribe(
                clip_path, output_path=None
            )
        except Exception as e:
            logger.warning(f"Clip {clip_num}: transcription failed: {e}")
            clip["hashtags"] = []
            return None

        text = (transcript.get("text") or "").strip()

        try:
            meta = await analysis_service.generate_clip_metadata(text)
            if meta.get("hook"):
                clip["hook"] = meta["hook"]
            clip["hashtags"] = meta.get("hashtags") or []
        except Exception as e:
            logger.warning(f"Clip {clip_num}: metadata LLM failed: {e}")
            clip.setdefault("hashtags", [])

        if not write_srt:
            return None

        srt_path = temp_dir / f"clip_{clip_num:03d}.srt"
        try:
            await subtitle_service.generate_single_srt(
                transcript, srt_path, start_offset=0.0
            )
            clip["srt_path"] = str(srt_path)
            return srt_path
        except Exception as e:
            logger.warning(f"Clip {clip_num}: SRT write failed: {e}")
            return None

    tasks = [
        _process(i, clip, path)
        for i, (clip, path) in enumerate(zip(final_clips, output_paths))
    ]
    return await asyncio.gather(*tasks)


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

        is_manual_mode = request.manual_clips is not None and len(request.manual_clips) > 0

        # =====================================================================
        # STEP 2: Full-video Transcription (AUTO MODE ONLY)
        # =====================================================================
        transcription = None
        if not is_manual_mode:
            job_service.update_status(
                job_id,
                JobStatus.TRANSCRIBING,
                progress=0.15,
                current_step="Transcribing audio with Whisper...",
            )

            progress_callback = create_progress_callback(job_id)
            transcription = await transcription_service.transcribe(
                video_path,
                output_path=transcription_path,
                progress_callback=progress_callback,
            )

        # =====================================================================
        # STEP 3 & 4: Analysis and Selection (SKIP in manual mode)
        # =====================================================================
        if is_manual_mode:
            # Manual mode: skip AI analysis and selection
            logger.info(f"Manual mode: skipping AI analysis, using {len(request.manual_clips)} user timestamps")
            final_clips = convert_manual_clips(request.manual_clips)
        else:
            # AI mode: analyze with LLM and select best clips
            job_service.update_status(
                job_id,
                JobStatus.ANALYZING,
                progress=0.35,
                current_step="Analyzing content with LLM...",
            )

            progress_callback = create_progress_callback(job_id)
            suggestions = await analysis_service.analyze(
                transcription,
                output_path=analysis_path,
                progress_callback=progress_callback,
            )

            if not suggestions:
                raise ValueError("LLM returned no clip suggestions")

            # Selection
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

        progress_callback = create_progress_callback(job_id)
        output_paths = await video_service.cut_clips(
            video_path,
            final_clips,
            progress_callback=progress_callback,
        )

        # =====================================================================
        # STEP 5b: Per-clip metadata (MANUAL MODE ONLY)
        # Transcribes each cut clip, asks LLM for hook+hashtags, and
        # writes per-clip SRT when subtitles are enabled.
        # =====================================================================
        clip_srt_paths: Optional[List[Optional[Path]]] = None
        if is_manual_mode:
            job_service.update_status(
                job_id,
                JobStatus.CLIP_METADATA,
                progress=0.65,
                current_step="Transcribing clips & generating titles...",
            )

            clip_srt_paths = await enrich_manual_clips_parallel(
                final_clips,
                output_paths,
                temp_dir,
                transcription_service,
                analysis_service,
                subtitle_service,
                write_srt=add_subtitles,
            )

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

            progress_callback = create_progress_callback(job_id)
            if is_manual_mode:
                # Per-clip SRTs already written in CLIP_METADATA step.
                srt_paths = [
                    p if p is not None else (temp_dir / f"clip_{i+1:03d}.srt")
                    for i, p in enumerate(clip_srt_paths or [])
                ]
            else:
                srt_paths = await subtitle_service.generate_subtitles(
                    transcription,
                    final_clips,
                    temp_dir,
                )

            # Burn subtitles into clips
            final_output_paths = []
            total_clips = len(output_paths)
            for i, (clip, clip_path, srt_path) in enumerate(zip(final_clips, output_paths, srt_paths)):
                progress_callback(i / total_clips, f"Adding subtitles to clip {i+1}/{total_clips}...")
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

            progress_callback(1.0, "Subtitles complete")
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
            logger.info(f"Building ClipInfo for clip {clip.get('clip_number')}")
            logger.info(f"  Hashtags from clip: {clip.get('hashtags', 'NOT FOUND')}")
            logger.info(f"  Description from clip: {clip.get('description', 'NOT FOUND')}")
            clip_info = ClipInfo(
                clip_number=clip["clip_number"],
                filename=path.name,
                start_seconds=clip["start_seconds"],
                end_seconds=clip["end_seconds"],
                duration=clip["duration"],
                hook=clip.get("hook"),
                score=clip.get("score"),
                hashtags=clip.get("hashtags"),
                description=clip.get("description"),
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
