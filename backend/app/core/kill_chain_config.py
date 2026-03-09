"""
🐺 KILL CHAIN CONFIGURATION
Centralized source of truth for symbols, thresholds, and logic gating.
"""

from typing import Dict, List

# ─── Data Layer Settings ─────────────────────────────────────────────────────

# Default symbols for each layer
SYMBOLS = {
    "INDEX": "SPY",
    "FUTURES": "ES",
    "INDEX_FUTURES": "SPX",
    "SECTORS": ["QQQ", "IWM", "VIX"],
}

# Cache TTLs (seconds)
CACHE_TTLS = {
    "DARK_POOL": 300,        # 5 mins
    "COT": 3600,            # 1 hour
    "GEX": 300,              # 5 mins
    "SEC_13F": 3600 * 24,    # 24 hours (quarterly data doesn't change fast)
}

# ─── Thresholds & Limits ──────────────────────────────────────────────────────

# Dark Pool
DP_THRESHOLDS = {
    "HEAVY_POSITION_DOLLARS": 20_000_000_000,  # $20B
    "HIGH_SHORT_VOLUME_PCT": 50.0,
}

# COT (Commitment of Traders)
COT_THRESHOLDS = {
    "SPECS_HEAVY_SHORT": -100_000,
    "DIVERGENCE_MAGNITUDE": 200_000,
}

# GEX (Gamma Exposure)
GEX_THRESHOLDS = {
    "STRONG_SUPPORT_GEX": 200_000,
    "STRONG_RESISTANCE_GEX": 500_000,
}

# 13F Institutional Funds
TRACKED_FUNDS = [
    "Bridgewater Associates",
    "Soros Fund Management",
    "Berkshire Hathaway",
    "Point72 Asset Management",
    "Citadel Advisors",
]

# ─── Alert Severity Mapping ───────────────────────────────────────────────────

ALERT_COLORS = {
    "RED": "🔴 RED ALERT",
    "YELLOW": "🟡 WARNING",
    "GREEN": "🟢 NORMAL",
}
