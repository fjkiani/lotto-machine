"""
AlphaState — shared state TypedDict for the LangGraph alpha pipeline.

Parallel nodes (macro, flow, regime) each write to their own exclusive key.
Shared accumulator fields (errors, node_timings) use Annotated reducers so
LangGraph can merge concurrent writes without conflict.
"""
import operator
from typing import TypedDict, Optional, List, Dict, Any, Annotated
import time


class AlphaState(TypedDict, total=False):
    # ── Input ─────────────────────────────────────────────────────────────────
    symbol: str                          # e.g. "SPY"
    run_id: str                          # UUID for this graph run
    started_at: float                    # time.time() at graph entry

    # ── Node outputs (each parallel node owns exactly one of these) ───────────
    macro_context: Optional[str]         # MacroNode exclusive
    flow_context: Optional[str]          # FlowNode exclusive
    regime_context: Optional[str]        # RegimeNode exclusive

    # ── Synthesis (sequential, no conflict) ───────────────────────────────────
    synthesis: Optional[str]             # SynthesisNode: unified LLM reasoning

    # ── Gate (sequential, no conflict) ────────────────────────────────────────
    gate_result: Optional[Dict[str, Any]]  # GateNode: kill chain snapshot

    # ── Final verdict (sequential, no conflict) ───────────────────────────────
    verdict: Optional[str]               # "ARMED" | "HOLD" | "VETO"
    confidence: Optional[float]          # 0.0 – 1.0
    thesis: Optional[str]                # 2-sentence plain English
    primary_risk: Optional[str]          # single biggest risk
    direction: Optional[str]             # "BULLISH" | "BEARISH" | "MIXED"

    # ── Accumulators — Annotated so parallel writes are merged, not conflicted ─
    errors: Annotated[List[str], operator.add]          # appended by each node
    node_timings: Annotated[Dict[str, float], lambda a, b: {**a, **b}]  # merged

    # ── Enrichment signals (populated at graph entry from main.py layers) ─────
    qqq_sv_delta: Optional[float]          # QQQ short vol 1-day delta in pp
    qqq_reshort_spike: Optional[bool]      # True if delta > 10pp while above call wall
    absorption_detected: Optional[bool]    # True if high vol + near-zero price move
    absorption_price: Optional[float]      # Price at absorption candle
    absorption_vol_ratio: Optional[float]  # Volume ratio at absorption
    pts_above_call_wall: Optional[float]   # Positive = above, negative = below
    spy_short_vol_pct: Optional[float]     # SPY dark pool short vol %
    vix: Optional[float]                   # VIX level
