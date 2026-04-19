"""
Analysis Service - Single Responsibility: LLM engagement analysis

Analyzes transcription for viral-worthy segments using LLM.
"""

import json
import re
from pathlib import Path
from typing import Callable, List, Optional
import asyncio

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("analysis_service")


class AnalysisService:
    """
    Single Responsibility: Analyze transcription for engaging segments using LLM.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.provider = provider or settings.LLM_PROVIDER
        self.model = model or settings.LLM_MODEL
        self.min_duration = settings.MIN_CLIP_DURATION
        self.max_duration = settings.MAX_CLIP_DURATION
        self.prompts_dir = settings.BASE_DIR / "app" / "prompts"
        self._llm = None

    def _get_llm(self):
        """Get LLM provider instance."""
        if self._llm is None:
            from app.services.llm_service import get_llm_provider
            self._llm = get_llm_provider(self.provider)
        return self._llm

    def _load_prompt_template(self) -> str:
        """Load the engagement analysis prompt template."""
        prompt_file = self.prompts_dir / "engagement_prompt.txt"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        else:
            return self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        """Return default prompt if template file doesn't exist."""
        return """You are an elite TikTok/YouTube Shorts content strategist. Your clips consistently hit 1M+ views.

Analyze this transcript and extract the TOP 10 most viral-worthy segments.

=== TRANSCRIPT ===
{transcript}
=== END TRANSCRIPT ===

VIRAL CONTENT PILLARS:

1. PATTERN INTERRUPTS (Score 9-10) - "Nobody talks about this...", shocking facts, hot takes
2. EMOTIONAL TRIGGERS (Score 8-10) - Rage bait, inspiration, FOMO, relatability
3. CURIOSITY GAPS (Score 8-9) - Secrets, hacks, "What they don't tell you..."
4. VALUE BOMBS (Score 7-9) - Actionable tips, money hacks, expert breakdowns
5. STORY HOOKS (Score 7-9) - Transformations, plot twists, relatable struggles

AVOID: Slow intros, context-dependent content, incomplete thoughts, boring setups, half sentences

CRITICAL - COMPLETE SENTENCES ONLY:
- START at the BEGINNING of a sentence (never mid-sentence)
- END at the END of a sentence (never mid-sentence)
- Must be fully understandable with no missing context
- If great hook starts mid-sentence, adjust timestamps to include full sentence

CLIP REQUIREMENTS:
- Duration: {min_duration}-{max_duration} seconds
- Killer hook in first 2-3 seconds
- Works standalone (no prior context needed)
- Clear payoff or conclusion
- MUST start and end with COMPLETE sentences only

HASHTAG STRATEGY (6-8 per clip):
- REACH: #fyp #foryou #viral
- ENGAGEMENT: #relatable #facts #truth
- EMOTION: #motivated #mindblown #gamechanger
- NICHE: Topic-specific tags

DESCRIPTION STRATEGY (scroll-stopping captions):
- Use curiosity gaps, controversy, FOMO, or engagement hooks
- NEVER repeat exact transcript words
- Use 2-3 emojis max
- Under 150 characters
- Examples: "Nobody tells you this...", "Comment YES if you agree"

OUTPUT FORMAT (JSON only):
{{
  "clips": [
    {{
      "start": "MM:SS",
      "end": "MM:SS",
      "score": 9,
      "hook": "First 5-10 attention-grabbing words",
      "reason": "Why this will go viral",
      "type": "pattern_interrupt|emotional|curiosity|value|story",
      "hashtags": ["#fyp", "#viral", "#mindset", "#success", "#entrepreneur", "#motivation"],
      "description": "Nobody tells you this about success... (save this)"
    }}
  ]
}}

Return ONLY the JSON. No markdown, no code blocks."""

    def _format_transcript_for_analysis(self, transcription: dict) -> str:
        """Format transcript with timestamps for LLM analysis."""
        lines = []
        for segment in transcription["segments"]:
            start_min = int(segment["start"] // 60)
            start_sec = int(segment["start"] % 60)
            timestamp = f"[{start_min:02d}:{start_sec:02d}]"
            lines.append(f"{timestamp} {segment['text']}")
        return "\n".join(lines)

    def _chunk_transcript(self, transcription: dict, chunk_duration: int = 600) -> list:
        """Split long transcripts into chunks for processing."""
        segments = transcription["segments"]
        if not segments:
            return []

        total_duration = segments[-1]["end"]

        if total_duration <= chunk_duration * 1.5:
            return [{
                "offset": 0,
                "segments": segments,
                "text": self._format_transcript_for_analysis(transcription)
            }]

        chunks = []
        current_chunk = []
        chunk_start = 0

        for segment in segments:
            current_chunk.append(segment)

            if segment["end"] - chunk_start >= chunk_duration:
                chunks.append({
                    "offset": chunk_start,
                    "segments": current_chunk,
                    "text": self._format_transcript_for_analysis({"segments": current_chunk})
                })
                chunk_start = segment["end"]
                current_chunk = []

        if current_chunk:
            chunks.append({
                "offset": chunk_start,
                "segments": current_chunk,
                "text": self._format_transcript_for_analysis({"segments": current_chunk})
            })

        return chunks

    def _parse_llm_response(self, response: str) -> list:
        """Parse LLM response to extract clip suggestions."""
        try:
            data = json.loads(response)
            return data.get("clips", [])
        except json.JSONDecodeError:
            pass

        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return data.get("clips", [])
            except json.JSONDecodeError:
                pass

        json_match = re.search(r"\{[^{}]*\"clips\"[^{}]*\[.*?\]\s*\}", response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return data.get("clips", [])
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse LLM response as JSON")
        return []

    def _parse_timestamp(self, timestamp: str) -> float:
        """Convert MM:SS or HH:MM:SS timestamp to seconds."""
        parts = timestamp.strip().split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            raise ValueError(f"Invalid timestamp format: {timestamp}")

    def _analyze_sync(
        self,
        transcription: dict,
        output_path: Optional[Path] = None
    ) -> List[dict]:
        """Synchronous analysis."""
        llm = self._get_llm()

        if not llm.is_available():
            raise RuntimeError(f"LLM provider '{llm.name}' is not available.")

        chunks = self._chunk_transcript(transcription)
        logger.info(f"Processing {len(chunks)} transcript chunk(s)...")

        all_clips = []
        prompt_template = self._load_prompt_template()

        for i, chunk in enumerate(chunks):
            logger.info(f"Analyzing chunk {i+1}/{len(chunks)}...")

            prompt = prompt_template.format(
                transcript=chunk["text"],
                min_duration=self.min_duration,
                max_duration=self.max_duration
            )

            response = llm.generate(prompt)
            logger.info(f"Raw LLM response (first 500 chars): {response[:500]}")
            clips = self._parse_llm_response(response)
            logger.info(f"Parsed {len(clips)} clips from LLM")
            if clips:
                logger.info(f"First clip keys: {clips[0].keys() if clips else 'none'}")
                logger.info(f"First clip hashtags: {clips[0].get('hashtags', 'NOT FOUND')}")
                logger.info(f"First clip description: {clips[0].get('description', 'NOT FOUND')}")

            for clip in clips:
                try:
                    start_seconds = self._parse_timestamp(clip["start"]) + chunk["offset"]
                    end_seconds = self._parse_timestamp(clip["end"]) + chunk["offset"]

                    clip["start_seconds"] = start_seconds
                    clip["end_seconds"] = end_seconds
                    clip["duration"] = end_seconds - start_seconds

                    all_clips.append(clip)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping invalid clip: {e}")
                    continue

        all_clips.sort(key=lambda x: x.get("score", 0), reverse=True)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({"clips": all_clips}, f, indent=2)
            logger.info(f"Analysis saved: {output_path}")

        return all_clips

    async def analyze(
        self,
        transcription: dict,
        output_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> List[dict]:
        """
        Analyze transcription for engaging clip suggestions.

        Args:
            transcription: Transcription dict with segments
            output_path: Optional path to save analysis JSON
            progress_callback: Optional callback(progress, message)

        Returns:
            List of clip suggestions with timestamps and scores
        """
        logger.info(f"Starting analysis with {self.provider}/{self.model}")

        if progress_callback:
            progress_callback(0.0, f"Analyzing with {self.provider}...")

        loop = asyncio.get_event_loop()

        suggestions = await loop.run_in_executor(
            None,
            self._analyze_sync,
            transcription,
            output_path,
        )

        if progress_callback:
            progress_callback(1.0, "Analysis complete")

        logger.info(f"Analysis complete: {len(suggestions)} suggestions")
        return suggestions

    async def load_existing(self, analysis_path: Path) -> Optional[List[dict]]:
        """Load existing analysis from file."""
        if not analysis_path.exists():
            return None

        def _load():
            with open(analysis_path, "r", encoding="utf-8") as f:
                return json.load(f).get("clips", [])

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _load)
