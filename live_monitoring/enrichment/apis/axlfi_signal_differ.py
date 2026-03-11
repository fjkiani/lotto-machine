#!/usr/bin/env python3
"""
📡 AXLFI Signal Differ — Snapshots AXLFI signal symbols daily, diffs against previous.

Detects when new tickers enter or exit the AXLFI bullish/bearish signal list.
New signals = potential emerging dark pool accumulation patterns.

Author: Zo (Alpha's AI)
"""

import os
import json
import time
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)


class AXLFISignalDiffer:
    """Diffs AXLFI signal symbols daily, logs additions/removals."""

    def __init__(self, log_dir: str = "/tmp/axlfi_signals"):
        os.makedirs(log_dir, exist_ok=True)
        self.log_dir = log_dir
        self._last_signals = {"bullish": [], "bearish": []}
        self._history = []
        self._load_latest()

    def _log_path(self, d: date = None):
        d = d or date.today()
        return os.path.join(self.log_dir, f"signals_{d.isoformat()}.json")

    def _load_latest(self):
        """Load the most recent snapshot for diffing."""
        try:
            files = sorted(f for f in os.listdir(self.log_dir) if f.startswith("signals_"))
            if files:
                with open(os.path.join(self.log_dir, files[-1])) as f:
                    data = json.load(f)
                self._last_signals = {
                    "bullish": data.get("bullish", []),
                    "bearish": data.get("bearish", []),
                }
        except Exception as e:
            logger.debug(f"No previous snapshot: {e}")

    def capture_and_diff(self):
        """Fetch current signals, diff against last, save snapshot."""
        try:
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
            client = StockgridClient(cache_ttl=60)
            signals = client.get_signal_symbols()

            bullish = sorted(s["symbol"] for s in signals if s.get("dir") == 1)
            bearish = sorted(s["symbol"] for s in signals if s.get("dir") == -1)

            # Diff
            prev_bull = set(self._last_signals.get("bullish", []))
            prev_bear = set(self._last_signals.get("bearish", []))
            new_bull = sorted(set(bullish) - prev_bull)
            removed_bull = sorted(prev_bull - set(bullish))
            new_bear = sorted(set(bearish) - prev_bear)
            removed_bear = sorted(prev_bear - set(bearish))

            snapshot = {
                "timestamp": datetime.utcnow().isoformat(),
                "bullish": bullish,
                "bearish": bearish,
                "diff": {
                    "new_bullish": new_bull,
                    "removed_bullish": removed_bull,
                    "new_bearish": new_bear,
                    "removed_bearish": removed_bear,
                },
            }

            # Save
            path = self._log_path()
            with open(path, "w") as f:
                json.dump(snapshot, f, indent=2)

            self._last_signals = {"bullish": bullish, "bearish": bearish}

            has_changes = bool(new_bull or removed_bull or new_bear or removed_bear)
            if has_changes:
                logger.warning(
                    f"📡 AXLFI SIGNAL CHANGE: +{len(new_bull)} bull, -{len(removed_bull)} bull, "
                    f"+{len(new_bear)} bear, -{len(removed_bear)} bear"
                )
            else:
                logger.info(f"📡 AXLFI signals unchanged: {len(bullish)} bull, {len(bearish)} bear")

            self._history.append(snapshot)
            return snapshot

        except Exception as e:
            logger.error(f"❌ AXLFI signal diff failed: {e}")
            return None

    def get_latest(self):
        """Get latest snapshot for API."""
        if self._history:
            return self._history[-1]
        try:
            path = self._log_path()
            if os.path.exists(path):
                with open(path) as f:
                    return json.load(f)
        except Exception:
            pass
        return {"bullish": [], "bearish": [], "diff": {}, "timestamp": None}

    def run_continuous(self, interval_minutes: int = 60):
        """Check hourly during market hours."""
        logger.info(f"📡 AXLFI Signal Differ started (interval: {interval_minutes}m)")
        while True:
            try:
                now = datetime.now()
                # Only check during extended market hours (8 AM - 5 PM ET)
                if 8 <= now.hour <= 17:
                    self.capture_and_diff()
                else:
                    logger.debug("Outside market hours, skipping AXLFI diff")
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"AXLFI differ loop error: {e}")
                time.sleep(120)
