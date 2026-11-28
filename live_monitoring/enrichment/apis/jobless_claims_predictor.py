"""
⚡ Jobless Claims Pre-Signal Predictor

Predicts Initial Jobless Claims vs consensus BEFORE the Thursday print.
Consensus from live TE calendar / jobless-claims indicator page only.
No invented 210K floors. FRED ICSA missing → degraded, no fake series.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"


class JoblessClaimsPredictor:
    """
    ICSA 4-week average vs TE consensus for Initial Jobless Claims.
    Emits MISS_LIKELY / BEAT_LIKELY / IN_LINE with reasons — or degraded.
    """

    EVENT_NAME = "Initial Jobless Claims"
    ALERT_TYPE = "JOBLESS_PRESIGNAL"

    def __init__(self):
        self.api_key = os.getenv("FRED_API_KEY", "")
        if not self.api_key:
            logger.warning("⚠️ FRED_API_KEY not set — JoblessClaimsPredictor FRED inputs degraded")

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

    @staticmethod
    def _parse_claims(raw: Optional[str]) -> Optional[int]:
        if raw is None:
            return None
        s = str(raw).strip()
        if not s or s in ("—", "-", "N/A", "n/a", ""):
            return None
        u = s.upper().replace(",", "").replace(" ", "")
        if u.endswith("K"):
            try:
                return int(round(float(u[:-1]) * 1000))
            except ValueError:
                return None
        try:
            v = float(u)
            # Values like 195 are typically thousands on TE tables when labeled K elsewhere;
            # TE jobless page uses "195K" style. Plain 195000 also accepted.
            if 50 <= abs(v) <= 500:
                return int(round(v * 1000))
            return int(round(v))
        except ValueError:
            m = re.search(r"[-+]?\d+(\.\d+)?", u)
            if not m:
                return None
            return JoblessClaimsPredictor._parse_claims(m.group(0) + ("K" if "K" in s.upper() else ""))

    def _get_consensus(self) -> Tuple[Optional[int], str]:
        """Live TE consensus only — never invent a 210K floor."""
        # 1) TECalendarScraper
        try:
            from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper

            scraper = TECalendarScraper(cache_ttl=900)
            for ev in list(scraper.get_upcoming(days=21)) + list(scraper.get_us_calendar()):
                name = (ev.event or "").lower()
                if "jobless" not in name and "initial claims" not in name:
                    continue
                if "continuing" in name:
                    continue
                for raw in (ev.consensus, ev.forecast):
                    v = self._parse_claims(raw)
                    if v is not None:
                        return v, getattr(ev, "source", "te_calendar")
        except Exception as e:
            logger.debug("TE calendar jobless consensus failed: %s", e)

        # 2) Economic veto engine (if wired)
        try:
            from backend.app.api.v1.brief import _lazy
            from live_monitoring.enrichment.apis.economic_veto import EconomicVetoEngine

            ve = _lazy("ve", EconomicVetoEngine)
            upcoming = (
                ve.get_upcoming_critical_events()
                if hasattr(ve, "get_upcoming_critical_events")
                else []
            )
            for ev in upcoming:
                name = str(ev.get("event", "")).lower()
                if "jobless" in name or "initial claims" in name:
                    v = self._parse_claims(ev.get("consensus"))
                    if v is not None:
                        return v, "economic_veto"
        except Exception as e:
            logger.debug("Could not get dynamic consensus from veto: %s", e)

        return None, "unavailable"

    def predict(self) -> dict:
        """
        Generate Jobless Claims pre-signal.
        Compares 4-week ICSA average vs live consensus.
        """
        consensus, consensus_source = self._get_consensus()
        reasons = []
        inputs = {}
        fred_degraded = not bool(self.api_key)

        icsa_vals = self._fetch("ICSA", limit=6)
        if not icsa_vals:
            return {
                "event": self.EVENT_NAME,
                "error": "FRED ICSA unavailable",
                "consensus": consensus,
                "consensus_source": consensus_source,
                "degraded": True,
                "fred_degraded": True,
                "icsa_4wk_avg": None,
                "icsa_latest": None,
                "signal": None,
                "delta": None,
                "reasons": [
                    "FRED ICSA series unavailable — not inventing claims levels",
                    (
                        f"Consensus from {consensus_source}: {consensus}"
                        if consensus is not None
                        else "Live jobless consensus also unavailable"
                    ),
                ],
                "as_of": datetime.utcnow().isoformat(),
            }

        if consensus is None:
            icsa_avg = sum(icsa_vals[:4]) / len(icsa_vals[:4])
            return {
                "event": self.EVENT_NAME,
                "consensus": None,
                "consensus_source": consensus_source,
                "icsa_4wk_avg": round(icsa_avg),
                "icsa_latest": round(icsa_vals[0]),
                "delta": None,
                "signal": None,
                "confidence": None,
                "degraded": True,
                "fred_degraded": fred_degraded,
                "reasons": [
                    "Live jobless consensus unavailable — not inventing a 210K floor",
                    f"ICSA 4wk avg available: {icsa_avg:,.0f}",
                ],
                "inputs": {
                    "icsa_latest": round(icsa_vals[0]),
                    "icsa_4wk_avg": round(icsa_avg),
                },
                "as_of": datetime.utcnow().isoformat(),
                "edge": "Jobless degraded: no live consensus",
            }

        icsa_4wk = icsa_vals[:4]
        icsa_avg = sum(icsa_4wk) / len(icsa_4wk)
        icsa_latest = icsa_vals[0]
        inputs["icsa_latest"] = round(icsa_latest)
        inputs["icsa_4wk_avg"] = round(icsa_avg)
        inputs["consensus"] = consensus

        if len(icsa_vals) >= 4:
            trend_delta = icsa_vals[0] - icsa_vals[3]
            inputs["4wk_trend"] = round(trend_delta)
            if trend_delta > 10_000:
                reasons.append(f"ICSA rising +{trend_delta:,.0f} over 4 weeks → claims worsening")
            elif trend_delta < -10_000:
                reasons.append(f"ICSA falling {trend_delta:,.0f} over 4 weeks → claims improving")
            else:
                reasons.append(f"ICSA flat trend ({trend_delta:+,.0f} over 4 weeks)")

        delta = round(icsa_avg) - consensus

        if delta > 15_000:
            signal = "MISS_LIKELY"
            confidence = 0.70 if delta > 25_000 else 0.55
            reasons.append(
                f"ICSA 4wk avg {icsa_avg:,.0f} vs consensus {consensus:,} → +{delta:,} (MISS)"
            )
        elif delta < -15_000:
            signal = "BEAT_LIKELY"
            confidence = 0.70 if delta < -25_000 else 0.55
            reasons.append(
                f"ICSA 4wk avg {icsa_avg:,.0f} vs consensus {consensus:,} → {delta:,} (BEAT)"
            )
        else:
            signal = "IN_LINE"
            confidence = 0.40
            reasons.append(
                f"ICSA 4wk avg {icsa_avg:,.0f} vs consensus {consensus:,} → {delta:+,} (IN LINE)"
            )

        sign = "+" if delta > 0 else ""
        return {
            "event": self.EVENT_NAME,
            "consensus": consensus,
            "consensus_source": consensus_source,
            "icsa_4wk_avg": round(icsa_avg),
            "icsa_latest": round(icsa_latest),
            "delta": delta,
            "signal": signal,
            "confidence": confidence,
            "degraded": False,
            "fred_degraded": fred_degraded,
            "reasons": reasons,
            "inputs": inputs,
            "as_of": datetime.utcnow().isoformat(),
            "edge": (
                f"ICSA 4wk avg {icsa_avg:,.0f} vs consensus {consensus:,} → {sign}{delta:,} ({signal})"
            ),
        }


if __name__ == "__main__":
    import json
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    predictor = JoblessClaimsPredictor()
    result = predictor.predict()
    print(json.dumps(result, indent=2))
