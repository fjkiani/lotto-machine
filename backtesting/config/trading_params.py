"""
📊 TRADING PARAMETERS CONFIGURATION
Configurable parameters for backtesting
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class TradingParams:
    """Trading parameters for backtesting"""
    
    # Risk Management
    stop_loss_pct: float = 0.25  # Stop loss percentage
    take_profit_pct: float = 0.40  # Take profit percentage
    
    # Position Sizing
    position_size_pct: float = 2.0  # Position size as % of capital
    
    # System Timing
    synthesis_interval_seconds: int = 120  # How often synthesis runs (2 min)
    
    # Narrative Brain Thresholds
    narrative_min_confluence: float = 70.0  # Minimum confluence to send
    narrative_min_alerts: int = 3  # Minimum alerts for confirmation
    narrative_critical_mass: int = 5  # Critical mass of alerts
    narrative_exceptional_confluence: float = 80.0  # Exceptional threshold
    
    # Current System Thresholds (for comparison)
    current_min_confluence: float = 0.0  # Current system sends all (0 = no filter)
    
    def __post_init__(self):
        """Validate parameters"""
        assert 0 < self.stop_loss_pct < 1, "Stop loss must be between 0 and 1"
        assert 0 < self.take_profit_pct < 1, "Take profit must be between 0 and 1"
        assert self.stop_loss_pct < self.take_profit_pct, "Take profit must be > stop loss"
        assert 0 < self.position_size_pct <= 10, "Position size must be reasonable"

# Default configuration
DEFAULT_PARAMS = TradingParams()


