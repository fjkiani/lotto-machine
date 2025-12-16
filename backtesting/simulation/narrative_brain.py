"""
🧠 NARRATIVE BRAIN SIMULATOR
Simulates Narrative Brain decision logic (smart filtering)
"""

from datetime import datetime, timedelta
from typing import List, Optional
from ..data.loader import DPAlert
from ..simulation.trade_simulator import TradeSimulator, Trade
from ..config.trading_params import TradingParams

class NarrativeBrainSimulator:
    """Simulates Narrative Brain: only sends when confluence is high"""
    
    def __init__(self, trade_simulator: TradeSimulator, params: TradingParams):
        self.trade_simulator = trade_simulator
        self.params = params
        self.last_alert_time: Optional[datetime] = None
    
    def simulate(self, alerts: List[DPAlert]) -> List[Trade]:
        """
        Simulate Narrative Brain behavior
        
        Logic:
        - Groups alerts into 2-minute windows
        - Calculates average confluence
        - Only sends if:
          * Confluence >= 80 (exceptional)
          * Confluence >= 70 + 3+ alerts (strong confirmation)
          * 5+ alerts (critical mass)
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
            
            # Check if we should evaluate (every 2 minutes)
            time_check = (
                last_send_time is None or
                (window_time - last_send_time).total_seconds() >= self.params.synthesis_interval_seconds
            )
            
            if time_check and buffer:
                # Calculate average confluence
                avg_confluence = sum(a.confluence_score for a in buffer) / len(buffer)
                
                # Narrative Brain decision logic
                should_send = self._should_send_alert(
                    avg_confluence=avg_confluence,
                    alert_count=len(buffer),
                    time_since_last=self._get_time_since_last()
                )
                
                if should_send:
                    # Trade on best alert in batch
                    best_alert = max(buffer, key=lambda a: a.confluence_score)
                    trade = self.trade_simulator.simulate_trade(best_alert)
                    trades.append(trade)
                    
                    last_send_time = window_time
                    self.last_alert_time = window_time
                    buffer = []  # Clear buffer after sending
                # If not sending, keep buffer for next check
        
        return trades
    
    def _should_send_alert(self, avg_confluence: float, alert_count: int, time_since_last: timedelta) -> bool:
        """Determine if alert should be sent based on Narrative Brain logic"""
        # Exceptional confluence
        if avg_confluence >= self.params.narrative_exceptional_confluence:
            return True
        
        # Strong confluence with confirmation
        if avg_confluence >= self.params.narrative_min_confluence and alert_count >= self.params.narrative_min_alerts:
            return True
        
        # Critical mass
        if alert_count >= self.params.narrative_critical_mass:
            return True
        
        # Been very quiet (12+ hours)
        if time_since_last >= timedelta(hours=12):
            if avg_confluence >= 60 and alert_count >= 2:
                return True
        
        return False
    
    def _get_time_since_last(self) -> timedelta:
        """Get time since last alert"""
        if self.last_alert_time:
            return datetime.now() - self.last_alert_time
        return timedelta(hours=6)  # Default: been quiet



