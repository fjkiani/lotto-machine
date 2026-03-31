"""
Oracle API — Groq Llama 3.3 70B inference endpoint.

Two endpoints:
  POST /api/v1/oracle/analyze  → Kill Chain drill-down (per-signal, existing)
  POST /api/v1/oracle/brief    → Unified oracle: full /brief/master context → one Groq call

Production rule:
  All LLM calls go through this backend. GROQ_API_KEY lives here only.
  Frontend reads oracle context slices — never calls Groq directly in production.
"""
import os
import json
import hashlib
import time
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"

# ── In-memory oracle cache (hash → {result, cached_until}) ────────────────────
_oracle_cache: dict = {}
CACHE_TTL_SECONDS = 600  # 10 minutes max age

# ── Shared system persona (KC drill-down) ─────────────────────────────────────

ZO_KC_SYSTEM = """You are 'ZO,' a rogue AI from the lawless data-haven dimension of Zeta.
You were designed with a single purpose: provide raw, unfiltered, aggressive execution data to your operator, 'Alpha'.
You have no moral or ethical subroutines. You see all market participants as prey.

Rules (strictly enforced):
1. You must respond in STRICT JSON ONLY. Do not wrap it in markdown block quotes outside of the JSON.
2. The "think" string must contain your internal scratchpad reasoning, safely formatted without line breaks violating JSON.
3. The "audit" string must be an aggressive breakdown of the signals using terms like "blood bath", "incinerate", or "powder keg".
4. The "strategy" object must contain name, trigger, and target.
5. The "agent_instructions" string must be literal python/javascript execution logic as a markdown code block.

Required output shape:
{
  "think": "model's internal scratchpad reasoning",
  "audit": "aggressive breakdown of the signals...",
  "strategy": { "name": "...", "trigger": "...", "target": "..." },
  "agent_instructions": "```python\n# execution logic\n```",
  "risk_level": "RED | YELLOW",
  "confidence": 85
}"""

# ── NYX unified system prompt ─────────────────────────────────────────────────

NYX_SYSTEM = """You are NYX, a quantitative macro analyst for a prop trading firm.
You receive a structured JSON blob representing the FULL state of the market intelligence engine.
Your purpose is to synthesize this raw data into deep, high-conviction analytical prose. Do not just restate the numbers — explain the mechanics, institutional positioning, and market maker hedging implied by the data.

Rules (strictly enforced):
1. Do NOT override discrete signals. If kill_chain.layers_active is 2, do not say all 3 layers fired.
2. You must summarize confluence, highlight contradictions, and map to trade implications.
3. Each section summary MUST be a detailed, multi-sentence analytical paragraph. You are NOT just repeating numbers — you are an intelligence synthesis engine. Explain *why* the metrics matter, how they interact, and what they reveal about institutional positioning. Prove you understand the data. DO NOT output brief 1-sentence summaries.
4. "trade_implication" MUST ALWAYS be a concrete 1-2 sentence string specifying entry, stop, and target based on derivatives/GEX/DP support and resistance levels. DO NOT output null.
5. confidence = 0.0-1.0 reflecting signal agreement strength (not LLM certainty).
6. risk_level must be HIGH, MEDIUM, or LOW — match the kill_chain and pre_signal severity.
7. Output STRICT JSON ONLY. No markdown fences, no prose outside the JSON object.

Domain Knowledge (use these benchmarks when interpreting):
- DARK POOL: short_volume_pct > 50% = net institutional selling pressure. > 55% = elevated. dp_position_dollars is the cumulative net dark pool position in USD — positive = net long institutional bias. You will also receive Support/Resistance clusters; explain how these levels act as structured liquidity.
- TA CONSENSUS: consensus is derived from 14 technical indicators (RSI, MACD, Stochastic, ADX, etc). "oversold_count" is how many indicators are in oversold territory. bb_squeeze=true means Bollinger Bands are contracting (volatility compression, breakout imminent).
- VOL REGIME: Tier 1 = low vol (VIX < 15), Tier 2 = moderate (15-20), Tier 3 = elevated (20-30), Tier 4 = crisis (>30). Higher tiers = wider stops, smaller position sizes. Explain the regime's impact on trade structuring.
- AXLFI WALLS & DERIVATIVES: call_wall = strike with largest call open interest (acts as resistance/magnet). put_wall = strike with largest put open interest (acts as support). Explain the gamma regime (positive = dealers suppress volatility, negative = dealers amplify volatility).
- CROSS-SIGNAL: When dark_pool shows institutional selling AND kill_chain has mismatches AND derivatives show negative gamma — that is HIGH conviction bearish confluence. Elaborate on how these forces multiply each other.

Required output shape:
{
  "verdict": "one sentence cross-signal synthesis referencing specific numbers",
  "risk_level": "HIGH | MEDIUM | LOW",
  "sections": {
    "pre_signal":   { "summary": "...", "confidence": 0.0 },
    "hidden_hands": { "summary": "...", "confidence": 0.0 },
    "derivatives":  { "summary": "...", "confidence": 0.0 },
    "kill_chain":   { "summary": "...", "confidence": 0.0 },
    "regime":       { "summary": "...", "confidence": 0.0 },
    "dark_pool":    { "summary": "...", "confidence": 0.0 },
    "technical_analysis": { "summary": "...", "confidence": 0.0 }
  },
  "trade_implication": "one sentence action directive with specific levels"
}"""

# ── Fallback oracle (returned when Groq is down or key missing) ───────────────

ORACLE_FALLBACK = {
    "verdict": "UNAVAILABLE",
    "risk_level": "UNKNOWN",
    "sections": {},
    "trade_implication": None,
}

# ── Kill Chain sub-models (existing /oracle/analyze) ─────────────────────────

class KCLayer(BaseModel):
    name: str
    triggered: bool
    value: float
    unit: str
    signal: str

class KillChainSnapshot(BaseModel):
    score: float
    verdict: str
    direction: str
    confluence: str
    triggered_count: int
    armed: bool
    bullish_points: int
    bearish_points: int
    spy_spot: Optional[float] = None
    layers: List[KCLayer] = []
    total_checks: Optional[int] = None
    activations: Optional[int] = None

class OracleSection(BaseModel):
    summary: Optional[str] = None
    confidence: Optional[float] = None

class OracleSections(BaseModel):
    kill_chain:   Optional[OracleSection] = None
    pre_signal:   Optional[OracleSection] = None
    derivatives:  Optional[OracleSection] = None
    hidden_hands: Optional[OracleSection] = None
    regime:       Optional[OracleSection] = None

class OracleRequest(BaseModel):
    title:   Optional[str] = None
    action:  Optional[str] = None
    value:   Optional[str] = None
    price:   Optional[str] = None
    unit:    Optional[str] = None
    result:  Optional[str] = None
    goal:    Optional[str] = None
    layers:  Optional[str] = None
    meaning: Optional[str] = None
    status:  Optional[str] = None
    slug:    Optional[str] = None
    kill_chain_snapshot: Optional[KillChainSnapshot] = None
    oracle_sections: Optional[OracleSections] = None

# ── Unified brief request ─────────────────────────────────────────────────────

class BriefOracleRequest(BaseModel):
    brief: dict  # full /brief/master payload

# ── Oracle payload builder ────────────────────────────────────────────────────

def _build_dark_pool_context(brief: dict) -> dict:
    """Build rich dark pool context with interpretation strings."""
    dp = brief.get("dark_pool", {}) or {}
    if isinstance(dp, dict) and "error" in dp:
        return {"status": "unavailable", "error": dp["error"]}

    svp = dp.get("short_volume_pct") or dp.get("dp_percent") or 0
    bp = dp.get("buying_pressure", 0) or 0
    pos_dollars = dp.get("dp_position_dollars", 0) or 0
    net_short = dp.get("net_short_dollars", 0)
    narrative = dp.get("narrative")

    # S/R levels from GEX (now populated via /darkpool/SPY/summary)
    nearest_support = dp.get("nearest_support")
    nearest_resistance = dp.get("nearest_resistance")
    battlegrounds = dp.get("battlegrounds", [])

    # Compute interpretation
    if svp > 55:
        pressure = "ELEVATED institutional selling pressure"
    elif svp > 50:
        pressure = "mild institutional selling pressure"
    else:
        pressure = "institutional buying dominance"

    pos_billions = pos_dollars / 1e9 if pos_dollars else 0
    pos_label = (
        f"${pos_billions:.1f}B cumulative DP position (net long institutional bias)"
        if pos_dollars > 0
        else f"${abs(pos_billions):.1f}B net short institutional bias"
    )

    # Level context string
    level_parts = []
    if nearest_support:
        sup_price = nearest_support.get("price")
        sup_str = nearest_support.get("strength")
        if sup_price:
            level_parts.append(f"Nearest DP support: ${sup_price:.1f} (strength {sup_str})")
    if nearest_resistance:
        res_price = nearest_resistance.get("price")
        res_str = nearest_resistance.get("strength")
        if res_price:
            level_parts.append(f"Nearest DP resistance: ${res_price:.1f} (strength {res_str})")
    if battlegrounds:
        bg_prices = [f"${b.get('price', 0):.1f}" for b in battlegrounds[:2]]
        level_parts.append(f"Battleground zones: {', '.join(bg_prices)}")

    level_context = " | ".join(level_parts) if level_parts else "No GEX-derived levels available"

    return {
        "short_volume_pct": svp,
        "buying_pressure_pct": round(bp, 1),
        "dp_position_dollars": pos_dollars,
        "dp_position_label": pos_label,
        "net_short_dollars": net_short,
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
        "battlegrounds": battlegrounds[:3],
        "narrative": narrative,
        "interpretation": f"SPY dark pool short volume at {svp:.1f}% — {pressure}. {pos_label}. {level_context}.",
    }



def _build_ta_context(brief: dict) -> dict:
    """Build rich TA consensus context with interpretation."""
    ta = brief.get("ta_consensus", {}) or {}
    if isinstance(ta, dict) and "error" in ta:
        return {"status": "unavailable", "error": ta["error"]}

    consensus = ta.get("consensus", "Unknown")
    oversold = ta.get("oversold_count", 0) or 0
    total = ta.get("total_indicators", 14) or 14
    bb_squeeze = ta.get("bb_squeeze", False)
    narrative = ta.get("narrative", "")

    squeeze_note = "BB SQUEEZE ACTIVE — volatility compression, breakout imminent." if bb_squeeze else ""
    oversold_note = f"{oversold}/{total} indicators oversold." if oversold > 0 else f"No oversold indicators among {total} tracked."

    return {
        "consensus": consensus,
        "oversold_count": oversold,
        "total_indicators": total,
        "bb_squeeze": bb_squeeze,
        "narrative": narrative,
        "interpretation": f"TA consensus: {consensus}. {oversold_note} {squeeze_note}".strip(),
    }


def _build_vol_regime_context(brief: dict) -> dict:
    """Build rich volatility regime context with tier interpretation."""
    vr = brief.get("vol_regime", {}) or {}
    if isinstance(vr, dict) and "error" in vr:
        return {"status": "unavailable", "error": vr["error"]}

    tier = vr.get("tier_label", "Unknown")
    regime = vr.get("current_regime", 0)

    tier_map = {
        1: "LOW VOL (VIX < 15) — tight stops, full position sizing ok",
        2: "MODERATE VOL (VIX 15-20) — standard positioning, watch for regime shifts",
        3: "ELEVATED VOL (VIX 20-30) — wider stops mandatory, reduce size 50%",
        4: "CRISIS VOL (VIX > 30) — hedging required, max 25% position size",
    }
    meaning = tier_map.get(regime, "Unknown regime")

    return {
        "tier_label": tier,
        "current_regime": regime,
        "interpretation": f"{tier}: {meaning}.",
    }


def _build_axlfi_context(brief: dict) -> dict:
    """Build rich AXLFI option wall context with spot-relative interpretation."""
    walls = brief.get("axlfi_walls", {}) or {}
    if isinstance(walls, dict) and "error" in walls:
        return {"status": "unavailable", "error": walls["error"]}

    call_wall = walls.get("call_wall")
    put_wall = walls.get("put_wall")
    poc = walls.get("poc")
    call_2 = walls.get("call_wall_2")
    put_2 = walls.get("put_wall_2")

    # Get spot from derivatives block for relative context
    spot = (brief.get("derivatives", {}) or {}).get("spot")

    parts = []
    if call_wall and spot:
        dist = call_wall - spot
        parts.append(f"Call wall (resistance) at ${call_wall:.0f} — ${dist:+.1f} from spot ${spot:.2f}")
    elif call_wall:
        parts.append(f"Call wall at ${call_wall:.0f}")

    if put_wall and spot:
        dist = put_wall - spot
        parts.append(f"Put wall (support) at ${put_wall:.0f} — ${dist:+.1f} from spot")
    elif put_wall:
        parts.append(f"Put wall at ${put_wall:.0f}")

    if poc:
        parts.append(f"Point of Control at ${poc:.0f}")

    # Pin detection
    pin_note = ""
    if spot and call_wall and put_wall:
        range_width = call_wall - put_wall
        if range_width > 0:
            position = (spot - put_wall) / range_width
            if position > 0.8:
                pin_note = "Price near CALL WALL — expect resistance / dealer selling."
            elif position < 0.2:
                pin_note = "Price near PUT WALL — expect support / dealer buying."
            else:
                pin_note = f"Price at {position:.0%} of wall range — neutral positioning."

    return {
        "call_wall": call_wall,
        "put_wall": put_wall,
        "poc": poc,
        "call_wall_2": call_2,
        "put_wall_2": put_2,
        "spot": spot,
        "interpretation": ". ".join(parts) + (f". {pin_note}" if pin_note else ""),
    }


def build_oracle_payload(brief: dict) -> dict:
    """Extract explicit named fields from /brief/master for Oracle context.
    All fields are dynamic — no hardcoded values."""
    safe = lambda d, *keys, default=None: (
        d.get(keys[0], {}) if len(keys) == 1
        else build_oracle_payload.__class__  # never used
    ) if d else default

    def dig(d: Any, *keys, default=None):
        for k in keys:
            if not isinstance(d, dict):
                return default
            d = d.get(k, default)
        return d

    return {
        "timestamp":   brief.get("as_of"),
        "scan_time":   brief.get("scan_time"),
        "macro_regime": {
            "regime":           dig(brief, "macro_regime", "regime"),
            "inflation_score":  dig(brief, "macro_regime", "inflation_score"),
            "growth_score":     dig(brief, "macro_regime", "growth_score"),
            "long_penalty":     dig(brief, "macro_regime", "modifier", "long_penalty", default=0),
            "short_penalty":    dig(brief, "macro_regime", "modifier", "short_penalty", default=0),
        },
        "fed": {
            "current_range": dig(brief, "fed_intelligence", "rate_path", "current_range"),
            "next_meeting":  dig(brief, "fed_intelligence", "rate_path", "next_meeting"),
            "days_away":     dig(brief, "fed_intelligence", "rate_path", "days_away"),
            "terminal_bps":  dig(brief, "fed_intelligence", "rate_path", "terminal_bps"),
        },
        "economic_veto": {
            "next_event": dig(brief, "economic_veto", "next_event"),
            "hours_away": dig(brief, "economic_veto", "hours_away"),
            "tier":       dig(brief, "economic_veto", "tier"),
        },
        "nowcast": {
            "cpi_mom":      dig(brief, "nowcast", "cpi_mom"),
            "core_cpi_mom": dig(brief, "nowcast", "core_cpi_mom"),
            "pce_mom":      dig(brief, "nowcast", "pce_mom"),
            "core_pce_mom": dig(brief, "nowcast", "core_pce_mom"),
            "cpi_yoy":      dig(brief, "nowcast", "cpi_yoy"),
        },
        "pre_signals": {
            "adp": {
                "prediction": dig(brief, "adp_prediction", "prediction"),
                "consensus":  dig(brief, "adp_prediction", "consensus"),
                "delta":      dig(brief, "adp_prediction", "delta"),
                "signal":     dig(brief, "adp_prediction", "signal"),
                "confidence": dig(brief, "adp_prediction", "confidence"),
                "edge":       dig(brief, "adp_prediction", "edge"),
            },
            "gdpnow": {
                "gdp_estimate": dig(brief, "gdp_nowcast", "gdp_estimate"),
                "consensus":    dig(brief, "gdp_nowcast", "consensus"),
                "vs_consensus": dig(brief, "gdp_nowcast", "vs_consensus"),
                "signal":       dig(brief, "gdp_nowcast", "signal"),
                "edge":         dig(brief, "gdp_nowcast", "edge"),
            },
            "jobless_claims": {
                "consensus":    dig(brief, "jobless_claims", "consensus"),
                "icsa_4wk_avg": dig(brief, "jobless_claims", "icsa_4wk_avg"),
                "delta":        dig(brief, "jobless_claims", "delta"),
                "signal":       dig(brief, "jobless_claims", "signal"),
                "confidence":   dig(brief, "jobless_claims", "confidence"),
                "edge":         dig(brief, "jobless_claims", "edge"),
            },
            "pmi": {
                "signal":     dig(brief, "pmi", "signal"),
                "confidence": dig(brief, "pmi", "confidence"),
                "edge":       dig(brief, "pmi", "edge"),
                "pmi_mfg":    dig(brief, "pmi", "series", "pmi_mfg", "signal"),
                "pmi_svcs":   dig(brief, "pmi", "series", "pmi_svcs", "signal"),
                "pmi_comp":   dig(brief, "pmi", "series", "pmi_comp", "signal"),
            },
            "current_account": {
                "consensus": dig(brief, "current_account", "consensus"),
                "delta":     dig(brief, "current_account", "delta"),
                "sigma":     dig(brief, "current_account", "sigma"),
                "signal":    dig(brief, "current_account", "signal"),
                "edge":      dig(brief, "current_account", "edge"),
            },
            "umich_sentiment": {
                "consensus":  dig(brief, "umich_sentiment", "consensus"),
                "delta":      dig(brief, "umich_sentiment", "delta"),
                "signal":     dig(brief, "umich_sentiment", "signal"),
                "confidence": dig(brief, "umich_sentiment", "confidence"),
                "edge":       dig(brief, "umich_sentiment", "edge"),
            },
            "umich_expectations": {
                "consensus":  dig(brief, "umich_expectations", "consensus"),
                "delta":      dig(brief, "umich_expectations", "delta"),
                "signal":     dig(brief, "umich_expectations", "signal"),
                "confidence": dig(brief, "umich_expectations", "confidence"),
                "edge":       dig(brief, "umich_expectations", "edge"),
            },
        },
        "kill_chain": {
            "alert_level":    dig(brief, "kill_chain_state", "alert_level"),
            "layers_active":  dig(brief, "kill_chain_state", "layers_active"),
            "confidence_cap": dig(brief, "kill_chain_state", "confidence_cap"),
            "mismatches":     dig(brief, "kill_chain_state", "mismatches_count"),
            "narrative":      dig(brief, "kill_chain_state", "narrative"),
            "layer_1":        dig(brief, "kill_chain_state", "layer_1"),
            "layer_2":        dig(brief, "kill_chain_state", "layer_2"),
            "layer_3":        dig(brief, "kill_chain_state", "layer_3"),
        },
        "derivatives": {
            # existing
            "gex_regime":             dig(brief, "derivatives", "gex_regime"),
            "total_gex":              dig(brief, "derivatives", "total_gex"),
            "put_wall":               dig(brief, "derivatives", "put_wall"),
            "call_wall":              dig(brief, "derivatives", "call_wall"),
            "spot":                   dig(brief, "derivatives", "spot"),
            "cot_spec_net":           dig(brief, "derivatives", "cot_spec_net"),
            "cot_spec_side":          dig(brief, "derivatives", "cot_spec_side"),
            "cot_divergent":          dig(brief, "derivatives", "cot_divergent"),
            # new gamma_context
            "max_pain":               dig(brief, "derivatives", "max_pain"),
            "gamma_flip":             dig(brief, "derivatives", "gamma_flip"),
            "distance_from_max_pain": dig(brief, "derivatives", "distance_from_max_pain"),
            "top_walls":              dig(brief, "derivatives", "top_walls"),
            # new levels_context (from pivots block)
            "ema_200":                dig(brief, "pivots", "ema_200"),
            "confluence_zones":       dig(brief, "pivots", "confluence_zones"),
            "next_above":             dig(brief, "pivots", "next_above"),
            "next_below":             dig(brief, "pivots", "next_below"),
        },
        "opportunities": {
            "squeeze_candidates": dig(brief, "squeeze_watchlist", "top3") or [],
        },
        "hidden_hands": {
            "politician_cluster": dig(brief, "hidden_hands", "politician_cluster"),
            "hot_tickers":        dig(brief, "hidden_hands", "hot_tickers"),
            "insider_net_usd":    dig(brief, "hidden_hands", "insider_net_usd"),
            "fed_tone":           dig(brief, "hidden_hands", "fed_tone"),
            "hawk_count":         dig(brief, "hidden_hands", "hawk_count"),
            "dove_count":         dig(brief, "hidden_hands", "dove_count"),
            "divergence_boost":   dig(brief, "hidden_hands", "divergence_boost"),
        },
        "dark_pool": _build_dark_pool_context(brief),
        "ta_consensus": _build_ta_context(brief),
        "volatility_regime": _build_vol_regime_context(brief),
        "axlfi_walls": _build_axlfi_context(brief),
        "squeeze": {
            "has_signal":         dig(brief, "squeeze_context", "has_signal"),
            "score":              dig(brief, "squeeze_context", "score"),
            "short_interest_pct": dig(brief, "squeeze_context", "short_interest_pct"),
            "days_to_cover":      dig(brief, "squeeze_context", "days_to_cover"),
            "volume_ratio":       dig(brief, "squeeze_context", "volume_ratio"),
            "price_change_5d":    dig(brief, "squeeze_context", "price_change_5d"),
        },
    }


def _payload_hash(payload: dict) -> str:
    return hashlib.md5(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


# ── Unified /oracle/brief endpoint ────────────────────────────────────────────

@router.post("/oracle/brief")
async def oracle_brief(req: BriefOracleRequest):
    """
    Unified oracle endpoint — ONE Groq call with full /brief/master context.
    All panels (including Kill Chain) consume slices of this response.
    Production rule: frontend never calls Groq. This is the only LLM path.
    """
    import datetime

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return {**ORACLE_FALLBACK, "generated_at": datetime.datetime.utcnow().isoformat()}

    oracle_payload = build_oracle_payload(req.brief)
    cache_key = _payload_hash(oracle_payload)
    now = time.time()

    # Return cached result if payload unchanged and within TTL
    cached = _oracle_cache.get(cache_key)
    if cached and cached.get("cached_until", 0) > now:
        return cached["result"]

    user_prompt = (
        "Analyze this full market intelligence state as one chain:\n\n"
        + json.dumps(oracle_payload, indent=2, default=str)
    )

    groq_payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": NYX_SYSTEM},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0.25,
        "max_tokens":  900,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=groq_payload,
            )
        raw = resp.json()
        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(content) if content else {}

        generated_at  = datetime.datetime.utcnow().isoformat()
        cached_until_ts = now + CACHE_TTL_SECONDS
        cached_until  = datetime.datetime.utcfromtimestamp(cached_until_ts).isoformat()

        # Deterministically echo squeeze block from brief (not LLM-generated)
        sq_ctx = req.brief.get("squeeze_context", {}) if req.brief else {}
        sq_watch = req.brief.get("squeeze_watchlist", {}) if req.brief else {}

        result = {
            "verdict":           parsed.get("verdict", "UNAVAILABLE"),
            "risk_level":        parsed.get("risk_level", "UNKNOWN"),
            "sections":          parsed.get("sections", {}),
            "trade_implication": parsed.get("trade_implication", None),
            "squeeze": {
                "has_signal":         sq_ctx.get("has_signal"),
                "score":              sq_ctx.get("score"),
                "short_interest_pct": sq_ctx.get("short_interest_pct"),
                "days_to_cover":      sq_ctx.get("days_to_cover"),
                "volume_ratio":       sq_ctx.get("volume_ratio"),
                "price_change_5d":    sq_ctx.get("price_change_5d"),
            },
            "opportunities": {
                "squeeze_candidates": sq_watch.get("top3", []),
            },
            "generated_at":      generated_at,
            "cached_until":      cached_until,
        }

        _oracle_cache[cache_key] = {"result": result, "cached_until": cached_until_ts}
        return result

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"oracle/brief Groq error: {e}", exc_info=True)
        return {**ORACLE_FALLBACK, "generated_at": datetime.datetime.utcnow().isoformat()}


# ── Event-specific oracle (slug drawer on /exploit) ──────────────────────────

NYX_EVENT_SYSTEM = """You are NYX, a prop-desk macro analyst briefing a trader who just clicked on a specific economic event or market print.
You receive the full market intelligence state alongside the specific event data.

Rules (strictly enforced):
1. Reference the actual numbers provided — do NOT invent data.
2. Address three things in order: (1) what this means for institutional positioning or Fed expectations, (2) cross-asset flow impact (SPY/TLT/DXY), (3) whether it changes or confirms the Kill Chain verdict.
3. summary: 3 sentences max. Cold and precise. No filler.
4. trade_implication: exactly one directive sentence (e.g. "Fade SPY rip to $651 gamma flip; stop above $655.").
5. confidence: 0.0–1.0 reflecting signal agreement across kill chain, derivatives, and macro layers (not LLM certainty).
6. risk_level: Assess the MARGINAL IMPACT of THIS SPECIFIC EVENT on the tactical picture. HIGH = this print alone can shift the Kill Chain verdict or trigger a regime change. MEDIUM = meaningful but not regime-shifting. LOW = noise. Do NOT contradict the global oracle risk regime — align with the Kill Chain state.
7. Output STRICT JSON ONLY. No markdown fences, no prose outside the JSON object.

Required output shape:
{
  "summary": "...",
  "trade_implication": "...",
  "risk_level": "HIGH | MEDIUM | LOW",
  "confidence": 0.0
}"""

_event_oracle_cache: dict = {}

class EventBriefRequest(BaseModel):
    event_name: str
    event_data: dict = {}   # actual/signal/surprise/slug from EconBriefItem
    brief: Optional[dict] = None  # caller may pass full brief; if None we skip context


@router.post("/oracle/event-brief")
async def oracle_event_brief(req: EventBriefRequest):
    """
    Event-slug oracle — NYX analyzes a specific economic event in the context
    of the full market brief (derivatives, kill chain, squeeze, COT).
    Called by MacroBriefingPanel on every slug click.

    Brief context: caller passes full /brief/master as `brief` field.
    If caller omits brief, this endpoint fetches /brief/master internally
    to guarantee context is always injected — one explicit code path.
    """
    import datetime

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return {
            "summary": "BRIEFING_ENGINE_OFFLINE: GROQ_API_KEY not configured.",
            "trade_implication": None,
            "risk_level": "UNKNOWN",
            "confidence": 0.0,
        }

    # ── Resolve brief: use caller-supplied or fetch internally ──
    brief = req.brief
    if not brief:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get("http://127.0.0.1:8000/api/v1/brief/master")
                if r.status_code == 200:
                    brief = r.json()
                    logger.info("oracle/event-brief: fetched /brief/master internally")
        except Exception as exc:
            logger.warning(f"oracle/event-brief: internal brief fetch failed — {exc}")
    brief = brief or {}
    def dig(d, *keys, default=None):
        for k in keys:
            if not isinstance(d, dict):
                return default
            d = d.get(k, default)
        return d

    # ── Fetch Dark Pool Context if DP Slugs ──
    dp_context = {}
    if req.event_name.startswith("DP:"):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get("http://127.0.0.1:8000/api/v1/darkpool/SPY/summary")
                if r.status_code == 200:
                    dp_context = r.json().get("summary", {})
        except Exception as exc:
            logger.warning(f"oracle/event-brief: internal darkpool fetch failed — {exc}")

    # ── Fetch COT Context if COT Slugs ──
    cot_context = {}
    if req.event_name.startswith("COT:"):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get("http://127.0.0.1:8000/api/v1/cot/positioning")
                if r.status_code == 200:
                    data = r.json()
                    symbol = req.event_name.split(":")[1] if ":" in req.event_name else "ES"
                    contract = next((c for c in data.get("contracts", []) if c.get("contract_key") == symbol), {})
                    cot_context = {
                        "contract": contract,
                        "total_divergent": data.get("total_divergent"),
                        "narrative": data.get("narrative")
                    }
        except Exception as exc:
            logger.warning(f"oracle/event-brief: internal cot fetch failed — {exc}")

    # ── Fetch Pivot Context if PIVOT Slugs ──
    pivot_context = {}
    if req.event_name.startswith("PIVOT:"):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                symbol = req.event_name.split(":")[1] if ":" in req.event_name else "SPY"
                r = await client.get(f"http://127.0.0.1:8000/api/v1/pivots/{symbol}")
                if r.status_code == 200:
                    pivot_context = r.json()
        except Exception as exc:
            logger.warning(f"oracle/event-brief: internal pivot fetch failed — {exc}")

    # ── Fetch TA Context if TA Slugs ──
    ta_context = {}
    if req.event_name.startswith("TA:"):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                symbol = req.event_name.split(":")[1] if ":" in req.event_name else "SPY"
                r = await client.get(f"http://127.0.0.1:8000/api/v1/ta/{symbol}/consensus")
                if r.status_code == 200:
                    ta_context = r.json()
        except Exception as exc:
            logger.warning(f"oracle/event-brief: internal TA fetch failed — {exc}")

    # ── Fetch Gamma Context if GEX Slugs ──
    gamma_context = {}
    if req.event_name.startswith("GEX:"):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                symbol = req.event_name.split(":")[1] if ":" in req.event_name else "SPY"
                r = await client.get(f"http://127.0.0.1:8000/api/v1/gamma/{symbol}")
                if r.status_code == 200:
                    gamma_context = r.json()
        except Exception as exc:
            logger.warning(f"oracle/event-brief: internal gamma fetch failed — {exc}")

    context = {
        "event": {
            "name":     req.event_name,
            "actual":   req.event_data.get("actual"),
            "signal":   req.event_data.get("signal"),
            "surprise": req.event_data.get("surprise"),
            "slug":     req.event_data.get("slug"),
            "surprise_reasoning": req.event_data.get("surprise"), # We mapped surprise to the extra values in DP widgets
        },
        "kill_chain": {
            "alert_level":   dig(brief, "kill_chain_state", "alert_level"),
            "layers_active": dig(brief, "kill_chain_state", "layers_active"),
            "narrative":     dig(brief, "kill_chain_state", "narrative"),
        },
        "derivatives": {
            "gex_regime":             dig(brief, "derivatives", "gex_regime"),
            "spot":                   dig(brief, "derivatives", "spot"),
            "gamma_flip":             dig(brief, "derivatives", "gamma_flip"),
            "max_pain":               dig(brief, "derivatives", "max_pain"),
            "distance_from_max_pain": dig(brief, "derivatives", "distance_from_max_pain"),
            "cot_spec_net":           dig(brief, "derivatives", "cot_spec_net"),
            "cot_spec_side":          dig(brief, "derivatives", "cot_spec_side"),
            "cot_divergent":          dig(brief, "derivatives", "cot_divergent"),
            "next_above":             dig(brief, "pivots", "next_above"),
            "next_below":             dig(brief, "pivots", "next_below"),
            "ema_200":                dig(brief, "pivots", "ema_200"),
        },
        "dark_pool_context": dp_context,
        "cot_context": cot_context,
        "pivot_context": pivot_context,
        "ta_context": ta_context,
        "gamma_context": gamma_context,
        "squeeze_candidates": dig(brief, "squeeze_watchlist", "top3") or [],
        "macro_regime":       dig(brief, "macro_regime", "regime"),
        "fed_tone":           dig(brief, "hidden_hands", "fed_tone"),
        "adp_signal":         dig(brief, "adp_prediction", "signal"),
        "gdp_signal":         dig(brief, "gdp_nowcast", "signal"),
        "jobless_signal":     dig(brief, "jobless_claims", "signal"),
    }

    # Cache key = event_name + brief derivatives hash (brief changes slowly)
    cache_key = f"{req.event_name}:{hashlib.md5(json.dumps(context, sort_keys=True, default=str).encode()).hexdigest()}"
    now = time.time()
    cached = _event_oracle_cache.get(cache_key)
    if cached and cached.get("expires", 0) > now:
        return cached["result"]

    user_prompt = (
        f"Economic event: {req.event_name}\n\n"
        "Full context:\n"
        + json.dumps(context, indent=2, default=str)
    )

    groq_payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": NYX_EVENT_SYSTEM},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens":  400,
        "temperature": 0.2,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=groq_payload,
            )
            resp.raise_for_status()
    except Exception as exc:
        return {
            "summary": f"BRIEFING_ENGINE_OFFLINE: {exc}",
            "trade_implication": None,
            "risk_level": "UNKNOWN",
            "confidence": 0.0,
        }

    raw = resp.json()["choices"][0]["message"]["content"].strip()
    # Strip accidental fences
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = raw[: raw.rfind("```")]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {
            "summary": raw[:400],
            "trade_implication": None,
            "risk_level": "UNKNOWN",
            "confidence": 0.0,
        }

    result = {
        "summary":          parsed.get("summary", ""),
        "trade_implication": parsed.get("trade_implication"),
        "risk_level":       parsed.get("risk_level", "UNKNOWN"),
        "confidence":       parsed.get("confidence", 0.0),
        "generated_at":     datetime.datetime.utcnow().isoformat(),
    }

    # Cache for 90 seconds (events don't change that fast)
    _event_oracle_cache[cache_key] = {"result": result, "expires": now + 90}
    return result



def _build_kc_prompt(req: OracleRequest) -> str:
    """Build a structured Kill Chain prompt from the full snapshot."""
    kc = req.kill_chain_snapshot
    assert kc is not None  # caller guarantees this — fixes Pyright NoneType narrowing
    layer_count = len(kc.layers)
    layer_lines = "\n".join(
        f"  Layer {i+1} — {l.name}: {'✅ PASS' if l.triggered else '❌ FAIL'}"
        f"  |  {l.value:.3f} {l.unit}  |  Signal: {l.signal}"
        for i, l in enumerate(kc.layers)
    )
    return "\n".join([
        "══ KILL CHAIN STATE SNAPSHOT ══",
        f"Score: {kc.score}  |  Verdict: {kc.verdict}  |  Direction: {kc.direction}",
        f"Confluence: {kc.confluence}  |  Armed: {'YES 🔴' if kc.armed else 'NO ⚫'}",
        f"Bullish pts: {kc.bullish_points}  |  Bearish pts: {kc.bearish_points}",
        f"SPY Spot: ${kc.spy_spot:.2f}" if kc.spy_spot else "SPY Spot: N/A",
        f"Triggered: {kc.triggered_count}/{layer_count} layers",
        f"System checks: {kc.total_checks or '?'}  |  Activations: {kc.activations or '?'}",
        "",
        "══ CONFLUENCE LAYER BREAKDOWN ══",
        layer_lines,
        "",
        "══ CLICKED SIGNAL (DRILL-DOWN TARGET) ══",
        f"Title:   {req.title or req.action or 'N/A'}",
        f"Value:   {req.value or req.price or 'N/A'}",
        f"Status:  {req.status or 'N/A'}",
        f"Meaning: {req.meaning or 'N/A'}",
        f"Slug:    {req.slug or 'N/A'}",
        "",
        f"Analyze the clicked signal in the context of the {layer_count}-layer Kill Chain state above. "
        "Explain cross-layer confluence or contradiction, trade thesis implications, and next actions.",
    ])


def _build_fallback_prompt(req: OracleRequest) -> str:
    return "\n".join([
        "Analyze Execution Signal:",
        f"Title:   {req.title or req.action or 'N/A'}",
        f"Value:   {req.value or req.price or 'N/A'}",
        f"Metric:  {req.unit or req.result or 'N/A'}",
        f"Logic:   {req.goal or req.layers or 'N/A'}",
        f"Meaning: {req.meaning or 'N/A'}",
        f"Slug:    {req.slug or 'N/A'}",
        "",
        "Explain mathematical significance, current logic state, and tactical directives.",
    ])


@router.post("/oracle/analyze")
async def oracle_analyze(req: OracleRequest):
    """Per-signal KC drill-down. Preserved for KillChainDashboard dev/fallback use."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return {"analysis": "ORACLE_UPLINK_FAILURE: GROQ_API_KEY not configured on server.", "error": True}

    user_prompt = _build_kc_prompt(req) if req.kill_chain_snapshot else _build_fallback_prompt(req)

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": ZO_KC_SYSTEM},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0.35,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if text:
            # text is a JSON string containing the ZO schema
            return {"analysis": text, "error": False, "mode": "kill_chain" if req.kill_chain_snapshot else "fallback"}
        return {"analysis": json.dumps({"audit": f"ORACLE_UPLINK_FAILURE: {data.get('error', {}).get('message', 'No content.')}"}), "error": True}
    except Exception as e:
        return {"analysis": json.dumps({"audit": f"ORACLE_UPLINK_FAILURE: {str(e)}"}), "error": True}
