#!/usr/bin/env python3
"""
Video Transcription Service - AssemblyAI Integration
=====================================================

Service for transcribing YouTube videos and extracting context.
Integrates with Discord bot for automated video analysis.
"""

import os
import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class VideoTranscriptionService:
    """
    Video transcription service using AssemblyAI
    
    Features:
    - Direct YouTube URL transcription (no download needed)
    - Automatic context extraction
    - Error handling and retries
    - Discord-friendly formatting
    """

    def __init__(self):
        """Initialize video transcription service"""
        self.api_key = os.getenv("ASSEMBLYAI_API_KEY")
        self.available = False
        self.client = None

        if not self.api_key:
            logger.warning("⚠️ ASSEMBLYAI_API_KEY not found - video transcription disabled")
            return

        try:
            import assemblyai as aai
            aai.settings.api_key = self.api_key
            self.client = aai
            self.available = True
            logger.info("✅ Video Transcription Service initialized (AssemblyAI)")
        except ImportError:
            logger.error("❌ AssemblyAI not installed. Install with: pip install assemblyai")
        except Exception as e:
            logger.error(f"❌ Failed to initialize AssemblyAI: {e}")

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL"""
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def is_youtube_url(self, text: str) -> bool:
        """Check if text contains a YouTube URL"""
        youtube_patterns = [
            r'youtube\.com/watch\?v=',
            r'youtu\.be/',
            r'youtube\.com/embed/',
        ]
        return any(re.search(pattern, text) for pattern in youtube_patterns)

    async def transcribe_video(self, url: str, extract_context: bool = True) -> Dict[str, Any]:
        """
        Transcribe YouTube video and extract context
        
        Args:
            url: YouTube video URL
            extract_context: Whether to extract context using LLM
            
        Returns:
            Dict with transcription and analysis
        """
        if not self.available:
            return {
                "success": False,
                "error": "Video transcription service not available. Check ASSEMBLYAI_API_KEY."
            }

        video_id = self.extract_video_id(url)
        if not video_id:
            return {
                "success": False,
                "error": "Invalid YouTube URL"
            }

        try:
            logger.info(f"🎥 Transcribing video: {video_id}")

            # Configure transcription
            config = self.client.TranscriptionConfig(
                punctuate=True,
                speaker_labels=False,
                language_code="en"
            )

            # Transcribe directly from URL
            transcriber = self.client.Transcriber(config=config)
            transcript = transcriber.transcribe(url)

            # Wait for completion
            import time
            max_wait = 300  # 5 minutes
            wait_time = 0

            while transcript.status != self.client.TranscriptStatus.completed:
                if transcript.status == self.client.TranscriptStatus.error:
                    return {
                        "success": False,
                        "error": f"Transcription failed: {transcript.error}"
                    }

                if wait_time >= max_wait:
                    return {
                        "success": False,
                        "error": "Transcription timeout"
                    }

                time.sleep(2)
                wait_time += 2
                transcript = transcriber.get_by_id(transcript.id)

            # Extract segments
            segments = []
            if transcript.utterances:
                for utterance in transcript.utterances:
                    segments.append({
                        "start": utterance.start / 1000,  # Convert ms to seconds
                        "end": utterance.end / 1000,
                        "text": utterance.text
                    })
            elif transcript.words:
                # Fallback to word-level
                current_segment = {"start": None, "end": None, "text": ""}
                for word in transcript.words:
                    if current_segment["start"] is None:
                        current_segment["start"] = word.start / 1000
                    current_segment["end"] = word.end / 1000
                    current_segment["text"] += word.text + " "
                segments.append(current_segment)

            result = {
                "success": True,
                "video_id": video_id,
                "url": url,
                "transcript": transcript.text,
                "language": transcript.language_code or "en",
                "segments": segments,
                "duration": transcript.audio_duration / 1000 if transcript.audio_duration else 0,
                "word_count": len(transcript.text.split()),
                "created_at": datetime.now().isoformat()
            }

            # Extract context if requested
            if extract_context:
                context = await self._extract_context(transcript.text, url)
                result["context"] = context

            logger.info(f"✅ Transcription complete: {video_id} ({result['word_count']} words)")
            return result

        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _extract_context(self, transcript: str, url: str) -> Dict[str, Any]:
        """Extract context and insights from transcript using LLM"""
        try:
            # Import LLM service
            from .savage_llm_service import SavageLLMService
            llm_service = SavageLLMService()

            # Build prompt for context extraction
            prompt = f"""
Analyze this video transcript and provide comprehensive context:

VIDEO URL: {url}
TRANSCRIPT (first 6000 chars):
{transcript[:6000]}

Provide analysis in this format:
1. **Summary**: 2-3 sentence summary of the video
2. **Key Points**: List 5-7 main points discussed
3. **Topics**: List main topics covered
4. **Sentiment**: Overall sentiment (positive/negative/neutral)
5. **Actionable Insights**: List 3-5 actionable takeaways
6. **Related Concepts**: List related concepts mentioned

Format as clear, structured text suitable for Discord.
"""

            # Get LLM analysis
            llm_response = await llm_service.get_savage_response(prompt, level="alpha_warrior")

            if llm_response.get("status") == "success":
                return {
                    "analysis": llm_response.get("response", ""),
                    "extracted_at": datetime.now().isoformat()
                }
            else:
                return {
                    "analysis": "Context extraction unavailable",
                    "error": llm_response.get("error", "Unknown error")
                }

        except Exception as e:
            logger.error(f"Context extraction error: {e}")
            return {
                "analysis": "Context extraction failed",
                "error": str(e)
            }

    def format_for_discord(self, result: Dict[str, Any]) -> str:
        """Format transcription result for Discord message"""
        if not result.get("success"):
            return f"❌ **Transcription Failed**\n{result.get('error', 'Unknown error')}"

        video_id = result.get("video_id", "Unknown")
        transcript = result.get("transcript", "")
        word_count = result.get("word_count", 0)
        duration = result.get("duration", 0)
        context = result.get("context", {})

        # Build Discord message
        message_parts = [
            f"🎥 **Video Transcription Complete**",
            f"**Video ID:** `{video_id}`",
            f"**Duration:** {duration:.1f} minutes",
            f"**Word Count:** {word_count:,} words",
            "",
            "📝 **Transcript Preview:**",
            f"```{transcript[:1000]}...```" if len(transcript) > 1000 else f"```{transcript}```"
        ]

        # Add context if available
        if context.get("analysis"):
            message_parts.extend([
                "",
                "🧠 **Context Analysis:**",
                context["analysis"][:1500]  # Limit length for Discord
            ])

        return "\n".join(message_parts)

    def is_ready(self) -> bool:
        """Check if service is ready"""
        return self.available



