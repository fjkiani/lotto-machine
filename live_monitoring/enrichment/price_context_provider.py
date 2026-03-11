"""
💰 PRICE CONTEXT PROVIDER — Cached Price Lookback
Sprint 2.4: Provides 1d/5d/20d price context for all checkers.

Uses yfinance with caching to avoid hammering the API.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# In-memory cache: {symbol: {data, timestamp}}
_price_cache: Dict[str, Dict] = {}
_CACHE_TTL = 300  # 5 minutes


class PriceContextProvider:
    """
    Cached price context for checkers.
    Provides 1d/5d/20d price changes + current price + volume context.
    All checkers can use this instead of each one calling yfinance separately.
    """

    def get_context(self, symbol: str) -> Dict:
        """
        Get price context with caching.
        Returns current price, 1d/5d/20d changes, volume info.
        """
        # Check cache
        cached = _price_cache.get(symbol)
        if cached and (time.time() - cached["timestamp"]) < _CACHE_TTL:
            return cached["data"]

        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo")

            if hist.empty or len(hist) < 2:
                return self._empty_result(symbol, "No price data from yfinance")

            current_price = float(hist['Close'].iloc[-1])
            current_volume = int(hist['Volume'].iloc[-1])
            avg_volume_20d = int(hist['Volume'].mean())

            # Price changes
            changes = {}
            for label, lookback in [("1d", 1), ("5d", 5), ("20d", 20)]:
                if len(hist) > lookback:
                    prev = float(hist['Close'].iloc[-(lookback + 1)])
                    change_pct = (current_price - prev) / prev * 100
                    changes[f"change_{label}_pct"] = round(change_pct, 2)
                else:
                    changes[f"change_{label}_pct"] = None

            # Volume context
            volume_ratio = current_volume / avg_volume_20d if avg_volume_20d > 0 else 1

            # High/Low in period
            high_20d = float(hist['High'].max())
            low_20d = float(hist['Low'].min())
            range_position = (current_price - low_20d) / (high_20d - low_20d) if high_20d != low_20d else 0.5

            result = {
                "symbol": symbol.upper(),
                "has_data": True,
                "current_price": round(current_price, 2),
                "current_volume": current_volume,
                "avg_volume_20d": avg_volume_20d,
                "volume_ratio": round(volume_ratio, 2),
                **changes,
                "high_20d": round(high_20d, 2),
                "low_20d": round(low_20d, 2),
                "range_position": round(range_position, 3),
                "data_points": len(hist),
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Cache it
            _price_cache[symbol] = {"data": result, "timestamp": time.time()}
            return result

        except ImportError:
            return self._empty_result(symbol, "yfinance not installed")
        except Exception as e:
            logger.warning(f"PriceContextProvider error for {symbol}: {e}")
            return self._empty_result(symbol, str(e))

    def get_multi(self, symbols: list) -> Dict[str, Dict]:
        """Get price context for multiple symbols."""
        return {sym: self.get_context(sym) for sym in symbols}

    def _empty_result(self, symbol: str, error: str) -> Dict:
        return {
            "symbol": symbol.upper(),
            "has_data": False,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        }
