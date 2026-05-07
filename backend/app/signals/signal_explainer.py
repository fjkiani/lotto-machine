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
        """Single LLM call that produces structured per-signal reads with specific numbers.
        Returns JSON with one verdict per signal — not a narrative paragraph.
        Uses OpenRouter (free) with Groq fallback.
        """
        import json as _json

        # ── Build context with every number the LLM needs ────────────────────
        spy_spot = layers.get("gex_spot_price") or layers.get("axlfi_spot") or 0
        call_wall = layers.get("axlfi_call_wall") or 0
        put_wall = layers.get("axlfi_put_wall") or 0
        above_call = round(spy_spot - call_wall, 2) if spy_spot and call_wall else None
        gamma_flip = layers.get("gex_gamma_flip")
        cot_specs = layers.get("cot_specs_net", 0)
        cot_comms = layers.get("cot_comm_net", 0)
        sv_pct = layers.get("sv_pct") or layers.get("spy_short_vol_pct") or 0
        vix = layers.get("vix")
        fed_hours = layers.get("fed_veto_hours")
        fed_event = layers.get("fed_veto_next")
        alpha_verdict = layers.get("alpha_graph_verdict")
        alpha_conf = layers.get("alpha_graph_confidence")
        pol_tickers = layers.get("politician_tickers") or []
        pol_signal = layers.get("politician_signal", "NONE")
        absorption = layers.get("absorption_detected", False)
        absorption_price = layers.get("absorption_price")
        absorption_ratio = layers.get("absorption_vol_ratio")
        qqq_sv_delta = layers.get("qqq_sv_delta")
        qqq_sv_latest = layers.get("qqq_sv_latest")
        gex_regime = layers.get("gex_regime", "UNKNOWN")
        gex_total_m = round((layers.get("gex_total") or layers.get("total_gex_dollars") or 0) / 1e6, 1)
        session_trend = layers.get("spy_session_trend")

        context = {
            # Position structure
            "COT": {
                "specs_net": cot_specs,
                "comms_net": cot_comms,
                "divergent": layers.get("cot_divergent", False),
                "read": "CROWDED_SHORT" if cot_specs < -80000 else "NEUTRAL",
            },
            # Options structure
            "WALLS": {
                "spy_spot": spy_spot,
                "call_wall": call_wall,
                "put_wall": put_wall,
                "pts_above_call_wall": above_call,
                "gamma_flip": gamma_flip,
                "session_trend": session_trend,
                "signal": layers.get("axlfi_signal", "UNKNOWN"),
            },
            # Volatility / GEX
            "GEX": {
                "regime": gex_regime,
                "total_millions": gex_total_m,
                "gamma_flip": gamma_flip,
                "vix": vix,
            },
            # Dark pool flow
            "FLOW": {
                "spy_short_vol_pct": sv_pct,
                "qqq_short_vol_latest": qqq_sv_latest,
                "qqq_short_vol_1day_delta": qqq_sv_delta,
                "absorption_detected": absorption,
                "absorption_price": absorption_price,
                "absorption_vol_ratio": absorption_ratio,
            },
            # Macro catalyst
            "CATALYST": {
                "fed_veto_hours": fed_hours,
                "fed_veto_event": fed_event,
                "veto_active": bool(fed_hours and fed_hours <= 4),
            },
            # Alpha graph
            "ALPHA_GRAPH": {
                "verdict": alpha_verdict,
                "confidence": alpha_conf,
            },
            # Smart money
            "SMART_MONEY": {
                "politician_tickers": pol_tickers,
                "politician_signal": pol_signal,
            },
        }

        # Build pre-filled JSON template — LLM only fills in the "read" fields
        # This is faster and more reliable than asking the LLM to construct the whole structure
        spy_spot_str = str(spy_spot) if spy_spot else "N/A"
        call_wall_str = str(call_wall) if call_wall else "N/A"
        above_str = f"+{above_call}pts above" if above_call and above_call > 0 else (f"{above_call}pts below" if above_call else "N/A")
        gex_str = f"{gex_regime} ${gex_total_m}M flip {gamma_flip} VIX {vix}"
        cot_str = f"{cot_specs:,} specs / {cot_comms:+,} comms" if cot_specs else "N/A"
        flow_parts = [f"SPY SV {sv_pct:.1f}%"]
        if qqq_sv_delta is not None:
            flow_parts.append(f"QQQ {qqq_sv_delta:+.1f}pp 1d")
        if absorption:
            flow_parts.append(f"ABSORPTION {absorption_price} at {absorption_ratio}x vol")
        flow_str = " / ".join(flow_parts)
        catalyst_str = f"{fed_event} in {fed_hours:.1f}h" if fed_hours and fed_event else "none"
        alpha_str = f"{alpha_verdict} {alpha_conf:.0%}" if alpha_verdict and alpha_conf else "N/A"

        # Count bullish signals for COMBINED
        bullish_count = sum([
            cot_specs < -80000,                          # crowded short = squeeze fuel
            above_call is not None and above_call > 0,  # above call wall
            absorption is True,                          # absorption at close
            qqq_sv_delta is not None and qqq_sv_delta > 10,  # QQQ reshort spike
        ])
        combined_str = f"{bullish_count}/4 BULLISH signals"

        # Walls read hint
        walls_hint = f"SPY is {above_call}pts above the {call_wall} call wall" if above_call and above_call > 0 else f"SPY is {abs(above_call) if above_call else '?'}pts below the {call_wall} call wall"
        # Catalyst hint
        catalyst_hint = f"NFP in {fed_hours:.1f}h with crowded shorts = DETONATOR" if fed_hours and fed_hours < 36 and cot_specs < -80000 else f"{fed_event} in {fed_hours:.1f}h" if fed_hours else "no catalyst"
        # Flow hint
        flow_hint_parts = []
        if absorption:
            flow_hint_parts.append(f"absorption at {absorption_price} at {absorption_ratio}x vol")
        if qqq_sv_delta and qqq_sv_delta > 10:
            flow_hint_parts.append(f"QQQ reshorted +{qqq_sv_delta}pp = squeeze fuel")
        flow_hint = " + ".join(flow_hint_parts) if flow_hint_parts else f"SPY SV {sv_pct:.1f}%"

        prompt = f"""Output JSON only. Fill in each "read" field with one specific sentence using the numbers in "number". No markdown.

{{"COT":{{"number":"{cot_str}","read":"FILL — what does {cot_specs:,} specs net mean right now","verdict":"BULLISH","invalidation":"specs add to shorts next report"}},"WALLS":{{"number":"SPY {spy_spot_str} / call wall {call_wall_str} / {above_str}","read":"FILL — {walls_hint}","verdict":"BULLISH","invalidation":"SPY closes below {call_wall_str}"}},"GEX":{{"number":"{gex_str}","read":"FILL — what dealers are forced to do","verdict":"NEUTRAL","invalidation":"GEX flips negative"}},"FLOW":{{"number":"{flow_str}","read":"FILL — {flow_hint}","verdict":"BULLISH","invalidation":"absorption fails on open"}},"CATALYST":{{"number":"{catalyst_str}","read":"FILL — {catalyst_hint}","verdict":"DETONATOR","invalidation":"NFP miss triggers risk-off"}},"COMBINED":{{"number":"{combined_str} / alpha {alpha_str}","read":"FILL — name {call_wall_str} and {fed_event}","verdict":"HOLD","invalidation":"SPY breaks below {call_wall_str}"}}}}"""

        try:
            from backend.app.graph.openrouter_client import call_openrouter as _call_or
            from backend.app.graph.openrouter_client import extract_json as _extract_json
            response = _call_or(
                prompt=prompt,
                role="explain",
                max_tokens=700,
                timeout=20,
                use_cache=False,  # always fresh — data changes every call
            )
            raw_content = response.get("content", "")
            if not raw_content:
                raise ValueError("Empty response from OpenRouter")

            parsed = _extract_json(raw_content)
            if not parsed:
                raise ValueError(f"JSON parse failed. Raw: {raw_content[:200]}")

            # Format each signal block into a labeled string for the UI
            def _fmt(block: dict, label: str) -> str:
                if not block:
                    return ""
                number = block.get("number", "")
                read = block.get("read", "")
                verdict = block.get("verdict", "")
                inv = block.get("invalidation", "")
                parts = []
                if number:
                    parts.append(f"[{number}]")
                if read:
                    parts.append(read)
                if verdict:
                    parts.append(f"→ {verdict}")
                if inv:
                    parts.append(f"| Invalidated if: {inv}")
                return " ".join(parts)

            cot_text = _fmt(parsed.get("COT", {}), "COT")
            walls_text = _fmt(parsed.get("WALLS", {}), "WALLS")
            gex_text = _fmt(parsed.get("GEX", {}), "GEX")
            flow_text = _fmt(parsed.get("FLOW", {}), "FLOW")
            catalyst_text = _fmt(parsed.get("CATALYST", {}), "CATALYST")
            combined_text = _fmt(parsed.get("COMBINED", {}), "COMBINED")

            return {
                "COT": cot_text,
                "GEX": gex_text,
                "FED_DP": flow_text,
                "BRAIN": catalyst_text,
                "COMBINED": combined_text,
                # Extra structured fields for frontend
                "WALLS": walls_text,
                "CATALYST": catalyst_text,
                "signal_reads": parsed,  # raw JSON for any consumer that wants it
                "_unified": True,
                "_model": response.get("model", "unknown"),
                "_source": response.get("source", "unknown"),
            }
        except Exception as e:
            logger.warning(f"explain_unified failed: {e} — falling back to explain_all()")
            return self.explain_all(layers)
