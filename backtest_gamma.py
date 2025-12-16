#!/usr/bin/env python3
"""
🎲 GAMMA TRACKER BACKTEST - MODULAR VERSION
===========================================

Lean, modular backtest using the backtesting framework.

Usage:
    python3 backtest_gamma.py --days 5 --symbols SPY QQQ
    python3 backtest_gamma.py --days 30 --symbols SPY QQQ DIA IWM
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import argparse
from dotenv import load_dotenv

load_dotenv()

# Add project paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from live_monitoring.exploitation.gamma_tracker import GammaTracker
from backtesting import TradingParams, PerformanceAnalyzer
from backtesting.simulation.gamma_detector import GammaDetectorSimulator
from backtesting.reports.gamma_report import GammaReportGenerator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Backtest Gamma Tracker (Modular)')
    parser.add_argument('--days', type=int, default=5, help='Number of days to backtest (default: 5)')
    parser.add_argument('--symbols', nargs='+', default=['SPY', 'QQQ'], help='Symbols to test (default: SPY QQQ)')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD), defaults to days ago')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD), defaults to today')
    args = parser.parse_args()
    
    # Parse dates
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    else:
        start_date = end_date - timedelta(days=args.days)
    
    logger.info("="*70)
    logger.info("🎲 GAMMA TRACKER BACKTEST (MODULAR)")
    logger.info("="*70)
    logger.info(f"   Symbols: {', '.join(args.symbols)}")
    logger.info(f"   Date Range: {start_date.date()} to {end_date.date()}")
    logger.info(f"   Days: {(end_date - start_date).days}")
    logger.info("="*70)
    logger.info("")
    
    # Initialize components
    logger.info("📡 Initializing components...")
    tracker = GammaTracker()
    simulator = GammaDetectorSimulator(tracker, TradingParams())
    analyzer = PerformanceAnalyzer()
    report_gen = GammaReportGenerator()
    
    logger.info("✅ Components initialized")
    logger.info("")
    
    # Run simulation
    logger.info("🚀 Running simulation...")
    trades = simulator.simulate(args.symbols, start_date, end_date)
    logger.info(f"✅ Simulation complete: {len(trades)} trades generated")
    logger.info("")
    
    if len(trades) == 0:
        logger.warning("⚠️ No trades generated! Check:")
        logger.warning("   1. Are symbols valid?")
        logger.warning("   2. Are there options available for these symbols?")
        logger.warning("   3. Do signals meet threshold requirements?")
        return
    
    # Analyze performance
    logger.info("📊 Analyzing performance...")
    metrics = analyzer.analyze(trades)
    gamma_metrics = report_gen.calculate_gamma_metrics(trades)
    logger.info("✅ Analysis complete")
    logger.info("")
    
    # Generate report
    logger.info("📄 Generating report...")
    date_range_str = f"{start_date.date()} to {end_date.date()}"
    report = report_gen.generate_report(
        metrics=metrics,
        gamma_metrics=gamma_metrics,
        date_range=date_range_str,
        symbols=args.symbols
    )
    print("\n" + report)
    logger.info("")
    
    # Criteria check is now in the report generator


if __name__ == "__main__":
    main()

