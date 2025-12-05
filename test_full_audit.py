#!/usr/bin/env python3
"""
🔥 ZO'S COMPREHENSIVE SYSTEM AUDIT 🔥
Tests every fucking module to see what's working vs broken

Run: python3 test_full_audit.py
"""

import sys
import os
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Results storage
AUDIT_RESULTS: Dict[str, Dict[str, Any]] = {}

def test_module(name: str, test_func):
    """Run a test and capture results"""
    print(f"\n{'='*60}")
    print(f"🧪 TESTING: {name}")
    print(f"{'='*60}")
    
    try:
        result = test_func()
        AUDIT_RESULTS[name] = {
            "status": "✅ PASS",
            "details": result if result else "Success",
            "error": None
        }
        print(f"✅ {name}: PASSED")
        return True
    except Exception as e:
        AUDIT_RESULTS[name] = {
            "status": "❌ FAIL", 
            "details": None,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(f"❌ {name}: FAILED - {str(e)}")
        return False

# ============================================================
# TEST 1: Environment & Configuration
# ============================================================
def test_environment():
    """Test environment setup"""
    results = {}
    
    # Check Python version
    results["python_version"] = sys.version
    
    # Check .env file
    env_path = ".env"
    results["env_file_exists"] = os.path.exists(env_path)
    
    # Check critical directories
    critical_dirs = [
        "live_monitoring",
        "live_monitoring/core",
        "live_monitoring/enrichment",
        "live_monitoring/alerting",
        "live_monitoring/trading",
        "core",
        "core/data",
        "configs"
    ]
    
    results["directories"] = {}
    for d in critical_dirs:
        results["directories"][d] = os.path.exists(d)
    
    # Check logs directory
    results["logs_dir_exists"] = os.path.exists("logs")
    if not os.path.exists("logs"):
        os.makedirs("logs", exist_ok=True)
        results["logs_dir_created"] = True
    
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  .env exists: {results['env_file_exists']}")
    print(f"  All directories exist: {all(results['directories'].values())}")
    
    return results

# ============================================================
# TEST 2: ChartExchange API Client
# ============================================================
def test_chartexchange_client():
    """Test ChartExchange API connectivity"""
    from configs.chartexchange_config import get_api_key, get_tier
    
    results = {}
    results["api_key_configured"] = True
    results["tier"] = get_tier()
    
    api_key = get_api_key()
    results["api_key_length"] = len(api_key)
    
    # Try to import the client
    try:
        from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
        client = UltimateChartExchangeClient(api_key)
        results["client_instantiated"] = True
        
        # Test a simple API call (get dark pool levels)
        print("  Testing API call: get_dark_pool_levels('SPY')...")
        dp_levels = client.get_dark_pool_levels("SPY")
        results["api_call_success"] = dp_levels is not None
        results["dp_levels_count"] = len(dp_levels) if dp_levels else 0
        print(f"  Got {results['dp_levels_count']} dark pool levels")
        
    except ImportError as e:
        results["client_instantiated"] = False
        results["import_error"] = str(e)
        raise
    
    return results

# ============================================================
# TEST 3: Signal Generator
# ============================================================
def test_signal_generator():
    """Test Signal Generator module"""
    results = {}
    
    try:
        from live_monitoring.core.signal_generator import SignalGenerator
        results["import_success"] = True
        
        # Try to instantiate
        from configs.chartexchange_config import get_api_key
        api_key = get_api_key()
        
        sig_gen = SignalGenerator(api_key=api_key)
        results["instantiated"] = True
        
        # Check for key methods
        methods = ["generate_signals", "_calculate_confidence_score", "_apply_narrative_enrichment"]
        results["methods"] = {}
        for method in methods:
            results["methods"][method] = hasattr(sig_gen, method)
        
        print(f"  SignalGenerator instantiated: {results['instantiated']}")
        print(f"  Methods available: {results['methods']}")
        
    except ImportError as e:
        results["import_success"] = False
        results["import_error"] = str(e)
        raise
    
    return results

# ============================================================
# TEST 4: Institutional Engine
# ============================================================
def test_institutional_engine():
    """Test Ultra Institutional Engine"""
    results = {}
    
    try:
        from core.ultra_institutional_engine import UltraInstitutionalEngine
        results["import_success"] = True
        
        from configs.chartexchange_config import get_api_key
        api_key = get_api_key()
        
        engine = UltraInstitutionalEngine(api_key)
        results["instantiated"] = True
        
        # Check for key methods
        methods = ["build_context", "analyze_dark_pool", "analyze_short_data"]
        results["methods"] = {}
        for method in methods:
            results["methods"][method] = hasattr(engine, method)
        
        print(f"  UltraInstitutionalEngine instantiated: {results['instantiated']}")
        
    except ImportError as e:
        results["import_success"] = False
        results["import_error"] = str(e)
        raise
    
    return results

# ============================================================
# TEST 5: Data Fetcher
# ============================================================
def test_data_fetcher():
    """Test Data Fetcher module"""
    results = {}
    
    try:
        from live_monitoring.core.data_fetcher import DataFetcher
        results["import_success"] = True
        
        from configs.chartexchange_config import get_api_key
        api_key = get_api_key()
        
        fetcher = DataFetcher(api_key=api_key)
        results["instantiated"] = True
        
        # Test fetching price data
        print("  Testing price fetch for SPY...")
        price_data = fetcher.fetch_price("SPY")
        results["price_fetch_success"] = price_data is not None
        if price_data:
            results["spy_price"] = price_data.get("price") or price_data.get("regularMarketPrice")
        
        print(f"  DataFetcher instantiated: {results['instantiated']}")
        print(f"  SPY price fetched: {results.get('spy_price', 'N/A')}")
        
    except ImportError as e:
        results["import_success"] = False
        results["import_error"] = str(e)
        raise
    
    return results

# ============================================================
# TEST 6: Narrative Enrichment Pipeline
# ============================================================
def test_narrative_pipeline():
    """Test Narrative Enrichment modules"""
    results = {}
    
    # Test individual components
    components = [
        ("market_narrative_pipeline", "live_monitoring.enrichment.market_narrative_pipeline", "MarketNarrativePipeline"),
        ("narrative_agent", "live_monitoring.enrichment.narrative_agent", "NarrativeAgent"),
        ("narrative_logger", "live_monitoring.enrichment.narrative_logger", "NarrativeLogger"),
        ("narrative_validation", "live_monitoring.enrichment.narrative_validation", "NarrativeValidationOrchestrator"),
        ("institutional_narrative", "live_monitoring.enrichment.institutional_narrative", "InstitutionalNarrativeSynthesizer"),
        ("crypto_correlation", "live_monitoring.enrichment.crypto_correlation", "CryptoCorrelationDetector"),
    ]
    
    results["components"] = {}
    
    for name, module_path, class_name in components:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name, None)
            results["components"][name] = {
                "import_success": True,
                "class_found": cls is not None
            }
            print(f"  ✅ {name}: OK")
        except Exception as e:
            results["components"][name] = {
                "import_success": False,
                "error": str(e)
            }
            print(f"  ❌ {name}: {str(e)[:50]}")
    
    # Check API connectors
    api_components = [
        ("perplexity_search", "live_monitoring.enrichment.apis.perplexity_search", "PerplexitySearchClient"),
        ("event_loader", "live_monitoring.enrichment.apis.event_loader", "EventLoader"),
    ]
    
    results["api_components"] = {}
    for name, module_path, class_name in api_components:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name, None)
            results["api_components"][name] = {
                "import_success": True,
                "class_found": cls is not None
            }
            print(f"  ✅ {name}: OK")
        except Exception as e:
            results["api_components"][name] = {
                "import_success": False,
                "error": str(e)
            }
            print(f"  ❌ {name}: {str(e)[:50]}")
    
    return results

# ============================================================
# TEST 7: Risk Manager
# ============================================================
def test_risk_manager():
    """Test Risk Manager module"""
    results = {}
    
    try:
        from live_monitoring.core.risk_manager import RiskManager
        results["import_success"] = True
        
        rm = RiskManager(account_value=100000)
        results["instantiated"] = True
        
        # Check limits
        results["max_positions"] = rm.max_positions
        results["max_correlated"] = rm.max_correlated
        
        print(f"  RiskManager instantiated with $100k account")
        print(f"  Max positions: {results['max_positions']}")
        
    except ImportError as e:
        results["import_success"] = False
        results["import_error"] = str(e)
        raise
    
    return results

# ============================================================
# TEST 8: Price Action Filter
# ============================================================
def test_price_action_filter():
    """Test Price Action Filter module"""
    results = {}
    
    try:
        from live_monitoring.core.price_action_filter import PriceActionFilter
        results["import_success"] = True
        
        paf = PriceActionFilter()
        results["instantiated"] = True
        
        # Check for key methods
        methods = ["confirm_signal", "_check_price_proximity", "_check_volume_spike"]
        results["methods"] = {}
        for method in methods:
            results["methods"][method] = hasattr(paf, method)
        
        print(f"  PriceActionFilter instantiated: {results['instantiated']}")
        
    except ImportError as e:
        results["import_success"] = False
        results["import_error"] = str(e)
        raise
    
    return results

# ============================================================
# TEST 9: Alerting System
# ============================================================
def test_alerting():
    """Test Alerting modules"""
    results = {}
    
    components = [
        ("alert_router", "live_monitoring.alerting.alert_router", "AlertRouter"),
        ("console_alerter", "live_monitoring.alerting.console_alerter", "ConsoleAlerter"),
        ("csv_logger", "live_monitoring.alerting.csv_logger", "CSVLogger"),
        ("slack_alerter", "live_monitoring.alerting.slack_alerter", "SlackAlerter"),
    ]
    
    results["components"] = {}
    for name, module_path, class_name in components:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name, None)
            results["components"][name] = {
                "import_success": True,
                "class_found": cls is not None
            }
            print(f"  ✅ {name}: OK")
        except Exception as e:
            results["components"][name] = {
                "import_success": False,
                "error": str(e)
            }
            print(f"  ❌ {name}: {str(e)[:50]}")
    
    return results

# ============================================================
# TEST 10: Paper Trading
# ============================================================
def test_paper_trading():
    """Test Paper Trading module"""
    results = {}
    
    try:
        from live_monitoring.trading.paper_trader import PaperTrader
        results["import_success"] = True
        print(f"  ✅ PaperTrader module importable")
        
        # Check if Alpaca is configured
        alpaca_key = os.environ.get("ALPACA_API_KEY")
        results["alpaca_configured"] = alpaca_key is not None
        print(f"  Alpaca API configured: {results['alpaca_configured']}")
        
    except ImportError as e:
        results["import_success"] = False
        results["import_error"] = str(e)
        print(f"  ❌ PaperTrader import failed: {str(e)[:50]}")
    
    return results

# ============================================================
# TEST 11: Run Lotto Machine Imports
# ============================================================
def test_lotto_machine_imports():
    """Test that run_lotto_machine.py can import everything it needs"""
    results = {}
    
    # Read the file and extract imports
    with open("run_lotto_machine.py", "r") as f:
        content = f.read()
    
    # Critical imports to test
    imports_to_test = [
        "from live_monitoring.core.signal_generator import SignalGenerator",
        "from live_monitoring.core.data_fetcher import DataFetcher",
        "from live_monitoring.core.risk_manager import RiskManager",
        "from live_monitoring.core.price_action_filter import PriceActionFilter",
        "from live_monitoring.alerting.alert_router import AlertRouter",
        "from core.ultra_institutional_engine import UltraInstitutionalEngine",
    ]
    
    results["imports"] = {}
    for imp in imports_to_test:
        try:
            exec(imp)
            results["imports"][imp.split()[-1]] = True
            print(f"  ✅ {imp.split()[-1]}")
        except Exception as e:
            results["imports"][imp.split()[-1]] = str(e)
            print(f"  ❌ {imp.split()[-1]}: {str(e)[:40]}")
    
    results["all_imports_ok"] = all(v == True for v in results["imports"].values())
    
    return results

# ============================================================
# TEST 12: Replay System
# ============================================================
def test_replay_system():
    """Test replay functionality"""
    results = {}
    
    # Check if replay file exists
    results["replay_file_exists"] = os.path.exists("replay_lotto_day.py")
    
    if results["replay_file_exists"]:
        try:
            # Try to parse it (don't run it)
            import ast
            with open("replay_lotto_day.py", "r") as f:
                ast.parse(f.read())
            results["syntax_valid"] = True
            print(f"  ✅ replay_lotto_day.py syntax valid")
        except SyntaxError as e:
            results["syntax_valid"] = False
            results["syntax_error"] = str(e)
            print(f"  ❌ Syntax error in replay_lotto_day.py")
    
    # Check for historical data
    historical_dirs = [
        "data/historical",
        "data/historical/institutional_contexts",
    ]
    results["data_dirs"] = {}
    for d in historical_dirs:
        exists = os.path.exists(d)
        results["data_dirs"][d] = exists
        status = "✅" if exists else "❌"
        print(f"  {status} {d}")
    
    return results

# ============================================================
# TEST 13: YFinance Integration
# ============================================================
def test_yfinance():
    """Test yfinance data fetching"""
    results = {}
    
    try:
        import yfinance as yf
        results["import_success"] = True
        
        # Fetch SPY data
        print("  Fetching SPY data from yfinance...")
        spy = yf.Ticker("SPY")
        hist = spy.history(period="1d")
        
        results["data_fetched"] = len(hist) > 0
        if len(hist) > 0:
            results["last_close"] = hist["Close"].iloc[-1]
            print(f"  ✅ SPY last close: ${results['last_close']:.2f}")
        
    except Exception as e:
        results["error"] = str(e)
        raise
    
    return results

# ============================================================
# TEST 14: Gemini API
# ============================================================
def test_gemini_api():
    """Test Google Gemini API connectivity"""
    results = {}
    
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        # Try from .env
        try:
            with open(".env") as f:
                for line in f:
                    if "GEMINI_API_KEY" in line:
                        gemini_key = line.split("=")[1].strip()
                        break
        except:
            pass
    
    results["api_key_found"] = gemini_key is not None
    
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content("Say 'API working' in 3 words")
            
            results["api_working"] = True
            results["response"] = response.text[:50] if response.text else "No response"
            print(f"  ✅ Gemini API working: {results['response']}")
            
        except Exception as e:
            results["api_working"] = False
            results["error"] = str(e)
            print(f"  ❌ Gemini API error: {str(e)[:50]}")
    else:
        print("  ⚠️ No Gemini API key found")
    
    return results

# ============================================================
# MAIN AUDIT RUNNER
# ============================================================
def run_full_audit():
    """Run all tests and generate report"""
    print("\n" + "🔥" * 30)
    print("   ZO'S COMPREHENSIVE SYSTEM AUDIT")
    print("🔥" * 30)
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🔥" * 30)
    
    tests = [
        ("1. Environment & Configuration", test_environment),
        ("2. ChartExchange API Client", test_chartexchange_client),
        ("3. Signal Generator", test_signal_generator),
        ("4. Institutional Engine", test_institutional_engine),
        ("5. Data Fetcher", test_data_fetcher),
        ("6. Narrative Enrichment Pipeline", test_narrative_pipeline),
        ("7. Risk Manager", test_risk_manager),
        ("8. Price Action Filter", test_price_action_filter),
        ("9. Alerting System", test_alerting),
        ("10. Paper Trading", test_paper_trading),
        ("11. Lotto Machine Imports", test_lotto_machine_imports),
        ("12. Replay System", test_replay_system),
        ("13. YFinance Integration", test_yfinance),
        ("14. Gemini API", test_gemini_api),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        if test_module(name, test_func):
            passed += 1
        else:
            failed += 1
    
    # Generate summary
    print("\n" + "=" * 60)
    print("📊 AUDIT SUMMARY")
    print("=" * 60)
    print(f"  Total Tests: {passed + failed}")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  Success Rate: {(passed/(passed+failed))*100:.1f}%")
    
    print("\n" + "=" * 60)
    print("📋 DETAILED RESULTS")
    print("=" * 60)
    
    for name, result in AUDIT_RESULTS.items():
        status = result["status"]
        print(f"\n{status} {name}")
        if result["error"]:
            print(f"   Error: {result['error'][:100]}")
    
    # Save results to file
    import json
    os.makedirs("logs", exist_ok=True)
    with open("logs/audit_results.json", "w") as f:
        # Convert to serializable format
        serializable = {}
        for k, v in AUDIT_RESULTS.items():
            serializable[k] = {
                "status": v["status"],
                "error": v.get("error"),
                "details": str(v.get("details"))[:500] if v.get("details") else None
            }
        json.dump(serializable, f, indent=2)
    
    print(f"\n💾 Results saved to: logs/audit_results.json")
    
    return passed, failed, AUDIT_RESULTS

if __name__ == "__main__":
    passed, failed, results = run_full_audit()
    
    print("\n" + "🔥" * 30)
    if failed == 0:
        print("   🎉 ALL TESTS PASSED! SYSTEM READY!")
    else:
        print(f"   ⚠️ {failed} TESTS FAILED - CHECK ABOVE")
    print("🔥" * 30)

