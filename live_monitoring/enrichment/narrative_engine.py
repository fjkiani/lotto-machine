"""
Narrative Engine — Full Pipeline Runner
========================================
Aggregates all available data sources and runs the regime-agnostic
NarrativeAgent synthesizer.

Sources (in order of reliability):
  1. RSS Feeds          — always live, no key
  2. yfinance           — SPY/VIX/BTC prices, always live
  3. Stockgrid          — Dark Pool, no auth
  4. Crypto Correlation — BTC/ETH via yfinance
  5. Yahoo Calendar     — Economic events via RAPIDAPI_KEY
  6. Kill Chain         — 5-layer institutional intelligence
  7. Cohere             — Final synthesis (command-a-reasoning-08-2025)

Usage:
    python -m live_monitoring.enrichment.narrative_engine
    python -m live_monitoring.enrichment.narrative_engine SPY
    python -m live_monitoring.enrichment.narrative_engine SPY QQQ
"""

from __future__ import annotations

import json
import logging
import os
import sys
import warnings
from datetime import datetime
from typing import Dict, Optional

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)


def _get_price_snapshot(symbol: str) -> Dict:
    """Pull live price + VIX from yfinance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d", interval="1d")
        vix_hist = yf.Ticker("^VIX").history(period="2d", interval="1d")
        if hist.empty:
            return {}
        close = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else close
        chg = (close - prev) / prev
        vix = float(vix_hist["Close"].iloc[-1]) if not vix_hist.empty else None
        return {"price": round(close, 2), "change_pct": round(chg, 4), "vix": vix}
    except Exception as e:
        logger.warning(f"⚠️  yfinance price snapshot failed: {e}")
        return {}


def _get_news(symbol: str) -> Dict:
    """Pull RSS news sentiment."""
    try:
        from live_monitoring.enrichment.apis.free_news import FreeNewsFetcher
        fetcher = FreeNewsFetcher()
        result = fetcher.get_market_sentiment()
        result["source"] = "RSS"
        return result
    except Exception as e:
        logger.warning(f"⚠️  RSS news failed: {e}")
        return {}


def _get_dark_pool(symbol: str) -> Dict:
    """Pull Stockgrid dark pool data."""
    try:
        from live_monitoring.enrichment.institutional_narrative import load_institutional_context
        ctx = load_institutional_context(symbol)
        return ctx.get("dark_pool", ctx)
    except Exception as e:
        logger.warning(f"⚠️  Dark pool fetch failed: {e}")
        return {}


def _get_crypto(lookback_minutes: int = 60) -> object:
    """Pull crypto correlation."""
    try:
        from live_monitoring.enrichment.crypto_correlation import CryptoCorrelationDetector
        detector = CryptoCorrelationDetector(lookback_minutes=lookback_minutes)
        return detector.get_crypto_sentiment()
    except Exception as e:
        logger.warning(f"⚠️  Crypto correlation failed: {e}")
        return {}


def _get_events(date: str) -> Dict:
    """Pull economic calendar events."""
    try:
        from live_monitoring.enrichment.apis.event_loader import EventLoader
        loader = EventLoader()
        return loader.load_events(date=date, min_impact="medium")
    except Exception as e:
        logger.warning(f"⚠️  Event loader failed: {e}")
        return {"has_events": False, "macro_events": [], "earnings": [], "opex": False}


def _get_kill_chain() -> Optional[object]:
    """Run Kill Chain 5-layer institutional intelligence."""
    try:
        from live_monitoring.enrichment.apis.kill_chain_engine import KillChainEngine
        kc = KillChainEngine()
        report = kc.run_full_scan()
        return report
    except Exception as e:
        logger.warning(f"⚠️  Kill Chain failed: {e}")
        return None


def run_narrative_engine(
    symbol: str = "SPY",
    date: str = None,
    verbose: bool = True,
) -> Dict:
    """
    Full narrative engine run.

    Returns the NarrativeResult as a dict.
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*72}")
    print(f"  🧠 NARRATIVE INTELLIGENCE ENGINE — {symbol} | {date}")
    print(f"{'='*72}\n")

    context: Dict = {}

    # ── Pillar 1: Aggregation ─────────────────────────────────────────────
    print("📡 [1/6] Fetching price snapshot (yfinance)...")
    context["price"] = _get_price_snapshot(symbol)
    p = context["price"]
    if p:
        print(f"   ${p.get('price')} | {p.get('change_pct',0)*100:+.2f}% | VIX {p.get('vix')}")

    print("📰 [2/6] Fetching news (RSS feeds)...")
    context["news"] = _get_news(symbol)
    n = context["news"]
    if n:
        print(f"   {n.get('total_articles',0)} articles | {n.get('sentiment','?')} "
              f"({n.get('bullish_pct',0):.0f}% bull / {n.get('bearish_pct',0):.0f}% bear)")

    print("🏦 [3/6] Fetching dark pool (Stockgrid)...")
    context["dark_pool"] = _get_dark_pool(symbol)
    dp = context["dark_pool"]
    if dp:
        pct = dp.get("pct") or dp.get("Short Volume %") or "N/A"
        vol = dp.get("volume") or dp.get("dp_volume") or 0
        print(f"   Short Vol: {pct}% | DP Volume: ${abs(vol)/1e9:.1f}B" if isinstance(vol, (int, float)) else f"   Short Vol: {pct}")

    print("₿ [4/6] Crypto correlation (BTC/ETH vs SPY)...")
    context["crypto"] = _get_crypto()
    cs = context["crypto"]
    if hasattr(cs, "btc_price"):
        env = getattr(cs, "environment", None) or getattr(cs, "risk_environment", "?")
        env_name = env.name if hasattr(env, "name") else str(env)
        print(f"   BTC ${cs.btc_price:,.0f} ({cs.btc_change_pct*100:+.2f}%) | ETH ${cs.eth_price:,.0f} | {env_name}")

    print("📅 [5/6] Economic calendar (Yahoo Finance via RapidAPI)...")
    context["events"] = _get_events(date)
    ev = context["events"]
    if ev.get("has_events"):
        macro = ev.get("macro_events", [])
        print(f"   {len(macro)} events | OPEX: {ev.get('opex')}")
        for e in macro[:3]:
            sigma = f" ({e['surprise_sigma']:+.1f}σ)" if e.get("surprise_sigma") else ""
            print(f"   • {e.get('time','?')} {e.get('name','?')[:40]} | {e.get('impact','?').upper()} | "
                  f"Act: {e.get('actual','?')} / Fcst: {e.get('forecast','?')}{sigma}")
    else:
        print("   No high-impact events today")

    print("⚔️  [6/6] Kill Chain intelligence (5-layer scan)...")
    context["kill_chain"] = _get_kill_chain()
    kc = context["kill_chain"]
    if kc:
        alerts = getattr(kc, "alerts", None) or (kc.get("alerts", []) if isinstance(kc, dict) else [])
        print(f"   Kill Chain complete | {len(alerts)} alert(s)")
        for a in (alerts or [])[:2]:
            print(f"   ⚠️  {a}")

    # ── Pillar 2–3: Divergence + Pattern handled inside NarrativeAgent ────

    # ── Pillar 4: Cohere Synthesis ────────────────────────────────────────
    print("\n🔬 Running Cohere command-a-reasoning synthesis...")
    try:
        from live_monitoring.enrichment.narrative_agent import NarrativeAgent
        agent = NarrativeAgent()
        result = agent.analyze_market_state(symbol, context, date=date)
        result_dict = result.to_dict()

        # ── Print Full Output ─────────────────────────────────────────────
        print(f"\n{'='*72}")
        print(f"  📊 NARRATIVE RESULT — {symbol}")
        print(f"{'='*72}")
        print(f"  Direction:       {result.direction}")
        print(f"  Conviction:      {result.conviction}")
        print(f"  Duration:        {result.duration}")
        print(f"  Risk Env:        {result.risk_environment}")
        print(f"  Confidence Adj:  {result.confidence_adjustment:+.2%}")
        print(f"\n  THESIS:\n  {result.thesis}")
        print(f"\n  CAUSAL CHAIN:\n  {result.causal_chain}")
        if result.key_catalysts:
            print(f"\n  KEY CATALYSTS:")
            for c in result.key_catalysts:
                print(f"    • {c}")
        if result.institutional_read:
            print(f"\n  INSTITUTIONAL READ:\n  {result.institutional_read}")
        if result.crypto_read:
            print(f"\n  CRYPTO READ:\n  {result.crypto_read}")
        if result.macro_read:
            print(f"\n  MACRO READ:\n  {result.macro_read}")
        if result.uncertainties:
            print(f"\n  UNCERTAINTIES:")
            for u in result.uncertainties:
                print(f"    ⚠️  {u}")
        if result.sources:
            print(f"\n  DATA SOURCES: {' | '.join(result.sources)}")
        print(f"{'='*72}\n")

        return result_dict

    except Exception as e:
        print(f"\n❌ Narrative synthesis failed: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "symbol": symbol, "date": date}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,  # Suppress noise for clean output
        format="%(levelname)s - %(name)s - %(message)s"
    )

    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["SPY"]
    today = datetime.now().strftime("%Y-%m-%d")

    results = {}
    for sym in symbols:
        results[sym] = run_narrative_engine(sym, date=today)

    # Final JSON dump
    print("\n📋 FULL JSON OUTPUT:")
    print(json.dumps(results, indent=2, default=str)[:6000])
