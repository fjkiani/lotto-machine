#!/usr/bin/env python3
"""
📊 SUNDAY RECAP RUNNER
Generates and sends Sunday market recap to Discord
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add paths
base_path = Path(__file__).parent
sys.path.insert(0, str(base_path))

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def send_to_discord(message: str):
    """Send message to Discord webhook (splits if too long)"""
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    
    if not webhook_url:
        logger.warning("⚠️  DISCORD_WEBHOOK_URL not set - printing to console")
        print("\n" + "="*70)
        print(message)
        print("="*70 + "\n")
        return
    
    try:
        import requests
        import time
        
        # Discord has 2000 char limit - split if needed
        MAX_LENGTH = 1900  # Leave some buffer
        
        # Split message into chunks
        chunks = []
        if len(message) > MAX_LENGTH:
            # Split on double newlines (paragraph breaks)
            sections = message.split("\n\n")
            current_chunk = ""
            
            for section in sections:
                if len(current_chunk) + len(section) + 2 > MAX_LENGTH:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = section
                else:
                    current_chunk += "\n\n" + section if current_chunk else section
            
            if current_chunk:
                chunks.append(current_chunk.strip())
        else:
            chunks = [message]
        
        # Send each chunk
        success = True
        for i, chunk in enumerate(chunks):
            payload = {
                "content": chunk,
                "username": "Alpha Intelligence - Sunday Recap"
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code != 204:
                logger.warning(f"⚠️  Discord webhook returned {response.status_code} for chunk {i+1}")
                success = False
            
            # Small delay between chunks to avoid rate limit
            if len(chunks) > 1 and i < len(chunks) - 1:
                time.sleep(0.5)
        
        if success:
            logger.info(f"✅ Sunday recap sent to Discord ({len(chunks)} message(s))")
        else:
            print("\n" + "="*70)
            print(message)
            print("="*70 + "\n")
    
    except Exception as e:
        logger.error(f"❌ Failed to send to Discord: {e}")
        print("\n" + "="*70)
        print(message)
        print("="*70 + "\n")


def main():
    """Main function"""
    logger.info("📊 Starting Sunday Recap...")
    
    try:
        from live_monitoring.recaps import SundayRecap
        
        recap = SundayRecap()
        result = recap.generate_recap()
        
        if result is None:
            logger.warning("⚠️  No meaningful content - recap not sent")
            print("\n" + "="*70)
            print("⚠️  SUNDAY RECAP: No meaningful content found")
            print("="*70)
            print("\nThe recap was not sent because:")
            print("  • No DP level interactions")
            print("  • No economic events")
            print("  • No narrative data")
            print("  • No signals generated")
            print("  • No upcoming events")
            print("\nThis is normal if:")
            print("  • System just started (no historical data yet)")
            print("  • No trading activity last week")
            print("  • APIs rate-limited")
            print("="*70 + "\n")
            return
        
        # Send to Discord
        send_to_discord(result.formatted_message)
        
        logger.info("✅ Sunday recap complete!")
        
    except Exception as e:
        logger.error(f"❌ Error generating recap: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

