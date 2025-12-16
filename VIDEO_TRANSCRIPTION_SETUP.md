# 🎥 Video Transcription Pipeline - Setup Guide

Complete solution for transcribing YouTube videos via webhook triggers with LLM-powered context extraction.

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Core dependencies
pip install fastapi uvicorn python-multipart

# YouTube extraction
pip install yt-dlp

# Transcription (choose one or both)
pip install openai-whisper  # Local transcription
# OR use YouTube captions (no additional install)

# Optional: FFmpeg for audio processing
# macOS: brew install ffmpeg
# Ubuntu: sudo apt-get install ffmpeg
```

### 2. Configure Environment

Create `.env` file:

```bash
# Webhook security
WEBHOOK_SECRET=your-secret-key-here

# Whisper model (tiny/base/small/medium/large)
WHISPER_MODEL=base

# Database path
DB_PATH=video_transcripts.db

# Directories
TRANSCRIPT_DIR=transcripts
AUDIO_DIR=audio_cache

# Video limits
MAX_VIDEO_LENGTH=3600  # 1 hour in seconds

# LLM for context extraction
LLM_PROVIDER=gemini  # or openai, anthropic, etc.
ENABLE_LLM_CONTEXT=true
```

### 3. Start Server

```bash
python3 video_transcription_pipeline.py
```

Server runs on `http://localhost:8000`

---

## 📡 Webhook Integration

### Webhook Endpoint

**POST** `/webhook/video`

### Request Format

```json
{
  "url": "https://www.youtube.com/watch?v=9EKmaqy9oFE",
  "secret": "your-secret-key-here"  // Optional if WEBHOOK_SECRET not set
}
```

### Example: cURL

```bash
curl -X POST http://localhost:8000/webhook/video \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=9EKmaqy9oFE",
    "secret": "your-secret-key-here"
  }'
```

### Example: Python

```python
import requests

webhook_url = "http://localhost:8000/webhook/video"
payload = {
    "url": "https://www.youtube.com/watch?v=9EKmaqy9oFE",
    "secret": "your-secret-key-here"
}

response = requests.post(webhook_url, json=payload)
print(response.json())
```

### Response Format

```json
{
  "status": "queued",
  "video_id": "9EKmaqy9oFE",
  "message": "Video queued for processing"
}
```

---

## 🔍 API Endpoints

### Get Video Data

**GET** `/video/{video_id}`

Returns: metadata, transcript, and context analysis

```bash
curl http://localhost:8000/video/9EKmaqy9oFE
```

### Get Transcript Only

**GET** `/video/{video_id}/transcript`

```bash
curl http://localhost:8000/video/9EKmaqy9oFE/transcript
```

### Get Context Analysis

**GET** `/video/{video_id}/context`

```bash
curl http://localhost:8000/video/9EKmaqy9oFE/context
```

---

## 🏗️ Architecture

```
Webhook Trigger
    ↓
FastAPI Endpoint (/webhook/video)
    ↓
Background Task Queue
    ↓
┌─────────────────────────────────────┐
│ 1. YouTube Extraction (yt-dlp)      │
│    - Extract metadata                │
│    - Download audio                  │
│    - Try YouTube captions            │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 2. Transcription                     │
│    - Method 1: YouTube captions      │
│    - Method 2: Whisper AI (fallback)│
│    - Generate segments + timestamps  │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 3. Context Extraction (LLM)          │
│    - Summary generation              │
│    - Key points extraction            │
│    - Topic identification             │
│    - Sentiment analysis               │
│    - Actionable insights              │
└─────────────────────────────────────┘
    ↓
SQLite Database Storage
    ↓
API Access (/video/{video_id})
```

---

## 📊 Database Schema

### Videos Table
- `video_id` (PRIMARY KEY)
- `url`, `title`, `duration`
- `uploader`, `upload_date`
- `view_count`, `description`

### Transcripts Table
- `id` (PRIMARY KEY)
- `video_id` (FOREIGN KEY)
- `transcript_text`
- `method` (youtube_captions/whisper/hybrid)
- `language`, `segments` (JSON)
- `confidence`, `processing_time`

### Context Analysis Table
- `id` (PRIMARY KEY)
- `video_id` (FOREIGN KEY)
- `summary`, `key_points` (JSON)
- `topics` (JSON), `sentiment`
- `actionable_insights` (JSON)
- `related_concepts` (JSON)

---

## ⚙️ Configuration Options

### Whisper Models

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| tiny | 39MB | Fastest | Basic | Quick testing |
| base | 74MB | Fast | Good | **Recommended** |
| small | 244MB | Medium | Better | Production |
| medium | 769MB | Slow | High | High quality |
| large | 1550MB | Slowest | Best | Maximum accuracy |

### Transcription Methods

1. **YouTube Captions** (if available)
   - Fastest, most accurate
   - Requires captions enabled on video
   - Language-specific

2. **Whisper AI** (fallback)
   - Works for all videos
   - Supports multiple languages
   - Requires audio download + processing

3. **Hybrid** (future)
   - Use captions when available
   - Fallback to Whisper
   - Combine for best accuracy

---

## 🔧 Advanced Usage

### Custom LLM Integration

Modify `ContextExtractor` class to use your LLM:

```python
class ContextExtractor:
    def extract_context(self, transcript, metadata):
        # Your custom LLM call
        prompt = build_custom_prompt(transcript, metadata)
        response = your_llm_client.generate(prompt)
        return parse_response(response)
```

### Batch Processing

Process multiple videos:

```python
import asyncio
import requests

videos = [
    "https://www.youtube.com/watch?v=VIDEO1",
    "https://www.youtube.com/watch?v=VIDEO2",
    "https://www.youtube.com/watch?v=VIDEO3",
]

async def process_batch():
    tasks = []
    for url in videos:
        response = requests.post(
            "http://localhost:8000/webhook/video",
            json={"url": url, "secret": "your-secret"}
        )
        tasks.append(response)
    return await asyncio.gather(*tasks)
```

### Webhook from YouTube

Set up YouTube webhook (requires YouTube API):

1. Create YouTube API project
2. Set up Pub/Sub notifications
3. Forward to your webhook endpoint

---

## 🐛 Troubleshooting

### "yt-dlp not found"
```bash
pip install yt-dlp
```

### "Whisper model failed to load"
- Check FFmpeg installation
- Try smaller model (base instead of large)
- Check disk space

### "Audio download failed"
- Check internet connection
- Verify video is public/accessible
- Check video length (may exceed MAX_VIDEO_LENGTH)

### "LLM context extraction failed"
- Verify LLM API key in environment
- Check API rate limits
- Review LLM provider configuration

---

## 📈 Performance

### Typical Processing Times

| Video Length | Method | Processing Time |
|-------------|--------|-----------------|
| 5 minutes | YouTube captions | ~5 seconds |
| 5 minutes | Whisper base | ~30 seconds |
| 30 minutes | Whisper base | ~3-5 minutes |
| 1 hour | Whisper base | ~10-15 minutes |

### Optimization Tips

1. **Use YouTube captions when available** (10x faster)
2. **Choose appropriate Whisper model** (base is good balance)
3. **Process in background** (already implemented)
4. **Cache transcripts** (database prevents re-processing)
5. **Parallel processing** (queue multiple videos)

---

## 🔐 Security

### Webhook Secret

Always use webhook secret in production:

```python
# In webhook handler
if secret != CONFIG["webhook_secret"]:
    raise HTTPException(401, "Invalid secret")
```

### Rate Limiting

Add rate limiting to prevent abuse:

```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/webhook/video")
@limiter.limit("10/minute")
async def webhook_video(...):
    ...
```

---

## 🚀 Production Deployment

### Docker

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY video_transcription_pipeline.py .

# Run
CMD ["python", "video_transcription_pipeline.py"]
```

### Environment Variables

Set all config via environment variables (see `.env` example above)

### Monitoring

- Log all webhook requests
- Track processing times
- Monitor database size
- Alert on failures

---

## 📝 Example Output

### Transcript Response

```json
{
  "video_id": "9EKmaqy9oFE",
  "transcript_text": "Full transcript text here...",
  "method": "whisper",
  "language": "en",
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "First segment text",
      "confidence": 0.95
    }
  ],
  "confidence": 0.92,
  "processing_time": 45.3
}
```

### Context Analysis Response

```json
{
  "video_id": "9EKmaqy9oFE",
  "summary": "Video discusses X, Y, and Z...",
  "key_points": [
    "Point 1",
    "Point 2",
    "Point 3"
  ],
  "topics": ["topic1", "topic2"],
  "sentiment": "positive",
  "actionable_insights": [
    "Insight 1",
    "Insight 2"
  ],
  "related_concepts": ["concept1", "concept2"]
}
```

---

## 🎯 Next Steps

1. **Set up webhook** from your video source
2. **Configure Whisper model** based on quality/speed needs
3. **Enable LLM context** for rich analysis
4. **Monitor processing** and optimize as needed
5. **Scale horizontally** if processing many videos

---

**Alpha, this pipeline is ready for deployment! 🔥⚡💥**

The system handles:
- ✅ Webhook triggers
- ✅ YouTube video extraction
- ✅ Multiple transcription methods
- ✅ LLM-powered context extraction
- ✅ Database storage
- ✅ API access to results

Just configure your webhook source to POST to `/webhook/video` and you're live! 🚀




