#!/usr/bin/env python3
"""
▶️ SESSION REPLAY ENGINE
Replays a specific date bar-by-bar against all active detectors.
Uses properly strictly historical OHLC data, fixes VIX leakage, 
and leverages the new modular backtesting/engine.

Usage:
    python -m backtesting.engine.run_replay --date 2026-03-09 --symbols SPY,QQQ

Author: Zo (Alpha's AI)
"""

import os
import sys
import argparse
from datetime import datetime

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if base_path not in sys.path:
    sys.path.insert(0, base_path)

from backtesting.engine.replayer import SessionReplayer
from backtesting.engine.reporting import ReplayReporter

def main():
    parser = argparse.ArgumentParser(description='Run a tick-by-tick Session Replay')
    parser.add_argument('--date', type=str, help='Date to replay (YYYY-MM-DD)', required=True)
    parser.add_argument('--symbols', type=str, default='SPY,QQQ', help='Comma-separated symbols')
    
    args = parser.parse_args()
    symbols = args.symbols.split(',')
    
    # 1. Initialize Engine
    replayer = SessionReplayer(symbols=symbols)
    reporter = ReplayReporter()
    
    # 2. Execute Replay
    try:
        results = replayer.replay_session(args.date)
        
        # 3. Report & Save
        reporter.print_summary(results)
        reporter.save_session_replay(args.date, results)
        
        print("\n✅ REPLAY COMPLETE!")
        
    except Exception as e:
        print(f"\n❌ REPLAY FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
