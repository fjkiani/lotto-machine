#!/usr/bin/env python3
"""
🎯 CAPABILITY TESTING - MODULE BY MODULE 🎯

Tests each module individually to understand:
1. What edge does this module provide?
2. Does it work standalone?
3. What inputs/outputs does it need?
4. How does it contribute to the lotto machine?

Run: python3 test_capabilities.py [module_name]

Author: Zo
Date: 2025-12-05
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json

sys.path.insert(0, str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'core'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'enrichment'))
sys.path.append(str(Path(__file__).parent / 'configs'))

from configs.chartexchange_config import get_api_key

# Test results storage
CAPABILITY_RESULTS = {}


def test_dark_pool_intelligence():
    """Test: Dark Pool Intelligence Module"""
    print("\n" + "="*70)
    print("1️⃣ DARK POOL INTELLIGENCE")
    print("="*70)
    
    from core.ultra_institutional_engine import UltraInstitutionalEngine
    
    api_key = get_api_key()
    engine = UltraInstitutionalEngine(api_key)
    
    symbol = "SPY"
    # Use yesterday's date (T+1 for DP data)
    date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"\n📊 Testing: {symbol} on {date}")
    print(f"   (Using yesterday's date - DP data is T+1)")
    
    try:
        context = engine.build_institutional_context(symbol, date)
        
        if context:
            print(f"\n✅ MODULE WORKS")
            print(f"\n📈 EDGE PROVIDED:")
            print(f"   • Identifies {len(context.dp_battlegrounds)} institutional battlegrounds")
            if context.dp_battlegrounds:
                print(f"      Levels: {[f'${b:.2f}' for b in sorted(context.dp_battlegrounds)[:5]]}")
            else:
                print(f"      ⚠️  No battlegrounds found (threshold may be too high)")
            print(f"   • Tracks {context.dp_total_volume:,} shares in dark pools")
            print(f"   • Calculates buy/sell ratio: {context.dp_buy_sell_ratio:.2f}")
            print(f"   • Measures dark pool %: {context.dark_pool_pct:.2f}%")
            print(f"   • Avg print size: {context.dp_avg_print_size:,.0f} shares")
            
            # Verify data consistency
            if context.dp_total_volume == 0:
                print(f"\n⚠️  WARNING: DP volume is 0")
                print(f"   This may indicate:")
                print(f"   - API data not available for this date")
                print(f"   - Data structure changed")
                print(f"   - Need to check raw API response")
            
            print(f"\n💡 EDGE EXPLANATION:")
            print(f"   Dark pools show where institutions are positioning.")
            print(f"   Battlegrounds = price levels with high institutional interest.")
            print(f"   Buy/sell ratio = institutional sentiment.")
            print(f"   Edge: Trade WITH institutions, not against them.")
            
            CAPABILITY_RESULTS['dark_pool_intelligence'] = {
                'status': 'WORKING',
                'edge': 'Institutional positioning visibility',
                'battlegrounds': len(context.dp_battlegrounds),
                'battleground_levels': [float(b) for b in context.dp_battlegrounds] if context.dp_battlegrounds else [],
                'dp_volume': context.dp_total_volume,
                'buy_sell_ratio': context.dp_buy_sell_ratio,
                'dark_pool_pct': context.dark_pool_pct,
                'avg_print_size': context.dp_avg_print_size
            }
        else:
            print(f"\n❌ MODULE FAILED - No context built")
            print(f"   Possible reasons:")
            print(f"   - API errors")
            print(f"   - Date has no data")
            print(f"   - Exception in build_institutional_context")
            CAPABILITY_RESULTS['dark_pool_intelligence'] = {'status': 'FAILED'}
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        print(f"\nFull traceback:")
        traceback.print_exc()
        CAPABILITY_RESULTS['dark_pool_intelligence'] = {'status': 'ERROR', 'error': str(e)}


def test_signal_generation():
    """Test: Signal Generation Module"""
    print("\n" + "="*70)
    print("2️⃣ SIGNAL GENERATION")
    print("="*70)
    
    from core.ultra_institutional_engine import UltraInstitutionalEngine
    from live_monitoring.core.signal_generator import SignalGenerator
    
    api_key = get_api_key()
    engine = UltraInstitutionalEngine(api_key)
    sig_gen = SignalGenerator(api_key=api_key)
    
    symbol = "SPY"
    date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    price = 684.50  # Mock price
    
    print(f"\n📊 Testing: {symbol} @ ${price}")
    
    try:
        # Build context
        context = engine.build_institutional_context(symbol, date)
        
        if context:
            # Debug: Show context values
            print(f"\n📊 Context Values:")
            print(f"   • Buying Pressure: {context.institutional_buying_pressure:.0%}")
            print(f"   • Squeeze Potential: {context.squeeze_potential:.0%}")
            print(f"   • Gamma Pressure: {context.gamma_pressure:.0%}")
            print(f"   • DP Buy/Sell Ratio: {context.dp_buy_sell_ratio:.2f}")
            print(f"   • Dark Pool %: {context.dark_pool_pct:.2f}%")
            
            # Generate signals
            signals = sig_gen.generate_signals(symbol, price, context, account_value=100000.0)
            
            print(f"\n✅ MODULE WORKS")
            print(f"\n📈 EDGE PROVIDED:")
            print(f"   • Generated {len(signals)} signals")
            
            master_signals = [s for s in signals if hasattr(s, 'confidence') and s.confidence >= 0.75]
            print(f"   • Master signals (75%+): {len(master_signals)}")
            
            if signals:
                for s in signals[:3]:
                    sig_type = getattr(s, 'signal_type', 'UNKNOWN')
                    action = getattr(s, 'action', 'UNKNOWN')
                    conf = getattr(s, 'confidence', 0.0)
                    print(f"   • {sig_type}: {action} @ {conf:.0%} confidence")
            else:
                print(f"   ⚠️  No signals generated - thresholds may be too high")
                print(f"      (Buying pressure: {context.institutional_buying_pressure:.0%}, needs >= 50%)")
            
            print(f"\n💡 EDGE EXPLANATION:")
            print(f"   Combines multiple factors:")
            print(f"   • Dark pool battlegrounds → Entry/exit levels")
            print(f"   • Short interest → Squeeze potential")
            print(f"   • Options flow → Gamma pressure")
            print(f"   • Multi-factor confidence scoring")
            print(f"   Edge: Only trades when multiple factors align")
            
            CAPABILITY_RESULTS['signal_generation'] = {
                'status': 'WORKING',
                'edge': 'Multi-factor signal filtering',
                'signals_generated': len(signals),
                'master_signals': len(master_signals)
            }
        else:
            print(f"\n❌ MODULE FAILED - No context")
            CAPABILITY_RESULTS['signal_generation'] = {'status': 'FAILED'}
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        CAPABILITY_RESULTS['signal_generation'] = {'status': 'ERROR', 'error': str(e)}


def test_volume_profile():
    """Test: Volume Profile Timing Module"""
    print("\n" + "="*70)
    print("3️⃣ VOLUME PROFILE TIMING")
    print("="*70)
    
    from live_monitoring.core.volume_profile import VolumeProfileAnalyzer
    
    api_key = get_api_key()
    analyzer = VolumeProfileAnalyzer(api_key=api_key)
    
    symbol = "SPY"
    date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"\n📊 Testing: {symbol} on {date}")
    
    try:
        profile = analyzer.fetch_intraday_volume(symbol, date)
        
        if profile:
            should_trade, reason = analyzer.should_trade_now(profile)
            
            print(f"\n✅ MODULE WORKS")
            print(f"\n📈 EDGE PROVIDED:")
            print(f"   • Identifies peak institutional times")
            print(f"   • Flags low liquidity periods")
            print(f"   • Current recommendation: {'TRADE' if should_trade else 'WAIT'}")
            print(f"   • Reason: {reason}")
            
            print(f"\n💡 EDGE EXPLANATION:")
            print(f"   Institutions trade at specific times.")
            print(f"   High off-exchange % = institutional activity.")
            print(f"   Edge: Enter when institutions are active (better fills, less slippage)")
            
            CAPABILITY_RESULTS['volume_profile'] = {
                'status': 'WORKING',
                'edge': 'Optimal entry timing',
                'should_trade': should_trade,
                'reason': reason
            }
        else:
            print(f"\n⚠️ MODULE PARTIAL - No profile data (may need T+1)")
            CAPABILITY_RESULTS['volume_profile'] = {'status': 'PARTIAL'}
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        CAPABILITY_RESULTS['volume_profile'] = {'status': 'ERROR', 'error': str(e)}


def test_stock_screener():
    """Test: Stock Screener Module"""
    print("\n" + "="*70)
    print("4️⃣ STOCK SCREENER")
    print("="*70)
    
    from live_monitoring.core.stock_screener import InstitutionalScreener
    
    api_key = get_api_key()
    screener = InstitutionalScreener(api_key=api_key)
    
    print(f"\n📊 Testing: High institutional flow tickers")
    
    try:
        results = screener.screen_high_flow_tickers(
            min_price=20.0,
            min_volume=5_000_000,
            max_results=10
        )
        
        print(f"\n✅ MODULE WORKS")
        print(f"\n📈 EDGE PROVIDED:")
        print(f"   • Discovered {len(results)} high-flow tickers")
        
        if results:
            for r in results[:5]:
                print(f"   • {r.symbol}: Score {r.institutional_score:.0f}/100")
        
        print(f"\n💡 EDGE EXPLANATION:")
        print(f"   Finds tickers with high institutional activity.")
        print(f"   Beyond SPY/QQQ, discovers opportunities.")
        print(f"   Edge: Expand universe to high-probability setups")
        
        CAPABILITY_RESULTS['stock_screener'] = {
            'status': 'WORKING',
            'edge': 'Ticker discovery',
            'tickers_found': len(results)
        }
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        CAPABILITY_RESULTS['stock_screener'] = {'status': 'ERROR', 'error': str(e)}


def test_gamma_exposure():
    """Test: Gamma Exposure Module"""
    print("\n" + "="*70)
    print("5️⃣ GAMMA EXPOSURE TRACKING")
    print("="*70)
    
    from live_monitoring.core.gamma_exposure import GammaExposureTracker
    
    api_key = get_api_key()
    tracker = GammaExposureTracker(api_key=api_key)
    
    symbol = "SPY"
    date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"\n📊 Testing: {symbol} on {date}")
    
    try:
        gamma_data = tracker.calculate_gamma_exposure(symbol, date)
        
        if gamma_data:
            print(f"\n✅ MODULE WORKS")
            print(f"\n📈 EDGE PROVIDED:")
            print(f"   • Gamma flip level: ${gamma_data.get('gamma_flip_level', 'N/A')}")
            print(f"   • Current regime: {gamma_data.get('current_regime', 'N/A')}")
            print(f"   • Total GEX: {gamma_data.get('total_gex', 0):,.0f}")
            
            print(f"\n💡 EDGE EXPLANATION:")
            print(f"   Positive gamma = dealers stabilize price (buy dips, sell rallies)")
            print(f"   Negative gamma = dealers amplify moves (sell dips, buy rallies)")
            print(f"   Edge: Trade WITH gamma regime for better entries")
            
            CAPABILITY_RESULTS['gamma_exposure'] = {
                'status': 'WORKING',
                'edge': 'Dealer positioning awareness',
                'regime': gamma_data.get('current_regime', 'UNKNOWN')
            }
        else:
            print(f"\n⚠️ MODULE PARTIAL - Options data may be limited")
            CAPABILITY_RESULTS['gamma_exposure'] = {'status': 'PARTIAL'}
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        CAPABILITY_RESULTS['gamma_exposure'] = {'status': 'ERROR', 'error': str(e)}


def test_volatility_expansion():
    """Test: Volatility Expansion Detector"""
    print("\n" + "="*70)
    print("6️⃣ VOLATILITY EXPANSION DETECTOR")
    print("="*70)
    
    from live_monitoring.core.volatility_expansion import VolatilityExpansionDetector
    import yfinance as yf
    import pandas as pd
    
    detector = VolatilityExpansionDetector()
    
    symbol = "SPY"
    
    print(f"\n📊 Testing: {symbol}")
    
    try:
        # Get minute bars for volatility calculation
        ticker = yf.Ticker(symbol)
        minute_bars = ticker.history(period='1d', interval='1m')
        
        if minute_bars.empty or len(minute_bars) < 30:
            print(f"\n⚠️  MODULE PARTIAL - Need 30+ minute bars, got {len(minute_bars)}")
            CAPABILITY_RESULTS['volatility_expansion'] = {'status': 'PARTIAL', 'reason': 'Insufficient data'}
            return
        
        status = detector.detect_expansion(symbol, minute_bars, lookback_minutes=30)
        
        if status:
            print(f"\n✅ MODULE WORKS")
            print(f"\n📈 EDGE PROVIDED:")
            print(f"   • Compression detected: {status.compression_detected}")
            print(f"   • Expansion detected: {status.expansion_detected}")
            print(f"   • Lottery potential: {status.lottery_potential}")
            print(f"   • Current IV: {status.current_iv:.1f}%")
            print(f"   • Average IV: {status.avg_iv:.1f}%")
            print(f"   • Status: {status.status}")
            
            print(f"\n💡 EDGE EXPLANATION:")
            print(f"   Detects IV compression (calm before storm)")
            print(f"   Detects IV expansion (volatility spike starting)")
            print(f"   Edge: Catch moves BEFORE they happen (lottery plays)")
            
            CAPABILITY_RESULTS['volatility_expansion'] = {
                'status': 'WORKING',
                'edge': 'Pre-move detection',
                'lottery_potential': status.lottery_potential
            }
        else:
            print(f"\n⚠️ MODULE PARTIAL - May need more data")
            CAPABILITY_RESULTS['volatility_expansion'] = {'status': 'PARTIAL'}
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        CAPABILITY_RESULTS['volatility_expansion'] = {'status': 'ERROR', 'error': str(e)}


def test_zero_dte_strategy():
    """Test: ZeroDTE Strategy Module"""
    print("\n" + "="*70)
    print("7️⃣ ZERO DTE STRATEGY")
    print("="*70)
    
    from live_monitoring.core.zero_dte_strategy import ZeroDTEStrategy
    
    strategy = ZeroDTEStrategy()
    
    print(f"\n📊 Testing: Convert signal to 0DTE trade")
    
    try:
        # Mock signal
        trade = strategy.convert_signal_to_0dte(
            signal_symbol='SPY',
            signal_action='BUY',
            signal_confidence=0.85,
            current_price=684.50,
            account_value=100000.0
        )
        
        if trade:
            print(f"\n✅ MODULE WORKS")
            print(f"\n📈 EDGE PROVIDED:")
            if trade.strike_recommendation:
                print(f"   • Strike selected: ${trade.strike_recommendation.strike:.2f}")
                print(f"   • Option type: {trade.strike_recommendation.option_type}")
                print(f"   • Premium: ${trade.strike_recommendation.premium:.2f}")
                print(f"   • Lottery potential: {trade.strike_recommendation.lottery_potential}")
            print(f"   • Position size: {trade.position_size_pct:.1%}")
            print(f"   • Max risk: ${trade.max_risk_dollars:.2f}")
            print(f"   • Is valid: {trade.is_valid}")
            if not trade.is_valid:
                print(f"   • Rejection reason: {trade.rejection_reason}")
            
            print(f"\n💡 EDGE EXPLANATION:")
            print(f"   Converts regular signals to 0DTE options.")
            print(f"   Deep OTM strikes for lottery potential (10-50x).")
            print(f"   Edge: Amplify winners with options leverage")
            
            CAPABILITY_RESULTS['zero_dte_strategy'] = {
                'status': 'WORKING',
                'edge': 'Options leverage for lottery plays',
                'is_valid': trade.is_valid,
                'has_strike': trade.strike_recommendation is not None
            }
        else:
            print(f"\n⚠️ MODULE PARTIAL - May need options data")
            CAPABILITY_RESULTS['zero_dte_strategy'] = {'status': 'PARTIAL'}
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        CAPABILITY_RESULTS['zero_dte_strategy'] = {'status': 'ERROR', 'error': str(e)}


def test_narrative_enrichment():
    """Test: Narrative Enrichment Module"""
    print("\n" + "="*70)
    print("8️⃣ NARRATIVE ENRICHMENT")
    print("="*70)
    
    try:
        from live_monitoring.enrichment.narrative_agent import NarrativeAgent
        
        agent = NarrativeAgent(api_key=os.getenv('GEMINI_API_KEY'))
        
        print(f"\n📊 Testing: Narrative generation")
        
        # Mock signal
        from live_monitoring.enrichment.models.enriched_signal import EnrichedSignal, SignalType
        
        mock_signal = EnrichedSignal(
            symbol="SPY",
            signal_type=SignalType.BREAKOUT,
            action="BUY",
            entry_price=684.50,
            confidence=0.75
        )
        
        analysis = agent.analyze_selloff(mock_signal)
        
        if analysis:
            print(f"\n✅ MODULE WORKS")
            print(f"\n📈 EDGE PROVIDED:")
            print(f"   • Narrative generated: {analysis.narrative[:100]}...")
            print(f"   • Direction: {analysis.direction}")
            print(f"   • Conviction: {analysis.conviction}")
            
            print(f"\n💡 EDGE EXPLANATION:")
            print(f"   LLM explains WHY market is moving.")
            print(f"   Provides context beyond numbers.")
            print(f"   Edge: Understand market psychology and catalysts")
            
            CAPABILITY_RESULTS['narrative_enrichment'] = {
                'status': 'WORKING',
                'edge': 'Market context understanding',
                'conviction': analysis.conviction
            }
        else:
            print(f"\n⚠️ MODULE PARTIAL - May need API key")
            CAPABILITY_RESULTS['narrative_enrichment'] = {'status': 'PARTIAL'}
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        CAPABILITY_RESULTS['narrative_enrichment'] = {'status': 'ERROR', 'error': str(e)}


def test_price_action_filter():
    """Test: Price Action Filter"""
    print("\n" + "="*70)
    print("9️⃣ PRICE ACTION FILTER")
    print("="*70)
    
    from live_monitoring.core.price_action_filter import PriceActionFilter
    
    filter_obj = PriceActionFilter()
    
    print(f"\n📊 Testing: Signal confirmation")
    
    try:
        # Mock signal
        from dataclasses import dataclass
        
        @dataclass
        class MockSignal:
            symbol: str = "SPY"
            action: str = "BUY"
            entry_price: float = 684.50
            confidence: float = 0.75
        
        signal = MockSignal()
        
        # PriceActionFilter gets price from yfinance, doesn't need current_price param
        confirmation = filter_obj.confirm_signal(signal, lookback_minutes=30)
        
        print(f"\n✅ MODULE WORKS")
        print(f"\n📈 EDGE PROVIDED:")
        print(f"   • Confirmation: {'YES' if confirmation.confirmed else 'NO'}")
        print(f"   • Reason: {confirmation.reason}")
        print(f"   • Current price: ${confirmation.current_price:.2f}")
        print(f"   • Distance from entry: {confirmation.distance_from_entry_pct:.2%}")
        print(f"   • Volume spike: {confirmation.volume_spike}")
        print(f"   • Regime: {confirmation.regime}")
        
        print(f"\n💡 EDGE EXPLANATION:")
        print(f"   Confirms signal with real-time price action.")
        print(f"   Checks: Price proximity, volume spike, candlestick patterns.")
        print(f"   Edge: Only trade when price action confirms setup")
        
        CAPABILITY_RESULTS['price_action_filter'] = {
            'status': 'WORKING',
            'edge': 'Real-time confirmation',
            'confirmed': confirmation.confirmed
        }
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        CAPABILITY_RESULTS['price_action_filter'] = {'status': 'ERROR', 'error': str(e)}


def test_risk_manager():
    """Test: Risk Manager"""
    print("\n" + "="*70)
    print("🔟 RISK MANAGER")
    print("="*70)
    
    from live_monitoring.core.risk_manager import RiskManager, RiskLimits
    
    limits = RiskLimits()
    rm = RiskManager(limits=limits, initial_capital=100000.0)
    
    print(f"\n📊 Testing: Risk limits")
    
    try:
        can_open, reason = rm.can_open_position("SPY", 0.02)
        
        print(f"\n✅ MODULE WORKS")
        print(f"\n📈 EDGE PROVIDED:")
        print(f"   • Max positions: {limits.max_open_positions}")
        print(f"   • Max correlated: {limits.max_correlated_positions}")
        print(f"   • Circuit breaker: {limits.circuit_breaker_pnl_pct:.0%}")
        print(f"   • Can open position: {can_open}")
        
        print(f"\n💡 EDGE EXPLANATION:")
        print(f"   Hard limits prevent catastrophic losses.")
        print(f"   Position sizing based on account value.")
        print(f"   Edge: Survive to trade another day")
        
        CAPABILITY_RESULTS['risk_manager'] = {
            'status': 'WORKING',
            'edge': 'Capital preservation',
            'max_positions': limits.max_open_positions
        }
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        CAPABILITY_RESULTS['risk_manager'] = {'status': 'ERROR', 'error': str(e)}


def print_summary():
    """Print capability summary"""
    print("\n" + "="*70)
    print("📊 CAPABILITY SUMMARY")
    print("="*70)
    
    working = sum(1 for r in CAPABILITY_RESULTS.values() if r.get('status') == 'WORKING')
    partial = sum(1 for r in CAPABILITY_RESULTS.values() if r.get('status') == 'PARTIAL')
    failed = sum(1 for r in CAPABILITY_RESULTS.values() if r.get('status') in ['FAILED', 'ERROR'])
    
    print(f"\n✅ Working: {working}")
    print(f"⚠️  Partial: {partial}")
    print(f"❌ Failed: {failed}")
    
    print(f"\n📋 EDGE BREAKDOWN:")
    for name, result in CAPABILITY_RESULTS.items():
        status = result.get('status', 'UNKNOWN')
        edge = result.get('edge', 'Unknown edge')
        print(f"   {name}: {status} - {edge}")
    
    # Save results
    results_file = Path("logs/capability_results.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(results_file, "w") as f:
        json.dump(CAPABILITY_RESULTS, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {results_file}")


def main():
    """Run all capability tests"""
    
    print("\n" + "🔥" * 35)
    print("   CAPABILITY TESTING - MODULE BY MODULE")
    print("🔥" * 35)
    print("\nTesting each module to understand what edge it provides...")
    
    # Test all modules
    test_dark_pool_intelligence()
    test_signal_generation()
    test_volume_profile()
    test_stock_screener()
    test_gamma_exposure()
    test_volatility_expansion()
    test_zero_dte_strategy()
    test_narrative_enrichment()
    test_price_action_filter()
    test_risk_manager()
    
    # Print summary
    print_summary()
    
    print("\n" + "="*70)
    print("🎯 NEXT: Document edge of each module and how they combine")
    print("="*70)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--module', help='Test specific module')
    args = parser.parse_args()
    
    if args.module:
        # Test single module
        module_map = {
            'dp': test_dark_pool_intelligence,
            'signals': test_signal_generation,
            'volume': test_volume_profile,
            'screener': test_stock_screener,
            'gamma': test_gamma_exposure,
            'vol': test_volatility_expansion,
            '0dte': test_zero_dte_strategy,
            'narrative': test_narrative_enrichment,
            'price': test_price_action_filter,
            'risk': test_risk_manager
        }
        
        if args.module in module_map:
            module_map[args.module]()
            print_summary()
        else:
            print(f"Unknown module: {args.module}")
            print(f"Available: {', '.join(module_map.keys())}")
    else:
        main()

