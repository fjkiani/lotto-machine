#!/usr/bin/env python3
"""
Mission 2 (Alpha): 36mo daily Adj Close for sector ETFs + USO + SPY; WTI from FRED;
compute oil betas vs WTI daily returns; write oil_beta_verified.json.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

try:
    from scipy.stats import pearsonr
except ImportError:
    pearsonr = None

REPO_ROOT = Path(__file__).resolve().parents[1]
GROUND = REPO_ROOT / "ground_truth"

SECTOR_ETFS = ["XLE", "XLY", "XLP", "XLI", "XLB", "XLF", "XLV", "XLK", "XLU", "XLRE", "XLC"]
ALL_YF = SECTOR_ETFS + ["USO", "SPY"]

START = "2023-01-01"
END = "2026-04-01"  # yfinance end exclusive → includes through 2026-03-31
FRED_START = "2023-01-01"
FRED_END = "2026-03-31"


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


def fetch_wti_fred(api_key: str) -> pd.Series:
    q = urlencode(
        {
            "series_id": "DCOILWTICO",
            "observation_start": FRED_START,
            "observation_end": FRED_END,
            "file_type": "json",
            "api_key": api_key,
        }
    )
    url = f"https://api.stlouisfed.org/fred/series/observations?{q}"
    with urlopen(url, timeout=120) as resp:
        raw = json.loads(resp.read().decode())
    rows = []
    for o in raw.get("observations") or []:
        v = o.get("value")
        if v in (".", "", None):
            continue
        rows.append({"date": pd.Timestamp(o["date"]), "WTI": float(v)})
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows).set_index("date").sort_index()
    return df["WTI"]


def yahoo_v8_adj_close(ticker: str) -> tuple[pd.Series | None, str | None]:
    """Yahoo chart API v8 (Adj Close) — same data as yfinance, often works when yfinance is throttled."""
    p1 = int(pd.Timestamp(START, tz="UTC").timestamp())
    p2 = int(pd.Timestamp(END, tz="UTC").timestamp())
    url = (
        f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?period1={p1}&period2={p2}&interval=1d"
    )
    try:
        req = urlopen(
            Request(url, headers={"User-Agent": "Mozilla/5.0"}),
            timeout=60,
        )
        raw = json.loads(req.read().decode())
    except Exception as exc:
        return None, str(exc)

    err = raw.get("chart", {}).get("error")
    if err:
        return None, str(err)

    res = (raw.get("chart") or {}).get("result") or []
    if not res:
        return None, "empty chart result"
    block = res[0]
    ts = block.get("timestamp") or []
    adj = (block.get("indicators") or {}).get("adjclose") or []
    if not ts or not adj or not adj[0].get("adjclose"):
        return None, "no adjclose in response"
    vals = adj[0]["adjclose"]
    idx = pd.to_datetime(ts, unit="s", utc=True).tz_localize(None).normalize()
    s = pd.Series(vals, index=idx, name=ticker).dropna()
    s = s.loc[(s.index >= pd.Timestamp(START)) & (s.index < pd.Timestamp(END))]
    return s, None


def yf_adj_close(ticker: str) -> tuple[pd.Series | None, str | None]:
    try:
        import yfinance as yf
    except ImportError:
        return None, "yfinance not installed"

    try:
        obj = yf.Ticker(ticker)
        df = obj.history(start=START, end=END, auto_adjust=False)
        if df is None or df.empty or "Adj Close" not in df.columns:
            return None, "empty or no Adj Close"
        s = df["Adj Close"].copy()
        s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
        s.name = ticker
        return s, None
    except Exception as exc:
        return None, str(exc)


def av_adj_close(ticker: str, api_key: str) -> tuple[pd.Series | None, str | None]:
    """Alpha Vantage TIME_SERIES_DAILY_ADJUSTED."""
    base = "https://www.alphavantage.co/query"
    q = urlencode(
        {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "outputsize": "full",
            "apikey": api_key,
        }
    )
    try:
        with urlopen(f"{base}?{q}", timeout=120) as resp:
            raw = json.loads(resp.read().decode())
    except Exception as exc:
        return None, str(exc)

    if "Note" in raw or "Information" in raw:
        return None, raw.get("Note") or raw.get("Information", "rate limit note")

    ts = raw.get("Time Series (Daily)")
    if not ts:
        return None, raw.get("Error Message", "no time series")

    rows = []
    for d_str, bar in ts.items():
        ac = bar.get("5. adjusted close")
        if ac is None:
            continue
        rows.append({"date": pd.Timestamp(d_str), ticker: float(ac)})
    if not rows:
        return None, "no rows parsed"
    df = pd.DataFrame(rows).set_index("date").sort_index()
    return df[ticker], None


def av_daily_close(ticker: str, api_key: str) -> tuple[pd.Series | None, str | None]:
    """Alpha Vantage TIME_SERIES_DAILY (free tier) — unadjusted close."""
    base = "https://www.alphavantage.co/query"
    q = urlencode(
        {
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "outputsize": "full",
            "apikey": api_key,
        }
    )
    try:
        with urlopen(f"{base}?{q}", timeout=120) as resp:
            raw = json.loads(resp.read().decode())
    except Exception as exc:
        return None, str(exc)

    if "Note" in raw or "Information" in raw:
        return None, raw.get("Note") or raw.get("Information", "rate limit note")

    ts = raw.get("Time Series (Daily)")
    if not ts:
        return None, raw.get("Error Message", "no time series")

    rows = []
    for d_str, bar in ts.items():
        c = bar.get("4. close")
        if c is None:
            continue
        rows.append({"date": pd.Timestamp(d_str), ticker: float(c)})
    if not rows:
        return None, "no rows parsed"
    df = pd.DataFrame(rows).set_index("date").sort_index()
    s = df[ticker]
    s = s.loc[(s.index >= pd.Timestamp(START)) & (s.index < pd.Timestamp(END))]
    return s, None


def stooq_daily_close(ticker: str) -> tuple[pd.Series | None, str | None]:
    """Stooq daily history (Close) — no API key; US listings `.us`."""
    sym = f"{ticker.lower()}.us"
    d1 = pd.Timestamp(START).strftime("%Y%m%d")
    d2 = (pd.Timestamp(END) - pd.Timedelta(days=1)).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d&d1={d1}&d2={d2}"
    try:
        with urlopen(url, timeout=120) as resp:
            txt = resp.read().decode()
    except Exception as exc:
        return None, str(exc)

    if not txt.strip() or "No data" in txt:
        return None, "empty or no data"

    df = pd.read_csv(io.StringIO(txt))
    if df.empty or "Date" not in df.columns or "Close" not in df.columns:
        return None, f"unexpected csv cols: {list(df.columns)}"

    df["date"] = pd.to_datetime(df["Date"])
    s = pd.Series(df["Close"].values, index=df["date"]).sort_index()
    s.index = pd.DatetimeIndex(s.index).normalize()
    s = s.loc[(s.index >= pd.Timestamp(START)) & (s.index < pd.Timestamp(END))]
    s.name = ticker
    return s, None


def fetch_equity_series(ticker: str, av_key: str) -> tuple[pd.Series | None, str]:
    """Priority: yfinance Adj Close (retry) → Yahoo v8 chart → AV adjusted → AV daily → Stooq close."""
    last_err = ""
    for attempt in range(2):
        s, err = yf_adj_close(ticker)
        last_err = str(err or "")
        if s is not None and len(s) > 10:
            return s, "yfinance_AdjClose"
        if attempt == 0:
            time.sleep(4)

    s, err = yahoo_v8_adj_close(ticker)
    last_err = str(err or last_err)
    if s is not None and len(s) > 10:
        return s, "yahoo_chart_v8_adjclose"

    if av_key:
        s, err = av_adj_close(ticker, av_key)
        last_err = str(err or last_err)
        if s is not None and len(s) > 10:
            return s, "alpha_vantage_adjusted"
        # AV free tier spacing; skip long wait if adjusted endpoint is premium-only
        if "premium" not in str(err or "").lower():
            time.sleep(15)
        else:
            time.sleep(2)
        s, err = av_daily_close(ticker, av_key)
        last_err = str(err or last_err)
        if s is not None and len(s) > 10:
            return s, "alpha_vantage_daily_close"

    s, err = stooq_daily_close(ticker)
    last_err = str(err or last_err)
    if s is not None and len(s) > 10:
        return s, "stooq_close"

    return None, f"all sources failed (last: {last_err})"


def oil_beta_label(beta: float, p_value: float) -> str:
    if p_value > 0.05:
        return "STATISTICALLY_INSIGNIFICANT"
    if beta > 0.02:
        return "BENEFITS"
    if beta < -0.10:
        return "HURT_HIGH"
    if beta < -0.03:
        return "HURT_MEDIUM"
    return "HURT_LOW"


def main() -> int:
    load_dotenv_keys()
    fred_key = os.environ.get("FRED_API_KEY", "").strip()
    av_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()

    if not fred_key:
        print("ERROR: FRED_API_KEY required for WTI column.", file=sys.stderr)
        return 1
    if pearsonr is None:
        print("ERROR: scipy required (pip install scipy).", file=sys.stderr)
        return 1

    GROUND.mkdir(parents=True, exist_ok=True)

    failures: dict[str, str] = {}
    series_map: dict[str, pd.Series] = {}
    equity_sources: dict[str, str] = {}

    try:
        import yfinance as yf

        batch = yf.download(
            ALL_YF,
            start=START,
            end=END,
            auto_adjust=False,
            group_by="ticker",
            threads=True,
            progress=False,
        )
        if not batch.empty and isinstance(batch.columns, pd.MultiIndex):
            ac = batch["Adj Close"]
            for t in ALL_YF:
                if t not in ac.columns:
                    continue
                col = ac[t].dropna()
                if len(col) < 30:
                    continue
                s = col.copy()
                s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
                s.name = t
                series_map[t] = s
                equity_sources[t] = "yfinance_batch_AdjClose"
                print(f"OK yfinance batch {t} ({len(s)} rows)")
        elif not batch.empty and len(ALL_YF) == 1:
            s = batch["Adj Close"].dropna()
            s.index = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
            series_map[ALL_YF[0]] = s
            equity_sources[ALL_YF[0]] = "yfinance_batch_AdjClose"
        else:
            raise ValueError("batch shape unexpected")
    except Exception as exc:
        print(f"WARN yfinance batch failed ({exc})")

    for t in ALL_YF:
        if t in series_map and len(series_map[t].dropna()) >= 30:
            continue
        if t in series_map:
            del series_map[t]
        s, src = fetch_equity_series(t, av_key)
        if s is not None and len(s.dropna()) >= 30:
            series_map[t] = s
            equity_sources[t] = src
            print(f"OK {t} via {src} ({len(s)} rows)")
        else:
            failures[t] = src
            print(f"FAIL {t}: {src}")

    wti = fetch_wti_fred(fred_key)
    if wti.empty:
        print("ERROR: FRED WTI empty", file=sys.stderr)
        return 1
    series_map["WTI"] = wti
    print(f"OK FRED WTI ({len(wti)} rows)")

    # Align all to union of dates then build wide CSV (business days from ETFs)
    df = pd.DataFrame(series_map).sort_index()
    df.index.name = "date"
    df = df.reset_index()
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    cols = ["date"] + [c for c in ALL_YF if c in df.columns] + (["WTI"] if "WTI" in df.columns else [])
    for c in ALL_YF + ["WTI"]:
        if c not in df.columns:
            df[c] = np.nan
    ordered = ["date"] + ALL_YF + ["WTI"]
    df = df[[c for c in ordered if c in df.columns]]
    out_csv = GROUND / "sector_prices_36mo.csv"
    df.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv} ({len(df)} rows)")

    # Daily returns — only rows where both sector and WTI valid
    px = pd.DataFrame(series_map).sort_index()
    rets = px.pct_change(fill_method=None).dropna(how="all")

    betas_out: dict = {
        "window": {"start": START, "end_exclusive": END},
        "wti_source": "FRED DCOILWTICO",
        "wti_note": (
            "Regression uses FRED DCOILWTICO daily returns — not the same object as Yahoo CL=F "
            "(front-month futures). Expect level divergences vs spot series."
        ),
        "price_sources": equity_sources,
        "notes": (
            "price_sources keys are exactly the tickers used for prices (11 sector ETFs + USO + SPY). "
            "sectors object includes the same 13 names with oil_beta blocks; "
            "use_in_eps_model is False for USO/SPY (benchmarks, not GICS sectors). "
            "Betas = cov(sector_ret, WTI_ret)/var(WTI_ret) on overlapping days."
        ),
        "fetch_failures": failures,
        "sectors": {},
    }

    wti_r = rets["WTI"].dropna()
    var_wti = float(wti_r.var(ddof=1))
    if var_wti <= 0 or wti_r.empty:
        print("ERROR: WTI returns have zero variance or empty", file=sys.stderr)
        return 1

    for etf in SECTOR_ETFS + ["USO", "SPY"]:
        is_sector = etf in SECTOR_ETFS
        if etf not in rets.columns:
            betas_out["sectors"][etf] = {
                "error": "no price series",
                "label": "STATISTICALLY_INSIGNIFICANT",
                "use_in_eps_model": False,
                "role": "gics_sector" if is_sector else "benchmark",
            }
            continue
        pair = pd.concat([rets[etf], rets["WTI"]], axis=1, keys=["sec", "wti"]).dropna()
        if len(pair) < 30:
            betas_out["sectors"][etf] = {
                "error": f"insufficient aligned days: {len(pair)}",
                "label": "STATISTICALLY_INSIGNIFICANT",
                "use_in_eps_model": False,
                "role": "gics_sector" if is_sector else "benchmark",
            }
            continue
        sec_v = pair["sec"].values
        wti_v = pair["wti"].values
        cov = np.cov(sec_v, wti_v, ddof=1)
        beta = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] > 0 else float("nan")
        r, p = pearsonr(sec_v, wti_v)
        r_sq = float(r**2)
        p_val = float(p)
        lbl = oil_beta_label(beta, p_val)
        if not is_sector:
            lbl = "BENCHMARK"
        use_eps = (p_val <= 0.05) and is_sector
        betas_out["sectors"][etf] = {
            "oil_beta": round(beta, 6),
            "r_squared": round(r_sq, 6),
            "p_value": p_val,
            "n_obs": int(len(pair)),
            "label": lbl,
            "use_in_eps_model": use_eps,
            "role": "gics_sector" if is_sector else "benchmark",
            "price_source": equity_sources.get(etf, "unknown"),
        }

    beta_path = GROUND / "oil_beta_verified.json"
    beta_path.write_text(json.dumps(betas_out, indent=2))
    print(f"Wrote {beta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
