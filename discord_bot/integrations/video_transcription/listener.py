"""
Video Transcription Listener
============================

Autonomously listens for YouTube URLs in Discord messages and transcribes them.
Sends transcription and analysis to the channel.
"""

import discord
import logging
import re
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class VideoTranscriptionListener:
    """
    Autonomous video transcription listener.
    
    Detects YouTube URLs in messages and automatically:
    1. Transcribes the video
    2. Extracts context and insights
    3. Sends formatted response to Discord
    """

    def __init__(self, bot):
        self.bot = bot
        
        # Initialize transcription service
        try:
            from ...services.video_transcription_service import VideoTranscriptionService
            self.transcription_service = VideoTranscriptionService()
        except Exception as e:
            logger.error(f"Failed to initialize transcription service: {e}")
            self.transcription_service = None

        # YouTube URL patterns (including template variables that YAGPDB uses)
        self.youtube_patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'https?://youtu\.be/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/embed/[\w-]+',
            # Also match template variables (YAGPDB will replace these with real URLs)
            r'\{\{\.URL\}\}',
        ]

    async def process_message(self, message: discord.Message):
        """Process incoming messages for YouTube URLs"""
        # Don't process bot's own messages
        if message.author == self.bot.user:
            return

        # Check message content for YouTube URL
        youtube_url = self._extract_youtube_url(message.content)
        
        # Also check embeds (YAGPDB often posts embeds with video links)
        if not youtube_url and message.embeds:
            for embed in message.embeds:
                # Check embed description
                if embed.description:
                    youtube_url = self._extract_youtube_url(embed.description)
                    if youtube_url:
                        break
                # Check embed URL
                if embed.url:
                    youtube_url = self._extract_youtube_url(embed.url)
                    if youtube_url:
                        break
                # Check embed fields
                if embed.fields:
                    for field in embed.fields:
                        if field.value:
                            youtube_url = self._extract_youtube_url(field.value)
                            if youtube_url:
                                break
                    if youtube_url:
                        break
        
        if youtube_url:
            # Check if this is from YAGPDB (for logging and special handling)
            is_yagpdb = (
                message.author.name.lower() == "yagpdb" or 
                "yagpdb" in message.author.name.lower() or
                message.author.name.lower() == "yagpdb.xyz"
            )
            
            if is_yagpdb:
                logger.info(f"🎥 Detected YAGPDB video notification from {message.author.name}")
                logger.info(f"   Channel: {message.channel.name}")
                logger.info(f"   Video URL: {youtube_url}")
            
            await self._process_video_transcription(message, youtube_url, is_yagpdb=is_yagpdb)

    def _extract_youtube_url(self, text: str) -> Optional[str]:
        """Extract YouTube URL from message text"""
        if not text:
            return None

        for pattern in self.youtube_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return None

    async def _process_video_transcription(self, message: discord.Message, url: str, is_yagpdb: bool = False):
        """Process video transcription and send response"""
        if not self.transcription_service or not self.transcription_service.is_ready():
            logger.warning("Video transcription service not available")
            return

        try:
            # Send "processing" message
            source_note = " (from YAGPDB)" if is_yagpdb else ""
            processing_msg = await message.channel.send(
                f"🎥 **Processing video transcription{source_note}...**\n{url}\n"
                f"*This may take a few moments...*"
            )

            logger.info(f"🎥 Transcribing video from message: {url}{source_note}")

            # Transcribe video
            result = await self.transcription_service.transcribe_video(
                url, 
                extract_context=True
            )

            if not result.get("success"):
                error_msg = result.get("error", "Unknown error")
                await processing_msg.edit(
                    content=f"❌ **Transcription Failed**\n{error_msg}"
                )
                logger.error(f"Transcription failed: {error_msg}")
                return

            # Build Discord embed
            embed = await self._build_transcription_embed(result, url)

            # Delete processing message and send result
            await processing_msg.delete()
            await message.channel.send(embed=embed)

            logger.info(f"✅ Video transcription sent: {result.get('video_id')}")

        except Exception as e:
            logger.error(f"❌ Error processing video transcription: {e}")
            try:
                await processing_msg.edit(
                    content=f"❌ **Error processing video**\n{str(e)}"
                )
            except:
                pass

    async def _build_transcription_embed(self, result: Dict, url: str) -> discord.Embed:
        """Build Discord embed for transcription result"""
        video_id = result.get("video_id", "Unknown")
        transcript = result.get("transcript", "")
        word_count = result.get("word_count", 0)
        duration = result.get("duration", 0)
        context = result.get("context", {})

        # Create embed
        embed = discord.Embed(
            title="🎥 Video Transcription Complete",
            description=f"**Video:** [{video_id}]({url})",
            color=0x00ff00,  # Green
            timestamp=discord.utils.utcnow()
        )

        # Add metadata
        embed.add_field(
            name="📊 Stats",
            value=f"**Duration:** {duration:.1f} min\n**Words:** {word_count:,}",
            inline=True
        )

        embed.add_field(
            name="🌐 Language",
            value=result.get("language", "en").upper(),
            inline=True
        )

        # Add transcript preview
        transcript_preview = transcript[:1000] + "..." if len(transcript) > 1000 else transcript
        embed.add_field(
            name="📝 Transcript Preview",
            value=f"```{transcript_preview}```",
            inline=False
        )

        # Add context analysis if available
        if context.get("analysis"):
            analysis = context["analysis"]
            # Limit analysis length for Discord
            if len(analysis) > 1000:
                analysis = analysis[:1000] + "..."
            
            embed.add_field(
                name="🧠 Context Analysis",
                value=analysis,
                inline=False
            )

        embed.set_footer(text="Alpha Intelligence | Video Transcription Service")

        return embed

