#!/usr/bin/env python3
"""
🔥 SQUEEZE DETECTOR BACKTEST - MODULAR VERSION
==============================================

Lean, modular backtest using the backtesting framework.

Usage:
    python3 backtest_squeeze.py --days 30 --symbols SPY QQQ
    python3 backtest_squeeze.py --days 90 --symbols GME AMC
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

from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
from live_monitoring.exploitation.squeeze_detector import SqueezeDetector
from backtesting import TradingParams, PerformanceAnalyzer
from backtesting.simulation.squeeze_detector import SqueezeDetectorSimulator
from backtesting.reports.squeeze_report import SqueezeReportGenerator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Backtest Squeeze Detector (Modular)')
    parser.add_argument('--days', type=int, default=30, help='Number of days to backtest (default: 30)')
    parser.add_argument('--symbols', nargs='+', default=['SPY', 'QQQ'], help='Symbols to test (default: SPY QQQ)')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD), defaults to days ago')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD), defaults to today')
    args = parser.parse_args()
    
    # Check API key
    api_key = os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
    if not api_key:
        logger.error("❌ No ChartExchange API key found!")
        logger.error("   Set CHARTEXCHANGE_API_KEY or CHART_EXCHANGE_API_KEY in .env")
        return
    
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
    logger.info("🔥 SQUEEZE DETECTOR BACKTEST (MODULAR)")
    logger.info("="*70)
    logger.info(f"   Symbols: {', '.join(args.symbols)}")
    logger.info(f"   Date Range: {start_date.date()} to {end_date.date()}")
    logger.info(f"   Days: {(end_date - start_date).days}")
    logger.info("="*70)
    logger.info("")
    
    # Initialize components
    logger.info("📡 Initializing components...")
    client = UltimateChartExchangeClient(api_key, tier=3)
    detector = SqueezeDetector(client)
    simulator = SqueezeDetectorSimulator(detector, TradingParams())
    analyzer = PerformanceAnalyzer()
    report_gen = SqueezeReportGenerator()
    
    logger.info("✅ Components initialized")
    logger.info("")
    
    # Run simulation
    logger.info("🚀 Running simulation...")
    trades = simulator.simulate(args.symbols, start_date, end_date)
    logger.info(f"✅ Simulation complete: {len(trades)} trades generated")
    logger.info("")
    
    # Analyze performance
    logger.info("📊 Analyzing performance...")
    metrics = analyzer.analyze(trades)
    squeeze_metrics = report_gen.calculate_squeeze_metrics(trades)
    logger.info("✅ Analysis complete")
    logger.info("")
    
    # Generate report
    date_range_str = f"{start_date.date()} to {end_date.date()}"
    report = report_gen.generate_report(
        metrics=metrics,
        squeeze_metrics=squeeze_metrics,
        date_range=date_range_str,
        symbols=args.symbols
    )
    
    print(report)
    
    # Save report
    report_file = report_gen.save_report(report)
    logger.info(f"📄 Report saved to: {report_file}")


if __name__ == "__main__":
    main()


