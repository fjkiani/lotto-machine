#!/usr/bin/env python3
"""
Mission 1 (Zo): Pull FRED observations for three analog windows, save raw JSON,
build monthly master CSVs, compute equity drawdown + harmonized oil shock stats.

Equity (FRED reality):
- SP500 daily on FRED has no pre-2016 history; observation_start is 2016-04-01.
  Do not use FRED SP500 for 1973/1990 drawdowns.
- 1973 + 1990 drawdowns: SPASTT01USM661N (monthly S&P 500 total return index).
- 2022 window: FRED SP500 (daily → month-end last) for drawdown (cash index).

Oil model input: FRED DCOILWTICO (spot/series definition per FRED); not front-month CL=F.
WTISPLC fills pre-1986 monthly WTI for the `wti` column when DCOIL is empty.

WTI shock: harmonized_12m_pre_peak_min_to_window_peak (see ground_truth_common).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from ground_truth_common import harmonized_oil_shock_monthly
GROUND = REPO_ROOT / "ground_truth"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

SERIES_IDS = [
    "DCOILWTICO",
    "CPIAUCSL",
    "FEDFUNDS",
    "UNRATE",
    "INDPRO",
    "UMCSENT",
    "SP500",
    "PAYEMS",
    "GDPC1",
]

COL_MAP = {
    "DCOILWTICO": "wti",
    "CPIAUCSL": "cpi",
    "FEDFUNDS": "fedfunds",
    "UNRATE": "unrate",
    "INDPRO": "indpro",
    "UMCSENT": "umcsent",
    "SP500": "sp500",
    "PAYEMS": "payems",
    "GDPC1": "gdp",
}

PERIODS = [
    ("1973", "1972-01-01", "1975-12-31"),
    ("1990", "1989-01-01", "1992-12-31"),
    ("2022", "2021-01-01", "2023-12-31"),
]


def load_dotenv_keys():
    for p in (REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"):
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def fetch_fred_json(series_id: str, start: str, end: str, api_key: str) -> dict:
    q = urlencode(
        {
            "series_id": series_id,
            "observation_start": start,
            "observation_end": end,
            "file_type": "json",
            "api_key": api_key,
        }
    )
    url = f"{FRED_URL}?{q}"
    with urlopen(url, timeout=120) as resp:
        return json.loads(resp.read().decode())


def observations_to_df(raw: dict, series_id: str) -> pd.DataFrame:
    obs = raw.get("observations") or []
    rows = []
    for o in obs:
        v = o.get("value")
        if v in (".", "", None):
            continue
        try:
            val = float(v)
        except ValueError:
            continue
        rows.append({"date": pd.Timestamp(o["date"]), "value": val})
    if not rows:
        return pd.DataFrame(columns=["date", "value"])
    df = pd.DataFrame(rows).sort_values("date")
    df["series"] = series_id
    return df


def to_monthly_end_last(df: pd.DataFrame) -> pd.Series:
    """Daily (or irregular) -> calendar month-end = last observation in that month."""
    if df.empty:
        return pd.Series(dtype=float)
    s = df.set_index("date")["value"].sort_index()
    out = s.resample("ME").last()
    out.index = pd.to_datetime(out.index).normalize()
    return out


def to_monthly_end_fred_monthly(df: pd.DataFrame) -> pd.Series:
    """FRED monthly (obs date often 1st): one value per calendar month at month-end label."""
    if df.empty:
        return pd.Series(dtype=float)
    s = df.set_index("date")["value"].sort_index()
    g = s.groupby(s.index.to_period("M")).last()
    g.index = pd.to_datetime(g.index.to_timestamp(how="end")).normalize()
    return g.sort_index()


def gdp_asof_monthly(df: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.Series:
    """Quarterly GDP: for each month-end, use latest released quarterly level (as-of)."""
    if df.empty:
        return pd.Series(index=idx, dtype=float)
    s = df.set_index("date")["value"].sort_index()
    out = []
    for t in idx:
        sub = s[s.index <= t]
        out.append(float(sub.iloc[-1]) if len(sub) else float("nan"))
    return pd.Series(out, index=idx)


def build_master_panel(dfs_by_id: dict[str, pd.DataFrame], start: str, end: str) -> pd.DataFrame:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    idx = pd.date_range(start=start_ts, end=end_ts, freq="ME").normalize()

    parts = {}
    for sid, short in COL_MAP.items():
        df = dfs_by_id.get(sid, pd.DataFrame())
        if df.empty:
            parts[short] = pd.Series(index=idx, dtype=float)
            continue
        if sid == "GDPC1":
            ser = gdp_asof_monthly(df, idx)
        elif sid in ("DCOILWTICO", "FEDFUNDS", "SP500"):
            # SP500: daily on FRED but only ~10y of history — pre-2016 months are NaN
            ser = to_monthly_end_last(df).reindex(idx)
        else:
            ser = to_monthly_end_fred_monthly(df).reindex(idx)

        if sid != "GDPC1":
            ser = ser.astype(float)
        parts[short] = ser

    out = pd.DataFrame(parts, index=idx)
    out.index.name = "date"
    out = out.reset_index()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out


def sp500_peak_trough_stats(sp500_monthly: pd.Series) -> dict:
    """Largest peak-to-trough decline in window (expanding high-water mark).

    peak_* = price level at the high before the worst drawdown;
    trough_* = price at the worst drawdown point;
    confirmed_drawdown_pct = (trough - peak) / peak * 100 (negative).
    """
    s = sp500_monthly.dropna().sort_index()
    s.index = pd.to_datetime(s.index).normalize()
    if s.empty:
        return {
            "peak_sp500": None,
            "trough_sp500": None,
            "confirmed_drawdown_pct": None,
            "peak_date": None,
            "trough_date": None,
            "duration_months": None,
        }
    cummax = s.cummax()
    dd_pct = (s / cummax - 1.0) * 100.0
    trough_idx = dd_pct.idxmin()
    trough_val = float(s.loc[trough_idx])
    peak_val = float(cummax.loc[trough_idx])
    sub = s.loc[:trough_idx]
    peak_idx = sub.idxmax()
    peak_val_at_peak = float(s.loc[peak_idx])
    dd = (trough_val - peak_val_at_peak) / peak_val_at_peak * 100.0
    dur = (trough_idx.year - peak_idx.year) * 12 + (trough_idx.month - peak_idx.month)
    return {
        "peak_sp500": peak_val_at_peak,
        "trough_sp500": trough_val,
        "confirmed_drawdown_pct": round(dd, 4),
        "peak_date": str(peak_idx.date()),
        "trough_date": str(trough_idx.date()),
        "duration_months": int(dur),
    }


def main() -> int:
    load_dotenv_keys()
    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if not api_key:
        print("ERROR: FRED_API_KEY not set (repo .env or env).", file=sys.stderr)
        return 1

    GROUND.mkdir(parents=True, exist_ok=True)

    for slug, p_start, p_end in PERIODS:
        period_dir = GROUND / slug
        period_dir.mkdir(parents=True, exist_ok=True)
        dfs: dict[str, pd.DataFrame] = {}

        for sid in SERIES_IDS:
            raw = fetch_fred_json(sid, p_start, p_end, api_key)
            out_path = period_dir / f"{sid}.json"
            out_path.write_text(json.dumps(raw, indent=2))
            dfs[sid] = observations_to_df(raw, sid)
            time.sleep(0.15)  # be polite to FRED

        # Supplemental: monthly S&P total return index (full history on FRED)
        raw_spast = fetch_fred_json("SPASTT01USM661N", p_start, p_end, api_key)
        (period_dir / "SPASTT01USM661N.json").write_text(json.dumps(raw_spast, indent=2))
        time.sleep(0.15)
        dfs_spast = observations_to_df(raw_spast, "SPASTT01USM661N")

        wti_src = "DCOILWTICO"
        sp500_cash_src = "SP500"

        master = build_master_panel(dfs, p_start, p_end)

        # DCOILWTICO begins 1986; pre-1986 windows: monthly spot WTI (FRED WTISPLC)
        if master["wti"].notna().sum() == 0:
            raw_w = fetch_fred_json("WTISPLC", p_start, p_end, api_key)
            (period_dir / "WTISPLC.json").write_text(json.dumps(raw_w, indent=2))
            time.sleep(0.15)
            df_w = observations_to_df(raw_w, "WTISPLC")
            ser_w = to_monthly_end_fred_monthly(df_w)
            idx = pd.to_datetime(master["date"]).dt.normalize()
            master["wti"] = ser_w.reindex(idx).values
            wti_src = "WTISPLC"

        idx = pd.to_datetime(master["date"]).dt.normalize()
        ser_spast = to_monthly_end_fred_monthly(dfs_spast).reindex(idx)
        master["sp_total_return_idx"] = ser_spast.values

        csv_path = GROUND / f"{slug}_macro.csv"
        master.to_csv(csv_path, index=False)
        print(f"Wrote {csv_path} ({len(master)} rows)")

        dt_idx = pd.to_datetime(master["date"])
        if slug == "2022":
            sp_dd_ser = pd.Series(master["sp500"].values, index=dt_idx)
            equity_dd_series_id = "SP500"
        else:
            sp_dd_ser = pd.Series(master["sp_total_return_idx"].values, index=dt_idx)
            equity_dd_series_id = "SPASTT01USM661N"
        dd = sp500_peak_trough_stats(sp_dd_ser)
        wti_ser = pd.Series(master["wti"].values, index=dt_idx)
        oil = harmonized_oil_shock_monthly(
            wti_ser, pd.Timestamp(p_start), pd.Timestamp(p_end)
        )
        stats = {
            **dd,
            **oil,
            "drawdown_field_names_note": (
                "Keys peak_sp500 / trough_sp500 are legacy names; numeric levels come from "
                "equity_drawdown_series_id (total return index or cash SP500), not always "
                "FRED SP500 cash."
            ),
            "period": slug,
            "window_start": p_start,
            "window_end": p_end,
            "wti_column_fred_series": wti_src,
            "wti_model_input": "FRED DCOILWTICO (or WTISPLC monthly pre-1986); not CME CL=F front month.",
            "sp500_cash_column_fred_series": sp500_cash_src,
            "equity_drawdown_series_id": equity_dd_series_id,
            "sp500_cash_fred_note": (
                "FRED SP500 daily: no observations before ~2016-04-01; "
                "`sp500` CSV column is NaN for 1973/1990 windows."
            ),
            "provenance": {
                "DCOILWTICO": "FRED WTI Cushing daily; observation range begins 1986-01-02.",
                "WTISPLC": "Monthly spot WTI used for `wti` column when DCOILWTICO has no observations in window.",
                "SP500": "FRED S&P 500 daily — use only when observations exist in-window (2022 window).",
                "SPASTT01USM661N": (
                    "Monthly S&P 500 total return index — used for drawdown stats in 1973/1990; "
                    "also in CSV as sp_total_return_idx. Not interchangeable with Shiller price column P."
                ),
            },
        }
        stats_path = GROUND / f"{slug}_macro_stats.json"
        stats_path.write_text(json.dumps(stats, indent=2))
        print(f"Wrote {stats_path}")
        print(json.dumps(stats, indent=2))

    print(
        "Mission 1 complete: 9 base series × 3 periods JSON each + "
        "SPASTT01USM661N.json per period + optional WTISPLC; "
        "3 master CSV + 3 *_macro_stats.json. "
        "Equity drawdown: SPAST (1973/1990), SP500 (2022). No NASDAQ-as-S&P."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
