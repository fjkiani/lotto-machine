"""
Multi-Source News Aggregator

Replaces the single-source Perplexity dependency with a layered approach:
  1. FreeNewsFetcher (RSS: Yahoo, Google, MarketWatch, Reuters, CNBC) — always available
  2. Perplexity (real-time search) — if PERPLEXITY_API_KEY is set
  3. Finnhub (market news + sentiment) — if FINNHUB_API_KEY is set

The pipeline calls aggregate_news() which returns a unified dict
regardless of which sources are available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class NarrativeSource:
    url: str
    snippet: str


def _fetch_rss_news(symbol: str) -> Dict[str, Any]:
    """
    Layer 1: Free RSS feeds — always available, no keys needed.
    Returns market sentiment + headlines from 5 RSS sources.
    """
    try:
        from live_monitoring.enrichment.apis.free_news import FreeNewsFetcher

        fetcher = FreeNewsFetcher()

        # Get market-wide sentiment
        market_sent = fetcher.get_market_sentiment()

        # Get ticker-specific news
        ticker_sent = fetcher.get_ticker_sentiment(symbol)

        # Build narrative from headlines
        headlines = []
        top_bullish = market_sent.get("top_bullish_headlines", [])
        top_bearish = market_sent.get("top_bearish_headlines", [])

        for h in top_bearish[:3]:
            headlines.append(f"📉 {h}")
        for h in top_bullish[:3]:
            headlines.append(f"📈 {h}")

        # Ticker-specific headlines
        ticker_headlines = ticker_sent.get("headlines", {})
        for h in ticker_headlines.get("bearish", [])[:2]:
            headlines.append(f"📉 [{symbol}] {h}")
        for h in ticker_headlines.get("bullish", [])[:2]:
            headlines.append(f"📈 [{symbol}] {h}")

        # Build narrative text from headlines
        headline_text = "\n".join(headlines[:8]) if headlines else ""

        # Sources from articles
        all_articles = fetcher.fetch_ticker_news(symbol, max_articles=10)
        sources = [
            NarrativeSource(url=a.url, snippet=a.title[:200])
            for a in all_articles[:8]
            if a.url
        ]

        logger.info(
            "📰 RSS: %d articles, sentiment=%s (%.0f%% bull / %.0f%% bear)",
            market_sent.get("total_articles", 0),
            market_sent.get("sentiment", "NEUTRAL"),
            market_sent.get("bullish_pct", 0),
            market_sent.get("bearish_pct", 0),
        )

        return {
            "macro": headline_text,
            "sentiment": market_sent.get("sentiment", "NEUTRAL"),
            "confidence": market_sent.get("confidence", 0),
            "bullish_pct": market_sent.get("bullish_pct", 0),
            "bearish_pct": market_sent.get("bearish_pct", 0),
            "total_articles": market_sent.get("total_articles", 0),
            "ticker_sentiment": ticker_sent.get("sentiment", "NEUTRAL"),
            "headlines": headlines,
            "sources": sources,
        }

    except Exception as e:
        logger.error("RSS news fetch failed: %s", e)
        return {"macro": "", "sentiment": "NEUTRAL", "headlines": [], "sources": []}


def _fetch_perplexity_news(symbol: str, date: str, inst_ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Layer 2: Perplexity real-time search — requires PERPLEXITY_API_KEY.
    Returns rich narrative text with citations.
    """
    try:
        from live_monitoring.enrichment.pipeline.perplexity_adapter import (
            build_perplexity_queries,
            run_perplexity_queries,
        )

        queries = build_perplexity_queries(symbol, date, inst_ctx)
        result = run_perplexity_queries(queries)

        macro = result.get("macro", "")
        if not macro:
            logger.warning("Perplexity returned empty macro narrative")
            return {"macro": "", "sector": "", "cross_asset": "", "sources": []}

        logger.info("🔍 Perplexity: got %d chars macro narrative", len(macro))
        return {
            "macro": macro,
            "sector": result.get("sector", ""),
            "cross_asset": result.get("cross", "") or result.get("cross_asset", ""),
            "sources": result.get("sources", []),
        }

    except Exception as e:
        logger.warning("Perplexity unavailable: %s", e)
        return {"macro": "", "sector": "", "cross_asset": "", "sources": []}


def _fetch_finnhub_news(symbol: str) -> Dict[str, Any]:
    """
    Layer 3: Finnhub market news — requires FINNHUB_API_KEY.
    """
    import os

    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        return {"headlines": [], "sources": []}

    try:
        import finnhub

        client = finnhub.Client(api_key=api_key)
        news = client.general_news("general", min_id=0)

        headlines = []
        sources = []
        for item in (news or [])[:10]:
            headline = item.get("headline", "")
            url = item.get("url", "")
            if headline:
                headlines.append(headline)
            if url:
                sources.append(NarrativeSource(url=url, snippet=headline[:200]))

        logger.info("📡 Finnhub: %d headlines", len(headlines))
        return {"headlines": headlines, "sources": sources}

    except ImportError:
        logger.debug("finnhub-python not installed")
        return {"headlines": [], "sources": []}
    except Exception as e:
        logger.warning("Finnhub failed: %s", e)
        return {"headlines": [], "sources": []}


def aggregate_news(
    symbol: str,
    date: str,
    inst_ctx: Dict[str, Any],
    price_summary: str = "",
) -> Dict[str, Any]:
    """
    Multi-source news aggregator — combines all available sources.

    Returns the same dict shape as the old perplexity_adapter.run_perplexity_queries(),
    so it's a drop-in replacement in market_narrative_pipeline.

    Priority:
      1. Perplexity (richest narrative) — used if available
      2. RSS (always available, no keys)
      3. Finnhub (additional headlines)

    Returns:
        {
            "macro": str,        # Main narrative text
            "sector": str,       # Sector narrative
            "asset": str,        # Asset narrative
            "cross_asset": str,  # Cross-asset (BTC vs equities)
            "sources": List[NarrativeSource],
            "news_sentiment": str,  # BULLISH/BEARISH/NEUTRAL from RSS
            "headlines": List[str],  # Raw headline list
        }
    """
    all_sources: List[NarrativeSource] = []
    all_headlines: List[str] = []

    # Layer 1: RSS (always runs — free, fast, no key)
    rss = _fetch_rss_news(symbol)
    rss_macro = rss.get("macro", "")
    rss_sentiment = rss.get("sentiment", "NEUTRAL")
    all_sources.extend(rss.get("sources", []))
    all_headlines.extend(rss.get("headlines", []))

    # Layer 2: Perplexity (if available)
    pplx = _fetch_perplexity_news(symbol, date, inst_ctx)
    pplx_macro = pplx.get("macro", "")
    pplx_sector = pplx.get("sector", "")
    pplx_cross = pplx.get("cross_asset", "")
    all_sources.extend(pplx.get("sources", []))

    # Layer 3: Finnhub (additional headlines)
    fh = _fetch_finnhub_news(symbol)
    all_headlines.extend(fh.get("headlines", []))
    all_sources.extend(fh.get("sources", []))

    # Merge: use Perplexity if available, otherwise build from RSS
    if pplx_macro:
        macro_narr = pplx_macro
    elif rss_macro:
        # Build a narrative from RSS headlines
        macro_narr = f"Market Headlines ({rss.get('total_articles', 0)} articles, sentiment: {rss_sentiment}):\n\n{rss_macro}"
    else:
        macro_narr = "No news data available from any source."

    # Sector: Perplexity or empty
    sector_narr = pplx_sector or ""

    # Cross-asset: Perplexity or empty
    cross_narr = pplx_cross or ""

    # Prepend price summary if provided
    if price_summary and macro_narr:
        macro_narr = price_summary + "\n\n" + macro_narr

    # Deduplicate sources
    seen = set()
    unique_sources: List[NarrativeSource] = []
    for s in all_sources:
        key = (s.url, s.snippet[:50])
        if key not in seen:
            seen.add(key)
            unique_sources.append(s)

    logger.info(
        "📊 Aggregated: %d sources, %d headlines, primary=%s",
        len(unique_sources),
        len(all_headlines),
        "perplexity" if pplx_macro else "rss",
    )

    return {
        "macro": macro_narr,
        "sector": sector_narr,
        "asset": sector_narr,  # Alias
        "cross_asset": cross_narr,
        "sources": unique_sources,
        "news_sentiment": rss_sentiment,
        "headlines": all_headlines,
    }
