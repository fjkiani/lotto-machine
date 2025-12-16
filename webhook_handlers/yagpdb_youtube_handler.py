"""
YAGPDB YouTube Webhook Handler
================================

Receives YouTube video notifications from YAGPDB and triggers
AssemblyAI transcription + Discord notification.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

# Import transcription service
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from discord_bot.services.video_transcription_service import VideoTranscriptionService

logger = logging.getLogger(__name__)


class YAGPDBYouTubeHandler:
    """
    Handle YAGPDB YouTube webhook notifications.
    
    Flow:
    1. Receive webhook from YAGPDB
    2. Extract video URL and metadata
    3. Queue video for transcription
    4. Process with AssemblyAI
    5. Send results to Discord
    """
    
    def __init__(self, discord_webhook_url: Optional[str] = None):
        """
        Initialize handler.
        
        Args:
            discord_webhook_url: Discord webhook URL for sending results
        """
        self.transcription_service = VideoTranscriptionService()
        self.discord_webhook_url = discord_webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        
        if not self.transcription_service.is_ready():
            logger.warning("⚠️ Video transcription service not ready - check ASSEMBLYAI_API_KEY")
        
        logger.info("✅ YAGPDB YouTube Handler initialized")
    
    def parse_yagpdb_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse YAGPDB webhook payload.
        
        Expected fields:
        - ChannelID: Discord channel ID
        - YoutubeChannelName: Channel name
        - YoutubeChannelID: YouTube channel ID
        - VideoID: Video ID
        - VideoTitle: Video title
        - VideoThumbnail: Thumbnail URL
        - VideoDescription: Description
        - VideoDurationSeconds: Duration in seconds
        - URL: Video URL
        - IsLiveStream: Boolean
        - IsUpcoming: Boolean
        """
        return {
            'channel_id': data.get('ChannelID'),
            'youtube_channel_name': data.get('YoutubeChannelName'),
            'youtube_channel_id': data.get('YoutubeChannelID'),
            'video_id': data.get('VideoID'),
            'video_title': data.get('VideoTitle'),
            'video_thumbnail': data.get('VideoThumbnail'),
            'video_description': data.get('VideoDescription'),
            'video_duration_seconds': data.get('VideoDurationSeconds'),
            'url': data.get('URL'),
            'is_live_stream': data.get('IsLiveStream', False),
            'is_upcoming': data.get('IsUpcoming', False)
        }
    
    async def process_video(self, video_data: Dict[str, Any]):
        """
        Process video: transcribe + send to Discord.
        
        Args:
            video_data: Parsed video data from YAGPDB
        """
        video_url = video_data.get('url')
        video_id = video_data.get('video_id')
        video_title = video_data.get('video_title', 'Unknown')
        channel_name = video_data.get('youtube_channel_name', 'Unknown')
        
        if not video_url:
            logger.error("No video URL in payload")
            return
        
        logger.info(f"🎥 Processing video: {video_id} - {video_title}")
        
        try:
            # Transcribe video
            transcription_result = await self.transcription_service.transcribe_video(
                video_url,
                extract_context=True
            )
            
            if not transcription_result.get('success'):
                logger.error(f"Transcription failed: {transcription_result.get('error')}")
                await self._send_error_notification(video_data, transcription_result.get('error'))
                return
            
            # Send to Discord
            await self._send_discord_notification(video_data, transcription_result)
            
            logger.info(f"✅ Successfully processed video: {video_id}")
            
        except Exception as e:
            logger.error(f"Error processing video {video_id}: {e}")
            await self._send_error_notification(video_data, str(e))
    
    async def _send_discord_notification(
        self, 
        video_data: Dict[str, Any], 
        transcription_result: Dict[str, Any]
    ):
        """Send transcription results to Discord"""
        import aiohttp
        
        if not self.discord_webhook_url:
            logger.warning("No Discord webhook URL configured - skipping notification")
            return
        
        # Format message
        video_title = video_data.get('video_title', 'Unknown')
        channel_name = video_data.get('youtube_channel_name', 'Unknown')
        video_url = video_data.get('url')
        transcript = transcription_result.get('transcript', '')
        word_count = transcription_result.get('word_count', 0)
        duration = transcription_result.get('duration', 0)
        context = transcription_result.get('context', {})
        
        # Build embed
        embed = {
            "title": f"🎥 Video Transcribed: {video_title}",
            "description": f"**Channel:** {channel_name}\n**Duration:** {duration:.1f} min\n**Words:** {word_count:,}",
            "url": video_url,
            "color": 0x00ff00,  # Green
            "fields": [
                {
                    "name": "📝 Transcript Preview",
                    "value": transcript[:1000] + "..." if len(transcript) > 1000 else transcript,
                    "inline": False
                }
            ],
            "footer": {
                "text": f"Video ID: {video_data.get('video_id')}"
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Add context analysis if available
        if context.get('analysis'):
            embed['fields'].append({
                "name": "🧠 Context Analysis",
                "value": context['analysis'][:1000] + "..." if len(context['analysis']) > 1000 else context['analysis'],
                "inline": False
            })
        
        # Send webhook
        payload = {
            "embeds": [embed]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.discord_webhook_url, json=payload) as response:
                    if response.status == 204:
                        logger.info("✅ Discord notification sent")
                    else:
                        logger.warning(f"Discord webhook returned status {response.status}")
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
    
    async def _send_error_notification(self, video_data: Dict[str, Any], error: str):
        """Send error notification to Discord"""
        import aiohttp
        
        if not self.discord_webhook_url:
            return
        
        embed = {
            "title": "❌ Transcription Failed",
            "description": f"**Video:** {video_data.get('video_title', 'Unknown')}\n**Error:** {error}",
            "url": video_data.get('url'),
            "color": 0xff0000,  # Red
            "timestamp": datetime.now().isoformat()
        }
        
        payload = {"embeds": [embed]}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.discord_webhook_url, json=payload) as response:
                    logger.info(f"Error notification sent (status: {response.status})")
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")


# FastAPI app for webhook endpoint
app = FastAPI(title="YAGPDB YouTube Webhook Handler")

# Initialize handler
handler = YAGPDBYouTubeHandler()


@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "operational",
        "service": "YAGPDB YouTube Webhook Handler",
        "transcription_ready": handler.transcription_service.is_ready()
    }


@app.post("/webhook/yagpdb/youtube")
async def handle_yagpdb_webhook(
    request: Request, 
    background_tasks: BackgroundTasks
):
    """
    Handle YAGPDB YouTube webhook.
    
    Expected payload format (from YAGPDB):
    {
        "ChannelID": "123456789",
        "YoutubeChannelName": "Channel Name",
        "YoutubeChannelID": "UC...",
        "VideoID": "9EKmaqy9oFE",
        "VideoTitle": "Video Title",
        "VideoThumbnail": "https://...",
        "VideoDescription": "Description...",
        "VideoDurationSeconds": 600,
        "URL": "https://www.youtube.com/watch?v=9EKmaqy9oFE",
        "IsLiveStream": false,
        "IsUpcoming": false
    }
    """
    try:
        # Get payload
        data = await request.json()
        
        # Parse YAGPDB payload
        video_data = handler.parse_yagpdb_payload(data)
        
        # Validate
        if not video_data.get('url'):
            raise HTTPException(status_code=400, detail="Missing video URL in payload")
        
        # Skip livestreams and upcoming videos (optional)
        if video_data.get('is_live_stream'):
            logger.info(f"Skipping livestream: {video_data.get('video_id')}")
            return {"status": "skipped", "reason": "livestream"}
        
        if video_data.get('is_upcoming'):
            logger.info(f"Skipping upcoming video: {video_data.get('video_id')}")
            return {"status": "skipped", "reason": "upcoming"}
        
        # Queue for processing
        background_tasks.add_task(handler.process_video, video_data)
        
        logger.info(f"✅ Video queued for processing: {video_data.get('video_id')}")
        
        return {
            "status": "queued",
            "video_id": video_data.get('video_id'),
            "message": "Video queued for transcription"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


