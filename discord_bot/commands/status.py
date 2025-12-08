"""
Status Command

Shows the current status of Alpha Intelligence systems.
"""

import discord


def setup(bot):
    """Setup the status command"""

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
            await interaction.response.send_message("❌ Status check failed. The matrix is glitching.")

