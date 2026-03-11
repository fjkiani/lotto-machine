#!/usr/bin/env python3
"""
📈 Volume Spike Detector — Monitors SPY intraday for institutional volume events.

Detects bars with volume > 1.5x rolling average, logs them with price context.
Volume spikes at key levels = institutional distribution or accumulation.

Author: Zo (Alpha's AI)
"""

import time
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class VolumeSpikeDetector:
    """Detect and log SPY intraday volume spikes."""

    def __init__(self, symbol: str = "SPY", log_dir: str = "/tmp/volume_spikes"):
        self.symbol = symbol
        os.makedirs(log_dir, exist_ok=True)
        self.log_dir = log_dir
        self._spikes_today = []
        self._spike_threshold = 1.5  # 1.5x average

    def check_for_spikes(self):
        """Pull latest intraday bars and check for volume spikes."""
        try:
            import yfinance as yf

            ticker = yf.Ticker(self.symbol)
            bars = ticker.history(period="1d", interval="30m")

            if bars is None or len(bars) < 3:
                logger.debug("Not enough bars for spike detection")
                return None

            avg_vol = bars["Volume"].mean()
            if avg_vol == 0:
                return None

            spikes = []
            for idx, row in bars.iterrows():
                ratio = row["Volume"] / avg_vol
                if ratio >= self._spike_threshold:
                    spike = {
                        "time": idx.strftime("%H:%M") if hasattr(idx, "strftime") else str(idx),
                        "volume": int(row["Volume"]),
                        "ratio": round(ratio, 2),
                        "close": round(float(row["Close"]), 2),
                        "move": round(float(row["Close"] - row["Open"]), 2),
                        "category": "LARGE" if ratio >= 2.0 else "MEDIUM",
                    }
                    spikes.append(spike)

            if spikes:
                for s in spikes:
                    if s not in self._spikes_today:
                        self._spikes_today.append(s)
                        logger.warning(
                            f"🚨 VOLUME SPIKE {self.symbol} at {s['time']}: "
                            f"{s['volume']:,.0f} ({s['ratio']}x avg) | "
                            f"${s['close']} | move=${s['move']:+.2f} | {s['category']}"
                        )

            # Save daily log
            today = datetime.now().strftime("%Y-%m-%d")
            snapshot = {
                "date": today,
                "symbol": self.symbol,
                "avg_volume": int(avg_vol),
                "spikes": self._spikes_today,
                "last_check": datetime.utcnow().isoformat(),
            }

            path = os.path.join(self.log_dir, f"spikes_{today}.json")
            with open(path, "w") as f:
                json.dump(snapshot, f, indent=2)

            return snapshot

        except Exception as e:
            logger.error(f"❌ Volume spike check failed: {e}")
            return None

    def get_latest(self):
        """Get today's spike data for API."""
        today = datetime.now().strftime("%Y-%m-%d")
        path = os.path.join(self.log_dir, f"spikes_{today}.json")
        try:
            if os.path.exists(path):
                with open(path) as f:
                    return json.load(f)
        except Exception:
            pass
        return {"date": today, "symbol": self.symbol, "spikes": [], "avg_volume": 0}

    def run_continuous(self, interval_minutes: int = 5):
        """Check every N minutes during market hours."""
        logger.info(f"📈 Volume Spike Detector started ({self.symbol}, interval: {interval_minutes}m)")
        while True:
            try:
                now = datetime.now()
                # Market hours check (9:30 AM - 4:00 PM ET, rough)
                if 9 <= now.hour <= 16:
                    self.check_for_spikes()
                else:
                    # Reset daily spikes after market close
                    if now.hour >= 17 and self._spikes_today:
                        self._spikes_today = []
                    logger.debug("Outside market hours, skipping volume check")
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Volume spike loop error: {e}")
                time.sleep(60)
