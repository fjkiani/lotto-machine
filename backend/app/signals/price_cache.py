"""
Live price fetcher with 60-second in-memory cache.
Uses yfinance fast_info to avoid heavy API calls.
"""
import time
import logging
from typing import Dict

import yfinance as yf

logger = logging.getLogger(__name__)

_price_cache: Dict[str, dict] = {}
_CACHE_TTL = 60  # seconds


def get_live_price(symbol: str) -> float:
    """Return the latest trade price for `symbol`, cached for 60 seconds.

    Returns 0.0 if the symbol cannot be fetched — callers must handle this.
    Never raises.
    """
    now = time.time()
    cached = _price_cache.get(symbol)
    if cached and (now - cached["time"]) < _CACHE_TTL:
        return cached["price"]

    try:
        ticker = yf.Ticker(symbol)
        price = ticker.fast_info.last_price
        if price:
            _price_cache[symbol] = {"price": float(price), "time": now}
            return float(price)
    except Exception as exc:
        logger.warning(f"get_live_price({symbol}) failed: {exc}")

    return 0.0
