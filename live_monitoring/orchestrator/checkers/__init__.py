"""
Checker modules for UnifiedAlphaMonitor.

Each checker handles a single responsibility:
- FedChecker: Fed watch and officials
- TrumpChecker: Trump intelligence
- EconomicChecker: Economic calendar
- DarkPoolChecker: Dark pool monitoring
- SynthesisChecker: Signal brain synthesis
- NarrativeChecker: Narrative brain signals
- TradyticsChecker: Tradytics analysis
- SqueezeChecker: Squeeze detection
- GammaChecker: Gamma tracking
- ScannerChecker: Opportunity scanner
- FTDChecker: FTD analysis
- DailyRecapChecker: Daily market recap
"""

from .base_checker import BaseChecker, CheckerAlert

__all__ = ['BaseChecker', 'CheckerAlert']

