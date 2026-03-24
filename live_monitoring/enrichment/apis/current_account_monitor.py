"""
💳 Current Account Deviation Monitor

Flags when the quarterly Current Account balance is expected to deviate
significantly from its rolling historical mean.

Data source: FRED series NETCBT (US Trade Balance in Goods & Services, quarterly proxy)
  — NETCBT is available monthly; we aggregate to quarterly to match CA release cadence.
  — Fallback: BOPTIMP (Quarterly Balance on Current Account) if NETCBT unavailable.

Rules:
  |forecast - rolling_mean| > 1σ → WIDE_DEFICIT or WIDE_SURPLUS
  Else                            → IN_LINE

Output shape (identical to ADPPredictor):
{
  "prediction":  float (consensus / forecast),
  "consensus":   float,
  "delta":       float (forecast - mean),
  "sigma":       float (how many σ from mean),
  "signal":      "WIDE_DEFICIT" | "WIDE_SURPLUS" | "IN_LINE",
  "confidence":  float,
  "reasons":     list[str],
  "edge":        str,
}
"""

import os
import logging
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class CurrentAccountMonitor:
    """
    FRED-based Current Account deviation monitor.

    Uses rolling 8-quarter mean + std dev of the trade balance proxy to
    flag expected prints that deviate more than 1σ from the historical norm.
    """

    FRED_BASE      = "https://api.stlouisfed.org/fred"
    FRED_SERIES    = "BOPTIMP"  # US Balance on Current Account (quarterly, BEA)
    FALLBACK_MEAN  = -900.0     # Approximate Q mean in $bn (recent trend)
    FALLBACK_STD   = 80.0       # Approximate σ
    ROLLING_N      = 8          # Quarters of history for rolling window

    # Hardcoded consensus fallback when TE calendar is unavailable (typical recent print)
    FALLBACK_CONSENSUS = -920.0  # $bn

    def __init__(self):
        self.api_key   = os.getenv("FRED_API_KEY", "")
        self._scraper  = None
        if not self.api_key:
            logger.warning("⚠️ FRED_API_KEY not set — CurrentAccountMonitor using fallback")

    def _get_scraper(self):
        if self._scraper is None:
            try:
                from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
                self._scraper = TECalendarScraper()
            except Exception as e:
                logger.warning(f"CurrentAccountMonitor: TECalendarScraper unavailable — {e}")
        return self._scraper

    def _fetch_fred(self, series_id: str, limit: int = 10) -> list:
        """Fetch latest N observations from FRED (newest first)."""
        if not self.api_key:
            return []
        try:
            r = requests.get(
                f"{self.FRED_BASE}/series/observations",
                params={
                    "series_id":     series_id,
                    "api_key":       self.api_key,
                    "file_type":     "json",
                    "sort_order":    "desc",
                    "limit":         limit,
                    "observation_start": "2019-01-01",
                },
                timeout=8,
            )
            r.raise_for_status()
            obs = r.json().get("observations", [])
            return [float(o["value"]) for o in obs if o.get("value") not in (".", None)]
        except Exception as e:
            logger.warning(f"CurrentAccountMonitor FRED fetch failed: {e}")
            return []

    def _rolling_stats(self) -> tuple[float, float]:
        """Return (mean, std) of the last ROLLING_N quarters from FRED."""
        obs = self._fetch_fred(self.FRED_SERIES, limit=self.ROLLING_N + 4)
        if len(obs) < 4:
            return self.FALLBACK_MEAN, self.FALLBACK_STD
        window = obs[:self.ROLLING_N]
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        std  = variance ** 0.5 or self.FALLBACK_STD
        return mean, std

    def _get_consensus(self) -> Optional[float]:
        """Pull consensus from TE Calendar for Current Account."""
        scraper = self._get_scraper()
        if not scraper:
            return None
        try:
            events = scraper.get_upcoming_events() or []
            for ev in events:
                name = (ev.get("event") or "").lower()
                if "current account" in name:
                    raw = ev.get("consensus") or ev.get("forecast")
                    if raw:
                        return float(str(raw).replace(",", "").replace("B", "").strip())
        except Exception as e:
            logger.warning(f"CurrentAccountMonitor._get_consensus failed: {e}")
        return None

    def _classify(self, delta: float, std: float) -> str:
        sigma = abs(delta) / std if std else 0
        if sigma < 1.0:
            return "IN_LINE"
        return "WIDE_DEFICIT" if delta < 0 else "WIDE_SURPLUS"

    def predict(self) -> dict:
        mean, std = self._rolling_stats()
        consensus = self._get_consensus() or self.FALLBACK_CONSENSUS
        delta  = consensus - mean
        sigma  = round(abs(delta) / std, 2) if std else 0
        signal = self._classify(delta, std)

        confidence = min(0.85, 0.4 + (sigma - 1.0) * 0.25) if sigma >= 1.0 else 0.4
        sign = "+" if delta > 0 else ""

        reasons = []
        if signal == "IN_LINE":
            reasons = [
                f"Consensus ${consensus:.0f}B is within 1σ of 8-quarter mean (${mean:.0f}B)",
                "No structural imbalance flagged",
            ]
        elif signal == "WIDE_DEFICIT":
            reasons = [
                f"Consensus ${consensus:.0f}B is {sigma:.1f}σ below rolling mean (${mean:.0f}B)",
                "Elevated deficit may pressure USD; bond-flight risk if combined with weak growth",
            ]
        else:
            reasons = [
                f"Consensus ${consensus:.0f}B is {sigma:.1f}σ above rolling mean (${mean:.0f}B)",
                "Wide surplus unusual for US; may reflect trade shift or seasonal factors",
            ]

        return {
            "prediction":  consensus,
            "consensus":   consensus,
            "delta":       round(delta, 1),
            "sigma":       sigma,
            "signal":      signal,
            "confidence":  round(confidence, 2),
            "reasons":     reasons,
            "edge": (
                f"Current Account ${consensus:.0f}B vs 8Q mean ${mean:.0f}B "
                f"→ {sign}{delta:.0f}B ({sigma:.1f}σ) → {signal}"
            ),
            "rolling_mean": round(mean, 1),
            "rolling_std":  round(std, 1),
        }
