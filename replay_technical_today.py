#!/usr/bin/env python3
"""
REPLAY TECHNICAL STRATEGY - TODAY'S SESSION
============================================
See what technical signals would have fired throughout today's trading session.

Author: Alpha's AI Hedge Fund
Date: 2024-10-18
"""

import sys
import os
from pathlib import Path
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging

# Add paths
sys.path.append(str(Path(__file__).parent / 'live_monitoring/strategies'))

from technical_strategy import TechnicalStrategyEngine, TechnicalContext

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_intraday_snapshots(symbol: str, interval: str = '15m'):
    """
    Get intraday price snapshots for replay
    
    Args:
        symbol: Ticker symbol
        interval: Bar interval (5m, 15m, 30m, 1h)
    
    Returns:
        DataFrame with OHLCV data
    """
    ticker = yf.Ticker(symbol)
    
    # Get today's intraday data
    df = ticker.history(interval=interval, period='1d')
    
    if df.empty:
        logger.warning(f"No intraday data for {symbol}")
        return None
    
    return df


def replay_technical_session(symbol: str, interval: str = '15m'):
    """
    Replay technical strategy throughout today's trading session
    """
    logger.info("=" * 100)
    logger.info(f"📊 REPLAYING TECHNICAL STRATEGY - {symbol} (Today's Session)")
    logger.info("=" * 100)
    logger.info(f"Interval: {interval}")
    logger.info("")
    
    # Get intraday data
    df = get_intraday_snapshots(symbol, interval)
    
    if df is None or df.empty:
        logger.error(f"Could not fetch intraday data for {symbol}")
        return
    
    logger.info(f"📈 Loaded {len(df)} bars from today's session")
    logger.info(f"   Session: {df.index[0]} to {df.index[-1]}")
    logger.info(f"   Price Range: ${df['Low'].min():.2f} - ${df['High'].max():.2f}")
    logger.info(f"   Total Volume: {df['Volume'].sum():,.0f}")
    logger.info("")
    
    # Initialize technical engine
    engine = TechnicalStrategyEngine(min_confidence=0.60)
    
    # Track signals throughout the day
    all_signals = []
    signal_times = []
    
    # Simulate checking at each bar
    logger.info("🔄 Replaying bar-by-bar...")
    logger.info("-" * 100)
    logger.info(f"{'Time':<20} {'Price':<10} {'RSI':<8} {'Volume':<12} {'Signals':<50}")
    logger.info("-" * 100)
    
    for i, (timestamp, row) in enumerate(df.iterrows()):
        # For each bar, generate signals
        try:
            signals = engine.generate_signals(symbol)
            
            # Fetch context for display
            ctx = engine.fetch_technical_context(symbol)
            
            if ctx:
                rsi_str = f"{ctx.rsi:.1f}"
                vol_str = f"{ctx.volume_ratio:.2f}x"
                
                signal_str = ""
                if signals:
                    signal_str = f"🎯 {len(signals)} signal(s): " + ", ".join([s.signal_type for s in signals])
                    all_signals.extend(signals)
                    signal_times.append((timestamp, signals))
                else:
                    signal_str = "⚪ No signals"
                
                logger.info(f"{str(timestamp)[:19]:<20} ${row['Close']:<9.2f} {rsi_str:<8} {vol_str:<12} {signal_str}")
            
        except Exception as e:
            logger.debug(f"Error at {timestamp}: {e}")
    
    logger.info("-" * 100)
    logger.info("")
    
    # Summary
    logger.info("=" * 100)
    logger.info("📊 SESSION SUMMARY")
    logger.info("=" * 100)
    logger.info("")
    
    if all_signals:
        logger.info(f"✅ Generated {len(all_signals)} total technical signals throughout the day:")
        logger.info("")
        
        # Group by signal type
        signal_types = {}
        for sig in all_signals:
            if sig.signal_type not in signal_types:
                signal_types[sig.signal_type] = []
            signal_types[sig.signal_type].append(sig)
        
        for sig_type, sigs in signal_types.items():
            logger.info(f"  📈 {sig_type}: {len(sigs)} signal(s)")
            for i, sig in enumerate(sigs, 1):
                logger.info(f"     {i}. {sig.action} @ ${sig.entry_price:.2f}")
                logger.info(f"        Confidence: {sig.confidence:.0f}% | R/R: {sig.risk_reward_ratio:.2f}")
                logger.info(f"        RSI: {sig.rsi:.1f} | Volume: {sig.volume_ratio:.1f}x | Trend: {sig.trend}")
                logger.info(f"        Reason: {sig.primary_reason}")
                for factor in sig.supporting_factors:
                    logger.info(f"          + {factor}")
                logger.info("")
    else:
        logger.info("⚪ No signals generated throughout the entire session")
        logger.info("   Market conditions did not meet technical thresholds")
    
    # Key moments
    logger.info("")
    logger.info("🔍 KEY MOMENTS:")
    logger.info("-" * 100)
    
    high_bar = df.loc[df['High'].idxmax()]
    low_bar = df.loc[df['Low'].idxmin()]
    high_vol_bar = df.loc[df['Volume'].idxmax()]
    
    logger.info(f"  📈 Highest Price: ${df['High'].max():.2f} at {df['High'].idxmax()}")
    logger.info(f"  📉 Lowest Price: ${df['Low'].min():.2f} at {df['Low'].idxmin()}")
    logger.info(f"  💨 Highest Volume: {df['Volume'].max():,.0f} at {df['Volume'].idxmax()}")
    logger.info(f"  📊 Price Range: ${df['High'].max() - df['Low'].min():.2f} ({((df['High'].max() / df['Low'].min() - 1) * 100):.2f}%)")
    
    logger.info("")
    logger.info("=" * 100)


def main():
    """Main entry point"""
    logger.info("")
    logger.info("🚀 TECHNICAL STRATEGY REPLAY - TODAY'S SESSION")
    logger.info("=" * 100)
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    logger.info("")
    
    # Replay for SPY and QQQ
    for symbol in ['SPY', 'QQQ']:
        replay_technical_session(symbol, interval='15m')
        logger.info("\n\n")
    
    logger.info("=" * 100)
    logger.info("✅ Replay complete!")
    logger.info("=" * 100)


if __name__ == "__main__":
    main()



