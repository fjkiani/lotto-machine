"""
Signal classifier — maps alert_type + description → (action, confidence).

Rules
-----
* Returns (None, None) for non-trading noise (startup, health_ping, daily_recap).
* Returns (action: str, confidence: int) for anything actionable.
* action ∈ {"LONG", "SHORT", "WATCH", "AVOID"}
* No hardcoded directions — dp_ prefix is no longer treated as LONG by default.
"""
import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Types that are pure infrastructure noise — never surface to traders
_EXCLUDED_TYPES = frozenset({"startup", "daily_recap", "health_ping"})


def classify_alert(
    alert_type: str,
    description: str = "",
    embed_json_str: str = "",
) -> Tuple[Optional[str], Optional[int]]:
    """Map alert_type + description to (action, confidence).

    Returns:
        (None, None)          → exclude this alert entirely
        (action, confidence)  → emit as a signal
    """
    try:
        at = str(alert_type or "").lower().strip()
        desc = str(description or "")

        # ── 1. Exclude infrastructure noise ──────────────────────────────────
        if at in _EXCLUDED_TYPES or "startup" in at:
            return None, None

        # ── 2. Earnings: extract real 8-factor score ──────────────────────────
        if "earnings" in at:
            m = re.search(r"score:\s*(\d+)\s*/\s*100", desc, re.IGNORECASE)
            if m:
                try:
                    score = int(m.group(1))
                    if score >= 75:
                        # Strong score — check desc for directional hint
                        if any(w in desc.lower() for w in ("bearish", "downgrade", "miss")):
                            return "SHORT", min(score, 90)
                        return "LONG", min(score, 95)
                    elif score >= 60:
                        return "WATCH", score
                    else:
                        return "WATCH", max(score, 40)
                except ValueError:
                    pass
            return "WATCH", 55

        # ── 3. Explicit directional types (most specific first) ───────────────
        # SHORT signals
        if "selloff" in at or "sell_off" in at:
            return "SHORT", 78
        if "bearish" in at:
            return "SHORT", 72
        if "dp_selloff" in at or "dp_bearish" in at:
            # Dark pool flow is explicitly bearish — was incorrectly LONG before
            return "SHORT", 75

        # LONG signals
        if "rally" in at:
            return "LONG", 78
        if "bullish" in at:
            return "LONG", 72
        if "dp_rally" in at or "dp_bullish" in at:
            return "LONG", 75

        # Generic dark pool divergence — direction unknown without more context
        # Check description for directional keywords before defaulting
        if "divergence" in at or at.startswith("dp_"):
            desc_lower = desc.lower()
            if any(w in desc_lower for w in ("bearish", "short", "sell", "downside")):
                return "SHORT", 68
            if any(w in desc_lower for w in ("bullish", "long", "buy", "upside")):
                return "LONG", 68
            # Genuinely ambiguous — surface as WATCH, not directional
            return "WATCH", 60

        # ── 4. Informational / monitoring types ───────────────────────────────
        if "fed_watch" in at or "fed_monitor" in at:
            return "WATCH", 55
        if "overnight" in at:
            return "WATCH", 50
        if "level_watcher" in at:
            return "WATCH", 65
        if "options_flow" in at or "options_alert" in at:
            # Options flow without bias tag — treat as WATCH
            return "WATCH", 60

        # ── 5. Default: surface as WATCH, low conviction ──────────────────────
        return "WATCH", 50

    except Exception as exc:
        logger.warning(f"classify_alert error for '{alert_type}': {exc}")
        return "WATCH", 50
