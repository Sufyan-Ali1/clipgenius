"""
Transcription Service - Single Responsibility: Audio to text conversion

Uses Groq Whisper API for fast, cloud-based speech-to-text.
Handles large files by chunking audio when needed.
"""

import json
import subprocess
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import asyncio

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("transcription_service")

# Groq file size limit (25MB)
GROQ_MAX_FILE_SIZE = 25 * 1024 * 1024


class TranscriptionService:
    """
    Single Responsibility: Convert audio/video to text with timestamps.

    Uses Groq Whisper API for fast, cloud-based transcription.
    """

    def __init__(self):
        self.model_name = settings.WHISPER_MODEL
        self.language = settings.WHISPER_LANGUAGE
        self.chunk_duration = settings.WHISPER_CHUNK_DURATION
        self.temp_dir = settings.TEMP_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _extract_audio(self, video_path: Path, output_format: str = "mp3") -> Path:
        """Extract audio from video file using FFmpeg."""
        audio_path = self.temp_dir / f"{video_path.stem}_audio.{output_format}"

        if audio_path.exists():
            logger.info(f"Using existing audio: {audio_path}")
            return audio_path

        logger.info(f"Extracting audio from {video_path.name}...")

        # Use mp3 for smaller file size (better for Groq API limit)
        if output_format == "mp3":
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vn",
                "-acodec", "libmp3lame",
                "-ar", "16000",
                "-ac", "1",
                "-b:a", "64k",  # Lower bitrate for smaller files
                "-y",
                str(audio_path)
            ]
        else:
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                "-y",
                str(audio_path)
            ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return audio_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg error: {e.stderr.decode()}")
        except FileNotFoundError:
            raise RuntimeError("FFmpeg not found. Please install FFmpeg.")

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds using FFprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path)
        ]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return float(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Could not get duration: {e}")
            return 0

    def _split_audio(self, audio_path: Path) -> List[Tuple[Path, float]]:
        """Split audio into chunks for Groq API limit."""
        file_size = audio_path.stat().st_size
        duration = self._get_audio_duration(audio_path)

        if file_size < GROQ_MAX_FILE_SIZE:
            logger.info(f"Audio file {file_size / 1024 / 1024:.1f}MB - no chunking needed")
            return [(audio_path, 0.0)]

        logger.info(f"Audio file {file_size / 1024 / 1024:.1f}MB exceeds 25MB limit - splitting into chunks")

        # Calculate chunk duration based on file size
        # Aim for ~20MB chunks to stay safely under 25MB
        target_chunk_size = 20 * 1024 * 1024
        bytes_per_second = file_size / duration if duration > 0 else 10000
        chunk_duration = min(self.chunk_duration, int(target_chunk_size / bytes_per_second))
        chunk_duration = max(60, chunk_duration)  # At least 1 minute

        logger.info(f"Splitting into {chunk_duration}s chunks...")

        chunks = []
        chunk_index = 0
        current_offset = 0.0

        while current_offset < duration:
            chunk_path = self.temp_dir / f"{audio_path.stem}_chunk_{chunk_index:03d}.mp3"

            cmd = [
                "ffmpeg",
                "-i", str(audio_path),
                "-ss", str(current_offset),
                "-t", str(chunk_duration),
                "-acodec", "libmp3lame",
                "-ar", "16000",
                "-ac", "1",
                "-b:a", "64k",
                "-y",
                str(chunk_path)
            ]

            try:
                subprocess.run(cmd, check=True, capture_output=True)
                if chunk_path.exists() and chunk_path.stat().st_size > 0:
                    chunks.append((chunk_path, current_offset))
                    logger.info(f"  Created chunk {chunk_index}: offset={current_offset:.1f}s")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Error creating chunk {chunk_index}: {e}")

            current_offset += chunk_duration
            chunk_index += 1

        logger.info(f"Split into {len(chunks)} chunks")
        return chunks

    def _transcribe_chunk_groq(self, audio_path: Path) -> dict:
        """Transcribe a single chunk using Groq API."""
        from groq import Groq

        client = Groq(api_key=settings.GROQ_API_KEY)

        logger.info(f"Transcribing {audio_path.name} via Groq API...")

        with open(audio_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                file=(audio_path.name, audio_file),
                model="whisper-large-v3",
                response_format="verbose_json",
                timestamp_granularities=["segment", "word"],
                language=self.language if self.language else None,
            )

        return response

    def _merge_transcriptions(self, chunk_results: List[Tuple[dict, float]]) -> dict:
        """Merge transcriptions from multiple chunks with adjusted timestamps."""
        merged = {
            "text": "",
            "language": None,
            "duration": 0,
            "segments": []
        }

        segment_id = 0
        texts = []

        for result, offset in chunk_results:
            # Get language from first chunk
            if merged["language"] is None:
                merged["language"] = getattr(result, "language", self.language)

            # Process segments
            segments = getattr(result, "segments", []) or []
            for seg in segments:
                seg_data = {
                    "id": segment_id,
                    "start": round((seg.get("start", 0) or 0) + offset, 2),
                    "end": round((seg.get("end", 0) or 0) + offset, 2),
                    "text": (seg.get("text", "") or "").strip(),
                }

                # Add word timestamps if available
                words = seg.get("words", [])
                if words:
                    seg_data["words"] = [
                        {
                            "word": w.get("word", ""),
                            "start": round((w.get("start", 0) or 0) + offset, 2),
                            "end": round((w.get("end", 0) or 0) + offset, 2)
                        }
                        for w in words
                    ]

                merged["segments"].append(seg_data)
                segment_id += 1

            # Collect text
            text = getattr(result, "text", "") or ""
            if text:
                texts.append(text.strip())

        merged["text"] = " ".join(texts)
        if merged["segments"]:
            merged["duration"] = merged["segments"][-1]["end"]

        return merged

    def _transcribe_groq_sync(self, video_path: Path, output_path: Optional[Path] = None) -> dict:
        """Synchronous Groq transcription with chunking support."""
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"File not found: {video_path}")

        # Extract audio as MP3 (smaller file size)
        audio_path = self._extract_audio(video_path, output_format="mp3")

        # Split if needed
        chunks = self._split_audio(audio_path)

        # Transcribe each chunk
        chunk_results = []
        for i, (chunk_path, offset) in enumerate(chunks):
            logger.info(f"Transcribing chunk {i + 1}/{len(chunks)}...")
            result = self._transcribe_chunk_groq(chunk_path)
            chunk_results.append((result, offset))

            # Clean up chunk files (but not the main audio)
            if chunk_path != audio_path:
                try:
                    chunk_path.unlink()
                except Exception:
                    pass

        # Merge results
        if len(chunk_results) == 1:
            result = chunk_results[0][0]
            transcription = {
                "text": getattr(result, "text", ""),
                "language": getattr(result, "language", self.language),
                "duration": 0,
                "segments": []
            }

            segments = getattr(result, "segments", []) or []
            for i, seg in enumerate(segments):
                seg_data = {
                    "id": i,
                    "start": round(seg.get("start", 0) or 0, 2),
                    "end": round(seg.get("end", 0) or 0, 2),
                    "text": (seg.get("text", "") or "").strip(),
                }
                words = seg.get("words", [])
                if words:
                    seg_data["words"] = [
                        {
                            "word": w.get("word", ""),
                            "start": round(w.get("start", 0) or 0, 2),
                            "end": round(w.get("end", 0) or 0, 2)
                        }
                        for w in words
                    ]
                transcription["segments"].append(seg_data)

            if transcription["segments"]:
                transcription["duration"] = transcription["segments"][-1]["end"]
        else:
            transcription = self._merge_transcriptions(chunk_results)

        # Save if output path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(transcription, f, indent=2, ensure_ascii=False)
            logger.info(f"Transcription saved: {output_path}")

        logger.info(f"Groq transcription complete. {len(transcription['segments'])} segments.")
        return transcription

    async def transcribe(
        self,
        video_path: Path,
        output_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> dict:
        """
        Transcribe video/audio to text with timestamps.

        Args:
            video_path: Path to video/audio file
            output_path: Optional path to save transcription JSON
            progress_callback: Optional callback(progress, message)

        Returns:
            Transcription dict with segments and word timestamps
        """
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not set. Please set your Groq API key in .env file.")

        if progress_callback:
            progress_callback(0.0, "Starting transcription (Groq Whisper)...")

        loop = asyncio.get_event_loop()

        if progress_callback:
            progress_callback(0.1, "Extracting and processing audio...")

        transcription = await loop.run_in_executor(
            None, self._transcribe_groq_sync, video_path, output_path
        )

        if progress_callback:
            progress_callback(1.0, "Transcription complete")

        return transcription

    async def load_existing(self, transcription_path: Path) -> Optional[dict]:
        """Load existing transcription from file."""
        if not transcription_path.exists():
            return None

        logger.info(f"Loading existing transcription: {transcription_path}")

        def _load():
            with open(transcription_path, "r", encoding="utf-8") as f:
                return json.load(f)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _load)

    def get_text_for_timerange(
        self,
        transcription: dict,
        start_time: float,
        end_time: float
    ) -> str:
        """Get transcript text for a specific time range."""
        texts = []
        for segment in transcription["segments"]:
            if segment["end"] >= start_time and segment["start"] <= end_time:
                texts.append(segment["text"])
        return " ".join(texts)
