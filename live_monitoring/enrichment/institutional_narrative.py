"""
Institutional Narrative Layer

Implements the feedback from `.cursor/rules/feedback.mdc`:
- Load institutional data FIRST (dark pool, lit, options, max pain, crypto)
- Detect divergences between institutional flows and mainstream narrative
- Build an institutional-first narrative with a causal chain and trade hint

V2: Focus on SPY / QQQ using Stockgrid (dark pool) + CryptoCorrelationDetector + yfinance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import yfinance as yf

from live_monitoring.enrichment.crypto_correlation import CryptoCorrelationDetector
from live_monitoring.enrichment.models.enriched_signal import RiskEnvironment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Institutional context loader
# ---------------------------------------------------------------------------


def load_institutional_context(symbol: str, date: Optional[str] = None) -> Dict[str, Any]:
    """
    Load institutional data for narrative use.

    Returns a dict with the minimal fields needed for divergence checks and story:
    - dark_pool.pct
    - lit_exchange.pct
    - max_pain
    - current_price
    - pct_change (1d)
    - crypto_correlation: "SIMULTANEOUS_DROP" / "DIVERGENCE" / "NEUTRAL"
    """
    symbol = symbol.upper()
    if date is None:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    ctx: Dict[str, Any] = {
        "symbol": symbol,
        "date": date,
        "dark_pool": {"pct": None},
        "lit_exchange": {"pct": None},
        "max_pain": None,
        "current_price": None,
        "pct_change": None,
        "crypto_correlation": "NEUTRAL",
    }

    # 1) Stockgrid institutional data (no API key needed)
    try:
        from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient

        sg = StockgridClient()
        detail = sg.get_ticker_detail(symbol)

        # Fallback: search top positions if detail fails
        if not detail:
            top = sg.get_top_positions(limit=100)
            if top:
                for pos in top:
                    if pos.ticker == symbol:
                        detail = pos
                        break

        if detail:
            # Stockgrid returns short_volume_pct as 0-1 decimal (e.g. 0.577)
            # Convert to 0-100 scale for consistency with divergence thresholds
            raw_pct = detail.short_volume_pct or 0
            short_vol_pct = raw_pct * 100.0 if raw_pct <= 1.0 else raw_pct
            dp_dollars = abs(detail.dp_position_dollars or 0)
            net_short = detail.net_short_dollars or 0

            # Map to narrative context format
            # short_vol_pct (0-100) = institutional dark pool proxy
            ctx["dark_pool"]["pct"] = short_vol_pct
            ctx["dark_pool"]["volume"] = dp_dollars
            ctx["dark_pool"]["net_short_dollars"] = net_short
            ctx["lit_exchange"]["pct"] = 100.0 - short_vol_pct if short_vol_pct else None

            logger.info(
                "📊 Stockgrid DP data: %.1f%% short vol, $%.1fM DP position, $%.1fM net short",
                short_vol_pct, dp_dollars / 1e6, net_short / 1e6,
            )
        else:
            logger.warning("No Stockgrid data for %s", symbol)

    except ImportError:
        logger.warning("StockgridClient not available; institutional context will be partial.")
    except Exception as e:
        logger.error("Error loading Stockgrid context for %s: %s", symbol, e)

    # 2) Price & pct_change (yfinance)
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d", interval="1d")
        if not hist.empty:
            close_today = float(hist["Close"].iloc[-1])
            if len(hist) > 1:
                close_prev = float(hist["Close"].iloc[-2])
                pct_change = (close_today - close_prev) / close_prev * 100.0
            else:
                pct_change = 0.0
            ctx["current_price"] = close_today
            ctx["pct_change"] = pct_change
    except Exception as e:
        logger.error("Error fetching price history via yfinance for %s: %s", symbol, e)

    # 3) Crypto correlation classification
    try:
        crypto = CryptoCorrelationDetector(lookback_minutes=60)
        cs = crypto.get_crypto_sentiment()
        if cs:
            # Simple classification for narrative:
            # If BTC/ETH down >2% and SPY down >2% -> SIMULTANEOUS_DROP
            # If BTC/ETH up >2% and SPY down >2% -> DIVERGENCE
            # Else NEUTRAL
            btc_ch = cs.btc_change_pct * 100.0
            eth_ch = cs.eth_change_pct * 100.0
            eq_ch = ctx["pct_change"] or 0.0
            if btc_ch < -2 and eth_ch < -2 and eq_ch < -2:
                ctx["crypto_correlation"] = "SIMULTANEOUS_DROP"
            elif btc_ch > 2 and eth_ch > 2 and eq_ch < -2:
                ctx["crypto_correlation"] = "DIVERGENCE"
            else:
                ctx["crypto_correlation"] = "NEUTRAL"
    except Exception as e:
        logger.error("Error computing crypto correlation for %s: %s", symbol, e)

    return ctx


# ---------------------------------------------------------------------------
# Divergence detector
# ---------------------------------------------------------------------------


class DivergenceDetector:
    """
    Detect mismatches between institutional data and mainstream narrative.

    Implements the three key checks from feedback:
    - DISTRIBUTION_MASKED_AS_RALLY
    - OPEX_MANIPULATION_LIKELY
    - LIQUIDITY_CRISIS_SIGNAL
    """

    def detect_manipulation(
        self,
        symbol: str,
        date: str,
        news_narrative: str,
        institutional_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        divergences: List[Dict[str, Any]] = []

        dp_pct = institutional_data.get("dark_pool", {}).get("pct")
        lit_pct = institutional_data.get("lit_exchange", {}).get("pct")
        max_pain = institutional_data.get("max_pain")
        current_price = institutional_data.get("current_price")
        crypto_corr = institutional_data.get("crypto_correlation")

        news_lower = news_narrative.lower()

        # Check 1: Distribution masked as rally (low DP %, high lit %, bullish headline)
        try:
            if dp_pct is not None and lit_pct is not None:
                if dp_pct < 25 and lit_pct > 75:
                    if any(k in news_lower for k in ["rally", "gains", "surge", "bullish"]):
                        divergences.append(
                            {
                                "type": "DISTRIBUTION_MASKED_AS_RALLY",
                                "severity": "HIGH",
                                "reality": f"Institutions selling {lit_pct:.1f}% on lit exchanges (dark pool only {dp_pct:.1f}%).",
                                "narrative": "Mainstream narrative highlights rally/gains.",
                                "signal": "SHORT_OR_TRIM - distribution into strength.",
                            }
                        )
        except Exception as e:
            logger.error("Error in distribution check for %s: %s", symbol, e)

        # Check 2: OPEX manipulation (price far from max pain)
        try:
            if max_pain is not None and current_price is not None:
                distance = abs(current_price - max_pain)
                if current_price > 0 and distance > current_price * 0.02:
                    divergences.append(
                        {
                            "type": "OPEX_MANIPULATION_LIKELY",
                            "severity": "MEDIUM",
                            "reality": f"Max pain at ${max_pain:.2f}, current ${current_price:.2f} (distance {distance:.2f}).",
                            "narrative": "No explicit mention of options expiration pressure.",
                            "signal": f"Expect mean-reversion toward ${max_pain:.2f} by OPEX.",
                        }
                    )
        except Exception as e:
            logger.error("Error in OPEX check for %s: %s", symbol, e)

        # Check 3: Liquidity crisis (simultaneous BTC + equities drop vs 'normal volatility' story)
        try:
            if crypto_corr == "SIMULTANEOUS_DROP":
                if "normal volatility" in news_lower or "routine pullback" in news_lower:
                    divergences.append(
                        {
                            "type": "LIQUIDITY_CRISIS_SIGNAL",
                            "severity": "HIGH",
                            "reality": "Bitcoin and equities dropping together → potential forced liquidations.",
                            "narrative": "Mainstream labels move as 'normal volatility'.",
                            "signal": "POTENTIAL_LIQUIDITY_CRUNCH – size down or wait.",
                        }
                    )
        except Exception as e:
            logger.error("Error in liquidity crisis check for %s: %s", symbol, e)

        return divergences


# ---------------------------------------------------------------------------
# Institutional narrative synthesizer
# ---------------------------------------------------------------------------


class InstitutionalNarrativeSynthesizer:
    """
    Build institutional-first story and causal chain, then compare vs news.
    """

    def _build_institutional_story(self, data: Dict[str, Any]) -> str:
        parts: List[str] = []
        dp_pct = data.get("dark_pool", {}).get("pct")
        lit_pct = data.get("lit_exchange", {}).get("pct")
        max_pain = data.get("max_pain")
        current_price = data.get("current_price")

        if dp_pct is not None and lit_pct is not None:
            if dp_pct < 25 and lit_pct > 75:
                parts.append(
                    f"Institutions sold mainly on lit exchanges ({lit_pct:.1f}% lit vs {dp_pct:.1f}% dark), "
                    "suggesting distribution into public liquidity."
                )

        if max_pain is not None and current_price is not None:
            distance = abs(current_price - max_pain)
            if current_price > 0 and distance > current_price * 0.02:
                parts.append(
                    f"Options max pain at ${max_pain:.2f}, current at ${current_price:.2f} "
                    f"(distance {distance:.2f}), implying OPEX pinning pressure."
                )

        if not parts:
            parts.append("No strong institutional flow pattern detected (V1 heuristic).")

        return " ".join(parts)

    def _extract_causal_chain(self, data: Dict[str, Any], divergences: List[Dict[str, Any]]) -> str:
        """
        A → B → C (institutional action → mechanics → price result).
        """
        if divergences:
            primary = divergences[0]
            t = primary.get("type")
            if t == "DISTRIBUTION_MASKED_AS_RALLY":
                return (
                    "Institutions used strength to sell on lit exchanges "
                    "→ retail absorbed supply at poor prices → late-day fade / selloff."
                )
            if t == "OPEX_MANIPULATION_LIKELY":
                return (
                    "Large options positioning around max pain "
                    "→ dealers push price toward strike cluster → mean-reversion move into OPEX."
                )
            if t == "LIQUIDITY_CRISIS_SIGNAL":
                return (
                    "Forced liquidations across crypto and equities "
                    "→ broad risk-off de-leveraging → correlated downside across assets."
                )

        return "Normal price action (no clear manipulation or distribution detected by V1 rules)."

    def generate_real_narrative(
        self,
        symbol: str,
        date: str,
        institutional_data: Dict[str, Any],
        news_narrative: str,
        divergences: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build the combined institutional + mainstream narrative package.
        """
        inst_story = self._build_institutional_story(institutional_data)
        causal_chain = self._extract_causal_chain(institutional_data, divergences)

        return {
            "date": date,
            "symbol": symbol,
            "institutional_reality": {
                "summary": inst_story,
                "causal_chain": causal_chain,
            },
            "mainstream_narrative": {
                "summary": news_narrative,
            },
            "divergences": divergences,
        }


def _demo() -> None:
    """
    Simple manual demo:
        python -m live_monitoring.enrichment.institutional_narrative
    """
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    symbol = "SPY"
    today = datetime.utcnow().strftime("%Y-%m-%d")

    print("=" * 80)
    print(f"🧪 INSTITUTIONAL NARRATIVE DEMO - {symbol} {today}")
    print("=" * 80)

    data = load_institutional_context(symbol, today)
    print("Context:", json.dumps(data, indent=2))

    # Dummy news narrative for divergence test
    news = "SPY rallied strongly today on bullish AI optimism and normal volatility."

    det = DivergenceDetector()
    divs = det.detect_manipulation(symbol, today, news, data)

    synth = InstitutionalNarrativeSynthesizer()
    narrative = synth.generate_real_narrative(symbol, today, data, news, divs)

    print("\nNarrative package:\n", json.dumps(narrative, indent=2))


if __name__ == "__main__":
    _demo()


