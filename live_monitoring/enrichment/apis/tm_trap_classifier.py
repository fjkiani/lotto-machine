"""
tm_trap_classifier.py — Trap Classification + Conviction Scoring
==================================================================

Reads a MarketState and returns a list of classified TrapZone objects.
Each trap type is an isolated classifier function — add new types without
touching existing ones.

Conviction scoring (per trap zone):
  +1  Aligns with pivot level (±10 pts)
  +1  COT specs net short > 100K contracts
  +1  Dark pool STRONG position in zone
  +1  GEX gamma regime aligns
  +1  COT threshold bonus / VIX regime / MA alignment

Minimum conviction threshold before a trap is emitted:
  DEATH_CROSS_TRAP  → 2/5
  BEAR_TRAP_COIL    → 3/5
  BULL_TRAP         → 2/5
  CEILING_TRAP      → 3/5
  LIQUIDITY_TRAP    → 2/5
  WAR_HEADLINE      → 2/5
"""

import logging
from typing import List

from .tm_models import MarketState, TrapZone

logger = logging.getLogger(__name__)


# ─── Formatting helpers ──────────────────────────────────────────────────────

def _fmt_dollars(val: float) -> str:
    """Format a dollar amount to B/M/K display. E.g. 35_007_000_000 → $35.0B"""
    abs_val = abs(val)
    if abs_val >= 1e9:
        return f"${abs_val / 1e9:.1f}B"
    elif abs_val >= 1e6:
        return f"${abs_val / 1e6:.0f}M"
    elif abs_val >= 1e3:
        return f"${abs_val / 1e3:.0f}K"
    else:
        return f"${abs_val:.0f}"


def _fmt_volume(shares: float) -> str:
    """Format share volume to readable display. E.g. 14_260_564 → 14.3M shares"""
    abs_val = abs(shares)
    if abs_val >= 1e9:
        return f"{abs_val / 1e9:.1f}B shares"
    elif abs_val >= 1e6:
        return f"{abs_val / 1e6:.1f}M shares"
    elif abs_val >= 1e3:
        return f"{abs_val / 1e3:.0f}K shares"
    else:
        return f"{abs_val:.0f} shares"


# ─── Individual Classifiers ───────────────────────────────────────────────────

def _classify_death_cross(state: MarketState) -> List[TrapZone]:
    if not state.death_cross:
        return []

    conviction = 1
    sources = ["MA"]
    narrative = "MA50 crossed below MA200"
    data_point = ""

    if state.cot_net_spec and state.cot_net_spec < -100_000:
        conviction += 1
        sources.append("COT")
        data_point = f"COT: {state.cot_net_spec:,} Short"
        narrative = "COT commercials defend every cycle | Retail dumps → institutions buy"

    if state.pivots:
        classic = state.pivots.get("classic", {})
        for key in ["S1", "S2", "S3"]:
            if classic.get(key) and abs(state.current_price - classic[key]) <= 10:
                conviction += 1
                sources.append("PIVOT")
                break

    if conviction < 2:
        return []

    ma200 = state.moving_averages.get("MA200_SMA", {}).get("value", 0)
    return [TrapZone(
        trap_type="DEATH_CROSS_TRAP",
        price_min=ma200 - 5 if ma200 else state.current_price - 20,
        price_max=ma200 + 5 if ma200 else state.current_price - 10,
        conviction=min(conviction, 5),
        narrative=narrative,
        data_point=data_point,
        supporting_sources=sources,
        emoji="🔴",
    )]


def _classify_bear_trap_coil(state: MarketState) -> List[TrapZone]:
    if not (state.cot_net_spec and state.cot_net_spec < -50_000):
        return []

    price = state.current_price
    conviction = 1
    sources = ["COT"]
    narrative = "Specs trapped short"
    data_point = f"COT: {state.cot_net_spec:,} Short"

    # DP buying pressure — use symbol-level dp_position_dollars from Stockgrid
    if state.dp_position_dollars > 0 or any(dp.get("volume", 0) > 0 for dp in state.dp_levels):
        conviction += 1
        sources.append("DP")
        narrative = f"{_fmt_dollars(state.dp_position_dollars)} dark pool loading | Snap-back incoming"

    # COT threshold bonus
    if state.cot_net_spec < -100_000:
        conviction += 1
        data_point = f"COT: {state.cot_net_spec:,} Short | SPEC TRAP LOADED"

    # GEX regime
    if state.gamma_regime == "NEGATIVE":
        conviction += 1
        sources.append("GEX")

    # Pivot alignment
    if state.pivots:
        classic = state.pivots.get("classic", {})
        for key in ["S1", "P"]:
            if classic.get(key) and abs(price - classic[key]) <= 10:
                conviction += 1
                sources.append("PIVOT")
                break

    if conviction < 3:
        return []

    return [TrapZone(
        trap_type="BEAR_TRAP_COIL",
        price_min=price - 20,
        price_max=price,
        conviction=min(conviction, 5),
        narrative=narrative,
        data_point=data_point,
        supporting_sources=sources,
        emoji="🟢",
    )]


def _classify_bull_trap(state: MarketState) -> List[TrapZone]:
    price = state.current_price
    traps = []
    dp_resistance = [
        dp for dp in state.dp_levels
        if dp.get("type") == "RESISTANCE" and dp.get("strength") in ("STRONG", "MODERATE")
        and dp.get("price", 0) > price
    ]

    for dp in dp_resistance[:3]:
        dp_price = dp.get("price", 0)
        if not dp_price or (dp_price - price) / price >= 0.03:
            continue

        conviction = 1
        sources = ["DP"]
        # Use symbol-level dp_position_dollars directly
        data_point = f"{_fmt_dollars(state.dp_position_dollars)} dark prints"
        narrative = "Institutions dump here"

        if state.cot_net_spec and state.cot_net_spec < -50_000:
            conviction += 1
            sources.append("COT")

        if state.pivots:
            classic = state.pivots.get("classic", {})
            for key in ["R1", "R2", "R3"]:
                if classic.get(key) and abs(dp_price - classic[key]) <= 10:
                    conviction += 1
                    sources.append("PIVOT")
                    break

        for wall in state.gex_walls:
            if wall.get("signal") == "RESISTANCE" and abs(wall.get("strike", 0) - dp_price) <= 10:
                conviction += 1
                sources.append("GEX")
                break

        if conviction >= 2:
            traps.append(TrapZone(
                trap_type="BULL_TRAP",
                price_min=dp_price - 5,
                price_max=dp_price + 5,
                conviction=min(conviction, 5),
                narrative=narrative,
                data_point=data_point,
                supporting_sources=sources,
                emoji="🔴",
            ))

    return traps


def _classify_ceiling_trap(state: MarketState) -> List[TrapZone]:
    gex_resistance = [w for w in state.gex_walls if w.get("signal") == "RESISTANCE"]
    if not gex_resistance or not state.pivots:
        return []

    top_wall = gex_resistance[0]
    wall_price = top_wall.get("strike", 0)
    classic = state.pivots.get("classic", {})
    r2 = classic.get("R2", 0)
    r3 = classic.get("R3", 0)

    if not wall_price or not (abs(wall_price - r2) <= 15 or abs(wall_price - r3) <= 15):
        return []

    conviction = 2  # GEX + PIVOT already aligned
    sources = ["GEX", "PIVOT"]

    if state.cot_net_spec and state.cot_net_spec < -100_000:
        conviction += 1
        sources.append("COT")

    if conviction < 3:
        return []

    return [TrapZone(
        trap_type="CEILING_TRAP",
        price_min=wall_price - 5,
        price_max=wall_price + 5,
        conviction=min(conviction, 5),
        narrative=f"Failed tests at {wall_price:.0f} | COT specs short",
        data_point=f"GEX wall: {top_wall.get('gex', 0) / 1e9:.1f}B",
        supporting_sources=sources,
        emoji="🔴",
    )]


def _classify_liquidity_trap(state: MarketState) -> List[TrapZone]:
    if not state.pivots:
        return []

    price = state.current_price
    classic = state.pivots.get("classic", {})
    traps = []

    for key in ["S2", "S3"]:
        stop_level = classic.get(key, 0)
        if not stop_level or abs(price - stop_level) / price >= 0.02:
            continue

        conviction = 1
        sources = ["PIVOT"]
        dp_at_level = any(abs(dp.get("price", 0) - stop_level) <= 5 for dp in state.dp_levels)
        if dp_at_level:
            conviction += 1
            sources.append("DP")

        if conviction >= 2:
            traps.append(TrapZone(
                trap_type="LIQUIDITY_TRAP",
                price_min=stop_level - 5,
                price_max=stop_level + 5,
                conviction=min(conviction, 5),
                narrative="Stop hunt zone | Flip long off-exchange",
                data_point=f"Pivot {key}={stop_level:.2f}",
                supporting_sources=sources,
                emoji="🟡",
            ))

    return traps


def _classify_war_headline(state: MarketState) -> List[TrapZone]:
    if not (state.vix and state.vix > 30):
        return []

    price = state.current_price
    conviction = 2  # VIX > 30 = inherent FEAR signal
    sources = ["VIX"]

    if state.cot_net_spec and state.cot_net_spec < -100_000:
        conviction += 1
        sources.append("COT")

    return [TrapZone(
        trap_type="WAR_HEADLINE",
        price_min=price + 10,
        price_max=price + 30,
        conviction=min(conviction, 5),
        narrative=f"VIX={state.vix:.1f} FEAR regime | Real flow: energy dark prints",
        data_point=f"VIX regime: {state.vix_regime}",
        supporting_sources=sources,
        emoji="⚠️",
    )]


# ─── Public Classifier ───────────────────────────────────────────────────────

# Registry: add new classifiers here, nothing else to change
_CLASSIFIERS = [
    _classify_death_cross,
    _classify_bear_trap_coil,
    _classify_bull_trap,
    _classify_ceiling_trap,
    _classify_liquidity_trap,
    _classify_war_headline,
]


def classify_traps(state: MarketState) -> List[TrapZone]:
    """
    Run all classifiers against the current MarketState.

    Each classifier is independent and isolated.
    Returns traps sorted by conviction (highest first).
    """
    if not state.current_price:
        return []

    traps = []
    for classifier in _CLASSIFIERS:
        try:
            result = classifier(state)
            if result:
                traps.extend(result)
        except Exception as e:
            logger.warning(f"Classifier {classifier.__name__} failed: {e}")

    traps.sort(key=lambda t: t.conviction, reverse=True)
    return traps
