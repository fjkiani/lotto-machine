"""
PerplexitySearchClient - Real-time web search for narrative engine.

Implements the manager's recommended approach from `.cursor/rules/feedback.mdc`:
- Use Perplexity API as the primary real-time search layer
- Return clean answers + citations for narrative/thesis building
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class PerplexitySearchClient:
    """
    Thin wrapper around Perplexity's chat/completions endpoint.

    NOTE:
    - API key is read from PERPLEXITY_API_KEY by default.
    - We do NOT hard-code the key; set it in env or pass explicitly.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        self.base_url = "https://api.perplexity.ai"

        if not self.api_key:
            logger.warning(
                "PerplexitySearchClient initialized without PERPLEXITY_API_KEY; "
                "all calls will fail until key is provided."
            )

    # ------------------------------------------------------------------
    # Core search
    # ------------------------------------------------------------------

    def search(self, query: str, recency_filter: str = "day") -> Dict:
        """
        Single-query search using Perplexity API.

        Args:
            query: Natural language search query
            recency_filter: "hour", "day", "week", "month", "year"

        Returns:
            {
                "answer": str,
                "citations": List[Dict],
                "related_queries": List[str],
            }
        """
        if not self.api_key:
            raise RuntimeError("PERPLEXITY_API_KEY not set")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "sonar",  # manager's recommended default
            "messages": [
                {
                    "role": "user",
                    "content": query,
                }
            ],
            "search_recency_filter": recency_filter,
            "return_citations": True,
            "return_related_questions": True,
        }

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=20,  # keep this tight so we don't hang the pipeline
            )
        except requests.exceptions.Timeout as e:
            raise RuntimeError(f"Perplexity API timeout: {e}") from e

        if resp.status_code == 401:
            # Auth / key / account issue – NOT a rate limit. Surface clearly so Alpha can fix key.
            raise RuntimeError(
                f"Perplexity API auth error (401). This is usually an invalid/expired key "
                f"or wrong project. Body: {resp.text[:200]}"
            )
        if resp.status_code == 429:
            # True rate limit from Perplexity – caller can decide to backoff or reuse cached narrative.
            raise RuntimeError(
                f"Perplexity API rate limit (429). Reduce call frequency or upgrade plan. "
                f"Body: {resp.text[:200]}"
            )
        if resp.status_code != 200:
            raise RuntimeError(f"Perplexity API error: {resp.status_code} - {resp.text[:200]}")

        data = resp.json()
        # Defensive parsing in case response shape changes
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}

        answer = message.get("content", "")
        citations = data.get("citations", [])
        related = data.get("related_questions", [])

        return {
            "answer": answer,
            "citations": citations,
            "related_queries": related,
        }

    def multi_query_search(self, queries: List[str], recency_filter: str = "day") -> List[Dict]:
        """
        Run multiple queries sequentially (like manager's workflow).
        """
        results: List[Dict] = []
        for q in queries:
            try:
                res = self.search(q, recency_filter=recency_filter)
                results.append(
                    {
                        "query": q,
                        "answer": res["answer"],
                        "citations": res["citations"],
                    }
                )
            except Exception as e:
                logger.error("Perplexity multi_query_search error for %s: %s", q, e)
        return results


def _demo() -> None:
    """
    Simple CLI demo:
        export PERPLEXITY_API_KEY="pplx-XXXX"
        python -m live_monitoring.enrichment.apis.perplexity_search
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    client = PerplexitySearchClient()
    print("=" * 80)
    print("🧪 TESTING PerplexitySearchClient")
    print("=" * 80)

    try:
        results = client.multi_query_search(
            [
                "SPY market selloff today - main causes",
                "Bitcoin price action today vs US equities",
            ]
        )
    except Exception as e:
        print(f"❌ Perplexity test failed: {e}")
        return

    for r in results:
        print(f"\n🔍 Query: {r['query']}")
        print(f"Answer (truncated): {r['answer'][:200]}...")
        print("Top citations:")
        for c in r["citations"][:3]:
            # Perplexity may return citations as strings or dicts depending on tier/version
            if isinstance(c, dict):
                url = c.get("url") or c.get("source_url") or "N/A"
                snippet = c.get("snippet", "")[:120]
                print(f"  - {url}: {snippet}...")
            else:
                print(f"  - {str(c)[:140]}...")

    print("\n✅ PerplexitySearchClient demo complete")


if __name__ == "__main__":
    _demo()


