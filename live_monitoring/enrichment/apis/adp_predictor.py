"""
🎯 ADP Pre-Signal Predictor — Leading Indicator Model

Predicts ADP Employment Change BEFORE the print using FRED leading indicators.
Same architecture as Cleveland nowcast for CPI — applied to labor.

Inputs:
  ICSA  (Initial Claims 4-wk avg)    → labor cracking speed
  CCSA  (Continuing Claims)           → sustained unemployment depth
  PAYEMS (NFP MoM change)             → payroll baseline drift
  UNRATE (Unemployment Rate trend)    → macro labor health
  MANEMP (Manufacturing Employment)   → goods sector drag

Consensus (street) is pulled live from Trading Economics calendar (primary),
then ForexFactory date page, then NER-style 40K baseline — not 150K.

Output:
  MISS_LIKELY | BEAT_LIKELY | IN_LINE vs ADP consensus

Pre-print model bands use jobs delta (prediction − consensus). Ops note: even IN_LINE by
band, a forecast far below street in level terms (e.g. ~22.5K vs ~40K) is still a
material soft miss for narrative — treat headline agreement separately from signal label.

REVISED ADP DECISION TREE (post–40K consensus; ops — 8:15 AM ET March print):

IF print < 25K:
    HARD MISS vs ~40K consensus → bear catalyst; VIX risk; sized puts per book.

IF print 25K–55K:
    INLINE band (40K ±15K); may mean-revert on headline; if Feb ADP revised
    down sharply vs 63K prior, treat as add-on bearish regardless of March.

IF print 55K–90K:
    MODEST BEAT vs street; ADP-alone bear thesis weaker; tariff/ISM context only.

IF print > 90K:
    STRONG BEAT — stand down ADP-puts; wait for ISM Manufacturing.

ALWAYS: check revised February ADP (prior 63K); downward revision below ~40K
adds bearish weight even on inline March.
"""
import os
import logging
import re
import requests
from typing import Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Heuristic job deltas below were tuned when street consensus was ~120–150K.
# Scale adjustments down when live consensus is much lower (e.g. 40K).
_ADJ_REF_CONSENSUS = 125_000


class ADPPredictor:
    """
    FRED-based ADP Employment Change predictor.
    Uses 5 leading indicators to generate a pre-signal before ADP prints.
    Consensus: TE calendar → ForexFactory → TE ADP page → 40K baseline.
    """

    FRED_BASE = "https://api.stlouisfed.org/fred"
    # NER Pulse–style floor: ~10K jobs/week × 4 when no calendar reads succeed.
    _FALLBACK_CONSENSUS = 40_000

    def __init__(self):
        self.api_key = os.getenv("FRED_API_KEY", "")
        if not self.api_key:
            logger.warning("⚠️ FRED_API_KEY not set — ADPPredictor disabled")

    @staticmethod
    def _parse_consensus_to_jobs(raw: Optional[str]) -> Optional[int]:
        """Parse calendar consensus like '40K', '12.75K', '40000', '—'."""
        if raw is None:
            return None
        s = str(raw).strip()
        if not s or s in ("—", "-", "N/A", "n/a", ""):
            return None
        u = s.upper().replace(",", "")
        if u.endswith("K"):
            try:
                return int(round(float(u[:-1]) * 1000))
            except ValueError:
                return None
        try:
            v = float(u)
            if abs(v) < 500:
                return int(round(v * 1000))
            return int(round(v))
        except ValueError:
            return None

    def _fetch_consensus_te_calendar(self) -> Optional[int]:
        """Primary: TE US calendar monthly ADP (exclude Weekly rows)."""
        try:
            from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper

            scraper = TECalendarScraper(cache_ttl=300)
            for e in scraper.get_us_calendar():
                el = e.event.lower()
                if "adp" not in el or "employment" not in el:
                    continue
                if "weekly" in el:
                    continue
                v = self._parse_consensus_to_jobs(e.consensus)
                if v is not None:
                    return v
                v = self._parse_consensus_to_jobs(e.forecast)
                if v is not None:
                    return v
        except Exception as e:
            logger.debug(f"TE calendar ADP consensus failed: {e}")
        return None

    def _fetch_consensus_forexfactory(self) -> Optional[int]:
        """Scrape ForexFactory day page for ADP National Employment / Employment Change."""
        urls = [
            "https://www.forexfactory.com/calendar?day=apr1.2026",
            "https://www.forexfactory.com/calendar?day=tomorrow",
        ]
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        }
        for url in urls:
            try:
                r = requests.get(url, headers=headers, timeout=18)
                r.raise_for_status()
                text = r.text
                # FF often embeds row JSON or table cells; grab first plausible forecast near ADP
                if "ADP" not in text.upper():
                    continue
                for m in re.finditer(
                    r"ADP[^<]{0,120}?(?:forecast|consensus)[^0-9]{0,24}([\d,.]+)\s*K?",
                    text, re.I | re.DOTALL
                ):
                    frag = m.group(1) + "K"
                    v = self._parse_consensus_to_jobs(frag)
                    if v is not None:
                        return v
                for m in re.finditer(
                    r"(?:ADP National Employment|ADP Employment)[^0-9]{0,200}?([\d,.]+)\s*K",
                    text,
                    re.I | re.DOTALL,
                ):
                    v = self._parse_consensus_to_jobs(m.group(1) + "K")
                    if v is not None and v < 500_000:
                        return v
            except Exception as e:
                logger.debug(f"ForexFactory ADP consensus failed ({url}): {e}")
        return None

    def _fetch_consensus_te_adp_page(self) -> Optional[int]:
        """Dedicated TE indicator page — JSON-LD / script TEForecast array."""
        url = "https://tradingeconomics.com/united-states/adp-employment-change"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        }
        try:
            r = requests.get(url, headers=headers, timeout=18)
            r.raise_for_status()
            m = re.search(r"TEForecast\s*=\s*\[([^\]]+)\]", r.text)
            if m:
                first = m.group(1).split(",")[0].strip()
                v = self._parse_consensus_to_jobs(first)
                if v is not None:
                    return v
        except Exception as e:
            logger.debug(f"TE ADP page consensus failed: {e}")
        return None

    def _fetch(self, series_id: str, limit: int = 4) -> list:
        """Fetch latest N observations from FRED as float list (newest first)."""
        if not self.api_key:
            return []
        try:
            r = requests.get(
                f"{self.FRED_BASE}/series/observations",
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

    def _get_consensus(self) -> Tuple[int, str]:
        """
        Live consensus chain:
          1) TE US calendar (monthly ADP row)
          2) ForexFactory day page
          3) TE /united-states/adp-employment-change (TEForecast)
          4) Baseline 40K (≈ NER pulse × 4)
        """
        v = self._fetch_consensus_te_calendar()
        if v is not None:
            return v, "te_calendar"
        v = self._fetch_consensus_forexfactory()
        if v is not None:
            return v, "forexfactory"
        v = self._fetch_consensus_te_adp_page()
        if v is not None:
            return v, "te_adp_page"
        logger.warning(
            "ADP consensus: all live pulls failed — using baseline %s",
            self._FALLBACK_CONSENSUS,
        )
        return self._FALLBACK_CONSENSUS, "ner_pulse_baseline"

    def predict(self) -> dict:
        """
        Generate ADP pre-signal prediction.

        Returns dict with: consensus, prediction, delta, signal, confidence,
        reasons, inputs, edge, as_of
        """
        base_consensus, consensus_source = self._get_consensus()
        inputs = {}
        adjustments = []
        reasons = []

        # ── 1. ICSA: Initial Claims 4-week average ──────────────────────
        icsa_vals = self._fetch("ICSA", limit=4)
        if icsa_vals:
            icsa_avg = sum(icsa_vals) / len(icsa_vals)
            inputs["icsa_4wk_avg"] = round(icsa_avg)
            inputs["icsa_latest"] = round(icsa_vals[0])
            if icsa_avg > 225_000:
                adjustments.append(-20_000)
                reasons.append(f"ICSA 4wk avg {icsa_avg:,.0f} > 225K → -20K (labor cracking)")
            elif icsa_avg > 210_000:
                adjustments.append(-10_000)
                reasons.append(f"ICSA 4wk avg {icsa_avg:,.0f} > 210K → -10K (elevated)")
            else:
                reasons.append(f"ICSA 4wk avg {icsa_avg:,.0f} ≤ 210K → stable (no adj)")

        # ── 2. CCSA: Continuing Claims ──────────────────────────────────
        ccsa_vals = self._fetch("CCSA", limit=2)
        if ccsa_vals:
            ccsa_latest = ccsa_vals[0]  # FRED CCSA is in raw units (e.g., 1857000)
            inputs["ccsa_latest"] = round(ccsa_latest)
            if ccsa_latest > 1_900_000:
                adjustments.append(-15_000)
                reasons.append(f"CCSA {ccsa_latest:,.0f} > 1.9M → -15K (sustained weakness)")
            else:
                reasons.append(f"CCSA {ccsa_latest:,.0f} ≤ 1.9M → normal (no adj)")

        # ── 3. PAYEMS: Feb NFP MoM shock ────────────────────────────────
        payems_vals = self._fetch("PAYEMS", limit=4)
        if len(payems_vals) >= 2:
            # PAYEMS is in thousands, MoM change
            feb_change = (payems_vals[0] - payems_vals[1]) * 1000  # convert to actual jobs
            inputs["feb_nfp_change"] = round(feb_change)
            inputs["payems_latest"] = round(payems_vals[0])

            # 3-month average
            if len(payems_vals) >= 4:
                changes_3mo = [(payems_vals[i] - payems_vals[i + 1]) * 1000 for i in range(3)]
                nfp_3mo_avg = sum(changes_3mo) / 3
                inputs["nfp_3mo_avg"] = round(nfp_3mo_avg)

            if feb_change < -50_000:
                adjustments.append(-30_000)
                reasons.append(f"Feb NFP {feb_change:+,.0f} shock (< -50K) → -30K (trend break)")
            elif feb_change < 0:
                adjustments.append(-15_000)
                reasons.append(f"Feb NFP {feb_change:+,.0f} negative → -15K")
            elif feb_change < 100_000:
                reasons.append(f"Feb NFP {feb_change:+,.0f} weak but positive (no adj)")
            else:
                reasons.append(f"Feb NFP {feb_change:+,.0f} strong (no adj)")

        # ── 4. UNRATE: Unemployment rate trend ──────────────────────────
        unrate_vals = self._fetch("UNRATE", limit=6)
        if len(unrate_vals) >= 3:
            unrate_latest = unrate_vals[0]
            unrate_3mo_change = unrate_vals[0] - unrate_vals[2]
            inputs["unrate_latest"] = unrate_latest
            inputs["unrate_3mo_change"] = round(unrate_3mo_change, 2)

            if unrate_3mo_change > 0.2:
                adjustments.append(-10_000)
                reasons.append(f"UNRATE +{unrate_3mo_change:.1f}pp in 3mo → -10K (deterioration)")
            else:
                reasons.append(f"UNRATE {unrate_latest}%, 3mo Δ={unrate_3mo_change:+.1f}pp → stable (no adj)")

        # ── 5. MANEMP: Manufacturing employment ────────────────────────
        manemp_vals = self._fetch("MANEMP", limit=2)
        if len(manemp_vals) >= 2:
            mfg_change = (manemp_vals[0] - manemp_vals[1]) * 1000
            inputs["mfg_employment_change"] = round(mfg_change)
            inputs["manemp_latest"] = round(manemp_vals[0])

            if mfg_change < 0:
                adjustments.append(-10_000)
                reasons.append(f"Mfg employment {mfg_change:+,.0f} contracting → -10K")
            else:
                reasons.append(f"Mfg employment {mfg_change:+,.0f} expanding (no adj)")

        # ── Prediction ──────────────────────────────────────────────────
        raw_adj = sum(adjustments)
        # Scale heuristic deltas when street consensus is far below the ~125K calibration point.
        _scale = min(1.0, max(0.35, base_consensus / _ADJ_REF_CONSENSUS))
        total_adj = int(round(raw_adj * _scale))
        if adjustments and raw_adj != total_adj:
            reasons.append(
                f"Consensus scale {_scale:.2f}× (consensus {base_consensus:,} vs ref {_ADJ_REF_CONSENSUS:,}) "
                f"→ adj {raw_adj:,} → {total_adj:,}"
            )
        prediction = base_consensus + total_adj
        delta = prediction - base_consensus

        if delta < -50_000:
            signal, confidence = "MISS_LIKELY", 0.70
        elif delta < -15_000:
            signal, confidence = "MISS_LIKELY", 0.55
        elif delta > 50_000:
            signal, confidence = "BEAT_LIKELY", 0.70
        elif delta > 15_000:
            signal, confidence = "BEAT_LIKELY", 0.55
        else:
            signal, confidence = "IN_LINE", 0.40

        sign = "+" if delta > 0 else ""
        return {
            "consensus": base_consensus,
            "consensus_source": consensus_source,
            "prediction": prediction,
            "delta": delta,
            "signal": signal,
            "confidence": confidence,
            "adjustment_count": len(adjustments),
            "total_adjustment": total_adj,
            "raw_adjustment_unscaled": raw_adj,
            "adjustment_scale": round(_scale, 4),
            "reasons": reasons,
            "inputs": inputs,
            "as_of": datetime.utcnow().isoformat(),
            "edge": f"Model predicts {prediction:,} vs consensus {base_consensus:,} → {sign}{delta:,} ({signal})",
        }


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO)
    predictor = ADPPredictor()
    result = predictor.predict()
    print(json.dumps(result, indent=2))
