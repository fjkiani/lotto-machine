#!/usr/bin/env python3
"""
🔒 DP SNAPSHOT RECORDER
Fetches Stockgrid Dark Pool snapshots every N minutes and saves them 
to a SQLite database (`data/dp_timeseries.db`).

Since Stockgrid doesn't provide an intraday historical API, this script 
MUST be running during RTH (Regular Trading Hours) to capture the time-series 
data required for accurate Session Replays matching real-time DP confluence.

Usage:
    python -m live_monitoring.enrichment.apis.dp_snapshot_recorder
    (Recommended: run via cron or as an orchestration background process)

Author: Zo (Alpha's AI)
"""

import os
import sys
import time
import json
import sqlite3
from datetime import datetime

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if base_path not in sys.path:
    sys.path.insert(0, base_path)

from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient

class DPSnapshotRecorder:
    def __init__(self, db_path: str = None):
        self.client = StockgridClient()
        
        if not db_path:
            self.db_path = os.path.join(base_path, "data", "dp_timeseries.db")
        else:
            self.db_path = db_path
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        
    def _init_db(self):
        """Initializes the timeseries database and tables if missing."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # We store the raw JSON response indexed by timestamp.
        # This gives us max flexibility to parse levels, alerts, and volume later.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dp_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                alerts_count INTEGER,
                short_vol_pct REAL,
                json_data TEXT NOT NULL
            )
        ''')
        
        # Add index for fast querying by date
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON dp_snapshots(timestamp)")
        
        conn.commit()
        conn.close()
        
    def capture_snapshot(self, symbols=["SPY", "QQQ"]):
        """
        Fetches the latest DP snapshot for the symbols and commits to SQLite.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📸 Capturing DP Snapshot...")
        
        for symbol in symbols:
            try:
                # Use get_ticker_detail which returns DarkPoolPosition
                detail = self.client.get_ticker_detail(symbol)
                
                if detail:
                    # Also fetch the current price
                    info = self.client.get_symbol_info(symbol)
                    current_price = info.get("symbol", {}).get("close", 0) if info else 0

                    short_vol = detail.short_volume_pct or 0
                    sentiment = {
                        "price": current_price,
                        "short_volume_pct": short_vol,
                        "dp_position_shares": detail.dp_position_shares,
                        "dp_position_dollars": detail.dp_position_dollars,
                        "net_short_dollars": detail.net_short_dollars,
                        "net_short_volume": detail.net_short_volume,
                        "short_volume": detail.short_volume,
                        "date": detail.date,
                        "alerts": [],
                    }
                    alerts_count = 0
                    
                    cursor.execute(
                        "INSERT INTO dp_snapshots (symbol, alerts_count, short_vol_pct, json_data) VALUES (?, ?, ?, ?)",
                        (symbol, alerts_count, short_vol, json.dumps(sentiment))
                    )
                    
                    print(f"  ✅ {symbol}: {short_vol:.1f}% Short Vol | DP ${detail.dp_position_dollars/1e6:.1f}M")
                else:
                    print(f"  ⚠️ {symbol}: No data returned from AXLFI.")
                    
            except Exception as e:
                print(f"  ❌ {symbol}: Failed to capture -> {e}")
                
        conn.commit()
        conn.close()
        
    def run_continuous(self, interval_minutes: int = 5):
        """
        Runs continuously, capturing a snapshot every interval_minutes.
        """
        print(f"🚀 Starting DP Snapshot Recorder (Interval: {interval_minutes}m)")
        print(f"💾 Saving to: {self.db_path}")
        
        while True:
            try:
                self.capture_snapshot()
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                print("\n🛑 Snapshot Recorder stopped by user.")
                break
            except Exception as e:
                print(f"❌ Critical loop error: {e}")
                time.sleep(60) # Backoff before retrying

def main():
    recorder = DPSnapshotRecorder()
    recorder.run_continuous()

if __name__ == "__main__":
    main()
