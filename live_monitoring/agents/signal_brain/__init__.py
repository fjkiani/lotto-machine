"""
🧠 Signal Synthesis Brain
=========================
The thinking layer that connects all signals.

Instead of 7 siloed alerts, outputs ONE unified synthesis with:
- Zone clustering (nearby levels → one zone)
- Cross-asset correlation (SPY + QQQ confirms)
- Full market context (trend, VIX, Fed, time)
- ONE clear trade recommendation
"""

from .models import (
    SupportZone, MarketContext, SignalState, 
    SynthesisResult, ConfluenceScore, TradeRecommendation
)
from .zone_clustering import ZoneClusterer
from .context import ContextEnricher
from .cross_asset import CrossAssetAnalyzer
from .confluence import ConfluenceScorer
from .synthesizer import SignalSynthesizer
from .engine import SignalBrainEngine

__all__ = [
    'SupportZone',
    'MarketContext', 
    'SignalState',
    'SynthesisResult',
    'ConfluenceScore',
    'TradeRecommendation',
    'ZoneClusterer',
    'ContextEnricher',
    'CrossAssetAnalyzer',
    'ConfluenceScorer',
    'SignalSynthesizer',
    'SignalBrainEngine',
]




