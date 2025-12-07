#!/usr/bin/env python3
"""
Alpha Intelligence Discord Bot - Modular Entry Point

This is now a clean entry point that imports from the modular discord_bot package.
All functionality has been moved to organized modules for better maintainability.
"""

import os
import sys
from pathlib import Path

# Add project paths
base_path = Path(__file__).parent
sys.path.insert(0, str(base_path))

from discord_bot.bot import AlphaIntelligenceBot

# Import and setup all command modules
from discord_bot.commands import economic, market, savage, status, tradytics

def setup_commands(bot):
    """Setup all command modules"""
    economic.setup(bot)
    market.setup(bot)
    savage.setup(bot)
    status.setup(bot)
    tradytics.setup(bot)

# Create bot instance and setup commands
bot = AlphaIntelligenceBot()
setup_commands(bot)

def main():
    """Main bot execution"""
    token = os.getenv("DISCORD_BOT_TOKEN")

    if not token:
        print("❌ DISCORD_BOT_TOKEN not found in environment variables!")
        print("Please set DISCORD_BOT_TOKEN in your Railway environment variables")
        sys.exit(1)

    print("🤖 Starting Alpha Intelligence Discord Bot...")
    print("🔥 Loading modular savage LLM integration...")

    try:
        bot.run(token)
    except KeyboardInterrupt:
        print("🛑 Bot shutdown requested")
    except Exception as e:
        print(f"❌ Bot failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

