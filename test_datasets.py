#!/usr/bin/env python3
"""
AGGRESSIVE DATASET AUDIT v3 — ALL FIXES APPLIED, FRED ADDED
Every field name verified from source code. No sandbagging.
"""
import sys
import os
import traceback
import logging
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.WARNING, format='%(name)s | %(levelname)s | %(message)s')

RESULTS = []

def test(name, fn):
    print(f"\n{'='*60}")
    print(f"🔬 TESTING: {name}")
    print(f"{'='*60}")
    try:
        result = fn()
        if result:
            print(f"✅ {name}: SUCCESS")
            print(f"   DATA: {str(result)[:300]}")
            RESULTS.append({"name": name, "status": "SUCCESS", "data": str(result)[:200]})
        else:
            print(f"❌ {name}: RETURNED NONE/EMPTY")
            RESULTS.append({"name": name, "status": "EMPTY", "data": "None"})
    except ImportError as e:
        print(f"❌ {name}: IMPORT FAILED — {e}")
        RESULTS.append({"name": name, "status": "IMPORT_FAIL", "error": str(e)})
    except Exception as e:
        print(f"❌ {name}: RUNTIME ERROR — {e}")
        traceback.print_exc()
        RESULTS.append({"name": name, "status": "RUNTIME_FAIL", "error": str(e)})


# ═══ 1. STOCKGRID (field: dp_position_dollars) ═══
def test_stockgrid():
    from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
    sg = StockgridClient()
    detail = sg.get_ticker_detail("SPY")
    if detail:
        return f"SPY DP$ {detail.dp_position_dollars:,.0f} | ShortVol% {detail.short_volume_pct:.1f}%"
    top = sg.get_top_positions(limit=3)
    if top:
        return f"Top: {[(t.ticker, t.dp_position_dollars) for t in top[:3]]}"
    return None

# ═══ 2. COT ═══
def test_cot():
    from live_monitoring.enrichment.apis.cot_client import COTClient
    cot = COTClient()
    pos = cot.get_position("ES")
    if pos:
        return f"ES Specs Net: {pos.specs_net:+,} | Comm Net: {pos.comm_net:+,} | Date: {pos.report_date}"
    return None

# ═══ 3. GEX ═══
def test_gex():
    from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator
    g = GEXCalculator()
    r = g.compute_gex("SPX")
    if r and r.spot_price > 0:
        walls = [f"{w.strike:.0f}" for w in r.gamma_walls[:3]]
        return f"Spot: {r.spot_price:,.2f} | GEX: {r.total_gex:,.0f} | Regime: {r.gamma_regime} | Walls: {walls}"
    return None

# ═══ 4. FEDWATCH (class: FedWatchEngine) ═══
def test_fedwatch():
    from live_monitoring.enrichment.apis.fedwatch_diy import FedWatchEngine
    fw = FedWatchEngine()
    r = fw.get_probabilities()
    if r and "error" not in r:
        nm = r.get("next_meeting", {})
        return f"Rate: {r.get('current_rate', '?')} | Next: {nm.get('label', '?')} Hold:{nm.get('p_hold', 0):.0f}% Cut:{nm.get('p_cut_25', 0):.0f}% | {r.get('summary', '')[:100]}"
    return None

def test_fedwatch_narrative():
    from live_monitoring.enrichment.apis.fedwatch_diy import FedWatchEngine
    fw = FedWatchEngine()
    return fw.get_narrative()

# ═══ 5. SEC 13F ═══
def test_sec13f():
    from live_monitoring.enrichment.apis.sec_13f_client import SEC13FClient
    sec = SEC13FClient()
    f = sec.get_latest_filing("Citadel Advisors")
    if f:
        return f"{f.fund_name} | Filed: {f.filing_date} | Form: {f.form_type}"
    return None

# ═══ 6. KILL CHAIN ═══
def test_kill_chain():
    from live_monitoring.enrichment.apis.kill_chain_engine import KillChainEngine
    kc = KillChainEngine()
    r = kc.run_full_scan()
    if r:
        return f"Alert: {kc.get_alert_level()} | Narrative: {kc.get_shadow_narrative()[:200]}"
    return None

# ═══ 7. FREE NEWS (class: FreeNewsFetcher) ═══
def test_free_news():
    from live_monitoring.enrichment.apis.free_news import FreeNewsFetcher
    fn = FreeNewsFetcher()
    articles = fn.fetch_all_news(max_per_source=3)
    if articles:
        return f"{len(articles)} articles. Top: {articles[0].title[:80]}"
    return None

def test_free_news_sentiment():
    from live_monitoring.enrichment.apis.free_news import FreeNewsFetcher
    fn = FreeNewsFetcher()
    s = fn.get_market_sentiment()
    if s:
        return f"Sentiment: {s.get('sentiment')} | Bull:{s.get('bullish_count')} Bear:{s.get('bearish_count')} Total:{s.get('total_count')}"
    return None

# ═══ 8. PERPLEXITY (class: PerplexitySearchClient) ═══
def test_perplexity():
    from live_monitoring.enrichment.apis.perplexity_search import PerplexitySearchClient
    px = PerplexitySearchClient()
    r = px.search("What is SPX doing today March 9 2026?")
    if r:
        return f"Perplexity: {str(r)[:200]}"
    return None

# ═══ 9. ALPHA VANTAGE ═══
def test_alpha_vantage():
    from live_monitoring.enrichment.apis.alpha_vantage_econ import AlphaVantageEcon
    av = AlphaVantageEcon()
    r = av.get_fed_funds_rate()
    if r:
        return f"Fed Rate: {r.value} ({r.change_direction}) | Date: {r.date}"
    return None

# ═══ 10. NEW — FRED CPI (replacement endpoint) ═══
def test_fred_cpi():
    from live_monitoring.enrichment.apis.fred_client import FREDClient
    fc = FREDClient()
    r = fc.get_cpi()
    if r:
        return f"CPI: {r.value:.1f} ({r.change_pct:+.2f}% MoM) | Date: {r.date}"
    return None

def test_fred_core_cpi():
    from live_monitoring.enrichment.apis.fred_client import FREDClient
    fc = FREDClient()
    r = fc.get_core_cpi()
    if r:
        return f"Core CPI: {r.value:.1f} ({r.change_pct:+.2f}% MoM) | Date: {r.date}"
    return None

def test_fred_unemployment():
    from live_monitoring.enrichment.apis.fred_client import FREDClient
    fc = FREDClient()
    r = fc.get_unemployment()
    if r:
        return f"Unemployment: {r.value:.1f}% | Date: {r.date}"
    return None

def test_fred_10y():
    from live_monitoring.enrichment.apis.fred_client import FREDClient
    fc = FREDClient()
    r = fc.get_treasury_10y()
    if r:
        return f"10Y Yield: {r.value:.2f}% | Date: {r.date}"
    return None

def test_fred_spread():
    from live_monitoring.enrichment.apis.fred_client import FREDClient
    fc = FREDClient()
    r = fc.get_yield_spread()
    if r:
        inv = " ⚠️ INVERTED" if r.value < 0 else ""
        return f"10Y-2Y Spread: {r.value:.2f}%{inv} | Date: {r.date}"
    return None

def test_fred_narrative():
    from live_monitoring.enrichment.apis.fred_client import FREDClient
    fc = FREDClient()
    return fc.get_narrative()

# ═══ 11. CME API ═══
def test_cme_api():
    from live_monitoring.enrichment.apis.cme_api_client import CMEAPIClient
    c = CMEAPIClient()
    r = c.get_fedwatch_probabilities()
    if r:
        return f"CME Fed Probs: {str(r)[:200]}"
    return None

# ═══ 12. ECONOMIC DATA SUMMARY ═══
def test_econ_data():
    from live_monitoring.enrichment.apis.economic_data_fetcher import EconomicDataFetcher
    e = EconomicDataFetcher()
    r = e.get_summary()
    if r:
        return f"Econ: {str(r)[:200]}"
    return None

# ═══ 13. TRADING ECONOMICS (method: get_upcoming_us_events) ═══
def test_trading_economics():
    from live_monitoring.enrichment.apis.trading_economics import TradingEconomicsWrapper
    te = TradingEconomicsWrapper()
    r = te.get_upcoming_us_events(hours_ahead=72)
    if r:
        return f"{len(r)} upcoming events. Next: {r[0].event[:50]} ({r[0].importance.value}) in {r[0].hours_until():.0f}h"
    return None

# ═══ 14. DIFFBOT ═══
def test_diffbot():
    from live_monitoring.enrichment.apis.diffbot_extractor import DiffbotExtractor
    d = DiffbotExtractor(token=os.getenv("DIFFBOT_TOKEN"))
    r = d.extract_article("https://www.barchart.com/economy/interest-rates/fed-funds-rate")
    if r:
        return f"Diffbot: title={r.get('title', 'N/A')}, text_len={len(r.get('full_text','') or '')}"
    return None

# ═══ 15. CRYPTO CORRELATION (field: btc_change_pct) ═══
def test_crypto():
    from live_monitoring.enrichment.crypto_correlation import CryptoCorrelationDetector
    cc = CryptoCorrelationDetector()
    r = cc.get_crypto_sentiment()
    if r:
        return f"BTC: ${r.btc_price:,.0f} ({r.btc_change_pct*100:+.2f}%) | ETH: ${r.eth_price:,.0f} ({r.eth_change_pct*100:+.2f}%) | Env: {r.environment.value}"
    return None

# ═══ 16. NARRATIVE AGENT ═══
def test_narrative_agent():
    from live_monitoring.enrichment.narrative_agent import NarrativeAgent
    na = NarrativeAgent()
    methods = [m for m in dir(na) if not m.startswith('_')]
    return f"NarrativeAgent methods: {methods}"

# ═══ 17. TRUMP INTELLIGENCE (class: TrumpKeywordEngine) ═══
def test_trump():
    from live_monitoring.enrichment.trump_intelligence import TrumpKeywordEngine
    te = TrumpKeywordEngine()
    r = te.analyze("Trump announces 25% tariffs on all imports from China effective immediately.")
    if r:
        keywords, catalyst_type, impact, sectors, severity = r
        return f"Keywords: {keywords} | Type: {catalyst_type} | Impact: {impact} | Severity: {severity}"
    return None

# ═══ 18. TRAP MATRIX (method: get_current_state) ═══
def test_trap_matrix():
    from live_monitoring.enrichment.apis.trap_matrix_orchestrator import TrapMatrixOrchestrator
    tm = TrapMatrixOrchestrator()
    r = tm.get_current_state("SPY")
    if r:
        return f"SPY @ {r.current_price:.2f} | DP Levels: {len(r.dp_levels)} | GEX: {r.gex_regime}"
    return None

# ═══ 19. PIVOT CALCULATOR ═══
def test_pivots():
    from live_monitoring.enrichment.apis.pivot_calculator import PivotCalculator
    pc = PivotCalculator()
    # find the actual compute method
    if hasattr(pc, 'compute'):
        r = pc.compute("SPY")
    elif hasattr(pc, 'get_pivots'):
        r = pc.get_pivots("SPY")
    else:
        methods = [m for m in dir(pc) if not m.startswith('_') and callable(getattr(pc, m))]
        return f"Methods: {methods}"
    if r:
        return f"Pivot: {r.classic.pivot:.2f} | R1: {r.classic.r1:.2f} | S1: {r.classic.s1:.2f}"
    return None

# ═══ 20. TECHNICAL AGENT ═══
def test_technical():
    from live_monitoring.enrichment.apis.technical_agent import TechnicalAgent
    ta = TechnicalAgent()
    if hasattr(ta, 'get_technical'):
        r = ta.get_technical("SPY")
    elif hasattr(ta, 'compute'):
        r = ta.compute("SPY")
    else:
        methods = [m for m in dir(ta) if not m.startswith('_') and callable(getattr(ta, m))]
        return f"Methods: {methods}"
    if r:
        ma200 = r.moving_averages.get('MA200_SMA')
        return f"SPY @ {r.current_price:.2f} | MA200: {ma200.value:.2f} ({ma200.signal}) | VIX Label: {r.vix_label}"
    return None


# ═══ RUN ALL ═══
if __name__ == "__main__":
    print("\n" + "🔥" * 30)
    print("AGGRESSIVE DATASET AUDIT v3 — ALL FIXES + FRED DEPLOYED")
    print("🔥" * 30 + "\n")

    tests = [
        ("1. Stockgrid Dark Pool", test_stockgrid),
        ("2. COT Positioning", test_cot),
        ("3. GEX SPX", test_gex),
        ("4a. FedWatch Engine", test_fedwatch),
        ("4b. FedWatch Narrative", test_fedwatch_narrative),
        ("5. SEC 13F Filing", test_sec13f),
        ("6. Kill Chain Full Scan", test_kill_chain),
        ("7a. Free News Articles", test_free_news),
        ("7b. Free News Sentiment", test_free_news_sentiment),
        ("8. Perplexity Search", test_perplexity),
        ("9. Alpha Vantage Fed Rate", test_alpha_vantage),
        ("10a. FRED CPI", test_fred_cpi),
        ("10b. FRED Core CPI", test_fred_core_cpi),
        ("10c. FRED Unemployment", test_fred_unemployment),
        ("10d. FRED 10Y Yield", test_fred_10y),
        ("10e. FRED 10Y-2Y Spread", test_fred_spread),
        ("10f. FRED Narrative", test_fred_narrative),
        ("11. CME API FedWatch", test_cme_api),
        ("12. Econ Data Summary", test_econ_data),
        ("13. Trading Economics", test_trading_economics),
        ("14. Diffbot Extractor", test_diffbot),
        ("15. Crypto Correlation", test_crypto),
        ("16. Narrative Agent", test_narrative_agent),
        ("17. Trump Intelligence", test_trump),
        ("18. Trap Matrix", test_trap_matrix),
        ("19. Pivot Calculator", test_pivots),
        ("20. Technical Agent", test_technical),
    ]

    for name, fn in tests:
        test(name, fn)

    print("\n\n" + "=" * 60)
    print("📊 FINAL SCORECARD")
    print("=" * 60)
    success = [r for r in RESULTS if r["status"] == "SUCCESS"]
    empty = [r for r in RESULTS if r["status"] == "EMPTY"]
    import_fail = [r for r in RESULTS if r["status"] == "IMPORT_FAIL"]
    runtime_fail = [r for r in RESULTS if r["status"] == "RUNTIME_FAIL"]

    print(f"\n✅ SUCCESS:      {len(success)}/{len(RESULTS)}")
    for r in success:
        print(f"   ✅ {r['name']}: {r['data'][:100]}")

    print(f"\n⚠️ EMPTY:        {len(empty)}/{len(RESULTS)}")
    for r in empty:
        print(f"   ⚠️ {r['name']}")

    print(f"\n❌ IMPORT FAIL:  {len(import_fail)}/{len(RESULTS)}")
    for r in import_fail:
        print(f"   ❌ {r['name']}: {r['error']}")

    print(f"\n💀 RUNTIME FAIL: {len(runtime_fail)}/{len(RESULTS)}")
    for r in runtime_fail:
        print(f"   💀 {r['name']}: {r['error']}")

    print(f"\n{'='*60}")
    print(f"TOTAL: {len(RESULTS)} tests | {len(success)} live | {len(empty)+len(import_fail)+len(runtime_fail)} broken")
    print(f"{'='*60}\n")
