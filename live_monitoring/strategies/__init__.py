"""
Trading Strategies Package
==========================

MOAT STRATEGIES (Unique Edge):
- PreMarketGapStrategy: Gap + DP confluence (20-25% edge)
- OptionsFlowStrategy: P/C ratio + max pain + gamma (15-20% edge)

These strategies integrate with our institutional data (DP levels, options)
to provide unique edge that retail traders don't have.

DELETED (No Unique Edge):
- VWAPStrategy: Too generic, every trader uses it
- OrderFlowStrategy: Duplicate of existing DP buy/sell analysis
"""

from .premarket_gap_strategy import PreMarketGapStrategy, PreMarketGapSignal
from .options_flow_strategy import OptionsFlowStrategy, OptionsFlowSignal

__all__ = [
    'PreMarketGapStrategy',
    'PreMarketGapSignal',
    'OptionsFlowStrategy', 
    'OptionsFlowSignal'
]
