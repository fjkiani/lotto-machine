"""
🎯 BACKTESTING FRAMEWORK
Modular, reusable backtesting system for all signal types.

DETECTORS:
- BaseDetector: Abstract base class for all detectors
- SelloffRallyDetector: Momentum-based selloff/rally signals
- RapidAPIOptionsDetector: Options flow from RapidAPI
- GapDetector: Pre-market gap signals
- SqueezeDetector: Short squeeze signals
- GammaDetector: Gamma exposure signals
- RedditDetector: Reddit sentiment signals

RUNNER:
- UnifiedBacktestRunner: Runs all detectors and generates reports
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

# New modular detector system
from .simulation.base_detector import BaseDetector, Signal, TradeResult, BacktestResult
from .simulation.selloff_rally_detector import SelloffRallyDetector
from .simulation.gap_detector import GapDetector
from .simulation.market_context_detector import MarketContextDetector, MarketContext
from .simulation.unified_backtest_runner import UnifiedBacktestRunner

# Optional imports (may need API keys)
try:
    from .simulation.rapidapi_options_detector import RapidAPIOptionsDetector
except ImportError:
    RapidAPIOptionsDetector = None

__all__ = [
    # Data
    'DataLoader',
    'AlertsLoader',
    'SignalAlert',
    
    # Base detector system (NEW)
    'BaseDetector',
    'Signal',
    'TradeResult',
    'BacktestResult',
    
    # Modular detectors (NEW)
    'SelloffRallyDetector',
    'GapDetector',
    'RapidAPIOptionsDetector',
    'MarketContextDetector',
    'MarketContext',
    'UnifiedBacktestRunner',
    
    # Legacy simulators
    'TradeSimulator',
    'CurrentSystemSimulator',
    'NarrativeBrainSimulator',
    'SqueezeDetectorSimulator',
    'SqueezeSignal',
    'GammaDetectorSimulator',
    'GammaBacktestSignal',
    'RedditSignalSimulator',
    'RedditBacktestResult',
    'RedditBacktestTrade',
    'RedditSignalTracker',
    'TrackedSignal',
    
    # Analysis
    'PerformanceAnalyzer',
    'SignalAnalyzer',
    'SignalSummary',
    'ProductionDiagnostics',
    'DiagnosticResult',
    'ProductionHealthMonitor',
    'HealthStatus',
    'DataStalenessCheck',
    
    # Reports
    'ReportGenerator',
    'SignalReportGenerator',
    'DiagnosticReportGenerator',
    'HealthReportGenerator',
    'SqueezeReportGenerator',
    'SqueezeMetrics',
    'GammaReportGenerator',
    'GammaMetrics',
    
    # Monitoring
    'ProductionMonitor',
    'MonitorConfig',
    
    # Config
    'TradingParams',
]



