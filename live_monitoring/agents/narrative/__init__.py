"""
🧠 NARRATIVE INTELLIGENCE ENGINE
================================
Tavily-powered deep research with specialized agents.

Architecture:
- TavilyClient: Core API client for deep search
- Specialized Agents: Fed, Trump, Institutional, Macro
- Synthesizer: Combines all agent outputs into unified narrative
- Engine: Orchestrates everything

Usage:
    from live_monitoring.agents.narrative import NarrativeIntelligenceEngine
    
    engine = NarrativeIntelligenceEngine(tavily_key="...")
    narrative = engine.get_full_narrative(symbol="SPY", dp_levels=levels)
"""

from .engine import NarrativeIntelligenceEngine
from .tavily_client import TavilyClient
from .synthesizer import NarrativeSynthesizer

__all__ = [
    'NarrativeIntelligenceEngine',
    'TavilyClient', 
    'NarrativeSynthesizer'
]

