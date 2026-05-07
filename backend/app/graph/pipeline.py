"""
Alpha Pipeline — LangGraph StateGraph
======================================
Fan-out: macro_node + flow_node + regime_node run in parallel
Fan-in:  synthesis_node → gate_node → END

Uses MemorySaver for in-process checkpointing (thread_id = run_id).
"""
import uuid
import time
import logging
from typing import Optional

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from backend.app.graph.state import AlphaState
from backend.app.graph.nodes import (
    macro_node,
    flow_node,
    regime_node,
    synthesis_node,
    gate_node,
)

logger = logging.getLogger(__name__)

# ── Build graph ───────────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    builder = StateGraph(AlphaState)

    # Register nodes
    builder.add_node("macro", macro_node)
    builder.add_node("flow", flow_node)
    builder.add_node("regime", regime_node)
    builder.add_node("synthesize", synthesis_node)
    builder.add_node("gate", gate_node)

    # Parallel fan-out from START → macro, flow, regime
    builder.add_edge(START, "macro")
    builder.add_edge(START, "flow")
    builder.add_edge(START, "regime")

    # Fan-in: all three parallel nodes → synthesis
    builder.add_edge("macro", "synthesize")
    builder.add_edge("flow", "synthesize")
    builder.add_edge("regime", "synthesize")

    # Sequential tail
    builder.add_edge("synthesize", "gate")
    builder.add_edge("gate", END)

    return builder


# Compile once at module load — MemorySaver keeps state in-process
_checkpointer = MemorySaver()
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        builder = _build_graph()
        _graph = builder.compile(checkpointer=_checkpointer)
        logger.info("✅ Alpha LangGraph compiled")
    return _graph


# ── Public API ────────────────────────────────────────────────────────────────

def run_alpha_pipeline(symbol: str = "SPY", thread_id: Optional[str] = None) -> AlphaState:
    """
    Run the full alpha pipeline for a symbol.
    Returns the final AlphaState dict.
    thread_id is used for MemorySaver checkpointing — pass same ID to resume.
    """
    run_id = thread_id or str(uuid.uuid4())
    initial_state: AlphaState = {
        "symbol": symbol,
        "run_id": run_id,
        "started_at": time.time(),
        "errors": [],
        "node_timings": {},
    }
    config = {"configurable": {"thread_id": run_id}}
    graph = get_graph()
    final_state = graph.invoke(initial_state, config=config)
    elapsed = round(time.time() - initial_state["started_at"], 2)
    logger.info(
        f"✅ Alpha pipeline complete | symbol={symbol} | verdict={final_state.get('verdict')} "
        f"| confidence={final_state.get('confidence')} | elapsed={elapsed}s"
    )
    return final_state


def get_pipeline_state(thread_id: str) -> Optional[AlphaState]:
    """Retrieve the last checkpointed state for a thread_id."""
    try:
        graph = get_graph()
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = graph.get_state(config)
        return snapshot.values if snapshot else None
    except Exception as e:
        logger.warning(f"get_pipeline_state({thread_id}): {e}")
        return None
