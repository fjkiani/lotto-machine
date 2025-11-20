#!/usr/bin/env python3
"""
COMBINED STRATEGY RUNNER
========================
Runs both Institutional Flow + Technical Analysis strategies in parallel.
Identifies:
- Institutional-only signals
- Technical-only signals
- HOLY GRAIL signals (both agree!)

Author: Alpha's AI Hedge Fund
Date: 2024-10-18
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# Add paths
sys.path.append(str(Path(__file__).parent / 'core'))
sys.path.append(str(Path(__file__).parent / 'core/data'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring/core'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring/strategies'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring/config'))

from ultra_institutional_engine import UltraInstitutionalEngine
from ultimate_chartexchange_client import UltimateChartExchangeClient
from signal_generator import SignalGenerator
from technical_strategy import TechnicalStrategyEngine
from monitoring_config import TradingConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_symbol(symbol: str, institutional_engine: UltraInstitutionalEngine,
                   inst_signal_gen: SignalGenerator, tech_engine: TechnicalStrategyEngine):
    """
    Run both strategies on a symbol and compare results
    """
    logger.info("=" * 80)
    logger.info(f"📊 ANALYZING {symbol}")
    logger.info("=" * 80)
    logger.info("")
    
    # 1. Institutional Flow Analysis
    logger.info("🏛️  INSTITUTIONAL FLOW ANALYSIS")
    logger.info("-" * 80)
    
    inst_signals = []
    try:
        # Get institutional context
        inst_context = institutional_engine.build_context(symbol)
        
        logger.info(f"  Institutional Score: {inst_context.institutional_buying_pressure:.0%}")
        logger.info(f"  Squeeze Potential: {inst_context.squeeze_potential:.0%}")
        logger.info(f"  Gamma Pressure: {inst_context.gamma_pressure:.0%}")
        logger.info(f"  DP Battlegrounds: {len(inst_context.dp_battlegrounds)}")
        
        # Generate signals (need current price)
        if inst_context.dp_battlegrounds:
            current_price = sum(inst_context.dp_battlegrounds) / len(inst_context.dp_battlegrounds)
            inst_signals = inst_signal_gen.generate_signals(symbol, current_price, inst_context)
            
            if inst_signals:
                logger.info(f"\n  ✅ Generated {len(inst_signals)} institutional signals:")
                for sig in inst_signals:
                    logger.info(f"    - {sig.signal_type}: {sig.action} @ ${sig.entry_price:.2f} (Confidence: {sig.confidence:.0f}%)")
            else:
                logger.info(f"\n  ⚪ No institutional signals (thresholds not met)")
        else:
            logger.info(f"\n  ⚪ No DP data available")
    
    except Exception as e:
        logger.error(f"  ❌ Error in institutional analysis: {e}")
    
    logger.info("")
    
    # 2. Technical Analysis
    logger.info("📈 TECHNICAL ANALYSIS")
    logger.info("-" * 80)
    
    tech_signals = []
    try:
        tech_signals = tech_engine.generate_signals(symbol)
        
        if tech_signals:
            logger.info(f"  ✅ Generated {len(tech_signals)} technical signals:")
            for sig in tech_signals:
                logger.info(f"    - {sig.signal_type}: {sig.action} @ ${sig.entry_price:.2f} (Confidence: {sig.confidence:.0f}%)")
        else:
            logger.info(f"  ⚪ No technical signals (thresholds not met)")
    
    except Exception as e:
        logger.error(f"  ❌ Error in technical analysis: {e}")
    
    logger.info("")
    
    # 3. Combined Analysis
    logger.info("🎯 COMBINED ANALYSIS")
    logger.info("-" * 80)
    
    # Check for agreement (HOLY GRAIL)
    holy_grail_signals = []
    
    for inst_sig in inst_signals:
        for tech_sig in tech_signals:
            # Check if they agree on direction
            if inst_sig.action == tech_sig.action:
                # Calculate combined confidence
                combined_confidence = (inst_sig.confidence + tech_sig.confidence) / 2
                
                holy_grail_signals.append({
                    'symbol': symbol,
                    'action': inst_sig.action,
                    'institutional_signal': inst_sig.signal_type,
                    'technical_signal': tech_sig.signal_type,
                    'inst_confidence': inst_sig.confidence,
                    'tech_confidence': tech_sig.confidence,
                    'combined_confidence': combined_confidence,
                    'inst_entry': inst_sig.entry_price,
                    'tech_entry': tech_sig.entry_price,
                })
    
    if holy_grail_signals:
        logger.info(f"  🔥🔥🔥 HOLY GRAIL: {len(holy_grail_signals)} signals where BOTH strategies agree!")
        logger.info("")
        for hg in holy_grail_signals:
            logger.info(f"    💎 {hg['action']} {hg['symbol']}")
            logger.info(f"       Institutional: {hg['institutional_signal']} ({hg['inst_confidence']:.0f}% conf)")
            logger.info(f"       Technical: {hg['technical_signal']} ({hg['tech_confidence']:.0f}% conf)")
            logger.info(f"       COMBINED CONFIDENCE: {hg['combined_confidence']:.0f}%")
            logger.info("")
    else:
        if inst_signals and tech_signals:
            logger.info(f"  ⚠️  Strategies DISAGREE - Institutional says {inst_signals[0].action}, Technical says {tech_signals[0].action}")
            logger.info(f"     → Proceed with caution or wait for alignment")
        elif inst_signals:
            logger.info(f"  📊 Institutional-only signal: {inst_signals[0].signal_type} ({inst_signals[0].action})")
            logger.info(f"     → No technical confirmation")
        elif tech_signals:
            logger.info(f"  📈 Technical-only signal: {tech_signals[0].signal_type} ({tech_signals[0].action})")
            logger.info(f"     → No institutional confirmation")
        else:
            logger.info(f"  ⚪ No signals from either strategy")
    
    logger.info("")
    
    return {
        'symbol': symbol,
        'institutional_signals': inst_signals,
        'technical_signals': tech_signals,
        'holy_grail_signals': holy_grail_signals
    }


def main():
    """Main entry point"""
    logger.info("🚀 COMBINED STRATEGY ANALYSIS")
    logger.info("=" * 80)
    logger.info("")
    
    # Initialize engines
    config = TradingConfig()
    symbols = config.symbols  # ['SPY', 'QQQ']
    
    logger.info("🔧 Initializing engines...")
    
    # Load API key from config
    from chartexchange_config import CHARTEXCHANGE_API_KEY
    
    institutional_engine = UltraInstitutionalEngine(api_key=CHARTEXCHANGE_API_KEY)
    inst_signal_gen = SignalGenerator()
    tech_engine = TechnicalStrategyEngine(min_confidence=0.60)
    logger.info("")
    
    # Analyze each symbol
    all_results = []
    
    for symbol in symbols:
        result = analyze_symbol(symbol, institutional_engine, inst_signal_gen, tech_engine)
        all_results.append(result)
    
    # Final summary
    logger.info("=" * 80)
    logger.info("📊 FINAL SUMMARY")
    logger.info("=" * 80)
    logger.info("")
    
    total_inst = sum(len(r['institutional_signals']) for r in all_results)
    total_tech = sum(len(r['technical_signals']) for r in all_results)
    total_holy_grail = sum(len(r['holy_grail_signals']) for r in all_results)
    
    logger.info(f"  Institutional Signals: {total_inst}")
    logger.info(f"  Technical Signals: {total_tech}")
    logger.info(f"  🔥 HOLY GRAIL Signals: {total_holy_grail}")
    logger.info("")
    
    if total_holy_grail > 0:
        logger.info("  🎯 ACTIONABLE TRADES (Both strategies agree):")
        for result in all_results:
            for hg in result['holy_grail_signals']:
                logger.info(f"     → {hg['action']} {hg['symbol']} (Combined: {hg['combined_confidence']:.0f}%)")
    else:
        logger.info("  ⏳ No high-conviction trades at this time")
        logger.info("     Wait for institutional + technical alignment")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ Analysis complete!")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()

