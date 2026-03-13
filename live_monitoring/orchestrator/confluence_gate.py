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
from dataclasses import dataclass, field
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

    def update_synthesis(self, bias: str, score: float):
        """
        Called by the orchestrator after synthesis_checker runs.
        Caches the latest synthesis bias/score so every subsequent
        signal check uses it automatically.
        """
        self._synthesis_bias = bias
        self._synthesis_score = score
        logger.info(f"🔄 Gate synthesis updated: {bias} ({score:.0f}%)")

    def should_fire(
        self,
        signal_direction: str,
        symbol: str = "SPY",
        raw_confidence: float = 50.0,
        synthesis_bias: Optional[str] = None,
        synthesis_score: float = 50.0,
        current_price: Optional[float] = None,
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
        # GATE 1: REGIME (Tier 1) — Hard block on strong counter-trend
        # ═══════════════════════════════════════════════════════════════
        regime = "CHOPPY"
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
                )

            # Aligned or neutral — pass
            gates_passed.append(f"BIAS: {direction} ok with {bias} synthesis")
        else:
            # No synthesis available — pass with penalty
            gates_passed.append("BIAS: No synthesis data (pass with penalty)")
            confidence *= 0.85

        # ═══════════════════════════════════════════════════════════════
        # GATE 3: KILL CHAIN MACRO (Tier 1 enrichment) — Optional boost
        # ═══════════════════════════════════════════════════════════════
        if self.kill_chain_logger:
            try:
                kc = self.kill_chain_logger
                if hasattr(kc, 'triple_active') and kc.triple_active:
                    gates_passed.append("KILL CHAIN: Triple confluence ACTIVE (COT+GEX+DVR)")
                    confidence *= 1.15  # Boost for full confluence
                elif hasattr(kc, 'cot_divergence') and kc.cot_divergence:
                    gates_passed.append("KILL CHAIN: COT divergence active")
                    # No boost, but not a penalty
                else:
                    gates_passed.append("KILL CHAIN: No macro confluence (no penalty)")
                    # Informational — don't block, but don't boost
            except Exception as e:
                logger.debug(f"⚠️ Gate: kill chain check failed: {e}")
                gates_passed.append("KILL CHAIN: Check failed (no penalty)")

        # ═══════════════════════════════════════════════════════════════
        # FINAL RESULT: All gates passed
        # ═══════════════════════════════════════════════════════════════
        confidence = min(confidence, 100.0)

        logger.info(
            f"✅ GATE PASS: {direction} {symbol} | "
            f"Regime={regime} | Bias={synthesis_bias or 'N/A'} | "
            f"Confidence: {raw_confidence:.0f}% → {confidence:.0f}% | "
            f"Gates: {len(gates_passed)}/{len(gates_passed) + len(gates_failed)}"
        )

        return GateResult(
            blocked=False,
            reason=f"✅ PASS: {direction} {symbol} ({len(gates_passed)} gates passed)",
            adjusted_confidence=confidence,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            regime=regime,
            bias=synthesis_bias or "NEUTRAL",
        )

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
