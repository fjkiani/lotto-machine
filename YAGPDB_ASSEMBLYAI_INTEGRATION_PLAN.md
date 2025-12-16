# 🎥 YAGPDB + AssemblyAI Integration Plan

**Goal:** Automatically transcribe YouTube videos when YAGPDB detects new uploads

---

## 📊 CURRENT SETUP

### **Webhooks:**
1. **YAGPDB Webhook** - Monitors YouTube channels
   - URL: `https://yagpdb.xyz/manage/928797749581840425/youtube`
   - Triggers when: New video published
   - Template variables:
     - `{{.URL}}` - Video URL
     - `{{.VideoID}}` - Video ID
     - `{{.VideoTitle}}` - Title
     - `{{.YoutubeChannelName}}` - Channel name
     - `{{.VideoThumbnail}}` - Thumbnail URL
     - `{{.VideoDescription}}` - Description
     - `{{.VideoDurationSeconds}}` - Duration
     - `{{.IsLiveStream}}` - Is livestream
     - `{{.IsUpcoming}}` - Is scheduled

2. **Discord Webhook** - For sending results back
   - Your Discord webhook URL (for sending transcription results)

---

## 🎯 INTEGRATION FLOW

```
1. YAGPDB detects new YouTube video
   ↓
2. YAGPDB sends webhook to our endpoint
   ↓
3. Our webhook handler receives notification
   ↓
4. Extract video URL from webhook payload
   ↓
5. Use AssemblyAI to transcribe video
   ↓
6. Extract context/analysis using LLM
   ↓
7. Send transcription + analysis to Discord
   (via Discord webhook or bot)
```

---

## 🛠️ IMPLEMENTATION PLAN

### **PHASE 1: YAGPDB Webhook Handler** ⏳

**Build:** FastAPI endpoint to receive YAGPDB notifications

**Endpoint:** `POST /webhook/yagpdb/youtube`

**Expected Payload:**
```json
{
  "ChannelID": "123456789",
  "YoutubeChannelName": "Channel Name",
  "YoutubeChannelID": "UC...",
  "IsLiveStream": false,
  "IsUpcoming": false,
  "VideoID": "9EKmaqy9oFE",
  "VideoTitle": "Video Title",
  "VideoThumbnail": "https://...",
  "VideoDescription": "Description...",
  "VideoDurationSeconds": 600,
  "URL": "https://www.youtube.com/watch?v=9EKmaqy9oFE"
}
```

**Handler Logic:**
1. Receive webhook payload
2. Extract video URL
3. Queue video for transcription
4. Return immediate acknowledgment
5. Process in background

---

### **PHASE 2: AssemblyAI Integration** ✅

**Status:** Already configured!

- ✅ API Key: `139c03eded19410f9e7ee85ece98bffd`
- ✅ Service: `VideoTranscriptionService`
- ✅ Ready to use

**Integration:**
- Use existing `discord_bot/services/video_transcription_service.py`
- Or use `transcription_api_providers.py` directly

---

### **PHASE 3: Discord Notification** ⏳

**Build:** Send transcription results to Discord

**Options:**
1. **Discord Webhook** - Direct webhook POST
2. **Discord Bot** - Use existing bot to send message
3. **Both** - Webhook for quick notification, bot for rich embeds

**Message Format:**
```
🎥 New Video Transcribed: {{.VideoTitle}}
📺 Channel: {{.YoutubeChannelName}}
🔗 URL: {{.URL}}

📝 Transcript Preview:
[First 1000 characters...]

🧠 Context Analysis:
- Summary: ...
- Key Points: ...
- Topics: ...
- Sentiment: ...
```

---

## 📋 FILES TO CREATE

### **1. YAGPDB Webhook Handler**
**File:** `webhook_handlers/yagpdb_youtube.py`

**Features:**
- Receive YAGPDB webhook
- Parse payload
- Extract video URL
- Queue for transcription
- Handle errors gracefully

### **2. Discord Notifier**
**File:** `webhook_handlers/discord_notifier.py`

**Features:**
- Send formatted messages to Discord
- Support webhook and bot methods
- Rich embeds with transcription
- Error handling

### **3. Main Webhook Server**
**File:** `webhook_server.py`

**Features:**
- FastAPI server
- YAGPDB endpoint
- Health checks
- Background processing
- Queue management

---

## 🚀 QUICK START

### **Step 1: Create Webhook Handler**

```python
# webhook_handlers/yagpdb_youtube.py
from fastapi import FastAPI, Request, BackgroundTasks
from discord_bot.services.video_transcription_service import VideoTranscriptionService
from webhook_handlers.discord_notifier import DiscordNotifier

app = FastAPI()
transcription_service = VideoTranscriptionService()
discord_notifier = DiscordNotifier()

@app.post("/webhook/yagpdb/youtube")
async def handle_yagpdb_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle YAGPDB YouTube webhook"""
    data = await request.json()
    
    # Extract video details
    video_url = data.get("URL")
    video_id = data.get("VideoID")
    video_title = data.get("VideoTitle")
    channel_name = data.get("YoutubeChannelName")
    
    # Queue for processing
    background_tasks.add_task(
        process_video_transcription,
        video_url,
        video_id,
        video_title,
        channel_name
    )
    
    return {"status": "queued", "video_id": video_id}

async def process_video_transcription(url, video_id, title, channel):
    """Process video transcription in background"""
    # Transcribe
    result = await transcription_service.transcribe_video(url)
    
    # Send to Discord
    await discord_notifier.send_transcription(
        video_id=video_id,
        title=title,
        channel=channel,
        transcription_result=result
    )
```

### **Step 2: Configure YAGPDB**

In YAGPDB dashboard:
1. Go to YouTube notifications
2. Set webhook URL: `https://your-server.com/webhook/yagpdb/youtube`
3. Configure announcement message (optional)
4. Save

### **Step 3: Deploy**

```bash
# Run webhook server
python3 webhook_server.py
```

---

## 📊 COMPLETE FLOW DIAGRAM

```
┌─────────────────┐
│  YouTube Video  │
│     Uploaded    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  YAGPDB Detects │
│   New Video     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  YAGPDB Sends   │
│    Webhook      │
│  (with URL, etc)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Our Webhook    │
│    Handler      │
│  Receives Data  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Queue Video    │
│  for Processing │
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
│  Send to Discord│
│  (Webhook/Bot)  │
└─────────────────┘
```

---

## 🎯 WHERE ASSEMBLYAI FITS

**AssemblyAI is the transcription engine:**

1. **Receives:** YouTube URL from YAGPDB webhook
2. **Processes:** Transcribes video (no download needed!)
3. **Returns:** Full transcript + segments + metadata
4. **Feeds:** LLM for context extraction
5. **Outputs:** Formatted message to Discord

**Key Advantage:**
- ✅ Direct URL transcription (no video download)
- ✅ Fast processing
- ✅ High accuracy
- ✅ Already configured and ready!

---

## 🔧 CONFIGURATION

### **Environment Variables**

```bash
# AssemblyAI (already set)
ASSEMBLYAI_API_KEY=139c03eded19410f9e7ee85ece98bffd

# Discord Webhook (add this)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Webhook Server
WEBHOOK_SECRET=your-secret-key
PORT=8000
```

### **YAGPDB Configuration**

**Webhook URL:** `https://your-server.com/webhook/yagpdb/youtube`

**Custom Announcement (Optional):**
```
{{.YoutubeChannelName}} published a new video! {{.URL}}
(Transcription processing...)
```

---

## 📝 NEXT STEPS

1. **Create webhook handler** - Receive YAGPDB notifications
2. **Integrate AssemblyAI** - Use existing service
3. **Build Discord notifier** - Send results to Discord
4. **Deploy webhook server** - Make it accessible
5. **Configure YAGPDB** - Point to your webhook URL
6. **Test end-to-end** - Post a video and verify flow

---

**STATUS: READY TO BUILD** 🚀💥

Let me know when you want me to start building the webhook handler!
