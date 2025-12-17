"""
📱 REDDIT CHECKER PRODUCTION CONFIGURATION

Controls for:
- Rate limiting and cooldowns
- Signal storage
- Algorithm tuning
- Spam prevention

Author: Alpha's AI Hedge Fund
Date: 2025-12-17
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class RedditCheckerConfig:
    """Production configuration for Reddit Checker."""
    
    # ==================== COOLDOWNS (Anti-Spam) ====================
    # Minimum time between same-type alerts per symbol
    
    HOT_TICKER_COOLDOWN_HOURS: int = 4      # Don't repeat hot ticker alert for 4 hours
    EMERGING_TICKER_COOLDOWN_HOURS: int = 6  # Don't repeat emerging ticker for 6 hours
    SIGNAL_COOLDOWN_HOURS: int = 4           # Don't repeat same signal for 4 hours
    
    # Maximum alerts per run to prevent spam
    MAX_HOT_TICKER_ALERTS: int = 3           # Max 3 hot ticker alerts per check
    MAX_EMERGING_ALERTS: int = 3             # Max 3 emerging alerts per check
    MAX_SIGNAL_ALERTS: int = 5               # Max 5 signal alerts per check
    
    # ==================== SIGNAL THRESHOLDS ====================
    
    MIN_SIGNAL_STRENGTH: int = 65            # Minimum confidence to alert
    MIN_SENTIMENT_EXTREME: float = 0.35      # Minimum sentiment for hot ticker
    
    # DP Enhancement thresholds
    DP_UPGRADE_THRESHOLD: int = 4            # Score needed for AVOID → LONG
    DP_WATCH_THRESHOLD: int = 2              # Score needed for AVOID → WATCH
    
    # ==================== STORAGE ====================
    
    ENABLE_SIGNAL_TRACKING: bool = True      # Store all signals for analysis
    SIGNAL_DB_PATH: str = "data/reddit_signal_tracking.db"
    
    # ==================== ALGORITHM IMPROVEMENT ====================
    
    # Track which signal types perform best
    TRACK_WIN_RATES: bool = True
    
    # Auto-adjust thresholds based on performance (future)
    ENABLE_AUTO_TUNING: bool = False
    
    # Minimum trades before adjusting
    MIN_TRADES_FOR_TUNING: int = 20
    
    # ==================== SYMBOLS ====================
    
    # Mega-caps get special treatment
    MEGA_CAPS: List[str] = None  # Will default to list below
    
    # Default monitored symbols
    DEFAULT_SYMBOLS: List[str] = None  # Will default to list below
    
    def __post_init__(self):
        if self.MEGA_CAPS is None:
            self.MEGA_CAPS = [
                'TSLA', 'NVDA', 'AAPL', 'MSFT', 'META', 
                'AMZN', 'GOOGL', 'GOOG', 'AMD', 'NFLX'
            ]
        
        if self.DEFAULT_SYMBOLS is None:
            self.DEFAULT_SYMBOLS = [
                # Mega-caps
                'TSLA', 'NVDA', 'AAPL', 'MSFT', 'META', 'AMZN', 'GOOGL', 'AMD',
                # Reddit favorites
                'GME', 'PLTR', 'SOFI', 'RIVN', 'LCID', 'NIO',
                # Crypto-adjacent
                'COIN', 'HOOD', 'MARA', 'RIOT',
                # SPY/QQQ
                'SPY', 'QQQ'
            ]


# ==================== UPGRADE SCORING ====================

# Points for DP-based signal enhancement
DP_UPGRADE_POINTS = {
    'price_rallying_5d': 2,         # Price up 5%+ in 5 days
    'dp_support': 2,                # DP level below price with volume
    'institutional_accumulation': 2, # Buy pressure > 60%
    'mega_cap': 1,                  # Large cap = more reliable
    'high_volume': 1                # Volume 1.5x+ average
}

# Total possible points: 8


# ==================== SIGNAL TYPE WEIGHTS ====================

# Initial weights for signal types (will be adjusted based on win rates)
SIGNAL_TYPE_WEIGHTS = {
    'CONFIRMED_MOMENTUM': 1.2,      # High confidence
    'BULLISH_DIVERGENCE': 1.1,      # Good edge historically
    'BEARISH_DIVERGENCE': 1.1,
    'FADE_HYPE': 1.0,               # Standard contrarian
    'FADE_FEAR': 1.0,
    'VELOCITY_SURGE': 0.8,          # Lower confidence (needs DP confirmation)
    'STEALTH_ACCUMULATION': 1.1,    # Often good edge
    'WSB_YOLO_WAVE': 0.7,           # High risk, use caution
    'WSB_CAPITULATION': 0.9,
    'PUMP_WARNING': 0.5,            # Avoid
    'SENTIMENT_FLIP': 0.9,
}


# ==================== DEFAULT CONFIG ====================

DEFAULT_CONFIG = RedditCheckerConfig()

