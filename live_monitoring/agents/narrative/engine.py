"""
🧠 NARRATIVE INTELLIGENCE ENGINE
================================
Main orchestrator for the narrative intelligence system.

Coordinates:
- TavilyClient for deep research
- Specialized agents (Fed, Trump, Institutional, Macro, Technical)
- Synthesizer for unified output

Usage:
    engine = NarrativeIntelligenceEngine(tavily_key="...")
    
    narrative = engine.get_full_narrative(
        symbol="SPY",
        current_price=685.65,
        dp_levels=[...],
        fed_sentiment="DOVISH",
        fed_cut_prob=87.2,
        trump_risk="HIGH"
    )
    
    print(narrative.headline)
    print(narrative.full_story)
    print(narrative.trade_thesis)
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .tavily_client import TavilyClient
from .synthesizer import NarrativeSynthesizer, SynthesizedNarrative
from .agents import (
    FedNarrativeAgent,
    TrumpNarrativeAgent,
    InstitutionalNarrativeAgent,
    MacroNarrativeAgent,
    TechnicalNarrativeAgent,
    AgentResult
)

logger = logging.getLogger(__name__)


class NarrativeIntelligenceEngine:
    """
    Main narrative intelligence engine.
    
    Orchestrates specialized agents to produce unified market narrative.
    
    Key features:
    - Modular agent architecture (easy to add/remove agents)
    - Tavily for deep, non-mainstream research
    - Synthesizer for unified output
    - Discord-ready output format
    """
    
    def __init__(
        self,
        tavily_key: Optional[str] = None,
        agents: List[str] = None,  # Which agents to enable
    ):
        """
        Initialize narrative engine.
        
        Args:
            tavily_key: Tavily API key
            agents: List of agent names to enable (default: all)
        """
        # Initialize Tavily client
        self.tavily_key = tavily_key or os.getenv('TAVILY_API_KEY')
        if not self.tavily_key:
            logger.warning("⚠️ TAVILY_API_KEY not set - narrative will be limited")
            self.tavily_client = None
        else:
            self.tavily_client = TavilyClient(self.tavily_key)
        
        # Initialize agents
        self.agents = {}
        enabled_agents = agents or ['fed', 'trump', 'institutional', 'macro', 'technical']
        
        if self.tavily_client:
            if 'fed' in enabled_agents:
                self.agents['fed'] = FedNarrativeAgent(self.tavily_client)
            if 'trump' in enabled_agents:
                self.agents['trump'] = TrumpNarrativeAgent(self.tavily_client)
            if 'institutional' in enabled_agents:
                self.agents['institutional'] = InstitutionalNarrativeAgent(self.tavily_client)
            if 'macro' in enabled_agents:
                self.agents['macro'] = MacroNarrativeAgent(self.tavily_client)
            if 'technical' in enabled_agents:
                self.agents['technical'] = TechnicalNarrativeAgent(self.tavily_client)
        
        # Initialize synthesizer
        self.synthesizer = NarrativeSynthesizer()
        
        logger.info(f"🧠 Narrative Engine initialized with {len(self.agents)} agents")
    
    def get_full_narrative(
        self,
        symbol: str = "SPY",
        current_price: float = None,
        dp_levels: List[Dict] = None,
        fed_sentiment: str = "NEUTRAL",
        fed_cut_prob: float = None,
        trump_risk: str = "LOW",
        trump_news: str = None,
        recent_event: Dict = None,
    ) -> SynthesizedNarrative:
        """
        Get full narrative using all available agents.
        
        Args:
            symbol: Symbol to analyze
            current_price: Current price
            dp_levels: Dark pool battlegrounds
            fed_sentiment: Fed sentiment (DOVISH/HAWKISH/NEUTRAL)
            fed_cut_prob: Fed cut probability (0-100)
            trump_risk: Trump risk level (LOW/MEDIUM/HIGH)
            trump_news: Latest Trump news headline
            recent_event: Recent economic event dict
            
        Returns:
            SynthesizedNarrative with full analysis
        """
        start_time = datetime.now()
        logger.info(f"🧠 Getting full narrative for {symbol}...")
        
        # Build context for agents
        context = {
            'symbol': symbol,
            'current_price': current_price,
            'dp_levels': dp_levels or [],
            'fed_sentiment': fed_sentiment,
            'fed_cut_prob': fed_cut_prob,
            'trump_risk': trump_risk,
            'trump_news': trump_news,
            'recent_event': recent_event,
        }
        
        # Run all agents
        agent_results: List[AgentResult] = []
        
        for name, agent in self.agents.items():
            try:
                logger.info(f"   Running {name} agent...")
                result = agent.research(context)
                agent_results.append(result)
                logger.info(f"   ✅ {name}: {result.bias} ({result.confidence:.0%})")
            except Exception as e:
                logger.error(f"   ❌ {name} agent failed: {e}")
        
        # Synthesize results
        narrative = self.synthesizer.synthesize(
            agent_results=agent_results,
            symbol=symbol,
            current_price=current_price
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"🧠 Narrative complete in {elapsed:.1f}s: {narrative.overall_bias} ({narrative.confidence:.0%})")
        
        return narrative
    
    def get_quick_narrative(
        self,
        symbol: str = "SPY",
        current_price: float = None,
        dp_levels: List[Dict] = None,
        fed_sentiment: str = "NEUTRAL",
    ) -> SynthesizedNarrative:
        """
        Get quick narrative using only essential agents (Fed + Institutional).
        
        Faster than full narrative, good for real-time use.
        """
        logger.info(f"⚡ Getting quick narrative for {symbol}...")
        
        context = {
            'symbol': symbol,
            'current_price': current_price,
            'dp_levels': dp_levels or [],
            'fed_sentiment': fed_sentiment,
        }
        
        agent_results = []
        
        # Only run essential agents
        essential_agents = ['fed', 'institutional']
        for name in essential_agents:
            if name in self.agents:
                try:
                    result = self.agents[name].research(context)
                    agent_results.append(result)
                except Exception as e:
                    logger.warning(f"Quick narrative {name} failed: {e}")
        
        return self.synthesizer.synthesize(
            agent_results=agent_results,
            symbol=symbol,
            current_price=current_price
        )
    
    def get_agent_result(
        self,
        agent_name: str,
        context: Dict[str, Any]
    ) -> Optional[AgentResult]:
        """
        Run a single agent.
        
        Useful for focused research on specific domain.
        """
        if agent_name not in self.agents:
            logger.warning(f"Agent {agent_name} not found")
            return None
        
        try:
            return self.agents[agent_name].research(context)
        except Exception as e:
            logger.error(f"Agent {agent_name} failed: {e}")
            return None
    
    def list_agents(self) -> List[str]:
        """List available agents."""
        return list(self.agents.keys())
    
    def get_status(self) -> Dict[str, Any]:
        """Get engine status."""
        return {
            'tavily_connected': self.tavily_client is not None,
            'agents_enabled': list(self.agents.keys()),
            'agent_count': len(self.agents),
        }

