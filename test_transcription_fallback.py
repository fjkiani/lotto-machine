#!/usr/bin/env python3
"""
Test Transcription with Download Fallback
==========================================
"""

import asyncio
import os
import sys
import tempfile
from dotenv import load_dotenv

load_dotenv()

# Test AssemblyAI with download fallback
import assemblyai as aai
import yt_dlp

api_key = os.getenv('ASSEMBLYAI_API_KEY')
if not api_key:
    print('❌ ASSEMBLYAI_API_KEY not found')
    sys.exit(1)

aai.settings.api_key = api_key

print('🧪 Testing Transcription with Download Fallback')
print('=' * 70)
print(f'✅ API Key: {api_key[:10]}...{api_key[-10:]}')
print(f'✅ yt-dlp installed: {yt_dlp is not None}')

# Test video
test_url = 'https://www.youtube.com/watch?v=jNQXAC9IVRw'
print(f'\n🎥 Testing with: {test_url}')
print('   Step 1: Downloading audio...')

try:
    # Step 1: Download audio
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
        temp_path = tmp_file.name
    
    # Try without conversion first (native format)
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': temp_path.replace('.wav', ''),
        'quiet': True,
        'no_warnings': True,
    }
    
    # Only add conversion if ffmpeg is available
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=2)
        if result.returncode == 0:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }]
            print('   Using ffmpeg for conversion')
        else:
            print('   Using native audio format (no ffmpeg)')
    except:
        print('   Using native audio format (no ffmpeg)')
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([test_url])
    
    # Find the actual file
    audio_file = None
    base_path = temp_path.replace('.wav', '')
    for ext in ['.wav', '.m4a', '.mp3', '.webm', '.opus']:
        if os.path.exists(base_path + ext):
            audio_file = base_path + ext
            break
    
    if not audio_file:
        print('❌ Failed to download audio file')
        sys.exit(1)
    
    print(f'   ✅ Audio downloaded: {audio_file}')
    file_size = os.path.getsize(audio_file) / 1024  # KB
    print(f'   ✅ File size: {file_size:.1f} KB')
    
    # Step 2: Transcribe
    print('\n   Step 2: Transcribing with AssemblyAI...')
    
    config = aai.TranscriptionConfig(
        punctuate=True,
        speaker_labels=False,
        language_code='en'
    )
    
    transcriber = aai.Transcriber(config=config)
    transcript = transcriber.transcribe(audio_file)
    
    print(f'   Status: {transcript.status}')
    print('   Waiting for completion...')
    
    import time
    max_wait = 300
    wait_time = 0
    
    while transcript.status != aai.TranscriptStatus.completed:
        if transcript.status == aai.TranscriptStatus.error:
            print(f'\n❌ Transcription failed: {transcript.error}')
            try:
                os.unlink(audio_file)
            except:
                pass
            sys.exit(1)
        
        if wait_time >= max_wait:
            print(f'\n❌ Timeout after {max_wait} seconds')
            try:
                os.unlink(audio_file)
            except:
                pass
            sys.exit(1)
        
        time.sleep(2)
        wait_time += 2
        transcript = transcriber.get_by_id(transcript.id)
        if wait_time % 10 == 0:
            print(f'   Processing... ({wait_time}s)')
    
    # Clean up
    try:
        os.unlink(audio_file)
    except:
        pass
    
    print(f'\n✅ TRANSCRIPTION SUCCESSFUL!')
    print(f'   Duration: {transcript.audio_duration / 1000 if transcript.audio_duration else 0:.1f} seconds')
    print(f'   Word Count: {len(transcript.text.split())}')
    print(f'   Language: {transcript.language_code}')
    print(f'\n📝 Transcript Preview:')
    print(f'   {transcript.text[:300]}...')
    print('\n🎯 FIX WORKS! Download fallback is working!')
    print('✅ Ready for YAGPDB integration!')
    
except Exception as e:
    print(f'\n❌ Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
