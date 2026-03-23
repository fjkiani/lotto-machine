"""
📊 SIGNAL OUTCOME TRACKER — The Missing Feedback Loop

Every signal that passes the Gate gets tracked here:
1. Record entry price, direction, stop, target
2. Poll price at +5m, +15m, +30m, +1hr
3. Determine outcome: WIN / LOSS / SCRATCH
4. Persist to signal_outcomes.db
5. Expose win rates by checker via API

Without this, we're flying blind — signals fire and disappear into the void.
"""

import os
import sqlite3
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "signal_outcomes_tracker.db"
)


@dataclass
class TrackedSignal:
    """A signal being tracked for outcome."""
    signal_id: str
    symbol: str
    direction: str          # LONG or SHORT
    entry_price: float
    stop_pct: float         # e.g., 0.20 for 0.20%
    target_pct: float       # e.g., 0.30 for 0.30%
    confidence: float
    source: str             # checker name
    regime: str
    bias: str
    sizing: float
    entry_time: str         # ISO timestamp


class SignalOutcomeTracker:
    """
    Tracks signal outcomes for win rate analysis.

    Usage:
        tracker = SignalOutcomeTracker()
        tracker.record_entry(signal_id, symbol, "LONG", 662.29, ...)
        # Background thread polls price and records outcomes
        stats = tracker.get_win_rates()
    """

    def __init__(self, db_path: str = None, poll_interval: int = 300):
        self.db_path = db_path or DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.poll_interval = poll_interval  # seconds between price checks
        self._init_db()
        self._active_signals: List[TrackedSignal] = []
        self._lock = threading.Lock()
        self._poll_thread = None
        self._running = False

    def _init_db(self):
        """Create outcome tracking tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_pct REAL,
                target_pct REAL,
                confidence REAL,
                source TEXT,
                regime TEXT,
                bias TEXT,
                sizing REAL,
                entry_time TEXT NOT NULL,
                -- Price snapshots
                price_5min REAL,
                price_15min REAL,
                price_30min REAL,
                price_60min REAL,
                -- Outcome
                outcome TEXT DEFAULT 'PENDING',
                outcome_time TEXT,
                exit_price REAL,
                pnl_pct REAL,
                max_favorable REAL,
                max_adverse REAL,
                -- Metadata
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        # Indices — wrapped in case DB was created with a different schema
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_outcomes_source ON signal_outcomes(source)",
            "CREATE INDEX IF NOT EXISTS idx_outcomes_symbol ON signal_outcomes(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_outcomes_outcome ON signal_outcomes(outcome)",
        ]:
            try:
                cursor.execute(idx_sql)
            except Exception:
                pass
        conn.commit()
        conn.close()
        logger.info(f"📊 Signal outcome tracker initialized: {self.db_path}")

    def record_entry(
        self,
        signal_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_pct: float = 0.20,
        target_pct: float = 0.30,
        confidence: float = 0.0,
        source: str = "",
        regime: str = "",
        bias: str = "",
        sizing: float = 1.0,
    ):
        """Record a signal entry for tracking."""
        entry_time = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR IGNORE INTO signal_outcomes
                (signal_id, symbol, direction, entry_price, stop_pct, target_pct,
                 confidence, source, regime, bias, sizing, entry_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (signal_id, symbol, direction, entry_price, stop_pct, target_pct,
                  confidence, source, regime, bias, sizing, entry_time))
            conn.commit()

            tracked = TrackedSignal(
                signal_id=signal_id, symbol=symbol, direction=direction,
                entry_price=entry_price, stop_pct=stop_pct, target_pct=target_pct,
                confidence=confidence, source=source, regime=regime,
                bias=bias, sizing=sizing, entry_time=entry_time
            )
            with self._lock:
                self._active_signals.append(tracked)

            logger.info(
                f"📊 TRACKING: {direction} {symbol} @ ${entry_price:.2f} "
                f"| stop={stop_pct:.2f}% target={target_pct:.2f}% "
                f"| source={source} | id={signal_id}"
            )
        except Exception as e:
            logger.error(f"Failed to record entry: {e}")
        finally:
            conn.close()

    def check_outcomes(self):
        """
        Check price for all pending signals and update outcomes.
        Called by background thread or scheduler.
        """
        conn = sqlite3.connect(self.db_path)
        pending = conn.execute(
            "SELECT signal_id, symbol, direction, entry_price, stop_pct, target_pct, entry_time "
            "FROM signal_outcomes WHERE outcome = 'PENDING'"
        ).fetchall()
        conn.close()

        if not pending:
            return

        logger.info(f"📊 Checking outcomes for {len(pending)} pending signals...")

        for row in pending:
            sig_id, symbol, direction, entry_price, stop_pct, target_pct, entry_time = row

            try:
                current_price = self._get_current_price(symbol)
                if current_price is None:
                    continue

                # Calculate move from entry
                if direction == "LONG":
                    move_pct = (current_price - entry_price) / entry_price * 100
                else:  # SHORT
                    move_pct = (entry_price - current_price) / entry_price * 100

                # Determine time since entry
                entry_dt = datetime.fromisoformat(entry_time)
                elapsed = datetime.now() - entry_dt
                elapsed_min = elapsed.total_seconds() / 60

                # Update price snapshots
                self._update_price_snapshot(sig_id, current_price, elapsed_min)

                # Check outcome
                outcome = None
                if move_pct >= target_pct:
                    outcome = "WIN"
                elif move_pct <= -stop_pct:
                    outcome = "LOSS"
                elif elapsed_min >= 60:
                    # Time-based exit after 1 hour
                    if move_pct > 0:
                        outcome = "WIN"
                    elif move_pct < -0.05:
                        outcome = "LOSS"
                    else:
                        outcome = "SCRATCH"

                if outcome:
                    self._record_outcome(
                        sig_id, outcome, current_price, move_pct
                    )
                    logger.info(
                        f"📊 OUTCOME: {outcome} | {direction} {symbol} "
                        f"| entry=${entry_price:.2f} exit=${current_price:.2f} "
                        f"| pnl={move_pct:+.2f}%"
                    )

            except Exception as e:
                logger.error(f"Error checking outcome for {sig_id}: {e}")

    def _update_price_snapshot(self, signal_id: str, price: float, elapsed_min: float):
        """Update price snapshot columns based on elapsed time."""
        conn = sqlite3.connect(self.db_path)
        try:
            if 4 <= elapsed_min < 10:
                conn.execute(
                    "UPDATE signal_outcomes SET price_5min = ? WHERE signal_id = ? AND price_5min IS NULL",
                    (price, signal_id)
                )
            elif 14 <= elapsed_min < 20:
                conn.execute(
                    "UPDATE signal_outcomes SET price_15min = ? WHERE signal_id = ? AND price_15min IS NULL",
                    (price, signal_id)
                )
            elif 29 <= elapsed_min < 35:
                conn.execute(
                    "UPDATE signal_outcomes SET price_30min = ? WHERE signal_id = ? AND price_30min IS NULL",
                    (price, signal_id)
                )
            elif 59 <= elapsed_min < 65:
                conn.execute(
                    "UPDATE signal_outcomes SET price_60min = ? WHERE signal_id = ? AND price_60min IS NULL",
                    (price, signal_id)
                )

            # Update max favorable / adverse excursion
            row = conn.execute(
                "SELECT direction, entry_price, max_favorable, max_adverse FROM signal_outcomes WHERE signal_id = ?",
                (signal_id,)
            ).fetchone()
            if row:
                direction, entry, max_fav, max_adv = row
                if direction == "LONG":
                    move = (price - entry) / entry * 100
                else:
                    move = (entry - price) / entry * 100

                new_fav = max(max_fav or 0, move)
                new_adv = min(max_adv or 0, move)
                conn.execute(
                    "UPDATE signal_outcomes SET max_favorable = ?, max_adverse = ? WHERE signal_id = ?",
                    (new_fav, new_adv, signal_id)
                )

            conn.commit()
        finally:
            conn.close()

    def _record_outcome(self, signal_id: str, outcome: str, exit_price: float, pnl_pct: float):
        """Record final outcome."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE signal_outcomes SET outcome = ?, outcome_time = ?, exit_price = ?, pnl_pct = ? "
                "WHERE signal_id = ?",
                (outcome, datetime.now().isoformat(), exit_price, pnl_pct, signal_id)
            )
            conn.commit()
        finally:
            conn.close()

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='1m')
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        except Exception as e:
            logger.warning(f"Price fetch failed for {symbol}: {e}")
        return None

    # ── Win Rate Statistics ──────────────────────────────────────────

    def get_win_rates(self) -> Dict:
        """Get win rates by source (checker)."""
        conn = sqlite3.connect(self.db_path)
        try:
            # Overall stats
            total = conn.execute(
                "SELECT COUNT(*) FROM signal_outcomes WHERE outcome != 'PENDING'"
            ).fetchone()[0]
            wins = conn.execute(
                "SELECT COUNT(*) FROM signal_outcomes WHERE outcome = 'WIN'"
            ).fetchone()[0]
            losses = conn.execute(
                "SELECT COUNT(*) FROM signal_outcomes WHERE outcome = 'LOSS'"
            ).fetchone()[0]
            scratches = conn.execute(
                "SELECT COUNT(*) FROM signal_outcomes WHERE outcome = 'SCRATCH'"
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM signal_outcomes WHERE outcome = 'PENDING'"
            ).fetchone()[0]

            avg_pnl = conn.execute(
                "SELECT AVG(pnl_pct) FROM signal_outcomes WHERE outcome != 'PENDING' AND pnl_pct IS NOT NULL"
            ).fetchone()[0] or 0

            # By source
            by_source = {}
            rows = conn.execute("""
                SELECT source,
                       COUNT(*) as total,
                       SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
                       AVG(CASE WHEN pnl_pct IS NOT NULL THEN pnl_pct ELSE NULL END) as avg_pnl,
                       SUM(CASE WHEN outcome = 'PENDING' THEN 1 ELSE 0 END) as pending
                FROM signal_outcomes
                GROUP BY source
            """).fetchall()
            for r in rows:
                completed = r[1] - r[5]
                by_source[r[0]] = {
                    "total": r[1],
                    "wins": r[2],
                    "losses": r[3],
                    "win_rate": (r[2] / completed * 100) if completed > 0 else 0,
                    "avg_pnl": r[4] or 0,
                    "pending": r[5],
                }

            # By regime
            by_regime = {}
            rows = conn.execute("""
                SELECT regime,
                       COUNT(*) as total,
                       SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                       AVG(CASE WHEN pnl_pct IS NOT NULL THEN pnl_pct ELSE NULL END) as avg_pnl
                FROM signal_outcomes
                WHERE outcome != 'PENDING' AND regime != ''
                GROUP BY regime
            """).fetchall()
            for r in rows:
                by_regime[r[0]] = {
                    "total": r[1],
                    "wins": r[2],
                    "win_rate": (r[2] / r[1] * 100) if r[1] > 0 else 0,
                    "avg_pnl": r[3] or 0,
                }

            return {
                "total_tracked": total + pending,
                "completed": total,
                "pending": pending,
                "wins": wins,
                "losses": losses,
                "scratches": scratches,
                "win_rate": (wins / total * 100) if total > 0 else 0,
                "avg_pnl_pct": round(avg_pnl, 4),
                "by_source": by_source,
                "by_regime": by_regime,
            }
        finally:
            conn.close()

    def get_recent_outcomes(self, limit: int = 20) -> List[Dict]:
        """Get recent signal outcomes for display."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute("""
                SELECT signal_id, symbol, direction, entry_price, exit_price,
                       pnl_pct, outcome, source, regime, confidence,
                       entry_time, outcome_time, max_favorable, max_adverse
                FROM signal_outcomes
                ORDER BY entry_time DESC
                LIMIT ?
            """, (limit,)).fetchall()

            return [
                {
                    "signal_id": r[0],
                    "symbol": r[1],
                    "direction": r[2],
                    "entry_price": r[3],
                    "exit_price": r[4],
                    "pnl_pct": r[5],
                    "outcome": r[6],
                    "source": r[7],
                    "regime": r[8],
                    "confidence": r[9],
                    "entry_time": r[10],
                    "outcome_time": r[11],
                    "max_favorable": r[12],
                    "max_adverse": r[13],
                }
                for r in rows
            ]
        finally:
            conn.close()

    # ── Background Poll Loop ─────────────────────────────────────────

    def start_background_poll(self):
        """Start background thread to poll outcomes."""
        if self._poll_thread and self._poll_thread.is_alive():
            return

        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="OutcomeTracker"
        )
        self._poll_thread.start()
        logger.info("📊 Signal outcome tracker background poll started")

    def _poll_loop(self):
        """Background loop to check outcomes."""
        while self._running:
            try:
                self.check_outcomes()
            except Exception as e:
                logger.error(f"Outcome poll error: {e}")
            time.sleep(self.poll_interval)

    def stop(self):
        """Stop background polling."""
        self._running = False
