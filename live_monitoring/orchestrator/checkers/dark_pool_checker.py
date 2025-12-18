"""
Dark Pool Checker - Monitors dark pool battleground levels.

Extracted from unified_monitor.py for modularity.

Note: This checker focuses on DP alerts. Momentum detection and synthesis
are handled separately by the orchestrator.
"""

import logging
from datetime import datetime
from typing import List, Optional, Callable

from .base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


class DarkPoolChecker(BaseChecker):
    """
    Checks dark pool battleground levels and generates alerts.
    
    Responsibilities:
    - Monitor DP levels for SPY/QQQ
    - Generate alerts when price approaches battlegrounds
    - Track recent DP alerts for synthesis
    - Handle DP interaction outcomes
    """
    
    def __init__(
        self,
        alert_manager,
        dp_monitor_engine=None,
        symbols: List[str] = None,
        unified_mode: bool = False,
        on_synthesis_trigger: Optional[Callable] = None
    ):
        """
        Initialize Dark Pool checker.
        
        Args:
            alert_manager: AlertManager instance
            dp_monitor_engine: DPMonitorEngine instance (optional)
            symbols: List of symbols to monitor (default: ['SPY', 'QQQ'])
            unified_mode: Whether unified mode is enabled
            on_synthesis_trigger: Callback when synthesis should be triggered
        """
        super().__init__(alert_manager)
        self.dp_monitor_engine = dp_monitor_engine
        self.symbols = symbols or ['SPY', 'QQQ']
        self.unified_mode = unified_mode
        self.on_synthesis_trigger = on_synthesis_trigger
        
        # State tracking
        self.recent_dp_alerts = []
    
    @property
    def name(self) -> str:
        return "dark_pool_checker"
    
    def check(self) -> List[CheckerAlert]:
        """
        Check dark pool levels.
        
        Returns:
            List of CheckerAlert objects
        """
        alerts = []
        
        if not self.dp_monitor_engine:
            return alerts
        
        logger.info("🔒 Checking Dark Pool levels (modular)...")
        
        try:
            # Check DP levels
            dp_alerts = self.dp_monitor_engine.check_all_symbols(self.symbols)
            
            if not dp_alerts:
                logger.info("   📊 No DP alerts triggered")
                return alerts
            
            logger.info(f"   ✅ Generated {len(dp_alerts)} DP alerts")
            
            for alert in dp_alerts:
                embed = self.dp_monitor_engine.format_discord_alert(alert)
                bg = alert.battleground
                ts = alert.trade_setup
                
                if ts:
                    content = f"🚨 **{alert.symbol} AT {bg.level_type.value} ${bg.price:.2f}** | {ts.direction.value} opportunity | {bg.volume:,} shares"
                else:
                    content = f"🚨 **{alert.symbol} AT BATTLEGROUND ${bg.price:.2f}** - {bg.volume:,} shares!"
                
                # Track recent alerts for synthesis
                self.recent_dp_alerts.append(alert)
                if len(self.recent_dp_alerts) > 20:
                    self.recent_dp_alerts = self.recent_dp_alerts[-20:]
                
                # In unified mode, buffer alerts instead of sending immediately
                if not self.unified_mode:
                    alerts.append(CheckerAlert(
                        embed=embed,
                        content=content,
                        alert_type="dp_alert",
                        source="dp_monitor",
                        symbol=alert.symbol
                    ))
                    logger.info(f"   📤 DP alert queued for immediate send: {alert.symbol} @ ${bg.price:.2f}")
                else:
                    logger.info(f"   🔇 DP alert buffered (unified mode): {alert.symbol} @ ${bg.price:.2f} (will send via synthesis)")
            
            # Trigger synthesis if we have enough alerts
            if len(self.recent_dp_alerts) >= 2 and self.on_synthesis_trigger:
                self.on_synthesis_trigger()
                    
        except Exception as e:
            logger.error(f"   ❌ Modular DP check error: {e}")
        
        return alerts
    
    def get_recent_alerts(self) -> List:
        """
        Get recent DP alerts (for synthesis checker).
        
        Returns:
            List of recent DPAlert objects
        """
        return self.recent_dp_alerts.copy()
    
    def clear_recent_alerts(self):
        """Clear recent alerts (called after synthesis)."""
        self.recent_dp_alerts = []
    
    def on_dp_outcome(self, interaction_id: int, outcome) -> Optional[CheckerAlert]:
        """
        Handle DP interaction outcome callback.
        
        Args:
            interaction_id: Interaction ID
            outcome: Outcome object
            
        Returns:
            CheckerAlert if should send, None otherwise
        """
        if self.unified_mode:
            return None
        
        try:
            outcome_emoji = {
                'BOUNCE': '✅ LEVEL HELD',
                'BREAK': '❌ LEVEL BROKE',
                'FADE': '⚪ NO CLEAR OUTCOME'
            }.get(outcome.outcome.value, '❓ UNKNOWN')
            
            embed = {
                "title": f"🎯 DP OUTCOME: {outcome_emoji}",
                "color": 3066993 if outcome.outcome.value == 'BOUNCE' else 15158332,
                "description": f"Interaction #{interaction_id} resolved after {outcome.time_to_outcome_min} min",
                "fields": [
                    {"name": "📊 Max Move", "value": f"{outcome.max_move_pct:+.2f}%", "inline": True},
                    {"name": "⏱️ Tracking Time", "value": f"{outcome.time_to_outcome_min} min", "inline": True},
                ],
                "footer": {"text": "Learning from this outcome... Patterns updated!"},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return CheckerAlert(
                embed=embed,
                content="",
                alert_type="dp_outcome",
                source="dp_learning",
                symbol=None
            )
        except Exception as e:
            logger.error(f"❌ Outcome alert error: {e}")
            return None

