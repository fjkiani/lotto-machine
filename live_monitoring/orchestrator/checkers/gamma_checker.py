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
        symbols=None,
        unified_mode=False
    ):
        """
        Initialize Gamma checker.
        
        Args:
            alert_manager: AlertManager instance for deduplication
            gamma_tracker: GammaTracker instance
            symbols: List of symbols to check (e.g., ['SPY', 'QQQ'])
            unified_mode: If True, suppresses individual alerts
        """
        super().__init__(alert_manager, unified_mode)
        self.gamma_tracker = gamma_tracker
        self.symbols = symbols or []
    
    def check(self) -> List[CheckerAlert]:
        """
        Check for gamma ramp setups.
        
        Returns:
            List of CheckerAlert objects (empty if no signals)
        """
        if not self.gamma_tracker:
            return []
        
        logger.info("🎲 Checking for GAMMA setups...")
        
        try:
            alerts = []
            
            # Check multiple expirations for each symbol
            for symbol in self.symbols:
                # Check nearest and weekly expirations
                for exp_idx in [0, 4]:  # 0=nearest, 4=weekly (Friday)
                    signal = self.gamma_tracker.analyze(symbol, expiration_idx=exp_idx)
                    
                    if signal:
                        alert = self._create_gamma_alert(signal)
                        if alert:
                            alerts.append(alert)
                            logger.info(f"   🎲 Gamma signal sent for {signal.symbol} ({signal.direction})!")
                        
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

