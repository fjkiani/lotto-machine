"""
⚡ Jobless Claims Pre-Signal Predictor

Predicts Initial Jobless Claims vs consensus BEFORE the Thursday print.
Reuses the same FRED ICSA plumbing from ADPPredictor.

Architecture: implements BasePreSignalPredictor for registry pattern in brief.py.
"""
import os
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"


class JoblessClaimsPredictor:
    """
    ICSA 4-week average vs TE consensus for Initial Jobless Claims.
    Emits MISS_LIKELY / BEAT_LIKELY / IN_LINE with reasons.
    """

    EVENT_NAME = "Initial Jobless Claims"
    ALERT_TYPE = "JOBLESS_PRESIGNAL"

    def __init__(self):
        self.api_key = os.getenv("FRED_API_KEY", "")
        if not self.api_key:
            logger.warning("⚠️ FRED_API_KEY not set — JoblessClaimsPredictor disabled")

    def _fetch(self, series_id: str, limit: int = 6) -> list:
        """Fetch latest N observations from FRED as float list (newest first)."""
        if not self.api_key:
            return []
        try:
            r = requests.get(
                f"{FRED_BASE}/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": limit,
                },
                timeout=10,
            )
            r.raise_for_status()
            obs = r.json().get("observations", [])
            return [float(o["value"]) for o in obs if o.get("value", ".") != "."]
        except Exception as e:
            logger.warning(f"FRED fetch failed for {series_id}: {e}")
            return []

    def _get_consensus(self, fallback: int = 210_000) -> int:
        """
        Get TE consensus for Initial Jobless Claims from veto calendar if available.
        Falls back to provided value (TE consensus is 210K this week).
        """
        try:
            from backend.app.api.v1.brief import _lazy
            from live_monitoring.enrichment.apis.economic_veto import EconomicVetoEngine
            ve = _lazy("ve", EconomicVetoEngine)
            upcoming = ve.get_upcoming_critical_events() if hasattr(ve, "get_upcoming_critical_events") else []
            for ev in upcoming:
                name = ev.get("event", "").lower()
                if "jobless" in name or "initial claims" in name:
                    cons = ev.get("consensus", "")
                    if cons and cons not in ("—", "", "N/A"):
                        # consensus is like "210K" or "210,000"
                        cleaned = str(cons).replace("K", "000").replace(",", "").replace(" ", "")
                        return int(float(cleaned))
        except Exception as e:
            logger.debug(f"Could not get dynamic consensus: {e}")
        return fallback

    def predict(self) -> dict:
        """
        Generate Jobless Claims pre-signal.
        Compares 4-week ICSA average vs consensus.
        Returns: signal, delta, confidence, reasons, edge
        """
        consensus = self._get_consensus(fallback=210_000)
        reasons = []
        adjustments = []
        inputs = {}

        # ICSA 4-week average
        icsa_vals = self._fetch("ICSA", limit=6)
        if not icsa_vals:
            return {
                "error": "FRED ICSA unavailable",
                "consensus": consensus,
            }

        icsa_4wk = icsa_vals[:4]
        icsa_avg = sum(icsa_4wk) / len(icsa_4wk)
        icsa_latest = icsa_vals[0]
        inputs["icsa_latest"] = round(icsa_latest)
        inputs["icsa_4wk_avg"] = round(icsa_avg)
        inputs["consensus"] = consensus

        # Trend: is claims accelerating or decelerating?
        if len(icsa_vals) >= 4:
            trend_delta = icsa_vals[0] - icsa_vals[3]  # latest vs 4 weeks ago
            inputs["4wk_trend"] = round(trend_delta)
            if trend_delta > 10_000:
                reasons.append(f"ICSA rising +{trend_delta:,.0f} over 4 weeks → claims worsening")
            elif trend_delta < -10_000:
                reasons.append(f"ICSA falling {trend_delta:,.0f} over 4 weeks → claims improving")
            else:
                reasons.append(f"ICSA flat trend ({trend_delta:+,.0f} over 4 weeks)")

        # Core signal: 4-week avg vs consensus
        delta = round(icsa_avg) - consensus

        if delta > 15_000:
            signal = "MISS_LIKELY"  # claims higher than expected = worse labor
            confidence = 0.70 if delta > 25_000 else 0.55
            reasons.append(f"ICSA 4wk avg {icsa_avg:,.0f} vs consensus {consensus:,} → +{delta:,} (MISS)")
        elif delta < -15_000:
            signal = "BEAT_LIKELY"  # claims lower than expected = better labor
            confidence = 0.70 if delta < -25_000 else 0.55
            reasons.append(f"ICSA 4wk avg {icsa_avg:,.0f} vs consensus {consensus:,} → {delta:,} (BEAT)")
        else:
            signal = "IN_LINE"
            confidence = 0.40
            reasons.append(f"ICSA 4wk avg {icsa_avg:,.0f} vs consensus {consensus:,} → {delta:+,} (IN LINE)")

        sign = "+" if delta > 0 else ""
        return {
            "event": self.EVENT_NAME,
            "consensus": consensus,
            "icsa_4wk_avg": round(icsa_avg),
            "icsa_latest": round(icsa_latest),
            "delta": delta,
            "signal": signal,
            "confidence": confidence,
            "reasons": reasons,
            "inputs": inputs,
            "as_of": datetime.utcnow().isoformat(),
            "edge": f"ICSA 4wk avg {icsa_avg:,.0f} vs consensus {consensus:,} → {sign}{delta:,} ({signal})",
        }


# ─── Standalone Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    predictor = JoblessClaimsPredictor()
    result = predictor.predict()
    print(json.dumps(result, indent=2))
