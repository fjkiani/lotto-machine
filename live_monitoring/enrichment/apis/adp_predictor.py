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

Output:
  MISS_LIKELY | BEAT_LIKELY | IN_LINE vs ADP consensus
"""
import os
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class ADPPredictor:
    """
    FRED-based ADP Employment Change predictor.
    Uses 5 leading indicators to generate a pre-signal before ADP prints.
    Consensus is fetched dynamically from the economic veto calendar;
    falls back to 150K if unavailable.
    """

    FRED_BASE = "https://api.stlouisfed.org/fred"
    _FALLBACK_CONSENSUS = 150_000  # Used only when calendar lookup fails

    def __init__(self):
        self.api_key = os.getenv("FRED_API_KEY", "")
        if not self.api_key:
            logger.warning("⚠️ FRED_API_KEY not set — ADPPredictor disabled")

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

    def _get_consensus(self) -> int:
        """
        Dynamically pull ADP consensus from the economic veto calendar
        (which scrapes TradingEconomics). Falls back to 150K.
        """
        try:
            from backend.app.api.v1.brief import EconomicVetoEngine
            ve = EconomicVetoEngine()
            upcoming = ve.get_critical_events() if hasattr(ve, 'get_critical_events') else []
            for ev in upcoming:
                name = ev.get("event", "").lower()
                if "adp" in name or ("employment" in name and "change" in name):
                    cons = ev.get("consensus", "")
                    if cons and str(cons) not in ("—", "", "N/A"):
                        # consensus may be "150K" or "150,000" or "150000"
                        cleaned = str(cons).upper().replace("K", "000").replace(",", "").strip()
                        return int(float(cleaned))
        except Exception as e:
            logger.debug(f"Dynamic ADP consensus lookup failed: {e}")
        return self._FALLBACK_CONSENSUS

    def predict(self) -> dict:
        """
        Generate ADP pre-signal prediction.

        Returns dict with: consensus, prediction, delta, signal, confidence,
        reasons, inputs, edge, as_of
        """
        base_consensus = self._get_consensus()
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
        total_adj = sum(adjustments)
        prediction = base_consensus + total_adj
        delta = prediction - base_consensus

        if delta < -50_000:
            signal, confidence = "MISS_LIKELY", 0.70
        elif delta < -30_000:
            signal, confidence = "MISS_LIKELY", 0.55
        elif delta > 50_000:
            signal, confidence = "BEAT_LIKELY", 0.70
        elif delta > 30_000:
            signal, confidence = "BEAT_LIKELY", 0.55
        else:
            signal, confidence = "IN_LINE", 0.40

        sign = "+" if delta > 0 else ""
        return {
            "consensus": base_consensus,
            "prediction": prediction,
            "delta": delta,
            "signal": signal,
            "confidence": confidence,
            "adjustment_count": len(adjustments),
            "total_adjustment": total_adj,
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
