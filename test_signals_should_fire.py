"""
🔍 TEST WHAT SIGNALS SHOULD BE FIRING
Uses existing backtesting tools to diagnose why alerts aren't firing
"""

import os
import sys
from datetime import datetime

# Add paths
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backtesting'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backtesting', 'simulation'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backtesting', 'analysis'))

# Load .env
from dotenv import load_dotenv
load_dotenv()

def main():
    print("=" * 80)
    print("🔍 TESTING WHAT SIGNALS SHOULD BE FIRING RIGHT NOW")
    print("=" * 80)
    print()
    
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"📅 Date: {today}")
    print(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}")
    print()
    
    # 1. Test Direct API
    print("=" * 80)
    print("1️⃣  TESTING DIRECT API (What signals would fire?)")
    print("=" * 80)
    try:
        from backtesting.simulation.direct_api_test import DirectAPITester
        
        tester = DirectAPITester()
        signals = tester.test_today(['SPY', 'QQQ'])
        
        print()
        print(f"✅ Generated {len(signals)} signals from direct API test")
        if signals:
            print("\n📊 Top Signals:")
            for i, sig in enumerate(signals[:5], 1):
                print(f"  {i}. {sig.symbol} {sig.signal_type} @ ${sig.price:.2f}")
                print(f"     Direction: {sig.direction} | Confidence: {sig.confidence:.0f}%")
                print(f"     Entry: ${sig.entry:.2f} | Stop: ${sig.stop_loss:.2f} | Target: ${sig.take_profit:.2f}")
        else:
            print("⚠️  NO SIGNALS GENERATED from direct API test")
            print("   → This means either:")
            print("     1. Price is too far from DP levels (>1%)")
            print("     2. DP levels don't have enough volume")
            print("     3. API is returning no data")
    except Exception as e:
        print(f"❌ Error testing direct API: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("2️⃣  DIAGNOSING PRODUCTION (Why aren't alerts firing?)")
    print("=" * 80)
    try:
        from backtesting.analysis.diagnostics import ProductionDiagnostics
        
        diagnostics = ProductionDiagnostics()
        result = diagnostics.diagnose_date(today)
        
        print(f"\n📊 RTH Signals: {result.rth_signals}")
        print(f"📊 Non-RTH Signals: {result.non_rth_signals}")
        print()
        
        print("📦 Data Availability:")
        for source, available in result.data_availability.items():
            status = "✅" if available else "❌"
            print(f"  {status} {source}: {available}")
        print()
        
        print("🎯 Threshold Analysis:")
        print(f"  Synthesis fired: {result.threshold_analysis.get('synthesis_fired', False)}")
        print(f"  Narrative fired: {result.threshold_analysis.get('narrative_fired', False)}")
        print(f"  DP alerts fired: {result.threshold_analysis.get('dp_alerts_fired', False)}")
        print()
        
        if result.signal_generation_issues:
            print("❌ ISSUES FOUND:")
            for issue in result.signal_generation_issues:
                print(f"  • {issue}")
        else:
            print("✅ No issues detected")
        print()
        
        if result.recommendations:
            print("💡 RECOMMENDATIONS:")
            for rec in result.recommendations:
                print(f"  • {rec}")
    except Exception as e:
        print(f"❌ Error running diagnostics: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("3️⃣  CHECKING SYSTEM HEALTH")
    print("=" * 80)
    try:
        from backtesting.analysis.production_health import ProductionHealthMonitor
        
        health = ProductionHealthMonitor()
        status = health.check_health(today)
        
        print(f"\n🏥 System Health: {'✅ HEALTHY' if status.is_healthy else '❌ UNHEALTHY'}")
        print(f"📊 Uptime: {status.uptime_pct:.1f}%")
        print(f"📊 RTH Coverage: {status.rth_coverage:.1f}%")
        print()
        
        if status.issues:
            print("⚠️  ISSUES:")
            for issue in status.issues:
                print(f"  • {issue}")
        print()
        
        if status.recommendations:
            print("💡 RECOMMENDATIONS:")
            for rec in status.recommendations:
                print(f"  • {rec}")
    except Exception as e:
        print(f"❌ Error checking health: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("✅ DIAGNOSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()

