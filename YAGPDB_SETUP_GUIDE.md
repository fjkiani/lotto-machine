# 🎥 YAGPDB + AssemblyAI Setup Guide

**Complete setup for automatic YouTube video transcription via YAGPDB webhooks**

---

## 📊 ARCHITECTURE

```
┌─────────────────┐
│  YouTube Video  │
│     Uploaded    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  YAGPDB Monitors│
│  YouTube Channel│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  YAGPDB Sends   │
│  Webhook to Our │
│     Server      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Our Server     │
│  Receives &     │
│  Queues Video   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  AssemblyAI     │
│  Transcribes    │
│     Video       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM Extracts   │
│    Context      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Send Results   │
│  to Discord     │
│  (Webhook/Bot)  │
└─────────────────┘
```

---

## 🚀 QUICK SETUP

### **Step 1: Install Dependencies**

```bash
# Activate virtual environment
source venv/bin/activate

# Install required packages
pip install fastapi uvicorn aiohttp python-dotenv
```

### **Step 2: Configure Environment**

Add to `.env` file:

```bash
# AssemblyAI (already set)
ASSEMBLYAI_API_KEY=139c03eded19410f9e7ee85ece98bffd

# Discord Webhook (for sending results)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN

# Server Configuration (optional)
PORT=8000
HOST=0.0.0.0
```

### **Step 3: Start Webhook Server**

```bash
python3 run_yagpdb_webhook_server.py
```

**Expected Output:**
```
🚀 Starting YAGPDB YouTube Webhook Server
======================================================================
✅ AssemblyAI API Key: 139c03eded...
✅ Server: http://0.0.0.0:8000
✅ Webhook Endpoint: http://0.0.0.0:8000/webhook/yagpdb/youtube
======================================================================

📝 Configure YAGPDB to send webhooks to:
   http://your-server.com/webhook/yagpdb/youtube

🎯 Ready to receive YouTube video notifications!
```

### **Step 4: Configure YAGPDB**

1. Go to YAGPDB dashboard: https://yagpdb.xyz/manage/928797749581840425/youtube
2. Set **Webhook URL** to: `http://your-server.com/webhook/yagpdb/youtube`
3. Configure announcement message (optional):
   ```
   {{.YoutubeChannelName}} published a new video! {{.URL}}
   (Transcription processing...)
   ```
4. Save configuration

---

## 📋 WEBHOOK PAYLOAD FORMAT

YAGPDB sends the following data:

```json
{
  "ChannelID": "123456789",
  "YoutubeChannelName": "Channel Name",
  "YoutubeChannelID": "UC...",
  "VideoID": "9EKmaqy9oFE",
  "VideoTitle": "Video Title",
  "VideoThumbnail": "https://i.ytimg.com/vi/.../maxresdefault.jpg",
  "VideoDescription": "Video description...",
  "VideoDurationSeconds": 600,
  "URL": "https://www.youtube.com/watch?v=9EKmaqy9oFE",
  "IsLiveStream": false,
  "IsUpcoming": false
}
```

---

## 🎯 HOW IT WORKS

### **1. YAGPDB Detects New Video**
- YAGPDB monitors configured YouTube channels
- When new video is published, it triggers webhook

### **2. Our Server Receives Webhook**
- FastAPI endpoint receives POST request
- Parses video data from payload
- Validates video URL

### **3. Video Queued for Processing**
- Video added to background task queue
- Server immediately returns acknowledgment
- Processing happens asynchronously

### **4. AssemblyAI Transcription**
- Video URL sent to AssemblyAI
- No download needed - direct URL transcription!
- Returns full transcript + segments

### **5. Context Extraction**
- LLM analyzes transcript
- Extracts: summary, key points, topics, sentiment
- Generates actionable insights

### **6. Discord Notification**
- Formatted message sent to Discord webhook
- Includes: transcript preview, context analysis
- Rich embed with video details

---

## 🔧 CONFIGURATION OPTIONS

### **Skip Livestreams**

By default, livestreams are skipped. To process them:

Edit `webhook_handlers/yagpdb_youtube_handler.py`:
```python
# Remove this check:
if video_data.get('is_live_stream'):
    return {"status": "skipped", "reason": "livestream"}
```

### **Skip Upcoming Videos**

By default, scheduled videos are skipped. To process them:

Edit `webhook_handlers/yagpdb_youtube_handler.py`:
```python
# Remove this check:
if video_data.get('is_upcoming'):
    return {"status": "skipped", "reason": "upcoming"}
```

### **Custom Discord Message Format**

Edit `_send_discord_notification()` method in `yagpdb_youtube_handler.py` to customize the Discord embed format.

---

## 🧪 TESTING

### **Test Webhook Endpoint**

```bash
curl -X POST http://localhost:8000/webhook/yagpdb/youtube \
  -H "Content-Type: application/json" \
  -d '{
    "ChannelID": "123456789",
    "YoutubeChannelName": "Test Channel",
    "VideoID": "9EKmaqy9oFE",
    "VideoTitle": "Test Video",
    "URL": "https://www.youtube.com/watch?v=9EKmaqy9oFE",
    "IsLiveStream": false,
    "IsUpcoming": false
  }'
```

**Expected Response:**
```json
{
  "status": "queued",
  "video_id": "9EKmaqy9oFE",
  "message": "Video queued for transcription"
}
```

### **Check Health**

```bash
curl http://localhost:8000/
```

**Expected Response:**
```json
{
  "status": "operational",
  "service": "YAGPDB YouTube Webhook Handler",
  "transcription_ready": true
}
```

---

## 📊 DISCORD OUTPUT FORMAT

When a video is transcribed, Discord receives:

```
🎥 Video Transcribed: [Video Title]
Channel: [Channel Name]
Duration: 10.5 min | Words: 1,234

📝 Transcript Preview:
[First 1000 characters of transcript...]

🧠 Context Analysis:
- Summary: [2-3 sentence summary]
- Key Points: [5-7 main points]
- Topics: [Topics covered]
- Sentiment: [positive/negative/neutral]
- Actionable Insights: [3-5 takeaways]
```

---

## 🐛 TROUBLESHOOTING

### **"Video transcription service not ready"**
- ✅ Check `ASSEMBLYAI_API_KEY` is set in `.env`
- ✅ Verify API key is valid
- ✅ Check AssemblyAI account status

### **"No Discord webhook URL configured"**
- ✅ Set `DISCORD_WEBHOOK_URL` in `.env`
- ✅ Verify webhook URL is valid
- ✅ Check webhook permissions

### **"Webhook error: Invalid video URL"**
- ✅ Check YAGPDB payload format
- ✅ Verify `URL` field is present
- ✅ Ensure URL is valid YouTube URL

### **"Transcription failed"**
- Video may be private/restricted
- Video may be too long (check AssemblyAI limits)
- Network issues
- Check AssemblyAI account quota

---

## 🚀 DEPLOYMENT

### **Local Development**

```bash
python3 run_yagpdb_webhook_server.py
```

### **Production Deployment**

**Option 1: Using systemd**

Create `/etc/systemd/system/yagpdb-webhook.service`:
```ini
[Unit]
Description=YAGPDB YouTube Webhook Handler
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python run_yagpdb_webhook_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Option 2: Using Docker**

Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "run_yagpdb_webhook_server.py"]
```

**Option 3: Using Cloud Services**

- **Heroku**: Deploy as web dyno
- **Railway**: Deploy as web service
- **Render**: Deploy as web service
- **Fly.io**: Deploy as app

---

## 📝 FILES CREATED

1. **`webhook_handlers/yagpdb_youtube_handler.py`** - Main webhook handler
2. **`webhook_handlers/__init__.py`** - Package init
3. **`run_yagpdb_webhook_server.py`** - Server runner script
4. **`YAGPDB_ASSEMBLYAI_INTEGRATION_PLAN.md`** - Integration plan
5. **`YAGPDB_SETUP_GUIDE.md`** - This file

---

## ✅ STATUS

**Ready to deploy!**

- ✅ AssemblyAI configured
- ✅ Webhook handler built
- ✅ Discord integration ready
- ✅ Background processing implemented
- ✅ Error handling in place

**Next Steps:**
1. Set `DISCORD_WEBHOOK_URL` in `.env`
2. Start webhook server
3. Configure YAGPDB webhook URL
4. Test with a new video upload!

---

**Last Updated:** 2025-12-11
**Status:** ✅ READY TO USE




