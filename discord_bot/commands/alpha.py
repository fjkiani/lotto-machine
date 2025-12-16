"""
🧠 ALPHA INTELLIGENCE COMMAND
Intelligent market assistant with access to all tools
"""

import discord
from discord import app_commands


def setup(bot):
    """Setup the alpha command"""
    
    # Initialize agent
    agent = None
    
    def get_agent():
        """Lazy load agent"""
        nonlocal agent
        if agent is None:
            from discord_bot.agents import AlphaIntelligenceAgent
            agent = AlphaIntelligenceAgent()
        return agent
    
    @bot.tree.command(name="alpha", description="Ask Alpha anything about the market")
    @app_commands.describe(
        query="Your question about the market (levels, context, Fed, trade setups, etc.)"
    )
    async def alpha_command(interaction: discord.Interaction, query: str):
        """
        🧠 Alpha Intelligence - Intelligent Market Assistant
        
        Routes your query to the appropriate data source and returns
        a synthesized, actionable response.
        
        Examples:
        - "What SPY levels should I watch?"
        - "What's the story on QQQ today?"
        - "Give me a long setup for SPY"
        - "What's the rate cut probability?"
        """
        await interaction.response.defer()
        
        try:
            # Get agent
            alpha_agent = get_agent()
            
            # Process query
            response = await alpha_agent.process(query)
            
            if response.success:
                # Add footer with tools used
                message = response.response
                if response.tools_used:
                    tools_str = ", ".join(response.tools_used)
                    message += f"\n\n*Tools used: {tools_str}*"
                
                # Handle long messages
                if len(message) > 1900:
                    chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
                    for i, chunk in enumerate(chunks):
                        header = f"🧠 **Alpha Intelligence** Part {i+1}/{len(chunks)}\n\n" if i > 0 else ""
                        await interaction.followup.send(f"{header}{chunk}")
                else:
                    await interaction.followup.send(f"🧠 **Alpha Intelligence**\n\n{message}")
            else:
                await interaction.followup.send(f"❌ {response.response}")
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error processing query: {str(e)}")
    
    @bot.tree.command(name="alpha-help", description="Show Alpha Intelligence capabilities")
    async def alpha_help_command(interaction: discord.Interaction):
        """Show help message for Alpha Intelligence"""
        await interaction.response.defer()
        
        try:
            alpha_agent = get_agent()
            help_message = alpha_agent.get_help_message()
            await interaction.followup.send(help_message)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}")
    
    @bot.tree.command(name="levels", description="Quick access to DP levels for a symbol")
    @app_commands.describe(symbol="Ticker symbol (default: SPY)")
    async def levels_command(interaction: discord.Interaction, symbol: str = "SPY"):
        """Quick access to dark pool levels"""
        await interaction.response.defer()
        
        try:
            alpha_agent = get_agent()
            response = await alpha_agent.process(f"What are the dark pool levels for {symbol}?")
            
            if response.success:
                await interaction.followup.send(f"🧠 **Alpha Intelligence**\n\n{response.response}")
            else:
                await interaction.followup.send(f"❌ {response.response}")
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}")
    
    @bot.tree.command(name="setup", description="Get a trade setup for a symbol")
    @app_commands.describe(
        symbol="Ticker symbol (default: SPY)",
        direction="Trade direction"
    )
    @app_commands.choices(direction=[
        app_commands.Choice(name="📈 Long", value="LONG"),
        app_commands.Choice(name="📉 Short", value="SHORT"),
    ])
    async def setup_command(interaction: discord.Interaction, symbol: str = "SPY", direction: str = "LONG"):
        """Quick access to trade setup"""
        await interaction.response.defer()
        
        try:
            alpha_agent = get_agent()
            response = await alpha_agent.process(f"Give me a {direction} trade setup for {symbol}")
            
            if response.success:
                await interaction.followup.send(f"🧠 **Alpha Intelligence**\n\n{response.response}")
            else:
                await interaction.followup.send(f"❌ {response.response}")
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}")



