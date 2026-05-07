"""
LangGraph nodes for the Alpha pipeline.

Fan-out (parallel):  MacroNode, FlowNode, RegimeNode
Fan-in (sequential): SynthesisNode → GateNode → END

IMPORTANT: Parallel nodes must return ONLY their own exclusive output key
plus their local slice of errors/node_timings (Annotated reducers merge them).
They must NOT return {**state, ...} — that causes InvalidUpdateError in LangGraph.
"""
import logging
import time
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

def macro_node(state: AlphaState) -> Dict[str, Any]:
    """
    Reads COT positioning + Fed calendar context.
    Returns ONLY macro_context, errors slice, node_timings slice.
    """
    t0 = time.time()
    symbol = state.get("symbol", "SPY")
    errors = []
    timings = {}

    cot_summary = "COT data unavailable"
    fed_summary = "Fed calendar unavailable"
    vix_val = None
    try:
        from live_monitoring.enrichment.apis.cot_client import COTClient
        cot = COTClient(cache_ttl=3600)
        sig = cot.get_divergence_signal("ES")
        if sig:
            cot_summary = (
                f"Specs net: {sig.get('specs_net', 0):,} contracts | "
                f"Commercials net: {sig.get('comm_net', 0):,} | "
                f"Divergent: {sig.get('divergent', False)} | "
                f"Signal: {sig.get('signal', 'UNKNOWN')}"
            )
    except Exception as e:
        errors.append(f"macro_node/cot: {e}")

    try:
        from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
        te = TECalendarScraper(cache_ttl=300)
        veto = te.get_hours_until_next_critical()
        if veto:
            hours_away, event_name = veto
            fed_summary = f"Next critical event: {event_name} in {hours_away:.1f} hours"
            if hours_away <= 4:
                fed_summary += " ⚠️ VETO ZONE"
    except Exception as e:
        errors.append(f"macro_node/fed: {e}")

    try:
        import yfinance as yf
        vix_val = round(yf.Ticker("^VIX").fast_info.get("lastPrice", 0), 2)
    except Exception:
        pass

    prompt = f"""You are a macro analyst. Given these live signals for {symbol}:

COT POSITIONING: {cot_summary}
FED CALENDAR: {fed_summary}
VIX: {vix_val if vix_val else "unavailable"}

Answer in JSON only, no markdown:
{{
  "cot_read": "one sentence: what the specs_net number means RIGHT NOW — is this squeeze fuel or distribution risk? Use the actual number.",
  "fed_read": "one sentence: is the upcoming event a detonator (forces shorts to cover) or a veto (stay flat)? Name the event and hours.",
  "vix_read": "one sentence: what VIX level means for vol regime — is vol suppressed (dealers long gamma, moves dampened) or elevated?",
  "dominant_factor": "the single number that dominates the setup and why",
  "regime": "RISK_ON or RISK_OFF or TRANSITIONAL"
}}"""

    content = _safe_call("macro", prompt, max_tokens=400)
    parsed_macro = extract_json(content) if content else None
    if parsed_macro:
        content = (
            f"COT: {parsed_macro.get('cot_read', '')} | "
            f"FED: {parsed_macro.get('fed_read', '')} | "
            f"VIX: {parsed_macro.get('vix_read', '')} | "
            f"DOMINANT: {parsed_macro.get('dominant_factor', '')} | "
            f"REGIME: {parsed_macro.get('regime', 'UNKNOWN')}"
        )
    elif not content:
        errors.append("macro_node: empty LLM response")
        content = f"Macro analysis unavailable. COT snapshot: {cot_summary}"

    timings["macro"] = round(time.time() - t0, 2)
    return {"macro_context": content, "errors": errors, "node_timings": timings}


# ── FlowNode ──────────────────────────────────────────────────────────────────

def flow_node(state: AlphaState) -> Dict[str, Any]:
    """
    Reads dark pool + AXLFI option wall data.
    Returns ONLY flow_context, errors slice, node_timings slice.
    """
    t0 = time.time()
    symbol = state.get("symbol", "SPY")
    errors = []
    timings = {}

    dp_summary = "Dark pool data unavailable"
    axlfi_summary = "AXLFI data unavailable"
    spot_price = None
    sv_pct = None

    _call_wall = None
    _put_wall = None
    above_call = None
    try:
        from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
        sg = StockgridClient(cache_ttl=300)
        walls = sg.get_option_walls_today(symbol)
        if walls:
            spot_price = getattr(walls, 'spot_price', None) or getattr(walls, 'current_price', None)
            _call_wall = getattr(walls, 'call_wall', None)
            _put_wall = getattr(walls, 'put_wall', None)
            above_call = round(spot_price - _call_wall, 2) if spot_price and _call_wall else None
            axlfi_summary = (
                f"Call wall: {_call_wall} | Put wall: {_put_wall} | "
                f"Spot: {spot_price} | "
                f"{'ABOVE call wall by ' + str(above_call) + 'pts' if above_call and above_call > 0 else 'BELOW call wall by ' + str(abs(above_call)) + 'pts' if above_call else 'wall proximity unknown'}"
            )
        sv_pct = sg.get_short_volume_pct(symbol)
        if sv_pct:
            dp_summary = f"Short volume: {sv_pct:.1f}% ({'elevated — distribution signal' if sv_pct > 55 else 'normal — no distribution' if sv_pct < 45 else 'neutral'})"
    except Exception as e:
        errors.append(f"flow_node/axlfi: {e}")

    prompt = f"""You are a market microstructure analyst. Given these flow signals for {symbol}:

AXLFI OPTION WALLS: {axlfi_summary}
DARK POOL FLOW: {dp_summary}

Answer in JSON only, no markdown:
{{
  "wall_read": "one sentence: is SPY above, below, or at the call wall? Use the exact pts_above number from the summary. Do NOT say 'pinned between walls' if spot is above the call wall.",
  "dp_read": "one sentence: what the short volume percentage means — above 55% is distribution, below 45% is accumulation, 45-55% is neutral",
  "key_level": "the single most important price level right now and why",
  "smart_money_bias": "ACCUMULATING or DISTRIBUTING or NEUTRAL — one sentence justification"
}}"""

    content = _safe_call("flow", prompt, max_tokens=400)
    parsed_flow = extract_json(content) if content else None
    if parsed_flow:
        content = (
            f"WALLS: {parsed_flow.get('wall_read', '')} | "
            f"DP: {parsed_flow.get('dp_read', '')} | "
            f"KEY LEVEL: {parsed_flow.get('key_level', '')} | "
            f"SMART MONEY: {parsed_flow.get('smart_money_bias', '')}"
        )
    elif not content:
        errors.append("flow_node: empty LLM response")
        content = f"Flow analysis unavailable. AXLFI: {axlfi_summary}"

    # Return structured dict so SynthesisNode can use numeric pts_above_call_wall
    flow_data = {
        "wall_read": parsed_flow.get("wall_read", "") if parsed_flow else axlfi_summary,
        "dp_read": parsed_flow.get("dp_read", "") if parsed_flow else dp_summary,
        "key_level": parsed_flow.get("key_level", "") if parsed_flow else "",
        "smart_money_bias": parsed_flow.get("smart_money_bias", "") if parsed_flow else "",
        "pts_above_call_wall": above_call,
        "call_wall": _call_wall,
        "put_wall": _put_wall,
        "spot_price": spot_price,
        "sv_pct": sv_pct,
        "raw_text": content,
    }

    timings["flow"] = round(time.time() - t0, 2)
    return {"flow_context": flow_data, "errors": errors, "node_timings": timings}


# ── RegimeNode ────────────────────────────────────────────────────────────────

def regime_node(state: AlphaState) -> Dict[str, Any]:
    """
    Reads GEX regime + short vol data.
    Returns ONLY regime_context, errors slice, node_timings slice.
    """
    t0 = time.time()
    symbol = state.get("symbol", "SPY")
    errors = []
    timings = {}

    gex_summary = "GEX data unavailable"
    try:
        from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
        sg = StockgridClient(cache_ttl=300)
        gex = sg.get_volatility_regime()
        if gex:
            # get_volatility_regime() returns a dict — use .get() defensively
            regime_val = gex.get('regime') or gex.get('gex_regime') or gex.get('status', 'UNKNOWN')
            total_gex = gex.get('total_gex') or gex.get('net_gex') or 0
            flip = gex.get('flip_level') or gex.get('zero_gamma') or 'N/A'
            gex_summary = (
                f"Regime: {regime_val} | "
                f"Total GEX: ${float(total_gex)/1e9:.1f}B | "
                f"Flip level: {flip}"
            )
    except Exception as e:
        errors.append(f"regime_node/gex: {e}")

    vix_val = None
    try:
        import yfinance as _yf
        _vix_info = _yf.Ticker("^VIX").fast_info
        vix_val = round(float(_vix_info.get("lastPrice") or _vix_info.get("regularMarketPrice") or 0), 2)
        if vix_val > 0:
            gex_summary += f" | VIX: {vix_val}"
    except Exception as _vix_e:
        errors.append(f"regime_node/vix: {_vix_e}")

    prompt = f"""You are a volatility regime analyst. Given this GEX data for {symbol}:
{gex_summary}

Answer in JSON only, no markdown:
{{
  "regime_label": "POSITIVE_GEX or NEGATIVE_GEX or TRANSITIONAL",
  "vol_expectation": "SUPPRESSED or ELEVATED or EXPLOSIVE",
  "dealer_positioning": "SHORT_GAMMA or LONG_GAMMA or NEUTRAL",
  "key_insight": "one sentence on what this means for intraday moves",
  "vix_read": "one sentence: VIX {vix_val} — suppressed (<15), normal (15-20), elevated (20-30), or extreme (>30)? What does this mean for move size?"
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
    return {"regime_context": regime_text, "errors": errors, "node_timings": timings}


# ── SynthesisNode ─────────────────────────────────────────────────────────────

def synthesis_node(state: AlphaState) -> Dict[str, Any]:
    """
    Combines macro + flow + regime into a unified verdict.
    Sequential — reads full state, returns verdict fields + synthesis text.
    """
    t0 = time.time()
    errors = []
    timings = {}

    macro = state.get("macro_context", "unavailable")
    _flow_raw = state.get("flow_context", "unavailable")
    if isinstance(_flow_raw, dict):
        flow = _flow_raw.get("raw_text", str(_flow_raw))
        flow_pts_above = _flow_raw.get("pts_above_call_wall")
        flow_call_wall = _flow_raw.get("call_wall")
    else:
        flow = _flow_raw
        flow_pts_above = None
        flow_call_wall = None
    regime = state.get("regime_context", "unavailable")

    # Enrichment signals from state (populated by main.py before graph entry)
    qqq_delta = state.get("qqq_sv_delta")
    qqq_spike = state.get("qqq_reshort_spike", False)
    absorption = state.get("absorption_detected", False)
    absorption_price_val = state.get("absorption_price")

    enrichment_lines = []
    if qqq_spike and qqq_delta:
        enrichment_lines.append(f"QQQ RESHORT SPIKE: short vol +{qqq_delta}pp in 1 day while SPY above call wall = squeeze fuel when catalyst hits")
    elif qqq_delta is not None:
        enrichment_lines.append(f"QQQ short vol delta: {qqq_delta:+.1f}pp (1 day)")
    if absorption:
        enrichment_lines.append(f"ABSORPTION at ${absorption_price_val}: high vol + near-zero price move = sellers exhausted")
    enrichment_context = "\n".join(enrichment_lines) if enrichment_lines else "No additional enrichment signals"

    wall_rule = ""
    if flow_pts_above is not None and flow_call_wall is not None:
        if flow_pts_above > 0:
            wall_rule = f"\n- SPY is {flow_pts_above}pts ABOVE the {flow_call_wall} call wall — thesis MUST reflect breakout, do NOT say 'pinned between walls'"
        else:
            wall_rule = f"\n- SPY is {abs(flow_pts_above)}pts BELOW the {flow_call_wall} call wall — thesis must reflect resistance overhead"

    prompt = f"""You are the Alpha Commander. You have received three independent intelligence reports:

MACRO INTELLIGENCE:
{macro}

FLOW INTELLIGENCE:
{flow}

REGIME INTELLIGENCE:
{regime}

ENRICHMENT SIGNALS:
{enrichment_context}

Synthesize these into a unified trading verdict. Answer in JSON only, no markdown:
{{
  "verdict": "ARMED or HOLD or VETO",
  "confidence": 0.75,
  "thesis": "2-sentence thesis — sentence 1: what the setup IS right now using specific numbers from the reports, sentence 2: what the trigger is and what invalidates it",
  "primary_risk": "single biggest risk — name a specific price level or event, not a generic phrase",
  "direction": "BULLISH or BEARISH or MIXED",
  "synthesis_notes": "which signal dominated and the exact number that made it dominant"
}}

Rules:
- ARMED = all signals aligned, high conviction
- HOLD = mixed signals, wait for clarity
- VETO = signals conflict or major risk event imminent
- thesis MUST use specific numbers from the reports — no generic phrases like "the combination of signals"
- If FLOW says SPY is above the call wall, thesis must reflect that — do not say "pinned between walls"
- primary_risk must name a price level (e.g. "SPY breaks below 720") not a concept (e.g. "volatility risk"){wall_rule}"""

    content = _safe_call("synthesis", prompt, max_tokens=600, timeout=25)
    parsed = extract_json(content) if content else None

    if parsed:
        verdict = parsed.get("verdict", "HOLD")
        confidence = float(parsed.get("confidence", 0.5))
        thesis = parsed.get("thesis", "")
        primary_risk = parsed.get("primary_risk", "")
        direction = parsed.get("direction", "MIXED")
    else:
        errors.append("synthesis_node: JSON parse failed")
        verdict = "HOLD"
        confidence = 0.0
        thesis = "Synthesis failed — defaulting to HOLD"
        primary_risk = "LLM synthesis unavailable"
        direction = "MIXED"

    timings["synthesis"] = round(time.time() - t0, 2)
    return {
        "synthesis": content or "unavailable",
        "verdict": verdict,
        "confidence": confidence,
        "thesis": thesis,
        "primary_risk": primary_risk,
        "direction": direction,
        "errors": errors,
        "node_timings": timings,
    }


# ── GateNode ──────────────────────────────────────────────────────────────────

def gate_node(state: AlphaState) -> Dict[str, Any]:
    """
    Pure Python gate: pulls live kill chain snapshot and applies veto logic.
    Sequential — no LLM call, deterministic rule check.
    """
    t0 = time.time()
    errors = []
    timings = {}
    verdict = state.get("verdict", "HOLD")
    confidence = state.get("confidence", 0.0) or 0.0

    gate_result = {"kill_chain_available": False, "veto_applied": False}

    try:
        from backend.app.signals.kill_chain import compute_kill_chain
        kc = compute_kill_chain()
        gate_result["kill_chain_available"] = True
        gate_result["confluence"] = kc.get("confluence", "WAITING")
        gate_result["armed"] = kc.get("armed", False)
        gate_result["fed_veto_active"] = kc.get("fed_veto_active", False)
        gate_result["layer_4_triggered"] = kc.get("layer_4", {}).get("triggered", False)

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
            # Surface the gate reasoning so it appears in the final thesis
            gate_result["gate_narrative"] = (
                f"Alpha graph says {state.get('verdict', 'HOLD')} at {state.get('confidence', 0):.0%} confidence, "
                f"but kill chain confluence is {kc.get('confluence', 'WAITING')} — "
                f"waiting for {4 - kc.get('triggered_count', 0)} more layer(s) to confirm before arming."
            )

    except Exception as e:
        errors.append(f"gate_node/kill_chain: {e}")

    timings["gate"] = round(time.time() - t0, 2)
    return {
        "verdict": verdict,
        "confidence": confidence,
        "gate_result": gate_result,
        "gate_narrative": gate_result.get("gate_narrative", ""),
        "errors": errors,
        "node_timings": timings,
    }
