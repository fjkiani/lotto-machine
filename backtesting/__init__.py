"""
🎯 BACKTESTING FRAMEWORK
Modular, reusable backtesting system for DP alerts and Reddit signals
"""

from .data.loader import DataLoader
from .data.alerts_loader import AlertsLoader, SignalAlert
from .simulation.trade_simulator import TradeSimulator
from .simulation.current_system import CurrentSystemSimulator
from .simulation.narrative_brain import NarrativeBrainSimulator
from .analysis.performance import PerformanceAnalyzer
from .analysis.signal_analyzer import SignalAnalyzer, SignalSummary
from .analysis.diagnostics import ProductionDiagnostics, DiagnosticResult
from .analysis.production_health import ProductionHealthMonitor, HealthStatus, DataStalenessCheck
from .reports.generator import ReportGenerator
from .reports.signal_report import SignalReportGenerator
from .reports.diagnostic_report import DiagnosticReportGenerator
from .reports.health_report import HealthReportGenerator
from .reports.squeeze_report import SqueezeReportGenerator, SqueezeMetrics
from .reports.gamma_report import GammaReportGenerator, GammaMetrics
from .monitoring.production_monitor import ProductionMonitor, MonitorConfig
from .config.trading_params import TradingParams
from .simulation.squeeze_detector import SqueezeDetectorSimulator, SqueezeSignal
from .simulation.gamma_detector import GammaDetectorSimulator, GammaBacktestSignal
from .simulation.reddit_detector import RedditSignalSimulator, RedditBacktestResult, RedditBacktestTrade
from .simulation.reddit_signal_tracker import RedditSignalTracker, TrackedSignal

__all__ = [
    'DataLoader',
    'AlertsLoader',
    'SignalAlert',
    'TradeSimulator',
    'CurrentSystemSimulator',
    'NarrativeBrainSimulator',
    'SqueezeDetectorSimulator',
    'SqueezeSignal',
    'PerformanceAnalyzer',
    'SignalAnalyzer',
    'SignalSummary',
    'ProductionDiagnostics',
    'DiagnosticResult',
    'ProductionHealthMonitor',
    'HealthStatus',
    'DataStalenessCheck',
    'ReportGenerator',
    'SignalReportGenerator',
    'DiagnosticReportGenerator',
    'HealthReportGenerator',
    'SqueezeReportGenerator',
    'SqueezeMetrics',
    'GammaReportGenerator',
    'GammaMetrics',
    'GammaDetectorSimulator',
    'GammaBacktestSignal',
    'ProductionMonitor',
    'MonitorConfig',
    'TradingParams',
    # Reddit backtesting
    'RedditSignalSimulator',
    'RedditBacktestResult',
    'RedditBacktestTrade',
    'RedditSignalTracker',
    'TrackedSignal',
]



