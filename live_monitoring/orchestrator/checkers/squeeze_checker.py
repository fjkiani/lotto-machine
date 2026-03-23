"""
Squeeze Checker - Detects short squeeze opportunities.

Extracted from unified_monitor.py for modularity.

This checker uses dynamic discovery to find high short interest stocks
and analyzes them for squeeze potential.
"""

import logging
from datetime import datetime
from typing import List, Optional

from .base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


class SqueezeChecker(BaseChecker):
    """
    Checks for short squeeze setups using dynamic discovery.
    
    Responsibilities:
    - Dynamically discover high SI stocks via opportunity scanner
    - Run squeeze detector on candidates
    - Generate alerts for high-score signals (>=60)
    - Fallback to seed list if scanner unavailable
    """
    
    def __init__(
        self,
        alert_manager,
        squeeze_detector=None,
        opportunity_scanner=None,
        squeeze_candidates=None,
        unified_mode=False,
        confluence_gate=None,
    ):
        """
        Initialize Squeeze checker.
        
        Args:
            alert_manager: AlertManager instance for deduplication
            squeeze_detector: SqueezeDetector instance
            opportunity_scanner: OpportunityScanner instance for dynamic discovery
            squeeze_candidates: Seed list of squeeze candidates (fallback)
            unified_mode: If True, suppresses individual alerts
            confluence_gate: ConfluenceGate instance (blocks blind signals)
        """
        super().__init__(alert_manager, unified_mode)
        self.squeeze_detector = squeeze_detector
        self.opportunity_scanner = opportunity_scanner
        self.squeeze_candidates = squeeze_candidates or []
        self.confluence_gate = confluence_gate
    
    @property
    def name(self) -> str:
        """Return checker name for identification."""
        return "squeeze_checker"

    def check(self) -> List[CheckerAlert]:
        """
        Check for short squeeze setups using dynamic discovery.
        
        Returns:
            List of CheckerAlert objects (empty if no signals)
        """
        if not self.squeeze_detector:
            return []
        
        logger.info("🔥 Checking for SQUEEZE setups (DYNAMIC DISCOVERY)...")
        
        try:
            alerts = []
            
            # STEP 1: DYNAMIC DISCOVERY - Use opportunity scanner to find ALL high SI stocks
            if self.opportunity_scanner:
                logger.info("   🔍 Running FULL dynamic squeeze scan...")
                try:
                    squeeze_opportunities = self.opportunity_scanner.scan_for_squeeze_candidates(
                        self.squeeze_detector,
                        min_score=55  # Slightly lower for discovery, will filter at 60 for alerts
                    )
                    
                    if squeeze_opportunities:
                        logger.info(f"   📡 Found {len(squeeze_opportunities)} squeeze candidates!")
                        for opp in squeeze_opportunities:
                            logger.info(f"      • {opp.symbol}: Score {opp.score:.0f} | SI: {opp.short_interest:.1f}%")
                    else:
                        logger.info("   📊 No squeeze candidates found above threshold")
                    
                    # Process signals directly from scan results
                    for opp in squeeze_opportunities:
                        if opp.score >= 60:  # Alert threshold
                            # ═══ CONFLUENCE GATE ═══
                            gate_multiplier = 1.0
                            if self.confluence_gate:
                                gate_result = self.confluence_gate.should_fire(
                                    signal_direction="LONG",
                                    symbol=opp.symbol,
                                    raw_confidence=min(90, opp.score),
                                )
                                if gate_result.blocked:
                                    logger.warning(f"   ⛔ SQUEEZE BLOCKED: {opp.symbol} LONG — {gate_result.reason}")
                                    continue
                                gate_multiplier = gate_result.sizing_multiplier
                            # ═══ END GATE ═══
                            # Get full signal for detailed alert
                            signal = self.squeeze_detector.analyze(opp.symbol)
                            if signal:
                                alert = self._create_squeeze_alert(signal, gate_multiplier)
                                if alert:
                                    alerts.append(alert)
                    
                    return alerts  # Dynamic scan complete
                    
                except Exception as e:
                    logger.warning(f"   ⚠️ Dynamic scan failed, falling back to seed list: {e}")
            
            # FALLBACK: Use seed list if scanner not available
            candidates_to_check = set(self.squeeze_candidates)
            logger.info(f"   📊 Using seed list: {len(candidates_to_check)} candidates")
            
            # STEP 2: Run squeeze detector on all candidates
            for symbol in candidates_to_check:
                signal = self.squeeze_detector.analyze(symbol)
                
                if signal and signal.score >= 60:
                    # ═══ CONFLUENCE GATE ═══
                    gate_multiplier = 1.0
                    if self.confluence_gate:
                        gate_result = self.confluence_gate.should_fire(
                            signal_direction="LONG",
                            symbol=symbol,
                            raw_confidence=min(90, signal.score),
                        )
                        if gate_result.blocked:
                            logger.warning(f"   ⛔ SQUEEZE BLOCKED: {symbol} LONG — {gate_result.reason}")
                            continue
                        gate_multiplier = gate_result.sizing_multiplier
                    # ═══ END GATE ═══
                    alert = self._create_squeeze_alert(signal, gate_multiplier)
                    if alert:
                        alerts.append(alert)
            
            logger.info(f"   📊 Squeeze check complete: {len(alerts)} signals found")
            return alerts
                    
        except Exception as e:
            logger.error(f"   ❌ Squeeze check error: {e}")
            return []
    
    def _create_squeeze_alert(self, signal, multiplier: float = 1.0) -> Optional[CheckerAlert]:
        """Create a CheckerAlert from a squeeze signal."""
        # Check for duplicate alert
        alert_key = f"squeeze_{signal.symbol}_{datetime.now().strftime('%Y-%m-%d')}"
        if self.alert_manager.is_alert_duplicate(alert_key, cooldown_minutes=60):
            logger.debug(f"   ⏭️ Skipping duplicate squeeze alert for {signal.symbol}")
            return None
        
        # Create Discord embed
        score_color = 3066993 if signal.score >= 80 else 16776960  # Green if high, yellow otherwise
        
        embed = {
            "title": f"🔥 SQUEEZE SETUP: {signal.symbol}",
            "color": score_color,
            "description": f"**Score: {signal.score:.0f}/100** | Short Interest {signal.short_interest_pct:.1f}%",
            "fields": [
                {"name": "📊 SI%", "value": f"{signal.short_interest_pct:.1f}% ({signal.si_score:.0f} pts)", "inline": True},
                {"name": "💰 Borrow Fee", "value": f"{signal.borrow_fee_pct:.1f}% ({signal.borrow_fee_score:.0f} pts)", "inline": True},
                {"name": "📈 FTD Spike", "value": f"{signal.ftd_spike_ratio:.1f}x ({signal.ftd_score:.0f} pts)", "inline": True},
                {"name": "🔒 DP Buying", "value": f"{signal.dp_buying_pressure:.0%} ({signal.dp_support_score:.0f} pts)", "inline": True},
                {"name": "🎯 Entry", "value": f"${signal.entry_price:.2f}", "inline": True},
                {"name": "⚖️ Sizing", "value": f"{multiplier}x", "inline": True},
                {"name": "🛑 Stop", "value": f"${signal.stop_price:.2f}", "inline": True},
                {"name": "🚀 Target", "value": f"${signal.target_price:.2f}", "inline": True},
                {"name": "📐 R/R", "value": f"{signal.risk_reward_ratio:.1f}:1", "inline": True},
                {"name": "💡 Action", "value": "**LONG** (Squeeze Play)", "inline": True},
            ],
            "footer": {"text": f"Exploitation Phase 1 • Dynamic Squeeze Detection"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add reasoning
        if signal.reasoning:
            embed["fields"].append({
                "name": "📝 Reasoning",
                "value": "\n".join([f"• {r}" for r in signal.reasoning[:3]]),
                "inline": False
            })
        
        # Add warnings
        if signal.warnings:
            embed["fields"].append({
                "name": "⚠️ Warnings",
                "value": "\n".join([f"• {w}" for w in signal.warnings[:3]]),
                "inline": False
            })
        
        content = f"🔥 **SQUEEZE ALERT** 🔥 | {signal.symbol} Score: {signal.score:.0f}/100"
        
        self.alert_manager.add_alert_to_history(alert_key)
        logger.info(f"   🔥 Squeeze signal sent for {signal.symbol}!")
        
        return CheckerAlert(
            embed=embed,
            content=content,
            alert_type="squeeze_signal",
            source="squeeze_checker",
            symbol=signal.symbol
        )

