"""
📊 DP TREND ANALYZER — Multi-Day Dark Pool Intelligence
Sprint 2.1: 5-day cumulative, 20-day rolling, acceleration detection.

Consumes daily DP data from Stockgrid and persists snapshots for cross-session trend analysis.
"""

import sqlite3
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DPTrendAnalyzer:
    """
    Analyzes multi-day dark pool accumulation/distribution trends.
    Uses Stockgrid daily data to compute:
    - 5-day cumulative DP position
    - 20-day rolling average
    - Acceleration (rate of change of DP position)
    - Price vs. DP divergence (accumulation while price drops)
    """

    def __init__(self, db_path: str = "data/dp_trends.db"):
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dp_daily_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                dp_position REAL,
                dollar_dp_position REAL,
                net_volume REAL,
                short_volume_pct REAL,
                price REAL,
                captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dp_trend_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                direction TEXT,
                strength REAL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def ingest_stockgrid_data(self, symbol: str, raw_data: dict) -> int:
        """
        Ingest raw Stockgrid data into daily snapshots.
        Returns number of new rows inserted.
        """
        dp_data = raw_data.get("individual_dark_pool_position_data", {})
        sv_data = raw_data.get("individual_short_volume", {})
        prices_data = raw_data.get("prices", {})

        dates = dp_data.get("dates", [])
        dp_positions = dp_data.get("dp_position", [])
        dollar_positions = dp_data.get("dollar_dp_position", [])
        net_volumes = sv_data.get("net_volume", [])
        short_pcts = sv_data.get("short_volume_pct", [])
        prices = prices_data.get("prices", [])
        price_dates = prices_data.get("dates", [])

        # Build price lookup by date
        price_map = {}
        for i, d in enumerate(price_dates):
            if i < len(prices):
                price_map[d] = prices[i]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        inserted = 0

        for i, date in enumerate(dates):
            dp_pos = dp_positions[i] if i < len(dp_positions) else None
            dollar_pos = dollar_positions[i] if i < len(dollar_positions) else None
            net_vol = net_volumes[i] if i < len(net_volumes) else None
            short_pct = short_pcts[i] if i < len(short_pcts) else None
            price = price_map.get(date)

            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO dp_daily_snapshots
                    (symbol, date, dp_position, dollar_dp_position, net_volume, short_volume_pct, price)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (symbol, date, dp_pos, dollar_pos, net_vol, short_pct, price))
                if cursor.rowcount > 0:
                    inserted += 1
            except Exception as e:
                logger.warning(f"Failed to insert snapshot for {symbol} {date}: {e}")

        conn.commit()
        conn.close()
        logger.info(f"Ingested {inserted} new daily snapshots for {symbol} (total dates: {len(dates)})")
        return inserted

    def analyze(self, symbol: str) -> Dict:
        """
        Run multi-day DP analysis on stored snapshots.
        Returns trend metrics + signals.
        """
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT date, dp_position, dollar_dp_position, net_volume, short_volume_pct, price
            FROM dp_daily_snapshots
            WHERE symbol = ?
            ORDER BY date ASC
        """, (symbol,)).fetchall()
        conn.close()

        if len(rows) < 5:
            return {
                "symbol": symbol,
                "has_data": False,
                "error": f"Need 5+ days, have {len(rows)}",
                "days_available": len(rows),
            }

        dates = [r[0] for r in rows]
        dp_positions = [r[1] or 0 for r in rows]
        dollar_positions = [r[2] or 0 for r in rows]
        net_volumes = [r[3] or 0 for r in rows]
        short_pcts = [r[4] or 50 for r in rows]
        prices = [r[5] or 0 for r in rows]

        # 5-day cumulative
        cum_5d = sum(dp_positions[-5:])
        cum_5d_dollar = sum(dollar_positions[-5:])

        # 20-day rolling average (or all available if < 20)
        window = min(20, len(dp_positions))
        avg_20d = sum(dp_positions[-window:]) / window
        avg_20d_dollar = sum(dollar_positions[-window:]) / window

        # Acceleration: 5-day slope vs previous 5-day slope
        if len(dp_positions) >= 10:
            prev_5d = sum(dp_positions[-10:-5])
            acceleration = cum_5d - prev_5d
        else:
            acceleration = 0

        # Short volume trend
        avg_short_pct_5d = sum(short_pcts[-5:]) / 5
        avg_short_pct_20d = sum(short_pcts[-window:]) / window

        # Price trend
        price_change_5d = (prices[-1] - prices[-5]) / prices[-5] * 100 if prices[-5] else 0
        price_change_20d = (prices[-1] - prices[-window]) / prices[-window] * 100 if prices[-window] else 0

        # Divergence detection: DP accumulation while price drops
        dp_accumulating = cum_5d > 0
        price_dropping = price_change_5d < -0.5
        divergence = dp_accumulating and price_dropping

        dp_distributing = cum_5d < 0
        price_rising = price_change_5d > 0.5
        reverse_divergence = dp_distributing and price_rising

        # Signals
        signals = []
        if divergence:
            signals.append({
                "type": "DP_ACCUMULATION_DIVERGENCE",
                "direction": "BULLISH",
                "strength": abs(cum_5d) / (abs(avg_20d) + 1),
                "detail": f"DP accumulating ({cum_5d:+,.0f}) while price down {price_change_5d:.1f}%",
            })
        if reverse_divergence:
            signals.append({
                "type": "DP_DISTRIBUTION_DIVERGENCE",
                "direction": "BEARISH",
                "strength": abs(cum_5d) / (abs(avg_20d) + 1),
                "detail": f"DP distributing ({cum_5d:+,.0f}) while price up {price_change_5d:.1f}%",
            })
        if abs(acceleration) > abs(avg_20d) * 0.5:
            signals.append({
                "type": "DP_ACCELERATION",
                "direction": "BULLISH" if acceleration > 0 else "BEARISH",
                "strength": abs(acceleration) / (abs(avg_20d) + 1),
                "detail": f"DP acceleration {acceleration:+,.0f} (strong shift from prior 5d)",
            })

        # Persist signals
        if signals:
            self._persist_signals(symbol, dates[-1], signals)

        return {
            "symbol": symbol,
            "has_data": True,
            "days_available": len(rows),
            "latest_date": dates[-1],
            "cumulative_5d": cum_5d,
            "cumulative_5d_dollar": cum_5d_dollar,
            "rolling_avg_20d": avg_20d,
            "rolling_avg_20d_dollar": avg_20d_dollar,
            "acceleration": acceleration,
            "short_volume_pct_5d": round(avg_short_pct_5d, 1),
            "short_volume_pct_20d": round(avg_short_pct_20d, 1),
            "price_change_5d_pct": round(price_change_5d, 2),
            "price_change_20d_pct": round(price_change_20d, 2),
            "has_divergence": divergence,
            "has_reverse_divergence": reverse_divergence,
            "signals": signals,
            "current_price": prices[-1],
            "latest_dp_position": dp_positions[-1],
        }

    def _persist_signals(self, symbol: str, date: str, signals: List[Dict]):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for sig in signals:
            cursor.execute("""
                INSERT INTO dp_trend_signals (symbol, date, signal_type, direction, strength, details)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (symbol, date, sig["type"], sig["direction"], sig["strength"], sig["detail"]))
        conn.commit()
        conn.close()

    def get_trend_history(self, symbol: str, days: int = 20) -> List[Dict]:
        """Get daily snapshot history for chart display."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT date, dp_position, dollar_dp_position, net_volume, short_volume_pct, price
            FROM dp_daily_snapshots
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT ?
        """, (symbol, days)).fetchall()
        conn.close()

        return [
            {
                "date": r[0],
                "dp_position": r[1],
                "dollar_dp_position": r[2],
                "net_volume": r[3],
                "short_volume_pct": r[4],
                "price": r[5],
            }
            for r in reversed(rows)
        ]
