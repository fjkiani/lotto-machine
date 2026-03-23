"""
Gamma Checker - Detects gamma ramp opportunities.

Extracted from unified_monitor.py for modularity.

This checker analyzes options open interest and max pain to detect
gamma ramp setups (bullish or bearish).
"""

import logging
from datetime import datetime
from typing import List, Optional

from .base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


class GammaChecker(BaseChecker):
    """
    Checks for gamma ramp setups.
    
    Responsibilities:
    - Analyze options OI and max pain for multiple symbols
    - Check nearest and weekly expirations
    - Generate alerts for gamma signals
    """
    
    def __init__(
        self,
        alert_manager,
        gamma_tracker=None,
        gamma_exposure_tracker=None,
        symbols=None,
        unified_mode=False,
        confluence_gate=None,
    ):
        """
        Initialize Gamma checker.
        
        Args:
            alert_manager: AlertManager instance for deduplication
            gamma_tracker: GammaTracker instance (max pain based)
            gamma_exposure_tracker: GammaExposureTracker instance (flip level based)
            symbols: List of symbols to check (e.g., ['SPY', 'QQQ'])
            unified_mode: If True, suppresses individual alerts
            confluence_gate: ConfluenceGate instance (blocks blind signals)
        """
        super().__init__(alert_manager, unified_mode)
        self.gamma_tracker = gamma_tracker
        self.gamma_exposure_tracker = gamma_exposure_tracker
        self.symbols = symbols or []
        self.confluence_gate = confluence_gate
    
    @property
    def name(self) -> str:
        """Return checker name for identification."""
        return "gamma_checker"

    def check(self) -> List[CheckerAlert]:
        """
        Check for gamma ramp setups AND gamma flip signals.
        
        Returns:
            List of CheckerAlert objects (empty if no signals)
        """
        if not self.gamma_tracker and not self.gamma_exposure_tracker:
            return []
        
        logger.info("🎲 Checking for GAMMA setups...")
        
        try:
            alerts = []
            
            for symbol in self.symbols:
                # PRIORITY 1: Check for gamma flip signals (more precise)
                if self.gamma_exposure_tracker:
                    try:
                        import yfinance as yf
                        ticker = yf.Ticker(symbol)
                        hist = ticker.history(period='1d')
                        if not hist.empty:
                            current_price = float(hist['Close'].iloc[-1])
                            
                            gamma_data = self.gamma_exposure_tracker.calculate_gamma_exposure(symbol, current_price)
                            if gamma_data:
                                flip_signal = self.gamma_exposure_tracker.detect_gamma_flip_signal(gamma_data)
                                
                                if flip_signal:
                                    # ═══ CONFLUENCE GATE ═══
                                    if self.confluence_gate:
                                        gate_result = self.confluence_gate.should_fire(
                                            signal_direction=flip_signal['action'],
                                            symbol=symbol,
                                            raw_confidence=flip_signal['confidence'] * 100,
                                            current_price=current_price,
                                        )
                                        if gate_result.blocked:
                                            logger.warning(
                                                f"   ⛔ GAMMA FLIP BLOCKED: {symbol} {flip_signal['action']} — {gate_result.reason}"
                                            )
                                            continue
                                        # Inject gate results into flip_signal for alert transparency
                                        flip_signal['gate_result'] = gate_result
                                        flip_signal['confidence'] = gate_result.adjusted_confidence / 100
                                    # ═══ END GATE ═══

                                    alert = self._create_gamma_flip_alert(flip_signal)
                                    if alert:
                                        alerts.append(alert)
                                        logger.info(f"   🎯 GAMMA FLIP signal sent for {symbol} ({flip_signal['action']})!")
                                        continue  # Skip ramp check if flip detected
                    except Exception as e:
                        logger.debug(f"   ⚠️ Gamma flip check error for {symbol}: {e}")
                
                # PRIORITY 2: Check for gamma ramp signals (max pain based)
                if self.gamma_tracker:
                    # Check multiple expirations for each symbol
                    for exp_idx in [0, 4]:  # 0=nearest, 4=weekly (Friday)
                        signal = self.gamma_tracker.analyze(symbol, expiration_idx=exp_idx)
                        
                        if signal:
                            alert = self._create_gamma_alert(signal)
                            if alert:
                                alerts.append(alert)
                                logger.info(f"   🎲 Gamma ramp signal sent for {signal.symbol} ({signal.direction})!")
                            
                            # Only send one signal per symbol (break after first hit)
                            break
            
            return alerts
                    
        except Exception as e:
            logger.error(f"   ❌ Gamma check error: {e}")
            return []
    
    def _create_gamma_alert(self, signal) -> Optional[CheckerAlert]:
        """Create a CheckerAlert from a gamma signal."""
        direction_color = 15548997 if signal.direction == 'DOWN' else 3066993  # Red for DOWN, Green for UP
        direction_emoji = "🔻" if signal.direction == 'DOWN' else "🔺"
        
        embed = {
            "title": f"🎲 GAMMA {signal.direction}: {signal.symbol}",
            "color": direction_color,
            "description": f"**Score: {signal.score:.0f}/100** | Max Pain ${signal.max_pain:.2f} ({signal.max_pain_distance_pct:+.1f}%)",
            "fields": [
                {"name": "📊 P/C Ratio", "value": f"{signal.put_call_ratio:.2f}", "inline": True},
                {"name": f"{direction_emoji} Direction", "value": f"**{signal.direction}**", "inline": True},
                {"name": "🎯 Max Pain", "value": f"${signal.max_pain:.2f}", "inline": True},
                {"name": "📈 Call OI", "value": f"{signal.total_call_oi:,}", "inline": True},
                {"name": "📉 Put OI", "value": f"{signal.total_put_oi:,}", "inline": True},
                {"name": "📅 Expiration", "value": signal.expiration, "inline": True},
                {"name": "💵 Entry", "value": f"${signal.entry_price:.2f}", "inline": True},
                {"name": "🛑 Stop", "value": f"${signal.stop_price:.2f}", "inline": True},
                {"name": "🎯 Target", "value": f"${signal.target_price:.2f}", "inline": True},
                {"name": "📐 R/R", "value": f"{signal.risk_reward_ratio:.1f}:1", "inline": True},
                {"name": "💡 Action", "value": f"**{signal.action}** (Gamma Play)", "inline": True},
            ],
            "footer": {"text": f"Exploitation Phase 2 • Gamma Tracking"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add reasoning
        if signal.reasoning:
            embed["fields"].append({
                "name": "📝 Reasoning",
                "value": "\n".join([f"• {r}" for r in signal.reasoning[:4]]),
                "inline": False
            })
        
        content = f"🎲 **GAMMA ALERT** 🎲 | {signal.symbol} {signal.direction} Score: {signal.score:.0f}/100"
        
        return CheckerAlert(
            embed=embed,
            content=content,
            alert_type="gamma_signal",
            source="gamma_checker",
            symbol=signal.symbol
        )
    
    def _create_gamma_flip_alert(self, flip_signal: dict) -> Optional[CheckerAlert]:
        """Create a CheckerAlert from a gamma flip signal."""
        direction_color = 15548997 if flip_signal['action'] == 'SHORT' else 3066993  # Red for SHORT, Green for LONG
        direction_emoji = "🔻" if flip_signal['action'] == 'SHORT' else "🔺"
        
        entry_range = flip_signal['entry_range']
        
        embed = {
            "title": f"🎯 GAMMA FLIP {flip_signal['action']}: {flip_signal['symbol']}",
            "color": direction_color,
            "description": f"**Price retesting gamma flip level**\n**Confidence: {flip_signal['confidence']:.0%}**",
            "fields": [
                {"name": "🎯 Gamma Flip Level", "value": f"${flip_signal['gamma_flip_level']:.2f}", "inline": True},
                {"name": f"{direction_emoji} Action", "value": f"**{flip_signal['action']}**", "inline": True},
                {"name": "📊 Regime", "value": f"{flip_signal['regime']} Gamma", "inline": True},
                {"name": "📍 Entry Zone", "value": f"${entry_range[0]:.2f}-${entry_range[1]:.2f}\n(retest of flip)", "inline": True},
                {"name": "🛑 Stop", "value": f"${flip_signal['stop_price']:.2f}\n(TIGHT - above flip)", "inline": True},
                {"name": "🎯 Target 1", "value": f"${flip_signal['target1']:.2f}\nR/R: {flip_signal['risk_reward1']:.1f}:1", "inline": True},
                {"name": "🎯 Target 2", "value": f"${flip_signal['target2']:.2f}\nR/R: {flip_signal['risk_reward2']:.1f}:1", "inline": True},
                {"name": "📏 Distance to Flip", "value": f"{flip_signal['distance_to_flip_pct']:.2f}%", "inline": True},
                {"name": "⚡ Total GEX", "value": f"{flip_signal['total_gex']:,.0f} shares", "inline": True},
            ],
            "footer": {"text": f"Exploitation Phase 2 • Gamma Flip Detection"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add reasoning
        if flip_signal['reasoning']:
            embed["fields"].append({
                "name": "📝 Reasoning",
                "value": "\n".join([f"• {r}" for r in flip_signal['reasoning'][:5]]),
                "inline": False
            })
        
        # Add gate results if available
        gate_result = flip_signal.get('gate_result')
        if gate_result:
            gate_lines = [f"✅ {g}" for g in gate_result.gates_passed[:3]]
            gate_text = "\n".join(gate_lines) or "No gate data"
            
            # Format sizing multiplier string
            multiplier = gate_result.sizing_multiplier
            if multiplier >= 3.0:
                sz_str = f"🔥 MAX CONVICTION ({multiplier}x)"
            elif multiplier >= 1.0:
                sz_str = f"🟡 STANDARD ({multiplier}x)"
            else:
                sz_str = f"⚪ LIGHT ({multiplier}x)"
            
            gate_text += f"\n\n**⚖️ Sizing:** {sz_str}"
            
            embed["fields"].append({
                "name": f"⚔️ Confluence Gate ({gate_result.pass_rate})",
                "value": gate_text[:1024],
                "inline": False
            })
        
        content = f"🎯 **GAMMA FLIP {flip_signal['action']}** 🎯 | {flip_signal['symbol']} retesting flip at ${flip_signal['gamma_flip_level']:.2f}"
        
        return CheckerAlert(
            embed=embed,
            content=content,
            alert_type="gamma_flip_signal",
            source="gamma_checker",
            symbol=flip_signal['symbol']
        )

