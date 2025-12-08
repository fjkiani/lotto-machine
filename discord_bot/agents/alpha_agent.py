"""
🧠 ALPHA INTELLIGENCE AGENT
Main orchestrator that routes queries to appropriate tools
"""

import os
import logging
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .tools.dp_intelligence import DPIntelligenceTool
from .tools.narrative_brain import NarrativeBrainTool
from .tools.signal_synthesis import SignalSynthesisTool
from .tools.fed_watch import FedWatchTool
from .tools.economic import EconomicTool
from .tools.trade_calc import TradeCalculatorTool

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Response from the agent"""
    success: bool
    response: str
    tools_used: List[str]
    error: Optional[str] = None


class AlphaIntelligenceAgent:
    """
    🧠 ALPHA INTELLIGENCE AGENT
    
    Intelligent orchestrator that:
    1. Understands user intent
    2. Routes to appropriate tools
    3. Executes tools
    4. Synthesizes response
    
    Example:
        agent = AlphaIntelligenceAgent()
        response = await agent.process("What levels should I watch for SPY?")
    """
    
    def __init__(self):
        """Initialize the agent with all available tools"""
        logger.info("🧠 Initializing Alpha Intelligence Agent...")
        
        # Initialize all tools
        self.tools = {}
        self._init_tools()
        
        # LLM for synthesis (optional, for advanced responses)
        self.llm_available = self._init_llm()
        
        logger.info(f"✅ Agent initialized with {len(self.tools)} tools")
    
    def _init_tools(self):
        """Initialize all available tools"""
        tool_classes = [
            DPIntelligenceTool,
            NarrativeBrainTool,
            SignalSynthesisTool,
            FedWatchTool,
            EconomicTool,
            TradeCalculatorTool,
        ]
        
        for tool_class in tool_classes:
            try:
                tool = tool_class()
                self.tools[tool.name] = tool
                logger.info(f"  ✅ {tool.name} tool loaded")
            except Exception as e:
                logger.warning(f"  ⚠️ {tool_class.__name__} failed: {e}")
    
    def _init_llm(self) -> bool:
        """Initialize LLM for synthesis"""
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                logger.info("  ✅ LLM available for synthesis")
                return True
        except Exception as e:
            logger.debug(f"LLM init: {e}")
        return False
    
    async def process(self, query: str) -> AgentResponse:
        """
        Process a user query.
        
        1. Route query to appropriate tools
        2. Execute tools
        3. Synthesize response
        
        Args:
            query: User query string
            
        Returns:
            AgentResponse with formatted response
        """
        try:
            # 1. Route query to tools
            routing = self._route_query(query)
            tools_to_use = routing["tools"]
            params = routing["params"]
            
            if not tools_to_use:
                return AgentResponse(
                    success=False,
                    response="I'm not sure how to help with that. Try asking about:\n"
                             "• **Levels** - 'What SPY levels should I watch?'\n"
                             "• **Market context** - 'What's the story on SPY?'\n"
                             "• **Fed** - 'What's the rate cut probability?'\n"
                             "• **Trade setups** - 'Give me a long setup for SPY'\n"
                             "• **Economic events** - 'Any economic data today?'",
                    tools_used=[],
                    error="No tools matched query"
                )
            
            # 2. Execute tools
            results = {}
            for tool_name in tools_to_use:
                if tool_name in self.tools:
                    tool = self.tools[tool_name]
                    result = tool.execute(params)
                    results[tool_name] = result
            
            # 3. Synthesize response
            response = self._synthesize_response(query, results)
            
            return AgentResponse(
                success=True,
                response=response,
                tools_used=tools_to_use
            )
            
        except Exception as e:
            logger.error(f"Agent process error: {e}")
            return AgentResponse(
                success=False,
                response=f"Sorry, I encountered an error: {str(e)}",
                tools_used=[],
                error=str(e)
            )
    
    def _route_query(self, query: str) -> Dict[str, Any]:
        """
        Route query to appropriate tools using keyword matching.
        
        Future: Use LLM for more intelligent routing.
        """
        query_lower = query.lower()
        matched_tools = []
        
        # Check each tool for keyword matches
        for tool_name, tool in self.tools.items():
            if tool.matches_query(query):
                matched_tools.append(tool_name)
        
        # Default to dp_intelligence if nothing matched but looks like a question
        if not matched_tools and any(word in query_lower for word in ["what", "where", "how", "should"]):
            matched_tools = ["dp_intelligence", "signal_synthesis"]
        
        # Extract parameters
        params = {
            "symbol": self._extract_symbol(query),
            "direction": self._extract_direction(query)
        }
        
        # Add specific actions based on query
        if "trade" in query_lower or "setup" in query_lower or "entry" in query_lower:
            matched_tools = ["trade_calculator", "dp_intelligence"]
        
        return {
            "tools": matched_tools,
            "params": params
        }
    
    def _extract_symbol(self, query: str) -> str:
        """Extract ticker symbol from query"""
        symbols = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'TSLA', 'NVDA', 'AMZN', 'META', 'GOOGL', 'IWM', 'DIA']
        query_upper = query.upper()
        
        for symbol in symbols:
            if symbol in query_upper:
                return symbol
        
        return 'SPY'  # Default
    
    def _extract_direction(self, query: str) -> str:
        """Extract trade direction from query"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["long", "buy", "bullish", "call"]):
            return "LONG"
        elif any(word in query_lower for word in ["short", "sell", "bearish", "put"]):
            return "SHORT"
        
        return "LONG"  # Default
    
    def _synthesize_response(self, query: str, results: Dict[str, Any]) -> str:
        """
        Synthesize final response from tool results.
        
        Combines outputs from multiple tools into coherent response.
        """
        if not results:
            return "No results available."
        
        response_parts = []
        
        # Format each tool's output
        for tool_name, result in results.items():
            if tool_name in self.tools:
                tool = self.tools[tool_name]
                formatted = tool.format_response(result)
                response_parts.append(formatted)
        
        # Combine responses
        if len(response_parts) == 1:
            return response_parts[0]
        
        # Multiple tools - combine with dividers
        combined = "\n\n" + "─" * 40 + "\n\n".join(response_parts)
        return combined
    
    def get_available_tools(self) -> List[Dict[str, str]]:
        """Get list of available tools with descriptions"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "capabilities": tool.capabilities
            }
            for tool in self.tools.values()
        ]
    
    def get_help_message(self) -> str:
        """Get help message showing available capabilities"""
        lines = ["🧠 **Alpha Intelligence Agent**\n"]
        lines.append("I can help you with:\n")
        
        examples = [
            ("📊 **Dark Pool Levels**", "What levels should I watch for SPY?"),
            ("🧠 **Market Context**", "What's the story on QQQ today?"),
            ("🏦 **Fed Watch**", "What's the rate cut probability?"),
            ("📅 **Economic Events**", "Any economic data today?"),
            ("🎯 **Trade Setups**", "Give me a long setup for SPY"),
            ("📈 **Market Synthesis**", "What's the overall market direction?"),
        ]
        
        for category, example in examples:
            lines.append(f"{category}\n  *Example: \"{example}\"*\n")
        
        return "\n".join(lines)


