"""
📊 SIGNAL OUTCOME TRACKER

Tracks whether signals hit their target, stopped out, or expired.
Runs periodically to check active signals against current prices.

Schema:
  signal_outcomes (
    id INTEGER PRIMARY KEY,
    signal_id TEXT,           -- "alert_421" etc.
    symbol TEXT,
    action TEXT,              -- LONG / SHORT / WATCH
    entry_price REAL,
    target_price REAL,
    stop_price REAL,
    opened_at TEXT,           -- when signal fired
    closed_at TEXT,           -- when outcome determined
    outcome TEXT,             -- TARGET_HIT / STOPPED_OUT / EXPIRED / ACTIVE
    actual_close_price REAL,  -- price when closed
    pnl_pct REAL,            -- realized P&L percentage
    max_favorable REAL,      -- max favorable excursion (MFE)
    max_adverse REAL,         -- max adverse excursion (MAE)
    duration_hours REAL       -- how long signal was active
  )
"""

import sqlite3
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path("data/signal_outcomes.db")

def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signal_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id TEXT UNIQUE,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            entry_price REAL NOT NULL,
            target_price REAL NOT NULL,
            stop_price REAL NOT NULL,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            outcome TEXT DEFAULT 'ACTIVE',
            actual_close_price REAL,
            pnl_pct REAL DEFAULT 0,
            max_favorable REAL DEFAULT 0,
            max_adverse REAL DEFAULT 0,
            duration_hours REAL DEFAULT 0,
            reasoning TEXT DEFAULT ''
        )
    """)
    conn.commit()
    return conn


def register_signal(signal_id: str, symbol: str, action: str,
                     entry_price: float, target_price: float, stop_price: float,
                     timestamp: str, reasoning: str = "") -> bool:
    """Register a new signal for outcome tracking. Returns True if newly registered."""
    if action == "WATCH":
        return False  # Don't track WATCH signals

    conn = _get_conn()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO signal_outcomes
            (signal_id, symbol, action, entry_price, target_price, stop_price, opened_at, reasoning)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (signal_id, symbol, action, entry_price, target_price, stop_price, timestamp, reasoning))
        conn.commit()
        return conn.total_changes > 0
    except Exception as e:
        logger.error(f"Failed to register signal {signal_id}: {e}")
        return False
    finally:
        conn.close()


def check_outcomes() -> dict:
    """Check all ACTIVE signals against current prices. Returns summary of changes."""
    try:
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance not available"}

    conn = _get_conn()
    active = conn.execute(
        "SELECT * FROM signal_outcomes WHERE outcome = 'ACTIVE'"
    ).fetchall()

    if not active:
        conn.close()
        return {"checked": 0, "changes": []}

    changes = []
    now = datetime.now()

    # Batch fetch prices for all unique symbols
    symbols = list(set(row['symbol'] for row in active))
    prices = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            price = ticker.fast_info.last_price
            if price and price > 0:
                prices[sym] = price
        except Exception:
            pass

    for row in active:
        signal_id = row['signal_id']
        sym = row['symbol']
        current_price = prices.get(sym)

        if not current_price:
            continue

        entry = row['entry_price']
        target = row['target_price']
        stop = row['stop_price']
        action = row['action']
        opened_at = datetime.fromisoformat(row['opened_at'])
        hours_active = (now - opened_at).total_seconds() / 3600

        # Calculate MFE/MAE
        if action == "LONG":
            favorable = max(0, (current_price - entry) / entry * 100)
            adverse = max(0, (entry - current_price) / entry * 100)
        else:  # SHORT
            favorable = max(0, (entry - current_price) / entry * 100)
            adverse = max(0, (current_price - entry) / entry * 100)

        # Update running MFE/MAE
        mfe = max(row['max_favorable'], favorable)
        mae = max(row['max_adverse'], adverse)

        # Check outcome
        outcome = "ACTIVE"
        close_price = None
        pnl = 0

        if action == "LONG":
            if current_price >= target:
                outcome = "TARGET_HIT"
                close_price = current_price
                pnl = round((current_price - entry) / entry * 100, 2)
            elif current_price <= stop:
                outcome = "STOPPED_OUT"
                close_price = current_price
                pnl = round((current_price - entry) / entry * 100, 2)
        elif action == "SHORT":
            if current_price <= target:
                outcome = "TARGET_HIT"
                close_price = current_price
                pnl = round((entry - current_price) / entry * 100, 2)
            elif current_price >= stop:
                outcome = "STOPPED_OUT"
                close_price = current_price
                pnl = round((entry - current_price) / entry * 100, 2)

        # Expire after 48 hours if no hit
        if outcome == "ACTIVE" and hours_active > 48:
            outcome = "EXPIRED"
            close_price = current_price
            if action == "LONG":
                pnl = round((current_price - entry) / entry * 100, 2)
            else:
                pnl = round((entry - current_price) / entry * 100, 2)

        # Update DB
        if outcome != "ACTIVE":
            conn.execute("""
                UPDATE signal_outcomes
                SET outcome = ?, closed_at = ?, actual_close_price = ?,
                    pnl_pct = ?, max_favorable = ?, max_adverse = ?,
                    duration_hours = ?
                WHERE signal_id = ?
            """, (outcome, now.isoformat(), close_price, pnl, mfe, mae,
                  round(hours_active, 1), signal_id))
            changes.append({
                "signal_id": signal_id, "symbol": sym,
                "outcome": outcome, "pnl_pct": pnl
            })
        else:
            conn.execute("""
                UPDATE signal_outcomes
                SET max_favorable = ?, max_adverse = ?, duration_hours = ?
                WHERE signal_id = ?
            """, (mfe, mae, round(hours_active, 1), signal_id))

    conn.commit()
    conn.close()

    return {"checked": len(active), "changes": changes}


def get_scorecard() -> dict:
    """Get P&L scorecard summary for the frontend."""
    conn = _get_conn()

    all_closed = conn.execute(
        "SELECT * FROM signal_outcomes WHERE outcome != 'ACTIVE'"
    ).fetchall()

    all_active = conn.execute(
        "SELECT * FROM signal_outcomes WHERE outcome = 'ACTIVE'"
    ).fetchall()

    conn.close()

    if not all_closed and not all_active:
        return {
            "total_signals": 0, "active": 0, "closed": 0,
            "wins": 0, "losses": 0, "expired": 0,
            "win_rate": 0, "avg_win_pct": 0, "avg_loss_pct": 0,
            "total_pnl_pct": 0, "profit_factor": 0,
            "best_trade": None, "worst_trade": None,
            "recent_trades": []
        }

    wins = [r for r in all_closed if r['outcome'] == 'TARGET_HIT']
    losses = [r for r in all_closed if r['outcome'] == 'STOPPED_OUT']
    expired = [r for r in all_closed if r['outcome'] == 'EXPIRED']

    total_closed = len(all_closed)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = round(win_count / total_closed * 100, 1) if total_closed > 0 else 0

    avg_win = round(sum(r['pnl_pct'] for r in wins) / win_count, 2) if wins else 0
    avg_loss = round(sum(r['pnl_pct'] for r in losses) / loss_count, 2) if losses else 0

    total_pnl = round(sum(r['pnl_pct'] for r in all_closed), 2)
    gross_wins = sum(r['pnl_pct'] for r in wins) if wins else 0
    gross_losses = abs(sum(r['pnl_pct'] for r in losses)) if losses else 0
    profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else float('inf')

    best = max(all_closed, key=lambda r: r['pnl_pct']) if all_closed else None
    worst = min(all_closed, key=lambda r: r['pnl_pct']) if all_closed else None

    def _trade_summary(row):
        return {
            "signal_id": row['signal_id'], "symbol": row['symbol'],
            "action": row['action'], "outcome": row['outcome'],
            "pnl_pct": row['pnl_pct'], "duration_hours": row['duration_hours'],
            "entry_price": row['entry_price'], "close_price": row['actual_close_price'],
            "opened_at": row['opened_at'], "closed_at": row['closed_at']
        }

    recent = sorted(all_closed, key=lambda r: r['closed_at'] or '', reverse=True)[:10]

    return {
        "total_signals": len(all_closed) + len(all_active),
        "active": len(all_active),
        "closed": total_closed,
        "wins": win_count,
        "losses": loss_count,
        "expired": len(expired),
        "win_rate": win_rate,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "total_pnl_pct": total_pnl,
        "profit_factor": profit_factor,
        "best_trade": _trade_summary(best) if best else None,
        "worst_trade": _trade_summary(worst) if worst else None,
        "recent_trades": [_trade_summary(r) for r in recent]
    }
""", "Complexity": 8, "Description": "Signal outcome tracker — registers directional signals, checks outcomes (target hit / stopped out / expired), tracks MFE/MAE, and generates P&L scorecards.", "EmptyFile": false, "IsArtifact": false, "Overwrite": false, "TargetFile": "/Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main/live_monitoring/core/signal_outcome_tracker.py"}
