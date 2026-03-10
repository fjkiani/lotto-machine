"""
📡 Finnhub Client — Insider Transactions, Sentiment, News
===========================================================
Three high-alpha pipes from Finnhub's free tier (250 calls/day):

1. /stock/insider-transactions → per-person SEC filings (names, shares, prices)
2. /stock/insider-sentiment    → monthly MSPR (net buy/sell ratio)
3. /company-news               → unlimited headline feed (saves Tavily quota)

Uses raw REST — no finnhub package needed. Tested live March 9 2026.
"""

import os
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# SEC transaction codes → human-readable
TX_CODES = {
    "P": "Purchase",
    "S": "Sale",
    "M": "Exercise/Conversion",
    "A": "Grant/Award",
    "F": "Tax Withholding",
    "G": "Gift",
    "C": "Conversion",
    "X": "Exercise of Derivative",
}


class FinnhubClient:
    """
    Finnhub API client for insider intelligence and news enrichment.
    Free tier: 250 calls/day. Budget: ~80 for insiders, ~80 for news, ~90 reserve.
    """

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY", "")
        if not self.api_key:
            logger.warning("FINNHUB_API_KEY not set — Finnhub calls will fail")

    def _get(self, path: str, params: Dict[str, Any] = None) -> Any:
        """Make authenticated GET request."""
        params = params or {}
        params["token"] = self.api_key
        try:
            r = requests.get(f"{self.BASE_URL}{path}", params=params, timeout=10)
            if r.status_code == 429:
                logger.warning("Finnhub rate limit hit (250/day)")
                return None
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"Finnhub {path} failed: {e}")
            return None

    # ── Insider Intelligence ───────────────────────────────────────────────

    def get_insider_transactions(self, ticker: str, limit: int = 20) -> List[Dict]:
        """
        Per-person SEC insider filings.
        Returns: name, shares changed, price, filing date, transaction type.
        """
        data = self._get("/stock/insider-transactions", {"symbol": ticker, "limit": limit})
        if not data or "data" not in data:
            return []

        results = []
        for tx in data["data"][:limit]:
            # Skip derivative transactions and zero-price exercises
            if tx.get("isDerivative", False):
                continue

            code = tx.get("transactionCode", "?")
            price = tx.get("transactionPrice", 0) or 0
            shares = abs(tx.get("change", 0))

            results.append({
                "name": tx.get("name", "Unknown"),
                "ticker": ticker,
                "type": TX_CODES.get(code, code),
                "shares": shares,
                "price": price,
                "value_usd": round(shares * price, 2) if price > 0 else 0,
                "filing_date": tx.get("filingDate", ""),
                "transaction_date": tx.get("transactionDate", ""),
                "sec_id": tx.get("id", ""),
                "source": "finnhub_sec",
            })

        return results

    def get_insider_sentiment(self, ticker: str, months: int = 24) -> Dict[str, Any]:
        """
        Monthly Purchase Ratio (MSPR).
        MSPR > 50 = net buying, MSPR < 0 = net selling.
        Returns latest month's MSPR + trend.
        Note: Some tickers only have data through mid-2024, so we look back 2 years.
        """
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d")

        data = self._get("/stock/insider-sentiment", {
            "symbol": ticker, "from": start, "to": end
        })
        if not data or "data" not in data or not data["data"]:
            return {"ticker": ticker, "mspr": None, "trend": "unknown", "months": []}

        months_data = data["data"]
        latest = months_data[-1]
        latest_mspr = latest.get("mspr", 0)

        # Calculate trend (last 3 months)
        recent = months_data[-3:] if len(months_data) >= 3 else months_data
        avg_mspr = sum(m.get("mspr", 0) for m in recent) / len(recent)

        if avg_mspr > 50:
            trend = "strong_buying"
        elif avg_mspr > 0:
            trend = "net_buying"
        elif avg_mspr > -20:
            trend = "mixed"
        else:
            trend = "net_selling"

        return {
            "ticker": ticker,
            "mspr": round(latest_mspr, 2),
            "mspr_avg_3m": round(avg_mspr, 2),
            "trend": trend,
            "latest_month": f"{latest.get('year', '')}-{latest.get('month', '')}",
            "net_share_change": latest.get("change", 0),
            "months": [
                {
                    "period": f"{m.get('year')}-{m.get('month'):02d}",
                    "mspr": round(m.get("mspr", 0), 2),
                    "change": m.get("change", 0),
                }
                for m in months_data
            ],
        }

    # ── News (Tavily Quota Saver) ──────────────────────────────────────────

    def get_company_news(self, ticker: str, days: int = 7, limit: int = 20) -> List[Dict]:
        """
        Company news headlines. Unlimited on free tier.
        Use BEFORE Tavily — save Tavily for deep "why" searches.
        """
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        data = self._get("/company-news", {"symbol": ticker, "from": start, "to": end})
        if not data or not isinstance(data, list):
            return []

        return [
            {
                "headline": article.get("headline", ""),
                "source": article.get("source", ""),
                "url": article.get("url", ""),
                "summary": article.get("summary", "")[:200],
                "datetime": datetime.fromtimestamp(
                    article.get("datetime", 0)
                ).strftime("%Y-%m-%d %H:%M") if article.get("datetime") else "",
                "related": article.get("related", ""),
            }
            for article in data[:limit]
        ]

    # ── Cross-Reference (The Power Play) ────────────────────────────────────

    def cross_reference_politician_trade(
        self, ticker: str, politician_action: str
    ) -> Dict[str, Any]:
        """
        Cross-reference a politician's trade against insider sentiment + news.
        
        Returns convergence/divergence signal with reasoning.
        
        politician_action: "buy" or "sell"
        """
        mspr_data = self.get_insider_sentiment(ticker)
        news = self.get_company_news(ticker, days=7, limit=10)

        mspr = mspr_data.get("mspr")
        trend = mspr_data.get("trend", "unknown")

        signal = {
            "ticker": ticker,
            "politician_action": politician_action,
            "insider_mspr": mspr,
            "insider_trend": trend,
            "news_count_7d": len(news),
            "convergence": "unknown",
            "divergence_boost": 0,
            "reasoning": [],
        }

        if mspr is None:
            signal["reasoning"].append("No MSPR data available")
            return signal

        pol_bullish = politician_action.lower() in ("buy", "purchase")

        # Convergence: politician and insiders agree
        if pol_bullish and mspr > 50:
            signal["convergence"] = "STRONG_CONVERGENCE"
            signal["divergence_boost"] = 3
            signal["reasoning"].append(
                f"Politician BUY + insider MSPR={mspr:.0f} (strong net buying) → convergence"
            )
        elif pol_bullish and mspr > 0:
            signal["convergence"] = "MILD_CONVERGENCE"
            signal["divergence_boost"] = 1
            signal["reasoning"].append(
                f"Politician BUY + insider MSPR={mspr:.0f} (mild net buying) → mild convergence"
            )
        # Divergence: politician fading insiders → red flag
        elif pol_bullish and mspr < -20:
            signal["convergence"] = "DIVERGENCE"
            signal["divergence_boost"] = -2
            signal["reasoning"].append(
                f"Politician BUY but insider MSPR={mspr:.0f} (net selling) → FADING INSIDERS"
            )
        elif not pol_bullish and mspr > 50:
            signal["convergence"] = "DIVERGENCE"
            signal["divergence_boost"] = -2
            signal["reasoning"].append(
                f"Politician SELL but insider MSPR={mspr:.0f} (net buying) → politician bailing early?"
            )
        elif not pol_bullish and mspr < -20:
            signal["convergence"] = "STRONG_CONVERGENCE"
            signal["divergence_boost"] = 3
            signal["reasoning"].append(
                f"Politician SELL + insider MSPR={mspr:.0f} (net selling) → everyone exiting"
            )
        else:
            signal["convergence"] = "NEUTRAL"
            signal["divergence_boost"] = 0
            signal["reasoning"].append(f"MSPR={mspr:.0f} — no strong signal")

        # News catalyst check
        if news:
            headlines = " ".join(n.get("headline", "").lower() for n in news[:5])
            catalysts = []
            if "earnings" in headlines:
                catalysts.append("earnings")
            if "fda" in headlines or "approval" in headlines:
                catalysts.append("FDA/regulatory")
            if "lawsuit" in headlines or "investigation" in headlines:
                catalysts.append("legal risk")
            if "acquisition" in headlines or "merger" in headlines:
                catalysts.append("M&A")

            if catalysts:
                signal["catalysts"] = catalysts
                signal["reasoning"].append(f"News catalysts: {', '.join(catalysts)}")
                if pol_bullish and any(c in ["earnings", "M&A"] for c in catalysts):
                    signal["divergence_boost"] += 1
                    signal["reasoning"].append("Positive catalyst + buy → extra boost")

        return signal
