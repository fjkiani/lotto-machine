"""
Economic Analysis Command

Provides savage economic analysis via slash command.
"""

import discord
from discord import app_commands


def setup(bot):
    """Setup the economic command"""

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

        except Exception as e:
            await interaction.followup.send("❌ The economic battlefield is too volatile right now. Try again later.")
