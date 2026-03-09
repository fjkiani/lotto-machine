#!/usr/bin/env python3
"""
📅 MULTI-DAY BACKTEST ENGINE
Leverages the modular `SessionReplayer` to run historical backtests over a date range.
Fully Replaces the old `date_range_backtest.py`.

Usage:
    python -m backtesting.engine.run_backtest --start 2026-03-03 --end 2026-03-09 --symbols SPY,QQQ

Author: Zo (Alpha's AI)
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if base_path not in sys.path:
    sys.path.insert(0, base_path)

from backtesting.engine.replayer import SessionReplayer

class MultiDayBacktester:
    def __init__(self, symbols: List[str] = None, output_dir: str = None):
        self.symbols = symbols or ["SPY", "QQQ"]
        self.replayer = SessionReplayer(symbols=self.symbols)
        
        if not output_dir:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.output_dir = os.path.join(base_path, "backtesting", "reports")
        else:
            self.output_dir = output_dir
            
        os.makedirs(self.output_dir, exist_ok=True)
        
    def run_range(self, start_date: str, end_date: str, skip_weekends: bool = True):
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        print(f"\n{'='*70}")
        print(f"🚀 INITIATING MULTI-DAY BACKTEST: {start_date} to {end_date}")
        print(f"{'='*70}")
        
        all_results = []
        current = start
        
        while current <= end:
            # Skip Weekends
            if skip_weekends and current.weekday() >= 5:
                current += timedelta(days=1)
                continue
                
            date_str = current.strftime('%Y-%m-%d')
            try:
                # Replay the single session
                daily_result = self.replayer.replay_session(date_str)
                all_results.append(daily_result)
            except Exception as e:
                print(f"❌ Failed to replay {date_str}: {e}")
                
            current += timedelta(days=1)
            
        # Aggregate the results
        self._aggregate_and_save(start_date, end_date, all_results)
        
    def _aggregate_and_save(self, start_date: str, end_date: str, results: List[Dict[str, Any]]):
        total_signals = sum(r.get('total_signals', 0) for r in results)
        total_trades = sum(r.get('total_trades', 0) for r in results)
        total_wins = sum(r.get('total_wins', 0) for r in results)
        total_losses = sum(r.get('total_losses', 0) for r in results)
        total_pnl = sum(r.get('total_pnl', 0) for r in results)
        
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        summary = {
            "timestamp_generated": datetime.now().isoformat(),
            "backtest_period": {
                "start": start_date,
                "end": end_date,
                "days_tested": len(results)
            },
            "aggregate_performance": {
                "total_signals": total_signals,
                "total_trades": total_trades,
                "total_wins": total_wins,
                "total_losses": total_losses,
                "win_rate": win_rate,
                "net_pnl_pct": total_pnl
            },
            "daily_breakdown": results
        }
        
        filename = f"backtest_{start_date}_{end_date}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
            
        print(f"\n{'='*70}")
        print(f"🏆 BACKTEST COMPLETE: {start_date} to {end_date}")
        print(f"   Win Rate : {win_rate:.1f}% ({total_wins}W / {total_losses}L)")
        print(f"   Net P&L  : {total_pnl:+.2f}%")
        print(f"💾 Report saved to: {filepath}")
        print(f"{'='*70}")

def main():
    parser = argparse.ArgumentParser(description='Run a multi-day historical backtest')
    parser.add_argument('--start', type=str, help='Start Date (YYYY-MM-DD)', required=True)
    parser.add_argument('--end', type=str, help='End Date (YYYY-MM-DD)', required=True)
    parser.add_argument('--symbols', type=str, default='SPY,QQQ', help='Comma-separated symbols')
    
    args = parser.parse_args()
    symbols = args.symbols.split(',')
    
    backtester = MultiDayBacktester(symbols=symbols)
    backtester.run_range(args.start, args.end)

if __name__ == "__main__":
    main()
