"""
LangGraph nodes for the Alpha pipeline.

Fan-out (parallel):  MacroNode, FlowNode, RegimeNode
Fan-in (sequential): SynthesisNode → GateNode → END
"""
import logging
import time
import json
from typing import Dict, Any

from backend.app.graph.state import AlphaState
from backend.app.graph.openrouter_client import call_openrouter, extract_json

logger = logging.getLogger(__name__)

# ── Shared prompt helpers ─────────────────────────────────────────────────────

def _safe_call(role: str, prompt: str, max_tokens: int = 500, timeout: int = 18) -> str:
    """Call OpenRouter and return content string. Never raises."""
    try:
        result = call_openrouter(prompt=prompt, role=role, max_tokens=max_tokens, timeout=timeout)
        return result.get("content", "") or ""
    except Exception as e:
        logger.warning(f"_safe_call({role}) failed: {e}")
        return ""


# ── MacroNode ─────────────────────────────────────────────────────────────────

def macro_node(state: AlphaState) -> AlphaState:
    """
    Reads COT positioning + Fed calendar context.
    Uses Qwen (262K ctx, thinking mode) — best for macro reasoning.
    """
    t0 = time.time()
    symbol = state.get("symbol", "SPY")
    errors = list(state.get("errors", []))
    timings = dict(state.get("node_timings", {}))

    # Pull live COT data if available
    cot_summary = "COT data unavailable"
    try:
        from live_monitoring.enrichment.apis.cot_client import COTClient
        cot = COTClient(cache_ttl=3600)
        sig = cot.get_divergence_signal("ES")
        if sig:
            cot_summary = (
                f"Specs net: {sig.get('specs_net', 0):,} contracts | "
                f"Divergent: {sig.get('divergent', False)} | "
                f"Signal: {sig.get('signal', 'UNKNOWN')}"
            )
    except Exception as e:
        errors.append(f"macro_node/cot: {e}")

    prompt = f"""You are a macro analyst. Given this COT positioning data for {symbol}:
{cot_summary}

In 3-4 sentences, explain:
1. What the current speculator positioning implies for near-term price direction
2. Whether this is a contrarian or trend-following signal
3. The key macro risk that could invalidate this positioning

Be direct and specific. No hedging."""

    content = _safe_call("macro", prompt, max_tokens=400)
    if not content:
        errors.append("macro_node: empty LLM response")
        content = f"Macro analysis unavailable. COT snapshot: {cot_summary}"

    timings["macro"] = round(time.time() - t0, 2)
    return {**state, "macro_context": content, "errors": errors, "node_timings": timings}


# ── FlowNode ──────────────────────────────────────────────────────────────────

def flow_node(state: AlphaState) -> AlphaState:
    """
    Reads dark pool + AXLFI option wall data.
    Uses Qwen — good for structured data reasoning.
    """
    t0 = time.time()
    symbol = state.get("symbol", "SPY")
    errors = list(state.get("errors", []))
    timings = dict(state.get("node_timings", {}))

    dp_summary = "Dark pool data unavailable"
    axlfi_summary = "AXLFI data unavailable"

    try:
        from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
        sg = StockgridClient(cache_ttl=300)
        walls = sg.get_option_walls_today(symbol)
        if walls:
            axlfi_summary = (
                f"Call wall: {walls.call_wall} | Put wall: {walls.put_wall} | "
                f"Net GEX: {getattr(walls, 'net_gex', 'N/A')}"
            )
    except Exception as e:
        errors.append(f"flow_node/axlfi: {e}")

    prompt = f"""You are a market microstructure analyst. Given these flow signals for {symbol}:
Dark Pool: {dp_summary}
AXLFI Option Walls: {axlfi_summary}

In 3-4 sentences, explain:
1. What the option wall positioning implies for price magnet/resistance levels
2. Whether dark pool flow is accumulation or distribution
3. The key level to watch in the next session

Be specific about price levels where relevant."""

    content = _safe_call("flow", prompt, max_tokens=400)
    if not content:
        errors.append("flow_node: empty LLM response")
        content = f"Flow analysis unavailable. AXLFI: {axlfi_summary}"

    timings["flow"] = round(time.time() - t0, 2)
    return {**state, "flow_context": content, "errors": errors, "node_timings": timings}


# ── RegimeNode ────────────────────────────────────────────────────────────────

def regime_node(state: AlphaState) -> AlphaState:
    """
    Reads GEX regime + short vol data.
    Uses Llama-3.3-70b — fast, good for structured classification.
    """
    t0 = time.time()
    symbol = state.get("symbol", "SPY")
    errors = list(state.get("errors", []))
    timings = dict(state.get("node_timings", {}))

    gex_summary = "GEX data unavailable"
    try:
        from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
        sg = StockgridClient(cache_ttl=300)
        gex = sg.get_gex_regime(symbol)
        if gex:
            gex_summary = (
                f"Regime: {gex.get('regime', 'UNKNOWN')} | "
                f"Total GEX: ${gex.get('total_gex', 0)/1e9:.1f}B | "
                f"Flip level: {gex.get('flip_level', 'N/A')}"
            )
    except Exception as e:
        errors.append(f"regime_node/gex: {e}")

    prompt = f"""You are a volatility regime analyst. Given this GEX data for {symbol}:
{gex_summary}

Answer in JSON only, no markdown:
{{
  "regime_label": "POSITIVE_GEX or NEGATIVE_GEX or TRANSITIONAL",
  "vol_expectation": "SUPPRESSED or ELEVATED or EXPLOSIVE",
  "dealer_positioning": "SHORT_GAMMA or LONG_GAMMA or NEUTRAL",
  "key_insight": "one sentence on what this means for intraday moves"
}}"""

    content = _safe_call("regime", prompt, max_tokens=300)
    parsed = extract_json(content) if content else None
    if parsed:
        regime_text = (
            f"Regime: {parsed.get('regime_label')} | "
            f"Vol: {parsed.get('vol_expectation')} | "
            f"Dealers: {parsed.get('dealer_positioning')} | "
            f"{parsed.get('key_insight', '')}"
        )
    else:
        errors.append("regime_node: JSON parse failed")
        regime_text = f"Regime analysis unavailable. GEX: {gex_summary}"

    timings["regime"] = round(time.time() - t0, 2)
    return {**state, "regime_context": regime_text, "errors": errors, "node_timings": timings}


# ── SynthesisNode ─────────────────────────────────────────────────────────────

def synthesis_node(state: AlphaState) -> AlphaState:
    """
    Combines macro + flow + regime into a unified verdict.
    Uses gpt-oss-120b:free — MoE reasoning, best for synthesis.
    """
    t0 = time.time()
    errors = list(state.get("errors", []))
    timings = dict(state.get("node_timings", {}))

    macro = state.get("macro_context", "unavailable")
    flow = state.get("flow_context", "unavailable")
    regime = state.get("regime_context", "unavailable")

    prompt = f"""You are the Alpha Commander. You have received three independent intelligence reports:

MACRO INTELLIGENCE:
{macro}

FLOW INTELLIGENCE:
{flow}

REGIME INTELLIGENCE:
{regime}

Synthesize these into a unified trading verdict. Answer in JSON only, no markdown:
{{
  "verdict": "ARMED or HOLD or VETO",
  "confidence": 0.75,
  "thesis": "2-sentence plain English trade thesis combining all three signals",
  "primary_risk": "single biggest risk that could invalidate this thesis",
  "direction": "BULLISH or BEARISH or MIXED",
  "synthesis_notes": "1 sentence on which signal dominated and why"
}}

Rules:
- ARMED = all signals aligned, high conviction
- HOLD = mixed signals, wait for clarity
- VETO = signals conflict or major risk event imminent"""

    content = _safe_call("synthesis", prompt, max_tokens=600, timeout=25)
    parsed = extract_json(content) if content else None

    if parsed:
        verdict = parsed.get("verdict", "HOLD")
        confidence = float(parsed.get("confidence", 0.5))
        thesis = parsed.get("thesis", "")
        primary_risk = parsed.get("primary_risk", "")
        direction = parsed.get("direction", "MIXED")
        synthesis_text = content
    else:
        errors.append("synthesis_node: JSON parse failed")
        verdict = "HOLD"
        confidence = 0.0
        thesis = "Synthesis failed — defaulting to HOLD"
        primary_risk = "LLM synthesis unavailable"
        direction = "MIXED"
        synthesis_text = content or "unavailable"

    timings["synthesis"] = round(time.time() - t0, 2)
    return {
        **state,
        "synthesis": synthesis_text,
        "verdict": verdict,
        "confidence": confidence,
        "thesis": thesis,
        "primary_risk": primary_risk,
        "direction": direction,
        "errors": errors,
        "node_timings": timings,
    }


# ── GateNode ──────────────────────────────────────────────────────────────────

def gate_node(state: AlphaState) -> AlphaState:
    """
    Pure Python gate: pulls live kill chain snapshot and applies veto logic.
    No LLM call — deterministic rule check.
    """
    t0 = time.time()
    errors = list(state.get("errors", []))
    timings = dict(state.get("node_timings", {}))
    verdict = state.get("verdict", "HOLD")
    confidence = state.get("confidence", 0.0)

    gate_result = {"kill_chain_available": False, "veto_applied": False}

    try:
        from backend.app.signals.kill_chain import compute_kill_chain
        kc = compute_kill_chain()
        gate_result["kill_chain_available"] = True
        gate_result["confluence"] = kc.get("confluence", "WAITING")
        gate_result["armed"] = kc.get("armed", False)
        gate_result["fed_veto_active"] = kc.get("fed_veto_active", False)
        gate_result["layer_4_triggered"] = kc.get("layer_4", {}).get("triggered", False)

        # Apply kill chain veto overrides
        if kc.get("fed_veto_active"):
            verdict = "VETO"
            confidence = max(confidence - 0.3, 0.0)
            gate_result["veto_applied"] = True
            gate_result["veto_reason"] = "Fed event veto active"
            errors.append("gate_node: Fed veto override applied")
        elif kc.get("confluence") == "WAITING" and verdict == "ARMED":
            verdict = "HOLD"
            gate_result["veto_applied"] = True
            gate_result["veto_reason"] = "Kill chain not armed — downgraded ARMED→HOLD"

    except Exception as e:
        errors.append(f"gate_node/kill_chain: {e}")

    timings["gate"] = round(time.time() - t0, 2)
    return {
        **state,
        "verdict": verdict,
        "confidence": confidence,
        "gate_result": gate_result,
        "errors": errors,
        "node_timings": timings,
    }
