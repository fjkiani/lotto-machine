#!/usr/bin/env python3
"""
Test Discord Transcription Integration (Standalone)
====================================================

Tests the complete flow without Discord.py dependency:
1. Transcribe a YouTube video
2. Format as Discord embed JSON
3. Post to Discord webhook

Usage:
    python3 test_discord_transcription_standalone.py <youtube_url> [discord_webhook_url]
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
import aiohttp
import json
import tempfile
import yt_dlp
import assemblyai as aai
import time

load_dotenv()

async def transcribe_video_standalone(url: str):
    """Transcribe video without Discord dependencies"""
    api_key = os.getenv('ASSEMBLYAI_API_KEY')
    if not api_key:
        return {"success": False, "error": "ASSEMBLYAI_API_KEY not found"}
    
    aai.settings.api_key = api_key
    
    # Extract video ID
    video_id = url.split('v=')[1].split('&')[0] if 'v=' in url else None
    if not video_id:
        return {"success": False, "error": "Invalid YouTube URL"}
    
    try:
        # Download audio
        temp_dir = tempfile.gettempdir()
        temp_base = os.path.join(temp_dir, f'youtube_{video_id}')
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': temp_base + '.%(ext)s',
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            ext = info.get('ext', 'webm')
            audio_file = temp_base + '.' + ext
        
        if not os.path.exists(audio_file):
            return {"success": False, "error": "Failed to download audio"}
        
        # Transcribe
        config = aai.TranscriptionConfig(punctuate=True, language_code='en')
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(audio_file)
        
        max_wait = 300
        wait_time = 0
        while transcript.status != aai.TranscriptStatus.completed:
            if transcript.status == aai.TranscriptStatus.error:
                try:
                    os.unlink(audio_file)
                except:
                    pass
                return {"success": False, "error": f"Transcription failed: {transcript.error}"}
            
            if wait_time >= max_wait:
                try:
                    os.unlink(audio_file)
                except:
                    pass
                return {"success": False, "error": "Transcription timeout"}
            
            time.sleep(2)
            wait_time += 2
            transcript = transcriber.get_by_id(transcript.id)
        
        # Clean up
        try:
            os.unlink(audio_file)
        except:
            pass
        
        return {
            "success": True,
            "video_id": video_id,
            "url": url,
            "transcript": transcript.text,
            "word_count": len(transcript.text.split()),
            "duration": transcript.audio_duration / 1000 if transcript.audio_duration else 0,
            "language": "en"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

async def post_to_discord(embed_data: dict, webhook_url: str):
    """Post embed to Discord webhook"""
    payload = {
        "embeds": [embed_data],
        "content": "🎥 **Test Transcription**"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, json=payload) as response:
            if response.status == 200 or response.status == 204:
                return True, None
            else:
                text = await response.text()
                return False, f"Status {response.status}: {text[:200]}"

async def test_discord_transcription(youtube_url: str, webhook_url: str = None):
    """Test transcription and Discord posting"""
    
    print('=' * 70)
    print('🧪 TESTING DISCORD TRANSCRIPTION INTEGRATION')
    print('=' * 70)
    print(f'\n📹 Video: {youtube_url}')
    
    # Step 1: Transcribe video
    print('\n1️⃣ Transcribing video...')
    print('   (This may take 1-2 minutes...)')
    
    result = await transcribe_video_standalone(youtube_url)
    
    if not result.get('success'):
        print(f'❌ Transcription failed: {result.get("error")}')
        return False
    
    print('✅ Transcription complete!')
    print(f'   Video ID: {result.get("video_id")}')
    print(f'   Duration: {result.get("duration", 0):.1f} minutes')
    print(f'   Word Count: {result.get("word_count", 0):,}')
    
    # Step 2: Format as Discord embed
    print('\n2️⃣ Formatting Discord embed...')
    
    video_id = result.get('video_id', 'Unknown')
    transcript = result.get('transcript', '')
    word_count = result.get('word_count', 0)
    duration = result.get('duration', 0)
    
    embed = {
        "title": "🎥 Video Transcription Complete",
        "description": f"**Video:** [{video_id}]({youtube_url})",
        "color": 65280,  # Green (0x00ff00)
        "fields": [
            {
                "name": "📊 Stats",
                "value": f"**Duration:** {duration:.1f} min\n**Words:** {word_count:,}",
                "inline": True
            },
            {
                "name": "🌐 Language",
                "value": result.get("language", "en").upper(),
                "inline": True
            }
        ],
        "footer": {
            "text": "Alpha Intelligence | Video Transcription Service"
        }
    }
    
    # Add transcript preview
    transcript_preview = transcript[:1000] + "..." if len(transcript) > 1000 else transcript
    embed["fields"].append({
        "name": "📝 Transcript Preview",
        "value": f"```{transcript_preview}```",
        "inline": False
    })
    
    print('✅ Embed formatted!')
    print(f'\n📋 Embed Preview:')
    print(json.dumps(embed, indent=2))
    
    # Step 3: Post to Discord
    if webhook_url:
        print(f'\n3️⃣ Posting to Discord webhook...')
        print(f'   Webhook: {webhook_url[:50]}...')
        
        success, error = await post_to_discord(embed, webhook_url)
        
        if success:
            print('✅ Successfully posted to Discord!')
            print('   Check your Discord channel for the message.')
            return True
        else:
            print(f'❌ Failed to post: {error}')
            return False
    else:
        print('\n⚠️  No webhook URL provided')
        print('\n💡 To post to Discord, provide a webhook URL:')
        print('   python3 test_discord_transcription_standalone.py <url> <webhook_url>')
        print('\n   Or set DISCORD_WEBHOOK_URL in .env')
        return True

async def main():
    if len(sys.argv) < 2:
        print('Usage: python3 test_discord_transcription_standalone.py <youtube_url> [webhook_url]')
        print('\nExample:')
        print('  python3 test_discord_transcription_standalone.py "https://www.youtube.com/watch?v=jNQXAC9IVRw"')
        print('  python3 test_discord_transcription_standalone.py "https://www.youtube.com/watch?v=jNQXAC9IVRw" "https://discord.com/api/webhooks/..."')
        sys.exit(1)
    
    youtube_url = sys.argv[1]
    webhook_url = sys.argv[2] if len(sys.argv) > 2 else os.getenv('DISCORD_WEBHOOK_URL')
    
    success = await test_discord_transcription(youtube_url, webhook_url)
    
    if success:
        print('\n' + '=' * 70)
        print('✅ TEST COMPLETE!')
        print('=' * 70)
    else:
        print('\n' + '=' * 70)
        print('❌ TEST FAILED')
        print('=' * 70)
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())


