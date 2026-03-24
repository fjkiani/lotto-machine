"""
📊 PMI Pre-Signal Monitor

Threshold-based monitor for S&P Global PMI releases:
  - Manufacturing PMI
  - Services PMI
  - Composite PMI

No FRED model needed — PMI signal is entirely binary vs 50 expansion/contraction line.
Consensus comes from TE calendar scraper.

Rules per series:
  < 50       → CONTRACTION (bearish macro signal)
  50 ≤ x < 51 → BORDERLINE  (reading near inflection — ambiguous)
  ≥ 51       → EXPANSION   (healthy / mildly hawkish)

Output shape (identical to ADPPredictor/JoblessClaimsPredictor):
{
  "prediction":  float,   # forecast value (consensus or last print)
  "consensus":   float,
  "delta":       float,   # forecast - consensus
  "signal":      "CONTRACTION" | "BORDERLINE" | "EXPANSION" | "IN_LINE",
  "confidence":  float,
  "reasons":     list[str],
  "series":      { "mfg": ..., "svcs": ..., "composite": ... }
}
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────

PMI_CONTRACTION  = 50.0   # < 50 = CONTRACTION
PMI_BORDERLINE   = 51.0   # 50–51 = BORDERLINE
# ≥ 51 = EXPANSION


def _classify_pmi(value: float) -> str:
    if value < PMI_CONTRACTION:
        return "CONTRACTION"
    elif value < PMI_BORDERLINE:
        return "BORDERLINE"
    else:
        return "EXPANSION"


class PMIPredictor:
    """
    S&P Global PMI threshold monitor.

    Reads consensus values from TECalendarScraper and classifies each series.
    Falls back to hardcoded safe defaults when calendar is unavailable.
    """

    # Fallback consensus values (S&P Global US PMI historical medians)
    FALLBACK_MFG       = 50.5
    FALLBACK_SVCS      = 52.0
    FALLBACK_COMPOSITE = 51.5

    def __init__(self):
        self._scraper = None

    def _get_scraper(self):
        if self._scraper is None:
            try:
                from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
                self._scraper = TECalendarScraper()
            except Exception as e:
                logger.warning(f"PMIPredictor: TECalendarScraper unavailable — {e}")
        return self._scraper

    def _get_consensus(self, event_keywords: list[str], fallback: float) -> Optional[float]:
        """Pull consensus from TE Calendar by fuzzy keyword match."""
        scraper = self._get_scraper()
        if not scraper:
            return fallback
        try:
            events = scraper.get_upcoming_events() or []
            for ev in events:
                name = (ev.get("event") or "").lower()
                if all(kw.lower() in name for kw in event_keywords):
                    raw = ev.get("consensus") or ev.get("forecast")
                    if raw:
                        return float(str(raw).replace(",", "").strip())
        except Exception as e:
            logger.warning(f"PMIPredictor._get_consensus failed: {e}")
        return fallback

    def _predict_series(self, name: str, keywords: list[str], fallback: float) -> dict:
        consensus = self._get_consensus(keywords, fallback)
        if consensus is None:
            consensus = fallback
        signal = _classify_pmi(consensus)
        confidence = self._confidence(consensus, signal)
        reasons = self._reasons(name, consensus, signal)
        return {
            "prediction":  consensus,   # Best estimate = consensus (no FRED model)
            "consensus":   consensus,
            "delta":       0.0,         # Will be updated post-print when actual is known
            "signal":      signal,
            "confidence":  confidence,
            "reasons":     reasons,
        }

    @staticmethod
    def _confidence(value: float, signal: str) -> float:
        """Confidence scales with distance from the 50 threshold."""
        dist = abs(value - 50.0)
        if signal == "CONTRACTION":
            return min(0.9, 0.5 + dist * 0.08)
        elif signal == "BORDERLINE":
            return 0.5
        else:
            return min(0.8, 0.4 + (value - 51.0) * 0.06)

    @staticmethod
    def _reasons(name: str, value: float, signal: str) -> list[str]:
        line = f"50 threshold (expansion/contraction line)"
        if signal == "CONTRACTION":
            return [
                f"{name} consensus {value:.1f} is below {line} — indicates contraction",
                "Bearish for growth assets; may signal Fed dovish response",
            ]
        elif signal == "BORDERLINE":
            return [
                f"{name} consensus {value:.1f} is in the borderline 50–51 zone",
                "Ambiguous signal — any miss risks dipping into contraction territory",
            ]
        return [
            f"{name} consensus {value:.1f} above {line} — expansion confirmed",
            "Mild hawkish macro bias; supports risk-on positioning",
        ]

    def predict(self) -> dict:
        """Return pre-signals for all three PMI series."""
        mfg  = self._predict_series("Manufacturing PMI",  ["pmi", "manufacturing"],  self.FALLBACK_MFG)
        svcs = self._predict_series("Services PMI",       ["pmi", "services"],       self.FALLBACK_SVCS)
        comp = self._predict_series("Composite PMI",      ["pmi", "composite"],      self.FALLBACK_COMPOSITE)

        # Composite drives the top-level signal (most representative)
        top_signal = comp["signal"]

        return {
            "signal":      top_signal,
            "prediction":  comp["prediction"],
            "consensus":   comp["consensus"],
            "delta":       comp["delta"],
            "confidence":  comp["confidence"],
            "reasons":     comp["reasons"],
            "series": {
                "pmi_mfg":  mfg,
                "pmi_svcs": svcs,
                "pmi_comp": comp,
            },
            "edge": (
                f"Composite PMI {comp['consensus']:.1f} → {top_signal} | "
                f"Mfg: {mfg['signal']}, Svcs: {svcs['signal']}"
            ),
        }
