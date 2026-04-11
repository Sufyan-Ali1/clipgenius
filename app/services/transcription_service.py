"""
Transcription Service - Single Responsibility: Audio to text conversion

Uses OpenAI Whisper for speech-to-text with timestamps.
"""

import json
import subprocess
from pathlib import Path
from typing import Callable, Optional
import asyncio
import warnings

from app.core.config import settings
from app.core.logging import get_logger

# Suppress FP16 warning on CPU
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

logger = get_logger("transcription_service")


class TranscriptionService:
    """
    Single Responsibility: Convert audio/video to text with timestamps.

    Uses OpenAI Whisper for transcription.
    """

    def __init__(self):
        self.model_name = settings.WHISPER_MODEL
        self.language = settings.WHISPER_LANGUAGE
        self.temp_dir = settings.TEMP_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._model = None

    def _load_model(self):
        """Load Whisper model (lazy loading)."""
        if self._model is None:
            import torch
            import whisper

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading Whisper model '{self.model_name}' on {device}...")
            self._model = whisper.load_model(self.model_name, device=device)
            logger.info("Model loaded successfully.")

    def _extract_audio(self, video_path: Path) -> Path:
        """Extract audio from video file using FFmpeg."""
        audio_path = self.temp_dir / f"{video_path.stem}_audio.wav"

        if audio_path.exists():
            logger.info(f"Using existing audio: {audio_path}")
            return audio_path

        logger.info(f"Extracting audio from {video_path.name}...")

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

    def _transcribe_sync(
        self,
        video_path: Path,
        output_path: Optional[Path] = None
    ) -> dict:
        """Synchronous transcription."""
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"File not found: {video_path}")

        # Extract audio if video file
        audio_extensions = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
        if video_path.suffix.lower() not in audio_extensions:
            audio_path = self._extract_audio(video_path)
        else:
            audio_path = video_path

        self._load_model()

        logger.info(f"Transcribing {audio_path.name}...")

        result = self._model.transcribe(
            str(audio_path),
            language=self.language,
            word_timestamps=True,
            verbose=False
        )

        # Format output
        transcription = {
            "text": result["text"],
            "language": result.get("language", self.language),
            "duration": result["segments"][-1]["end"] if result["segments"] else 0,
            "segments": []
        }

        for segment in result["segments"]:
            seg_data = {
                "id": segment["id"],
                "start": round(segment["start"], 2),
                "end": round(segment["end"], 2),
                "text": segment["text"].strip(),
            }

            if "words" in segment:
                seg_data["words"] = [
                    {
                        "word": w["word"],
                        "start": round(w["start"], 2),
                        "end": round(w["end"], 2)
                    }
                    for w in segment["words"]
                ]

            transcription["segments"].append(seg_data)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(transcription, f, indent=2, ensure_ascii=False)
            logger.info(f"Transcription saved: {output_path}")

        logger.info(f"Transcription complete. {len(transcription['segments'])} segments.")
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
        if progress_callback:
            progress_callback(0.0, "Loading Whisper model...")

        loop = asyncio.get_event_loop()

        if progress_callback:
            progress_callback(0.1, "Transcribing audio...")

        transcription = await loop.run_in_executor(
            None,
            self._transcribe_sync,
            video_path,
            output_path,
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
