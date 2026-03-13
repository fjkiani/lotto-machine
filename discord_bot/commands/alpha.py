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
                # Post-agent gate check — append warning if thesis invalid
                message = response.response
                try:
                    from live_monitoring.orchestrator.confluence_gate import ConfluenceGate
                    gate = ConfluenceGate()
                    response_lower = message.lower()
                    if any(word in response_lower for word in ["buy", "long", "calls", "bullish entry"]):
                        gate_result = gate.should_fire(signal_direction="LONG", symbol="SPY", raw_confidence=50)
                        if gate_result.blocked:
                            message += f"\n\n⚠️ **Gate Warning**: {gate_result.reason}"
                    elif any(word in response_lower for word in ["sell", "short", "puts", "bearish entry"]):
                        gate_result = gate.should_fire(signal_direction="SHORT", symbol="SPY", raw_confidence=50)
                        if gate_result.blocked:
                            message += f"\n\n⚠️ **Gate Warning**: {gate_result.reason}"
                except Exception:
                    pass  # Gate unavailable — proceed without warning

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
        """Quick access to dark pool levels — with thesis warning."""
        await interaction.response.defer()
        
        try:
            alpha_agent = get_agent()
            response = await alpha_agent.process(f"What are the dark pool levels for {symbol}?")
            
            if response.success:
                message = response.response
                # ── Thesis warning: append if thesis invalid ──
                try:
                    import json, os
                    snap_path = "/tmp/intraday_snapshot.json"
                    if os.path.exists(snap_path):
                        with open(snap_path) as f:
                            snap = json.load(f)
                        if snap.get("market_open") and not snap.get("thesis_valid", True):
                            reason = snap.get("thesis_invalidation_reason", "Thesis invalidated")
                            message += f"\n\n⚠️ **THESIS WARNING**: {reason}\n_Levels shown for reference only — thesis is currently INVALID._"
                except Exception:
                    pass  # Don't fail levels on snapshot read error
                await interaction.followup.send(f"🧠 **Alpha Intelligence**\n\n{message}")
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
        """Quick access to trade setup — gated through ConfluenceGate."""
        await interaction.response.defer()
        
        try:
            # Gate check BEFORE generating setup
            try:
                from live_monitoring.orchestrator.confluence_gate import ConfluenceGate
                gate = ConfluenceGate()
                gate_result = gate.should_fire(
                    signal_direction=direction.upper(),
                    symbol=symbol.upper(),
                    raw_confidence=75,
                )
                if gate_result.blocked:
                    await interaction.followup.send(f"⛔ **BLOCKED by Gate**: {gate_result.reason}")
                    return
            except Exception:
                pass  # Gate unavailable — proceed with setup

            alpha_agent = get_agent()
            response = await alpha_agent.process(f"Give me a {direction} trade setup for {symbol}")
            
            if response.success:
                await interaction.followup.send(f"🧠 **Alpha Intelligence**\n\n{response.response}")
            else:
                await interaction.followup.send(f"❌ {response.response}")
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}")



