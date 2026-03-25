"""
Kill Chain — Layer Registry

Handles data layer imports (with graceful fallbacks), client initialization,
the safe_fetch decorator, and all 5 layer fetcher properties.

Extracted from kill_chain_engine.py for modularity.
Each fetcher is a standalone property that returns a callable.
"""

import os
import time
import logging
from functools import wraps
from typing import Optional, Dict

from backend.app.core import kill_chain_config as config

logger = logging.getLogger(__name__)


# ─── Import Data Layer Modules (graceful fallbacks) ─────────────────────────

try:
    from live_monitoring.enrichment.apis.fedwatch_diy import FedWatchEngine
    FEDWATCH_AVAILABLE = True
except ImportError:
    try:
        from fedwatch_diy import FedWatchEngine
        FEDWATCH_AVAILABLE = True
    except ImportError:
        FEDWATCH_AVAILABLE = False
        logger.warning("⚠️ FedWatch engine not available")

try:
    from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
    STOCKGRID_AVAILABLE = True
except ImportError:
    try:
        from stockgrid_client import StockgridClient
        STOCKGRID_AVAILABLE = True
    except ImportError:
        STOCKGRID_AVAILABLE = False
        logger.warning("⚠️ Stockgrid client not available")

try:
    from live_monitoring.enrichment.apis.cot_client import COTClient
    COT_AVAILABLE = True
except ImportError:
    try:
        from cot_client import COTClient
        COT_AVAILABLE = True
    except ImportError:
        COT_AVAILABLE = False
        logger.warning("⚠️ COT client not available")

try:
    from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator
    GEX_AVAILABLE = True
except ImportError:
    try:
        from gex_calculator import GEXCalculator
        GEX_AVAILABLE = True
    except ImportError:
        GEX_AVAILABLE = False
        logger.warning("⚠️ GEX calculator not available")

try:
    from live_monitoring.enrichment.apis.sec_13f_client import SEC13FClient
    SEC13F_AVAILABLE = True
except ImportError:
    try:
        from sec_13f_client import SEC13FClient
        SEC13F_AVAILABLE = True
    except ImportError:
        SEC13F_AVAILABLE = False
        logger.warning("⚠️ SEC 13F client not available")


# 🔥 OOM FIX: Module-level singletons for COT + GEX used by LayerRegistry
import threading as _kc_threading
_kc_cot_singleton = None
_kc_gex_singleton = None
_kc_singleton_lock = _kc_threading.Lock()

def _get_cot_singleton():
    global _kc_cot_singleton
    if _kc_cot_singleton is None:
        with _kc_singleton_lock:
            if _kc_cot_singleton is None:
                _kc_cot_singleton = COTClient(cache_ttl=config.CACHE_TTLS.get("COT", 3600))
    return _kc_cot_singleton

def _get_gex_singleton():
    global _kc_gex_singleton
    if _kc_gex_singleton is None:
        with _kc_singleton_lock:
            if _kc_gex_singleton is None:
                _kc_gex_singleton = GEXCalculator(cache_ttl=config.CACHE_TTLS.get("GEX", 300))
    return _kc_gex_singleton


# ─── Layer Registry ────────────────────────────────────────────────────────

class LayerRegistry:
    """
    Manages data layer client lifecycle and provides safe fetchers.
    
    Each layer is optional — the registry works even if some sources fail.
    """

    def __init__(self, diffbot_token: Optional[str] = None):
        """Initialize all available data layer clients."""
        self._clients: Dict = {}
        
        if FEDWATCH_AVAILABLE:
            token = diffbot_token or os.getenv("DIFFBOT_TOKEN")
            self._clients["fedwatch"] = FedWatchEngine(diffbot_token=token)
        
        if STOCKGRID_AVAILABLE:
            self._clients["dark_pool"] = StockgridClient(cache_ttl=config.CACHE_TTLS["DARK_POOL"])
        
        # 🔥 OOM FIX: Use module-level singletons for COT + GEX
        if COT_AVAILABLE:
            self._clients["cot"] = _get_cot_singleton()
        
        if GEX_AVAILABLE:
            self._clients["gex"] = _get_gex_singleton()
        
        if SEC13F_AVAILABLE:
            self._clients["sec_13f"] = SEC13FClient(cache_ttl=config.CACHE_TTLS["SEC_13F"])
        
        available = list(self._clients.keys())
        logger.info(f"🐺 KillChainEngine initialized: {len(available)}/5 layers active: {available}")
    
    @property
    def available_layers(self):
        return list(self._clients.keys())

    def _layer_safe_fetch(self, layer_name: str):
        """Decorator to safely fetch layer data with logging and timing."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if layer_name not in self._clients:
                    return None
                try:
                    t0 = time.time()
                    result = func(*args, **kwargs)
                    elapsed = time.time() - t0
                    if result:
                        logger.debug(f"✅ {layer_name} fetch complete ({elapsed:.2f}s)")
                    return result
                except Exception as e:
                    logger.error(f"❌ {layer_name} layer failed: {e}")
                    return None
            return wrapper
        return decorator

    # ── Layer Fetchers ───────────────────────────────────────────────────

    @property
    def fedwatch_fetcher(self):
        @self._layer_safe_fetch("fedwatch")
        def fetch():
            data = self._clients["fedwatch"].get_probabilities()
            return {
                "current_rate": data.get("current_rate", ""),
                "current_range": data.get("current_range", ""),
                "next_meeting": data.get("next_meeting", {}),
                "summary": data.get("summary", ""),
                "source": data.get("source", ""),
                "narrative": self._clients["fedwatch"].get_narrative(),
            }
        return fetch

    @property
    def dark_pool_fetcher(self):
        @self._layer_safe_fetch("dark_pool")
        def fetch():
            symbol = config.SYMBOLS["INDEX"]
            client = self._clients["dark_pool"]
            top_all = client.get_top_positions(limit=100)
            spy = client.get_ticker_detail(symbol)
            
            # Fallback: find SPY in top_all if detail fails
            if not spy and top_all:
                for pos in top_all:
                    if pos.ticker == symbol:
                        spy = pos
                        break
            
            top = top_all[:5]
            return {
                "spy_position_dollars": spy.dp_position_dollars if spy else 0,
                "spy_short_vol_pct": spy.short_volume_pct if spy else 0,
                "spy_net_short_dollars": spy.net_short_dollars if spy else 0,
                "top_positions": [
                    {"ticker": p.ticker, "dp_position_dollars": p.dp_position_dollars,
                     "short_vol_pct": p.short_volume_pct}
                    for p in top
                ],
                "narrative": client.get_narrative(),
            }
        return fetch

    @property
    def cot_fetcher(self):
        @self._layer_safe_fetch("cot")
        def fetch():
            symbol = config.SYMBOLS["FUTURES"]
            client = self._clients["cot"]
            pos = client.get_position(symbol)
            div = client.get_divergence_signal(symbol)
            return {
                "specs_net": pos.specs_net if pos else 0,
                "comm_net": pos.comm_net if pos else 0,
                "open_interest": pos.open_interest if pos else 0,
                "report_date": pos.report_date if pos else "",
                "divergence": div,
                "narrative": client.get_narrative(symbol),
            }
        return fetch

    @property
    def gex_fetcher(self):
        @self._layer_safe_fetch("gex")
        def fetch():
            symbol = config.SYMBOLS["INDEX_FUTURES"]
            calc = self._clients["gex"]
            result = calc.compute_gex(symbol)
            return {
                "spot_price": result.spot_price,
                "total_gex": result.total_gex,
                "gamma_regime": result.gamma_regime,
                "gamma_flip": result.gamma_flip,
                "max_pain": result.max_pain,
                "gamma_walls": [
                    {"strike": w.strike, "gex": w.gex, "signal": w.signal}
                    for w in result.gamma_walls[:5]
                ],
                "negative_zones": [
                    {"strike": z.strike, "gex": z.gex}
                    for z in result.negative_zones[:3]
                ],
                "narrative": calc.get_narrative(symbol),
            }
        return fetch

    @property
    def sec_13f_fetcher(self):
        @self._layer_safe_fetch("sec_13f")
        def fetch():
            client = self._clients["sec_13f"]
            filings = []
            for name in config.TRACKED_FUNDS:
                f = client.get_latest_filing(name)
                if f:
                    filings.append({
                        "fund": f.fund_name,
                        "filing_date": f.filing_date,
                        "form_type": f.form_type,
                    })
                time.sleep(0.1)  # Small throttle
            return {
                "filings": filings,
                "narrative": f"13F: {len(filings)} key funds tracked, latest: {filings[0]['fund']} ({filings[0]['filing_date']})" if filings else "No 13F data",
            }
        return fetch

    def get_all_fetchers(self) -> Dict:
        """Return mapping of layer names to fetcher callables."""
        return {
            "fedwatch": self.fedwatch_fetcher,
            "dark_pool": self.dark_pool_fetcher,
            "cot": self.cot_fetcher,
            "gex": self.gex_fetcher,
            "sec_13f": self.sec_13f_fetcher,
        }
