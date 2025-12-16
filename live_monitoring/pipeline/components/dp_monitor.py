"""
DP Monitor Component - Wrapper for DP Monitor Engine

Integrates with existing DPMonitorEngine and DP Learning Engine.
"""

import logging
from typing import Optional, Dict, Any, List, Callable

logger = logging.getLogger(__name__)


class DPMonitor:
    """
    Monitors Dark Pool levels and generates alerts.
    
    Wraps existing DPMonitorEngine for integration into modular pipeline.
    """
    
    def __init__(
        self,
        dp_monitor_engine,
        dp_learning_engine=None,
        symbols: List[str] = None,
        unified_mode: bool = False,
        alert_callback: Optional[Callable] = None
    ):
        """
        Initialize DP Monitor.
        
        Args:
            dp_monitor_engine: DPMonitorEngine instance
            dp_learning_engine: DPLearningEngine instance (optional)
            symbols: List of symbols to monitor
            unified_mode: If True, suppress individual alerts
            alert_callback: Function to call when alert should be sent
        """
        self.dp_monitor_engine = dp_monitor_engine
        self.dp_learning_engine = dp_learning_engine
        self.symbols = symbols or ['SPY', 'QQQ']
        self.unified_mode = unified_mode
        self.alert_callback = alert_callback
        
        # Buffer for synthesis
        self.recent_alerts: List = []
        
        logger.info("🔒 DPMonitor initialized")
    
    def check(self) -> Dict[str, Any]:
        """
        Check Dark Pool levels.
        
        NOTE: This modular component is NOT currently used.
        The deployed version uses run_all_monitors.py directly.
        
        Returns:
            Dict with alerts and buffered alerts for synthesis
        """
        result = {
            'alerts': [],
            'buffered': []
        }
        
        try:
            # Use existing engine to check all symbols
            alerts = self.dp_monitor_engine.check_all_symbols(self.symbols)
            
            if not alerts:
                logger.info("   📊 No DP alerts triggered (debounced or too far)")
                return result
            
            # Process each alert
            for alert in alerts:
                # Format for Discord
                embed = self.dp_monitor_engine.format_discord_alert(alert)
                
                # Generate content
                bg = alert.battleground
                ts = alert.trade_setup
                
                # Calculate expected move
                expected_move_pct = 0.0
                if ts:
                    if ts.direction.value == "LONG":
                        expected_move_pct = ((ts.target - ts.entry) / ts.entry) * 100
                    else:
                        expected_move_pct = ((ts.entry - ts.target) / ts.entry) * 100
                
                # Add warning for small moves
                warning = ""
                if expected_move_pct > 0 and expected_move_pct < 0.5:
                    warning = f" ⚠️ **SCALPING SIGNAL** - Small move expected (~{expected_move_pct:.2f}%)"
                elif expected_move_pct >= 0.5:
                    warning = f" ✅ **STRONGER MOVE** - Expected ~{expected_move_pct:.2f}%"
                
                if alert.alert_type.value == "AT_LEVEL":
                    if ts:
                        content = f"🚨 **{alert.symbol} AT {bg.level_type.value} ${bg.price:.2f}** | {ts.direction.value} opportunity | {bg.volume:,} shares{warning}"
                    else:
                        content = f"🚨 **{alert.symbol} AT BATTLEGROUND ${bg.price:.2f}** - {bg.volume:,} shares!{warning}"
                elif alert.alert_type.value == "APPROACHING":
                    content = f"⚠️ **{alert.symbol} APPROACHING** ${bg.price:.2f} ({bg.level_type.value}) | {bg.volume:,} shares{warning}"
                else:
                    content = f"📊 {alert.symbol} near DP level ${bg.price:.2f}{warning}"
                
                # Store for synthesis (ALWAYS)
                self.recent_alerts.append(alert)
                if len(self.recent_alerts) > 20:
                    self.recent_alerts = self.recent_alerts[-20:]
                
                # ALWAYS send scalping signals (don't suppress in unified mode)
                alert_dict = {
                    'type': 'dp_alert',
                    'embed': embed,
                    'content': content,
                    'source': 'dp_monitor',
                    'symbol': alert.symbol
                }
                
                result['alerts'].append(alert_dict)
                result['buffered'].append(alert)
                
                # Send via callback
                if self.alert_callback:
                    self.alert_callback(alert_dict)
                
                # Log to learning engine
                if self.dp_learning_engine:
                    interaction_id = self.dp_monitor_engine.log_to_learning_engine(alert)
                    if interaction_id:
                        logger.debug(f"   📝 Tracking interaction #{interaction_id}")
                
                logger.info(f"   ✅ DP ALERT: {alert.symbol} @ ${bg.price:.2f} ({alert.priority.value})")
            
        except Exception as e:
            logger.error(f"   ❌ DP check error: {e}")
            result['error'] = str(e)
        
        return result
    
    def get_buffered_alerts(self) -> List:
        """Get buffered alerts for synthesis"""
        return self.recent_alerts
    
    def clear_buffer(self):
        """Clear buffered alerts"""
        self.recent_alerts = []

