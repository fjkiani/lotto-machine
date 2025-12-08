#!/usr/bin/env python3
"""
Alpha Intelligence Discord Bot - Main Bot Class

Core bot setup, event handling, and orchestration.
"""

import discord
from discord import app_commands
import os
import logging
import sys
from pathlib import Path

# Add project paths
base_path = Path(__file__).parent.parent
sys.path.insert(0, str(base_path))

from .services.savage_llm_service import SavageLLMService
from .integrations.tradytics.listener import TradyticsListener

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class AlphaIntelligenceBot(discord.Client):
    """
    Alpha Intelligence Discord Bot with Savage LLM Integration

    Features:
    - Slash commands for financial analysis
    - Autonomous Tradytics integration (listens to bot alerts)
    - Multiple savagery levels
    - Error handling and user feedback
    - Railway deployment ready
    """

    def __init__(self):
        # Enable required intents
        intents = discord.Intents.default()
        intents.message_content = True  # For command processing

        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

        # Initialize services
        self.savage_llm = SavageLLMService()
        self.tradytics_listener = TradyticsListener(self)

        # Bot status
        self.ready = False

    async def setup_hook(self):
        """Setup slash commands on startup"""
        try:
            # Import and register all commands
            from .commands import (
                economic, market, savage, status, tradytics
            )

            # Commands are registered via decorators in their modules
            # Just sync them here
            await self.tree.sync()
            logger.info("✅ Discord slash commands synced!")

            # Check LLM service
            if self.savage_llm.is_ready():
                self.ready = True
                logger.info("✅ Savage LLM service ready!")
                await self.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.watching,
                        name="markets with savage intelligence"
                    )
                )
            else:
                logger.error("❌ Savage LLM service not ready")
                await self.change_presence(
                    activity=discord.Activity(name="Savage LLM initializing...")
                )

        except Exception as e:
            logger.error(f"❌ Setup error: {e}")

    async def on_message(self, message):
        """Handle incoming messages"""
        # Don't respond to own messages
        if message.author == self.user:
            return

        # Let Tradytics listener handle autonomous processing
        await self.tradytics_listener.process_message(message)

    async def on_ready(self):
        """Called when bot connects to Discord"""
        logger.info(f'🤖 {self.user} has connected to Discord!')
        logger.info(f'📊 Connected to {len(self.guilds)} servers')

        if self.ready:
            logger.info('🔥 Alpha Intelligence Bot ready to savage the markets!')
        else:
            logger.warning('⚠️ Bot connected but savage LLM not ready')

