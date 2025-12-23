"""
🎯 BACKTESTING SIMULATION MODULES

NEW MODULAR SYSTEM (2025-12-19):
- BaseDetector: Abstract base class for all detectors
- SelloffRallyDetector: Momentum-based selloff/rally (52.9% win rate)
- GapDetector: Pre-market gap signals (50% win rate)
- RapidAPIOptionsDetector: Options flow signals
- MarketContextDetector: News + price action analysis
- UnifiedBacktestRunner: Runs all detectors with context filtering

USAGE:
```python
from backtesting import UnifiedBacktestRunner

runner = UnifiedBacktestRunner(symbols=['SPY', 'QQQ'])
results = runner.run_all()
print(runner.generate_report(results))
```
"""

from .base_detector import BaseDetector, Signal, TradeResult, BacktestResult
from .selloff_rally_detector import SelloffRallyDetector
from .gap_detector import GapDetector
from .market_context_detector import MarketContextDetector, MarketContext
from .unified_backtest_runner import UnifiedBacktestRunner

# Legacy modules
from .trade_simulator import TradeSimulator
from .current_system import CurrentSystemSimulator
from .narrative_brain import NarrativeBrainSimulator
from .squeeze_detector import SqueezeDetectorSimulator, SqueezeSignal
from .gamma_detector import GammaDetectorSimulator, GammaBacktestSignal
from .reddit_detector import RedditSignalSimulator, RedditBacktestResult, RedditBacktestTrade
from .reddit_signal_tracker import RedditSignalTracker, TrackedSignal

# Optional
try:
    from .rapidapi_options_detector import RapidAPIOptionsDetector
except ImportError:
    RapidAPIOptionsDetector = None

__all__ = [
    # New modular system
    'BaseDetector',
    'Signal',
    'TradeResult', 
    'BacktestResult',
    'SelloffRallyDetector',
    'GapDetector',
    'RapidAPIOptionsDetector',
    'MarketContextDetector',
    'MarketContext',
    'UnifiedBacktestRunner',
    
    # Legacy
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
]
