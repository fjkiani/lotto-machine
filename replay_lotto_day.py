#!/usr/bin/env python3
"""
REPLAY LOTTO MACHINE SIGNALS FOR A PAST DAY
===========================================

Uses the production SignalGenerator (regular + lottery) to replay a historical
session minute-by-minute and log all signals that *would* have fired.

- Loads InstitutionalContext from data/historical/institutional_contexts/{SYMBOL}/{DATE}.pkl
- Loads 1m OHLCV data for that date from yfinance
- Feeds rolling minute bars into SignalGenerator.generate_signals(...)
- Writes all signals to logs/replay/lotto_signals_{SYMBOL}_{DATE}.csv

Author: Alpha's AI Hedge Fund
Date: 2025-11-20
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging
from typing import List

import pandas as pd
import pickle

# Paths
ROOT = Path(__file__).parent
sys.path.extend([
    str(ROOT / "live_monitoring" / "core"),
    str(ROOT / "live_monitoring" / "config"),
    str(ROOT / "core"),
    str(ROOT / "core" / "data"),
])

from signal_generator import SignalGenerator
from lottery_signals import LiveSignal, LotterySignal
from ultra_institutional_engine import InstitutionalContext, UltraInstitutionalEngine
from alpha_vantage_client import AlphaVantageClient
import monitoring_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_institutional_context(symbol: str, date_str: str) -> InstitutionalContext:
    """
    Load InstitutionalContext from disk if available, otherwise build via API.
    
    Disk path: data/historical/institutional_contexts/{symbol}/{date}.pkl
    Live path: UltraInstitutionalEngine.build_institutional_context()
    """
    data_dir = ROOT / "data" / "historical" / "institutional_contexts" / symbol
    path = data_dir / f"{date_str}.pkl"

    if path.exists():
        with open(path, "rb") as f:
            obj = pickle.load(f)

        # Old code may have stored dict with 'context' key
        if isinstance(obj, dict) and "context" in obj:
            ctx = obj["context"]
        else:
            ctx = obj

        if not isinstance(ctx, InstitutionalContext):
            raise TypeError(f"Expected InstitutionalContext, got {type(ctx)}")

        logger.info(f"✅ Loaded InstitutionalContext from {path}")
        return ctx

    # Fallback: build via UltraInstitutionalEngine using previous day's date
    api_key = monitoring_config.API.chartexchange_api_key
    engine = UltraInstitutionalEngine(api_key)

    replay_date = datetime.fromisoformat(date_str)
    ctx_date = (replay_date - timedelta(days=1)).strftime("%Y-%m-%d")
    logger.info(f"📡 No local context; building InstitutionalContext via API for {symbol} ({ctx_date})")

    ctx = engine.build_institutional_context(symbol, ctx_date)
    if not ctx:
        raise RuntimeError(f"Failed to build InstitutionalContext for {symbol} on {ctx_date}")

    return ctx


def load_intraday(symbol: str, date_str: str) -> pd.DataFrame:
    """
    Load 1-minute intraday bars for a given date using Alpha Vantage.
    
    Alpha Vantage provides ~15 days of 1-minute data (20k+ bars).
    This replaces yfinance to avoid rate limits.
    """
    logger.info(f"📊 Loading intraday 1m bars for {symbol} via Alpha Vantage")
    
    # Initialize Alpha Vantage client
    av_client = AlphaVantageClient(api_key="DWUGOPJJ75DPU39D")
    
    # Fetch full intraday data
    df = av_client.get_intraday_1min(symbol, outputsize="full")
    
    if df.empty:
        raise RuntimeError(f"No intraday data for {symbol} from Alpha Vantage")
    
    # Filter for specific date if provided
    if date_str:
        target_date = pd.to_datetime(date_str).date()
        df = df[df.index.date == target_date]
        
        if df.empty:
            raise RuntimeError(f"No data for {symbol} on {date_str}")
        
        logger.info(f"   Filtered to {date_str}: {len(df)} bars")
    
    # Make index timezone-naive (Alpha Vantage returns UTC)
    try:
        df.index = df.index.tz_localize(None)
    except Exception:
        pass
    
    # Standardize column names to match expected format (uppercase first letter)
    df.columns = [col.capitalize() for col in df.columns]
    
    logger.info(f"   Loaded {len(df)} bars from {df.index.min()} to {df.index.max()}")
    return df


def replay_day(symbol: str, date_str: str) -> List[LiveSignal]:
    """
    Replay a full day for one symbol and return all generated signals.
    """
    api_key = monitoring_config.API.chartexchange_api_key

    sig_gen = SignalGenerator(
        min_master_confidence=monitoring_config.TRADING.min_master_confidence,
        min_high_confidence=monitoring_config.TRADING.min_high_confidence,
        api_key=api_key,
        use_sentiment=False,   # keep deterministic on sentiment
        use_gamma=False,       # optional; can enable later
        use_lottery_mode=True,
        lottery_confidence_threshold=0.80,
        use_narrative=True,    # ✅ enable narrative enrichment for replay
    )

    ctx = load_institutional_context(symbol, date_str)
    df = load_intraday(symbol, date_str)

    all_signals: List[LiveSignal] = []
    account_value = monitoring_config.TRADING.account_size

    logger.info(f"🔁 Replaying {symbol} on {date_str} ({len(df)} bars)")

    # Iterate minute-by-minute
    for i, (ts, row) in enumerate(df.iterrows()):
        price = float(row["Close"])
        # rolling window of last 30 bars
        window = df.iloc[max(0, i - 29) : i + 1][["Open", "High", "Low", "Close", "Volume"]].copy()

        try:
            signals = sig_gen.generate_signals(
                symbol, price, ctx, minute_bars=window, account_value=account_value
            )
        except Exception as e:
            logger.error(f"Error generating signals at {ts} for {symbol}: {e}")
            continue

        if signals:
            for s in signals:
                # Attach timestamp for logging
                setattr(s, "timestamp", ts)
            all_signals.extend(signals)

    logger.info(f"✅ Finished replay for {symbol} on {date_str}: {len(all_signals)} signals")
    return all_signals


def write_signals_csv(symbol: str, date_str: str, signals: List[LiveSignal]) -> Path:
    """
    Write signals to logs/replay/lotto_signals_{symbol}_{date}.csv
    """
    out_dir = ROOT / "logs" / "replay"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"lotto_signals_{symbol}_{date_str}.csv"

    import csv

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp",
                "symbol",
                "action",
                "signal_type",
                "entry_price",
                "stop_price",
                "target_price",
                "confidence",
                "position_size_pct",
                "risk_reward_ratio",
                "lottery",
                "rationale",
            ]
        )
        for s in signals:
            action = s.action.value if hasattr(s.action, "value") else str(s.action)
            sig_type = s.signal_type.value if hasattr(s.signal_type, "value") else str(s.signal_type)
            is_lottery = isinstance(s, LotterySignal)
            writer.writerow(
                [
                    getattr(s, "timestamp", None),
                    s.symbol,
                    action,
                    sig_type,
                    getattr(s, "entry_price", 0.0),
                    getattr(s, "stop_price", 0.0),
                    getattr(s, "target_price", 0.0),
                    getattr(s, "confidence", 0.0),
                    getattr(s, "position_size_pct", 0.0),
                    getattr(s, "risk_reward_ratio", 0.0),
                    is_lottery,
                    getattr(s, "rationale", ""),
                ]
            )

    logger.info(f"📝 Wrote signals to {out_path}")
    return out_path


def find_latest_context_date(symbol: str) -> str:
    """
    Find the most recent date for which we have an institutional context.
    """
    ctx_dir = ROOT / "data" / "historical" / "institutional_contexts" / symbol
    if not ctx_dir.exists():
        raise FileNotFoundError(f"No context dir: {ctx_dir}")

    dates = []
    for p in ctx_dir.glob("*.pkl"):
        # filenames like 2025-10-17.pkl
        try:
            d = p.stem
            datetime.fromisoformat(d)
            dates.append(d)
        except Exception:
            continue

    if not dates:
        raise RuntimeError(f"No context dates found in {ctx_dir}")

    return sorted(dates)[-1]


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Replay lotto signals for a historical day")
    parser.add_argument("--symbol", nargs="+", default=["SPY", "QQQ"], help="Symbols to replay")
    parser.add_argument("--date", type=str, default=None, help="Date YYYY-MM-DD (default: latest context date)")
    args = parser.parse_args()

    symbols = args.symbol

    for sym in symbols:
        # If no date provided, use today's date (for intraday) but context from previous day
        if args.date:
            date_str = args.date
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"\n=== REPLAY {sym} on {date_str} ===")
        try:
            signals = replay_day(sym, date_str)
            write_signals_csv(sym, date_str, signals)
        except Exception as e:
            logger.error(f"Error replaying {sym} on {date_str}: {e}")


if __name__ == "__main__":
    main()


