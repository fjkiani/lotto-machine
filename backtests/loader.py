"""
Shared data loader for all backtest modules.
Run: python -m backtests.loader   (prints inventory)
"""
import json, sqlite3, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def bars_15min():
    """494 bars, Feb 17 → Mar 13 2026, full OHLCV."""
    with open(ROOT / "backtesting/data/spy_15min_1mo.json") as f:
        return json.load(f)


def bars_daily():
    """547 bars, Jan 2024 → Mar 2026, close + pct_change only."""
    with open(ROOT / "live_monitoring/data/backtest/spy_daily.json") as f:
        return json.load(f)


def bars_daily_2022():
    """532 bars, Dec 2021 → Jan 2024, open + close only."""
    with open(ROOT / "live_monitoring/data/backtest/spy_daily_2022_2023.json") as f:
        return json.load(f)


def dp_interactions():
    """346 settled DP level interactions with BOUNCE/BREAK outcomes."""
    db = ROOT / "data/dp_learning.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM dp_interactions WHERE outcome IS NOT NULL AND outcome != 'PENDING' ORDER BY timestamp"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def dp_snapshots():
    """32 daily DP position snapshots for SPY."""
    db = ROOT / "data/dp_trends.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM dp_daily_snapshots WHERE symbol='SPY' ORDER BY date"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def alerts():
    """All historical alerts from alerts_history.db."""
    db = ROOT / "data/alerts_history.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM alerts ORDER BY timestamp").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def forward_return_intraday(bars, idx, direction, offsets=None):
    """
    Forward returns from 15-min bars.
    Returns dict like {'15m': +0.12, '1h': -0.05, ...}
    """
    offsets = offsets or {"15m": 1, "30m": 2, "1h": 4, "2h": 8, "4h": 16}
    entry = bars[idx]["close"]
    out = {}
    for label, off in offsets.items():
        ti = idx + off
        if ti < len(bars):
            ep = bars[ti]["close"]
            pnl = ((ep - entry) / entry * 100) if direction == "LONG" else ((entry - ep) / entry * 100)
            out[label] = round(pnl, 4)
    return out


def forward_return_daily(daily, idx, direction, offsets=None):
    """Forward returns from daily bars (close-only)."""
    offsets = offsets or {"1d": 1, "2d": 2, "3d": 3, "5d": 5}
    c = daily[idx].get("Close") or daily[idx].get("close", 0)
    if not c:
        return {}
    out = {}
    for label, off in offsets.items():
        ti = idx + off
        if ti < len(daily):
            ep = daily[ti].get("Close") or daily[ti].get("close", 0)
            if ep:
                pnl = ((ep - c) / c * 100) if direction == "LONG" else ((c - ep) / c * 100)
                out[label] = round(pnl, 4)
    return out


def score(label, pnls):
    """Print win rate and avg P&L for a list of pnl values."""
    if not pnls:
        print(f"  {label}: NO DATA")
        return 0, 0
    wins = sum(1 for p in pnls if p > 0)
    wr = wins / len(pnls) * 100
    avg = sum(pnls) / len(pnls)
    cum = sum(pnls)
    print(f"  {label}: n={len(pnls):3d} | WR={wr:.0f}% | avg={avg:+.4f}% | cum={cum:+.2f}%")
    return wr, avg


if __name__ == "__main__":
    print("DATA INVENTORY:")
    b = bars_15min()
    print(f"  15-min bars: {len(b)} | {b[0]['timestamp'][:10]} → {b[-1]['timestamp'][:10]}")
    d = bars_daily()
    print(f"  Daily bars:  {len(d)} | {d[0].get('date',d[0].get('Date',''))[:10]} → {d[-1].get('date',d[-1].get('Date',''))[:10]}")
    print(f"  DP interactions: {len(dp_interactions())}")
    print(f"  DP snapshots:    {len(dp_snapshots())}")
    print(f"  Alerts:          {len(alerts())}")
