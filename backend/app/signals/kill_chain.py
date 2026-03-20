"""
Kill Chain scorer — computes a multi-layer confluence score + market direction.

Direction is derived from actual data signals, NOT hardcoded.

Returned dict shape:
    {
        "score": int,           # 0-10+
        "verdict": str,         # BOOST | NEUTRAL | SOFT_VETO | HARD_VETO
        "direction": str,       # BULLISH | BEARISH | MIXED
        "bearish_points": int,  # score contribution toward SHORT thesis
        "bullish_points": int,  # score contribution toward LONG thesis
        "layers": dict,         # per-layer debug info
        "errors": bool,
    }
"""
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

_kc_cache: Dict[str, Any] = {"data": None, "ts": 0}
_CACHE_TTL = 300  # 5 minutes


def compute_kill_chain() -> dict:
    """Compute the kill chain score with real directional bias.

    Caches for 5 minutes. Each layer fails independently — a layer error
    lowers reliability but doesn't kill the whole computation.
    """
    now = time.time()
    if _kc_cache["data"] and (now - _kc_cache["ts"]) < _CACHE_TTL:
        return _kc_cache["data"]

    bullish_pts = 0
    bearish_pts = 0
    layers: Dict[str, Any] = {}

    # ── Layer 1: Brain Manager (insider/politician divergence) ────────────────
    # Brain boost is directional — high boost = smart money is positioned.
    # We read the direction from the brain report itself; default is NEUTRAL.
    try:
        from live_monitoring.core.brain_manager import BrainManager
        brain = BrainManager().get_report(use_cache=True)
        if brain:
            boost = brain.get("divergence_boost", 0)
            brain_direction = str(brain.get("direction", "NEUTRAL")).upper()
            layers["brain_boost"] = boost
            layers["brain_direction"] = brain_direction
            if "BEAR" in brain_direction:
                bearish_pts += boost
            else:
                bullish_pts += boost
    except Exception as exc:
        layers["brain_error"] = str(exc)

    # ── Layer 2: COT Divergence ───────────────────────────────────────────────
    # COT specs net short at extreme = CONTRARIAN bullish ONLY when divergent=True
    # (i.e. commercials are simultaneously net long, indicating real hedgers disagree).
    # If specs are short but NOT divergent, trend-following says BEARISH.
    try:
        from live_monitoring.enrichment.apis.cot_client import COTClient
        cot = COTClient(cache_ttl=3600).get_divergence_signal("ES")
        if cot:
            specs = cot.get("specs_net", 0)
            comms = cot.get("comm_net", 0)
            divergent = cot.get("divergent", False)
            layers["cot_specs_net"] = specs
            layers["cot_comm_net"] = comms
            layers["cot_divergent"] = divergent

            if divergent and specs < -100_000 and comms > 50_000:
                # Classic extreme divergence — historically bullish reversal
                bullish_pts += 3
                layers["cot_signal"] = "EXTREME_DIVERGENCE → BULLISH"
            elif divergent and specs < -50_000 and comms > 25_000:
                bullish_pts += 1
                layers["cot_signal"] = "MODERATE_DIVERGENCE → BULLISH"
            elif specs < -50_000 and not divergent:
                # Specs pile short and commercials are NOT lined up bullish
                # → specs may be right this time (trend continuation)
                bearish_pts += 1
                layers["cot_signal"] = "SPEC_SHORTS_NO_DIVERGENCE → BEARISH"
            else:
                layers["cot_signal"] = "NEUTRAL"
    except Exception as exc:
        layers["cot_error"] = str(exc)

    # ── Layer 3: GEX Regime ───────────────────────────────────────────────────
    # Negative GEX = dealers amplify moves.
    # In a downtrend it amplifies the DOWN move → bearish.
    # In an uptrend it amplifies the UP move → bullish.
    # We use SPY SV% as a proxy for current trend direction.
    try:
        from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator
        from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient

        gex_calc = GEXCalculator(cache_ttl=300)
        gex_result = gex_calc.compute_gex("SPX")
        regime = gex_result.gamma_regime or ""
        total_gex = gex_result.total_gex

        # Read SV% as trend proxy (>55 = institutional shorts active)
        sv_pct = 50.0
        try:
            sg = StockgridClient()
            sv_pct = sg.get_short_volume_pct("SPY") or 50.0
        except Exception:
            pass

        layers["gex_regime"] = regime
        layers["gex_total"] = total_gex
        layers["sv_pct"] = sv_pct

        if "NEGATIVE" in regime and abs(total_gex) > 10e9:
            if sv_pct > 55:
                # Negative gamma + heavy short flow = dealers amplifying downside
                bearish_pts += 2
                layers["gex_signal"] = "NEG_GEX + HIGH_SV → BEARISH AMPLIFIER"
            else:
                # Negative gamma but flow not bearish — snap-back risk
                bullish_pts += 1
                layers["gex_signal"] = "NEG_GEX + NEUTRAL_SV → SNAP_BACK_RISK"
        elif "POSITIVE" in regime:
            bullish_pts += 1
            layers["gex_signal"] = "POS_GEX → VOLATILITY SUPPRESSED (BULLISH BIAS)"
        else:
            layers["gex_signal"] = "NEUTRAL"
    except Exception as exc:
        layers["gex_error"] = str(exc)

    # ── Compute final verdict ─────────────────────────────────────────────────
    total_score = bullish_pts + bearish_pts

    # Direction: whichever side dominates, with a tie going MIXED
    if bullish_pts > bearish_pts + 1:
        direction = "BULLISH"
    elif bearish_pts > bullish_pts + 1:
        direction = "BEARISH"
    else:
        direction = "MIXED"

    # Verdict is based on total signal strength (direction-agnostic conviction level)
    if total_score > 7:
        verdict = "BOOST"
    elif total_score >= 5:
        verdict = "NEUTRAL"
    elif total_score > 0:
        verdict = "SOFT_VETO"
    else:
        verdict = "HARD_VETO"

    result = {
        "score": total_score,
        "verdict": verdict,
        "direction": direction,
        "bullish_points": bullish_pts,
        "bearish_points": bearish_pts,
        "layers": layers,
        "errors": any("error" in k for k in layers),
    }

    _kc_cache["data"] = result
    _kc_cache["ts"] = now
    return result
