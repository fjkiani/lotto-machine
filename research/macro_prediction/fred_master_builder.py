"""
FRED Master Frame Builder
=========================
Builds and caches the 149-month x 84-column macro master frame used by
all Phase 1-5 prediction models and the production CPI pre-release modifier.

Run manually or via weekly cron:
    python research/macro_prediction/fred_master_builder.py

Output:
    data/macro_master.parquet   -- 149 rows x 84 cols, month-start index
    data/macro_master_meta.json -- build timestamp, row/col counts, series status

Requirements:
    pip install fredapi yfinance pandas pyarrow

Environment:
    FRED_API_KEY -- required (set in .env or environment)

Design decisions:
    - FRED data is monthly -- no need for daily refresh. Weekly cron is sufficient.
    - Parquet format for fast columnar reads in production (macro_pre_release.py).
    - All feature engineering is deterministic -- same inputs always produce same outputs.
    - Failure on any single FRED series is non-fatal -- series is skipped with a warning.
    - Parquet written atomically (temp file -> rename) to avoid partial reads.

Research basis:
    5-phase FRED-enhanced audit (commit ad2c9b1)
    Key finding: Phase 1 CPI Pre-COVID DM p=0.023 (significant), all-period p=0.197
    Top CPI predictors: PCE MoM (r=+0.548), PPI All (r=+0.544), DBC (r=+0.538),
                        T10YIEM (r=+0.461), Michigan (r=+0.395)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "data"
_PARQUET_PATH = _DATA_DIR / "macro_master.parquet"
_META_PATH = _DATA_DIR / "macro_master_meta.json"

# ---------------------------------------------------------------------------
# Series definitions
# ---------------------------------------------------------------------------
FRED_SERIES: Dict[str, str] = {
    # Inflation
    "CPIAUCSL":      "CPI All Items",
    "CPILFESL":      "Core CPI",
    "PCEPI":         "PCE",
    "PCEPILFE":      "Core PCE",
    "PPIFID":        "PPI Final Demand",
    "PPIACO":        "PPI All Commodities",
    "MICH":          "Michigan Inflation Expectations",
    # Labor
    "PAYEMS":        "Nonfarm Payrolls",
    "UNRATE":        "Unemployment Rate",
    "ICSA":          "Initial Claims (weekly -> monthly mean)",
    "IC4WSA":        "4-Week Avg Initial Claims (weekly -> monthly mean)",
    "CCSA":          "Continued Claims (weekly -> monthly mean)",
    "AWHAETP":       "Avg Weekly Hours",
    "CES0500000003": "Avg Hourly Earnings",
    # Growth
    "GDP":           "Nominal GDP",
    "GDPC1":         "Real GDP",
    "INDPRO":        "Industrial Production",
    "RSAFS":         "Retail Sales",
    "DGORDER":       "Durable Goods Orders",
    "HOUST":         "Housing Starts",
    # Rates
    "FEDFUNDS":      "Fed Funds Rate",
    "DGS10":         "10yr Treasury",
    "DGS2":          "2yr Treasury",
    "DGS1MO":        "1mo Treasury",
    "T10Y2Y":        "10Y-2Y Spread",
    "T10YIEM":       "10yr Breakeven Inflation",
    # Credit / Money
    "BAMLH0A0HYM2":  "HY OAS Spread",
    "M2SL":          "M2 Money Supply",
    "TOTALSL":       "Consumer Credit",
}

# Weekly series -> resample to monthly mean (not last)
_WEEKLY_SERIES = {"ICSA", "IC4WSA", "CCSA"}

YF_TICKERS: Dict[str, str] = {
    "SPY":  "YF_SPY",
    "QQQ":  "YF_QQQ",
    "IWM":  "YF_IWM",
    "TLT":  "YF_TLT",
    "TIP":  "YF_TIP",
    "HYG":  "YF_HYG",
    "UUP":  "YF_UUP",
    "DBC":  "YF_DBC",
    "GLD":  "YF_GLD",
    "^VIX": "YF_VIX",
}

START_DATE = "2014-01-01"

# Phase 1 CPI feature set (validated, Pre-COVID DM p=0.023)
CPI_FEATURES = [
    "T10YIEM", "MICH", "PCEPI_MOM", "PCEPILFE_MOM",
    "PPIFID_MOM", "PPIACO_MOM", "YF_TLT_RET", "YF_TIP_RET",
    "BREAKEVEN_MKT", "YF_UUP_RET", "YF_DBC_RET", "YF_GLD_RET",
    "CPIAUCSL_MOM", "CPILFESL_MOM", "CES0500000003_MOM",
    "UNRATE", "M2SL_MOM", "CPI_MOM3",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_fred(api_key: str) -> Dict[str, pd.Series]:
    """Load all FRED series. Non-fatal on individual series failures."""
    try:
        from fredapi import Fred
    except ImportError:
        raise ImportError("fredapi not installed. Run: pip install fredapi")

    fred = Fred(api_key=api_key)
    loaded: Dict[str, pd.Series] = {}
    skipped = []

    for sid in FRED_SERIES:
        try:
            s = fred.get_series(sid, observation_start=START_DATE)
            s.name = sid
            loaded[sid] = s
        except Exception as e:
            logger.warning("FRED skip %s: %s", sid, e)
            skipped.append(sid)

    if skipped:
        logger.warning("Skipped %d FRED series: %s", len(skipped), skipped)
    logger.info("Loaded %d / %d FRED series", len(loaded), len(FRED_SERIES))
    return loaded


def _load_yf() -> Dict[str, pd.Series]:
    """Load Yahoo Finance monthly close prices."""
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance not installed. Run: pip install yfinance")

    loaded: Dict[str, pd.Series] = {}
    for ticker, col in YF_TICKERS.items():
        try:
            df = yf.download(ticker, start=START_DATE, interval="1mo",
                             auto_adjust=True, progress=False)
            if df is not None and len(df) > 0:
                close = df["Close"].squeeze()
                close.index = close.index.to_period("M").to_timestamp()
                loaded[col] = close
        except Exception as e:
            logger.warning("YF skip %s: %s", ticker, e)

    logger.info("Loaded %d / %d YF tickers", len(loaded), len(YF_TICKERS))
    return loaded


# ---------------------------------------------------------------------------
# Master frame assembly + feature engineering
# ---------------------------------------------------------------------------

def build_master(fred_data: Dict[str, pd.Series],
                 yf_data: Dict[str, pd.Series]) -> pd.DataFrame:
    """
    Assemble raw series and engineer all features.

    Returns:
        pd.DataFrame with DatetimeIndex (month-start), ~84 columns.
    """
    frames = []

    # FRED -> resample to month-start
    for sid, s in fred_data.items():
        s2 = s.copy()
        s2.index = pd.to_datetime(s2.index)
        if sid in _WEEKLY_SERIES:
            s2 = s2.resample("MS").mean()
        else:
            s2 = s2.resample("MS").last()
        s2.index = s2.index.normalize()
        frames.append(s2.rename(sid))

    # YF -> already monthly, normalize index
    for col, s in yf_data.items():
        s2 = s.copy()
        s2.index = pd.to_datetime(s2.index).normalize()
        frames.append(s2.rename(col))

    master = pd.concat(frames, axis=1).sort_index()
    master = master.loc[START_DATE:]

    m = master.copy()

    # MoM % changes
    for col in ["CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE", "PPIFID", "PPIACO",
                "PAYEMS", "INDPRO", "RSAFS", "DGORDER", "HOUST", "M2SL", "TOTALSL",
                "CES0500000003"]:
        if col in m.columns:
            m[f"{col}_MOM"] = m[col].pct_change() * 100

    # YoY % changes
    for col in ["CPIAUCSL", "CPILFESL", "PCEPI", "GDP"]:
        if col in m.columns:
            m[f"{col}_YOY"] = m[col].pct_change(12) * 100

    # Rate level changes (absolute diff)
    for col in ["FEDFUNDS", "DGS10", "DGS2", "T10Y2Y", "T10YIEM",
                "BAMLH0A0HYM2", "UNRATE"]:
        if col in m.columns:
            m[f"{col}_CHG"] = m[col].diff()

    # YF returns
    for col in [c for c in m.columns if c.startswith("YF_")]:
        m[f"{col}_RET"] = m[col].pct_change() * 100

    # Composite features
    if "T10Y2Y" in m.columns:
        m["YIELD_SLOPE_CHG"] = m["T10Y2Y"].diff()
    if "IC4WSA" in m.columns:
        m["CLAIMS_TREND"] = m["IC4WSA"].pct_change(3) * 100
    if "UNRATE" in m.columns:
        m["SAHM_PROXY"] = m["UNRATE"] - m["UNRATE"].rolling(12).min()
    if "T10YIEM" in m.columns:
        m["BREAKEVEN_MKT"] = m["T10YIEM"].diff()
    if "CPIAUCSL_MOM" in m.columns:
        m["CPI_MOM3"] = m["CPIAUCSL_MOM"].rolling(3).mean()

    # Target variables (research use only -- not used in production inference)
    if "CPIAUCSL_MOM" in m.columns:
        m["TARGET_CPI_MOM"] = m["CPIAUCSL_MOM"].shift(-1)
    if "PAYEMS_MOM" in m.columns:
        m["TARGET_NFP_MOM"] = m["PAYEMS_MOM"].shift(-1)
    if "DGS10" in m.columns:
        m["TARGET_YIELD_DIR"] = (m["DGS10"].diff().shift(-1) > 0).astype(float)

    logger.info("Master frame: %d rows x %d cols (%s -> %s)",
                len(m), m.shape[1],
                m.index[0].date(), m.index[-1].date())
    return m


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_master(m: pd.DataFrame) -> None:
    """Write master frame to parquet atomically (temp -> rename)."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    tmp = tempfile.NamedTemporaryFile(
        dir=_DATA_DIR, suffix=".parquet.tmp", delete=False
    )
    try:
        m.to_parquet(tmp.name, engine="pyarrow", index=True)
        tmp.close()
        Path(tmp.name).replace(_PARQUET_PATH)
        logger.info("Saved: %s", _PARQUET_PATH)
    except Exception:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        raise

    meta = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": len(m),
        "cols": m.shape[1],
        "date_start": str(m.index[0].date()),
        "date_end": str(m.index[-1].date()),
        "fred_series_loaded": [s for s in FRED_SERIES if s in m.columns],
        "yf_tickers_loaded": [c for c in YF_TICKERS.values() if c in m.columns],
        "cpi_features": CPI_FEATURES,
    }
    _META_PATH.write_text(json.dumps(meta, indent=2))
    logger.info("Metadata: %s", _META_PATH)


def load_master() -> Optional[pd.DataFrame]:
    """
    Load master frame from parquet cache.

    Returns:
        pd.DataFrame or None if file missing / unreadable.
    """
    if not _PARQUET_PATH.exists():
        logger.warning("macro_master.parquet not found at %s", _PARQUET_PATH)
        return None
    try:
        m = pd.read_parquet(_PARQUET_PATH, engine="pyarrow")
        m.index = pd.to_datetime(m.index)
        return m
    except Exception as e:
        logger.error("Failed to load macro_master.parquet: %s", e)
        return None


def get_master_age_hours() -> Optional[float]:
    """Return age of cached parquet in hours, or None if missing."""
    if not _META_PATH.exists():
        return None
    try:
        meta = json.loads(_META_PATH.read_text())
        built = datetime.fromisoformat(meta["built_at_utc"])
        if built.tzinfo is None:
            built = built.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - built).total_seconds() / 3600
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_and_save(api_key: Optional[str] = None) -> pd.DataFrame:
    """
    Full pipeline: load FRED + YF -> build master -> save parquet.

    Args:
        api_key: FRED API key. Falls back to FRED_API_KEY env var.

    Returns:
        Built master DataFrame.
    """
    key = api_key or os.getenv("FRED_API_KEY", "")
    if not key:
        raise ValueError(
            "FRED_API_KEY not set. Export it or pass api_key= argument.\n"
            "Free key: https://fred.stlouisfed.org/docs/api/api_key.html"
        )

    logger.info("Building FRED master frame (start=%s)...", START_DATE)
    fred_data = _load_fred(key)
    yf_data = _load_yf()
    m = build_master(fred_data, yf_data)
    save_master(m)
    return m


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s -- %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        from dotenv import load_dotenv
        load_dotenv(_REPO_ROOT / ".env")
    except ImportError:
        pass

    api_key = os.getenv("FRED_API_KEY", "")
    if not api_key:
        print("ERROR: FRED_API_KEY not set.", file=sys.stderr)
        print("  export FRED_API_KEY=your_key_here", file=sys.stderr)
        sys.exit(1)

    m = build_and_save(api_key)

    print(f"\nMaster frame built: {len(m)} rows x {m.shape[1]} cols")
    print(f"  Date range : {m.index[0].date()} -> {m.index[-1].date()}")
    print(f"  Saved to   : {_PARQUET_PATH}")

    if "TARGET_CPI_MOM" in m.columns:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            corrs = (
                m.drop(columns=["TARGET_CPI_MOM"])
                .corrwith(m["TARGET_CPI_MOM"])
                .dropna()
                .abs()
                .sort_values(ascending=False)
            )
        print("\nTop CPI correlations (next-month CPI MoM):")
        for feat, r in corrs.head(10).items():
            bar = "=" * int(r * 30)
            print(f"  {feat:30s} r={r:.3f} {bar}")
