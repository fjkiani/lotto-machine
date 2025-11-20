#!/usr/bin/env python3
"""
ULTRA INSTITUTIONAL ENGINE DEMO
- Tests complete institutional data integration
- Shows squeeze, gamma, and breakout setups
- Demonstrates multi-factor confirmation
"""

import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / 'core'))
sys.path.append(str(Path(__file__).parent / 'configs'))

from ultra_institutional_engine import UltraInstitutionalEngine
import chartexchange_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    logger.info("🚀 ULTRA INSTITUTIONAL ENGINE DEMO")
    logger.info("=" * 100)
    
    # Initialize engine
    engine = UltraInstitutionalEngine(chartexchange_config.CHARTEXCHANGE_API_KEY)
    
    # Test symbols
    symbols = ["SPY", "GME", "AMC"]  # SPY for normal, GME/AMC for squeeze potential
    
    for symbol in symbols:
        logger.info(f"\n{'=' * 100}")
        logger.info(f"🔍 ANALYZING {symbol}")
        logger.info("=" * 100)
        
        try:
            # Build institutional context
            context = engine.build_institutional_context(symbol)
            
            logger.info(f"\n📊 INSTITUTIONAL CONTEXT FOR {symbol}:")
            logger.info("-" * 100)
            
            # Dark Pool
            logger.info(f"\n🌑 DARK POOL DATA:")
            logger.info(f"   Battlegrounds: {len(context.dp_battlegrounds)} (${', $'.join(f'{bg:.2f}' for bg in context.dp_battlegrounds[:5])})")
            logger.info(f"   Total Volume: {context.dp_total_volume:,} shares")
            logger.info(f"   Buy/Sell Ratio: {context.dp_buy_sell_ratio:.2f}")
            logger.info(f"   Avg Print Size: {context.dp_avg_print_size:.0f} shares")
            logger.info(f"   Dark Pool %: {context.dark_pool_pct:.1f}%")
            
            # Short Data
            logger.info(f"\n📉 SHORT DATA:")
            logger.info(f"   Short Volume %: {context.short_volume_pct:.1f}%")
            logger.info(f"   Short Interest: {context.short_interest:,} shares" if context.short_interest else "   Short Interest: N/A")
            if context.days_to_cover:
                try:
                    dtc_float = float(context.days_to_cover)
                    logger.info(f"   Days to Cover: {dtc_float:.1f}")
                except:
                    logger.info(f"   Days to Cover: {context.days_to_cover}")
            else:
                logger.info("   Days to Cover: N/A")
            logger.info(f"   Borrow Fee: {context.borrow_fee_rate:.2f}%")
            
            # Options
            logger.info(f"\n📈 OPTIONS DATA:")
            logger.info(f"   Max Pain: ${context.max_pain:.2f}" if context.max_pain else "   Max Pain: N/A")
            logger.info(f"   Put/Call Ratio: {context.put_call_ratio:.2f}")
            logger.info(f"   Total OI: {context.total_option_oi:,}")
            
            # FTDs
            logger.info(f"\n⚠️ FTD DATA:")
            logger.info(f"   Recent FTDs: {context.recent_ftds:,} shares")
            logger.info(f"   Trend: {context.ftd_trend}")
            
            # Composite Scores
            logger.info(f"\n🎯 COMPOSITE SCORES:")
            logger.info(f"   Institutional Buying Pressure: {context.institutional_buying_pressure:.0%}")
            logger.info(f"   Squeeze Potential: {context.squeeze_potential:.0%}")
            logger.info(f"   Gamma Pressure: {context.gamma_pressure:.0%}")
            
            # Check for signals (using dummy price)
            dummy_price = 100.0  # Would use real price in production
            signals = engine.analyze_for_signals(symbol, dummy_price)
            
            if signals:
                logger.info(f"\n🎯 ULTRA SIGNALS DETECTED: {len(signals)}")
                logger.info("=" * 100)
                
                for i, signal in enumerate(signals, 1):
                    logger.info(f"\n{i}. {signal.signal_type} SIGNAL")
                    logger.info(f"   Action: {signal.action} @ ${signal.entry_price:.2f}")
                    logger.info(f"   PRIMARY: {signal.primary_catalyst}")
                    logger.info(f"   Confidence: {signal.confidence:.0%} | Institutional Score: {signal.institutional_score:.0%}")
                    logger.info(f"   Entry: ${signal.entry_price:.2f} | Stop: ${signal.stop_loss:.2f} | Target: ${signal.take_profit:.2f}")
                    logger.info(f"   Risk/Reward: 1:{signal.risk_reward_ratio:.1f}")
                    
                    logger.info(f"\n   Confirmation:")
                    logger.info(f"      DP Confirmed: {'✅' if signal.dp_confirmed else '❌'}")
                    logger.info(f"      Squeeze Setup: {'✅' if signal.short_squeeze_setup else '❌'}")
                    logger.info(f"      Gamma Setup: {'✅' if signal.gamma_setup else '❌'}")
                    logger.info(f"      FTD Pressure: {'✅' if signal.ftd_pressure else '❌'}")
                    
                    if signal.supporting_factors:
                        logger.info(f"\n   Supporting:")
                        for factor in signal.supporting_factors:
                            logger.info(f"      • {factor}")
                    
                    if signal.warnings:
                        logger.info(f"\n   ⚠️ Warnings:")
                        for warning in signal.warnings:
                            logger.info(f"      • {warning}")
            else:
                logger.info(f"\n✅ No ultra signals detected - waiting for setup")
        
        except Exception as e:
            logger.error(f"❌ Error analyzing {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    logger.info("\n" + "=" * 100)
    logger.info("✅ ULTRA ENGINE DEMO COMPLETE")
    logger.info("=" * 100)

if __name__ == "__main__":
    main()

