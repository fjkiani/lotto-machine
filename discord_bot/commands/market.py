"""
Market Analysis Command

Provides savage market analysis via slash command.
"""

import discord
from discord import app_commands


def setup(bot):
    """Setup the market command"""

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

        except Exception as e:
            await interaction.followup.send("❌ Market analysis failed. The algorithms are fighting back!")






