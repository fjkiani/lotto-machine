"""
📊 CURRENT SYSTEM SIMULATOR
Simulates the current system behavior (always sends if alerts exist)
"""

from datetime import datetime, timedelta
from typing import List
from ..data.loader import DPAlert
from ..simulation.trade_simulator import TradeSimulator, Trade
from ..config.trading_params import TradingParams

class CurrentSystemSimulator:
    """Simulates current system: sends synthesis every 2 min if alerts exist"""
    
    def __init__(self, trade_simulator: TradeSimulator, params: TradingParams):
        self.trade_simulator = trade_simulator
        self.params = params
    
    def simulate(self, alerts: List[DPAlert]) -> List[Trade]:
        """
        Simulate current system behavior
        
        Logic:
        - Groups alerts into 2-minute windows
        - Sends synthesis if been 2+ minutes since last send
        - Trades on best alert in batch
        """
        trades = []
        buffer = []
        last_send_time = None
        
        for alert in alerts:
            # Round to 2-minute window
            window_time = alert.timestamp.replace(
                minute=alert.timestamp.minute // 2 * 2,
                second=0,
                microsecond=0
            )
            
            buffer.append(alert)
            
            # Check if we should send (every 2 minutes)
            should_send = (
                last_send_time is None or
                (window_time - last_send_time).total_seconds() >= self.params.synthesis_interval_seconds
            )
            
            if should_send and buffer:
                # Current system: Trade on best alert in batch
                best_alert = max(buffer, key=lambda a: a.confluence_score)
                trade = self.trade_simulator.simulate_trade(best_alert)
                trades.append(trade)
                
                last_send_time = window_time
                buffer = []  # Clear buffer after sending
        
        return trades


