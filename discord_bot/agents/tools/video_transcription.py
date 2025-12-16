"""
Video Transcription Tool
========================

Tool for transcribing YouTube videos and extracting context.
Integrates with Discord bot for automated video analysis.
"""

import logging
import re
from typing import Dict, Any, Optional, List

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class VideoTranscriptionTool(BaseTool):
    """
    Video Transcription Tool
    
    Transcribes YouTube videos and extracts context using AssemblyAI.
    """

    def __init__(self):
        # Initialize transcription service
        try:
            from ...services.video_transcription_service import VideoTranscriptionService
            self.transcription_service = VideoTranscriptionService()
        except Exception as e:
            logger.error(f"Failed to initialize transcription service: {e}")
            self.transcription_service = None

    @property
    def name(self) -> str:
        return "video_transcription"

    @property
    def description(self) -> str:
        return "Transcribe YouTube videos and extract context/insights"

    @property
    def capabilities(self) -> List[str]:
        return [
            "Transcribe YouTube videos",
            "Extract key points and insights",
            "Generate summaries",
            "Identify topics and sentiment"
        ]

    @property
    def keywords(self) -> List[str]:
        return [
            "transcribe", "transcription", "video", "youtube",
            "analyze video", "video analysis", "video summary"
        ]

    def matches_query(self, query: str) -> bool:
        """Check if query is about video transcription"""
        query_lower = query.lower()
        
        video_keywords = [
            "transcribe", "transcription", "video", "youtube",
            "analyze video", "video analysis", "video summary",
            "what did they say", "video content"
        ]
        
        youtube_patterns = [
            r'youtube\.com',
            r'youtu\.be',
            r'watch\?v='
        ]
        
        # Check for keywords
        if any(keyword in query_lower for keyword in video_keywords):
            return True
        
        # Check for YouTube URLs
        if any(re.search(pattern, query) for pattern in youtube_patterns):
            return True
        
        return False

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute video transcription"""
        if not self.transcription_service or not self.transcription_service.is_ready():
            return ToolResult(
                success=False,
                data={},
                error="Video transcription service not available. Check ASSEMBLYAI_API_KEY."
            )

        # Extract URL from params or query
        url = params.get("url") or params.get("query", "")
        
        # Try to extract URL from query if not provided
        if not url or not self.transcription_service.is_youtube_url(url):
            url = self._extract_url_from_query(params.get("query", ""))
        
        if not url:
            return ToolResult(
                success=False,
                data={},
                error="No YouTube URL found. Please provide a YouTube video URL."
            )

        # Transcribe video (async, but we'll handle it)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            self.transcription_service.transcribe_video(url, extract_context=True)
        )

        if result.get("success"):
            return ToolResult(
                success=True,
                data=result,
                error=None
            )
        else:
            return ToolResult(
                success=False,
                data={},
                error=result.get("error", "Transcription failed")
            )

    def _extract_url_from_query(self, query: str) -> Optional[str]:
        """Extract YouTube URL from query text"""
        patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'https?://youtu\.be/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/embed/[\w-]+',
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                return match.group(0)

        return None

    def format_response(self, result: ToolResult) -> str:
        """Format transcription result for display"""
        if not result.success:
            return f"❌ **Transcription Failed**\n{result.error}"

        # Use service's Discord formatter
        return self.transcription_service.format_for_discord(result.data)

