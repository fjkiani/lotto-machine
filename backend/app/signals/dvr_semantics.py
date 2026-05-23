"""
Short-volume % semantics aligned with Kill Chain layer 3 (DVR).

Uses FINRA / Stockgrid-style "short volume %" (off-exchange short as % of total volume).
Thresholds are policy constants only — all displayed numbers come from upstream feeds.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Layer 3 arms when short vol exceeds this (matches kill_chain layer_3_triggered).
LAYER3_TRIGGER_PCT = 55.0
# Below this band: framework treats elevated off-exchange short as accumulation / demand skew.
ACCUMULATION_CEILING_PCT = 50.0


def interpret_dvr(short_vol_pct: Optional[float]) -> Dict[str, Any]:
    """
    Classify DVR without inventing prices or percentages.
    """
    if short_vol_pct is None:
        return {
            "zone": "UNKNOWN",
            "label": "NO_DATA",
            "layer3_triggered": False,
            "note": "Short volume percent unavailable — DVR cannot be classified.",
        }
    try:
        sv = float(short_vol_pct)
    except (TypeError, ValueError):
        return {
            "zone": "UNKNOWN",
            "label": "INVALID",
            "layer3_triggered": False,
            "note": "Short volume percent is not numeric.",
        }

    if sv > LAYER3_TRIGGER_PCT:
        return {
            "zone": "PANIC_THRESHOLD",
            "label": "LAYER3_ARMED",
            "layer3_triggered": True,
            "note": (
                f"Short vol {sv:.2f}% above {LAYER3_TRIGGER_PCT:.0f}% — "
                "Kill Chain layer 3 triggered (distribution / capitulation band per DVR rules)."
            ),
        }
    if sv >= ACCUMULATION_CEILING_PCT:
        return {
            "zone": "DISTRIBUTION_WATCH",
            "label": "BORDERLINE_PRE_LAYER3",
            "layer3_triggered": False,
            "note": (
                f"Short vol {sv:.2f}% in watch band [{ACCUMULATION_CEILING_PCT:.0f}, {LAYER3_TRIGGER_PCT:.0f}) — "
                "heavy off-exchange short vs demand; not institutional absorption; approaching layer 3."
            ),
        }
    return {
        "zone": "ACCUMULATION",
        "label": "INSTITUTIONAL_ABSORPTION",
        "layer3_triggered": False,
        "note": (
            f"Short vol {sv:.2f}% below {ACCUMULATION_CEILING_PCT:.0f}% — "
            "framework reads as demand skew / accumulation vs this metric."
        ),
    }
