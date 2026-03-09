"""
tm_layer_fetcher.py — Agent Data Fetching Layer
================================================

One method per data source. Each method:
  - Has its own failure mode (never throws — logs and returns partial state)
  - Reads from its agent's cache (TTL-controlled by each agent)
  - Writes only to its slice of MarketState

Cadences:
  Pivots      → 24h cache — daily pre-open
  Technicals  → 1h cache — daily at close
  Dark Pool   → 5m cache — hourly during market hours
  GEX         → 5m cache — every 5min during market hours
  COT         → 1h cache — weekly Fri 3:30pm

Adding a new data source = add one method here + call it in fetch_all().
"""

import logging
import time
from datetime import datetime
from typing import Optional

from .tm_models import MarketState, StalenessInfo

logger = logging.getLogger(__name__)

# Equity → Futures contract mapping for COT
_COT_MAP = {"SPY": "ES", "QQQ": "NQ", "IWM": "RTY", "DIA": "YM"}


class LayerFetcher:
    """
    Fetches data from all 5 agent clients and writes into a MarketState.
    Each fetch_* method is independent and safe to fail in isolation.
    """

    def __init__(self):
        self._pivot_calc = None
        self._tech_agent = None
        self._cot_client = None
        self._stockgrid = None
        self._gex_calc = None
        self._initialized = False

    def _init_agents(self):
        """Lazy initialize all agent clients once."""
        if self._initialized:
            return
        self._initialized = True  # Set first — prevents retry storm

        try:
            from .pivot_calculator import PivotCalculator
            self._pivot_calc = PivotCalculator()
        except Exception as e:
            logger.warning(f"⚠️ Pivot agent unavailable: {e}")

        try:
            from .technical_agent import TechnicalAgent
            self._tech_agent = TechnicalAgent()
        except Exception as e:
            logger.warning(f"⚠️ Technical agent unavailable: {e}")

        try:
            from .cot_client import COTClient
            self._cot_client = COTClient()
        except Exception as e:
            logger.warning(f"⚠️ COT agent unavailable: {e}")

        try:
            from .stockgrid_client import StockgridClient
            self._stockgrid = StockgridClient()
        except Exception as e:
            logger.warning(f"⚠️ Dark Pool agent unavailable: {e}")

        try:
            from .gex_calculator import GEXCalculator
            self._gex_calc = GEXCalculator()
        except Exception as e:
            logger.warning(f"⚠️ GEX agent unavailable: {e}")

    # ── 1. Pivots ─────────────────────────────────────────────────────────────

    def fetch_pivots(self, symbol: str, state: MarketState) -> None:
        """Fetch Classic/Fib/Camarilla pivots. Cache TTL: 24h."""
        if not self._pivot_calc:
            return
        try:
            result = self._pivot_calc.compute(symbol)
            if not result:
                return
            state.pivots = result.to_dict()
            state.staleness["pivots"] = StalenessInfo(
                source="pivots",
                age_seconds=time.time() - self._pivot_calc._cache_ts.get(symbol, time.time()),
                stale=result.stale,
                last_updated=result.computed_at,
            )
        except Exception as e:
            logger.warning(f"Pivot fetch error: {e}")

    # ── 2. Technicals (MAs + VIX) ────────────────────────────────────────────

    def fetch_technicals(self, symbol: str, state: MarketState) -> None:
        """Fetch MA signals + VIX regime. Cache TTL: 1h."""
        if not self._tech_agent:
            return
        try:
            result = self._tech_agent.compute(symbol)
            if not result:
                return
            state.current_price = result.current_price
            state.moving_averages = result.to_dict().get("moving_averages", {})
            state.vix = result.vix
            state.vix_regime = result.vix_regime
            state.death_cross = result.death_cross
            state.staleness["technicals"] = StalenessInfo(
                source="technicals",
                age_seconds=time.time() - self._tech_agent._cache_ts.get(symbol, time.time()),
                stale=result.stale,
                last_updated=result.computed_at,
            )
        except Exception as e:
            logger.warning(f"Technical fetch error: {e}")

    # ── 3. Dark Pool ─────────────────────────────────────────────────────────

    def fetch_dark_pool(self, symbol: str, state: MarketState) -> None:
        """Fetch Stockgrid dark pool positions. Cache TTL: 5m."""
        if not self._stockgrid:
            return
        try:
            detail = self._stockgrid.get_ticker_detail(symbol)
            top = self._stockgrid.get_top_positions(limit=20)
            levels = []

            if detail:
                vol = abs(detail.net_short_dollars or detail.dp_position_dollars or 0)
                short_pct = detail.short_volume_pct or 50.0
                levels.append({
                    "price": round(state.current_price, 2),
                    "volume": int(abs(detail.dp_position_dollars or 0)),
                    "type": "SUPPORT" if short_pct < 50 else "RESISTANCE",
                    "strength": "STRONG" if abs(detail.dp_position_dollars or 0) > 1e9 else "MODERATE",
                    "short_pct": round(short_pct, 1),
                })

            for pos in top[:10]:
                if pos.ticker and pos.dp_position_dollars:
                    levels.append({
                        "price": 0,
                        "ticker": pos.ticker,
                        "volume": int(abs(pos.dp_position_dollars)),
                        "type": "SUPPORT" if pos.short_volume_pct < 50 else "RESISTANCE",
                        "strength": "STRONG" if abs(pos.dp_position_dollars) > 1e9 else "MODERATE",
                        "short_pct": round(pos.short_volume_pct, 1),
                    })

            state.dp_levels = levels
            state.staleness["dp"] = StalenessInfo(
                source="dark_pool",
                age_seconds=0,
                stale=False,
                last_updated=detail.date if detail else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        except Exception as e:
            logger.warning(f"Dark pool fetch error: {e}")

    # ── 4. GEX (Gamma Exposure) ───────────────────────────────────────────────

    def fetch_gex(self, symbol: str, state: MarketState) -> None:
        """Fetch CBOE gamma walls, flip, max pain, regime. Cache TTL: 5m."""
        if not self._gex_calc:
            return
        try:
            result = self._gex_calc.compute_gex(symbol)
            if not result:
                return
            state.gex_walls = [
                {
                    "strike": w.strike,
                    "gex": w.gex,
                    "signal": w.signal or ("RESISTANCE" if w.gex > 0 else "SUPPORT"),
                }
                for w in result.gamma_walls[:10]
            ]
            state.gamma_flip = result.gamma_flip or None
            state.max_pain = result.max_pain or None
            state.gamma_regime = result.gamma_regime or "UNKNOWN"
            state.staleness["gex"] = StalenessInfo(
                source="gex",
                age_seconds=0,
                stale=False,
                last_updated=result.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        except Exception as e:
            logger.warning(f"GEX fetch error: {e}")

    # ── 5. COT ───────────────────────────────────────────────────────────────

    def fetch_cot(self, symbol: str, state: MarketState) -> None:
        """Fetch CFTC COT speculator positioning. Cache TTL: 1h."""
        if not self._cot_client:
            return
        try:
            contract = _COT_MAP.get(symbol, "ES")
            pos = self._cot_client.get_position(contract)
            if not pos:
                return

            state.cot_net_spec = pos.specs_net
            if pos.specs_net < -100_000:
                state.cot_signal = "SPEC_TRAP_LOADED"
            elif pos.specs_net < 0:
                state.cot_signal = "SPECS_SHORT"
            elif pos.specs_net > 100_000:
                state.cot_signal = "SPECS_CROWDED_LONG"
            else:
                state.cot_signal = "NEUTRAL"

            cache_ts = getattr(self._cot_client, "_cache_ts", {})
            state.staleness["cot"] = StalenessInfo(
                source="cot",
                age_seconds=time.time() - cache_ts.get(f"position_{contract}", time.time()),
                stale=False,
                last_updated=getattr(pos, "report_date", ""),
            )
        except Exception as e:
            logger.warning(f"COT fetch error: {e}")

    # ── Entry Point ───────────────────────────────────────────────────────────

    def fetch_all(self, symbol: str, state: MarketState) -> None:
        """
        Fetch all 5 data layers into state.

        Each fetch is isolated — one failure never blocks others.
        Order matters: technicals must run before trap classification
        (sets current_price used by classifiers).
        """
        self._init_agents()
        self.fetch_pivots(symbol, state)
        self.fetch_technicals(symbol, state)  # sets current_price
        self.fetch_dark_pool(symbol, state)
        self.fetch_gex(symbol, state)
        self.fetch_cot(symbol, state)
