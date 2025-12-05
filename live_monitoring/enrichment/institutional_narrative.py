"""
Institutional Narrative Layer

Implements the feedback from `.cursor/rules/feedback.mdc`:
- Load institutional data FIRST (dark pool, lit, options, max pain, crypto)
- Detect divergences between institutional flows and mainstream narrative
- Build an institutional-first narrative with a causal chain and trade hint

V1: Focus on SPY / QQQ using ChartExchange + CryptoCorrelationDetector + yfinance.
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

    # 1) ChartExchange institutional data (if API key present)
    import os

    api_key: Optional[str] = None

    # Primary: use the same config file the rest of the system uses
    try:
        from configs.chartexchange_config import CHARTEXCHANGE_API_KEY  # type: ignore

        if CHARTEXCHANGE_API_KEY and "your_api_key_here" not in CHARTEXCHANGE_API_KEY:
            api_key = CHARTEXCHANGE_API_KEY
            logger.info("Using CHARTEXCHANGE_API_KEY from configs.chartexchange_config.")
    except Exception:
        api_key = None

    # Fallback: environment variable (e.g. for deployment)
    if not api_key:
        env_key = os.getenv("CHARTEXCHANGE_API_KEY")
        if env_key:
            api_key = env_key
            logger.info("Using CHARTEXCHANGE_API_KEY from environment.")

    if api_key:
        try:
            from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient

            ce = UltimateChartExchangeClient(api_key=api_key, tier=3)
            
            # Dark pool data from LEVELS (aggregated by price level)
            dp_levels = ce.get_dark_pool_levels(symbol, date)
            dp_prints = ce.get_dark_pool_prints(symbol, date)
            
            # Calculate total DP volume from levels (dicts with 'volume' key)
            dp_vol = 0
            if dp_levels:
                for level in dp_levels:
                    if isinstance(level, dict) and 'volume' in level:
                        dp_vol += int(level['volume'])
            
            # Calculate total DP volume from prints as backup
            if dp_vol == 0 and dp_prints:
                for print_obj in dp_prints:
                    if isinstance(print_obj, dict) and 'size' in print_obj:
                        dp_vol += int(print_obj['size'])
            
            # Get lit exchange volume (try multiple methods)
            ex_vols = ce.get_exchange_volume(symbol, date)
            lit_vol = sum(ev.volume for ev in ex_vols) if ex_vols else 0
            
            # If exchange volume API returns 0, estimate from yfinance total volume
            if lit_vol == 0 and dp_vol > 0:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="2d", interval="1d")
                    if not hist.empty:
                        total_vol = int(hist["Volume"].iloc[-1])
                        lit_vol = max(0, total_vol - dp_vol)
                except Exception:
                    pass
            
            total = dp_vol + lit_vol
            if total > 0:
                dp_pct = dp_vol / total * 100.0
                lit_pct = lit_vol / total * 100.0
                ctx["dark_pool"]["pct"] = dp_pct
                ctx["dark_pool"]["volume"] = dp_vol
                ctx["lit_exchange"]["pct"] = lit_pct
                ctx["lit_exchange"]["volume"] = lit_vol
                logger.info(
                    "📊 DP data: %.1f%% DP (%s shares) vs %.1f%% lit (%s shares)",
                    dp_pct, f"{dp_vol:,}", lit_pct, f"{lit_vol:,}"
                )
            else:
                ctx["dark_pool"]["pct"] = None
                ctx["lit_exchange"]["pct"] = None
                logger.warning("No volume data available for %s on %s", symbol, date)

            # Options max pain (currently returns 400, skip for now)
            try:
                opt_summary = ce.get_options_chain_summary(symbol, date)
                if opt_summary:
                    ctx["max_pain"] = float(opt_summary.max_pain)
            except Exception as opt_e:
                logger.debug("Options summary not available: %s", opt_e)

        except Exception as e:
            logger.error("Error loading ChartExchange context for %s: %s", symbol, e)

    else:
        logger.warning(
            "CHARTEXCHANGE_API_KEY not found in configs.chartexchange_config or environment; "
            "institutional context will be partial."
        )

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
        CHARTEXCHANGE_API_KEY=... python -m live_monitoring.enrichment.institutional_narrative
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


