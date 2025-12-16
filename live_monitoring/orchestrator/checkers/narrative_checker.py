"""
Narrative Checker - Generates high-quality narrative brain signals.

Extracted from unified_monitor.py for modularity.

This checker analyzes recent DP alerts and generates narrative signals
when confluence thresholds are met. It includes strict filtering for
regime conflicts, synthesis conflicts, and direction locks.
"""

import logging
import time
from datetime import datetime
from typing import List, Optional, Callable

from .base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


class NarrativeChecker(BaseChecker):
    """
    Checks Narrative Brain decision logic and generates high-quality signals.
    
    Responsibilities:
    - Calculate confluence from recent DP alerts
    - Apply strict filtering (regime, synthesis, direction locks)
    - Generate narrative brain signals when thresholds met
    - Manage cooldowns and direction locks
    """
    
    def __init__(
        self,
        alert_manager,
        narrative_brain=None,
        regime_detector=None,
        dp_monitor_engine=None,
        unified_mode=False
    ):
        """
        Initialize Narrative checker.
        
        Args:
            alert_manager: AlertManager instance for deduplication
            narrative_brain: NarrativeBrain instance (optional)
            regime_detector: RegimeDetector instance for market regime
            dp_monitor_engine: DPMonitorEngine instance for trade calculator
            unified_mode: If True, suppresses individual alerts
        """
        super().__init__(alert_manager, unified_mode)
        self.narrative_brain = narrative_brain
        self.regime_detector = regime_detector
        self.dp_monitor_engine = dp_monitor_engine
        
        # State management
        self.last_narrative_sent = None
        self._last_symbol_directions = {}
        self._last_level_directions = {}
        self._last_regime_details = {}
    
    def check(
        self,
        recent_dp_alerts: List,
        synthesis_result,
        spy_price: float,
        qqq_price: float
    ) -> List[CheckerAlert]:
        """
        Check for narrative brain signals.
        
        Args:
            recent_dp_alerts: List of recent DP alerts
            synthesis_result: Synthesis result object
            spy_price: Current SPY price
            qqq_price: Current QQQ price
            
        Returns:
            List of CheckerAlert objects (empty if no signal)
        """
        if not self.narrative_brain or not recent_dp_alerts:
            return []
        
        try:
            # Calculate average confluence from recent alerts
            def get_alert_confluence(alert):
                """Calculate confluence score for an alert"""
                score = 50
                bg = alert.battleground
                if bg.volume >= 2_000_000:
                    score += 30
                elif bg.volume >= 1_000_000:
                    score += 20
                elif bg.volume >= 500_000:
                    score += 10
                if alert.priority.value == "CRITICAL":
                    score += 20
                elif alert.priority.value == "HIGH":
                    score += 10
                if alert.alert_type.value == "AT_LEVEL":
                    score += 10
                if alert.ai_prediction and alert.ai_prediction > 0.7:
                    score += 10
                return min(score, 100)
            
            avg_confluence = sum(
                get_alert_confluence(alert) 
                for alert in recent_dp_alerts
            ) / len(recent_dp_alerts)
            
            # Narrative Brain decision logic
            min_confluence = 70.0
            min_alerts = 3
            critical_mass = 5
            exceptional_confluence = 80.0
            
            should_send = False
            reason = ""
            
            if avg_confluence >= exceptional_confluence:
                should_send = True
                reason = f"Exceptional confluence ({avg_confluence:.0f}%)"
            elif avg_confluence >= min_confluence and len(recent_dp_alerts) >= min_alerts:
                should_send = True
                reason = f"Strong confluence ({avg_confluence:.0f}%) + {len(recent_dp_alerts)} alerts"
            elif len(recent_dp_alerts) >= critical_mass:
                should_send = True
                reason = f"Critical mass ({len(recent_dp_alerts)} alerts)"
            
            if not should_send:
                return []
            
            # Cooldown check
            current_time = time.time()
            if self.last_narrative_sent:
                elapsed = current_time - self.last_narrative_sent
                if elapsed < 300:
                    logger.debug(f"   ⏭️ Narrative Brain on cooldown ({elapsed:.0f}s < 300s)")
                    return []
            
            best_alert = max(recent_dp_alerts, key=get_alert_confluence)
            bg = best_alert.battleground
            
            # CRITICAL FIX: Recalculate trade setup with CURRENT price!
            # The cached trade setup may have stale entry prices from minutes ago
            current_price = spy_price if bg.symbol == 'SPY' else qqq_price
            if self.dp_monitor_engine:
                ts = self.dp_monitor_engine.trade_calculator.calculate_setup(bg, current_price=current_price)
                logger.debug(f"   📊 Recalculated trade setup: Entry ${ts.entry:.2f} (current price: ${current_price:.2f})")
            else:
                ts = best_alert.trade_setup  # Fallback to cached
                logger.warning(f"   ⚠️ Using cached trade setup (no trade_calculator available)")
            
            # Regime-aware filtering
            market_regime = self._detect_market_regime(spy_price)
            signal_direction = ts.direction.value if ts else "UNKNOWN"
            
            regime_details = self._last_regime_details
            bullish_signals = regime_details.get('bullish_signals', 0)
            bearish_signals = regime_details.get('bearish_signals', 0)
            
            # STRONG regimes = HARD BLOCK
            if market_regime == "STRONG_DOWNTREND" and signal_direction == "LONG":
                logger.warning(f"   ⛔ REGIME FILTER: Blocking LONG in STRONG DOWNTREND")
                return []
            
            if market_regime == "STRONG_UPTREND" and signal_direction == "SHORT":
                logger.warning(f"   ⛔ REGIME FILTER: Blocking SHORT in STRONG UPTREND")
                return []
            
            # Normal downtrend = block LONG unless exceptional
            if market_regime == "DOWNTREND" and signal_direction == "LONG":
                if avg_confluence < 90:
                    logger.warning(f"   ⛔ REGIME FILTER: Blocking LONG in DOWNTREND (confluence {avg_confluence:.0f}% < 90%)")
                    return []
            
            # Normal uptrend = block SHORT unless exceptional
            if market_regime == "UPTREND" and signal_direction == "SHORT":
                if avg_confluence < 90:
                    logger.warning(f"   ⛔ REGIME FILTER: Blocking SHORT in UPTREND (confluence {avg_confluence:.0f}% < 90%)")
                    return []
            
            # Synthesis-signal alignment - STRICT! No conflicting signals allowed
            synthesis_bias = synthesis_result.confluence.bias.value if synthesis_result and hasattr(synthesis_result, 'confluence') else "NEUTRAL"
            synthesis_score = synthesis_result.confluence.score if synthesis_result and hasattr(synthesis_result, 'confluence') else 50
            
            # HARD BLOCK any synthesis conflict (lowered threshold from 60 to 40)
            if synthesis_bias == "BEARISH" and signal_direction == "LONG":
                if synthesis_score >= 40:  # More strict - block even weak bearish
                    logger.warning(f"   ⛔ SYNTHESIS CONFLICT: Blocking LONG (synthesis {synthesis_score:.0f}% BEARISH)")
                    return []
            
            if synthesis_bias == "BULLISH" and signal_direction == "SHORT":
                if synthesis_score >= 40:  # More strict - block even weak bullish
                    logger.warning(f"   ⛔ SYNTHESIS CONFLICT: Blocking SHORT (synthesis {synthesis_score:.0f}% BULLISH)")
                    return []
            
            # Also check for regime-synthesis alignment
            if market_regime == "DOWNTREND" and synthesis_bias == "BULLISH":
                logger.warning(f"   ⚠️ REGIME-SYNTHESIS MISMATCH: Regime={market_regime}, Synthesis={synthesis_bias}")
                # Don't block, but log the inconsistency
            
            # ═══════════════════════════════════════════════════════════════
            # GLOBAL DIRECTION LOCK - No flip-flopping between LONG/SHORT!
            # ═══════════════════════════════════════════════════════════════
            symbol_key = bg.symbol
            if symbol_key in self._last_symbol_directions:
                last_direction, last_time = self._last_symbol_directions[symbol_key]
                elapsed = current_time - last_time
                
                # Block opposite direction for 10 minutes (600 seconds)
                if last_direction != signal_direction and elapsed < 600:
                    logger.warning(f"   ⛔ DIRECTION LOCK: {bg.symbol} already committed to {last_direction} ({elapsed:.0f}s ago)")
                    logger.warning(f"      → Blocking {signal_direction} signal to prevent flip-flopping")
                    return []
            
            # Record this direction for the symbol
            self._last_symbol_directions[symbol_key] = (signal_direction, current_time)
            
            # Clean up old entries (older than 30 min)
            self._last_symbol_directions = {
                k: v for k, v in self._last_symbol_directions.items() 
                if current_time - v[1] < 1800
            }
            
            # Level-direction cooldown (original - kept for same-level protection)
            level_key = f"{bg.symbol}_{bg.price:.2f}"
            if level_key in self._last_level_directions:
                last_direction, last_time = self._last_level_directions[level_key]
                elapsed = current_time - last_time
                
                if last_direction != signal_direction and elapsed < 600:
                    logger.warning(f"   ⛔ FLIP PREVENTION: Same level ${bg.price:.2f} flipped from {last_direction} to {signal_direction}")
                    return []
            
            self._last_level_directions[level_key] = (signal_direction, current_time)
            self._last_level_directions = {
                k: v for k, v in self._last_level_directions.items() 
                if current_time - v[1] < 1800
            }
            
            # Create alert
            embed = {
                "title": f"🧠 **NARRATIVE BRAIN SIGNAL** - {best_alert.symbol}",
                "description": f"**Higher Quality Signal** - Better move predictability\n\n"
                               f"**Reason:** {reason}\n"
                               f"**Confluence:** {avg_confluence:.0f}%\n"
                               f"**Alerts Confirmed:** {len(recent_dp_alerts)}\n"
                               f"**Regime:** {market_regime} | **Synthesis:** {synthesis_bias}",
                "color": 0x00ff00,
                "fields": []
            }
            
            if ts:
                embed["fields"].extend([{
                    "name": "🎯 Trade Setup",
                    "value": f"**Direction:** {ts.direction.value}\n"
                            f"**Entry:** ${ts.entry:.2f}\n"
                            f"**Stop:** ${ts.stop:.2f}\n"
                            f"**Target:** ${ts.target:.2f}\n"
                            f"**R/R:** {ts.risk_reward:.1f}:1",
                    "inline": False
                }])
            
            embed["fields"].append({
                "name": "📊 Battleground",
                "value": f"**Level:** ${bg.price:.2f} ({bg.level_type.value})\n"
                        f"**Volume:** {bg.volume:,} shares",
                "inline": False
            })
            
            content = f"🧠 **NARRATIVE BRAIN SIGNAL** | {best_alert.symbol} | {reason} | ✅ **HIGHER QUALITY**"
            
            logger.info(f"   🧠 Narrative Brain: Sending HIGH-QUALITY signal ({reason})")
            
            # Update state
            self.last_narrative_sent = current_time
            
            return [CheckerAlert(
                embed=embed,
                content=content,
                alert_type="narrative_brain",
                source="narrative_checker",
                symbol=best_alert.symbol
            )]
                
        except Exception as e:
            logger.error(f"   ❌ Narrative Brain check error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def _detect_market_regime(self, current_price: float) -> str:
        """Detect market regime (delegates to RegimeDetector)."""
        if not self.regime_detector:
            return "NEUTRAL"
        
        regime = self.regime_detector.detect(current_price)
        details = self.regime_detector.get_regime_details(current_price)
        self._last_regime_details = details
        return regime

