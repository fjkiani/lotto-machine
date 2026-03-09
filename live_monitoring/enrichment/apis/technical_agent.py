"""
Technical Agent — Moving Averages + VIX Regime Intelligence
=============================================================

Calculates MA50/100/200 SMA and EMA values from yfinance historical data.
Classifies each MA as BUY/SELL vs current price.
Pulls VIX level and classifies regime (COMPLACENT / ELEVATED / FEAR).

Cadence: Daily at close + on-demand
Cache TTL: 3600s (1h)
Source: yfinance only (no external API dependency)

This is a specialized agent in the Trap Matrix architecture.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


# ─── Data Models ────────────────────────────────────────────────────────────

@dataclass
class MASignal:
    """Moving average value with directional signal."""
    period: int
    ma_type: str  # "SMA" or "EMA"
    value: float
    signal: str   # "BUY", "SELL", or "NEUTRAL"

    def to_dict(self) -> dict:
        return {
            "value": round(self.value, 2),
            "signal": self.signal,
        }


@dataclass
class TechnicalResult:
    """Complete technical agent output."""
    symbol: str
    current_price: float
    moving_averages: Dict[str, MASignal]  # key = "MA200_SMA", "MA200_EMA", etc.
    vix: Optional[float] = None
    vix_regime: str = "UNKNOWN"  # COMPLACENT, ELEVATED, FEAR
    death_cross: bool = False    # MA50 < MA200
    golden_cross: bool = False   # MA50 > MA200 (after being below)
    computed_at: str = ""
    stale: bool = False

    def to_dict(self) -> dict:
        ma_dict = {}
        for key, ma in self.moving_averages.items():
            ma_dict[key] = ma.to_dict()

        return {
            "symbol": self.symbol,
            "current_price": round(self.current_price, 2),
            "moving_averages": ma_dict,
            "vix": round(self.vix, 2) if self.vix else None,
            "vix_regime": self.vix_regime,
            "death_cross": self.death_cross,
            "golden_cross": self.golden_cross,
            "computed_at": self.computed_at,
            "stale": self.stale,
        }

    def ma_levels_for_chart(self) -> list:
        """Return MA levels formatted for TradingViewChart overlay."""
        levels = []
        color_map = {
            200: {"SMA": "#ff3366", "EMA": "#ff6699"},  # Red family
            100: {"SMA": "#ff8c00", "EMA": "#ffb347"},  # Orange family
            50:  {"SMA": "#3399ff", "EMA": "#66b2ff"},  # Blue family
        }
        width_map = {200: 2, 100: 1, 50: 1}
        style_map = {"SMA": "solid", "EMA": "dashed"}

        for key, ma in self.moving_averages.items():
            levels.append({
                "price": round(ma.value, 2),
                "label": f"{key} ({ma.signal})",
                "color": color_map.get(ma.period, {}).get(ma.ma_type, "#aaaaaa"),
                "width": width_map.get(ma.period, 1),
                "style": style_map.get(ma.ma_type, "solid"),
                "type": "MA",
            })
        return levels


# ─── Calculator ─────────────────────────────────────────────────────────────

class TechnicalAgent:
    """
    Technical Agent — MA signals + VIX regime classification.

    Source: yfinance only.
    Cache TTL: 3600s (1h).
    Cadence: Daily at close + on-demand.
    Failure mode: yfinance unavailable → serve last cached, flag stale.
    """

    cache_ttl = 3600  # 1 hour

    def __init__(self):
        self._cache: Dict[str, TechnicalResult] = {}
        self._cache_ts: Dict[str, float] = {}

    def _is_cached(self, symbol: str) -> bool:
        if symbol not in self._cache_ts:
            return False
        return (time.time() - self._cache_ts[symbol]) < self.cache_ttl

    def _classify_vix(self, vix: float) -> str:
        """Classify VIX regime."""
        if vix < 15:
            return "COMPLACENT"
        elif vix < 25:
            return "ELEVATED"
        else:
            return "FEAR"

    def _ma_signal(self, current_price: float, ma_value: float) -> str:
        """Classify MA signal based on price vs MA."""
        pct_diff = (current_price - ma_value) / ma_value * 100
        if pct_diff > 0.5:
            return "BUY"
        elif pct_diff < -0.5:
            return "SELL"
        return "NEUTRAL"

    def compute(self, symbol: str) -> Optional[TechnicalResult]:
        """
        Compute all MA signals and VIX regime for a symbol.

        Returns TechnicalResult or None.
        Uses cache if fresh (< 1h old).
        """
        symbol = symbol.upper()

        if self._is_cached(symbol):
            logger.debug(f"Technical cache hit for {symbol}")
            return self._cache[symbol]

        try:
            import yfinance as yf
            import pandas as pd
            from datetime import datetime

            ticker = yf.Ticker(symbol)
            # Need 200+ days for MA200
            hist = ticker.history(period="1y")

            if hist is None or len(hist) < 200:
                logger.warning(f"Insufficient history for {symbol} MAs (got {len(hist) if hist is not None else 0} days)")
                if symbol in self._cache:
                    self._cache[symbol].stale = True
                    return self._cache[symbol]
                return None

            close = hist["Close"]
            current_price = float(close.iloc[-1])

            # Compute SMAs
            sma50 = float(close.rolling(50).mean().iloc[-1])
            sma100 = float(close.rolling(100).mean().iloc[-1])
            sma200 = float(close.rolling(200).mean().iloc[-1])

            # Compute EMAs
            ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
            ema100 = float(close.ewm(span=100, adjust=False).mean().iloc[-1])
            ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])

            # Build MA signals
            moving_averages = {
                "MA200_SMA": MASignal(200, "SMA", sma200, self._ma_signal(current_price, sma200)),
                "MA200_EMA": MASignal(200, "EMA", ema200, self._ma_signal(current_price, ema200)),
                "MA100_SMA": MASignal(100, "SMA", sma100, self._ma_signal(current_price, sma100)),
                "MA100_EMA": MASignal(100, "EMA", ema100, self._ma_signal(current_price, ema100)),
                "MA50_SMA":  MASignal(50, "SMA", sma50, self._ma_signal(current_price, sma50)),
                "MA50_EMA":  MASignal(50, "EMA", ema50, self._ma_signal(current_price, ema50)),
            }

            # Detect death cross / golden cross
            death_cross = sma50 < sma200
            golden_cross = sma50 > sma200

            # Get VIX
            vix_value = None
            vix_regime = "UNKNOWN"
            try:
                vix_ticker = yf.Ticker("^VIX")
                vix_hist = vix_ticker.history(period="1d")
                if vix_hist is not None and len(vix_hist) > 0:
                    vix_value = float(vix_hist["Close"].iloc[-1])
                    vix_regime = self._classify_vix(vix_value)
            except Exception as ve:
                logger.warning(f"Failed to fetch VIX: {ve}")

            result = TechnicalResult(
                symbol=symbol,
                current_price=current_price,
                moving_averages=moving_averages,
                vix=vix_value,
                vix_regime=vix_regime,
                death_cross=death_cross,
                golden_cross=golden_cross,
                computed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                stale=False,
            )

            # Cache
            self._cache[symbol] = result
            self._cache_ts[symbol] = time.time()

            cross_status = "☠️ DEATH CROSS" if death_cross else "✨ GOLDEN CROSS" if golden_cross else "—"
            logger.info(
                f"✅ Technicals computed for {symbol}: "
                f"Price={current_price:.2f}, "
                f"MA200={sma200:.2f} ({moving_averages['MA200_SMA'].signal}), "
                f"VIX={vix_value:.1f} ({vix_regime}), "
                f"{cross_status}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to compute technicals for {symbol}: {e}")
            if symbol in self._cache:
                self._cache[symbol].stale = True
                return self._cache[symbol]
            return None

    def get_narrative(self, symbol: str) -> str:
        """Generate human-readable technical summary for SavageAgents."""
        result = self.compute(symbol)
        if not result:
            return f"No technical data available for {symbol}"

        ma_summary = []
        for key, ma in result.moving_averages.items():
            ma_summary.append(f"{key}={ma.value:.2f}({ma.signal})")

        cross = ""
        if result.death_cross:
            cross = " | ☠️ DEATH CROSS ACTIVE"
        elif result.golden_cross:
            cross = " | ✨ GOLDEN CROSS"

        vix_str = f"VIX={result.vix:.1f} ({result.vix_regime})" if result.vix else "VIX=N/A"

        return (
            f"📊 TECHNICALS ({symbol})\n"
            f"Price: {result.current_price:.2f} | {vix_str}{cross}\n"
            f"{' | '.join(ma_summary)}"
        )


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    agent = TechnicalAgent()

    for symbol in ["SPY", "QQQ"]:
        print(f"\n{'='*60}")
        result = agent.compute(symbol)
        if result:
            print(json.dumps(result.to_dict(), indent=2))
            print(f"\n--- Narrative ---")
            print(agent.get_narrative(symbol))
            print(f"\n--- Chart Levels ---")
            for lvl in result.ma_levels_for_chart():
                print(f"  {lvl['label']:30s} {lvl['price']:>10.2f}  {lvl['style']}")
        else:
            print(f"No data for {symbol}")
