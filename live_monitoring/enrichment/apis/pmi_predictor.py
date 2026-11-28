"""
📊 PMI Pre-Signal Monitor

Threshold-based monitor for S&P Global / ISM PMI releases.
Consensus comes from live TE calendar / indicator pages only.
Never invents consensus floors (no 51.5 / 50.5 / 52.0 echo).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

PMI_CONTRACTION = 50.0
PMI_BORDERLINE = 51.0


def _classify_pmi(value: float) -> str:
    if value < PMI_CONTRACTION:
        return "CONTRACTION"
    elif value < PMI_BORDERLINE:
        return "BORDERLINE"
    return "EXPANSION"


def _parse_pmi_number(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s in ("—", "-", "N/A", "n/a", ""):
        return None
    s = s.replace(",", "").replace("%", "")
    try:
        return float(s)
    except ValueError:
        m = re.search(r"[-+]?\d+(\.\d+)?", s)
        return float(m.group(0)) if m else None


class PMIPredictor:
    """
    PMI threshold monitor backed by live TE/FF calendar consensus.
    If consensus cannot be scraped: degraded=True and consensus/prediction=null.
    """

    def __init__(self):
        self._scraper = None

    def _get_scraper(self):
        if self._scraper is None:
            try:
                from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper

                self._scraper = TECalendarScraper(cache_ttl=900)
            except Exception as e:
                logger.warning("PMIPredictor: TECalendarScraper unavailable — %s", e)
        return self._scraper

    def _get_consensus(self, event_keywords: list[str]) -> tuple[Optional[float], Optional[str]]:
        """Pull consensus from TE calendar by keyword match. No invented fallback."""
        scraper = self._get_scraper()
        if not scraper:
            return None, "scraper_unavailable"
        try:
            from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
            from datetime import datetime

            now = datetime.now()
            # Prefer future unreleased events only (avoid past Flash PMI rows)
            candidates = list(scraper.get_upcoming(days=45))
            if not candidates:
                # Fall back to full calendar but still skip past datetimes
                for ev in scraper.get_us_calendar():
                    if ev.has_actual:
                        continue
                    dt = TECalendarScraper._parse_event_datetime(ev)
                    if dt is not None and dt < now:
                        continue
                    candidates.append(ev)

            seen = set()
            for ev in candidates:
                eid = id(ev)
                if eid in seen:
                    continue
                seen.add(eid)
                name = (ev.event or "").lower()
                if not all(kw.lower() in name for kw in event_keywords):
                    continue
                # Skip flash prints when looking for ISM-style monthly unless asked
                raw = ev.consensus or ev.forecast
                val = _parse_pmi_number(raw)
                if val is not None:
                    return val, getattr(ev, "source", "te_calendar")
        except Exception as e:
            logger.warning("PMIPredictor._get_consensus failed: %s", e)
            return None, f"error:{e}"
        return None, "not_found"

    def _predict_series(self, name: str, keywords: list[str]) -> dict:
        consensus, source = self._get_consensus(keywords)
        if consensus is None:
            return {
                "prediction": None,
                "consensus": None,
                "delta": None,
                "signal": None,
                "confidence": None,
                "degraded": True,
                "consensus_source": source,
                "reasons": [
                    f"{name}: live consensus unavailable ({source}) — not inventing a PMI floor",
                ],
            }

        signal = _classify_pmi(consensus)
        return {
            "prediction": consensus,  # no separate model — report scraped consensus only
            "consensus": consensus,
            "delta": 0.0,
            "signal": signal,
            "confidence": self._confidence(consensus, signal),
            "degraded": False,
            "consensus_source": source,
            "reasons": self._reasons(name, consensus, signal),
        }

    @staticmethod
    def _confidence(value: float, signal: str) -> float:
        dist = abs(value - 50.0)
        if signal == "CONTRACTION":
            return min(0.9, 0.5 + dist * 0.08)
        if signal == "BORDERLINE":
            return 0.5
        return min(0.8, 0.4 + (value - 51.0) * 0.06)

    @staticmethod
    def _reasons(name: str, value: float, signal: str) -> list[str]:
        line = "50 threshold (expansion/contraction line)"
        if signal == "CONTRACTION":
            return [
                f"{name} consensus {value:.1f} is below {line} — indicates contraction",
                "Bearish for growth assets; may signal Fed dovish response",
            ]
        if signal == "BORDERLINE":
            return [
                f"{name} consensus {value:.1f} is in the borderline 50–51 zone",
                "Ambiguous signal — any miss risks dipping into contraction territory",
            ]
        return [
            f"{name} consensus {value:.1f} above {line} — expansion confirmed",
            "Mild hawkish macro bias; supports risk-on positioning",
        ]

    def predict(self) -> dict:
        """Return pre-signals for manufacturing / services / composite when available."""
        mfg = self._predict_series("Manufacturing PMI", ["ism", "manufacturing"])
        if mfg.get("consensus") is None:
            # TE business-confidence slug surfaces as "ISM Manufacturing PMI"
            mfg = self._predict_series("Manufacturing PMI", ["manufacturing", "pmi"])

        svcs = self._predict_series("Services PMI", ["services", "pmi"])
        if svcs.get("consensus") is None:
            svcs = self._predict_series("Services PMI", ["non-manufacturing"])

        comp = self._predict_series("Composite PMI", ["composite", "pmi"])

        series = {"pmi_mfg": mfg, "pmi_svcs": svcs, "pmi_comp": comp}
        # Prefer composite; else manufacturing as top-level representative
        top = comp if comp.get("consensus") is not None else mfg
        if top.get("consensus") is None and svcs.get("consensus") is not None:
            top = svcs

        degraded = all(s.get("degraded") for s in series.values())
        return {
            "signal": top.get("signal"),
            "prediction": top.get("prediction"),
            "consensus": top.get("consensus"),
            "delta": top.get("delta"),
            "confidence": top.get("confidence"),
            "reasons": top.get("reasons") or [],
            "series": series,
            "degraded": degraded,
            "edge": (
                f"Composite/top PMI {top.get('consensus')} → {top.get('signal')}"
                if top.get("consensus") is not None
                else "PMI consensus unavailable from live calendar (degraded)"
            ),
        }
