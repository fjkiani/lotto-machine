"""
Canonical position-sizing engine — SINGLE SOURCE OF TRUTH for trade size.

Replaces the hardcoded sizing constants scattered across confluence_gate
(CHOPPY 0.5x, TREND_EXTENDED 1.5x, BREAKDOWN 1.0x, kill-chain 3.0/1.0/0.5)
with ONE multiplicative penalty stack. Every step logs its intermediate
value. The unclamped size is logged BEFORE the 2.0x clamp on every call,
permanently.

Hard rules (from the sizing-inversion audit):
  - PROVEN-EDGE CAP: any signal family with ZERO measured outcome records
    gets base <= 0.85x. Nothing exceeds 1.0x without a calibration curve
    (measured win-rate by confidence band). Unproven chase can never
    out-size a structural setup.
  - MULTIPLICATIVE STACK, not a cascade floor: base_band x regime_mult x
    modifiers, each logged. No single hardcoded constant decides size.
  - UNCLAMPED LOG: the raw product is logged before clamping to [0, 2.0],
    so boost-stacking past the ceiling is visible, not hidden.
  - NO-TRADE FLOOR: final clamped size < 0.10x -> 0.0 (NO-TRADE).

The 0.082x-vs-1.27x inversion this fixes: a structural short (base 0.35 x
CHOPPY 0.6 x no-KC 0.7 x negGEX 0.8 x opposed-bias 0.7 = 0.082x -> NO-TRADE)
while an unproven 86% chase got 1.27x. The proven-edge cap + multiplicative
stack make that ordering impossible without measured outcomes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# ── Hard limits ───────────────────────────────────────────────────────────
MAX_SIZE = 2.0            # ceiling clamp
NO_TRADE_FLOOR = 0.10     # below this -> NO-TRADE (0.0)
PROVEN_EDGE_BASE_CAP = 0.85   # base cap when zero measured outcomes
CALIBRATION_REQUIRED_FOR = 1.0  # nothing above this without a calibration curve

# ── Base bands by adjusted confidence (%) ─────────────────────────────────
BASE_BANDS = [
    (55, 0.15),
    (65, 0.35),
    (75, 0.60),
    (85, 0.85),
    (92, 1.10),
    (101, 1.30),   # >= 92
]

# ── Regime multipliers: {regime: (long_mult, short_mult)} ─────────────────
REGIME_MULT = {
    "BULLISH":          (1.0, 0.6),
    "UPTREND":          (1.0, 0.5),
    "STRONG_UPTREND":   (1.0, 0.5),
    "TREND_EXTENDED":   (1.2, 0.4),
    "CHOPPY":           (0.6, 0.6),
    "DOWNTREND":        (0.5, 1.0),
    "STRONG_DOWNTREND": (0.4, 1.2),
    "BREAKDOWN":        (0.3, 1.2),
    "UNKNOWN":          (0.5, 0.5),
}


@dataclass
class SizingResult:
    """Full audit trail of one sizing decision."""
    size: float                 # final clamped size (0.0 = NO-TRADE)
    unclamped_size: float       # raw product BEFORE the 2.0x clamp
    no_trade: bool              # True if below NO_TRADE_FLOOR
    base: float                 # base band value
    regime_mult: float          # regime multiplier applied
    proven_edge_capped: bool    # True if base was capped for lack of outcomes
    calibration_capped: bool    # True if clamped to <=1.0 for no calibration
    steps: List[str] = field(default_factory=list)  # per-step logged intermediates
    inputs: Dict = field(default_factory=dict)


def _base_band(confidence: float) -> float:
    for ceiling, mult in BASE_BANDS:
        if confidence < ceiling:
            return mult
    return BASE_BANDS[-1][1]


def compute_size(
    direction: str,
    confidence: float,
    regime: str,
    dp_score: Optional[float] = None,          # 0..1 DP confluence (None = no DP)
    kill_chain_layers: int = 0,                # 0..3 active kill-chain layers
    kill_chain_triple: bool = False,           # triple active
    neg_gex: bool = False,                     # GEX negative
    short_vol_pct: Optional[float] = None,     # e.g. 60.9 for 60.9%
    bias: Optional[str] = None,                # synthesis bias BULLISH/BEARISH/NEUTRAL
    has_synthesis: bool = True,                # False -> no-synthesis penalty
    econ_regime: str = "NORMAL",               # NORMAL -> 0.85x penalty
    measured_outcomes: int = 0,                # count of measured outcome records for this family
    has_calibration_curve: bool = False,       # True if a WR-by-band curve exists
) -> SizingResult:
    """
    THE sizing function. Multiplicative stack with per-step logging.

    Returns SizingResult with the full audit trail. The unclamped size is
    logged before the clamp on EVERY call (permanent instrumentation).
    """
    steps: List[str] = []
    direction = (direction or "LONG").upper()
    regime = (regime or "UNKNOWN").upper()
    inputs = dict(direction=direction, confidence=confidence, regime=regime,
                  dp_score=dp_score, kill_chain_layers=kill_chain_layers,
                  kill_chain_triple=kill_chain_triple, neg_gex=neg_gex,
                  short_vol_pct=short_vol_pct, bias=bias,
                  has_synthesis=has_synthesis, econ_regime=econ_regime,
                  measured_outcomes=measured_outcomes,
                  has_calibration_curve=has_calibration_curve)

    # ── 1. Base band ──────────────────────────────────────────────────────
    base = _base_band(confidence)
    steps.append(f"base_band(conf={confidence:.0f}%)={base:.3f}")

    # ── 2. PROVEN-EDGE CAP: zero measured outcomes -> base <= 0.85x ───────
    proven_edge_capped = False
    if measured_outcomes <= 0 and base > PROVEN_EDGE_BASE_CAP:
        base = PROVEN_EDGE_BASE_CAP
        proven_edge_capped = True
        steps.append(f"PROVEN-EDGE CAP: 0 outcomes -> base capped to {PROVEN_EDGE_BASE_CAP:.3f}")

    size = base

    # ── 3. Regime multiplier ──────────────────────────────────────────────
    long_mult, short_mult = REGIME_MULT.get(regime, REGIME_MULT["UNKNOWN"])
    regime_mult = long_mult if direction == "LONG" else short_mult
    size *= regime_mult
    steps.append(f"regime_mult({regime}/{direction})={regime_mult:.3f} -> {size:.3f}")

    # ── 4. DP confluence modifier ─────────────────────────────────────────
    if dp_score is not None:
        if dp_score >= 0.85:
            size *= 1.5
            steps.append(f"dp_modifier(>={0.85})=x1.500 -> {size:.3f}")
        elif dp_score >= 0.75:
            size *= 1.25
            steps.append(f"dp_modifier(>=0.75)=x1.250 -> {size:.3f}")

    # ── 5. Kill-chain modifier ────────────────────────────────────────────
    if kill_chain_triple:
        size *= 1.5
        steps.append(f"kc_modifier(TRIPLE)=x1.500 -> {size:.3f}")
    elif kill_chain_layers >= 2:
        size *= 1.2
        steps.append(f"kc_modifier({kill_chain_layers} layers)=x1.200 -> {size:.3f}")
    elif kill_chain_layers == 0:
        size *= 0.7
        steps.append(f"kc_modifier(0 layers)=x0.700 -> {size:.3f}")

    # ── 6. negGEX modifier ────────────────────────────────────────────────
    if neg_gex:
        size *= 0.8
        steps.append(f"negGEX=x0.800 -> {size:.3f}")

    # ── 7. Short-volume modifier ──────────────────────────────────────────
    if short_vol_pct is not None and short_vol_pct > 55.0:
        if direction == "LONG":
            size *= 0.8
            steps.append(f"sv({short_vol_pct:.0f}%>55 LONG)=x0.800 -> {size:.3f}")
        else:
            size *= 1.1
            steps.append(f"sv({short_vol_pct:.0f}%>55 SHORT)=x1.100 -> {size:.3f}")

    # ── 8. Bias alignment modifier ────────────────────────────────────────
    if bias:
        b = bias.upper()
        aligned = (direction == "LONG" and b == "BULLISH") or (direction == "SHORT" and b == "BEARISH")
        opposed = (direction == "LONG" and b == "BEARISH") or (direction == "SHORT" and b == "BULLISH")
        if aligned:
            size *= 1.1
            steps.append(f"bias_aligned({b})=x1.100 -> {size:.3f}")
        elif opposed:
            size *= 0.7
            steps.append(f"bias_opposed({b})=x0.700 -> {size:.3f}")

    # ── 9. No-synthesis penalty ───────────────────────────────────────────
    if not has_synthesis:
        size *= 0.7
        steps.append(f"no_synthesis=x0.700 -> {size:.3f}")

    # ── 10. Econ regime penalty ───────────────────────────────────────────
    if econ_regime and econ_regime.upper() == "NORMAL":
        size *= 0.85
        steps.append(f"econ(NORMAL)=x0.850 -> {size:.3f}")

    # ── UNCLAMPED LOG (permanent, before clamp) ───────────────────────────
    unclamped = size
    logger.info(
        f"📐 SIZING unclamped={unclamped:.4f} | {direction} conf={confidence:.0f}% "
        f"regime={regime} | steps: {' | '.join(steps)}"
    )

    # ── 11. CALIBRATION CAP: nothing above 1.0x without a curve ──────────
    calibration_capped = False
    if not has_calibration_curve and size > CALIBRATION_REQUIRED_FOR:
        size = CALIBRATION_REQUIRED_FOR
        calibration_capped = True
        steps.append(f"CALIBRATION CAP: no curve -> clamped to {CALIBRATION_REQUIRED_FOR:.3f}")

    # ── 12. Clamp to [0, MAX_SIZE] ────────────────────────────────────────
    clamped = max(0.0, min(size, MAX_SIZE))
    if clamped != size:
        steps.append(f"clamp[{0.0},{MAX_SIZE}] {size:.3f} -> {clamped:.3f}")

    # ── 13. NO-TRADE floor ────────────────────────────────────────────────
    no_trade = clamped < NO_TRADE_FLOOR
    final = 0.0 if no_trade else round(clamped, 4)
    if no_trade:
        steps.append(f"NO-TRADE: {clamped:.3f} < {NO_TRADE_FLOOR} floor")

    logger.info(
        f"📐 SIZING final={final:.4f} (unclamped={unclamped:.4f}, "
        f"no_trade={no_trade}, proven_capped={proven_edge_capped}, "
        f"calib_capped={calibration_capped})"
    )

    return SizingResult(
        size=final,
        unclamped_size=round(unclamped, 4),
        no_trade=no_trade,
        base=base,
        regime_mult=regime_mult,
        proven_edge_capped=proven_edge_capped,
        calibration_capped=calibration_capped,
        steps=steps,
        inputs=inputs,
    )
