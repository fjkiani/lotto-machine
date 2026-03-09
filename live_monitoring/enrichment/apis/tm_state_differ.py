"""
tm_state_differ.py — Rebuild Gate + Alert Level
=================================================

Decides whether the Trap Matrix chart needs to be rebuilt.
Also computes the overall alert level from trap convictions.

Operates entirely on MarketState snapshots — no I/O, no agent calls.

Design rule: Each check is isolated and independently testable.
"""

import logging
from typing import Tuple

from .tm_models import MarketState

logger = logging.getLogger(__name__)


# ─── Alert Level ─────────────────────────────────────────────────────────────

def compute_alert_level(state: MarketState) -> str:
    """
    Compute RED / YELLOW / GREEN from the highest trap conviction.

    RED    ≥ 4/5 conviction
    YELLOW ≥ 3/5 conviction
    GREEN  < 3 or no traps
    """
    if not state.traps:
        return "GREEN"
    max_conviction = max(t.conviction for t in state.traps)
    if max_conviction >= 4:
        return "RED"
    if max_conviction >= 3:
        return "YELLOW"
    return "GREEN"


# ─── Rebuild Gate ─────────────────────────────────────────────────────────────

def should_rebuild(old: MarketState, new: MarketState) -> Tuple[bool, str]:
    """
    Decide whether the chart needs rebuilding based on state diff.

    Returns (rebuild: bool, reason: str).
    Prevents chart spam by filtering sub-threshold moves.

    Triggers:
      1. Gamma flip shifted > 10 points
      2. Max pain shifted > 10 points
      3. COT direction flipped (long ↔ short)
      4. GEX regime changed (POSITIVE ↔ NEGATIVE)
      5. New high-conviction trap (≥ 4/5) appeared
      6. VIX regime changed
      7. Death cross appeared or cleared
    """
    reasons = []

    # 1. Gamma flip level shift
    if old.gamma_flip and new.gamma_flip:
        if abs(new.gamma_flip - old.gamma_flip) > 10:
            reasons.append(f"gamma_flip_{old.gamma_flip:.0f}→{new.gamma_flip:.0f}")

    # 2. Max pain shift
    if old.max_pain and new.max_pain:
        if abs(new.max_pain - old.max_pain) > 10:
            reasons.append("max_pain_shifted")

    # 3. COT direction flip
    if old.cot_net_spec and new.cot_net_spec:
        if (old.cot_net_spec > 0) != (new.cot_net_spec > 0):
            reasons.append("cot_direction_flipped")

    # 4. GEX regime change
    if old.gamma_regime != new.gamma_regime and new.gamma_regime != "UNKNOWN":
        reasons.append(f"gex_regime_{old.gamma_regime}→{new.gamma_regime}")

    # 5. New high-conviction trap appeared
    old_high = {t.trap_type for t in old.traps if t.conviction >= 4}
    new_high = {t.trap_type for t in new.traps if t.conviction >= 4}
    new_traps = new_high - old_high
    if new_traps:
        reasons.append(f"new_high_conviction: {','.join(new_traps)}")

    # 6. VIX regime change
    if old.vix_regime != new.vix_regime and new.vix_regime != "UNKNOWN":
        reasons.append(f"vix_regime_{old.vix_regime}→{new.vix_regime}")

    # 7. Death cross status change
    if old.death_cross != new.death_cross:
        reasons.append("death_cross_changed")

    rebuild = len(reasons) > 0
    reason = " | ".join(reasons) if reasons else "no_change"
    return rebuild, reason
