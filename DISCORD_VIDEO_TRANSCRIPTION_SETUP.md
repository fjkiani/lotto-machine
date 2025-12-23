# 🎥 Discord Bot Video Transcription Setup

**AssemblyAI integration for automatic YouTube video transcription in Discord!**

---

## 🚀 Quick Setup

### 1. Install AssemblyAI

```bash
pip install assemblyai
```

### 2. Set Environment Variable

```bash
export ASSEMBLYAI_API_KEY=your-api-key-here
```

Get your API key from: https://www.assemblyai.com/

### 3. Restart Discord Bot

The bot will automatically:
- Detect YouTube URLs in messages
- Transcribe videos automatically
- Send transcription + analysis to Discord

---

## 🎯 How It Works

### Automatic Detection

When someone posts a YouTube URL in Discord:

```
User: Check this out! https://www.youtube.com/watch?v=VIDEO_ID
```

The bot automatically:
1. ✅ Detects the YouTube URL
2. ✅ Transcribes the video (no download needed!)
3. ✅ Extracts context and insights
4. ✅ Sends formatted response with:
   - Full transcript preview
   - Key points
   - Topics covered
   - Sentiment analysis
   - Actionable insights

### Manual Commands

You can also use the agent tool:

```
/alpha transcribe https://www.youtube.com/watch?v=VIDEO_ID
```

Or ask naturally:

```
/alpha analyze this video: https://www.youtube.com/watch?v=VIDEO_ID
```

---

## 📊 Features

### ✅ Automatic Processing
- Detects YouTube URLs in any message
- Processes in background
- Sends results when complete

### ✅ Rich Context Analysis
- Summary generation
- Key points extraction
- Topic identification
- Sentiment analysis
- Actionable insights

### ✅ Discord-Friendly Format
- Beautiful embeds
- Formatted transcripts
- Easy to read analysis
- Timestamped segments

---

## 🔧 Configuration

### Environment Variables

```bash
# Required
ASSEMBLYAI_API_KEY=your-key-here

# Optional (for context extraction)
GEMINI_API_KEY=your-key-here  # For LLM analysis
```

### Pricing

**AssemblyAI:**
- Free tier: 5 hours/month
- Paid: $0.015/minute (~$0.90/hour)

**Recommendation:** Start with free tier, upgrade if needed.

---

## 🎯 Example Output

When a YouTube URL is detected, the bot sends:

```
🎥 Video Transcription Complete
Video: [VIDEO_ID](https://youtube.com/watch?v=...)

📊 Stats
Duration: 10.5 min | Words: 1,234

📝 Transcript Preview
[First 1000 characters of transcript...]

🧠 Context Analysis
Summary: This video discusses...
Key Points:
• Point 1
• Point 2
• Point 3
...
```

---

## 🐛 Troubleshooting

### "Video transcription service not available"
- Check `ASSEMBLYAI_API_KEY` is set
- Verify API key is valid
- Check AssemblyAI account status

### "Transcription failed"
- Video may be private/restricted
- Video may be too long (check limits)
- Network issues

### "No YouTube URL found"
- Ensure URL format is correct
- Check message contains valid YouTube link

---

## 🚀 Advanced Usage

### Custom Analysis

The bot uses your existing LLM service for context extraction. To customize:

1. Edit `discord_bot/services/video_transcription_service.py`
2. Modify `_extract_context()` method
3. Adjust prompt for your needs

### Rate Limiting

AssemblyAI has rate limits. The bot handles:
- Automatic retries
- Error messages
- Graceful degradation

---

## 📝 Integration Details

### Files Created

1. **`discord_bot/services/video_transcription_service.py`**
   - AssemblyAI integration
   - Transcription logic
   - Context extraction

2. **`discord_bot/agents/tools/video_transcription.py`**
   - Agent tool for manual transcription
   - Query matching
   - Response formatting

3. **`discord_bot/integrations/video_transcription/listener.py`**
   - Automatic URL detection
   - Message processing
   - Discord embed creation

### Bot Integration

The bot automatically:
- ✅ Listens for YouTube URLs
- ✅ Processes transcriptions
- ✅ Sends formatted responses
- ✅ Handles errors gracefully

---

## 🎯 Next Steps

1. **Get AssemblyAI API key** (free tier available)
2. **Set environment variable**
3. **Restart Discord bot**
4. **Test with a YouTube URL!**

**Alpha, the bot is ready to transcribe videos automatically! 🔥⚡💥**

Just post a YouTube URL and watch it work! 🚀






