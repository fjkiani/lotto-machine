"""
Trap Matrix Orchestrator — Thin Coordinator
============================================

The brain of the Trap Matrix system. Wires the 4 focused modules together.

This file owns:
  - Singleton agent lifecycle (via LayerFetcher)
  - State version tracking + history for diffing
  - The get_current_state() public entry point

All logic lives in the modules:
  tm_models.py          → data classes (TrapZone, MarketState, StalenessInfo)
  tm_layer_fetcher.py   → one fetch method per data source
  tm_trap_classifier.py → one classifier function per trap type
  tm_state_differ.py    → should_rebuild() + compute_alert_level()

Architecture:
  pivot_calculator.py   (24h cache, daily pre-open)
  technical_agent.py    (1h cache, daily at close)
  stockgrid_client.py   (5m cache, hourly during market hours)
  gex_calculator.py     (5m cache, every 5min)
  cot_client.py         (1h cache, weekly Fri 3:30pm)
  ↓
  tm_layer_fetcher.py   → writes into MarketState
  tm_trap_classifier.py → classifies traps from MarketState
  tm_state_differ.py    → decides whether to rebuild
  ↓
  THIS FILE: coordinates + returns final MarketState
"""

import logging
from datetime import datetime
from typing import Dict

from .tm_models import MarketState
from .tm_layer_fetcher import LayerFetcher
from .tm_trap_classifier import classify_traps
from .tm_state_differ import compute_alert_level, should_rebuild

logger = logging.getLogger(__name__)


class TrapMatrixOrchestrator:
    """
    Trap Matrix Brain — orchestrates data fetching, trap classification,
    conviction scoring, and rebuild decisions.

    Usage:
        orch = TrapMatrixOrchestrator()
        state = orch.get_current_state("SPY")
        print(state.to_dict())
    """

    def __init__(self):
        self._fetcher = LayerFetcher()
        self._prev_state: Dict[str, MarketState] = {}
        self._version: Dict[str, int] = {}

    def get_current_state(self, symbol: str) -> MarketState:
        """
        Build the current MarketState for a symbol.

        Steps:
          1. Fetch all 5 data layers (each uses its own cache TTL)
          2. Classify trap zones from the merged state
          3. Compute alert level
          4. Diff against previous state to decide if rebuild is needed
          5. Track version and return
        """
        symbol = symbol.upper()
        state = MarketState(symbol=symbol, timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # 1. Fetch (writes into state directly)
        self._fetcher.fetch_all(symbol, state)

        # 2. Classify traps
        state.traps = classify_traps(state)

        # 3. Alert level
        state.alert_level = compute_alert_level(state)

        # 4. Version
        self._version[symbol] = self._version.get(symbol, 0) + 1
        state.version = self._version[symbol]

        # 5. Rebuild diff
        prev = self._prev_state.get(symbol)
        if prev:
            rebuild, reason = should_rebuild(prev, state)
            state.rebuild_reason = reason if rebuild else "no_change"
        else:
            state.rebuild_reason = "initial_build"

        self._prev_state[symbol] = state
        return state


# ─── Standalone Test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    orch = TrapMatrixOrchestrator()

    for symbol in ["SPY", "QQQ"]:
        print(f"\n{'='*70}")
        print(f"🐺 TRAP MATRIX — {symbol}")
        print(f"{'='*70}")

        state = orch.get_current_state(symbol)

        print(f"\n📊 Price: ${state.current_price:.2f}")
        print(f"🎯 Alert: {state.alert_level}")
        print(f"♻️  Rebuild: {state.rebuild_reason}")
        print(f"📈 VIX: {state.vix} ({state.vix_regime})")
        print(f"📋 COT: {state.cot_net_spec} ({state.cot_signal})")
        print(f"⚡ GEX Regime: {state.gamma_regime}")
        print(f"☠️  Death Cross: {state.death_cross}")

        if state.traps:
            print(f"\n🪤 TRAPS ({len(state.traps)}):")
            for t in state.traps:
                print(f"  {t.emoji} {t.trap_type} [{t.conviction}/5]  ${t.price_min:.2f}–${t.price_max:.2f}")
                print(f"     {t.narrative}")
                print(f"     {t.data_point}")
                print(f"     Sources: {', '.join(t.supporting_sources)}")
        else:
            print("\n✅ No traps detected")

        print(f"\n⏱️  STALENESS:")
        for src, info in state.staleness.items():
            flag = "🔴 STALE" if info.stale else "🟢 FRESH"
            print(f"  {src}: {flag}")

        print(f"\n{json.dumps(state.to_dict(), indent=2, default=str)}")
