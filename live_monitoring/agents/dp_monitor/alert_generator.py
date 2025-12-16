"""
🔒 DP Monitor - Alert Generator
================================
Smart alerts with debouncing and trade direction.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .models import (
    Battleground, DPAlert, AlertType, AlertPriority, 
    LevelType, TradeDirection, TradeSetup
)
from .trade_calculator import TradeCalculator

logger = logging.getLogger(__name__)


class AlertGenerator:
    """
    Generates smart DP alerts with:
    - Debouncing (no spam)
    - Trade direction (LONG/SHORT)
    - Volume-based priority
    """
    
    # Distance thresholds for alert types
    DISTANCE_THRESHOLDS = {
        AlertType.AT_LEVEL: 0.10,      # 0.10%
        AlertType.APPROACHING: 0.30,   # 0.30%
        AlertType.NEAR: 0.50,          # 0.50%
    }
    
    def __init__(self, debounce_minutes: int = 30):
        """
        Args:
            debounce_minutes: Minimum time between alerts for same level
        """
        self.debounce_minutes = debounce_minutes
        self.trade_calculator = TradeCalculator()
        
        # Track last alert time per level: {symbol_price -> datetime}
        self._last_alerts: Dict[str, datetime] = {}
        
        # Track which levels we've already alerted on this cycle
        self._alerted_this_cycle: set = set()
    
    def generate_alerts(
        self, 
        battlegrounds: List[Battleground],
        ai_predictions: Optional[Dict[float, dict]] = None,
        current_price: float = None
    ) -> List[DPAlert]:
        """
        Generate alerts for battlegrounds that warrant attention.
        
        Args:
            battlegrounds: List of analyzed battlegrounds
            ai_predictions: Optional predictions from learning engine
                           {level_price -> {'probability': float, 'confidence': str, 'patterns': list}}
            current_price: Current market price for REAL-TIME entries (REQUIRED!)
        
        Returns:
            List of DPAlert objects for levels that should be alerted
        """
        alerts = []
        ai_predictions = ai_predictions or {}
        
        for bg in battlegrounds:
            # Skip if no distance calculated
            if bg.distance_pct is None:
                continue
            
            # Determine alert type based on distance
            alert_type = self._get_alert_type(bg.distance_pct)
            if alert_type is None:
                continue  # Too far away
            
            # Check debounce
            level_key = f"{bg.symbol}_{bg.price:.2f}"
            if self._should_debounce(level_key, alert_type):
                continue
            
            # Determine priority
            priority = self._get_priority(bg, alert_type)
            
            # Calculate trade setup with CURRENT PRICE for real-time entries
            trade_setup = self.trade_calculator.calculate_setup(bg, current_price=current_price)
            
            # Get AI prediction if available
            ai_pred = ai_predictions.get(bg.price, {})
            
            # Create alert
            alert = DPAlert(
                symbol=bg.symbol,
                battleground=bg,
                alert_type=alert_type,
                priority=priority,
                timestamp=datetime.now(),
                trade_setup=trade_setup,
                ai_prediction=ai_pred.get('probability'),
                ai_confidence=ai_pred.get('confidence'),
                ai_patterns=ai_pred.get('patterns'),
            )
            
            # Record this alert
            self._last_alerts[level_key] = datetime.now()
            
            alerts.append(alert)
            logger.debug(f"📢 Alert generated: {bg.symbol} @ ${bg.price:.2f} ({alert_type.value})")
        
        return alerts
    
    def _get_alert_type(self, distance_pct: float) -> Optional[AlertType]:
        """Determine alert type based on distance."""
        if distance_pct <= self.DISTANCE_THRESHOLDS[AlertType.AT_LEVEL]:
            return AlertType.AT_LEVEL
        elif distance_pct <= self.DISTANCE_THRESHOLDS[AlertType.APPROACHING]:
            return AlertType.APPROACHING
        elif distance_pct <= self.DISTANCE_THRESHOLDS[AlertType.NEAR]:
            return AlertType.NEAR
        return None
    
    def _should_debounce(self, level_key: str, alert_type: AlertType) -> bool:
        """
        Check if we should debounce this alert.
        
        AT_LEVEL alerts get shorter debounce (5 min)
        APPROACHING/NEAR get longer debounce (30 min)
        """
        if level_key not in self._last_alerts:
            return False
        
        last_time = self._last_alerts[level_key]
        elapsed = (datetime.now() - last_time).total_seconds() / 60
        
        # AT_LEVEL is more urgent, shorter debounce
        if alert_type == AlertType.AT_LEVEL:
            return elapsed < 5  # 5 minute debounce for AT_LEVEL
        else:
            return elapsed < self.debounce_minutes
    
    def _get_priority(self, bg: Battleground, alert_type: AlertType) -> AlertPriority:
        """Determine alert priority based on volume and distance."""
        # Volume-based priority
        if bg.volume >= 2_000_000:
            base_priority = AlertPriority.CRITICAL
        elif bg.volume >= 1_000_000:
            base_priority = AlertPriority.HIGH
        elif bg.volume >= 500_000:
            base_priority = AlertPriority.MEDIUM
        else:
            base_priority = AlertPriority.LOW
        
        # Upgrade priority if AT_LEVEL
        if alert_type == AlertType.AT_LEVEL:
            if base_priority == AlertPriority.MEDIUM:
                return AlertPriority.HIGH
            elif base_priority == AlertPriority.LOW:
                return AlertPriority.MEDIUM
        
        return base_priority
    
    def reset_cycle(self):
        """Reset cycle tracking (call at start of each check cycle)."""
        self._alerted_this_cycle.clear()
    
    def clear_debounce(self, symbol: Optional[str] = None):
        """Clear debounce tracking."""
        if symbol:
            keys_to_remove = [k for k in self._last_alerts if k.startswith(symbol)]
            for k in keys_to_remove:
                del self._last_alerts[k]
        else:
            self._last_alerts.clear()
    
    def get_stats(self) -> dict:
        """Get alert generator stats."""
        return {
            'levels_tracked': len(self._last_alerts),
            'debounce_minutes': self.debounce_minutes,
        }





