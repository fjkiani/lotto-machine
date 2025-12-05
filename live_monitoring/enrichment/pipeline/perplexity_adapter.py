"""
Perplexity Adapter

Isolates all Perplexity-specific query construction and result parsing so that
`market_narrative_pipeline` can stay thin and orchestration-focused.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from live_monitoring.enrichment.apis.perplexity_search import PerplexitySearchClient

logger = logging.getLogger(__name__)


@dataclass
class NarrativeSource:
    url: str
    snippet: str


def build_perplexity_queries(
    symbol: str,
    trading_date_str: str,
    inst_ctx: Dict[str, Any],
) -> List[str]:
    """
    Build Perplexity queries for macro / sector / cross-asset narrative.
    """
    dp_pct = inst_ctx.get("dark_pool", {}).get("pct")
    max_pain = inst_ctx.get("max_pain")

    if symbol == "SPY":
        return [
            (
                f"SPY realized move on {trading_date_str}: summarize actual price action "
                f"(open, high, low, close, % change) and the main causes; "
                f"dark pool share {dp_pct}%, max pain {max_pain}."
            ),
            f"QQQ price action on {trading_date_str} and tech / semis sector narrative.",
            f"Bitcoin price action on {trading_date_str} vs US equities (risk-on vs risk-off).",
        ]
    if symbol == "QQQ":
        return [
            (
                f"QQQ realized move on {trading_date_str}: summarize actual price action "
                f"and the main causes; dark pool share {dp_pct}%, max pain {max_pain}."
            ),
            f"SPY market move on {trading_date_str} and macro narrative.",
            f"Bitcoin price action on {trading_date_str} vs US equities (risk-on vs risk-off).",
        ]

    return [
        (
            f"{symbol} realized move on {trading_date_str}: summarize actual price action "
            f"and the main causes; dark pool share {dp_pct}%, max pain {max_pain}."
        ),
        f"{symbol} sector narrative on {trading_date_str}.",
        f"Bitcoin price action on {trading_date_str} vs US equities (risk-on vs risk-off).",
    ]


def run_perplexity_queries(queries: List[str]) -> Dict[str, Any]:
    """
    Execute Perplexity multi-query search and normalize outputs.
    Safe if PERPLEXITY_API_KEY is missing (returns empty strings).
    """
    pplx = PerplexitySearchClient()

    macro_narr = ""
    sector_narr = ""
    asset_narr = ""
    cross_asset_narr = ""
    sources: List[NarrativeSource] = []

    try:
        results = pplx.multi_query_search(queries)
    except Exception as e:
        logger.error("Perplexity multi_query_search error: %s", e)
        results = []

    for idx, r in enumerate(results):
        answer = (r.get("answer") or "").strip()
        cits = r.get("citations") or []

        if idx == 0:
            macro_narr = answer
        elif idx == 1:
            sector_narr = answer
            asset_narr = answer
        elif idx == 2:
            cross_asset_narr = answer

        for c in cits[:5]:
            if isinstance(c, dict):
                url = c.get("url") or c.get("source_url") or ""
                snippet = c.get("snippet") or ""
            else:
                url = ""
                snippet = str(c)
            if url or snippet:
                sources.append(NarrativeSource(url=url, snippet=snippet[:280]))

    uniq_sources: List[NarrativeSource] = []
    seen = set()
    for s in sources:
        key = (s.url, s.snippet)
        if key not in seen:
            seen.add(key)
            uniq_sources.append(s)

    return {
        "macro": macro_narr,
        "sector": sector_narr,
        "asset": asset_narr,
        "cross_asset": cross_asset_narr,
        "sources": uniq_sources,
    }


