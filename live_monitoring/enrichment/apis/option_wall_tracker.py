#!/usr/bin/env python3
"""
🧱 Option Wall Tracker — Snapshots AXLFI option walls daily for SPY/QQQ/IWM.

Tracks call wall / put wall / POC levels and alerts when price breaches walls.
Wall breaches = institutional gamma hedging flows that move markets.

Author: Zo (Alpha's AI)
"""

import os
import json
import time
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)


class OptionWallTracker:
    """Snapshot and track option wall levels from AXLFI."""

    def __init__(self, symbols=None, log_dir: str = "/tmp/option_walls"):
        self.symbols = symbols or ["SPY", "QQQ", "IWM"]
        os.makedirs(log_dir, exist_ok=True)
        self.log_dir = log_dir
        self._latest = {}

    def capture_walls(self):
        """Fetch current option walls for tracked symbols."""
        try:
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
            client = StockgridClient(cache_ttl=300)

            results = {}
            for symbol in self.symbols:
                try:
                    walls = client.get_option_walls_today(symbol)
                    if walls:
                        entry = {
                            "call_wall": getattr(walls, "call_wall", None),
                            "put_wall": getattr(walls, "put_wall", None),
                            "poc": getattr(walls, "poc", None),
                        }
                    else:
                        # Fallback: try raw API
                        raw = client.get_option_walls(symbol)
                        if raw:
                            walls_dict = raw.get("option_walls", {})
                            today_str = date.today().isoformat()
                            # Get most recent date
                            dates = sorted(walls_dict.keys(), reverse=True)
                            if dates:
                                latest_date = dates[0]
                                w = walls_dict[latest_date]
                                entry = {
                                    "call_wall": w.get("call_wall"),
                                    "put_wall": w.get("put_wall"),
                                    "poc": w.get("poc"),
                                    "date": latest_date,
                                }
                            else:
                                entry = None
                        else:
                            entry = None

                    if entry:
                        results[symbol] = entry
                        logger.info(
                            f"🧱 {symbol} walls: Call=${entry.get('call_wall')} "
                            f"Put=${entry.get('put_wall')} POC=${entry.get('poc')}"
                        )
                    else:
                        logger.warning(f"⚠️ No option wall data for {symbol}")

                except Exception as e:
                    logger.error(f"❌ Wall fetch failed for {symbol}: {e}")

            # Check for wall breaches
            self._check_breaches(results)

            # Save snapshot
            snapshot = {
                "timestamp": datetime.utcnow().isoformat(),
                "walls": results,
            }

            path = os.path.join(self.log_dir, f"walls_{date.today().isoformat()}.json")
            with open(path, "w") as f:
                json.dump(snapshot, f, indent=2)

            self._latest = snapshot
            return snapshot

        except Exception as e:
            logger.error(f"❌ Option wall capture failed: {e}")
            return None

    def _check_breaches(self, walls: dict):
        """Check if current price has breached any walls."""
        try:
            import yfinance as yf

            for symbol, wall_data in walls.items():
                call_wall = wall_data.get("call_wall")
                put_wall = wall_data.get("put_wall")
                if not call_wall or not put_wall:
                    continue

                ticker = yf.Ticker(symbol)
                price = ticker.history(period="1d")["Close"].iloc[-1]

                if price > call_wall:
                    gap = price - call_wall
                    logger.warning(
                        f"🚨 {symbol} ABOVE CALL WALL: ${price:.2f} > ${call_wall} "
                        f"(+${gap:.2f} above — gamma squeeze territory)"
                    )
                    wall_data["breach"] = f"ABOVE_CALL (+${gap:.2f})"
                elif price < put_wall:
                    gap = put_wall - price
                    logger.warning(
                        f"🚨 {symbol} BELOW PUT WALL: ${price:.2f} < ${put_wall} "
                        f"(-${gap:.2f} below — dealer hedging territory)"
                    )
                    wall_data["breach"] = f"BELOW_PUT (-${gap:.2f})"
                else:
                    wall_data["breach"] = None
                    wall_data["position"] = f"Between walls (${put_wall} - ${call_wall})"

                wall_data["current_price"] = round(float(price), 2)

        except Exception as e:
            logger.debug(f"Breach check skipped: {e}")

    def get_latest(self):
        """Get latest wall data for API."""
        if self._latest:
            return self._latest

        today_path = os.path.join(self.log_dir, f"walls_{date.today().isoformat()}.json")
        try:
            if os.path.exists(today_path):
                with open(today_path) as f:
                    return json.load(f)
        except Exception:
            pass
        return {"walls": {}, "timestamp": None}

    def run_continuous(self, interval_minutes: int = 30):
        """Check walls periodically during market hours."""
        logger.info(f"🧱 Option Wall Tracker started (interval: {interval_minutes}m)")
        while True:
            try:
                now = datetime.now()
                if 9 <= now.hour <= 16:
                    self.capture_walls()
                else:
                    logger.debug("Outside market hours, skipping wall check")
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Wall tracker loop error: {e}")
                time.sleep(120)
