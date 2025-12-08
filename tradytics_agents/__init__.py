"""
🎯 TRADYTICS ECOSYSTEM - Specialized Agents for Each Feed Type

Non-monolithic architecture with individual agents for:
- Options Sweeps (GEX, gamma, volatility analysis)
- Golden Sweeps (High-conviction institutional moves)
- Trady Flow (Volume-based institutional tracking)
- Darkpool (Block trades, iceberg detection)
- Bullseye (Multi-timeframe confluence)
- Scalps (Short-term momentum plays)
- Social Spike (Sentiment-driven catalysts)
- Insider Trades (Corporate intelligence)
- Stock Breakouts (Technical breakout analysis)
- Analyst Grades (Institutional ratings synthesis)
- Important News (Catalyst identification)
- Crypto Breakouts (Digital asset technicals)
- Crypto Signals (Blockchain-based signals)

Each agent has specialized parsing, context, and analysis approach.
"""

from .base_agent import BaseTradyticsAgent
from .options_sweeps_agent import OptionsSweepsAgent
from .golden_sweeps_agent import GoldenSweepsAgent
from .trady_flow_agent import TradyFlowAgent
from .darkpool_agent import DarkpoolAgent
from .bullseye_agent import BullseyeAgent
from .scalps_agent import ScalpsAgent
from .social_spike_agent import SocialSpikeAgent
from .insider_trades_agent import InsiderTradesAgent
from .stock_breakouts_agent import StockBreakoutsAgent
from .analyst_grades_agent import AnalystGradesAgent
from .important_news_agent import ImportantNewsAgent
from .crypto_breakouts_agent import CryptoBreakoutsAgent
from .crypto_signals_agent import CryptoSignalsAgent
from .synthesis_engine import TradyticsSynthesisEngine

__all__ = [
    'BaseTradyticsAgent',
    'OptionsSweepsAgent',
    'GoldenSweepsAgent',
    'TradyFlowAgent',
    'DarkpoolAgent',
    'BullseyeAgent',
    'ScalpsAgent',
    'SocialSpikeAgent',
    'InsiderTradesAgent',
    'StockBreakoutsAgent',
    'AnalystGradesAgent',
    'ImportantNewsAgent',
    'CryptoBreakoutsAgent',
    'CryptoSignalsAgent',
    'TradyticsSynthesisEngine'
]
