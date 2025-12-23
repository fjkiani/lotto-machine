"""
Tradytics Listener Module

Autonomously listens for and processes Tradytics bot alerts.
"""

import discord
import logging
from .parser import TradyticsParser
from .analyzer import TradyticsAnalyzer

logger = logging.getLogger(__name__)


class TradyticsListener:
    """
    Autonomous Tradytics bot alert listener and processor.
    """

    def __init__(self, bot):
        self.bot = bot
        self.parser = TradyticsParser()
        self.analyzer = TradyticsAnalyzer(bot.savage_llm)

    async def process_message(self, message):
        """Process incoming messages for Tradytics alerts"""
        # Check if message is from a Tradytics bot
        if not self._is_tradytics_bot(message.author):
            return

        # Extract and analyze the alert
        await self._process_tradytics_alert(message)

    def _is_tradytics_bot(self, author):
        """Check if message is from a Tradytics bot"""
        tradytics_bots = [
            "Tradytics", "Trady Flow", "Bullseye", "Scalps", "Sweeps",
            "Golden Sweeps", "Darkpool", "Insider", "Analyst Grades",
            "Important News", "Stock Breakouts", "AI Predictions",
            "Top Flow", "Big Flow", "Flow Summary", "Unusual Flow",
            "Algo Flow Line", "Flow Heatmap", "Open Interest", "Implied Volatility",
            "Largest DP Prints", "Largest Block Trades", "Darkpool Levels",
            "Recent Darkpool Data", "Support Resistance Levels", "Big Stock Movers",
            "Simulated Price Projections", "Insider Trades", "Seasonality",
            "Revenue Estimates", "Latest News", "Analyst Grades", "Scanner Signals"
        ]

        return any(bot.lower() in author.name.lower() for bot in tradytics_bots)

    async def _process_tradytics_alert(self, message):
        """Process and analyze Tradytics bot alerts autonomously"""
        try:
            alert_text = message.content
            bot_name = message.author.name

            logger.info(f"🎯 Detected Tradytics alert from {bot_name}: {alert_text[:100]}...")

            # Parse the alert
            alert_data = self.parser.parse_alert(alert_text, bot_name)

            if not alert_data:
                return

            # Generate savage analysis
            analysis = await self.analyzer.analyze_alert(alert_data, bot_name)

            if analysis:
                # Send autonomous response
                embed = discord.Embed(
                    title=f"🧠 **SAVAGE ANALYSIS** - {bot_name} Alert",
                    description=f"**Alert:** {alert_data.get('summary', 'Unknown')}\n\n{analysis}",
                    color=0xff0000,  # Red for savage
                    timestamp=message.created_at
                )

                embed.set_footer(text="Alpha Intelligence | Autonomous Tradytics Integration")

                await message.channel.send(embed=embed)
                logger.info(f"✅ Sent autonomous Tradytics analysis for {bot_name}")

        except Exception as e:
            logger.error(f"❌ Error processing Tradytics alert: {e}")







