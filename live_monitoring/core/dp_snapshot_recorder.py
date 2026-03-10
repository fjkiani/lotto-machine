#!/usr/bin/env python3
"""
Dark Pool Snapshot Recorder (Intraday Tape)
===========================================

Runs as a background daemon during Regular Trading Hours (RTH).
Takes frequent snapshots of the dark pool levels and saves them 
so the Session Replay engine has historical intraday dark tape.
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from typing import List

# Setup path
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if base_path not in sys.path:
    sys.path.insert(0, base_path)

from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DP_SnapshotRecorder")

class DPSnapshotRecorder:
    def __init__(self, symbols: List[str] = None, interval_seconds: int = 300):
        self.symbols = symbols or ["SPY", "QQQ"]
        self.interval = interval_seconds
        self.client = StockgridClient()
        
        # Determine output dir
        self.output_dir = os.path.join(base_path, "backtesting", "data", "dp_snapshots")
        os.makedirs(self.output_dir, exist_ok=True)
        
    def _is_rth(self) -> bool:
        """Check if currently Regular Trading Hours (09:30 - 16:00 ET)"""
        # Note: This is a simplistic check using local time.
        # For a true hedge fund, timezone mapping is critical.
        now = datetime.now()
        # Monday to Friday
        if now.weekday() > 4:
            return False
            
        # 09:30 to 16:00
        current_time = now.time()
        start = datetime.strptime("09:30", "%H:%M").time()
        end = datetime.strptime("16:00", "%H:%M").time()
        
        return start <= current_time <= end
        
    def record_snapshot(self):
        """Fetch and record DP snapshots."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().isoformat()
        
        for symbol in self.symbols:
            try:
                logger.info(f"📸 Taking DP snapshot for {symbol}...")
                data = self.client.get_ticker_detail(symbol)
                
                if data:
                    snapshot = {
                        "timestamp": timestamp,
                        "symbol": symbol,
                        "dp_position_dollars": data.dp_position_dollars,
                        "short_volume_pct": data.short_volume_pct,
                        "net_short_dollars": data.net_short_dollars,
                    }
                    
                    filename = os.path.join(self.output_dir, f"{symbol}_dp_tape_{today_str}.jsonl")
                    with open(filename, 'a') as f:
                        f.write(json.dumps(snapshot) + "\n")
                else:
                    logger.warning(f"Failed to fetch DP data for {symbol}")
            except Exception as e:
                logger.error(f"Error recording snapshot for {symbol}: {e}")
                
    def run(self):
        """Main loop."""
        logger.info(f"🚀 Starting DP Snapshot Recorder. Interval: {self.interval}s")
        logger.info(f"Saving to: {self.output_dir}")
        
        while True:
            if self._is_rth() or os.environ.get("FORCE_DP_RECORD", "0") == "1":
                self.record_snapshot()
            else:
                logger.info("Outside RTH. Sleeping...")
                
            time.sleep(self.interval)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the DP Snapshot logger")
    parser.add_argument("--symbols", type=str, default="SPY,QQQ", help="Comma-separated symbols")
    parser.add_argument("--interval", type=int, default=300, help="Log interval in seconds")
    
    args = parser.parse_args()
    symbols = args.symbols.split(",")
    
    recorder = DPSnapshotRecorder(symbols=symbols, interval=args.interval)
    
    # Just run exactly once if triggered in CI/Test
    if os.environ.get("TEST_RUN", "0") == "1":
        recorder.record_snapshot()
        print("✅ DP Snapshot created.")
        sys.exit(0)
        
    recorder.run()

