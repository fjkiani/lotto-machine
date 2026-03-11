"""
🏆 ALERT OUTCOME TRACKER — Win Rate Computation
Sprint 3.3: Track alert_price vs. price 1h/4h/1d later.

Populates checker_win_rates table in checker_health.db.
"""

import sqlite3
import os
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertOutcomeTracker:
    """
    Tracks directional alert outcomes by comparing alert price
    to actual price after 1h/4h/1d.

    Uses checker_alerts + yfinance to compute:
    - Was the alert direction correct?
    - What was the actual move?
    - Per-checker win rate over time
    """

    def __init__(self, health_db: str = "data/checker_health.db"):
        self.health_db = health_db
        self._init_db()

    def _init_db(self):
        if not os.path.exists(self.health_db):
            return
        conn = sqlite3.connect(self.health_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER,
                checker_name TEXT NOT NULL,
                symbol TEXT,
                direction TEXT,
                alert_price REAL,
                alert_time TEXT,
                price_1h REAL,
                price_4h REAL,
                price_1d REAL,
                move_1h_pct REAL,
                move_4h_pct REAL,
                move_1d_pct REAL,
                correct_1h INTEGER,
                correct_4h INTEGER,
                correct_1d INTEGER,
                tracked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(alert_id, checker_name)
            )
        """)
        conn.commit()
        conn.close()

    def track_alert(self, alert_id: int, checker_name: str, symbol: str,
                    direction: str, alert_price: float, alert_time: str) -> bool:
        """
        Register an alert for outcome tracking.
        The compute_outcomes() method later fills in actual prices.
        """
        conn = sqlite3.connect(self.health_db)
        try:
            conn.execute("""
                INSERT OR IGNORE INTO alert_outcomes
                (alert_id, checker_name, symbol, direction, alert_price, alert_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (alert_id, checker_name, symbol, direction, alert_price, alert_time))
            conn.commit()
            return True
        except Exception as e:
            logger.warning(f"Failed to track alert {alert_id}: {e}")
            return False
        finally:
            conn.close()

    def compute_outcomes(self) -> Dict:
        """
        For tracked alerts older than 1 day without outcomes,
        fetch actual prices and compute win rates.
        """
        conn = sqlite3.connect(self.health_db)
        pending = conn.execute("""
            SELECT id, symbol, direction, alert_price, alert_time
            FROM alert_outcomes
            WHERE price_1d IS NULL
            AND datetime(alert_time) < datetime('now', '-1 day')
            ORDER BY alert_time ASC
            LIMIT 20
        """).fetchall()

        if not pending:
            conn.close()
            return {"processed": 0, "message": "No pending alerts to track"}

        try:
            import yfinance as yf
        except ImportError:
            conn.close()
            return {"processed": 0, "error": "yfinance not installed"}

        processed = 0
        for row_id, symbol, direction, alert_price, alert_time in pending:
            if not symbol or not alert_price:
                continue

            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d")
                if hist.empty:
                    continue

                current_price = float(hist['Close'].iloc[-1])
                move_pct = (current_price - alert_price) / alert_price * 100

                # Was the direction correct?
                correct = False
                if direction in ("LONG", "BUY", "BULLISH") and move_pct > 0:
                    correct = True
                elif direction in ("SHORT", "SELL", "BEARISH") and move_pct < 0:
                    correct = True

                conn.execute("""
                    UPDATE alert_outcomes
                    SET price_1d = ?, move_1d_pct = ?, correct_1d = ?,
                        tracked_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (current_price, round(move_pct, 2), 1 if correct else 0, row_id))
                processed += 1

            except Exception as e:
                logger.warning(f"Failed to track outcome for {symbol}: {e}")
                continue

        conn.commit()
        conn.close()

        # Update win rates
        self._update_win_rates()

        return {"processed": processed, "pending_remaining": len(pending) - processed}

    def _update_win_rates(self):
        """Compute per-checker win rates and update checker_win_rates table."""
        conn = sqlite3.connect(self.health_db)

        checkers = conn.execute("""
            SELECT checker_name, COUNT(*) as total,
                   SUM(CASE WHEN correct_1d = 1 THEN 1 ELSE 0 END) as wins
            FROM alert_outcomes
            WHERE correct_1d IS NOT NULL
            GROUP BY checker_name
        """).fetchall()

        today = datetime.utcnow().strftime('%Y-%m-%d')

        for checker_name, total, wins in checkers:
            win_rate = (wins / total * 100) if total > 0 else 0
            conn.execute("""
                INSERT OR REPLACE INTO checker_win_rates
                (checker_name, date, win_rate, total_trades)
                VALUES (?, ?, ?, ?)
            """, (checker_name, today, round(win_rate, 1), total))

        conn.commit()
        conn.close()
        logger.info(f"Updated win rates for {len(checkers)} checkers")

    def get_stats(self) -> Dict:
        """Get tracker statistics."""
        if not os.path.exists(self.health_db):
            return {"has_data": False}

        conn = sqlite3.connect(self.health_db)
        try:
            total = conn.execute("SELECT COUNT(*) FROM alert_outcomes").fetchone()[0]
            tracked = conn.execute(
                "SELECT COUNT(*) FROM alert_outcomes WHERE correct_1d IS NOT NULL"
            ).fetchone()[0]
            correct = conn.execute(
                "SELECT COUNT(*) FROM alert_outcomes WHERE correct_1d = 1"
            ).fetchone()[0]
        except:
            conn.close()
            return {"has_data": False, "error": "alert_outcomes table not found"}

        conn.close()

        return {
            "has_data": True,
            "total_tracked": total,
            "outcomes_computed": tracked,
            "correct": correct,
            "win_rate": round(correct / tracked * 100, 1) if tracked > 0 else None,
        }
