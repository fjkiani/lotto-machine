"""
Pivot Calculator — Technical Pivot Agent
=========================================

Calculates Classic, Fibonacci, Camarilla, and Woodie pivot points from prior day's OHLC.
Pure math — no external API dependency. Uses yfinance only for prior day OHLC + 200-day EMA.

Cadence: Daily pre-open (9:25am EST) + on-demand if price moves >1%
Cache TTL: 86400s (24h) — pivots only change at market open

This is a specialized agent in the Trap Matrix architecture.
Each agent owns exactly one data domain with its own cadence and failure mode.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


# ─── Data Models ────────────────────────────────────────────────────────────

@dataclass
class PivotSet:
    """A single pivot calculation set (Classic, Fibonacci, or Camarilla)."""
    name: str
    pivot: float
    r1: float
    r2: float
    r3: float
    s1: float
    s2: float
    s3: float
    r4: Optional[float] = None  # Camarilla only
    s4: Optional[float] = None  # Camarilla only

    def to_dict(self) -> dict:
        d = {
            "P": round(self.pivot, 2),
            "R1": round(self.r1, 2), "R2": round(self.r2, 2), "R3": round(self.r3, 2),
            "S1": round(self.s1, 2), "S2": round(self.s2, 2), "S3": round(self.s3, 2),
        }
        if self.r4 is not None:
            d["R4"] = round(self.r4, 2)
        if self.s4 is not None:
            d["S4"] = round(self.s4, 2)
        return d


@dataclass
class PivotResult:
    """Complete pivot calculation output."""
    symbol: str
    prior_high: float
    prior_low: float
    prior_close: float
    prior_date: str
    classic: PivotSet
    fibonacci: PivotSet
    camarilla: PivotSet
    woodie: Optional[PivotSet] = None
    ema_200: Optional[float] = None
    computed_at: str = ""
    stale: bool = False

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "prior_date": self.prior_date,
            "prior_hlc": {
                "high": round(self.prior_high, 2),
                "low": round(self.prior_low, 2),
                "close": round(self.prior_close, 2),
            },
            "classic": self.classic.to_dict(),
            "fibonacci": self.fibonacci.to_dict(),
            "camarilla": self.camarilla.to_dict(),
            "woodie": self.woodie.to_dict() if self.woodie else None,
            "ema_200": round(self.ema_200, 2) if self.ema_200 else None,
            "computed_at": self.computed_at,
            "stale": self.stale,
        }

    def all_levels_flat(self) -> list:
        """Return all pivot levels as a flat list of {price, label, type} dicts."""
        levels = []
        all_sets = [self.classic, self.fibonacci, self.camarilla]
        if self.woodie:
            all_sets.append(self.woodie)
        for pset in all_sets:
            d = pset.to_dict()
            prefix = pset.name[:3].upper()
            for key, val in d.items():
                level_type = "PIVOT" if key == "P" else "RESISTANCE" if key.startswith("R") else "SUPPORT"
                levels.append({
                    "price": val,
                    "label": f"{prefix}_{key}",
                    "type": level_type,
                    "set": pset.name,
                })
        if self.ema_200:
            levels.append({
                "price": round(self.ema_200, 2),
                "label": "EMA_200",
                "type": "MOVING_AVERAGE",
                "set": "EMA",
            })
        return levels


# ─── Calculator ─────────────────────────────────────────────────────────────

class PivotCalculator:
    """
    Pivot Agent — calculates Classic, Fibonacci, Camarilla, Woodie pivots + 200-day EMA.
    
    Pure math. No external API dependency beyond yfinance for prior OHLC.
    Cache TTL: 86400s (24h).
    Cadence: Daily pre-open.
    Failure mode: yfinance unavailable → serve last cached, flag stale.
    """

    cache_ttl = 86400  # 24 hours

    def __init__(self):
        self._cache: Dict[str, PivotResult] = {}
        self._cache_ts: Dict[str, float] = {}

    def _is_cached(self, symbol: str) -> bool:
        if symbol not in self._cache_ts:
            return False
        return (time.time() - self._cache_ts[symbol]) < self.cache_ttl

    # ── Core Pivot Math ──────────────────────────────────────────────────

    @staticmethod
    def _classic(H: float, L: float, C: float) -> PivotSet:
        P = (H + L + C) / 3
        R1 = 2 * P - L
        S1 = 2 * P - H
        R2 = P + (H - L)
        S2 = P - (H - L)
        R3 = H + 2 * (P - L)
        S3 = L - 2 * (H - P)
        return PivotSet(name="Classic", pivot=P, r1=R1, r2=R2, r3=R3, s1=S1, s2=S2, s3=S3)

    @staticmethod
    def _fibonacci(H: float, L: float, C: float) -> PivotSet:
        P = (H + L + C) / 3
        diff = H - L
        R1 = P + 0.382 * diff
        R2 = P + 0.618 * diff
        R3 = P + 1.000 * diff
        S1 = P - 0.382 * diff
        S2 = P - 0.618 * diff
        S3 = P - 1.000 * diff
        return PivotSet(name="Fibonacci", pivot=P, r1=R1, r2=R2, r3=R3, s1=S1, s2=S2, s3=S3)

    @staticmethod
    def _camarilla(H: float, L: float, C: float) -> PivotSet:
        P = (H + L + C) / 3
        diff = H - L
        R1 = C + 1.1 * diff / 12
        R2 = C + 1.1 * diff / 6
        R3 = C + 1.1 * diff / 4
        R4 = C + 1.1 * diff / 2
        S1 = C - 1.1 * diff / 12
        S2 = C - 1.1 * diff / 6
        S3 = C - 1.1 * diff / 4
        S4 = C - 1.1 * diff / 2
        return PivotSet(name="Camarilla", pivot=P, r1=R1, r2=R2, r3=R3, s1=S1, s2=S2, s3=S3, r4=R4, s4=S4)

    @staticmethod
    def _woodie(H: float, L: float, C: float, O: float) -> PivotSet:
        """Woodie pivot uses Open price instead of Close for pivot point."""
        P = (H + L + 2 * O) / 4  # Woodie: weight Open
        R1 = 2 * P - L
        S1 = 2 * P - H
        R2 = P + (H - L)
        S2 = P - (H - L)
        R3 = H + 2 * (P - L)
        S3 = L - 2 * (H - P)
        return PivotSet(name="Woodie", pivot=P, r1=R1, r2=R2, r3=R3, s1=S1, s2=S2, s3=S3)

    @staticmethod
    def _compute_ema_200(hist) -> Optional[float]:
        """Compute 200-day EMA from historical close prices."""
        try:
            if hist is None or len(hist) < 200:
                return None
            closes = hist["Close"].values
            # EMA with span=200
            multiplier = 2 / (200 + 1)
            ema = float(closes[0])
            for price in closes[1:]:
                ema = (float(price) - ema) * multiplier + ema
            return ema
        except Exception:
            return None

    # ── Public API ───────────────────────────────────────────────────────

    def compute(self, symbol: str) -> Optional[PivotResult]:
        """
        Compute all pivot sets for a symbol.

        Returns PivotResult or None if prior OHLC unavailable.
        Uses cache if fresh (< 24h old).
        """
        symbol = symbol.upper()

        # Return cache if fresh
        if self._is_cached(symbol):
            logger.debug(f"Pivot cache hit for {symbol}")
            return self._cache[symbol]

        try:
            import yfinance as yf
            from datetime import datetime

            ticker = yf.Ticker(symbol)
            # Get 250 trading days for 200-day EMA + prior day OHLC
            hist = ticker.history(period="1y")

            if hist is None or len(hist) < 2:
                logger.warning(f"Insufficient history for {symbol}")
                # Return stale cache if available
                if symbol in self._cache:
                    self._cache[symbol].stale = True
                    return self._cache[symbol]
                return None

            # Prior day = second to last row
            prior = hist.iloc[-2]
            H = float(prior["High"])
            L = float(prior["Low"])
            C = float(prior["Close"])
            O = float(prior["Open"])
            prior_date = str(hist.index[-2].date())

            # 200-day EMA (use all history up to and including prior day)
            ema_200 = self._compute_ema_200(hist.iloc[:-1])

            result = PivotResult(
                symbol=symbol,
                prior_high=H,
                prior_low=L,
                prior_close=C,
                prior_date=prior_date,
                classic=self._classic(H, L, C),
                fibonacci=self._fibonacci(H, L, C),
                camarilla=self._camarilla(H, L, C),
                woodie=self._woodie(H, L, C, O),
                ema_200=ema_200,
                computed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                stale=False,
            )

            # Cache it
            self._cache[symbol] = result
            self._cache_ts[symbol] = time.time()

            logger.info(
                f"✅ Pivots computed for {symbol} from {prior_date}: "
                f"Classic P={result.classic.pivot:.2f}, "
                f"Woodie P={result.woodie.pivot:.2f}, "
                f"EMA200={'%.2f' % ema_200 if ema_200 else 'N/A'}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to compute pivots for {symbol}: {e}")
            # Return stale cache if available
            if symbol in self._cache:
                self._cache[symbol].stale = True
                return self._cache[symbol]
            return None

    def get_narrative(self, symbol: str) -> str:
        """Generate human-readable pivot summary for SavageAgents."""
        result = self.compute(symbol)
        if not result:
            return f"No pivot data available for {symbol}"

        c = result.classic
        ema_str = f" | EMA200={result.ema_200:.2f}" if result.ema_200 else ""
        woodie_str = f" | Woodie P={result.woodie.pivot:.2f}" if result.woodie else ""
        return (
            f"📐 PIVOTS ({symbol}) — Prior {result.prior_date}\n"
            f"Classic: S3={c.s3:.2f} | S2={c.s2:.2f} | S1={c.s1:.2f} | "
            f"P={c.pivot:.2f} | R1={c.r1:.2f} | R2={c.r2:.2f} | R3={c.r3:.2f}\n"
            f"Fib R1={result.fibonacci.r1:.2f} | Cam R3={result.camarilla.r3:.2f}"
            f"{woodie_str}{ema_str}"
        )


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    calc = PivotCalculator()

    for symbol in ["SPY", "QQQ", "AAPL"]:
        print(f"\n{'='*60}")
        result = calc.compute(symbol)
        if result:
            print(json.dumps(result.to_dict(), indent=2))
            print(f"\n--- Narrative ---")
            print(calc.get_narrative(symbol))
            print(f"\n--- All Levels (flat) ---")
            for lvl in result.all_levels_flat():
                print(f"  {lvl['label']:12s} {lvl['price']:>10.2f}  ({lvl['type']})")
        else:
            print(f"No data for {symbol}")
