"""
Savage Analysis Command

Custom savagery level analysis with multiple brutality options.
"""

import discord
from discord import app_commands


def setup(bot):
    """Setup the savage command"""

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

        except Exception as e:
            await interaction.followup.send("❌ Savagery level containment breach! The AI is fighting back.")





