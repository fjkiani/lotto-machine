#!/usr/bin/env python3
"""
Video Transcription Pipeline with Webhook Integration
======================================================

Complete solution for transcribing YouTube videos triggered by webhooks.
Includes: webhook handler, video extraction, transcription, and context analysis.

Usage:
    python3 video_transcription_pipeline.py

Features:
- FastAPI webhook endpoint for YouTube video URLs
- Multiple transcription methods (YouTube captions, Whisper AI)
- LLM-powered context extraction
- Async processing with queue system
- Database storage for transcripts and metadata
"""

import os
import re
import json
import logging
import asyncio
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from urllib.parse import urlparse, parse_qs

# FastAPI for webhook
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

# YouTube extraction
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    print("⚠️  yt-dlp not installed. Install with: pip install yt-dlp")

# Transcription APIs (replaces Whisper)
try:
    from transcription_api_providers import TranscriptionAPIManager
    TRANSCRIPTION_AVAILABLE = True
except ImportError:
    TRANSCRIPTION_AVAILABLE = False
    print("⚠️  Transcription APIs not available. Install dependencies from requirements_transcription.txt")

# LLM for context extraction
try:
    from src.data.llm_api import query_llm
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("⚠️  LLM API not available. Context extraction will be limited.")

# Database (SQLite for simplicity, can upgrade to PostgreSQL)
import sqlite3
from contextlib import contextmanager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Video Transcription Pipeline", version="1.0.0")

# Configuration
CONFIG = {
    "webhook_secret": os.getenv("WEBHOOK_SECRET", "your-secret-key"),
    "transcription_provider": os.getenv("TRANSCRIPTION_PROVIDER", "assemblyai"),  # assemblyai, deepgram, rev_ai
    "db_path": os.getenv("DB_PATH", "video_transcripts.db"),
    "transcript_dir": os.getenv("TRANSCRIPT_DIR", "transcripts"),
    "audio_dir": os.getenv("AUDIO_DIR", "audio_cache"),
    "max_video_length": int(os.getenv("MAX_VIDEO_LENGTH", "3600")),  # 1 hour default
    "enable_llm_context": LLM_AVAILABLE,
    "llm_provider": os.getenv("LLM_PROVIDER", "gemini"),
}


@dataclass
class VideoMetadata:
    """Video metadata structure"""
    video_id: str
    url: str
    title: str
    duration: int
    uploader: str
    upload_date: str
    view_count: Optional[int] = None
    description: Optional[str] = None


@dataclass
class Transcript:
    """Transcript structure"""
    video_id: str
    transcript_text: str
    method: str  # "youtube_captions", "whisper", "hybrid"
    language: str
    segments: List[Dict[str, Any]]
    confidence: float
    processing_time: float
    created_at: str


@dataclass
class ContextAnalysis:
    """LLM context analysis structure"""
    video_id: str
    summary: str
    key_points: List[str]
    topics: List[str]
    sentiment: str
    actionable_insights: List[str]
    related_concepts: List[str]
    created_at: str


class DatabaseManager:
    """SQLite database manager for transcripts and metadata"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize database tables"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Videos table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    video_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT,
                    duration INTEGER,
                    uploader TEXT,
                    upload_date TEXT,
                    view_count INTEGER,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Transcripts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    transcript_text TEXT NOT NULL,
                    method TEXT NOT NULL,
                    language TEXT,
                    segments TEXT,  -- JSON
                    confidence REAL,
                    processing_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(video_id)
                )
            """)

            # Context analysis table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS context_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    summary TEXT,
                    key_points TEXT,  -- JSON
                    topics TEXT,  -- JSON
                    sentiment TEXT,
                    actionable_insights TEXT,  -- JSON
                    related_concepts TEXT,  -- JSON
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(video_id)
                )
            """)

            # Processing queue table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',  -- pending, processing, completed, failed
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            logger.info("Database initialized successfully")

    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_video_metadata(self, metadata: VideoMetadata):
        """Save video metadata"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO videos 
                (video_id, url, title, duration, uploader, upload_date, view_count, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.video_id, metadata.url, metadata.title, metadata.duration,
                metadata.uploader, metadata.upload_date, metadata.view_count, metadata.description
            ))

    def save_transcript(self, transcript: Transcript):
        """Save transcript"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO transcripts 
                (video_id, transcript_text, method, language, segments, confidence, processing_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                transcript.video_id, transcript.transcript_text, transcript.method,
                transcript.language, json.dumps(transcript.segments),
                transcript.confidence, transcript.processing_time
            ))

    def save_context_analysis(self, analysis: ContextAnalysis):
        """Save context analysis"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO context_analysis 
                (video_id, summary, key_points, topics, sentiment, actionable_insights, related_concepts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis.video_id, analysis.summary,
                json.dumps(analysis.key_points), json.dumps(analysis.topics),
                analysis.sentiment, json.dumps(analysis.actionable_insights),
                json.dumps(analysis.related_concepts)
            ))

    def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video metadata"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_transcript(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get latest transcript for video"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM transcripts 
                WHERE video_id = ? 
                ORDER BY created_at DESC 
                LIMIT 1
            """, (video_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                result['segments'] = json.loads(result['segments'])
                return result
            return None

    def get_context_analysis(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get context analysis for video"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM context_analysis 
                WHERE video_id = ? 
                ORDER BY created_at DESC 
                LIMIT 1
            """, (video_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                for key in ['key_points', 'topics', 'actionable_insights', 'related_concepts']:
                    if result[key]:
                        result[key] = json.loads(result[key])
                return result
            return None


class YouTubeExtractor:
    """Extract video metadata and audio from YouTube"""

    def __init__(self, audio_dir: str = "audio_cache"):
        self.audio_dir = audio_dir
        os.makedirs(audio_dir, exist_ok=True)

        if not YT_DLP_AVAILABLE:
            raise ImportError("yt-dlp is required. Install with: pip install yt-dlp")

    def extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL"""
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        raise ValueError(f"Could not extract video ID from URL: {url}")

    def get_video_metadata(self, url: str) -> VideoMetadata:
        """Get video metadata using yt-dlp"""
        video_id = self.extract_video_id(url)

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            return VideoMetadata(
                video_id=video_id,
                url=url,
                title=info.get('title', 'Unknown'),
                duration=int(info.get('duration', 0)),
                uploader=info.get('uploader', 'Unknown'),
                upload_date=info.get('upload_date', ''),
                view_count=info.get('view_count'),
                description=info.get('description', '')
            )

    def download_audio(self, url: str, output_path: Optional[str] = None) -> str:
        """Download audio from YouTube video"""
        video_id = self.extract_video_id(url)

        if output_path is None:
            output_path = os.path.join(self.audio_dir, f"{video_id}.wav")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path.replace('.wav', ''),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # yt-dlp adds extension, so find the actual file
        base_path = output_path.replace('.wav', '')
        for ext in ['.wav', '.m4a', '.mp3', '.webm']:
            if os.path.exists(base_path + ext):
                return base_path + ext

        raise FileNotFoundError(f"Audio file not found after download: {base_path}")

    def get_youtube_captions(self, url: str, language: str = 'en') -> Optional[Dict[str, Any]]:
        """Try to get YouTube captions/subtitles"""
        video_id = self.extract_video_id(url)

        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': [language, 'en'],
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # Check for available captions
                if 'subtitles' in info or 'automatic_captions' in info:
                    # yt-dlp can extract captions, but we need to download them
                    # For now, return None and use Whisper as fallback
                    logger.info(f"Captions available for {video_id}, but extraction requires download")
                    return None

        except Exception as e:
            logger.warning(f"Could not get YouTube captions: {e}")

        return None


class Transcriptor:
    """Handle video transcription using professional APIs (replaces Whisper)"""

    def __init__(self, provider: str = "assemblyai"):
        self.provider = provider
        self.api_manager = None

        if not TRANSCRIPTION_AVAILABLE:
            logger.warning("Transcription APIs not available. Install dependencies.")
        else:
            try:
                self.api_manager = TranscriptionAPIManager(preferred_provider=provider)
                logger.info(f"Transcription API manager initialized with provider: {provider}")
            except Exception as e:
                logger.error(f"Failed to initialize transcription APIs: {e}")

    def transcribe_video(self, url: str, extractor: YouTubeExtractor, 
                        prefer_captions: bool = True) -> Transcript:
        """
        Transcribe video using professional API (no download needed!)
        
        Args:
            url: YouTube URL or direct video URL
            extractor: YouTube extractor (for metadata only)
            prefer_captions: Try YouTube captions first (future enhancement)
        """
        video_id = extractor.extract_video_id(url)
        start_time = datetime.now()

        if not self.api_manager:
            raise ImportError("Transcription APIs not available")

        # Try YouTube captions first if preferred (future enhancement)
        if prefer_captions:
            captions = extractor.get_youtube_captions(url)
            if captions:
                logger.info(f"Using YouTube captions for {video_id}")
                # Process captions (implementation would go here)
                # For now, fall through to API

        # Use professional transcription API (direct URL - no download!)
        logger.info(f"Transcribing with {self.provider} API: {url}")
        
        try:
            api_result = self.api_manager.transcribe(url, provider=self.provider)
            
            return Transcript(
                video_id=video_id,
                transcript_text=api_result.text,
                method=api_result.provider,
                language=api_result.language,
                segments=api_result.segments,
                confidence=api_result.confidence,
                processing_time=api_result.processing_time,
                created_at=datetime.now().isoformat()
            )
        except Exception as e:
            logger.error(f"Transcription API failed: {e}")
            # Try fallback providers
            logger.info("Attempting fallback providers...")
            try:
                fallback_result = self.api_manager.transcribe(url, provider=None)  # Auto-fallback
                return Transcript(
                    video_id=video_id,
                    transcript_text=fallback_result.text,
                    method=fallback_result.provider,
                    language=fallback_result.language,
                    segments=fallback_result.segments,
                    confidence=fallback_result.confidence,
                    processing_time=fallback_result.processing_time,
                    created_at=datetime.now().isoformat()
                )
            except Exception as fallback_error:
                logger.error(f"All transcription providers failed: {fallback_error}")
                raise


class ContextExtractor:
    """Extract context and insights from transcripts using LLM"""

    def __init__(self, llm_provider: str = "gemini"):
        self.llm_provider = llm_provider

    def extract_context(self, transcript: Transcript, metadata: VideoMetadata) -> ContextAnalysis:
        """Extract context using LLM analysis"""
        if not LLM_AVAILABLE:
            logger.warning("LLM not available, returning basic analysis")
            return self._basic_analysis(transcript, metadata)

        prompt = f"""
Analyze this video transcript and provide comprehensive context:

VIDEO TITLE: {metadata.title}
UPLOADER: {metadata.uploader}
TRANSCRIPT:
{transcript.transcript_text[:8000]}  # Limit to avoid token limits

Provide analysis in JSON format with:
1. summary: 2-3 sentence summary
2. key_points: List of 5-7 main points
3. topics: List of topics covered
4. sentiment: Overall sentiment (positive/negative/neutral)
5. actionable_insights: List of actionable takeaways
6. related_concepts: List of related concepts mentioned
"""

        try:
            llm_response = query_llm(prompt, provider=self.llm_provider)
            
            # Parse LLM response (adjust based on your LLM API format)
            if isinstance(llm_response, dict):
                analysis_data = llm_response
            else:
                # Try to extract JSON from text response
                import re
                json_match = re.search(r'\{.*\}', str(llm_response), re.DOTALL)
                if json_match:
                    analysis_data = json.loads(json_match.group())
                else:
                    return self._basic_analysis(transcript, metadata)

            return ContextAnalysis(
                video_id=transcript.video_id,
                summary=analysis_data.get('summary', ''),
                key_points=analysis_data.get('key_points', []),
                topics=analysis_data.get('topics', []),
                sentiment=analysis_data.get('sentiment', 'neutral'),
                actionable_insights=analysis_data.get('actionable_insights', []),
                related_concepts=analysis_data.get('related_concepts', []),
                created_at=datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(f"LLM context extraction failed: {e}")
            return self._basic_analysis(transcript, metadata)

    def _basic_analysis(self, transcript: Transcript, metadata: VideoMetadata) -> ContextAnalysis:
        """Basic analysis without LLM"""
        words = transcript.transcript_text.split()
        word_count = len(words)
        
        return ContextAnalysis(
            video_id=transcript.video_id,
            summary=f"Video transcript with {word_count} words. Title: {metadata.title}",
            key_points=[],
            topics=[],
            sentiment="neutral",
            actionable_insights=[],
            related_concepts=[],
            created_at=datetime.now().isoformat()
        )


# Global instances
db = DatabaseManager(CONFIG["db_path"])
extractor = YouTubeExtractor(CONFIG["audio_dir"])
transcriptor = Transcriptor(CONFIG["transcription_provider"])
context_extractor = ContextExtractor(CONFIG["llm_provider"])


async def process_video(url: str, background_tasks: BackgroundTasks):
    """Process video: extract, transcribe, analyze"""
    try:
        logger.info(f"Processing video: {url}")

        # 1. Extract metadata
        metadata = extractor.get_video_metadata(url)
        db.save_video_metadata(metadata)

        # 2. Transcribe
        transcript = transcriptor.transcribe_video(url, extractor)
        db.save_transcript(transcript)

        # 3. Extract context (if enabled)
        if CONFIG["enable_llm_context"]:
            analysis = context_extractor.extract_context(transcript, metadata)
            db.save_context_analysis(analysis)

        logger.info(f"✅ Successfully processed video: {metadata.video_id}")
        return {
            "status": "success",
            "video_id": metadata.video_id,
            "metadata": asdict(metadata),
            "transcript": asdict(transcript),
            "has_context": CONFIG["enable_llm_context"]
        }

    except Exception as e:
        logger.error(f"Error processing video {url}: {e}")
        raise


# FastAPI Routes

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "operational",
        "service": "Video Transcription Pipeline",
        "version": "1.0.0"
    }


@app.post("/webhook/video")
async def webhook_video(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook endpoint for new video notifications
    
    Expected payload:
    {
        "url": "https://www.youtube.com/watch?v=9EKmaqy9oFE",
        "secret": "your-secret-key"  # Optional, for security
    }
    """
    try:
        data = await request.json()
        url = data.get("url")
        secret = data.get("secret")

        # Verify secret (optional)
        if CONFIG["webhook_secret"] and secret != CONFIG["webhook_secret"]:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

        if not url:
            raise HTTPException(status_code=400, detail="URL is required")

        # Validate YouTube URL
        if "youtube.com" not in url and "youtu.be" not in url:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")

        # Extract video ID
        video_id = extractor.extract_video_id(url)

        # Check if already processed
        existing = db.get_video(video_id)
        if existing:
            transcript = db.get_transcript(video_id)
            context = db.get_context_analysis(video_id)
            return {
                "status": "already_processed",
                "video_id": video_id,
                "transcript_available": transcript is not None,
                "context_available": context is not None
            }

        # Process in background
        background_tasks.add_task(process_video, url, background_tasks)

        return {
            "status": "queued",
            "video_id": video_id,
            "message": "Video queued for processing"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/video/{video_id}")
async def get_video(video_id: str):
    """Get video metadata, transcript, and context"""
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    transcript = db.get_transcript(video_id)
    context = db.get_context_analysis(video_id)

    return {
        "video": video,
        "transcript": transcript,
        "context": context
    }


@app.get("/video/{video_id}/transcript")
async def get_transcript(video_id: str):
    """Get transcript for video"""
    transcript = db.get_transcript(video_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return transcript


@app.get("/video/{video_id}/context")
async def get_context(video_id: str):
    """Get context analysis for video"""
    context = db.get_context_analysis(video_id)
    if not context:
        raise HTTPException(status_code=404, detail="Context analysis not found")
    return context


if __name__ == "__main__":
    # Create necessary directories
    os.makedirs(CONFIG["transcript_dir"], exist_ok=True)
    os.makedirs(CONFIG["audio_dir"], exist_ok=True)

    # Run FastAPI server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level="info"
    )
