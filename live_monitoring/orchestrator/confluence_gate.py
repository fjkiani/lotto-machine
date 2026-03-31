"""
⚔️ CONFLUENCE GATE — The Single Filter Between Signal and Action

Every directional signal (LONG/SHORT) must pass through this gate.
If Tier 1 (regime) or Tier 2 (bias) disagrees, the signal is BLOCKED.

Usage:
    gate = ConfluenceGate(regime_detector, kill_chain_logger)
    result = gate.should_fire(
        signal_direction="LONG",
        symbol="SPY",
        raw_confidence=95,
        synthesis_bias="BEARISH",   # from synthesis_checker
        synthesis_score=72,         # 0-100
    )
    if result.blocked:
        logger.warning(f"BLOCKED: {result.reason}")
    else:
        # safe to fire alert
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Result of a confluence gate check."""
    blocked: bool
    reason: str
    adjusted_confidence: float
    gates_passed: List[str] = field(default_factory=list)
    gates_failed: List[str] = field(default_factory=list)
    regime: str = "UNKNOWN"
    bias: str = "UNKNOWN"
    sizing_multiplier: float = 1.0  # Dynamic pos sizing: 0.0x to 3.0x
    dp_proximity: Optional[dict] = None  # DP level proximity info if near a known level

    @property
    def passed(self) -> bool:
        return not self.blocked

    @property
    def gates_total(self) -> int:
        return len(self.gates_passed) + len(self.gates_failed)

    @property
    def pass_rate(self) -> str:
        return f"{len(self.gates_passed)}/{self.gates_total}"


class ConfluenceGate:
    """
    The gate between Tier 3 (tactical entry) and action.

    Three inputs:
        - Tier 1: Market regime (from RegimeDetector)
        - Tier 2: Directional bias (from synthesis)
        - Tier 3: Signal direction (from the checker)

    One output:
        - GateResult: fire or block
    """

    def __init__(self, regime_detector=None, kill_chain_logger=None):
        """
        Args:
            regime_detector: RegimeDetector instance (Tier 1)
            kill_chain_logger: KillChainLogger instance (Tier 1 enrichment)
        """
        self.regime_detector = regime_detector
        self.kill_chain_logger = kill_chain_logger
        # Cached synthesis state — updated by orchestrator after each synthesis run
        self._synthesis_bias: str = None
        self._synthesis_score: float = 50.0
        # Trade-intent logger — every signal passes through here
        self._tracker = None
        try:
            from .gate_outcome_tracker import GateOutcomeTracker
            self._tracker = GateOutcomeTracker()
        except Exception:
            pass
        # DP learning edge — 89% WR proximity boost 🧠
        self._dp_db_path = self._find_dp_db()

        self._regime_evaluators = {
            "BULLISH": self._evaluate_long_proposal,
            "BREAKDOWN": self._evaluate_short_proposal,
            "CHOPPY": self._evaluate_choppy_proposal,
            "TREND_EXTENDED": self._evaluate_trend_extended_proposal,
        }

    def update_synthesis(self, bias: str, score: float):
        """
        Called by the orchestrator after synthesis_checker runs.
        Caches the latest synthesis bias/score so every subsequent
        signal check uses it automatically.
        """
        self._synthesis_bias = bias
        self._synthesis_score = score
        logger.info(f"🔄 Gate synthesis updated: {bias} ({score:.0f}%)")

    def _get_market_regime(
        self,
        snapshot: dict,
        symbol: str = "SPY",
        alternate_price: Optional[float] = None,
    ) -> str:
        """Determine market regime from Guardian snapshot.

        Priority order:
        1. BREAKDOWN — thesis broken, bearish_breakdown_building active
        2. TREND_EXTENDED — SPY at or above call wall (strong uptrend)
        3. CHOPPY — SPY between walls with tight spread (< 12)
        4. BULLISH — default when thesis_valid and none of the above
        5. UNKNOWN — fallback
        """
        # BREAKDOWN takes priority — wall already broken
        if snapshot.get("bearish_breakdown_building", False):
            return "BREAKDOWN"

        if not snapshot.get("thesis_valid", True):
            return "UNKNOWN"

        # Wall-relative positioning (requires spy_call_wall / spy_put_wall)
        spy_price = float(snapshot.get("spy_price") or 0)
        spy_call_wall = snapshot.get("spy_call_wall", 0)
        spy_put_wall = snapshot.get("spy_put_wall", 0)

        # Missing snapshot price (e.g. guardian yfinance fail) — try signal price, then fetch
        if spy_price <= 0:
            if alternate_price and alternate_price > 0:
                spy_price = float(alternate_price)
                snapshot["spy_price"] = spy_price
                snapshot["spy_price_source"] = "alternate_should_fire"
            else:
                try:
                    fb = self._get_price(symbol)
                    if fb and fb > 0:
                        spy_price = float(fb)
                        snapshot["spy_price"] = spy_price
                        snapshot["spy_price_source"] = "yfinance_fallback"
                except Exception as e:
                    logger.debug(f"⚠️ Gate: regime price fallback failed: {e}")

        if spy_price <= 0:
            return "UNKNOWN"

        if spy_price > 0 and spy_call_wall > 0 and spy_put_wall > 0:
            wall_spread = spy_call_wall - spy_put_wall

            # TREND_EXTENDED: SPY at or above call wall
            if spy_price >= spy_call_wall:
                return "TREND_EXTENDED"

            # CHOPPY: SPY between walls with tight spread
            if spy_price > spy_put_wall and wall_spread < 12:
                return "CHOPPY"

        # Default: thesis valid, no special wall positioning
        return "BULLISH"

    def should_fire(
        self,
        signal_direction: str,
        symbol: str = "SPY",
        raw_confidence: float = 50.0,
        synthesis_bias: Optional[str] = None,
        synthesis_score: Optional[float] = None,
        current_price: Optional[float] = None,
        snapshot: Optional[dict] = None,
        **kwargs
    ) -> GateResult:
        """Wrapper: evaluates the signal and logs every decision."""
        import json as _json, os as _os
        _SNAP = "/tmp/intraday_snapshot.json"
        loaded_from_file = False
        snap = snapshot or {}
        if not snap:
            if _os.path.exists(_SNAP):
                try:
                    with open(_SNAP) as _f:
                        snap = _json.load(_f)
                    loaded_from_file = True
                except Exception as e:
                    logger.debug(f"⚠️ Gate: snapshot read failed: {e}")

        regime = self._get_market_regime(snap, symbol=symbol, alternate_price=current_price)

        if loaded_from_file and snap.get("spy_price_source"):
            try:
                with open(_SNAP, "w") as _f:
                    _json.dump(snap, _f)
            except Exception as e:
                logger.debug(f"⚠️ Gate: snapshot write-back failed: {e}")

        # UNKNOWN = no usable data (spy_price=0 or thesis invalid) → block everything
        if regime == "UNKNOWN":
            result = GateResult(
                blocked=True,
                reason="⛔ NO DATA: Cannot evaluate signal — spy_price=0 or thesis invalid",
                adjusted_confidence=0,
                gates_passed=[],
                gates_failed=["REGIME: UNKNOWN — no price data to evaluate"],
                regime="UNKNOWN",
                bias=synthesis_bias or "UNKNOWN",
                sizing_multiplier=0.0,
            )
            self._log_result(result, symbol, signal_direction, current_price or 0)
            return result

        evaluator = self._regime_evaluators.get(regime, self._evaluate_long_proposal)

        # Remove snapshot from kwargs if it's there to prevent duplication
        kwargs.pop('snapshot', None)

        # Fallback to snapshot for synthesis metrics if not explicitly passed
        final_bias = synthesis_bias or snap.get("synthesis_bias") or self._synthesis_bias
        final_score = synthesis_score if synthesis_score is not None else snap.get("synthesis_score", self._synthesis_score)

        result = evaluator(
            signal_direction=signal_direction, symbol=symbol,
            raw_confidence=raw_confidence, synthesis_bias=final_bias,
            synthesis_score=final_score, current_price=current_price,
            snapshot=snap, **kwargs
        )
        self._log_result(result, symbol, signal_direction, current_price or 0)
        return result

    def _evaluate_choppy_proposal(
        self,
        signal_direction: str,
        symbol: str = "SPY",
        raw_confidence: float = 50.0,
        synthesis_bias: Optional[str] = None,
        synthesis_score: float = 50.0,
        current_price: Optional[float] = None,
        snapshot: Optional[dict] = None,
        **kwargs
    ) -> GateResult:
        """CHOPPY regime: SPY between walls, tight spread.
        
        Rules:
        - SHORT: always blocked (no directional edge in chop)
        - LONG: requires 90%+ confidence, sizing = 0.5x (half size)
        """
        gates_passed = []
        gates_failed = []
        direction = signal_direction.upper()
        bias = (synthesis_bias or self._synthesis_bias or "UNKNOWN").upper()
        regime = "CHOPPY"

        # SHORT always blocked in CHOPPY
        if direction == "SHORT":
            gates_failed.append("DIRECTION: SHORT blocked in CHOPPY regime (no edge)")
            return GateResult(
                blocked=True,
                reason="⛔ CHOPPY BLOCK: No short edge in choppy market",
                adjusted_confidence=0,
                gates_passed=gates_passed,
                gates_failed=gates_failed,
                regime=regime,
                bias=bias,
                sizing_multiplier=0.0
            )
        gates_passed.append("DIRECTION: LONG ok in CHOPPY")

        # LONG requires 90%+ confidence
        if raw_confidence < 90:
            gates_failed.append(f"CONFIDENCE: {raw_confidence:.0f}% < 90% required in CHOPPY")
            return GateResult(
                blocked=True,
                reason=f"⛔ CHOPPY CONFIDENCE BLOCK: Need 90%+ (got {raw_confidence:.0f}%)",
                adjusted_confidence=0,
                gates_passed=gates_passed,
                gates_failed=gates_failed,
                regime=regime,
                bias=bias,
                sizing_multiplier=0.0
            )
        gates_passed.append(f"CONFIDENCE: {raw_confidence:.0f}% >= 90% (CHOPPY threshold)")

        logger.info(
            f"✅ GATE PASS: {direction} {symbol} | "
            f"Regime=CHOPPY | Bias={bias} | "
            f"Confidence: {raw_confidence:.0f}% | Sizing: 0.5x"
        )
        return GateResult(
            blocked=False,
            reason=f"✅ PASS: {direction} {symbol} (CHOPPY 0.5x)",
            adjusted_confidence=raw_confidence,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            regime=regime,
            bias=bias,
            sizing_multiplier=0.5
        )

    def _evaluate_trend_extended_proposal(
        self,
        signal_direction: str,
        symbol: str = "SPY",
        raw_confidence: float = 50.0,
        synthesis_bias: Optional[str] = None,
        synthesis_score: float = 50.0,
        current_price: Optional[float] = None,
        snapshot: Optional[dict] = None,
        **kwargs
    ) -> GateResult:
        """TREND_EXTENDED regime: SPY at or above call wall.
        
        Rules:
        - SHORT: always blocked (don't short a breakout)
        - LONG: requires 70%+ confidence, sizing = 1.5x (add on strength)
        """
        gates_passed = []
        gates_failed = []
        direction = signal_direction.upper()
        bias = (synthesis_bias or self._synthesis_bias or "UNKNOWN").upper()
        regime = "TREND_EXTENDED"

        # SHORT always blocked in TREND_EXTENDED
        if direction == "SHORT":
            gates_failed.append("DIRECTION: SHORT blocked in TREND_EXTENDED (breakout in progress)")
            return GateResult(
                blocked=True,
                reason="⛔ TREND_EXTENDED BLOCK: No shorting during breakout",
                adjusted_confidence=0,
                gates_passed=gates_passed,
                gates_failed=gates_failed,
                regime=regime,
                bias=bias,
                sizing_multiplier=0.0
            )
        gates_passed.append("DIRECTION: LONG ok in TREND_EXTENDED")

        # LONG requires 70%+ confidence
        if raw_confidence < 70:
            gates_failed.append(f"CONFIDENCE: {raw_confidence:.0f}% < 70% required in TREND_EXTENDED")
            return GateResult(
                blocked=True,
                reason=f"⛔ TREND_EXTENDED CONFIDENCE BLOCK: Need 70%+ (got {raw_confidence:.0f}%)",
                adjusted_confidence=0,
                gates_passed=gates_passed,
                gates_failed=gates_failed,
                regime=regime,
                bias=bias,
                sizing_multiplier=0.0
            )
        gates_passed.append(f"CONFIDENCE: {raw_confidence:.0f}% >= 70% (TREND_EXTENDED threshold)")

        logger.info(
            f"✅ GATE PASS: {direction} {symbol} | "
            f"Regime=TREND_EXTENDED | Bias={bias} | "
            f"Confidence: {raw_confidence:.0f}% | Sizing: 1.5x"
        )
        return GateResult(
            blocked=False,
            reason=f"✅ PASS: {direction} {symbol} (TREND_EXTENDED 1.5x)",
            adjusted_confidence=raw_confidence,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            regime=regime,
            bias=bias,
            sizing_multiplier=1.5
        )

    def _evaluate_short_proposal(
        self,
        signal_direction: str,
        symbol: str = "SPY",
        raw_confidence: float = 50.0,
        synthesis_bias: Optional[str] = None,
        synthesis_score: float = 50.0,
        current_price: Optional[float] = None,
        snapshot: Optional[dict] = None,
        **kwargs
    ) -> GateResult:
        gates_passed = []
        gates_failed = []
        direction = signal_direction.upper()
        snap = snapshot or {}
        
        bias = synthesis_bias or self._synthesis_bias or "UNKNOWN"
        bias = bias.upper()

        regime = "BREAKDOWN"

        # Tier 0 Gate Unlock
        if not snap.get("bearish_breakdown_building", False):
            gates_failed.append("GATE UNLOCK: bearish_breakdown_building is False")
            return GateResult(
                blocked=True,
                reason="⛔ GATE UNLOCK BLOCK: Breakdown not confirmed",
                adjusted_confidence=0,
                gates_passed=gates_passed,
                gates_failed=gates_failed,
                regime=regime,
                bias=bias,
                sizing_multiplier=0.0
            )
        gates_passed.append("GATE UNLOCK: Breakdown confirmed")

        # Tier 1 Direction
        if direction != "SHORT":
            gates_failed.append(f"DIRECTION: Longs are blocked in {regime} regime")
            return GateResult(
                blocked=True,
                reason="⛔ DIRECTION BLOCK: Cannot go LONG during market breakdown",
                adjusted_confidence=0,
                gates_passed=gates_passed,
                gates_failed=gates_failed,
                regime=regime,
                bias=bias,
                sizing_multiplier=0.0
            )
        gates_passed.append("DIRECTION: SHORT ok")

        # Tier 2 Synthesis
        if bias != "BEARISH":
            gates_failed.append(f"SYNTHESIS: Synthesis bias is {bias}, requiring BEARISH")
            return GateResult(
                blocked=True,
                reason=f"⛔ SYNTHESIS BLOCK: Shorts isolated when bias is {bias}",
                adjusted_confidence=0,
                gates_passed=gates_passed,
                gates_failed=gates_failed,
                regime=regime,
                bias=bias,
                sizing_multiplier=0.0
            )
        gates_passed.append("SYNTHESIS: Bias is BEARISH")

        # Tier 3 Pressure
        dp_flow_direction = kwargs.get("dp_flow_direction", "UNKNOWN")
        if dp_flow_direction != "NEGATIVE":
            gates_failed.append(f"PRESSURE: DP Flow is {dp_flow_direction}, requiring NEGATIVE")
            return GateResult(
                blocked=True,
                reason=f"⛔ PRESSURE BLOCK: dp_flow_direction is {dp_flow_direction}",
                adjusted_confidence=0,
                gates_passed=gates_passed,
                gates_failed=gates_failed,
                regime=regime,
                bias=bias,
                sizing_multiplier=0.0
            )
        gates_passed.append("PRESSURE: DP Flow NEGATIVE")

        # Tier 4 Momentum
        breakdown_vol_ratio = kwargs.get("breakdown_vol_ratio", 0.0)
        if breakdown_vol_ratio <= 1.5:
            gates_failed.append(f"MOMENTUM: Volume ratio {breakdown_vol_ratio:.2f} <= 1.5")
            return GateResult(
                blocked=True,
                reason=f"⛔ MOMENTUM BLOCK: breakdown_vol_ratio is {breakdown_vol_ratio:.2f}",
                adjusted_confidence=0,
                gates_passed=gates_passed,
                gates_failed=gates_failed,
                regime=regime,
                bias=bias,
                sizing_multiplier=0.0
            )
        gates_passed.append(f"MOMENTUM: Volume ratio {breakdown_vol_ratio:.2f} > 1.5")

        logger.info(
            f"✅ GATE PASS: {direction} {symbol} | "
            f"Regime={regime} | Bias={bias} | "
            f"Confidence: {raw_confidence:.0f}%"
        )
        return GateResult(
            blocked=False,
            reason=f"✅ PASS: {direction} {symbol} (Short Evaluator)",
            adjusted_confidence=raw_confidence,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            regime=regime,
            bias=bias,
            sizing_multiplier=1.0  # sizing logic for shorts could be added later
        )

    def _evaluate_long_proposal(
        self,
        signal_direction: str,
        symbol: str = "SPY",
        raw_confidence: float = 50.0,
        synthesis_bias: Optional[str] = None,
        synthesis_score: float = 50.0,
        current_price: Optional[float] = None,
        snapshot: Optional[dict] = None,
        **kwargs
    ) -> GateResult:
        """
        The one method. Three tiers in. True or False out.

        Args:
            signal_direction: "LONG" or "SHORT"
            symbol: Ticker symbol
            raw_confidence: Original signal confidence (0-100)
            synthesis_bias: "BULLISH", "BEARISH", or "NEUTRAL" (Tier 2)
            synthesis_score: Synthesis conviction 0-100 (Tier 2)
            current_price: Current price (if None, fetched via yfinance)

        Returns:
            GateResult with blocked=True/False and reason
        """
        gates_passed = []
        gates_failed = []
        confidence = raw_confidence
        direction = signal_direction.upper()

        # Use cached synthesis if not explicitly provided
        if synthesis_bias is None and self._synthesis_bias:
            synthesis_bias = self._synthesis_bias
            synthesis_score = self._synthesis_score

        # ─── FETCH PRICE IF NEEDED ────────────────────────────────────
        if current_price is None:
            current_price = self._get_price(symbol)

        # ═══════════════════════════════════════════════════════════════
        # GATE 0: INTRADAY THESIS — Hard block when thesis invalid
        # ═══════════════════════════════════════════════════════════════
        _snap = snapshot or {}
        if _snap:
            try:
                if _snap.get("market_open") and not _snap.get("thesis_valid", True):
                    reason = _snap.get("thesis_invalidation_reason", "Thesis invalidated")
                    gates_failed.append(f"THESIS: {reason}")
                    return GateResult(
                        blocked=True,
                        reason=f"⛔ THESIS BLOCK: {reason}",
                        adjusted_confidence=0,
                        gates_passed=gates_passed,
                        gates_failed=gates_failed,
                        regime="THESIS_INVALID",
                        bias=synthesis_bias or "UNKNOWN",
                        sizing_multiplier=0.0,
                    )
                if _snap.get("circuit_breaker_active"):
                    reason = _snap.get("circuit_breaker_reason", "Circuit breaker active")
                    gates_failed.append(f"CIRCUIT BREAKER: {reason}")
                    return GateResult(
                        blocked=True,
                        reason=f"🚨 CIRCUIT BREAKER: {reason}",
                        adjusted_confidence=0,
                        gates_passed=gates_passed,
                        gates_failed=gates_failed,
                        regime="CIRCUIT_BREAKER",
                        bias=synthesis_bias or "UNKNOWN",
                        sizing_multiplier=0.0,
                    )
                gates_passed.append("THESIS: Valid")
            except Exception as e:
                logger.debug(f"⚠️ Gate: snapshot read failed: {e}")
                gates_passed.append("THESIS: Snapshot unavailable (no penalty)")

        # ═══════════════════════════════════════════════════════════════
        # GATE 1: REGIME (Tier 1) — Hard block on strong counter-trend
        # ═══════════════════════════════════════════════════════════════
        regime = "BULLISH"
        if self.regime_detector and current_price:
            try:
                regime = self.regime_detector.detect(current_price, symbol)
            except Exception as e:
                logger.warning(f"⚠️ Gate: regime detection failed: {e}")

        # HARD BLOCK: LONG into strong downtrend
        if regime == "STRONG_DOWNTREND" and direction == "LONG":
            gates_failed.append("REGIME: LONG blocked in STRONG_DOWNTREND")
            return GateResult(
                blocked=True,
                reason=f"⛔ REGIME HARD BLOCK: Cannot go LONG in STRONG_DOWNTREND",
                adjusted_confidence=0,
                gates_passed=gates_passed,
                gates_failed=gates_failed,
                regime=regime,
                bias=synthesis_bias or "UNKNOWN",
            )

        # HARD BLOCK: SHORT into strong uptrend
        if regime == "STRONG_UPTREND" and direction == "SHORT":
            gates_failed.append("REGIME: SHORT blocked in STRONG_UPTREND")
            return GateResult(
                blocked=True,
                reason=f"⛔ REGIME HARD BLOCK: Cannot go SHORT in STRONG_UPTREND",
                adjusted_confidence=0,
                gates_passed=gates_passed,
                gates_failed=gates_failed,
                regime=regime,
                bias=synthesis_bias or "UNKNOWN",
            )

        # SOFT BLOCK: Counter-trend in normal trend (needs high conviction)
        if regime == "DOWNTREND" and direction == "LONG":
            if raw_confidence < 90:
                gates_failed.append(f"REGIME: LONG in DOWNTREND needs 90%+ (got {raw_confidence:.0f}%)")
                return GateResult(
                    blocked=True,
                    reason=f"⛔ REGIME SOFT BLOCK: LONG in DOWNTREND requires 90%+ confidence (got {raw_confidence:.0f}%)",
                    adjusted_confidence=0,
                    gates_passed=gates_passed,
                    gates_failed=gates_failed,
                    regime=regime,
                    bias=synthesis_bias or "UNKNOWN",
                )
            else:
                gates_passed.append(f"REGIME: LONG in DOWNTREND allowed (confidence {raw_confidence:.0f}% ≥ 90%)")
                confidence *= 0.7  # Penalize counter-trend

        elif regime == "UPTREND" and direction == "SHORT":
            if raw_confidence < 90:
                gates_failed.append(f"REGIME: SHORT in UPTREND needs 90%+ (got {raw_confidence:.0f}%)")
                return GateResult(
                    blocked=True,
                    reason=f"⛔ REGIME SOFT BLOCK: SHORT in UPTREND requires 90%+ confidence (got {raw_confidence:.0f}%)",
                    adjusted_confidence=0,
                    gates_passed=gates_passed,
                    gates_failed=gates_failed,
                    regime=regime,
                    bias=synthesis_bias or "UNKNOWN",
                )
            else:
                gates_passed.append(f"REGIME: SHORT in UPTREND allowed (confidence {raw_confidence:.0f}% ≥ 90%)")
                confidence *= 0.7

        else:
            # Trend-aligned or choppy — regime gate passes
            gates_passed.append(f"REGIME: {direction} ok in {regime}")

        # ═══════════════════════════════════════════════════════════════
        # GATE 2: SYNTHESIS BIAS (Tier 2) — Block signals that fight bias
        # ═══════════════════════════════════════════════════════════════
        if synthesis_bias:
            bias = synthesis_bias.upper()

            if bias == "BEARISH" and direction == "LONG" and synthesis_score >= 40:
                gates_failed.append(f"BIAS: LONG blocked by BEARISH synthesis ({synthesis_score:.0f}%)")
                return GateResult(
                    blocked=True,
                    reason=f"⛔ BIAS BLOCK: Cannot go LONG when synthesis is BEARISH ({synthesis_score:.0f}%)",
                    adjusted_confidence=0,
                    gates_passed=gates_passed,
                    gates_failed=gates_failed,
                    regime=regime,
                    bias=bias,
                    sizing_multiplier=0.0,
                )

            if bias == "BULLISH" and direction == "SHORT" and synthesis_score >= 40:
                gates_failed.append(f"BIAS: SHORT blocked by BULLISH synthesis ({synthesis_score:.0f}%)")
                return GateResult(
                    blocked=True,
                    reason=f"⛔ BIAS BLOCK: Cannot go SHORT when synthesis is BULLISH ({synthesis_score:.0f}%)",
                    adjusted_confidence=0,
                    gates_passed=gates_passed,
                    gates_failed=gates_failed,
                    regime=regime,
                    bias=bias,
                    sizing_multiplier=0.0,
                )

            # Aligned or neutral — pass
            gates_passed.append(f"BIAS: {direction} ok with {bias} synthesis")
        else:
            # No synthesis available — pass with penalty
            gates_passed.append("BIAS: No synthesis data (pass with penalty)")
            confidence *= 0.85

        # ═══════════════════════════════════════════════════════════════
        # GATE 2.5: DP PROXIMITY — Boost when near proven DP level (89% WR)
        # ═══════════════════════════════════════════════════════════════
        dp_info = self._check_dp_proximity(symbol, current_price)
        if dp_info:
            if dp_info["aligned"]:
                gates_passed.append(
                    f"🧠 DP EDGE: {dp_info['level_type']} @ ${dp_info['level_price']:.2f} "
                    f"(dist={dp_info['distance_pct']:.2f}%, WR={dp_info['bounce_rate']:.0f}%)"
                )
                confidence *= 1.10  # +10% confidence boost
            elif dp_info["distance_pct"] < 0.3:
                gates_passed.append(
                    f"⚠️ DP WARNING: {dp_info['level_type']} wall at ${dp_info['level_price']:.2f} "
                    f"({dp_info['distance_pct']:.2f}% away) — expect bounce"
                )

        # ═══════════════════════════════════════════════════════════════
        # GATE 3: KILL CHAIN MACRO & CONVICTION SCALING
        # ═══════════════════════════════════════════════════════════════
        multiplier = 1.0  # Default sizing

        if self.kill_chain_logger:
            try:
                kc = self.kill_chain_logger
                
                if hasattr(kc, 'triple_active') and kc.triple_active:
                    multiplier = 3.0
                    gates_passed.append("🔥 MAX CONVICTION: Kill Chain Triple Active (3.0x size)")
                    confidence *= 1.15
                else:
                    layers = sum([
                        getattr(kc, 'cot_divergence', False),
                        getattr(kc, 'gex_positive', False),
                        getattr(kc, 'dp_selling', False)
                    ])
                    if layers == 0:
                        multiplier = 0.5
                        gates_passed.append("⚪ LOW CONVICTION: No Kill Chain layers active (0.5x size)")
                    else:
                        multiplier = 1.0
                        gates_passed.append(f"🟡 MED CONVICTION: {layers}/3 Kill Chain layers active (1.0x size)")
                    
            except Exception as e:
                logger.debug(f"⚠️ Gate: kill chain conviction check failed: {e}")
                gates_passed.append("KILL CHAIN: Conviction check failed (1.0x size fallback)")

        # ═══════════════════════════════════════════════════════════════
        # FINAL RESULT: All gates passed
        # ═══════════════════════════════════════════════════════════════
        confidence = min(confidence, 100.0)

        logger.info(
            f"✅ GATE PASS: {direction} {symbol} | "
            f"Regime={regime} | Bias={synthesis_bias or 'N/A'} | "
            f"Confidence: {raw_confidence:.0f}% → {confidence:.0f}% | "
            f"Sizing: {multiplier}x"
        )

        return GateResult(
            blocked=False,
            reason=f"✅ PASS: {direction} {symbol} ({len(gates_passed)} gates passed | {multiplier}x size)",
            adjusted_confidence=confidence,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            regime=regime,
            bias=synthesis_bias or "NEUTRAL",
            sizing_multiplier=multiplier,
        )

    def _log_result(self, result: 'GateResult', symbol: str, direction: str,
                    entry_price: float, source: str = ""):
        """Log every gate decision to the outcome tracker."""
        if self._tracker:
            try:
                # We can store the sizing multiplier in the reason string or extend the outcome tracker DB schema
                reason_with_size = f"{result.reason} [Sz:{result.sizing_multiplier}x]" if not result.blocked else result.reason
                self._tracker.log_signal(
                    ticker=symbol,
                    direction=direction,
                    entry_price=entry_price or 0,
                    confidence=result.adjusted_confidence,
                    blocked=result.blocked,
                    reason=reason_with_size,
                    regime=result.regime,
                    bias=result.bias,
                    source=source,
                )
            except Exception as e:
                logger.debug(f"⚠️ Gate log failed: {e}")

    def _get_price(self, symbol: str) -> Optional[float]:
        """Fetch current price via yfinance. Fail-safe."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d')
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        except Exception as e:
            logger.warning(f"⚠️ Gate: price fetch failed for {symbol}: {e}")
        return None

    def _find_dp_db(self) -> Optional[Path]:
        """Locate dp_learning.db — fail-safe, never crash."""
        candidates = [
            Path("data/dp_learning.db"),
            Path(__file__).parent.parent.parent / "data" / "dp_learning.db",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    def _check_dp_proximity(
        self, symbol: str, current_price: Optional[float], threshold_pct: float = 0.5
    ) -> Optional[dict]:
        """
        Check if current_price is within threshold_pct of a known DP level
        with settled interactions (89% WR edge).

        Returns dict with level info or None if no nearby level.
        """
        if not self._dp_db_path or not current_price:
            return None
        try:
            conn = sqlite3.connect(str(self._dp_db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT level_price, level_type, outcome, touch_count "
                "FROM dp_interactions WHERE symbol = ? AND outcome IN ('BOUNCE','BREAK') "
                "ORDER BY timestamp DESC LIMIT 200",
                (symbol,),
            ).fetchall()
            conn.close()
            if not rows:
                return None

            # Group by level_price (round to nearest 0.50)
            levels = {}
            for r in rows:
                lp = round(r["level_price"] * 2) / 2  # snap to $0.50 grid
                if lp not in levels:
                    levels[lp] = {"type": r["level_type"], "bounces": 0, "breaks": 0, "touches": 0}
                if r["outcome"] == "BOUNCE":
                    levels[lp]["bounces"] += 1
                else:
                    levels[lp]["breaks"] += 1
                levels[lp]["touches"] = max(levels[lp]["touches"], r["touch_count"] or 1)

            # Find closest level within threshold
            best = None
            best_dist = float("inf")
            for lp, info in levels.items():
                total = info["bounces"] + info["breaks"]
                if total < 3:  # need minimum sample size
                    continue
                dist_pct = abs(current_price - lp) / current_price * 100
                if dist_pct <= threshold_pct and dist_pct < best_dist:
                    wr = info["bounces"] / total * 100
                    # Only flag if WR >= 70% (strong level)
                    if wr >= 70:
                        best = {
                            "level_price": lp,
                            "level_type": info["type"],
                            "distance_pct": dist_pct,
                            "bounce_rate": wr,
                            "total_samples": total,
                            "touches": info["touches"],
                            "aligned": True,  # signal near a high-WR level = aligned
                        }
                        best_dist = dist_pct

            return best
        except Exception as e:
            logger.debug(f"⚠️ DP proximity check failed: {e}")
            return None
