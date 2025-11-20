#!/usr/bin/env python3
"""
SPY 1m Intraday Replay Analyzer
- Fetches today's 1-minute SPY data (yfinance)
- Computes rolling price/volume features and regimes
- Scans multiple breakout/reversal windows and thresholds
- Exports timestamped signal log and saves overlay chart
"""

import sys
import os
import math
import json
from datetime import datetime
from typing import List, Dict, Any

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import yfinance as yf


def slope_normalized(series: pd.Series) -> float:
    """Return normalized linear slope over the series (slope / mean(price))."""
    values = series.values.astype(float)
    if len(values) < 3 or np.mean(values) == 0:
        return np.nan
    x = np.arange(len(values))
    slope = np.polyfit(x, values, 1)[0]
    return float(slope / np.mean(values))


def fetch_intraday(symbol: str, period: str = "1d", interval: str = "1m") -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    if df is None or df.empty:
        raise RuntimeError(f"No data returned for {symbol} {period} {interval}")
    # Ensure naive timestamps for consistent plotting/logging
    df = df.copy()
    try:
        df = df.tz_localize(None)
    except Exception:
        pass
    return df


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ret"] = out["Close"].pct_change()

    # Volume z-score (30-lookback)
    vol_mean = out["Volume"].rolling(30).mean()
    vol_std = out["Volume"].rolling(30).std()
    out["vol_z"] = (out["Volume"] - vol_mean) / vol_std

    # Trend and momentum windows
    for n in [5, 10, 20, 30]:
        out[f"trend_{n}"] = out["Close"].rolling(n).apply(slope_normalized, raw=False)
        out[f"mom_{n}"] = out["Close"].pct_change(n)

    # Simple volatility (returns std)
    out["volatility_30"] = out["ret"].rolling(30).std()
    return out


def detect_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Scan for breakouts/reversals across windows and thresholds.
    Returns a dataframe with timestamped signals.
    """
    records: List[Dict[str, Any]] = []
    windows = [5, 10, 20, 30]
    thresholds = [0.002, 0.004, 0.006, 0.010, 0.015]  # 0.2%..1.5%

    for n in windows:
        roll_max = df["Close"].rolling(n).max().shift(1)
        roll_min = df["Close"].rolling(n).min().shift(1)

        for thr in thresholds:
            bo_mask = df["Close"] > roll_max * (1.0 + thr)
            rv_mask = df["Close"] < roll_min * (1.0 - thr)

            for ts, is_bo in bo_mask[bo_mask].items():
                price = float(df.at[ts, "Close"]) if ts in df.index else np.nan
                vol = int(df.at[ts, "Volume"]) if ts in df.index else 0
                rec = {
                    "timestamp": ts.isoformat(),
                    "type": "BREAKOUT",
                    "window": n,
                    "threshold": thr,
                    "price": price,
                    "level": float(roll_max.at[ts]) if ts in roll_max.index else np.nan,
                    "strength": float((price - roll_max.at[ts]) / roll_max.at[ts]) if ts in roll_max.index and roll_max.at[ts] not in (0, np.nan) else np.nan,
                    "volume": vol,
                    "vol_z": float(df.at[ts, "vol_z"]) if ts in df.index else np.nan,
                    "trend_10": float(df.at[ts, "trend_10"]) if ts in df.index else np.nan,
                    "trend_20": float(df.at[ts, "trend_20"]) if ts in df.index else np.nan,
                    "mom_10": float(df.at[ts, "mom_10"]) if ts in df.index else np.nan,
                    "mom_20": float(df.at[ts, "mom_20"]) if ts in df.index else np.nan,
                }
                records.append(rec)

            for ts, is_rv in rv_mask[rv_mask].items():
                price = float(df.at[ts, "Close"]) if ts in df.index else np.nan
                vol = int(df.at[ts, "Volume"]) if ts in df.index else 0
                rec = {
                    "timestamp": ts.isoformat(),
                    "type": "REVERSAL",
                    "window": n,
                    "threshold": thr,
                    "price": price,
                    "level": float(roll_min.at[ts]) if ts in roll_min.index else np.nan,
                    "strength": float((roll_min.at[ts] - price) / roll_min.at[ts]) if ts in roll_min.index and roll_min.at[ts] not in (0, np.nan) else np.nan,
                    "volume": vol,
                    "vol_z": float(df.at[ts, "vol_z"]) if ts in df.index else np.nan,
                    "trend_10": float(df.at[ts, "trend_10"]) if ts in df.index else np.nan,
                    "trend_20": float(df.at[ts, "trend_20"]) if ts in df.index else np.nan,
                    "mom_10": float(df.at[ts, "mom_10"]) if ts in df.index else np.nan,
                    "mom_20": float(df.at[ts, "mom_20"]) if ts in df.index else np.nan,
                }
                records.append(rec)

    sig_df = pd.DataFrame.from_records(records)
    if not sig_df.empty:
        sig_df.sort_values(by=["timestamp", "window", "threshold"], inplace=True)
    return sig_df


def save_overlay_chart(df: pd.DataFrame, symbol: str, window: int = 20, thr: float = 0.006, out_path: str = "spy_1m_breakout_overlay.png") -> None:
    roll_max = df["Close"].rolling(window).max().shift(1)
    roll_min = df["Close"].rolling(window).min().shift(1)
    bo = df["Close"] > roll_max * (1.0 + thr)
    rv = df["Close"] < roll_min * (1.0 - thr)

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(df.index, df["Close"], color="black", lw=1, label="Close")
    ax.plot(df.index, roll_max * (1.0 + thr), color="orange", alpha=0.6, lw=1, label=f"BO threshold (n={window}, thr={thr*100:.1f}%)")
    ax.plot(df.index, roll_min * (1.0 - thr), color="purple", alpha=0.6, lw=1, label=f"RV threshold (n={window}, thr={thr*100:.1f}%)")
    ax.scatter(df.index[bo], df["Close"][bo], color="green", s=16, label="Breakout")
    ax.scatter(df.index[rv], df["Close"][rv], color="red", s=16, label="Reversal")
    ax.set_title(f"{symbol} 1m Intraday with Breakout/Reversal Markers")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    plt.tight_layout()
    plt.savefig(out_path, dpi=220)
    plt.close()


def main() -> None:
    symbol = "SPY"
    period = "1d"
    interval = "1m"

    print(f"Fetching {symbol} {period} {interval}...")
    df = fetch_intraday(symbol, period=period, interval=interval)
    feat = compute_features(df)

    print("Computing breakout/reversal signals across windows/thresholds...")
    sig = detect_signals(feat)

    # Save artifacts
    feats_path = "spy_1m_features.csv"
    sig_path = "spy_1m_signal_log.csv"
    feat.to_csv(feats_path)
    sig.to_csv(sig_path, index=False)
    save_overlay_chart(feat, symbol=symbol)

    # Print concise diagnostics
    print("\nRolling feature snapshot (last 10 rows):")
    cols = [
        "Close", "Volume", "vol_z", "volatility_30",
        "trend_5", "trend_10", "trend_20", "trend_30",
        "mom_5", "mom_10", "mom_20", "mom_30",
    ]
    print(feat[cols].tail(10).to_string())

    print("\nSignal summary (top 10):")
    if sig.empty:
        print("No signals detected with current windows/thresholds.")
    else:
        print(sig.head(10).to_string(index=False))

    print("\nArtifacts saved:")
    print(f"- {feats_path}")
    print(f"- {sig_path}")
    print("- spy_1m_breakout_overlay.png")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


