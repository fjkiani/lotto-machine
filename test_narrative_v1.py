#!/usr/bin/env python3
"""
V1 Narrative Pipeline Test Script

Tests all components of the V1 narrative engine:
1. EventLoader (economic calendar)
2. Perplexity (real-time news)
3. Crypto correlation
4. Institutional context
5. Divergence detection
6. LLM synthesis
7. Full pipeline
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
load_dotenv()


def test_env_vars():
    """Test required environment variables"""
    print("\n" + "=" * 60)
    print("🔑 TESTING ENVIRONMENT VARIABLES")
    print("=" * 60)
    
    required = {
        'PERPLEXITY_API_KEY': os.getenv('PERPLEXITY_API_KEY'),
        'CHARTEXCHANGE_API_KEY': os.getenv('CHARTEXCHANGE_API_KEY'),
    }
    
    optional = {
        'RAPIDAPI_KEY': os.getenv('RAPIDAPI_KEY'),
        'GOOGLE_API_KEY': os.getenv('GOOGLE_API_KEY'),  # For Gemini (optional)
    }
    
    print("   Required:")
    for key, value in required.items():
        status = "✅" if value else "❌"
        val_preview = f"...{value[-8:]}" if value else "NOT SET"
        print(f"   {status} {key}: {val_preview}")
    
    print("   Optional:")
    for key, value in optional.items():
        status = "✅" if value else "⚠️"
        val_preview = f"...{value[-8:]}" if value else "NOT SET"
        print(f"   {status} {key}: {val_preview}")
    
    # Only required keys need to be set
    return all(required.values())


def test_event_loader():
    """Test EventLoader (Baby-Pips API)"""
    print("\n" + "=" * 60)
    print("📅 TESTING EVENT LOADER (Baby-Pips API)")
    print("=" * 60)
    
    try:
        from live_monitoring.enrichment.apis.event_loader import EventLoader
        
        loader = EventLoader()
        today = datetime.now().strftime('%Y-%m-%d')
        
        print(f"   Loading events for: {today}")
        events = loader.load_events(today)
        
        if events:
            macro_events = events.get('macro_events', [])
            print(f"   ✅ Loaded {len(macro_events)} macro events")
            print(f"   OPEX: {events.get('opex', False)}")
            print(f"   Has Events: {events.get('has_events', False)}")
            
            if macro_events:
                print("\n   📊 Today's Events:")
                for evt in macro_events[:5]:  # Show first 5
                    name = evt.get('name', evt.get('title', 'Unknown'))
                    time = evt.get('time', 'N/A')
                    impact = evt.get('impact', 'N/A')
                    print(f"      • {time} | {name} | Impact: {impact}")
            else:
                print("   ⚠️  No macro events today (or market closed)")
            
            return True
        else:
            print("   ❌ No events returned")
            return False
            
    except Exception as e:
        print(f"   ❌ EventLoader FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_perplexity():
    """Test Perplexity search"""
    print("\n" + "=" * 60)
    print("🔍 TESTING PERPLEXITY SEARCH")
    print("=" * 60)
    
    try:
        from live_monitoring.enrichment.apis.perplexity_search import PerplexitySearchClient
        
        client = PerplexitySearchClient()
        query = "What happened in US stock markets today? Focus on SPY, macro news, and Fed commentary."
        
        print(f"   Query: {query[:80]}...")
        result = client.search(query)
        
        if result:
            content = result.get('content', result.get('answer', ''))
            if content:
                print(f"   ✅ Got response ({len(content)} chars)")
                print(f"\n   📰 Preview:")
                print(f"   {content[:500]}...")
                return True
            else:
                print("   ❌ Empty response")
                return False
        else:
            print("   ❌ No response from Perplexity")
            return False
            
    except Exception as e:
        print(f"   ❌ Perplexity FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_crypto_correlation():
    """Test crypto correlation detector"""
    print("\n" + "=" * 60)
    print("₿ TESTING CRYPTO CORRELATION")
    print("=" * 60)
    
    try:
        from live_monitoring.enrichment.pipeline.crypto_analyzer import analyze_crypto_correlation
        
        result = analyze_crypto_correlation("SPY", datetime.now().strftime('%Y-%m-%d'))
        
        if result:
            regime = result.get('regime', 'UNKNOWN')
            btc_change = result.get('btc_change', 0)
            correlation = result.get('correlation', 0)
            
            print(f"   ✅ Crypto analysis complete")
            print(f"   📊 Regime: {regime}")
            # Handle both float and string values
            try:
                print(f"   📈 BTC Change: {float(btc_change):.2f}%")
            except:
                print(f"   📈 BTC Change: {btc_change}")
            try:
                print(f"   📉 Correlation: {float(correlation):.2f}")
            except:
                print(f"   📉 Correlation: {correlation}")
            return True
        else:
            print("   ❌ No result")
            return False
            
    except Exception as e:
        print(f"   ❌ Crypto correlation FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_institutional_context():
    """Test institutional context loader"""
    print("\n" + "=" * 60)
    print("🏦 TESTING INSTITUTIONAL CONTEXT")
    print("=" * 60)
    
    try:
        from live_monitoring.enrichment.pipeline.institutional_loader import load_institutional_context
        
        today = datetime.now().strftime('%Y-%m-%d')
        ctx = load_institutional_context("SPY", today, "NEUTRAL")
        
        if ctx:
            print(f"   ✅ Institutional context loaded")
            
            # Dark Pool
            dp = ctx.get('dark_pool', {})
            if dp:
                print(f"   📊 Dark Pool:")
                print(f"      • DP %: {dp.get('pct', 'N/A')}")
                print(f"      • Buy/Sell Ratio: {dp.get('buy_sell_ratio', 'N/A')}")
            
            # Gamma
            gamma = ctx.get('gamma', {})
            if gamma:
                print(f"   📊 Gamma:")
                print(f"      • Max Pain: ${gamma.get('max_pain', 'N/A')}")
                print(f"      • GEX: {gamma.get('gex', 'N/A')}")
            
            # VIX
            vix = ctx.get('vix', 'N/A')
            print(f"   📊 VIX: {vix}")
            
            return True
        else:
            print("   ❌ No context returned")
            return False
            
    except Exception as e:
        print(f"   ❌ Institutional context FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_divergence_detection():
    """Test divergence detection"""
    print("\n" + "=" * 60)
    print("⚠️  TESTING DIVERGENCE DETECTION")
    print("=" * 60)
    
    try:
        from live_monitoring.enrichment.pipeline.institutional_loader import detect_divergences
        
        # Mock institutional context
        mock_inst = {
            'dark_pool': {'pct': 45, 'buy_sell_ratio': 0.7},  # Sell-heavy
            'gamma': {'max_pain': 660},
            'vix': 22,
            'date': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Mock Perplexity narrative (bullish headlines but DP is selling)
        mock_pplx = {
            'macro': 'Markets rally on optimism, investors buying the dip',
            'sector': 'Tech leads rally',
            'asset': 'SPY hits new highs',
            'cross': 'Risk-on sentiment'
        }
        
        result = detect_divergences("SPY", mock_inst, mock_pplx)
        
        if result:
            detected = result.get('detected', [])
            print(f"   ✅ Divergence detection complete")
            print(f"   📊 Divergences found: {len(detected)}")
            
            for div in detected:
                print(f"      • {div.get('type', 'Unknown')}: {div.get('reason', 'N/A')}")
            
            return True
        else:
            print("   ❌ No result")
            return False
            
    except Exception as e:
        print(f"   ❌ Divergence detection FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_pipeline():
    """Test full market narrative pipeline"""
    print("\n" + "=" * 60)
    print("🧠 TESTING FULL NARRATIVE PIPELINE")
    print("=" * 60)
    
    try:
        from live_monitoring.enrichment.market_narrative_pipeline import market_narrative_pipeline
        
        today = datetime.now().strftime('%Y-%m-%d')
        print(f"   Running pipeline for SPY on {today}...")
        print("   (This may take 30-60 seconds)\n")
        
        narrative = market_narrative_pipeline("SPY", today, enable_logging=True)
        
        if narrative:
            print(f"   ✅ NARRATIVE PIPELINE COMPLETE")
            print(f"\n   📊 RESULTS:")
            print(f"   {'='*50}")
            print(f"   Symbol: {narrative.symbol}")
            print(f"   Date: {narrative.date}")
            print(f"   Direction: {narrative.overall_direction}")
            print(f"   Conviction: {narrative.conviction}")
            print(f"   Risk Environment: {narrative.risk_environment}")
            print(f"   Duration: {narrative.duration}")
            print(f"\n   📝 Causal Chain:")
            print(f"   {narrative.causal_chain}")
            print(f"\n   📰 Macro Narrative (preview):")
            print(f"   {narrative.macro_narrative[:500]}..." if narrative.macro_narrative else "   N/A")
            
            # Divergences
            if narrative.divergences:
                print(f"\n   ⚠️  Divergences Detected ({len(narrative.divergences)}):")
                for div in narrative.divergences[:3]:
                    print(f"      • {div.get('type', 'Unknown')}")
            
            # Sources
            if narrative.sources:
                print(f"\n   📚 Sources ({len(narrative.sources)}):")
                for src in narrative.sources[:3]:
                    print(f"      • {src.url[:60]}...")
            
            # Uncertainties
            if narrative.uncertainties:
                print(f"\n   ❓ Uncertainties ({len(narrative.uncertainties)}):")
                for unc in narrative.uncertainties[:3]:
                    print(f"      • {unc}")
            
            return True
        else:
            print("   ❌ No narrative returned")
            return False
            
    except Exception as e:
        print(f"   ❌ Pipeline FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_logs():
    """Check if narrative logs were created"""
    print("\n" + "=" * 60)
    print("📁 CHECKING LOG FILES")
    print("=" * 60)
    
    today = datetime.now().strftime('%Y-%m-%d')
    log_dir = project_root / 'logs' / 'narratives' / today
    
    if log_dir.exists():
        files = list(log_dir.glob('*.json'))
        print(f"   ✅ Log directory exists: {log_dir}")
        print(f"   📄 Files found: {len(files)}")
        for f in files:
            print(f"      • {f.name}")
        return len(files) > 0
    else:
        print(f"   ❌ Log directory not found: {log_dir}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🧪 V1 NARRATIVE PIPELINE TEST SUITE")
    print("=" * 60)
    print(f"   Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Purpose: Verify all V1 narrative components work")
    
    results = {}
    
    # 1. Environment
    results['env'] = test_env_vars()
    
    # 2. Event Loader
    results['events'] = test_event_loader()
    
    # 3. Perplexity
    results['perplexity'] = test_perplexity()
    
    # 4. Crypto
    results['crypto'] = test_crypto_correlation()
    
    # 5. Institutional
    results['institutional'] = test_institutional_context()
    
    # 6. Divergence
    results['divergence'] = test_divergence_detection()
    
    # 7. Full Pipeline (only if env vars are set)
    if results['env'] and results['perplexity']:
        results['pipeline'] = test_full_pipeline()
        results['logs'] = check_logs()
    else:
        print("\n⚠️  Skipping full pipeline test (missing API keys)")
        results['pipeline'] = False
        results['logs'] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} | {test}")
    
    print(f"\n   Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n   🎉 ALL TESTS PASSED - V1 NARRATIVE PIPELINE OPERATIONAL!")
    else:
        print("\n   ⚠️  Some tests failed - check logs above")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

