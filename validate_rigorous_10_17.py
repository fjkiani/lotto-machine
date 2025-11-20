#!/usr/bin/env python3
"""
RIGOROUS DP VALIDATION - 10/17 SESSION
- Only signals at MAJOR DP levels (>500K shares)
- NEVER act on first touch
- Require BOTH volume AND momentum confirmation
- Adaptive stops outside battlefield zones
- Complete cycle-by-cycle audit
"""

import pandas as pd
import logging
import sys
from pathlib import Path
from datetime import datetime
import yfinance as yf

# Add core to path
sys.path.append(str(Path(__file__).parent / 'core'))

from rigorous_dp_signal_engine import RigorousDPEngine, RigorousSignal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/rigorous_validation.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def detect_regime(price_window: pd.Series) -> tuple:
    """Simple regime detection"""
    if len(price_window) < 20:
        return "INSUFFICIENT_DATA", 0.0, 0.0, 0.0
    
    returns = price_window.pct_change().dropna()
    
    # Trend strength
    trend = (price_window.iloc[-1] - price_window.iloc[0]) / price_window.iloc[0]
    
    # Volatility
    volatility = returns.std()
    
    # Momentum (last return)
    momentum = returns.iloc[-1] if len(returns) > 0 else 0.0
    
    # Classify regime
    if abs(trend) > 0.005 and volatility < 0.003:
        regime = "UPTREND" if trend > 0 else "DOWNTREND"
    elif volatility < 0.002:
        regime = "RANGE"
    else:
        regime = "CHOP"
    
    return regime, trend, volatility, momentum

def main():
    logger.info("🎯 RIGOROUS DP VALIDATION - 10/17 SESSION")
    logger.info("=" * 100)
    
    # Load DP data
    dp_file = "data/cx_dark_pool_levels_nyse-spy_2025-10-16_17607558648217.csv"
    dp_df = pd.read_csv(dp_file)
    
    logger.info(f"📊 Loaded {len(dp_df)} DP levels")
    
    # Show battlegrounds
    battlegrounds = dp_df[dp_df['volume'] >= 1000000].sort_values(by='volume', ascending=False)
    logger.info(f"\n⚔️ BATTLEGROUNDS (>1M shares):")
    for _, bg in battlegrounds.iterrows():
        logger.info(f"   ${bg['level']:.2f} - {bg['volume']:,.0f} shares")
    
    # Show major levels
    major = dp_df[(dp_df['volume'] >= 500000) & (dp_df['volume'] < 1000000)].sort_values(by='volume', ascending=False)
    logger.info(f"\n📍 MAJOR LEVELS (500K-1M shares):")
    for _, lv in major.head(10).iterrows():
        logger.info(f"   ${lv['level']:.2f} - {lv['volume']:,.0f} shares")
    
    # Initialize engine
    engine = RigorousDPEngine(dp_df)
    
    # Load intraday data
    logger.info(f"\n📊 Loading intraday data for SPY on 2025-10-17...")
    ticker = yf.Ticker("SPY")
    df = ticker.history(start="2025-10-17", end="2025-10-18", interval="1m")
    
    if df.empty:
        logger.error("❌ No intraday data available")
        return
    
    # Filter for RTH
    df.index = df.index.tz_convert('America/New_York')
    df = df.between_time('09:30', '15:59')
    
    logger.info(f"✅ Loaded {len(df)} minute bars")
    logger.info(f"   Price range: ${df['Close'].min():.2f} - ${df['Close'].max():.2f}")
    
    # Process each bar
    logger.info("\n🎬 PROCESSING SESSION")
    logger.info("=" * 100)
    
    signals = []
    cycle_logs = []
    
    for i, (timestamp, bar) in enumerate(df.iterrows(), 1):
        # Calculate rolling metrics
        if i < 30:
            avg_volume = df['Volume'].iloc[:i].mean()
        else:
            avg_volume = df['Volume'].iloc[i-30:i].mean()
        
        # Get price window for regime
        if i < 20:
            price_window = df['Close'].iloc[:i]
        else:
            price_window = df['Close'].iloc[i-20:i]
        
        regime, trend, volatility, momentum = detect_regime(price_window)
        
        # Process bar
        signal = engine.process_bar(
            timestamp=timestamp,
            open_price=bar['Open'],
            high=bar['High'],
            low=bar['Low'],
            close=bar['Close'],
            volume=int(bar['Volume']),
            avg_volume=avg_volume,
            momentum=momentum,
            regime=regime
        )
        
        # Log cycle
        cycle_log = {
            'timestamp': timestamp,
            'price': bar['Close'],
            'volume': int(bar['Volume']),
            'volume_vs_avg': bar['Volume'] / avg_volume if avg_volume > 0 else 1.0,
            'momentum': momentum,
            'regime': regime,
            'signal': signal.action if signal else 'NO_SIGNAL'
        }
        cycle_logs.append(cycle_log)
        
        if signal:
            signals.append(signal)
            logger.info(f"\n🎯 RIGOROUS SIGNAL #{len(signals)}")
            logger.info(f"   Time: {signal.timestamp}")
            logger.info(f"   Action: {signal.action} @ ${signal.entry_price:.2f}")
            logger.info(f"   PRIMARY: {signal.primary_reason}")
            logger.info(f"   Confidence: {signal.confidence:.0%} | Touch #{signal.touch_count}")
            logger.info(f"   Entry: ${signal.entry_price:.2f} | Stop: ${signal.stop_loss:.2f} | Target: ${signal.take_profit:.2f}")
            logger.info(f"   Risk/Reward: 1:{signal.risk_reward_ratio:.1f}")
            logger.info(f"   Volume: {signal.volume_vs_avg:.1f}x avg | Momentum: {signal.momentum:+.2%}")
            logger.info(f"   Regime: {signal.regime} | Quality: {signal.entry_quality}")
            if signal.supporting_factors:
                logger.info(f"   Supporting: {', '.join(signal.supporting_factors)}")
            if signal.warning_factors:
                logger.info(f"   ⚠️ Warnings: {', '.join(signal.warning_factors)}")
    
    # Summary
    logger.info("\n" + "=" * 100)
    logger.info("📊 SESSION SUMMARY")
    logger.info("=" * 100)
    
    interaction_summary = engine.get_interaction_summary()
    
    logger.info(f"Total cycles processed: {len(cycle_logs)}")
    logger.info(f"Total magnet interactions: {interaction_summary['total_interactions']}")
    logger.info(f"   First touches: {interaction_summary['first_touches']}")
    logger.info(f"   Testing: {interaction_summary['testing']}")
    logger.info(f"   Bounces: {interaction_summary['bounces']}")
    logger.info(f"   Breaks: {interaction_summary['breaks']}")
    logger.info(f"   Rejections: {interaction_summary['rejections']}")
    logger.info(f"\n🎯 RIGOROUS SIGNALS: {len(signals)}")
    logger.info(f"   Filter rate: {len(signals)/len(cycle_logs)*100:.2f}% of cycles")
    logger.info(f"   Signal rate: {len(signals)/interaction_summary['total_interactions']*100:.1f}% of interactions")
    
    # Save logs
    pd.DataFrame(cycle_logs).to_csv('logs/rigorous_cycles_10_17.csv', index=False)
    logger.info(f"\n💾 Saved cycle log to: logs/rigorous_cycles_10_17.csv")
    
    # Detailed signal analysis
    if signals:
        logger.info("\n" + "=" * 100)
        logger.info("🔍 DETAILED SIGNAL ANALYSIS")
        logger.info("=" * 100)
        
        for i, sig in enumerate(signals, 1):
            logger.info(f"\n{i}. {sig.action} @ {sig.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"   Entry: ${sig.entry_price:.2f} | DP Level: ${sig.dp_level:.2f} ({sig.dp_volume:,} shares)")
            logger.info(f"   Type: {sig.interaction_type} | Quality: {sig.entry_quality} | Touch #{sig.touch_count}")
            logger.info(f"   Stop: ${sig.stop_loss:.2f} | Target: ${sig.take_profit:.2f} | R/R: 1:{sig.risk_reward_ratio:.1f}")
            logger.info(f"   Confidence: {sig.confidence:.0%}")
    
    logger.info("\n✅ RIGOROUS VALIDATION COMPLETE")
    logger.info("=" * 100)

if __name__ == "__main__":
    main()



