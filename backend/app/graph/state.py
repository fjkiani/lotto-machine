"""
AlphaState — shared state TypedDict for the LangGraph alpha pipeline.
Each node reads from and writes to this dict.
"""
from typing import TypedDict, Optional, List, Dict, Any
import time


class AlphaState(TypedDict, total=False):
    # ── Input ─────────────────────────────────────────────────────────────────
    symbol: str                          # e.g. "SPY"
    run_id: str                          # UUID for this graph run
    started_at: float                    # time.time() at graph entry

    # ── Node outputs ──────────────────────────────────────────────────────────
    macro_context: Optional[str]         # MacroNode: COT + Fed narrative
    flow_context: Optional[str]          # FlowNode: dark pool + AXLFI narrative
    regime_context: Optional[str]        # RegimeNode: GEX regime + vol narrative

    # ── Synthesis ─────────────────────────────────────────────────────────────
    synthesis: Optional[str]             # SynthesisNode: unified LLM reasoning

    # ── Gate ──────────────────────────────────────────────────────────────────
    gate_result: Optional[Dict[str, Any]]  # GateNode: kill chain snapshot

    # ── Final verdict ─────────────────────────────────────────────────────────
    verdict: Optional[str]               # "ARMED" | "HOLD" | "VETO"
    confidence: Optional[float]          # 0.0 – 1.0
    thesis: Optional[str]                # 2-sentence plain English
    primary_risk: Optional[str]          # single biggest risk
    direction: Optional[str]             # "BULLISH" | "BEARISH" | "MIXED"

    # ── Diagnostics ───────────────────────────────────────────────────────────
    errors: List[str]                    # non-fatal errors accumulated
    node_timings: Dict[str, float]       # node_name → elapsed seconds
