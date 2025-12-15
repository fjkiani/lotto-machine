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
        Check Dark Pool levels + Selloff Detection.
        
        Returns:
            Dict with alerts and buffered alerts for synthesis
        """
        result = {
            'alerts': [],
            'buffered': []
        }
        
        try:
            # ═══════════════════════════════════════════════════════════════
            # 🚨 SELLOFF DETECTION (Real-time momentum)
            # Check for selloffs BEFORE checking DP levels
            # ═══════════════════════════════════════════════════════════════
            selloff_alerts = self._check_selloffs()
            if selloff_alerts:
                result['alerts'].extend(selloff_alerts)
            
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
    
    def _check_selloffs(self) -> List[Dict[str, Any]]:
        """
        🚨 REAL-TIME SELLOFF DETECTION
        
        Detects rapid price drops with volume spikes (momentum-based).
        This catches selloffs that happen BEFORE price reaches battlegrounds.
        
        Threshold: -0.5% drop in 20 minutes with 1.5x volume spike
        """
        selloff_alerts = []
        
        try:
            from live_monitoring.core.signal_generator import SignalGenerator
            from live_monitoring.core.ultra_institutional_engine import UltraInstitutionalEngine
            import yfinance as yf
            from datetime import datetime, timedelta
            import os
            
            # Initialize SignalGenerator if needed
            if not hasattr(self, '_signal_generator') or self._signal_generator is None:
                try:
                    api_key = os.getenv('CHARTEXCHANGE_API_KEY')
                    self._signal_generator = SignalGenerator(api_key=api_key)
                except Exception as e:
                    logger.debug(f"   ⚠️ SignalGenerator not available for selloff detection: {e}")
                    return selloff_alerts
            
            for symbol in self.symbols:
                try:
                    # Get recent minute bars (last 30 minutes)
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='1d', interval='1m')
                    
                    if hist.empty or len(hist) < 20:
                        continue
                    
                    # Get last 30 bars for selloff detection
                    minute_bars = hist.tail(30)
                    current_price = float(minute_bars['Close'].iloc[-1])
                    
                    # Get institutional context (for selloff detector)
                    inst_context = None
                    try:
                        from core.ultra_institutional_engine import UltraInstitutionalEngine
                        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                        inst_engine = UltraInstitutionalEngine(api_key=os.getenv('CHARTEXCHANGE_API_KEY'))
                        inst_context = inst_engine.build_context(symbol, yesterday)
                    except Exception as e:
                        logger.debug(f"   ⚠️ Could not build institutional context for selloff: {e}")
                    
                    # Check for selloff
                    selloff_signal = self._signal_generator._detect_realtime_selloff(
                        symbol=symbol,
                        current_price=current_price,
                        minute_bars=minute_bars,
                        context=inst_context
                    )
                    
                    if selloff_signal:
                        logger.warning(f"   🚨 SELLOFF DETECTED: {symbol} @ ${current_price:.2f}")
                        logger.warning(f"      → Confidence: {selloff_signal.confidence:.0%}")
                        logger.warning(f"      → Action: {selloff_signal.action.value}")
                        
                        # Create alert dict
                        embed = {
                            "title": f"🚨 **REAL-TIME SELLOFF** - {symbol}",
                            "description": selloff_signal.rationale or "Rapid price drop with volume spike detected",
                            "color": 0xff0000,  # Red for selloff
                            "fields": [
                                {
                                    "name": "🎯 Trade Setup",
                                    "value": f"**Action:** {selloff_signal.action.value}\n"
                                            f"**Entry:** ${selloff_signal.entry_price:.2f}\n"
                                            f"**Stop:** ${selloff_signal.stop_price:.2f}\n"
                                            f"**Target:** ${selloff_signal.target_price:.2f}\n"
                                            f"**Confidence:** {selloff_signal.confidence:.0%}",
                                    "inline": False
                                }
                            ],
                            "footer": {"text": "Real-time momentum detection"},
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        content = f"🚨 **REAL-TIME SELLOFF** | {symbol} | {selloff_signal.action.value} @ ${current_price:.2f}"
                        
                        alert_dict = {
                            'type': 'selloff',
                            'embed': embed,
                            'content': content,
                            'source': 'selloff_detector',
                            'symbol': symbol
                        }
                        
                        selloff_alerts.append(alert_dict)
                        
                        # Send via callback
                        if self.alert_callback:
                            self.alert_callback(alert_dict)
                            
                except Exception as e:
                    logger.debug(f"   ⚠️ Selloff check error for {symbol}: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"   ⚠️ Selloff detection error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        return selloff_alerts
    
    def get_buffered_alerts(self) -> List:
        """Get buffered alerts for synthesis"""
        return self.recent_alerts
    
    def clear_buffer(self):
        """Clear buffered alerts"""
        self.recent_alerts = []

