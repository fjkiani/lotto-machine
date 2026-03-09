"""
Narrative Agent — Regime-Agnostic Market Synthesizer
=====================================================
Uses Cohere command-a-reasoning-08-2025 to produce a structured
market narrative for ANY regime: rally, dump, chop, squeeze, OPEX pin.

Replaces the old selloff-only Gemini approach.

Data inputs:
  - RSS News (always live, no key)
  - Stockgrid Dark Pool (live, no key)
  - Crypto Correlation (yfinance, live)
  - Economic Events (Yahoo Calendar via EventLoader)
  - Kill Chain Intelligence (5-layer institutional scan)
  - yfinance price/VIX snapshot

Output: NarrativeResult dataclass with full structured analysis.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
COHERE_MODEL = "command-a-reasoning-08-2025"


# ─────────────────────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NarrativeResult:
    """Structured output from the regime-agnostic narrative synthesizer."""
    symbol: str
    date: str
    timestamp: str

    # Core thesis
    thesis: str = ""
    causal_chain: str = ""          # "A → B → C"
    direction: str = "NEUTRAL"      # BULLISH | BEARISH | NEUTRAL
    conviction: str = "LOW"         # HIGH | MEDIUM | LOW
    duration: str = "INTRADAY"      # INTRADAY | MULTI_DAY | WEEK
    risk_environment: str = "NEUTRAL"  # RISK_ON | RISK_OFF | NEUTRAL | ACCUMULATION | DISTRIBUTION

    # Supporting analysis
    key_catalysts: List[str] = field(default_factory=list)
    institutional_read: str = ""
    crypto_read: str = ""
    macro_read: str = ""

    # Signal boosts
    confidence_adjustment: float = 0.0   # +0.15 aligned HIGH, -0.30 contradiction
    confidence_rationale: str = ""

    # Meta
    uncertainties: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    raw_reasoning: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# NarrativeAgent
# ─────────────────────────────────────────────────────────────────────────────

class NarrativeAgent:
    """
    Regime-agnostic narrative synthesizer.

    Usage
    -----
    agent = NarrativeAgent()
    result = agent.analyze_market_state("SPY", context)
    enriched = agent.enrich_signal(signal, "SPY", context)
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or COHERE_API_KEY
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize Cohere client with version-safe response handling."""
        try:
            import cohere
            self._client = cohere.ClientV2(api_key=self.api_key)
            logger.info("✅ Cohere ClientV2 initialized (command-a-reasoning-08-2025)")
        except ImportError:
            logger.error("❌ cohere not installed — run: pip install cohere")
        except Exception as e:
            logger.error(f"❌ Cohere init failed: {e}")

    # ─── Public API ──────────────────────────────────────────────────────────

    def analyze_market_state(
        self,
        symbol: str,
        context: Dict[str, Any],
        date: str = None,
    ) -> NarrativeResult:
        """
        Regime-agnostic market analysis. Handles any market state.

        Parameters
        ----------
        symbol : str
            Ticker (e.g. "SPY", "QQQ")
        context : dict
            Keys expected (all optional with graceful fallback):
              news          – dict from FreeNewsFetcher / news_aggregator
              dark_pool     – dict from StockgridClient
              crypto        – CryptoSentiment or dict
              events        – dict from EventLoader.load_events()
              kill_chain    – dict from KillChainEngine.run_full_scan()
              price         – dict {price, change_pct, vix}
        date : str
            YYYY-MM-DD (defaults to today)
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M ET")

        result = NarrativeResult(symbol=symbol, date=date, timestamp=ts)

        try:
            market_ctx = self._build_market_context(symbol, context)
            raw_json = self._call_cohere(symbol, market_ctx)
            self._parse_response(raw_json, result)
            self._apply_confidence_boost(result, context)
            result.sources = self._extract_sources(context)
            logger.info(f"✅ Narrative: {result.direction} | {result.conviction} | {result.thesis[:60]}...")
        except Exception as e:
            logger.error(f"❌ analyze_market_state failed: {e}", exc_info=True)
            result.thesis = f"Narrative generation error: {e}"
            result.uncertainties.append(str(e))

        return result

    def enrich_signal(
        self,
        signal: Any,
        symbol: str,
        context: Dict[str, Any],
    ) -> Any:
        """
        Enrich a signal object with narrative and apply confidence boost/veto.
        Works with any signal object that has `.confidence` and `.rationale`.
        """
        try:
            result = self.analyze_market_state(symbol, context)

            if hasattr(signal, "confidence"):
                old = signal.confidence
                signal.confidence = max(0.0, min(1.0, signal.confidence + result.confidence_adjustment))
                logger.info(f"Signal confidence: {old:.2%} → {signal.confidence:.2%} ({result.confidence_adjustment:+.2%})")

            if hasattr(signal, "rationale") and result.thesis:
                signal.rationale = f"{signal.rationale} | NARRATIVE: {result.thesis[:120]}"

            if hasattr(signal, "narrative_analysis"):
                signal.narrative_analysis = result.to_dict()

        except Exception as e:
            logger.warning(f"⚠️  enrich_signal failed: {e}")

        return signal

    # ─── Context Builder ─────────────────────────────────────────────────────

    def _build_market_context(self, symbol: str, context: Dict) -> str:
        """Build a rich, grounded context block for the Cohere prompt."""
        lines = [f"SYMBOL: {symbol}", f"DATE: {datetime.now().strftime('%Y-%m-%d %H:%M ET')}", ""]

        # ── Price Snapshot ──────────────────────────────────────────────────
        price_data = context.get("price", {})
        if price_data:
            lines.append("── PRICE SNAPSHOT ──")
            lines.append(f"  Price:    ${price_data.get('price', 'N/A')}")
            lines.append(f"  Change:   {price_data.get('change_pct', 0)*100:+.2f}%")
            lines.append(f"  VIX:      {price_data.get('vix', 'N/A')}")
        else:
            # Pull live if not provided
            try:
                import yfinance as yf
                spy = yf.Ticker(symbol)
                hist = spy.history(period="2d", interval="1d")
                vix = yf.Ticker("^VIX").history(period="2d", interval="1d")
                if not hist.empty:
                    close = float(hist["Close"].iloc[-1])
                    prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else close
                    chg = (close - prev) / prev
                    vix_val = float(vix["Close"].iloc[-1]) if not vix.empty else "N/A"
                    lines.append("── PRICE SNAPSHOT ──")
                    lines.append(f"  Price: ${close:.2f} | Change: {chg*100:+.2f}% | VIX: {vix_val}")
            except Exception:
                lines.append("  Price: N/A (yfinance unavailable)")

        lines.append("")

        # ── News Sentiment ──────────────────────────────────────────────────
        news = context.get("news", {})
        if news:
            lines.append("── NEWS / SENTIMENT ──")
            lines.append(f"  Source:    {news.get('source', 'RSS')}")
            lines.append(f"  Articles:  {news.get('total_articles', 0)}")
            lines.append(f"  Sentiment: {news.get('sentiment', 'NEUTRAL')} "
                         f"({news.get('bullish_pct', 0):.0f}% bull / {news.get('bearish_pct', 0):.0f}% bear)")
            # Top headlines
            articles = news.get("articles", [])
            if articles:
                lines.append("  Headlines:")
                for a in articles[:5]:
                    title = a.get("title", a.get("headline", ""))[:90]
                    if title:
                        lines.append(f"    • {title}")
        else:
            lines.append("── NEWS ──\n  No news data available")

        lines.append("")

        # ── Dark Pool / Institutional ──────────────────────────────────────
        dp = context.get("dark_pool", {})
        if dp:
            lines.append("── DARK POOL (Stockgrid) ──")
            pct = dp.get("pct") or dp.get("short_volume_pct") or dp.get("Short Volume %")
            vol = dp.get("volume") or dp.get("dp_volume")
            pos = dp.get("dp_position") or dp.get("DP Position $")
            lines.append(f"  Short Vol %:  {pct:.1f}%" if isinstance(pct, (int, float)) else f"  Short Vol %:  {pct}")
            lines.append(f"  DP Volume:    ${abs(vol)/1e9:.1f}B" if isinstance(vol, (int, float)) else f"  DP Volume:    {vol}")
            lines.append(f"  Net Position: ${abs(pos)/1e9:.2f}B" if isinstance(pos, (int, float)) else f"  Net Position: {pos}")
        else:
            lines.append("── DARK POOL ──\n  No DP data available")

        lines.append("")

        # ── Crypto Correlation ──────────────────────────────────────────────
        crypto = context.get("crypto", {})
        if crypto:
            # Handle both CryptoSentiment dataclass and plain dict
            if hasattr(crypto, "btc_price"):
                btc_chg = getattr(crypto, "btc_change_pct", 0) * 100
                eth_chg = getattr(crypto, "eth_change_pct", 0) * 100
                env_raw = getattr(crypto, "environment", None) or getattr(crypto, "risk_environment", "N/A")
                env = env_raw.name if hasattr(env_raw, "name") else str(env_raw)
                corr = getattr(crypto, "correlation", 0)
                lines.append("── CRYPTO CORRELATION ──")
                lines.append(f"  BTC: {btc_chg:+.2f}% | ETH: {eth_chg:+.2f}%")
                lines.append(f"  Risk Env: {env} | SPY corr: {corr:.2f}")
            elif isinstance(crypto, dict):
                lines.append("── CRYPTO CORRELATION ──")
                lines.append(f"  BTC: {crypto.get('btc_change_pct', 0)*100:+.2f}%")
                lines.append(f"  Risk Env: {crypto.get('risk_environment', 'N/A')}")

        lines.append("")

        # ── Economic Events ─────────────────────────────────────────────────
        events = context.get("events", {})
        if events and events.get("has_events"):
            lines.append("── ECONOMIC EVENTS TODAY ──")
            for e in events.get("macro_events", [])[:5]:
                sigma = f" (Surprise: {e['surprise_sigma']:+.1f}σ)" if e.get("surprise_sigma") else ""
                lines.append(f"  • {e.get('time','?')} {e.get('name','?')[:45]} | {e.get('impact','?').upper()} | "
                             f"Act: {e.get('actual','?')} / Fcst: {e.get('forecast','?')}{sigma}")
            if events.get("opex"):
                lines.append("  ⚠️  MONTHLY OPEX DAY")
        else:
            lines.append("── ECONOMIC EVENTS ──\n  No high-impact events scheduled today")

        lines.append("")

        # ── Kill Chain Intelligence ─────────────────────────────────────────
        kc = context.get("kill_chain", {})
        if kc:
            lines.append("── KILL CHAIN INTELLIGENCE (5-Layer) ──")
            # Handle KillChainReport object or plain dict
            if hasattr(kc, "alerts"):
                alerts = kc.alerts or []
                score = getattr(kc, "overall_score", "N/A")
                mismatches = getattr(kc, "mismatches", [])
                lines.append(f"  Overall Score: {score}")
                if alerts:
                    lines.append(f"  Alerts ({len(alerts)}):")
                    for a in alerts[:3]:
                        lines.append(f"    ⚠️  {a}")
                if mismatches:
                    lines.append(f"  Mismatches ({len(mismatches)}):")
                    for m in mismatches[:3]:
                        lines.append(f"    → {m}")
            elif isinstance(kc, dict):
                layers = kc.get("layers", {})
                for layer_name, layer_data in list(layers.items())[:5]:
                    lines.append(f"  {layer_name}: {str(layer_data)[:80]}")
                alerts = kc.get("alerts", [])
                if alerts:
                    for a in alerts[:3]:
                        lines.append(f"  ⚠️  {a}")
        else:
            lines.append("── KILL CHAIN ──\n  Intelligence not available")

        return "\n".join(lines)

    # ─── Cohere Call ─────────────────────────────────────────────────────────

    def _call_cohere(self, symbol: str, market_ctx: str) -> str:
        """Call Cohere command-a-reasoning and return raw text."""
        if not self._client:
            raise RuntimeError("Cohere client not initialized")

        system_prompt = (
            "You are a ruthless, regime-agnostic market intelligence engine. "
            "Analyze the provided multi-source market data and produce a structured JSON narrative. "
            "Do NOT make up data. Only use what is explicitly provided. "
            "If data is missing for a field, say 'Insufficient data'. "
            "Never hedge with disclaimers. Be precise and actionable."
        )

        user_prompt = f"""
Analyze the following market intelligence data for {symbol} and return ONLY a JSON object.

{market_ctx}

Return EXACTLY this JSON structure (no markdown, no explanation, pure JSON):
{{
  "thesis": "2-3 sentence explanation of WHY the market is doing what it's doing",
  "causal_chain": "EventA → MarketImpactB → PriceActionC",
  "direction": "BULLISH|BEARISH|NEUTRAL",
  "conviction": "HIGH|MEDIUM|LOW",
  "duration": "INTRADAY|MULTI_DAY|WEEK",
  "risk_environment": "RISK_ON|RISK_OFF|NEUTRAL|ACCUMULATION|DISTRIBUTION",
  "key_catalysts": ["catalyst1", "catalyst2", "catalyst3"],
  "institutional_read": "What dark pool data tells us institutions are doing",
  "crypto_read": "What BTC/ETH correlation implies for risk sentiment",
  "macro_read": "What today's macro events / rates indicate",
  "confidence_adjustment": 0.0,
  "confidence_rationale": "Why this narrative boosts or penalizes signal confidence",
  "uncertainties": ["Unknown factor 1", "Unknown factor 2"]
}}

Rules:
- confidence_adjustment: +0.10 to +0.20 if narrative strongly aligns with SELL signals, -0.10 to -0.30 if it contradicts
- conviction HIGH = all data sources agree | MEDIUM = mixed signals | LOW = conflicting data
- Never output anything except the JSON object
"""

        try:
            response = self._client.chat(
                model=COHERE_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
            # Handle Cohere V2 response — content may be a list of typed blocks
            msg = response.message
            text = ""
            if hasattr(msg, "content"):
                content = msg.content
                if isinstance(content, list):
                    for block in content:
                        # ThinkingAssistantMessageResponseContentItem has .thinking
                        # TextAssistantMessageResponseContentItem has .text
                        if hasattr(block, "text") and block.text:
                            text += block.text
                        elif hasattr(block, "thinking") and block.thinking:
                            pass  # skip thinking blocks, only take text
                elif isinstance(content, str):
                    text = content
            elif hasattr(msg, "text"):
                text = msg.text

            return text.strip()

        except Exception as e:
            logger.error(f"❌ Cohere API call failed: {e}")
            raise

    # ─── Response Parser ─────────────────────────────────────────────────────

    def _parse_response(self, raw: str, result: NarrativeResult):
        """Parse Cohere JSON response into NarrativeResult fields."""
        result.raw_reasoning = raw

        # Strip markdown code fences if present
        clean = raw.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1]) if len(lines) > 2 else clean

        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            # Try extracting JSON block from text
            import re
            match = re.search(r"\{[\s\S]+\}", clean)
            if match:
                try:
                    data = json.loads(match.group())
                except Exception:
                    logger.warning("⚠️  Could not parse Cohere JSON output")
                    result.thesis = clean[:300]
                    return
            else:
                result.thesis = clean[:300]
                return

        result.thesis = data.get("thesis", "")
        result.causal_chain = data.get("causal_chain", "")
        result.direction = data.get("direction", "NEUTRAL").upper()
        result.conviction = data.get("conviction", "LOW").upper()
        result.duration = data.get("duration", "INTRADAY").upper()
        result.risk_environment = data.get("risk_environment", "NEUTRAL").upper()
        result.key_catalysts = data.get("key_catalysts", [])
        result.institutional_read = data.get("institutional_read", "")
        result.crypto_read = data.get("crypto_read", "")
        result.macro_read = data.get("macro_read", "")
        result.confidence_adjustment = float(data.get("confidence_adjustment", 0.0))
        result.confidence_rationale = data.get("confidence_rationale", "")
        result.uncertainties = data.get("uncertainties", [])

    # ─── Confidence Boost ────────────────────────────────────────────────────

    def _apply_confidence_boost(self, result: NarrativeResult, context: Dict):
        """Adjust confidence_adjustment based on data agreement signals."""
        # If conviction is already set by Cohere, trust it
        # Apply bounds: max ±0.30
        result.confidence_adjustment = max(-0.30, min(0.20, result.confidence_adjustment))

        # Override if Cohere returned 0 but we have strong DP signal
        dp = context.get("dark_pool", {})
        pct = dp.get("pct") or dp.get("short_volume_pct") or 0
        if isinstance(pct, (int, float)):
            if pct > 65 and result.direction == "BEARISH" and result.conviction == "HIGH":
                # Strong DP short + bearish narrative = strong boost
                if result.confidence_adjustment < 0.10:
                    result.confidence_adjustment = 0.15
                    result.confidence_rationale += " | DP short >65% confirms bearish."
            elif pct < 35 and result.direction == "BULLISH" and result.conviction == "HIGH":
                if result.confidence_adjustment < 0.10:
                    result.confidence_adjustment = 0.12
                    result.confidence_rationale += " | DP long >65% confirms bullish."

    def _extract_sources(self, context: Dict) -> List[str]:
        """Build list of data sources actually used."""
        sources = []
        if context.get("news"):
            sources.append(f"RSS ({context['news'].get('total_articles', 0)} articles)")
        if context.get("dark_pool"):
            sources.append("Stockgrid Dark Pool")
        if context.get("crypto"):
            sources.append("yfinance Crypto Correlation")
        if context.get("events", {}).get("has_events"):
            n = len(context["events"].get("macro_events", []))
            sources.append(f"Yahoo Economic Calendar ({n} events)")
        if context.get("kill_chain"):
            sources.append("Kill Chain Intelligence (5-layer)")
        return sources

    # ─── Backward Compat ────────────────────────────────────────────────────

    def analyze_selloff(self, signal: Any, context: Dict) -> Any:
        """
        Backward-compatible wrapper. Routes to analyze_market_state.
        Old callers won't break.
        """
        logger.warning("⚠️  analyze_selloff() is deprecated. Use analyze_market_state().")
        symbol = getattr(signal, "symbol", "SPY")
        result = self.analyze_market_state(symbol, context)
        return self.enrich_signal(signal, symbol, context)
