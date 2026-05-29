"""
Phase 2 — NFP (Non-Farm Payrolls) Prediction Model
====================================================
Status: NO EDGE — stub only.

Research finding (commit ad2c9b1, 2026-05-24):
  - Walk-forward RF model using FRED market-only features (T10Y2Y, VIX, DXY, SPY, etc.)
  - All-period DM p=0.382 — not significant vs naive (previous-month) baseline
  - Root cause: missing ADP Employment (2-day lead) and ISM Manufacturing PMI
  - Post-COVID regime: model worse than naive due to structural labour market shifts

Why this matters:
  - ADP is the single best NFP predictor (r~0.85 historically)
  - ISM Manufacturing PMI employment sub-index (r~0.6 with NFP)
  - Both are paywalled or require separate data agreements
  - IC4WSA (jobless claims) is a partial proxy but insufficient alone

What to do when ADP becomes available:
  1. Add FRED series 'ADPWNUSNERSA' (ADP private payrolls, if available)
     or scrape ADP Research Institute release (https://adpemploymentreport.com/)
  2. Add ISM Manufacturing PMI via FRED 'MANEMP' (manufacturing employment proxy)
  3. Wire IC4WSA 3-month trend from fetch_jobless_claims() as live feature
  4. Retrain with 48-month rolling window, walk-forward validate
  5. Target: DM p < 0.05 pre-COVID, p < 0.10 all-period

Current proxy approach (partial):
  - IC4WSA trend is already in brief/fetchers/signals.py via fetch_jobless_claims()
  - CLAIMS_TREND feature importance = 0.225 in Phase 5 GDP model
  - Use as a directional indicator only, not a point forecast

DO NOT WIRE into production signals until DM p < 0.10 is achieved.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Feature set (what we have vs what we need) ────────────────────────────────

AVAILABLE_FEATURES = [
    # FRED market-based (monthly)
    "T10Y2Y",          # yield curve spread
    "T10YIEM",         # TIPS breakeven
    "UNRATE",          # unemployment rate
    "IC4WSA",          # initial jobless claims (weekly → monthly avg)
    "PAYEMS_MOM",      # NFP MoM change (lagged 1 month)
    # Yahoo Finance (monthly)
    "YF_SPY_RET",      # SPY monthly return
    "YF_DXY_RET",      # DXY monthly return
    "YF_VIX_CLOSE",    # VIX level
]

MISSING_FEATURES = [
    # These are the critical missing predictors
    "ADP_PRIVATE",     # ADP private payrolls (r~0.85 with NFP) — paywalled
    "ISM_PMI_EMP",     # ISM Manufacturing PMI employment sub-index — paywalled
    "JOLTS_OPENINGS",  # JOLTS job openings (FRED: JTSJOL) — 1-month lag, free
    "JOLTS_QUITS",     # JOLTS quits rate (FRED: JTSQUR) — free
]

# JOLTS is free via FRED and has predictive value — add when building v2
FRED_JOLTS_SERIES = {
    "JTSJOL": "Job Openings: Total Nonfarm",
    "JTSQUR": "Quits: Total Nonfarm",
    "JTSHIR": "Hires: Total Nonfarm",
}


# ── Stub model ────────────────────────────────────────────────────────────────

def run_phase2(
    months: int = 144,
    fred_data: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    NFP walk-forward prediction model.

    STATUS: NO EDGE — returns empty DataFrame with explanation.
    Wire ADP + ISM PMI before activating.

    Args:
        months: Number of months of history to use (default 144 = 12 years)
        fred_data: Pre-loaded FRED master frame (from fred_master_builder.py).
                   If None, will attempt to load from data/macro_master.parquet.

    Returns:
        pd.DataFrame with columns: [date, actual, predicted, naive, error_rf, error_naive]
        Currently returns empty DataFrame — model not validated.
    """
    logger.warning(
        "Phase 2 NFP model has NO EDGE (DM p=0.382). "
        "Missing ADP and ISM PMI. Returning empty DataFrame. "
        "See phase2_nfp.py docstring for upgrade path."
    )
    return pd.DataFrame(
        columns=["date", "actual", "predicted", "naive", "error_rf", "error_naive"]
    )


def get_claims_trend(fred_data: Optional[pd.DataFrame] = None) -> Optional[float]:
    """
    Compute IC4WSA 3-month trend as a partial NFP proxy.

    This is the only validated leading indicator available without ADP/ISM.
    Feature importance = 0.225 in Phase 5 GDP model (commit ad2c9b1).

    Returns:
        float: 3-month % change in initial jobless claims (positive = rising = bad)
        None: if data unavailable
    """
    if fred_data is None:
        try:
            import os
            parquet_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "data", "macro_master.parquet"
            )
            fred_data = pd.read_parquet(parquet_path)
        except Exception as e:
            logger.warning(f"Could not load macro_master.parquet: {e}")
            return None

    if "IC4WSA" not in fred_data.columns:
        logger.warning("IC4WSA not in FRED master frame")
        return None

    claims = fred_data["IC4WSA"].dropna().sort_index()
    if len(claims) < 4:
        return None

    current = claims.iloc[-1]
    three_mo_ago = claims.iloc[-4]
    if three_mo_ago <= 0:
        return None

    trend_pct = ((current - three_mo_ago) / three_mo_ago) * 100
    return round(trend_pct, 2)


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)

    print("=== Phase 2 NFP — Status Report ===")
    print()
    print("VERDICT: NO EDGE")
    print("  All-period DM p = 0.382 (not significant)")
    print("  Root cause: missing ADP Employment + ISM Manufacturing PMI")
    print()
    print("Available features:", AVAILABLE_FEATURES)
    print()
    print("Missing features (critical):", MISSING_FEATURES)
    print()
    print("Free FRED series to add (JOLTS):")
    for series, name in FRED_JOLTS_SERIES.items():
        print(f"  {series}: {name}")
    print()
    print("Claims trend (partial proxy):")
    trend = get_claims_trend()
    if trend is not None:
        direction = "RISING ⚠️" if trend > 5 else "FALLING ✅" if trend < -5 else "FLAT"
        print(f"  IC4WSA 3-month trend: {trend:+.1f}% ({direction})")
    else:
        print("  IC4WSA: data unavailable (run fred_master_builder.py first)")
    print()
    print("Upgrade path:")
    print("  1. Add JOLTS series (free via FRED)")
    print("  2. Add ADP when available")
    print("  3. Retrain with 48-month rolling window")
    print("  4. Target: DM p < 0.10 before wiring into production")
