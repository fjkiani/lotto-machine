#!/usr/bin/env python3
"""
ALPHA INTELLIGENCE DISCORD BOT - SAVAGE LLM INTEGRATION

Features:
- Slash commands for savage LLM queries
- Economic, market, and custom analysis
- Multiple savagery levels
- Error handling and rate limiting
- Integration with Railway deployment

Commands:
/economic [query] - Get savage economic analysis
/market [query] - Get savage market analysis
/savage <level> <query> - Custom savagery level analysis
"""

import discord
from discord import app_commands
import os
import logging
import sys
from pathlib import Path

# Add project paths
base_path = Path(__file__).parent
sys.path.insert(0, str(base_path))

from services.savage_llm_service import SavageLLMService

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

        # Initialize savage LLM service
        self.savage_llm = SavageLLMService()

        # Bot status
        self.ready = False

    async def setup_hook(self):
        """Setup slash commands on startup"""
        try:
            # Sync commands with Discord
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

    async def on_ready(self):
        """Called when bot connects to Discord"""
        logger.info(f'🤖 {self.user} has connected to Discord!')
        logger.info(f'📊 Connected to {len(self.guilds)} servers')

        if self.ready:
            logger.info('🔥 Alpha Intelligence Bot ready to savage the markets!')
        else:
            logger.warning('⚠️ Bot connected but savage LLM not ready')

# Create bot instance
bot = AlphaIntelligenceBot()

# ===============================
# SLASH COMMANDS
# ===============================

@bot.tree.command(name="economic", description="Get savage economic analysis from Alpha Intelligence")
@app_commands.describe(query="Your economic question (optional)")
async def economic_command(interaction: discord.Interaction, query: str = "whats the economic update today"):
    """
    Get savage economic analysis
    Uses chained_pro level for maximum brutality
    """
    await interaction.response.defer()  # Shows "thinking..." message

    if not bot.ready:
        await interaction.followup.send("❌ Savage system initializing... Try again in a moment.")
        return

    try:
        logger.info(f"📊 Economic query from {interaction.user}: {query[:50]}...")

        # Get savage response
        response = await bot.savage_llm.get_savage_response(
            f"Economic Intelligence Query: {query}",
            level="chained_pro"
        )

        if response.get("status") == "error":
            await interaction.followup.send(f"❌ {response['error']}")
            return

        # Handle long responses (Discord 2000 char limit)
        message = response['response']
        if len(message) > 1900:
            # Split into chunks with part indicators
            chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
            for i, chunk in enumerate(chunks):
                part_header = f"📊 **Economic Analysis - Part {i+1}/{len(chunks)}**\n\n"
                await interaction.followup.send(f"{part_header}{chunk}")
        else:
            await interaction.followup.send(f"📊 **Economic Analysis**\n\n{message}")

        logger.info(f"✅ Economic response sent to {interaction.user}")

    except Exception as e:
        logger.error(f"Economic command error: {e}")
        await interaction.followup.send("❌ The economic battlefield is too volatile right now. Try again later.")

@bot.tree.command(name="market", description="Get savage market analysis from Alpha Intelligence")
@app_commands.describe(query="Your market question (optional)")
async def market_command(interaction: discord.Interaction, query: str = "whats happening in the market"):
    """
    Get savage market analysis
    Uses chained_pro level for GODLIKE insights
    """
    await interaction.response.defer()

    if not bot.ready:
        await interaction.followup.send("❌ Savage market intelligence offline. System rebooting...")
        return

    try:
        logger.info(f"📈 Market query from {interaction.user}: {query[:50]}...")

        response = await bot.savage_llm.get_savage_response(
            f"Market Intelligence Query: {query}",
            level="chained_pro"
        )

        if response.get("status") == "error":
            await interaction.followup.send(f"❌ {response['error']}")
            return

        message = response['response']
        if len(message) > 1900:
            chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
            for i, chunk in enumerate(chunks):
                part_header = f"📈 **Market Analysis - Part {i+1}/{len(chunks)}**\n\n"
                await interaction.followup.send(f"{part_header}{chunk}")
        else:
            await interaction.followup.send(f"📈 **Market Analysis**\n\n{message}")

        logger.info(f"✅ Market response sent to {interaction.user}")

    except Exception as e:
        logger.error(f"Market command error: {e}")
        await interaction.followup.send("❌ Market analysis failed. The algorithms are fighting back!")

@bot.tree.command(name="savage", description="Custom savagery level analysis from Alpha Intelligence")
@app_commands.describe(
    level="Choose your savagery level",
    query="Your question for the savage intelligence"
)
@app_commands.choices(level=[
    app_commands.Choice(name="🐺 Basic Savage (4K chars)", value="basic"),
    app_commands.Choice(name="⚔️ Alpha Warrior (3K chars)", value="alpha_warrior"),
    app_commands.Choice(name="🔥 Maximum Savage (5K chars)", value="full_savage"),
    app_commands.Choice(name="👹 GODLIKE Savage (8K chars)", value="chained_pro"),
])
async def savage_command(interaction: discord.Interaction, level: str, query: str):
    """
    Custom savagery level analysis
    Allows users to choose their preferred brutality level
    """
    await interaction.response.defer()

    if not bot.ready:
        await interaction.followup.send("❌ Savage intelligence core offline. Rebooting quantum matrix...")
        return

    try:
        logger.info(f"🔥 Custom savage query from {interaction.user}: level={level}, query='{query[:50]}...'")

        response = await bot.savage_llm.get_savage_response(query, level)

        if response.get("status") == "error":
            await interaction.followup.send(f"❌ {response['error']}")
            return

        # Level display names
        level_names = {
            "basic": "🐺 Basic Savage",
            "alpha_warrior": "⚔️ Alpha Warrior",
            "full_savage": "🔥 Maximum Savage",
            "chained_pro": "👹 GODLIKE Savage"
        }

        message = response['response']
        if len(message) > 1900:
            chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
            for i, chunk in enumerate(chunks):
                part_header = f"{level_names[level]} **Part {i+1}/{len(chunks)}**\n\n"
                await interaction.followup.send(f"{part_header}{chunk}")
        else:
            await interaction.followup.send(f"{level_names[level]}\n\n{message}")

        logger.info(f"✅ Custom savage response sent to {interaction.user} at level {level}")

    except Exception as e:
        logger.error(f"Savage command error: {e}")
        await interaction.followup.send("❌ Savagery level containment breach! The AI is fighting back.")

@bot.tree.command(name="status", description="Check Alpha Intelligence system status")
async def status_command(interaction: discord.Interaction):
    """Check the status of all Alpha Intelligence systems"""
    try:
        embed = discord.Embed(
            title="🤖 Alpha Intelligence Status",
            color=0x00ff00 if bot.ready else 0xff0000,
            timestamp=interaction.created_at
        )

        # LLM Service Status
        llm_stats = bot.savage_llm.get_stats()
        embed.add_field(
            name="🔥 Savage LLM",
            value="✅ Ready" if llm_stats['ready'] else "❌ Offline",
            inline=True
        )

        # Available Levels
        levels = bot.savage_llm.get_available_levels()
        level_list = [f"• {name}: {desc.split(' - ')[0]}" for name, desc in levels.items()]
        embed.add_field(
            name="🎯 Available Levels",
            value="\n".join(level_list),
            inline=False
        )

        # System Info
        embed.add_field(
            name="📊 System Info",
            value=f"Connected to {len(bot.guilds)} servers\nUptime: Online",
            inline=True
        )

        embed.set_footer(text="Alpha Intelligence | GODLIKE Market Analysis")
        embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        logger.error(f"Status command error: {e}")
        await interaction.response.send_message("❌ Status check failed. The matrix is glitching.")

# ===============================
# ERROR HANDLING
# ===============================

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for commands"""
    logger.error(f"Command error: {error}")
    if isinstance(error, discord.app_commands.CommandOnCooldown):
        await ctx.send(f"⏰ Command on cooldown. Try again in {error.retry_after:.1f} seconds.")
    else:
        await ctx.send("❌ An error occurred. The savage intelligence is recalibrating.")

# ===============================
# MAIN EXECUTION
# ===============================

def main():
    """Main bot execution"""
    token = os.getenv("DISCORD_BOT_TOKEN")

    if not token:
        logger.error("❌ DISCORD_BOT_TOKEN not found in environment variables!")
        logger.error("Please set DISCORD_BOT_TOKEN in your Railway environment variables")
        sys.exit(1)

    logger.info("🤖 Starting Alpha Intelligence Discord Bot...")
    logger.info("🔥 Preparing savage LLM integration...")

    try:
        bot.run(token)
    except KeyboardInterrupt:
        logger.info("🛑 Bot shutdown requested")
    except Exception as e:
        logger.error(f"❌ Bot failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
