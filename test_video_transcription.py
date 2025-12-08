#!/usr/bin/env python3
"""
Test script for Video Transcription Pipeline

Usage:
    python3 test_video_transcription.py
"""

import requests
import time
import json
from typing import Dict, Any

# Configuration
WEBHOOK_URL = "http://localhost:8000/webhook/video"
API_BASE = "http://localhost:8000"
WEBHOOK_SECRET = "your-secret-key-here"  # Change this!

# Test video
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=9EKmaqy9oFE"


def test_webhook(video_url: str) -> Dict[str, Any]:
    """Test webhook endpoint"""
    print(f"🔥 Testing webhook with video: {video_url}")
    
    payload = {
        "url": video_url,
        "secret": WEBHOOK_SECRET
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ Webhook response: {json.dumps(result, indent=2)}")
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Webhook error: {e}")
        return {"status": "error", "error": str(e)}


def wait_for_processing(video_id: str, max_wait: int = 300) -> Dict[str, Any]:
    """Wait for video processing to complete"""
    print(f"⏳ Waiting for processing: {video_id} (max {max_wait}s)")
    
    start_time = time.time()
    check_interval = 5  # Check every 5 seconds
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{API_BASE}/video/{video_id}", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("transcript"):
                    print(f"✅ Processing complete!")
                    return data
                else:
                    print(f"⏳ Still processing... ({int(time.time() - start_time)}s)")
            elif response.status_code == 404:
                print(f"⏳ Video not found yet, still processing...")
            else:
                print(f"⚠️  Unexpected status: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Error checking status: {e}")
        
        time.sleep(check_interval)
    
    print(f"⏰ Timeout waiting for processing")
    return {"status": "timeout"}


def get_video_data(video_id: str) -> Dict[str, Any]:
    """Get complete video data"""
    print(f"📊 Fetching video data: {video_id}")
    
    try:
        response = requests.get(f"{API_BASE}/video/{video_id}", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Video data retrieved")
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching video data: {e}")
        return {"status": "error", "error": str(e)}


def get_transcript(video_id: str) -> Dict[str, Any]:
    """Get transcript only"""
    print(f"📝 Fetching transcript: {video_id}")
    
    try:
        response = requests.get(f"{API_BASE}/video/{video_id}/transcript", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Transcript retrieved ({len(data.get('transcript_text', ''))} chars)")
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching transcript: {e}")
        return {"status": "error", "error": str(e)}


def get_context(video_id: str) -> Dict[str, Any]:
    """Get context analysis"""
    print(f"🧠 Fetching context analysis: {video_id}")
    
    try:
        response = requests.get(f"{API_BASE}/video/{video_id}/context", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Context analysis retrieved")
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching context: {e}")
        return {"status": "error", "error": str(e)}


def print_summary(video_data: Dict[str, Any]):
    """Print formatted summary"""
    print("\n" + "=" * 80)
    print("📊 VIDEO PROCESSING SUMMARY")
    print("=" * 80)
    
    video = video_data.get("video", {})
    transcript = video_data.get("transcript")
    context = video_data.get("context")
    
    if video:
        print(f"\n🎥 VIDEO METADATA:")
        print(f"  Title: {video.get('title', 'N/A')}")
        print(f"  Uploader: {video.get('uploader', 'N/A')}")
        print(f"  Duration: {video.get('duration', 0)} seconds")
        print(f"  Views: {video.get('view_count', 'N/A')}")
    
    if transcript:
        print(f"\n📝 TRANSCRIPT:")
        print(f"  Method: {transcript.get('method', 'N/A')}")
        print(f"  Language: {transcript.get('language', 'N/A')}")
        print(f"  Length: {len(transcript.get('transcript_text', ''))} characters")
        print(f"  Confidence: {transcript.get('confidence', 0):.2%}")
        print(f"  Processing Time: {transcript.get('processing_time', 0):.1f}s")
        print(f"\n  Preview (first 200 chars):")
        print(f"  {transcript.get('transcript_text', '')[:200]}...")
    
    if context:
        print(f"\n🧠 CONTEXT ANALYSIS:")
        print(f"  Summary: {context.get('summary', 'N/A')[:200]}...")
        print(f"  Sentiment: {context.get('sentiment', 'N/A')}")
        print(f"  Topics: {', '.join(context.get('topics', [])[:5])}")
        print(f"  Key Points: {len(context.get('key_points', []))} points")
        print(f"  Actionable Insights: {len(context.get('actionable_insights', []))} insights")
    
    print("\n" + "=" * 80)


def main():
    """Main test flow"""
    print("🚀 VIDEO TRANSCRIPTION PIPELINE TEST")
    print("=" * 80)
    print(f"Webhook URL: {WEBHOOK_URL}")
    print(f"Test Video: {TEST_VIDEO_URL}")
    print("=" * 80)
    
    # Step 1: Trigger webhook
    webhook_result = test_webhook(TEST_VIDEO_URL)
    
    if webhook_result.get("status") != "queued":
        print(f"❌ Webhook failed or video already processed")
        if webhook_result.get("status") == "already_processed":
            video_id = webhook_result.get("video_id")
        else:
            return
    else:
        video_id = webhook_result.get("video_id")
        print(f"✅ Video queued: {video_id}")
    
    # Step 2: Wait for processing
    if webhook_result.get("status") == "queued":
        video_data = wait_for_processing(video_id, max_wait=600)  # 10 minutes max
    else:
        video_data = get_video_data(video_id)
    
    # Step 3: Get detailed data
    if video_data.get("status") != "timeout":
        complete_data = get_video_data(video_id)
        print_summary(complete_data)
        
        # Step 4: Test individual endpoints
        print("\n🔍 Testing individual endpoints...")
        get_transcript(video_id)
        get_context(video_id)
    else:
        print("⏰ Processing timeout - video may still be processing")
        print(f"   Check status later: GET {API_BASE}/video/{video_id}")
    
    print("\n✅ Test complete!")


if __name__ == "__main__":
    main()
