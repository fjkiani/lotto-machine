"""
Pipeline Configuration - Centralized Settings

ALL thresholds, intervals, and parameters in ONE place.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import os


@dataclass
class DPConfig:
    """Dark Pool configuration"""
    min_volume: int = 100_000  # Minimum volume for DP level (was hardcoded 500k!)
    interval: int = 60  # Check every 60 seconds
    debounce_minutes: int = 30  # Don't alert same level within 30 min
    symbols: List[str] = field(default_factory=lambda: ['SPY', 'QQQ'])
    
    # API Configuration
    api_key: Optional[str] = field(default_factory=lambda: os.getenv('CHARTEXCHANGE_API_KEY'))


@dataclass
class SynthesisConfig:
    """Signal Synthesis configuration"""
    min_confluence: float = 0.50  # Minimum 50% confluence to send
    unified_mode: bool = True  # Suppress individual alerts, only synthesis
    cross_asset_weight: float = 1.0  # Weight for cross-asset confirmation
    macro_weight: float = 0.6  # Weight for macro context
    dp_weight: float = 0.6  # Weight for DP signals
    timing_weight: float = 0.4  # Weight for timing signals


@dataclass
class FedConfig:
    """Fed Monitor configuration"""
    alert_threshold: float = 10.0  # % change to alert (15% in unified mode)
    unified_mode_threshold: float = 15.0  # % change in unified mode
    moderate_threshold: float = 5.0  # % change to buffer for synthesis


@dataclass
class TrumpConfig:
    """Trump Monitor configuration"""
    cooldown_minutes: int = 60  # Minutes between alerts on same topic
    min_exploit_score: int = 60  # Minimum exploit score to alert
    critical_score: int = 90  # Critical score (always alert even in unified mode)


@dataclass
class EconomicConfig:
    """Economic Monitor configuration"""
    alert_hours_high: int = 24  # Alert 24h before HIGH importance events
    alert_hours_any: int = 4  # Alert 4h before ANY event
    use_api_calendar: bool = True  # Use EventLoader (API) vs static calendar


@dataclass
class MonitoringIntervals:
    """Monitoring check intervals (in seconds)"""
    fed_watch: int = 300  # 5 minutes
    trump_intel: int = 180  # 3 minutes
    economic: int = 3600  # 1 hour
    dark_pool: int = 60  # 1 minute
    synthesis: int = 60  # 1 minute
    tradytics: int = 300  # 5 minutes


@dataclass
class AlertConfig:
    """Alert configuration"""
    discord_webhook: Optional[str] = field(default_factory=lambda: os.getenv('DISCORD_WEBHOOK_URL'))
    console_enabled: bool = True
    csv_enabled: bool = True
    slack_enabled: bool = False


@dataclass
class PipelineConfig:
    """
    Complete pipeline configuration.
    
    ALL settings in one place - no more hardcoded values!
    """
    # Component configs
    dp: DPConfig = field(default_factory=DPConfig)
    synthesis: SynthesisConfig = field(default_factory=SynthesisConfig)
    fed: FedConfig = field(default_factory=FedConfig)
    trump: TrumpConfig = field(default_factory=TrumpConfig)
    economic: EconomicConfig = field(default_factory=EconomicConfig)
    intervals: MonitoringIntervals = field(default_factory=MonitoringIntervals)
    alerts: AlertConfig = field(default_factory=AlertConfig)
    
    # General
    symbols: List[str] = field(default_factory=lambda: ['SPY', 'QQQ'])
    log_level: str = 'INFO'
    unified_mode: bool = True  # Suppress individual alerts, only synthesis
    
    # Feature flags
    enable_fed: bool = True
    enable_trump: bool = True
    enable_economic: bool = True
    enable_dp: bool = True
    enable_signal_brain: bool = True
    enable_narrative_brain: bool = True
    enable_tradytics: bool = True
    
    def __post_init__(self):
        """Validate configuration"""
        if self.dp.min_volume < 10_000:
            raise ValueError("DP min_volume too low (minimum 10k)")
        if self.synthesis.min_confluence < 0 or self.synthesis.min_confluence > 1:
            raise ValueError("min_confluence must be between 0 and 1")


