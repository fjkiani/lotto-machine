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
            levels = []

            # 1. LIVE LEVEL: Current Day Positioning
            if detail:
                # Stockgrid gives SV as 59.2. Threshold is 55.
                short_pct = detail.short_volume_pct or 50.0
                is_resistance = short_pct > 55
                is_support = short_pct < 45
                
                levels.append({
                    "price": round(state.current_price, 2),
                    "volume": int(abs(detail.dp_position_dollars or 0)),
                    "type": "RESISTANCE" if is_resistance else "SUPPORT" if is_support else "BATTLEGROUND",
                    "strength": "STRONG" if abs(detail.dp_position_dollars or 0) > 1e9 else "MODERATE",
                    "short_pct": round(short_pct, 1),
                    "is_live": True,
                    "bounce_rate": None,
                })

            # 2. HISTORIC LEVELS: dp_learning.db clusters
            import sqlite3
            import os
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "dp_learning.db")
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                # Find top 5 clustered zones within 5% of current price
                c.execute('''
                    SELECT ROUND(level_price, 1) as zone, 
                           COUNT(*) as touches,
                           SUM(CASE WHEN outcome='BOUNCE' THEN 1 ELSE 0 END) as bounces,
                           AVG(level_volume) as avg_vol
                    FROM dp_interactions 
                    WHERE symbol = ? 
                      AND level_price BETWEEN ? AND ?
                    GROUP BY ROUND(level_price, 1) 
                    HAVING touches >= 3
                    ORDER BY touches DESC 
                    LIMIT 5
                ''', (symbol, state.current_price * 0.95, state.current_price * 1.05))
                
                for r in c.fetchall():
                    price, touches, bounces, avg_vol = r
                    bounce_rate = round((bounces / touches) * 100) if touches > 0 else 0
                    
                    levels.append({
                        "price": price,
                        "volume": int(avg_vol),
                        "type": "SUPPORT" if bounce_rate > 60 else "RESISTANCE" if bounce_rate < 40 else "BATTLEGROUND",
                        "strength": "STRONG" if touches > 10 else "MODERATE",
                        "short_pct": None,
                        "is_live": False,
                        "bounce_rate": bounce_rate,
                        "touches": touches,
                    })
                conn.close()

            # Sort by volume descending
            levels.sort(key=lambda x: x["volume"], reverse=True)
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
