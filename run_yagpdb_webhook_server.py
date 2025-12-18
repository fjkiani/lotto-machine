#!/usr/bin/env python3
"""
Run YAGPDB YouTube Webhook Server
==================================

Starts the FastAPI server to receive YAGPDB webhook notifications
and automatically transcribe YouTube videos with AssemblyAI.

Usage:
    python3 run_yagpdb_webhook_server.py

Environment Variables:
    ASSEMBLYAI_API_KEY - AssemblyAI API key (required)
    DISCORD_WEBHOOK_URL - Discord webhook URL for notifications (optional)
    PORT - Server port (default: 8000)
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check required variables
if not os.getenv("ASSEMBLYAI_API_KEY"):
    print("❌ ERROR: ASSEMBLYAI_API_KEY not found in environment")
    print("   Set it in .env file or export it")
    sys.exit(1)

# Import and run server
from webhook_handlers.yagpdb_youtube_handler import app
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    print("🚀 Starting YAGPDB YouTube Webhook Server")
    print("=" * 70)
    print(f"✅ AssemblyAI API Key: {os.getenv('ASSEMBLYAI_API_KEY')[:10]}...")
    print(f"✅ Server: http://{host}:{port}")
    print(f"✅ Webhook Endpoint: http://{host}:{port}/webhook/yagpdb/youtube")
    print("=" * 70)
    print("\n📝 Configure YAGPDB to send webhooks to:")
    print(f"   http://your-server.com/webhook/yagpdb/youtube")
    print("\n🎯 Ready to receive YouTube video notifications!")
    print("   Press Ctrl+C to stop\n")
    
    uvicorn.run(app, host=host, port=port, log_level="info")



