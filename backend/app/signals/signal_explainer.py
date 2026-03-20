"""
Signal Explainer — LLM-Powered Plain English Explanations
==========================================================
Takes raw signal data + per-signal prompt templates → Cohere inference → 
2-3 sentence plain English explanation.

Each signal gets:
  1. What this means for a trader
  2. What typically happens next
  3. What would INVALIDATE this signal
"""
import logging
import os
import json
from typing import Dict, Optional

logger = logging.getLogger(__name__)

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
COHERE_MODEL = "command-r-plus-08-2024"


# ─── Per-Signal Prompt Templates ─────────────────────────────────────────────

SIGNAL_PROMPTS = {
    "BRAIN": """You are a trading intelligence system. Given this data:
- Divergence boost: {boost} points
- Reasons: {reasons}

In 2-3 sentences, explain:
1. What this insider/politician activity means for a trader
2. Historical pattern: politicians win 3-6 weeks, insiders win 3-6 months
3. What would INVALIDATE this signal
Be direct. No jargon.""",

    "COT": """You are a trading intelligence system. Given this COT data:
- Speculator net position: {specs_net:+,} contracts
- Commercial net position: {comms_net:+,} contracts
- Report date: {report_date}
- Divergent: {divergent}

In 2-3 sentences, explain:
1. What this means in plain English for a trader
2. At this spec extreme, markets historically reversed upward in what % of cases
3. What would INVALIDATE this signal (specs ADD to shorts = confirmation not reversal)
Be direct. No jargon. Assume the trader is smart but not a quant.""",

    "GEX": """You are a trading intelligence system. Given this GEX data:
- Total gamma exposure: ${total_gex_display}
- Gamma regime: {gamma_regime} (dealers {dealer_behavior} moves)
- Gamma flip level: {gamma_flip}
- Spot price: ${spot_price}

In 2-3 sentences, explain:
1. What negative/positive gamma means mechanically (dealers must sell/buy)
2. Snap-back velocity potential once gamma flip level is reclaimed
3. When this regime expires (next OPEX)
Be direct. No jargon.""",

    "FED_DP": """You are a trading intelligence system. Given this data:
- SPY short volume: {sv_pct:.1f}%
- Fed tone from officials: {fed_tone}
- Divergence detected: {divergence}

In 2-3 sentences, explain:
1. What {sv_pct:.1f}% short volume means (above/below 50% threshold)
2. Whether the Fed tone and dark pool flow agree or diverge
3. What would INVALIDATE this (SV% trend reversal)
Be direct.""",

    "COMBINED": """You are a trading intelligence system. Given combined signals:
- COT extreme: {cot_extreme} (specs deep short)
- GEX regime: {gex_regime}
- Combined score: +{combined_score}

In 2-3 sentences, explain:
1. What COT extreme + GEX convergence means (coil loaded)
2. Historical snap-back average when these converge
3. The specific trigger that releases the coil
Be direct.""",
}


# ─── Explainer Class ─────────────────────────────────────────────────────────

class SignalExplainer:
    """
    LLM-powered explanation engine for Kill Shots signals.
    
    Uses Cohere command-r-plus to generate plain-English explanations
    for each signal layer. Caches results per signal to avoid redundant calls.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or COHERE_API_KEY
        self._client = None
        self._cache: Dict[str, str] = {}
        self._init_client()

    def _init_client(self):
        try:
            import cohere
            self._client = cohere.ClientV2(api_key=self.api_key)
            logger.info("✅ SignalExplainer Cohere client initialized")
        except ImportError:
            logger.warning("⚠️ cohere not installed — explanations will use templates")
        except Exception as e:
            logger.warning(f"⚠️ SignalExplainer init error: {e}")

    def explain(self, signal_name: str, raw_data: dict) -> str:
        """
        Generate plain-English explanation for a signal.
        
        Args:
            signal_name: One of BRAIN, COT, GEX, FED_DP, COMBINED
            raw_data: Dict of raw values to inject into the prompt template
            
        Returns:
            2-3 sentence plain English explanation, or template fallback
        """
        cache_key = f"{signal_name}_{hash(json.dumps(raw_data, default=str))}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        template = SIGNAL_PROMPTS.get(signal_name)
        if not template:
            return ""

        try:
            prompt = template.format(**raw_data)
        except KeyError as e:
            logger.warning(f"Missing key {e} for {signal_name} prompt")
            return ""

        if not self._client:
            # Template fallback — no LLM available
            return self._template_fallback(signal_name, raw_data)

        try:
            response = self._client.chat(
                model=COHERE_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "You are a concise trading intelligence explainer. "
                        "Answer in exactly 2-3 sentences. No bullet points. "
                        "No disclaimers. Be direct and actionable."
                    )},
                    {"role": "user", "content": prompt},
                ]
            )
            # Extract text from Cohere V2 response
            msg = response.message
            text = ""
            if hasattr(msg, "content"):
                content = msg.content
                if isinstance(content, list):
                    for block in content:
                        if hasattr(block, "text") and block.text:
                            text += block.text
                elif isinstance(content, str):
                    text = content
            elif hasattr(msg, "text"):
                text = msg.text

            explanation = text.strip()
            self._cache[cache_key] = explanation
            logger.info(f"✅ LLM explanation generated for {signal_name}")
            return explanation

        except Exception as e:
            logger.warning(f"⚠️ LLM explanation failed for {signal_name}: {e}")
            return self._template_fallback(signal_name, raw_data)

    def _template_fallback(self, signal_name: str, data: dict) -> str:
        """Deterministic fallback when LLM is unavailable."""
        if signal_name == "COT":
            specs = data.get("specs_net", 0)
            comms = data.get("comms_net", 0)
            return (
                f"Speculators are net short {abs(specs):,} contracts — this is an extreme "
                f"positioning that historically precedes reversals. Commercials at +{comms:,} "
                f"are on the other side. Invalidated if specs add to shorts next report."
            )
        elif signal_name == "GEX":
            gex = data.get("total_gex_display", "N/A")
            regime = data.get("gamma_regime", "UNKNOWN")
            return (
                f"Gamma exposure is {gex} ({regime} regime). "
                f"Dealers must {'sell into drops and buy into rips, amplifying volatility' if 'NEG' in regime else 'buy dips and sell rips, dampening volatility'}. "
                f"Regime resets at next monthly OPEX expiration."
            )
        elif signal_name == "BRAIN":
            return (
                f"Insider/politician activity detected with +{data.get('boost', 0)} conviction boost. "
                f"Politicians tend to win the next 3-6 weeks; insiders tend to win 3-6 months."
            )
        elif signal_name == "FED_DP":
            sv = data.get("sv_pct", 0)
            return (
                f"SPY dark pool short volume is {sv:.1f}%. "
                f"{'Above 55% indicates institutional short positioning' if sv > 55 else 'Below 55% indicates normal flow'}. "
                f"Direction of the trend matters more than the absolute number."
            )
        elif signal_name == "COMBINED":
            return (
                f"COT extreme + GEX convergence detected. When these signals align, "
                f"snap-back rallies average 3-5% over 5-10 trading days historically. "
                f"The trigger is SPX reclaiming the gamma flip level."
            )
        return ""

    def explain_all(self, layers: dict) -> dict:
        """
        Generate explanations for all active signals in a kill-shots layers dict.
        Returns dict of {signal_name: explanation}.
        """
        explanations = {}

        # Brain — always explain (boost=0 is still a valid null signal to explain)
        explanations["BRAIN"] = self.explain("BRAIN", {
            "boost": layers.get("brain_boost", 0),
            "reasons": "; ".join(layers.get("brain_reasons", [])) or "No active conviction signals from this scan.",
        })

        # COT
        if layers.get("cot_divergent"):
            explanations["COT"] = self.explain("COT", {
                "specs_net": layers.get("cot_specs_net", 0),
                "comms_net": layers.get("cot_comm_net", 0),
                "report_date": layers.get("cot_source_date", "unknown"),
                "divergent": layers.get("cot_divergent", False),
            })

        # GEX — always explain when we have GEX data
        total_gex = layers.get("total_gex_dollars", 0)
        if total_gex != 0:
            regime = layers.get("gex_regime", "UNKNOWN")
            is_neg = "NEGATIVE" in regime
            explanations["GEX"] = self.explain("GEX", {
                "total_gex_display": f"{total_gex/1e9:.1f}B",
                "gamma_regime": regime,
                "dealer_behavior": "AMPLIFY" if is_neg else "DAMPEN",
                "gamma_flip": layers.get("gex_gamma_flip", "N/A"),
                "spot_price": f"{layers.get('gex_spot_price', 0):,.2f}",
            })

        # Fed vs DP
        if "spy_short_vol_pct" in layers:
            explanations["FED_DP"] = self.explain("FED_DP", {
                "sv_pct": layers.get("spy_short_vol_pct", 0),
                "fed_tone": "HAWKISH" if layers.get("fed_dp_divergence") else "NEUTRAL",
                "divergence": layers.get("fed_dp_divergence", False),
            })

        # Combined
        if layers.get("combined_boost", 0) > 0:
            explanations["COMBINED"] = self.explain("COMBINED", {
                "cot_extreme": layers.get("cot_boost", 0) >= 3,
                "gex_regime": layers.get("gex_regime", "UNKNOWN"),
                "combined_score": layers.get("combined_boost", 0),
            })

        return explanations
