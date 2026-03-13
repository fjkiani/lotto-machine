"""
Morning Brief Generator — Produces the trader's zero-click daily brief.

Reads from SignalIntelEngine + DP divergence flags.
Any ticker with SV% > 55 AND negative DP position trend = BLOCKED.
Only tickers that pass DP + signal confluence = APPROVED.

Output: morning_brief.json in /tmp/morning_briefs/YYYY-MM-DD.json
"""

import json
import logging
import os
from datetime import datetime, date
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

BRIEF_DIR = "/tmp/morning_briefs"


class MorningBriefGenerator:
    """Generates the trader brief from SignalIntelEngine output."""

    def __init__(self):
        os.makedirs(BRIEF_DIR, exist_ok=True)

    def generate(self, force: bool = False) -> Dict[str, Any]:
        """Generate today's brief. Returns the brief dict and writes to disk."""
        today = date.today().isoformat()
        brief_path = os.path.join(BRIEF_DIR, f"{today}.json")

        # If already generated today and not forcing, return cached
        if not force and os.path.exists(brief_path):
            with open(brief_path) as f:
                return json.load(f)

        # ── Stage 1: Get signal intel ────────────────────────────────
        from live_monitoring.enrichment.apis.signal_intel_engine import SignalIntelEngine
        engine = SignalIntelEngine()
        intel = engine.generate_report()

        # ── Stage 2: Get DP divergence for bull tickers ──────────────
        from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
        client = StockgridClient(cache_ttl=120)

        bull_tickers = intel.get("bull_signals", {}).get("tickers", [])
        ticker_intel = intel.get("bull_signals", {}).get("intel", {})

        approved = []
        blocked = []

        for t in bull_tickers:
            info = ticker_intel.get(t, {})
            sv = info.get("sv_pct", 50)
            dp_dollars = info.get("dp_position_dollars", 0)
            bias = info.get("bias", "UNKNOWN")

            # DP divergence gate: high SV% + negative DP = BLOCKED
            is_dp_diverging = sv > 55
            is_dp_negative = dp_dollars > 0  # positive DP position = net short exposure

            # Also check SV trend if available
            try:
                raw = client.get_ticker_detail_raw(t, window=5)
                sv_table = raw.get("individual_short_volume_table", {}) if raw else {}
                items = sv_table.get("data", []) if isinstance(sv_table, dict) else sv_table if isinstance(sv_table, list) else []
                sorted_items = sorted(items, key=lambda x: x.get("date", ""))
                if len(sorted_items) >= 2:
                    prev_sv = float(sorted_items[-2].get("short_volume_pct", sorted_items[-2].get("short_volume%", 0)) or 0)
                    curr_sv = float(sorted_items[-1].get("short_volume_pct", sorted_items[-1].get("short_volume%", 0)) or 0)
                    if prev_sv <= 1: prev_sv *= 100
                    if curr_sv <= 1: curr_sv *= 100
                    sv_rising = curr_sv > prev_sv + 2
                else:
                    sv_rising = False
            except Exception:
                sv_rising = False

            entry = {
                "ticker": t,
                "sv_pct": sv,
                "bias": bias,
                "dp_position_dollars": dp_dollars,
            }

            if is_dp_diverging:
                reason = f"SV {sv:.1f}% (heavy short)"
                if sv_rising:
                    reason += " + SV rising"
                if is_dp_negative:
                    reason += " + net short DP"
                entry["reason"] = reason
                entry["flag"] = "DP_DIVERGING"
                blocked.append(entry)
            elif bias in ("LOW_SHORT_VOL_BULLISH",):
                entry["reason"] = f"SV {sv:.1f}% (bullish flow), clean DP"
                entry["flag"] = "CLEAN"
                approved.append(entry)
            else:
                entry["reason"] = f"SV {sv:.1f}% (neutral)"
                entry["flag"] = "NEUTRAL"
                approved.append(entry)

        # ── Stage 3: Build brief ─────────────────────────────────────
        spy_wall = intel.get("spy_vs_wall", {})
        close_def = intel.get("close_defense", {})
        verdict_data = intel.get("verdict", {})
        walls = intel.get("walls", {})

        # SPY summary
        spy_summary = {
            "price": spy_wall.get("current_price"),
            "call_wall": walls.get("SPY", {}).get("call_wall"),
            "put_wall": walls.get("SPY", {}).get("put_wall"),
            "delta_from_wall": spy_wall.get("delta_from_wall"),
            "trend": spy_wall.get("trend"),
            "close_defense": close_def.get("defense"),
            "close_vol_ratio": close_def.get("vol_ratio"),
        }

        # QQQ summary
        qqq_sv = intel.get("qqq_sv_trend", {})
        qqq_summary = {
            "call_wall": walls.get("QQQ", {}).get("call_wall"),
            "put_wall": walls.get("QQQ", {}).get("put_wall"),
            "sv_direction": qqq_sv.get("direction"),
            "sv_read": qqq_sv.get("read"),
        }

        # IWM summary
        iwm_summary = {
            "call_wall": walls.get("IWM", {}).get("call_wall"),
            "put_wall": walls.get("IWM", {}).get("put_wall"),
        }

        # Volume profile
        vol_profile = intel.get("volume_profile", {})

        # Build the summary sentence
        approved_names = [t["ticker"] for t in approved if t.get("flag") == "CLEAN"]
        blocked_names = [t["ticker"] for t in blocked]

        summary_parts = []
        if close_def.get("defense") == "DEFENDED":
            summary_parts.append(f"Wall defended at ${walls.get('SPY', {}).get('call_wall', '?')} with {close_def.get('vol_ratio', '?')}x close volume")
        elif close_def.get("defense") == "BREACHED":
            summary_parts.append(f"Wall BREACHED — caution")

        if qqq_sv.get("direction") == "FALLING":
            summary_parts.append("QQQ loading complete")
        elif qqq_sv.get("direction") == "RISING":
            summary_parts.append("QQQ still accumulating")

        if approved_names:
            summary_parts.append(f"Clean entries: {', '.join(approved_names)}")
        if blocked_names:
            summary_parts.append(f"Blocked (DP diverging): {', '.join(blocked_names)}")

        brief = {
            "date": today,
            "generated_at": datetime.now().strftime("%H:%M ET"),
            "verdict": verdict_data.get("signal", "UNKNOWN"),
            "signals": verdict_data.get("signals", []),
            "spy": spy_summary,
            "qqq": qqq_summary,
            "iwm": iwm_summary,
            "volume_profile": {
                "pattern": vol_profile.get("pattern"),
                "first_hour_pct": vol_profile.get("first_hour_pct"),
                "front_back_ratio": vol_profile.get("front_back_ratio"),
            },
            "approved_tickers": approved,
            "blocked_tickers": blocked,
            "summary": ". ".join(summary_parts) + ".",
        }

        # Write to disk
        with open(brief_path, "w") as f:
            json.dump(brief, f, indent=2, default=str)
        logger.info(f"📋 Morning brief written: {brief_path}")

        return brief

    @staticmethod
    def get_latest() -> Dict[str, Any]:
        """Read the most recent brief from disk (no generation)."""
        if not os.path.exists(BRIEF_DIR):
            return {"error": "No briefs generated yet"}

        files = sorted(f for f in os.listdir(BRIEF_DIR) if f.endswith(".json"))
        if not files:
            return {"error": "No briefs generated yet"}

        latest = os.path.join(BRIEF_DIR, files[-1])
        with open(latest) as f:
            return json.load(f)
