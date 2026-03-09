"""
GEX Calculator — Gamma Exposure Intelligence from CBOE Options

Source: CBOE free delayed options API (no auth, no key)
Data:   Full options chains with pre-calculated greeks (delta, gamma, vega, theta, rho)
Tickers: SPX, SPY, QQQ, NDX, RUT, and any CBOE-listed equity
Freshness: ~15 min delay (free tier)

Endpoint: GET https://cdn.cboe.com/api/global/delayed_quotes/options/{ticker}.json

How GEX works:
  - Positive GEX = dealers are long gamma = they BUY dips and SELL rips = dampening
  - Negative GEX = dealers are short gamma = they SELL into drops and BUY into rips = amplifying
  - Gamma Flip = strike where cumulative GEX crosses zero = key pivot level
"""
import logging
import time
import requests
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple

logger = logging.getLogger(__name__)


# ─── Data Models ────────────────────────────────────────────────────────────

@dataclass
class GammaWall:
    """A strike price with significant gamma exposure."""
    strike: float
    gex: float  # positive = support, negative = resistance
    open_interest: int = 0
    signal: str = ""  # "SUPPORT" or "RESISTANCE"


@dataclass
class GEXResult:
    """Complete gamma exposure analysis."""
    ticker: str = ""
    spot_price: float = 0.0
    total_gex: float = 0.0
    gamma_regime: str = ""  # "POSITIVE" or "NEGATIVE"
    gamma_flip: float = 0.0  # strike where GEX flips sign
    max_pain: float = 0.0  # max OI strike
    gamma_walls: List[GammaWall] = field(default_factory=list)
    negative_zones: List[GammaWall] = field(default_factory=list)
    total_contracts: int = 0
    total_calls: int = 0
    total_puts: int = 0
    timestamp: str = ""
    source: str = "cboe"


# ─── GEX Calculator ────────────────────────────────────────────────────────

class GEXCalculator:
    """
    Gamma Exposure calculator from CBOE free delayed options data.
    
    Computes:
      - GEX by strike (gamma * OI * 100 * spot * 0.01 * direction)
      - Top gamma walls (support levels with large positive GEX)
      - Negative gamma zones (resistance with large negative GEX)
      - Gamma regime (positive = dealers dampen, negative = dealers amplify)
      - Gamma flip point (where GEX transitions)
      - Max pain strike (highest total OI)
    """

    BASE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options"
    HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    
    # CBOE tickers use underscore prefix for indices
    TICKER_MAP = {
        "SPX": "_SPX",
        "NDX": "_NDX",
        "RUT": "_RUT",
        "VIX": "_VIX",
        "SPY": "SPY",
        "QQQ": "QQQ",
        "IWM": "IWM",
    }

    def __init__(self, cache_ttl: int = 300):
        """
        Args:
            cache_ttl: Cache TTL in seconds (default 5 min).
        """
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}
        self._cache_ttl = cache_ttl
        logger.info("📊 GEXCalculator initialized (CBOE free API, no auth)")

    def _is_cached(self, key: str) -> bool:
        return key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < self._cache_ttl

    def _fetch_options_chain(self, ticker: str) -> Tuple[float, List[Dict], str]:
        """
        Fetch raw options chain from CBOE.
        
        Returns: (spot_price, options_list, timestamp)
        """
        cboe_ticker = self.TICKER_MAP.get(ticker.upper(), ticker.upper())
        url = f"{self.BASE_URL}/{cboe_ticker}.json"
        
        r = requests.get(url, headers=self.HEADERS, timeout=15)
        r.raise_for_status()
        
        data = r.json()
        spot = float(data.get("data", {}).get("current_price", 0))
        options = data.get("data", {}).get("options", [])
        ts = data.get("timestamp", "")
        
        return spot, options, ts

    # ── Main GEX Computation ─────────────────────────────────────────────

    def compute_gex(self, ticker: str = "SPX", range_pct: float = 5.0) -> GEXResult:
        """
        Compute gamma exposure for a ticker.
        
        Args:
            ticker: Ticker symbol (SPX, SPY, QQQ, etc.)
            range_pct: % range around spot to focus analysis on.
        
        Returns:
            GEXResult with gamma walls, regime, flip point, max pain.
        """
        cache_key = f"gex_{ticker}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        try:
            spot, options, ts = self._fetch_options_chain(ticker)
            
            if not options or spot == 0:
                logger.warning(f"⚠️ No options data for {ticker}")
                return GEXResult(ticker=ticker)
            
            # Parse options and compute GEX
            strike_min = spot * (1 - range_pct / 100)
            strike_max = spot * (1 + range_pct / 100)
            
            strike_gex: Dict[float, float] = {}
            strike_oi: Dict[float, int] = {}
            n_calls = 0
            n_puts = 0
            
            for o in options:
                sym = o.get("option", "")
                if not sym or len(sym) < 10:
                    continue
                
                delta = o.get("delta", 0) or 0
                gamma = o.get("gamma", 0) or 0
                oi = int(o.get("open_interest", 0) or 0)
                
                # Extract strike from symbol (last 8 digits / 1000)
                try:
                    strike = int(sym[-8:]) / 1000
                except (ValueError, IndexError):
                    continue
                
                if strike < strike_min or strike > strike_max:
                    continue
                
                # Determine call/put by delta sign
                is_call = delta > 0
                if is_call:
                    n_calls += 1
                else:
                    n_puts += 1
                
                # GEX formula: gamma * OI * 100 * spot * 0.01 * direction
                # Calls: positive GEX (dealers buy dips)
                # Puts: negative GEX (dealers sell rips)
                direction = 1 if is_call else -1
                gex = gamma * oi * 100 * spot * 0.01 * direction
                
                strike_gex[strike] = strike_gex.get(strike, 0) + gex
                strike_oi[strike] = strike_oi.get(strike, 0) + oi
            
            # Sort by GEX
            sorted_strikes = sorted(strike_gex.items(), key=lambda x: x[1], reverse=True)
            
            # Top gamma walls (positive GEX = support)
            gamma_walls = []
            for strike, gex in sorted_strikes[:10]:
                if gex > 0:
                    gamma_walls.append(GammaWall(
                        strike=strike, gex=gex,
                        open_interest=strike_oi.get(strike, 0),
                        signal="SUPPORT"
                    ))
            
            # Negative gamma zones (negative GEX = resistance)
            negative_zones = []
            for strike, gex in sorted(sorted_strikes, key=lambda x: x[1])[:5]:
                if gex < 0:
                    negative_zones.append(GammaWall(
                        strike=strike, gex=gex,
                        open_interest=strike_oi.get(strike, 0),
                        signal="RESISTANCE"
                    ))
            
            # Total GEX
            total_gex = sum(strike_gex.values())
            regime = "POSITIVE" if total_gex > 0 else "NEGATIVE"
            
            # Max pain (strike with max total OI)
            max_pain = max(strike_oi.items(), key=lambda x: x[1])[0] if strike_oi else 0
            
            # Gamma flip (where cumulative GEX crosses zero)
            gamma_flip = 0.0
            sorted_by_strike = sorted(strike_gex.items(), key=lambda x: x[0])
            cumulative = 0
            prev_cumulative = 0
            for strike, gex in sorted_by_strike:
                prev_cumulative = cumulative
                cumulative += gex
                if prev_cumulative * cumulative < 0 and abs(strike - spot) < spot * 0.05:
                    gamma_flip = strike
            
            result = GEXResult(
                ticker=ticker,
                spot_price=spot,
                total_gex=total_gex,
                gamma_regime=regime,
                gamma_flip=gamma_flip,
                max_pain=max_pain,
                gamma_walls=gamma_walls,
                negative_zones=negative_zones,
                total_contracts=len(options),
                total_calls=n_calls,
                total_puts=n_puts,
                timestamp=ts,
            )
            
            self._cache[cache_key] = result
            self._cache_ts[cache_key] = time.time()
            logger.info(f"✅ {ticker} GEX: {regime} ({total_gex:,.0f}), "
                        f"spot=${spot:,.2f}, walls={len(gamma_walls)}")
            return result
            
        except Exception as e:
            logger.error(f"❌ GEX calculation error for {ticker}: {e}")
            return self._cache.get(cache_key, GEXResult(ticker=ticker))

    # ── Narrative ────────────────────────────────────────────────────────

    def get_narrative(self, ticker: str = "SPX") -> str:
        """Generate narrative-ready text for SavageAgents."""
        try:
            r = self.compute_gex(ticker)
            if not r.spot_price:
                return f"{ticker} GEX data unavailable"
            
            parts = [
                f"{ticker} ${r.spot_price:,.2f}",
                f"GEX: {r.gamma_regime} ({r.total_gex:,.0f})",
            ]
            
            if r.gamma_regime == "NEGATIVE":
                parts.append("dealers AMPLIFY moves (sell rips, buy dips)")
            else:
                parts.append("dealers DAMPEN moves (buy dips, sell rips)")
            
            if r.gamma_walls:
                top_wall = r.gamma_walls[0]
                parts.append(f"Top wall: {top_wall.strike:.0f} ({top_wall.gex:+,.0f} GEX)")
            
            if r.negative_zones:
                top_neg = r.negative_zones[0]
                parts.append(f"Key resistance: {top_neg.strike:.0f} ({top_neg.gex:,.0f} GEX)")
            
            if r.gamma_flip:
                loc = "BELOW" if r.spot_price < r.gamma_flip else "ABOVE"
                parts.append(f"Gamma flip: {r.gamma_flip:.0f} (spot {loc})")
            
            return " | ".join(parts)
        except Exception as e:
            logger.error(f"❌ GEX narrative error: {e}")
            return f"{ticker} GEX data unavailable"


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    calc = GEXCalculator()
    
    print("=" * 60)
    print("🐺 GEX Calculator — Live Test")
    print("=" * 60)
    
    for ticker in ["SPX", "SPY"]:
        print(f"\n--- {ticker} ---")
        result = calc.compute_gex(ticker)
        print(f"  Spot: ${result.spot_price:,.2f}")
        print(f"  Total GEX: {result.total_gex:,.0f} ({result.gamma_regime})")
        print(f"  Contracts: {result.total_contracts:,} ({result.total_calls:,} calls, {result.total_puts:,} puts)")
        print(f"  Max Pain: {result.max_pain:.0f}")
        
        if result.gamma_walls:
            print(f"  Gamma Walls:")
            for w in result.gamma_walls[:5]:
                print(f"    {w.strike:>7.0f}: {w.gex:>+12,.0f} GEX 🟢")
        
        if result.negative_zones:
            print(f"  Negative Zones:")
            for z in result.negative_zones[:3]:
                print(f"    {z.strike:>7.0f}: {z.gex:>+12,.0f} GEX 🔴")
        
        if result.gamma_flip:
            print(f"  Gamma Flip: {result.gamma_flip:.0f}")
    
    print(f"\n--- Narrative ---")
    print(calc.get_narrative("SPX"))
