"""
Signal Explainer — LLM-Powered Plain English Explanations
==========================================================
Takes raw signal data + per-signal prompt templates → Groq inference → 
2-3 sentence plain English explanation.

Backend: Groq free tier (Llama 3.3 70B) — no monthly call limit.
Previously: Cohere trial (1000 calls/month, hit 429 at 28 remaining).

Each signal gets:
  1. What this means for a trader
  2. What typically happens next
  3. What would INVALIDATE this signal
"""
import logging
import os
import json
import time
import hashlib
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# 4-hour disk cache — survives restarts, keeps Groq rate limit safe
_CACHE_DIR = Path("/tmp/kill_shots_explanations")
_CACHE_TTL_SEC = 4 * 3600  # 4 hours


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
    
    Backend: Groq free tier (Llama 3.3 70B) — no monthly call limit.
    Disk cache: 4 hours per signal to stay under Groq's per-minute rate limits.
    Fallback: deterministic templates if Groq is unreachable.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GROQ_API_KEY
        self._mem_cache: Dict[str, str] = {}
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if self.api_key:
            logger.info("✅ SignalExplainer Groq client initialized (Llama 3.3 70B)")
        else:
            logger.warning("⚠️ GROQ_API_KEY not set — explanations will use templates")

    def _disk_cache_key(self, signal_name: str, raw_data: dict) -> str:
        """Stable hash for disk cache keying."""
        payload = json.dumps({"signal": signal_name, **raw_data}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def _read_disk_cache(self, cache_key: str) -> Optional[str]:
        """Read from 4-hour disk cache."""
        path = _CACHE_DIR / f"{cache_key}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                if time.time() - data.get("ts", 0) < _CACHE_TTL_SEC:
                    return data["text"]
            except Exception:
                pass
        return None

    def _write_disk_cache(self, cache_key: str, text: str):
        """Write to disk cache."""
        path = _CACHE_DIR / f"{cache_key}.json"
        try:
            path.write_text(json.dumps({"ts": time.time(), "text": text}))
        except Exception as e:
            logger.warning(f"Disk cache write failed: {e}")

    def explain(self, signal_name: str, raw_data: dict) -> str:
        """
        Generate plain-English explanation for a signal.
        
        Checks: mem cache → disk cache (4hr) → Groq API → template fallback.
        """
        dk = self._disk_cache_key(signal_name, raw_data)

        # 1. Memory cache
        if dk in self._mem_cache:
            return self._mem_cache[dk]

        # 2. Disk cache (4hr TTL)
        cached = self._read_disk_cache(dk)
        if cached:
            self._mem_cache[dk] = cached
            return cached

        # 3. Build prompt
        template = SIGNAL_PROMPTS.get(signal_name)
        if not template:
            return ""
        try:
            prompt = template.format(**raw_data)
        except KeyError as e:
            logger.warning(f"Missing key {e} for {signal_name} prompt")
            return ""

        if not self.api_key:
            return self._template_fallback(signal_name, raw_data)

        # 4. Groq API call (OpenAI-compatible)
        try:
            import httpx
            resp = httpx.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": (
                            "You are a concise trading intelligence explainer. "
                            "Answer in exactly 2-3 sentences. No bullet points. "
                            "No disclaimers. Be direct and actionable."
                        )},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 200,
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            explanation = resp.json()["choices"][0]["message"]["content"].strip()

            self._mem_cache[dk] = explanation
            self._write_disk_cache(dk, explanation)
            logger.info(f"✅ Groq explanation generated for {signal_name}")
            return explanation

        except Exception as e:
            logger.warning(f"⚠️ Groq explanation failed for {signal_name}: {e}")
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

    def explain_unified(self, layers: dict) -> dict:
        """Single LLM call reasoning across ALL scorers simultaneously.
        Replaces 5 serial explain() calls. Returns same key structure as explain_all().
        Uses OpenRouter (free) with Groq fallback.
        """
        import json as _json

        context = {
            "brain_boost": layers.get("brain_boost", 0),
            "brain_direction": layers.get("brain_direction", "NEUTRAL"),
            "cot_specs_net": layers.get("cot_specs_net", 0),
            "cot_divergent": layers.get("cot_divergent", False),
            "gex_regime": layers.get("gex_regime", "UNKNOWN"),
            "gex_total_millions": round(layers.get("gex_total", 0) / 1e6, 2),
            "sv_pct": layers.get("sv_pct", 50),
            "axlfi_call_wall": layers.get("axlfi_call_wall"),
            "axlfi_put_wall": layers.get("axlfi_put_wall"),
            "axlfi_signal": layers.get("axlfi_signal", "NONE"),
            "politician_cluster": layers.get("politician_cluster", 0),
            "politician_signal": layers.get("politician_signal", "NONE"),
            "fed_veto": layers.get("fed_veto"),
        }

        prompt = f"""You are a trading intelligence system. Given these simultaneous market signals:
{_json.dumps(context, indent=2)}

In 3-4 sentences total, explain:
1. What the COMBINATION of these signals means (not each individually)
2. The single most important signal and why it dominates
3. What would INVALIDATE the current setup

Be direct. No jargon. Assume a smart trader who wants the truth."""

        try:
            from backend.app.graph.openrouter_client import call_openrouter as _call_or
            response = _call_or(
                prompt=prompt,
                role="explain",
                max_tokens=400,
                timeout=12,
            )
            unified_text = response.get("content", "")
            if not unified_text:
                raise ValueError("Empty response from OpenRouter")
            return {
                "BRAIN": unified_text,
                "COT": unified_text,
                "GEX": unified_text,
                "FED_DP": unified_text,
                "COMBINED": unified_text,
                "_unified": True,
                "_model": response.get("model", "unknown"),
                "_source": response.get("source", "unknown"),
            }
        except Exception as e:
            logger.warning(f"explain_unified failed: {e} — falling back to explain_all()")
            return self.explain_all(layers)
