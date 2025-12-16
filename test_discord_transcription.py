#!/usr/bin/env python3
"""
Test Discord Transcription Integration
======================================

Tests the complete flow:
1. Transcribe a YouTube video
2. Format as Discord embed
3. Post to Discord (via webhook or bot)

Usage:
    python3 test_discord_transcription.py <youtube_url> [discord_webhook_url]
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
import aiohttp
import json

load_dotenv()

# Import the transcription service
sys.path.insert(0, '.')
from discord_bot.services.video_transcription_service import VideoTranscriptionService

async def test_discord_transcription(youtube_url: str, webhook_url: str = None):
    """Test transcription and Discord posting"""
    
    print('=' * 70)
    print('🧪 TESTING DISCORD TRANSCRIPTION INTEGRATION')
    print('=' * 70)
    print(f'\n📹 Video: {youtube_url}')
    
    # Step 1: Transcribe video
    print('\n1️⃣ Transcribing video...')
    print('   (This may take 1-2 minutes...)')
    
    service = VideoTranscriptionService()
    if not service.is_ready():
        print('❌ Transcription service not ready')
        return False
    
    try:
        result = await service.transcribe_video(youtube_url, extract_context=True)
        
        if not result.get('success'):
            print(f'❌ Transcription failed: {result.get("error")}')
            return False
        
        print('✅ Transcription complete!')
        print(f'   Video ID: {result.get("video_id")}')
        print(f'   Duration: {result.get("duration", 0):.1f} minutes')
        print(f'   Word Count: {result.get("word_count", 0):,}')
        
    except Exception as e:
        print(f'❌ Error during transcription: {e}')
        import traceback
        traceback.print_exc()
        return False
    
    # Step 2: Format as Discord embed
    print('\n2️⃣ Formatting Discord embed...')
    
    video_id = result.get('video_id', 'Unknown')
    transcript = result.get('transcript', '')
    word_count = result.get('word_count', 0)
    duration = result.get('duration', 0)
    context = result.get('context', {})
    
    # Create embed (same format as listener)
    embed = {
        "title": "🎥 Video Transcription Complete",
        "description": f"**Video:** [{video_id}]({youtube_url})",
        "color": 0x00ff00,  # Green
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
    
    # Add context analysis if available
    if context.get("analysis"):
        analysis = context["analysis"]
        if len(analysis) > 1000:
            analysis = analysis[:1000] + "..."
        embed["fields"].append({
            "name": "🧠 Context Analysis",
            "value": analysis,
            "inline": False
        })
    
    print('✅ Embed formatted!')
    
    # Step 3: Post to Discord
    print('\n3️⃣ Posting to Discord...')
    
    if webhook_url:
        # Use webhook
        print(f'   Using webhook: {webhook_url[:50]}...')
        
        payload = {
            "embeds": [embed],
            "content": f"🎥 **Test Transcription**\n{youtube_url}"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 200 or response.status == 204:
                        print('✅ Successfully posted to Discord!')
                        print('   Check your Discord channel for the message.')
                        return True
                    else:
                        text = await response.text()
                        print(f'❌ Failed to post: {response.status}')
                        print(f'   Response: {text[:200]}')
                        return False
        except Exception as e:
            print(f'❌ Error posting to Discord: {e}')
            return False
    
    else:
        # Just show what would be posted
        print('⚠️  No webhook URL provided')
        print('\n📋 Discord Embed Preview:')
        print('=' * 70)
        print(json.dumps(embed, indent=2))
        print('=' * 70)
        print('\n💡 To post to Discord, provide a webhook URL:')
        print('   python3 test_discord_transcription.py <url> <webhook_url>')
        return True

async def main():
    if len(sys.argv) < 2:
        print('Usage: python3 test_discord_transcription.py <youtube_url> [webhook_url]')
        print('\nExample:')
        print('  python3 test_discord_transcription.py https://www.youtube.com/watch?v=NFXXrCsRvCo')
        print('  python3 test_discord_transcription.py https://www.youtube.com/watch?v=NFXXrCsRvCo https://discord.com/api/webhooks/...')
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


