"""
CPI Pre-Release Modifier
========================
Provides a Random Forest CPI forecast for use as a pre-release confidence
modifier in the signals inject loop (signals.py).

ONLY fires when ALL of the following are true:
  1. CPI release is within 24h (checked by caller via econ_hours)
  2. Regime is stable (not STAGFLATION / RECESSION / DEFLATIONARY_BUST)
  3. VIX < 22 (no elevated volatility)
  4. RF forecast diverges from consensus by > 0.15% (meaningful signal)
  5. Parquet cache is fresh (< 48h old)

Research basis:
  Phase 1 CPI walk-forward audit (commit ad2c9b1)
  Pre-COVID DM p=0.023 (significant), all-period p=0.197 (marginal)
  Top features: PCEPI_MOM (r=0.562), CPIAUCSL_MOM (r=0.549), YF_DBC_RET (r=0.545),
                PPIACO_MOM (r=0.540), T10YIEM (r=0.461), MICH (r=0.395)

Confidence modifier: +8% max (weak signal -- tiebreaker only, not standalone)

Failure modes:
  - Returns None silently on any error -- never raises, never blocks signals
  - Parquet missing -> None
  - FRED data stale (> 48h) -> None
  - Unstable regime -> None
  - Insufficient training rows (< 36) -> None
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Regimes where the CPI model is unreliable (COVID-era relationships break)
_UNSTABLE_REGIMES = {
    "STAGFLATION",
    "RECESSION",
    "DEFLATIONARY_BUST",
    "INFLATIONARY_BOOM",  # rate-hike cycle -- model trained on pre-hike data
}

# VIX threshold above which we suppress the modifier (elevated vol = regime shift)
_VIX_STABLE_THRESHOLD = 22.0

# Minimum divergence (RF forecast vs consensus) to fire the modifier
_MIN_DIVERGENCE = 0.15  # percentage points

# Confidence boost applied when signal aligns with RF forecast direction
_CONFIDENCE_BOOST = 8  # percentage points

# Cache TTL for the RF forecast (4 hours -- CPI data doesn't change intraday)
_FORECAST_CACHE_TTL = 4 * 3600

# Maximum age of parquet file before we refuse to use it
_MAX_PARQUET_AGE_HOURS = 48.0

# Minimum training rows for walk-forward RF
_MIN_TRAIN_ROWS = 36

# Phase 1 CPI feature set (validated, Pre-COVID DM p=0.023)
CPI_FEATURES = [
    "T10YIEM", "MICH", "PCEPI_MOM", "PCEPILFE_MOM",
    "PPIFID_MOM", "PPIACO_MOM", "YF_TLT_RET", "YF_TIP_RET",
    "BREAKEVEN_MKT", "YF_UUP_RET", "YF_DBC_RET", "YF_GLD_RET",
    "CPIAUCSL_MOM", "CPILFESL_MOM", "CES0500000003_MOM",
    "UNRATE", "M2SL_MOM", "CPI_MOM3",
]

# ---------------------------------------------------------------------------
# Module-level cache (same pattern as _MACRO_REGIME_INJECT_CACHE in signals.py)
# ---------------------------------------------------------------------------
_forecast_cache: dict = {"value": None, "ts": 0.0}
_forecast_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Repo path resolution
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_PARQUET_PATH = _REPO_ROOT / "data" / "macro_master.parquet"
_META_PATH = _REPO_ROOT / "data" / "macro_master_meta.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_stable_regime(macro_regime: str, vix: float) -> bool:
    """
    Return True only when the CPI RF model is expected to be reliable.

    Args:
        macro_regime: String from MacroRegimeDetector (e.g. 'GOLDILOCKS')
        vix: Current VIX level

    Returns:
        True if regime is stable and VIX is below threshold.
    """
    if macro_regime.upper() in _UNSTABLE_REGIMES:
        return False
    if vix >= _VIX_STABLE_THRESHOLD:
        return False
    return True


def get_cpi_rf_forecast() -> Optional[float]:
    """
    Return the RF model's CPI MoM forecast for the upcoming release.

    Uses a 4-hour module-level cache. Trains on the last 48 months of
    parquet data using the validated Phase 1 feature set.

    Returns:
        float: Forecasted CPI MoM % (e.g. 0.28 means +0.28%)
        None:  If parquet missing, stale, insufficient data, or any error
    """
    now = time.monotonic()

    # Fast path -- check cache outside lock
    with _forecast_lock:
        cached = _forecast_cache["value"]
        ts = _forecast_cache["ts"]
        if cached is not None and (now - ts) < _FORECAST_CACHE_TTL:
            return cached

    # Slow path -- compute forecast
    try:
        forecast = _compute_cpi_forecast()
    except Exception as e:
        logger.warning("CPI RF forecast failed: %s", e)
        forecast = None

    with _forecast_lock:
        _forecast_cache["value"] = forecast
        _forecast_cache["ts"] = time.monotonic()

    return forecast


def get_cpi_consensus_from_te() -> Optional[float]:
    """
    Fetch CPI MoM consensus from TECalendarScraper singleton.

    Returns:
        float: Consensus CPI MoM % (e.g. 0.30 means +0.30%)
        None:  If TE scraper unavailable or no CPI event found
    """
    try:
        from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
        scraper = TECalendarScraper(cache_ttl=300)
        events = scraper.get_us_calendar()
        for event in events:
            name = (event.event or "").upper()
            if "CPI" in name and "CORE" not in name:
                raw = event.consensus
                if raw:
                    cleaned = (raw.strip()
                                  .replace("%", "")
                                  .replace(",", "")
                                  .replace("K", "")
                                  .replace("M", ""))
                    try:
                        return float(cleaned)
                    except ValueError:
                        pass
    except Exception as e:
        logger.warning("TE consensus fetch failed: %s", e)
    return None


def get_pre_release_modifier(
    sig_action: str,
    macro_regime: str,
    vix: float,
    econ_event: str = "",
) -> Optional[dict]:
    """
    Compute the CPI pre-release confidence modifier for a signal.

    Args:
        sig_action:   Signal action string ('LONG', 'SHORT', 'WATCH')
        macro_regime: Current macro regime from MacroRegimeDetector
        vix:          Current VIX level
        econ_event:   Upcoming economic event name (must contain 'CPI')

    Returns:
        dict with keys: boost (int), direction (str), rf_forecast (float),
                        consensus (float), divergence (float), warning (str)
        None if modifier should not fire
    """
    # Gate 1: must be a CPI event
    if "CPI" not in econ_event.upper():
        return None

    # Gate 2: stable regime
    if not is_stable_regime(macro_regime, vix):
        logger.debug("CPI modifier suppressed: unstable regime=%s vix=%.1f",
                     macro_regime, vix)
        return None

    # Gate 3: get RF forecast
    rf_forecast = get_cpi_rf_forecast()
    if rf_forecast is None:
        return None

    # Gate 4: get consensus
    consensus = get_cpi_consensus_from_te()
    if consensus is None:
        logger.debug("CPI modifier suppressed: no consensus available")
        return None

    # Gate 5: meaningful divergence
    divergence = rf_forecast - consensus
    if abs(divergence) <= _MIN_DIVERGENCE:
        logger.debug("CPI modifier suppressed: divergence %.3f <= threshold %.3f",
                     abs(divergence), _MIN_DIVERGENCE)
        return None

    direction = "HOT" if divergence > 0 else "COOL"

    # Gate 6: signal must align with forecast direction
    # HOT forecast -> SHORT signals get boost (inflation bad for longs)
    # COOL forecast -> LONG signals get boost (disinflation good for longs)
    aligns = (
        (direction == "HOT" and sig_action == "SHORT") or
        (direction == "COOL" and sig_action == "LONG")
    )
    if not aligns:
        return None

    warning = (
        f"CPI pre-release RF: {rf_forecast:.2f}% vs consensus {consensus:.2f}% "
        f"({direction}, +{_CONFIDENCE_BOOST}% -- stable regime only)"
    )

    return {
        "boost": _CONFIDENCE_BOOST,
        "direction": direction,
        "rf_forecast": rf_forecast,
        "consensus": consensus,
        "divergence": round(divergence, 3),
        "warning": warning,
    }


# ---------------------------------------------------------------------------
# Internal: RF forecast computation
# ---------------------------------------------------------------------------

def _compute_cpi_forecast() -> Optional[float]:
    """
    Load parquet, train RF on last 48 months, predict next CPI MoM.

    Returns:
        float forecast or None on any failure.
    """
    import json

    # Check parquet age
    if _META_PATH.exists():
        try:
            meta = json.loads(_META_PATH.read_text())
            from datetime import datetime, timezone
            built = datetime.fromisoformat(meta["built_at_utc"])
            if built.tzinfo is None:
                built = built.replace(tzinfo=timezone.utc)
            age_h = (datetime.now(timezone.utc) - built).total_seconds() / 3600
            if age_h > _MAX_PARQUET_AGE_HOURS:
                logger.warning("macro_master.parquet is %.1fh old (max %.1fh) -- "
                               "run fred_master_builder.py to refresh",
                               age_h, _MAX_PARQUET_AGE_HOURS)
                return None
        except Exception:
            pass

    if not _PARQUET_PATH.exists():
        logger.warning("macro_master.parquet not found at %s -- "
                       "run research/macro_prediction/fred_master_builder.py",
                       _PARQUET_PATH)
        return None

    import pandas as pd
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler

    m = pd.read_parquet(_PARQUET_PATH, engine="pyarrow")
    m.index = pd.to_datetime(m.index)

    # Use last 48 months for training (regime-aware window)
    m_recent = m.tail(48).copy()

    # Build feature set -- only use columns that exist
    feats = [f for f in CPI_FEATURES if f in m_recent.columns]
    if not feats:
        logger.warning("No CPI features found in parquet")
        return None

    # Target: next-month CPI MoM (already computed in builder as TARGET_CPI_MOM)
    if "TARGET_CPI_MOM" not in m_recent.columns:
        if "CPIAUCSL_MOM" in m_recent.columns:
            m_recent = m_recent.copy()
            m_recent["TARGET_CPI_MOM"] = m_recent["CPIAUCSL_MOM"].shift(-1)
        else:
            logger.warning("TARGET_CPI_MOM not available")
            return None

    # Deduplicate columns (safety)
    m_recent = m_recent.loc[:, ~m_recent.columns.duplicated()]

    # Training set: all rows except the last (which has no target yet)
    df_train = m_recent[feats + ["TARGET_CPI_MOM"]].dropna()
    if len(df_train) < _MIN_TRAIN_ROWS:
        logger.warning("Insufficient training rows: %d < %d", len(df_train), _MIN_TRAIN_ROWS)
        return None

    X_train = df_train[feats].values
    y_train = df_train["TARGET_CPI_MOM"].values

    # Prediction row: the most recent complete feature row (last row of m_recent)
    # This is the current month's data -- predicting NEXT month's CPI
    pred_row = m_recent[feats].dropna().tail(1)
    if len(pred_row) == 0:
        logger.warning("No complete feature row for prediction")
        return None

    X_pred = pred_row.values

    # Train RF (same hyperparameters as validated walk-forward)
    rf = RandomForestRegressor(
        n_estimators=200,
        max_depth=4,
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    forecast = float(rf.predict(X_pred)[0])

    logger.info("CPI RF forecast: %.3f%% (trained on %d months, %d features)",
                forecast, len(df_train), len(feats))
    return forecast
