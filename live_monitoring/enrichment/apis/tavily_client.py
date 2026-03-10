"""
Tavily Search Client — Drop-In Replacement for PerplexitySearchClient

Same public interface:
    .search(query, max_results=5) → {"answer", "citations", "related_queries"}
    .multi_query_search(queries)   → [{"query", "answer", "citations"}, ...]

Additional:
    .enrich_hot_tickers(tickers, context) → {"summary", "sources", "score"}

Budget Guard:
    Max 30 calls/day stored in SQLite (~/.tavily_budget.db).
    When budget hit → raises BudgetExhausted so callers can fallback to RSS.

Replaces: perplexity_search.py (quota dead, 401)
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import date
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ─── Budget Guard ─────────────────────────────────────────────────────────────

_BUDGET_DB = os.path.join(os.path.expanduser("~"), ".tavily_budget.db")
_DAILY_LIMIT = 30


class BudgetExhausted(RuntimeError):
    """Raised when the daily Tavily call budget is hit."""
    pass


def _init_budget_db():
    """Create budget table if it doesn't exist."""
    conn = sqlite3.connect(_BUDGET_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tavily_calls ("
        "  call_date TEXT NOT NULL,"
        "  call_count INTEGER NOT NULL DEFAULT 0,"
        "  PRIMARY KEY (call_date)"
        ")"
    )
    conn.commit()
    conn.close()


def _check_and_increment() -> int:
    """
    Check budget. If under limit, increment and return new count.
    If at limit, raise BudgetExhausted.
    """
    _init_budget_db()
    today = date.today().isoformat()
    conn = sqlite3.connect(_BUDGET_DB)

    row = conn.execute(
        "SELECT call_count FROM tavily_calls WHERE call_date = ?", (today,)
    ).fetchone()

    current = row[0] if row else 0

    if current >= _DAILY_LIMIT:
        conn.close()
        raise BudgetExhausted(
            f"Tavily daily budget exhausted ({current}/{_DAILY_LIMIT}). "
            f"Fallback to RSS/OpenBB. Resets tomorrow."
        )

    if row:
        conn.execute(
            "UPDATE tavily_calls SET call_count = ? WHERE call_date = ?",
            (current + 1, today),
        )
    else:
        conn.execute(
            "INSERT INTO tavily_calls (call_date, call_count) VALUES (?, 1)",
            (today,),
        )

    conn.commit()
    conn.close()
    return current + 1


def _get_remaining() -> int:
    """Get remaining calls for today."""
    _init_budget_db()
    today = date.today().isoformat()
    conn = sqlite3.connect(_BUDGET_DB)
    row = conn.execute(
        "SELECT call_count FROM tavily_calls WHERE call_date = ?", (today,)
    ).fetchone()
    conn.close()
    return _DAILY_LIMIT - (row[0] if row else 0)


# ─── Tavily Client ────────────────────────────────────────────────────────────

class TavilySearchClient:
    """
    Drop-in replacement for PerplexitySearchClient.

    Same interface:
        .search(query) → {"answer": str, "citations": list, "related_queries": list}

    Uses Tavily Python SDK under the hood with 30-call/day SQLite budget guard.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self._client = None

        if not self.api_key:
            logger.warning(
                "TavilySearchClient initialized without TAVILY_API_KEY; "
                "all calls will fail until key is provided."
            )
        else:
            try:
                from tavily import TavilyClient
                self._client = TavilyClient(api_key=self.api_key)
                remaining = _get_remaining()
                logger.info(f"🔍 TavilySearchClient initialized ({remaining}/{_DAILY_LIMIT} calls remaining)")
            except ImportError:
                logger.error("❌ tavily-python not installed — run: pip install tavily-python")
            except Exception as e:
                logger.error(f"❌ Tavily init failed: {e}")

    # ── Core search (same signature as PerplexitySearchClient) ────────────

    def search(self, query: str, recency_filter: str = "day", max_results: int = 5) -> Dict[str, Any]:
        """
        Single-query search.

        Args:
            query: Natural language search query
            recency_filter: Ignored (kept for Perplexity compat). Tavily is always real-time.
            max_results: Number of results (default 5)

        Returns:
            {"answer": str, "citations": List[Dict], "related_queries": List[str]}
        """
        if not self._client:
            raise RuntimeError("Tavily client not initialized (missing TAVILY_API_KEY or tavily-python)")

        # Budget guard
        count = _check_and_increment()
        logger.info(f"🔍 Tavily search #{count}/{_DAILY_LIMIT}: {query[:60]}...")

        try:
            response = self._client.search(
                query=query,
                max_results=max_results,
                include_answer=True,
                include_raw_content=False,
            )

            # Map to Perplexity-compatible response format
            answer = response.get("answer", "")
            results = response.get("results", [])

            citations = [
                {
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("content", "")[:200],
                    "score": r.get("score", 0),
                }
                for r in results
            ]

            return {
                "answer": answer,
                "citations": citations,
                "related_queries": [],  # Tavily doesn't return related queries
            }

        except BudgetExhausted:
            raise  # Let callers handle budget exhaustion
        except Exception as e:
            raise RuntimeError(f"Tavily search error: {e}") from e

    def multi_query_search(self, queries: List[str], recency_filter: str = "day") -> List[Dict]:
        """
        Run multiple queries sequentially (same as PerplexitySearchClient).
        """
        results: List[Dict] = []
        for q in queries:
            try:
                res = self.search(q, recency_filter=recency_filter)
                results.append({
                    "query": q,
                    "answer": res["answer"],
                    "citations": res["citations"],
                })
            except BudgetExhausted as e:
                logger.warning(f"⚠️ Budget hit during multi_query: {e}")
                break
            except Exception as e:
                logger.error(f"Tavily multi_query error for '{q}': {e}")
        return results

    # ── Hot ticker enrichment (new capability) ────────────────────────────

    def enrich_hot_tickers(
        self,
        tickers: List[str],
        context: str = "",
        max_results: int = 4,
    ) -> Dict[str, Any]:
        """
        Research why specific tickers are seeing unusual activity.

        Args:
            tickers: List of ticker symbols (e.g. ["AMRZ", "NWBI"])
            context: Additional context (e.g. "politician cluster buys")
            max_results: Number of Tavily results

        Returns:
            {"summary": str, "sources": List[str], "score": float, "raw_results": List}
        """
        ticker_str = ", ".join(tickers[:8])  # Cap at 8 tickers
        query = f"why are politicians or insiders buying {ticker_str} {date.today().strftime('%B %Y')} market catalyst"
        if context:
            query += f" {context}"

        try:
            response = self.search(query, max_results=max_results)

            return {
                "summary": response["answer"][:800] if response["answer"] else "",
                "sources": [c["url"] for c in response["citations"][:6]],
                "score": response["citations"][0]["score"] if response["citations"] else 0.0,
                "tickers_queried": tickers,
                "raw_results": response["citations"][:4],
            }

        except BudgetExhausted as e:
            logger.warning(f"⚠️ Tavily budget exhausted for ticker enrichment: {e}")
            return {
                "summary": f"Budget exhausted — {len(tickers)} tickers queued for tomorrow",
                "sources": [],
                "score": 0.0,
                "tickers_queried": tickers,
                "raw_results": [],
            }
        except Exception as e:
            logger.error(f"❌ Tavily ticker enrichment error: {e}")
            return {
                "summary": f"Enrichment failed: {e}",
                "sources": [],
                "score": 0.0,
                "tickers_queried": tickers,
                "raw_results": [],
            }

    # ── Budget info ───────────────────────────────────────────────────────

    @staticmethod
    def get_budget_remaining() -> int:
        """Get remaining Tavily calls for today."""
        return _get_remaining()


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    client = TavilySearchClient()

    print("=" * 60)
    print("🔍 Tavily Search Client — Standalone Test")
    print(f"   Budget remaining: {client.get_budget_remaining()}/{_DAILY_LIMIT}")
    print("=" * 60)

    # Test 1: Basic search (same as Perplexity)
    print("\n📌 Test 1: Basic search...")
    try:
        res = client.search("What is happening with SPX S&P 500 today March 9 2026?")
        print(f"   Answer: {res['answer'][:200]}...")
        print(f"   Citations: {len(res['citations'])}")
        for c in res["citations"][:3]:
            print(f"     - {c['title'][:60]}: {c['url']}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # Test 2: Hot ticker enrichment
    print("\n📌 Test 2: Hot ticker enrichment...")
    try:
        enrich = client.enrich_hot_tickers(["AMRZ", "NWBI"], context="politician cluster buys")
        print(f"   Summary: {enrich['summary'][:200]}...")
        print(f"   Score: {enrich['score']}")
        print(f"   Sources: {enrich['sources'][:3]}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    print(f"\n   Budget remaining: {client.get_budget_remaining()}/{_DAILY_LIMIT}")
    print("\n✅ Tavily standalone test complete")
