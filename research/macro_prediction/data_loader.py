"""
Shared data loader for macro prediction framework.
Sources: BLS Public API (no key) + Yahoo Finance monthly bars.
All data 2018-01-01 through 2025-12-31.
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time

HEADERS = {'User-Agent': 'Mozilla/5.0 (macro-research-bot)'}

# ── BLS series ──────────────────────────────────────────────────────────────
BLS_SERIES = {
    'CPI_ALL':            'CUUR0000SA0',       # CPI-U all items (NSA index)
    'CPI_CORE':           'CUUR0000SA0L1E',    # CPI-U less food & energy
    'PPI_FINAL':          'WPSFD4',            # PPI final demand
    'UNEMPLOYMENT':       'LNS14000000',       # Unemployment rate (%)
    'NFP_TOTAL':          'CES0000000001',     # Nonfarm payrolls (thousands)
    'AVG_HOURLY_EARNINGS':'CES0500000003',     # Avg hourly earnings ($)
}

# ── Yahoo Finance monthly tickers ───────────────────────────────────────────
YF_TICKERS = {
    'TLT':  '20yr Treasury bond ETF',
    '^TNX': '10yr yield',
    '^IRX': '13-wk T-bill yield',
    'TIP':  'TIPS ETF (breakeven inflation)',
    'UUP':  'Dollar bull ETF',
    'DBC':  'Commodity index ETF',
    'GLD':  'Gold ETF',
    'SPY':  'S&P 500',
    'IWM':  'Russell 2000',
    'HYG':  'High yield bonds',
    'LQD':  'Investment grade bonds',
    'XLF':  'Financials ETF',
}


def load_bls(start_year: int = 2018, end_year: int = 2025) -> dict[str, pd.DataFrame]:
    """
    Pull BLS monthly series via public API (no key required).
    Returns dict of {name: DataFrame(index=DatetimeIndex, columns=['value'])}.
    """
    payload = {
        "seriesid": list(BLS_SERIES.values()),
        "startyear": str(start_year),
        "endyear": str(end_year),
    }
    r = requests.post(
        'https://api.bls.gov/publicAPI/v2/timeseries/data/',
        json=payload, headers=HEADERS, timeout=25
    )
    r.raise_for_status()
    j = r.json()

    if j.get('status') != 'REQUEST_SUCCEEDED':
        raise RuntimeError(f"BLS API error: {j.get('message')}")

    out = {}
    for series in j.get('Results', {}).get('series', []):
        sid = series['seriesID']
        name = next((k for k, v in BLS_SERIES.items() if v == sid), sid)
        rows = []
        for d in series.get('data', []):
            period = d['period']
            if not (period.startswith('M') and period != 'M13'):
                continue
            try:
                val = float(d['value'])
                month = int(period[1:])
                rows.append({
                    'date': pd.Timestamp(f"{d['year']}-{month:02d}-01"),
                    'value': val
                })
            except (ValueError, TypeError):
                pass
        if rows:
            df = (pd.DataFrame(rows)
                    .sort_values('date')
                    .set_index('date')
                    .rename(columns={'value': name}))
            out[name] = df
    return out


def load_yf_monthly(start: str = '2018-01-01', end: str = '2025-12-31') -> dict[str, pd.DataFrame]:
    """
    Pull monthly OHLC from Yahoo Finance for macro proxy tickers.
    Returns dict of {ticker: DataFrame(index=DatetimeIndex, columns=['close'])}.
    """
    p1 = int(pd.Timestamp(start).timestamp())
    p2 = int(pd.Timestamp(end).timestamp())
    out = {}

    for ticker in YF_TICKERS:
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
               f"?interval=1mo&period1={p1}&period2={p2}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            j = r.json()
            result = j.get('chart', {}).get('result', [{}])[0]
            ts = result.get('timestamp', [])
            q = result.get('indicators', {}).get('quote', [{}])[0]
            if ts and q.get('close'):
                dates = [
                    datetime.fromtimestamp(t, tz=timezone.utc)
                             .replace(day=1, tzinfo=None)
                    for t in ts
                ]
                df = pd.DataFrame(
                    {'close': q['close']},
                    index=pd.DatetimeIndex(dates)
                ).dropna()
                df.index.name = 'date'
                out[ticker] = df
        except Exception:
            pass
        time.sleep(0.15)

    return out


def build_master_frame(bls: dict, yf: dict) -> pd.DataFrame:
    """
    Merge all series into a single monthly DataFrame aligned on date index.
    Computes derived features:
      - MoM changes for BLS levels
      - YoY changes for CPI/PPI
      - Monthly returns for YF tickers
      - TIPS breakeven proxy: TIP return - TLT return
    """
    frames = []

    # BLS levels
    for name, df in bls.items():
        frames.append(df.rename(columns={name: name}))

    # YF closes
    for ticker, df in yf.items():
        safe = ticker.replace('^', '').replace('=', '')
        frames.append(df.rename(columns={'close': f'YF_{safe}'}))

    master = pd.concat(frames, axis=1).sort_index()

    # ── Derived: BLS MoM changes ──
    for col in ['CPI_ALL', 'CPI_CORE', 'PPI_FINAL', 'NFP_TOTAL', 'AVG_HOURLY_EARNINGS']:
        if col in master.columns:
            master[f'{col}_MOM'] = master[col].pct_change() * 100  # percent

    # ── Derived: CPI YoY ──
    for col in ['CPI_ALL', 'CPI_CORE']:
        if col in master.columns:
            master[f'{col}_YOY'] = master[col].pct_change(12) * 100

    # ── Derived: YF monthly returns ──
    for ticker in YF_TICKERS:
        safe = ticker.replace('^', '').replace('=', '')
        col = f'YF_{safe}'
        if col in master.columns:
            master[f'{col}_RET'] = master[col].pct_change() * 100

    # ── Derived: TIPS breakeven proxy (TIP return - TLT return) ──
    if 'YF_TIP_RET' in master.columns and 'YF_TLT_RET' in master.columns:
        master['BREAKEVEN_PROXY'] = master['YF_TIP_RET'] - master['YF_TLT_RET']

    # ── Derived: Credit spread proxy (HYG - LQD return) ──
    if 'YF_HYG_RET' in master.columns and 'YF_LQD_RET' in master.columns:
        master['CREDIT_SPREAD_CHG'] = master['YF_HYG_RET'] - master['YF_LQD_RET']

    return master


def regime_label(spy_ret: float) -> str:
    """Classify monthly SPY return into regime."""
    if spy_ret >= 1.0:
        return 'UPTREND'
    elif spy_ret <= -1.0:
        return 'DOWNTREND'
    else:
        return 'CHOPPY'


if __name__ == '__main__':
    print("Loading BLS data...")
    bls = load_bls()
    for k, v in bls.items():
        print(f"  {k}: {len(v)} obs, {v.index[0].date()} → {v.index[-1].date()}")

    print("\nLoading Yahoo Finance data...")
    yf = load_yf_monthly()
    for k, v in yf.items():
        print(f"  {k}: {len(v)} bars")

    print("\nBuilding master frame...")
    master = build_master_frame(bls, yf)
    print(f"  Shape: {master.shape}")
    print(f"  Columns: {list(master.columns)}")
    print(f"  Date range: {master.index[0].date()} → {master.index[-1].date()}")
    print(f"  Non-null counts:\n{master.count()}")
