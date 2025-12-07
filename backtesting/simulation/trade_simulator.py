"""
💰 TRADE SIMULATOR
Simulates individual trades with realistic entry/exit logic
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple
from ..data.loader import DPAlert
from ..config.trading_params import TradingParams

@dataclass
class Trade:
    """Represents a simulated trade"""
    entry_time: datetime
    symbol: str
    direction: str  # LONG or SHORT
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_time: Optional[datetime]
    exit_price: Optional[float]
    pnl_pct: float
    outcome: str  # WIN, LOSS, or PENDING
    alert_confluence: float
    max_move_observed: float

class TradeSimulator:
    """Simulates trades from DP alerts"""
    
    def __init__(self, params: TradingParams):
        self.params = params
    
    def simulate_trade(self, alert: DPAlert) -> Trade:
        """
        Simulate a trade from a DP alert
        
        Uses outcome data (max_move_pct) to determine if trade wins or loses
        """
        # Determine trade direction
        if alert.level_type == 'SUPPORT':
            direction = 'LONG'
            entry_price = alert.level_price
            stop_loss = entry_price * (1 - self.params.stop_loss_pct / 100)
            take_profit = entry_price * (1 + self.params.take_profit_pct / 100)
        else:  # RESISTANCE
            direction = 'SHORT'
            entry_price = alert.level_price
            stop_loss = entry_price * (1 + self.params.stop_loss_pct / 100)
            take_profit = entry_price * (1 - self.params.take_profit_pct / 100)
        
        # Determine outcome based on alert outcome and move size
        pnl_pct, outcome = self._calculate_outcome(
            alert=alert,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        return Trade(
            entry_time=alert.timestamp,
            symbol=alert.symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            exit_time=None,  # Not tracking exact exit time
            exit_price=None,
            pnl_pct=pnl_pct,
            outcome=outcome,
            alert_confluence=alert.confluence_score,
            max_move_observed=alert.max_move_pct
        )
    
    def _calculate_outcome(self, alert: DPAlert, direction: str, entry_price: float, 
                          stop_loss: float, take_profit: float) -> Tuple[float, str]:
        """
        Calculate trade outcome based on alert outcome and move size
        
        Returns:
            (pnl_pct, outcome) tuple
        """
        if alert.level_type == 'SUPPORT':
            if alert.outcome == 'BOUNCE':
                # Long trade: wins if move >= take profit
                if alert.max_move_pct >= self.params.take_profit_pct:
                    return (self.params.take_profit_pct, 'WIN')
                else:
                    # Move too small, hit stop
                    return (-self.params.stop_loss_pct, 'LOSS')
            else:  # BREAK
                # Long trade loses on break
                return (-self.params.stop_loss_pct, 'LOSS')
        else:  # RESISTANCE
            if alert.outcome == 'BOUNCE':
                # Short trade: wins if move >= take profit
                if alert.max_move_pct >= self.params.take_profit_pct:
                    return (self.params.take_profit_pct, 'WIN')
                else:
                    # Move too small, hit stop
                    return (-self.params.stop_loss_pct, 'LOSS')
            else:  # BREAK
                # Short trade loses on break
                return (-self.params.stop_loss_pct, 'LOSS')

