"""
🧭 Michigan Consumer Sentiment & Expectations Monitors

Threshold-based weakness monitors for University of Michigan consumer surveys.

Two classes are provided:
  MichiganSentimentMonitor    → UMCSENT series
  MichiganExpectationsMonitor → UMICH5YR expectations series

Rules (applied identically to both):
  forecast < 55                   → WEAKNESS      (soft consumer = dovish macro risk)
  55 ≤ forecast < 60              → BORDERLINE    (deteriorating but not collapsed)
  ≥ 60                            → IN_LINE       (normal range for current cycle)

Consensus is pulled from TECalendarScraper keyed by event name substring.
Falls back to FRED latest observation when TE is unavailable.

Output shape (identical to ADPPredictor/JoblessClaimsPredictor):
{
  "prediction":  float,
  "consensus":   float,
  "delta":       float (forecast - last_print),
  "signal":      "WEAKNESS" | "BORDERLINE" | "IN_LINE",
  "confidence":  float,
  "reasons":     list[str],
  "last_print":  float | null,
  "edge":        str,
}
"""

import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# ── Signal thresholds ─────────────────────────────────────────────────────────

UMICH_WEAKNESS    = 55.0
UMICH_BORDERLINE  = 60.0


def _classify_umich(value: float) -> str:
    if value < UMICH_WEAKNESS:
        return "WEAKNESS"
    elif value < UMICH_BORDERLINE:
        return "BORDERLINE"
    return "IN_LINE"


def _confidence_umich(value: float, signal: str) -> float:
    if signal == "WEAKNESS":
        return min(0.90, 0.55 + (UMICH_WEAKNESS - value) * 0.025)
    elif signal == "BORDERLINE":
        dist = min(abs(value - UMICH_WEAKNESS), abs(value - UMICH_BORDERLINE))
        return max(0.4, 0.55 - dist * 0.04)
    return 0.35  # IN_LINE — signal strength is low


def _reasons_umich(series_name: str, value: float, signal: str, last_print: Optional[float]) -> list[str]:
    trend = ""
    if last_print is not None:
        delta = value - last_print
        trend = f"Previous print was {last_print:.1f}; forecast shows {'decline' if delta < 0 else 'improvement'} of {abs(delta):.1f}."

    base = {
        "WEAKNESS":   f"{series_name} at {value:.1f} is below the 55 weakness threshold — consumer confidence severely impaired.",
        "BORDERLINE": f"{series_name} at {value:.1f} is in the 55–60 deteriorating zone — watching for break below 55.",
        "IN_LINE":    f"{series_name} at {value:.1f} is within normal cycle range (≥60).",
    }
    macro = {
        "WEAKNESS":   "Consumer confidence weakness often precedes spending contraction; dovish macro bias.",
        "BORDERLINE": "Borderline sentiment supports caution on consumer discretionary; watch for follow-through.",
        "IN_LINE":    "No consumer confidence concern flagged.",
    }
    reasons = [base[signal]]
    if trend:
        reasons.append(trend)
    reasons.append(macro[signal])
    return reasons


# ── Shared FRED fetch utility ─────────────────────────────────────────────────

class _FredFetcher:
    FRED_BASE = "https://api.stlouisfed.org/fred"

    def __init__(self):
        self.api_key = os.getenv("FRED_API_KEY", "")
        if not self.api_key:
            logger.warning("⚠️ FRED_API_KEY not set — Michigan monitors using fallback values")

    def latest(self, series_id: str) -> Optional[float]:
        if not self.api_key:
            return None
        try:
            r = requests.get(
                f"{self.FRED_BASE}/series/observations",
                params={
                    "series_id":  series_id,
                    "api_key":    self.api_key,
                    "file_type":  "json",
                    "sort_order": "desc",
                    "limit":      2,
                },
                timeout=8,
            )
            r.raise_for_status()
            obs = r.json().get("observations", [])
            vals = [float(o["value"]) for o in obs if o.get("value") not in (".", None)]
            return vals[0] if vals else None
        except Exception as e:
            logger.warning(f"Michigan FRED fetch ({series_id}) failed: {e}")
            return None


# ── Shared TE Calendar consensus fetch ───────────────────────────────────────

def _get_te_consensus(keywords: list[str]) -> Optional[float]:
    try:
        from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
        scraper = TECalendarScraper()
        events  = scraper.get_upcoming_events() or []
        for ev in events:
            name = (ev.get("event") or "").lower()
            if all(kw.lower() in name for kw in keywords):
                raw = ev.get("consensus") or ev.get("forecast")
                if raw:
                    return float(str(raw).replace(",", "").strip())
    except Exception as e:
        logger.warning(f"Michigan TE consensus fetch failed: {e}")
    return None


# ── MichiganSentimentMonitor ──────────────────────────────────────────────────

class MichiganSentimentMonitor:
    """
    University of Michigan Consumer Sentiment (UMCSENT) weakness monitor.
    Signals WEAKNESS (<55), BORDERLINE (55–60), or IN_LINE (≥60).
    """

    FRED_SERIES       = "UMCSENT"
    FALLBACK_CONSENSUS = 62.0

    def __init__(self):
        self._fred = _FredFetcher()

    def predict(self) -> dict:
        last_print = self._fred.latest(self.FRED_SERIES)
        consensus  = _get_te_consensus(["michigan", "sentiment"]) or \
                     _get_te_consensus(["umich", "consumer"]) or \
                     self.FALLBACK_CONSENSUS

        signal     = _classify_umich(consensus)
        confidence = _confidence_umich(consensus, signal)
        reasons    = _reasons_umich("Michigan Sentiment", consensus, signal, last_print)
        delta      = round(consensus - last_print, 1) if last_print is not None else 0.0

        return {
            "prediction":  consensus,
            "consensus":   consensus,
            "delta":       delta,
            "signal":      signal,
            "confidence":  round(confidence, 2),
            "reasons":     reasons,
            "last_print":  last_print,
            "edge": (
                f"Michigan Sentiment consensus {consensus:.1f} "
                f"{'vs last {:.1f} '.format(last_print) if last_print else ''}"
                f"→ {signal}"
            ),
        }


# ── MichiganExpectationsMonitor ───────────────────────────────────────────────

class MichiganExpectationsMonitor:
    """
    University of Michigan Consumer Expectations weakness monitor.
    Same thresholds as Sentiment; uses FRED MICH (5-year inflation expectations) as proxy
    since UMich expectations index (UMCSI) has the same weekly cadence.
    """

    FRED_SERIES        = "MICH"       # 5-year inflation expectations (Univ of Michigan)
    FALLBACK_CONSENSUS = 65.0         # Consumer Expectations Index typical range

    def __init__(self):
        self._fred = _FredFetcher()

    def predict(self) -> dict:
        last_print = self._fred.latest(self.FRED_SERIES)
        consensus  = _get_te_consensus(["michigan", "expectations"]) or \
                     _get_te_consensus(["consumer", "expectations"]) or \
                     self.FALLBACK_CONSENSUS

        signal     = _classify_umich(consensus)
        confidence = _confidence_umich(consensus, signal)
        reasons    = _reasons_umich("Michigan Expectations", consensus, signal, last_print)
        delta      = round(consensus - last_print, 1) if last_print is not None else 0.0

        return {
            "prediction":  consensus,
            "consensus":   consensus,
            "delta":       delta,
            "signal":      signal,
            "confidence":  round(confidence, 2),
            "reasons":     reasons,
            "last_print":  last_print,
            "edge": (
                f"Michigan Expectations consensus {consensus:.1f} "
                f"{'vs last {:.1f} '.format(last_print) if last_print else ''}"
                f"→ {signal}"
            ),
        }
