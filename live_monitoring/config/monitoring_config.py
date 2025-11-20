#!/usr/bin/env python3
"""
MONITORING CONFIGURATION
- All settings in one place
- Easy to modify without touching code
"""

from dataclasses import dataclass
from typing import List

@dataclass
class TradingConfig:
    """Trading parameters"""
    # Universe
    symbols: List[str] = None
    
    # Risk Management
    max_position_size_pct: float = 0.02  # 2% per trade
    max_daily_drawdown_pct: float = 0.05  # 5% daily limit
    max_open_positions: int = 1  # Intraday only
    
    # Signal Filtering
    min_master_confidence: float = 0.75  # 75%+ for master signals
    min_high_confidence: float = 0.60  # 60%+ for half-size
    
    # Account
    account_size: float = 10000  # Paper trading start size
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["SPY", "QQQ"]

@dataclass
class MonitoringConfig:
    """Monitoring parameters"""
    # Timing
    market_open_hour: int = 9
    market_open_minute: int = 30
    market_close_hour: int = 16
    market_close_minute: int = 0
    check_interval_seconds: int = 60  # Check every 1 minute
    
    # Data Sources
    use_chartexchange: bool = True
    use_local_cache: bool = True  # Fallback to cached DP data
    cache_max_age_hours: int = 24
    use_screener: bool = True  # Enable stock screener for ticker discovery
    use_volume_profile: bool = True  # Enable volume profile timing
    use_sentiment: bool = True  # Enable Reddit sentiment filtering
    
    # Logging
    log_dir: str = "logs/live_monitoring"
    log_level: str = "INFO"
    save_rejected_signals: bool = True

@dataclass
class AlertConfig:
    """Alert routing configuration"""
    # Channels (enable/disable)
    console_enabled: bool = True
    csv_enabled: bool = True
    slack_enabled: bool = False  # Set to True when webhook configured
    email_enabled: bool = False
    
    # Slack
    slack_webhook_url: str = ""  # Set your webhook URL
    slack_channel: str = "#trading-signals"
    slack_username: str = "Signal Bot"
    
    # CSV
    csv_file: str = "logs/live_monitoring/signals.csv"
    
    # Alert Levels
    alert_on_master_signals: bool = True
    alert_on_high_confidence: bool = True
    alert_on_rejections: bool = False  # Usually too noisy

@dataclass
class APIConfig:
    """API credentials"""
    chartexchange_api_key: str = ""  # Will load from configs/
    chartexchange_tier: int = 3

# Create default configs
TRADING = TradingConfig()
MONITORING = MonitoringConfig()
ALERTS = AlertConfig()
API = APIConfig()

# Load API key from existing config
try:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent / 'configs'))
    import chartexchange_config
    API.chartexchange_api_key = chartexchange_config.CHARTEXCHANGE_API_KEY
    API.chartexchange_tier = chartexchange_config.CHARTEXCHANGE_TIER
except:
    print("⚠️ Warning: Could not load ChartExchange API key from configs/")



