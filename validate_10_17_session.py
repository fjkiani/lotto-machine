#!/usr/bin/env python3
"""
VALIDATE 10/17 SESSION WITH REAL 10/16 DP DATA
- Run minute-by-minute replay
- Log every cycle with full reasoning
- Identify all DP level interactions
- Generate complete audit trail
"""

import pandas as pd
import logging
import sys
from pathlib import Path

# Add core to path
sys.path.append(str(Path(__file__).parent / 'core'))

from replay_engine import ReplayEngine
from master_signal_generator import MasterSignalGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/replay_10_17.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Run the full validation"""
    logger.info("🚀 STARTING 10/17 SESSION VALIDATION")
    logger.info("=" * 100)
    
    # Load real DP data from 10/16
    logger.info("📊 Loading real DP data from 10/16...")
    dp_df = pd.read_csv('data/cx_dark_pool_levels_nyse-spy_2025-10-16_17607558648217.csv')
    logger.info(f"✅ Loaded {len(dp_df)} DP levels")
    
    # Show key battlegrounds
    battlegrounds = dp_df[dp_df['volume'] > 1000000].sort_values('volume', ascending=False)
    logger.info("")
    logger.info("⚔️ INSTITUTIONAL BATTLEGROUNDS:")
    for _, row in battlegrounds.iterrows():
        logger.info(f"   ${row['level']:.2f} - {row['volume']:,} shares ({row['trades']} trades)")
    logger.info("")
    
    # Create replay engine
    engine = ReplayEngine(dp_df)
    
    # Run replay for 10/17
    logger.info("🎬 Running replay for 10/17...")
    logger.info("=" * 100)
    
    states = engine.replay_session(
        ticker='SPY',
        date='2025-10-17',
        output_file='logs/replay_10_17_detailed.csv'
    )
    
    if not states:
        logger.error("❌ Replay failed - no data")
        return
    
    # Analyze results
    logger.info("")
    logger.info("🔍 DETAILED ANALYSIS")
    logger.info("=" * 100)
    
    # Find all signals
    buy_signals = [s for s in states if s.decision == "SIGNAL_BUY"]
    sell_signals = [s for s in states if s.decision == "SIGNAL_SELL"]
    
    logger.info(f"📈 RAW BUY SIGNALS: {len(buy_signals)}")
    logger.info(f"📉 RAW SELL SIGNALS: {len(sell_signals)}")
    
    # Convert to master signals
    logger.info("")
    logger.info("🎯 GENERATING MASTER SIGNALS")
    logger.info("=" * 100)
    
    master_gen = MasterSignalGenerator()
    
    # Prepare signal dicts
    all_signal_dicts = []
    for sig in buy_signals + sell_signals:
        sig_dict = {
            'timestamp': sig.timestamp,
            'price': sig.price,
            'action': sig.decision.replace('SIGNAL_', ''),
            'dp_level': sig.nearest_support if sig.decision == "SIGNAL_BUY" else sig.nearest_resistance,
            'dp_volume': sig.support_volume if sig.decision == "SIGNAL_BUY" else sig.resistance_volume,
            'volume_vs_avg': sig.volume_vs_avg,
            'volume_confirmed': sig.volume_confirmed,
            'momentum': sig.momentum,
            'momentum_confirmed': sig.momentum_confirmed,
            'regime': sig.regime,
            'magnet_alerts': sig.magnet_alerts,
            'confidence': sig.signal_confidence
        }
        all_signal_dicts.append(sig_dict)
    
    # Generate master signals
    master_signals = master_gen.filter_to_master_signals(all_signal_dicts)
    
    logger.info("")
    logger.info("=" * 100)
    logger.info("🎯 MASTER SIGNALS (ACTIONABLE)")
    logger.info("=" * 100)
    
    for i, master in enumerate(master_signals, 1):
        logger.info(f"\n{i}. {master.action} @ {master.timestamp}")
        logger.info(f"   Price: ${master.price:.2f}")
        logger.info(f"   PRIMARY: {master.primary_reason}")
        logger.info(f"   Confidence: {master.confidence:.0%}")
        logger.info(f"   Entry: ${master.entry_price:.2f} | Stop: ${master.stop_loss:.2f} | Target: ${master.take_profit:.2f}")
        logger.info(f"   Risk/Reward: 1:{master.risk_reward_ratio:.1f}")
        if master.supporting_factors:
            logger.info(f"   Supporting: {', '.join(master.supporting_factors)}")
    
    # Show rejection summary
    logger.info("")
    logger.info("📊 REJECTION ANALYSIS")
    logger.info("=" * 100)
    rejections = master_gen.get_rejection_summary(all_signal_dicts)
    logger.info(f"Total signals rejected: {rejections['total_rejected']}")
    logger.info(f"   Low DP strength: {rejections['low_dp_strength']}")
    logger.info(f"   No volume confirmation: {rejections['no_volume']}")
    logger.info(f"   Weak momentum: {rejections['weak_momentum']}")
    logger.info(f"   Poor regime: {rejections['poor_regime']}")
    logger.info(f"   No magnet interaction: {rejections['no_magnet_interaction']}")
    
    # Find times when price was AT battleground levels
    logger.info("")
    logger.info("⚔️ BATTLEGROUND INTERACTIONS:")
    for _, bg in battlegrounds.iterrows():
        bg_level = bg['level']
        bg_volume = bg['volume']
        
        # Find cycles near this level
        near_cycles = [s for s in states if abs(s.price - bg_level) / s.price < 0.003]
        
        if near_cycles:
            logger.info(f"   ${bg_level:.2f} ({bg_volume:,} shares):")
            for cycle in near_cycles:
                logger.info(f"      {cycle.timestamp} @ ${cycle.price:.2f} - {cycle.decision}")
                logger.info(f"         {cycle.reasoning}")
    
    logger.info("")
    logger.info("✅ VALIDATION COMPLETE!")
    logger.info(f"📄 Detailed log saved to: logs/replay_10_17_detailed.csv")
    logger.info(f"📄 Full log saved to: logs/replay_10_17.log")

if __name__ == '__main__':
    main()

