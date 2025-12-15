"""
Signal Brain Monitor Component - Wrapper for Signal Synthesis

Integrates with existing SignalBrainEngine for synthesis.
"""

import logging
import hashlib
from typing import Optional, Dict, Any, List, Callable

logger = logging.getLogger(__name__)


class SignalBrainMonitor:
    """
    Monitors and synthesizes signals using Signal Brain.
    
    Wraps existing SignalBrainEngine for integration into modular pipeline.
    """
    
    def __init__(
        self,
        signal_brain_engine,
        macro_provider=None,
        unified_mode: bool = True,
        alert_callback: Optional[Callable] = None
    ):
        """
        Initialize Signal Brain Monitor.
        
        Args:
            signal_brain_engine: SignalBrainEngine instance
            macro_provider: MacroContextProvider instance (optional)
            unified_mode: If True, suppress individual alerts
            alert_callback: Function to call when alert should be sent
        """
        self.signal_brain = signal_brain_engine
        self.macro_provider = macro_provider
        self.unified_mode = unified_mode
        self.alert_callback = alert_callback
        
        # Deduplication
        self.sent_synthesis_hashes = set()
        
        logger.info("🧠 SignalBrainMonitor initialized")
    
    def synthesize(
        self,
        dp_alerts: List,
        spy_price: float,
        qqq_price: float,
        spy_levels: List[Dict] = None,
        qqq_levels: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Synthesize signals from DP alerts.
        
        Args:
            dp_alerts: List of DP alerts to synthesize
            spy_price: Current SPY price
            qqq_price: Current QQQ price
            spy_levels: SPY DP levels (optional, if alerts not available)
            qqq_levels: QQQ DP levels (optional, if alerts not available)
        
        Returns:
            Dict with synthesis result and alerts
        """
        result = {
            'synthesis': None,
            'alert': None,
            'should_send': False
        }
        
        try:
            # Convert alerts to levels if needed
            if not spy_levels and not qqq_levels:
                spy_levels = []
                qqq_levels = []
                for alert in dp_alerts:
                    bg = alert.battleground
                    level_data = {
                        'price': bg.price,
                        'volume': bg.volume
                    }
                    if alert.symbol == 'SPY':
                        spy_levels.append(level_data)
                    elif alert.symbol == 'QQQ':
                        qqq_levels.append(level_data)
            
            if not spy_levels and not qqq_levels:
                logger.info("   📊 No DP levels available for synthesis")
                return result
            
            # Get macro context
            fed_sentiment = "NEUTRAL"
            trump_risk = "LOW"
            
            if self.macro_provider:
                try:
                    macro_context = self.macro_provider.get_context()
                    fed_sentiment = macro_context.fed_sentiment
                    trump_risk = macro_context.trump_risk
                except Exception as e:
                    logger.warning(f"   ⚠️ Macro context error: {e}")
            
            # Run synthesis
            synthesis_result = self.signal_brain.analyze(
                spy_levels=spy_levels,
                qqq_levels=qqq_levels,
                spy_price=spy_price,
                qqq_price=qqq_price,
                fed_sentiment=fed_sentiment,
                trump_risk=trump_risk,
            )
            
            result['synthesis'] = synthesis_result
            
            # Check if should send
            should_send = False
            if self.unified_mode and len(dp_alerts) > 0:
                should_send = True
                logger.info(f"   🧠 Unified mode: {len(dp_alerts)} alerts → Sending synthesis")
            elif self.signal_brain.should_alert(synthesis_result):
                should_send = True
            
            result['should_send'] = should_send
            
            if should_send:
                # Check for duplicates
                synthesis_hash = hashlib.md5(
                    f"{synthesis_result.confluence.score:.0f}:{synthesis_result.confluence.bias.value}:{spy_price:.2f}:{qqq_price:.2f}".encode()
                ).hexdigest()[:12]
                
                if synthesis_hash in self.sent_synthesis_hashes:
                    logger.debug(f"   📊 Synthesis duplicate (hash: {synthesis_hash[:8]}) - skipping")
                    return result
                
                # Create alert
                embed = self.signal_brain.to_discord(synthesis_result)
                content = f"🧠 **UNIFIED MARKET SYNTHESIS** | {synthesis_result.confluence.score:.0f}% {synthesis_result.confluence.bias.value}"
                
                if synthesis_result.recommendation and synthesis_result.recommendation.wait_for:
                    content += f" | ⏳ {synthesis_result.recommendation.wait_for}"
                elif synthesis_result.recommendation and synthesis_result.recommendation.action != "WAIT":
                    content += f" | 🎯 {synthesis_result.recommendation.action} SPY"
                
                alert_dict = {
                    'type': 'synthesis',
                    'embed': embed,
                    'content': content,
                    'source': 'signal_brain',
                    'symbol': 'SPY,QQQ'
                }
                
                result['alert'] = alert_dict
                
                # Track hash
                self.sent_synthesis_hashes.add(synthesis_hash)
                if len(self.sent_synthesis_hashes) > 10:
                    self.sent_synthesis_hashes = set(list(self.sent_synthesis_hashes)[-10:])
                
                # Send via callback
                if self.alert_callback:
                    self.alert_callback(alert_dict)
                
                logger.info(f"   ✅ UNIFIED SYNTHESIS ALERT SENT!")
            
        except Exception as e:
            logger.error(f"   ❌ Synthesis error: {e}")
            result['error'] = str(e)
        
        return result

