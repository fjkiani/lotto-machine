"""
🤖 BASE NARRATIVE AGENT
=======================
Abstract base class for specialized research agents.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from a specialized agent's research."""
    agent_name: str
    domain: str  # "FED", "TRUMP", "INSTITUTIONAL", "MACRO", "TECHNICAL"
    
    # Core findings
    summary: str = ""  # One-line summary
    full_context: str = ""  # Full detailed context
    key_points: List[str] = field(default_factory=list)
    
    # Market implications
    bias: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    confidence: float = 0.5  # 0-1
    impact: str = "LOW"  # LOW, MEDIUM, HIGH
    
    # Actionable
    trade_implication: str = ""  # What does this mean for trading?
    risk_factors: List[str] = field(default_factory=list)
    
    # Sources
    sources: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'agent': self.agent_name,
            'domain': self.domain,
            'summary': self.summary,
            'full_context': self.full_context,
            'key_points': self.key_points,
            'bias': self.bias,
            'confidence': self.confidence,
            'impact': self.impact,
            'trade_implication': self.trade_implication,
            'risk_factors': self.risk_factors,
            'sources': self.sources,
            'timestamp': self.timestamp,
        }


class BaseNarrativeAgent(ABC):
    """
    Base class for specialized narrative research agents.
    
    Each agent:
    1. Has a specific domain focus (Fed, Trump, Institutional, etc.)
    2. Uses Tavily for deep research
    3. Returns structured AgentResult
    4. Can be enhanced/extended independently
    """
    
    def __init__(self, tavily_client, name: str = "BaseAgent", domain: str = "GENERAL"):
        """
        Initialize agent.
        
        Args:
            tavily_client: TavilyClient instance for research
            name: Agent name for logging
            domain: Agent's focus domain
        """
        self.tavily = tavily_client
        self.name = name
        self.domain = domain
        self.logger = logging.getLogger(f"narrative.{name}")
    
    @abstractmethod
    def research(self, context: Dict[str, Any]) -> AgentResult:
        """
        Execute research and return findings.
        
        Args:
            context: Dict with symbol, price, dp_levels, etc.
            
        Returns:
            AgentResult with findings
        """
        pass
    
    def _create_result(
        self,
        summary: str = "",
        full_context: str = "",
        key_points: List[str] = None,
        bias: str = "NEUTRAL",
        confidence: float = 0.5,
        impact: str = "LOW",
        trade_implication: str = "",
        risk_factors: List[str] = None,
        sources: List[str] = None
    ) -> AgentResult:
        """Helper to create AgentResult."""
        return AgentResult(
            agent_name=self.name,
            domain=self.domain,
            summary=summary,
            full_context=full_context,
            key_points=key_points or [],
            bias=bias,
            confidence=confidence,
            impact=impact,
            trade_implication=trade_implication,
            risk_factors=risk_factors or [],
            sources=sources or []
        )
    
    def _extract_bias(self, text: str) -> str:
        """Extract market bias from text."""
        text_lower = text.lower()
        
        bullish_keywords = ['bullish', 'rally', 'surge', 'upside', 'buy', 'long', 'support', 'dovish', 'cut']
        bearish_keywords = ['bearish', 'selloff', 'crash', 'downside', 'sell', 'short', 'resistance', 'hawkish', 'hike']
        
        bullish_count = sum(1 for k in bullish_keywords if k in text_lower)
        bearish_count = sum(1 for k in bearish_keywords if k in text_lower)
        
        if bullish_count > bearish_count + 1:
            return "BULLISH"
        elif bearish_count > bullish_count + 1:
            return "BEARISH"
        return "NEUTRAL"
    
    def _extract_impact(self, text: str, confidence: float) -> str:
        """Determine impact level."""
        text_lower = text.lower()
        
        high_impact_keywords = ['breaking', 'major', 'significant', 'unprecedented', 'crisis', 'emergency']
        medium_impact_keywords = ['important', 'notable', 'substantial', 'considerable']
        
        if any(k in text_lower for k in high_impact_keywords) or confidence > 0.8:
            return "HIGH"
        elif any(k in text_lower for k in medium_impact_keywords) or confidence > 0.6:
            return "MEDIUM"
        return "LOW"

