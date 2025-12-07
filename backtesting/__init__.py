"""
🎯 BACKTESTING FRAMEWORK
Modular, reusable backtesting system for DP alerts
"""

from .data.loader import DataLoader
from .simulation.trade_simulator import TradeSimulator
from .simulation.current_system import CurrentSystemSimulator
from .simulation.narrative_brain import NarrativeBrainSimulator
from .analysis.performance import PerformanceAnalyzer
from .reports.generator import ReportGenerator
from .config.trading_params import TradingParams

__all__ = [
    'DataLoader',
    'TradeSimulator',
    'CurrentSystemSimulator',
    'NarrativeBrainSimulator',
    'PerformanceAnalyzer',
    'ReportGenerator',
    'TradingParams'
]

