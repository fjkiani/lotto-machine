"""
Options Flow API Endpoints

Provides options flow data, most active options, unusual activity, and accumulation zones.

Data source: CBOE free delayed options API (no auth, no key, ~15 min delay).
NO MOCK FALLBACKS — if data is unavailable the endpoint raises HTTP 503.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Shared CBOE session (lazy init)
# ---------------------------------------------------------------------------

_session = None


def _get_session():
    """Get or create a requests Session for CBOE API."""
    global _session
    if _session is None:
        import requests
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        })
    return _session


CBOE_BASE = "https://cdn.cboe.com/api/global/delayed_quotes/options"

# CBOE uses underscore prefix for indices
TICKER_MAP = {
    "SPX": "_SPX", "NDX": "_NDX", "RUT": "_RUT", "VIX": "_VIX",
    "SPY": "SPY", "QQQ": "QQQ", "IWM": "IWM", "AAPL": "AAPL",
    "TSLA": "TSLA", "NVDA": "NVDA", "AMZN": "AMZN", "MSFT": "MSFT",
    "META": "META", "GOOG": "GOOG", "AMD": "AMD",
}


def _fetch_cboe_chain(symbol: str) -> Dict:
    """Fetch raw options chain from CBOE. Raises HTTPException on failure."""
    cboe_ticker = TICKER_MAP.get(symbol.upper(), symbol.upper())
    url = f"{CBOE_BASE}/{cboe_ticker}.json"
    session = _get_session()

    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"CBOE options chain fetch failed for {symbol}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"CBOE options API error for {symbol}: {e}"
        )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class OptionFlow(BaseModel):
    """Most active option"""
    symbol: str
    strike: float
    expiration: str
    option_type: str = Field(..., description="CALL or PUT")
    volume: int
    open_interest: int
    last_price: float
    bid: float
    ask: float
    implied_volatility: Optional[float] = None


class UnusualActivity(BaseModel):
    """Unusual options activity"""
    symbol: str
    strike: float
    expiration: str
    option_type: str = Field(..., description="CALL or PUT")
    volume: int
    open_interest: int
    volume_oi_ratio: float
    last_price: float
    reason: str = Field(..., description="Why it's unusual")


class StrikeZone(BaseModel):
    """Call/Put accumulation zone"""
    strike: float
    expiration: str
    total_volume: int
    total_oi: int
    avg_price: float
    direction: str = Field(..., description="CALL or PUT")


class Sweep(BaseModel):
    """Options sweep"""
    symbol: str
    strike: float
    expiration: str
    option_type: str = Field(..., description="CALL or PUT")
    contracts: int
    premium: float
    timestamp: datetime


class OptionsFlowResponse(BaseModel):
    """Options flow response"""
    symbol: str
    most_active: List[OptionFlow] = Field(default_factory=list)
    unusual_activity: List[UnusualActivity] = Field(default_factory=list)
    call_put_ratio: float = Field(..., description="Call/Put volume ratio")
    accumulation_zones: Dict[str, List[StrikeZone]] = Field(
        default_factory=dict,
        description="calls and puts accumulation zones"
    )
    sweeps: List[Sweep] = Field(default_factory=list)
    source: str = "cboe"
    timestamp: datetime


# ---------------------------------------------------------------------------
# Routes — powered by CBOE free delayed options API
# ---------------------------------------------------------------------------

@router.get("/options/{symbol}/flow", response_model=OptionsFlowResponse)
async def get_options_flow(
    symbol: str,
    limit: int = Query(10, ge=1, le=50, description="Number of results per category"),
):
    """
    Get options flow data for a symbol from CBOE.

    Returns most active options (by volume), unusual activity (high vol/OI),
    P/C ratio, and accumulation zones — all from real CBOE delayed data.
    Raises HTTP 502/503 if CBOE is unavailable. Never returns mock data.
    """
    symbol = symbol.upper()
    raw = _fetch_cboe_chain(symbol)

    data = raw.get("data", {})
    spot = float(data.get("current_price", 0))
    options = data.get("options", [])

    if not options or not spot:
        raise HTTPException(
            status_code=404,
            detail=f"No options data available for {symbol} from CBOE"
        )

    # Parse all options into structured records
    parsed = []
    for o in options:
        opt_sym = o.get("option", "")
        if not opt_sym or len(opt_sym) < 10:
            continue

        volume = int(o.get("volume", 0) or 0)
        oi = int(o.get("open_interest", 0) or 0)
        last = float(o.get("last_trade_price", 0) or 0)
        bid = float(o.get("bid", 0) or 0)
        ask = float(o.get("ask", 0) or 0)
        iv = float(o.get("iv", 0) or 0)
        delta = float(o.get("delta", 0) or 0)

        # Parse strike from CBOE symbol (last 8 chars / 1000)
        try:
            strike = int(opt_sym[-8:]) / 1000
        except (ValueError, IndexError):
            continue

        # Determine call/put from delta sign (or symbol pattern)
        is_call = delta > 0
        option_type = "CALL" if is_call else "PUT"

        # Parse expiration from symbol (YYMMDD at positions after ticker)
        try:
            # OCC format: SYMBOL + YYMMDD + C/P + strike
            # Find the date portion
            ticker_end = len(opt_sym) - 15  # 6 date + 1 type + 8 strike
            if ticker_end > 0:
                date_str = opt_sym[ticker_end:ticker_end + 6]
                exp = f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"
            else:
                exp = ""
        except (ValueError, IndexError):
            exp = ""

        parsed.append({
            "symbol": symbol,
            "strike": strike,
            "expiration": exp,
            "option_type": option_type,
            "volume": volume,
            "open_interest": oi,
            "last_price": last,
            "bid": bid,
            "ask": ask,
            "iv": iv,
            "delta": delta,
        })

    if not parsed:
        raise HTTPException(
            status_code=404,
            detail=f"No valid options parsed for {symbol} from CBOE chain"
        )

    # ── Most Active (by volume) ──────────────────────────────────────────
    by_volume = sorted(parsed, key=lambda x: x["volume"], reverse=True)
    most_active = [
        OptionFlow(
            symbol=p["symbol"],
            strike=p["strike"],
            expiration=p["expiration"],
            option_type=p["option_type"],
            volume=p["volume"],
            open_interest=p["open_interest"],
            last_price=p["last_price"],
            bid=p["bid"],
            ask=p["ask"],
            implied_volatility=p["iv"] if p["iv"] else None,
        )
        for p in by_volume[:limit]
        if p["volume"] > 0
    ]

    # ── Unusual Activity (volume/OI > 1.5 threshold) ─────────────────────
    unusual = []
    for p in parsed:
        if p["open_interest"] < 100:
            continue  # skip illiquid
        ratio = p["volume"] / max(p["open_interest"], 1)
        if ratio > 1.5:
            reason = f"Vol/OI: {ratio:.1f}x"
            if ratio > 5:
                reason = f"Extreme vol/OI: {ratio:.1f}x (possible sweep)"
            elif ratio > 3:
                reason = f"High vol/OI: {ratio:.1f}x (unusual accumulation)"
            unusual.append(UnusualActivity(
                symbol=p["symbol"],
                strike=p["strike"],
                expiration=p["expiration"],
                option_type=p["option_type"],
                volume=p["volume"],
                open_interest=p["open_interest"],
                volume_oi_ratio=round(ratio, 2),
                last_price=p["last_price"],
                reason=reason,
            ))

    unusual.sort(key=lambda x: x.volume_oi_ratio, reverse=True)

    # ── Call/Put Volume Ratio ─────────────────────────────────────────────
    call_vol = sum(p["volume"] for p in parsed if p["option_type"] == "CALL")
    put_vol = sum(p["volume"] for p in parsed if p["option_type"] == "PUT")
    call_put_ratio = round(call_vol / max(put_vol, 1), 2)

    # ── Accumulation Zones ────────────────────────────────────────────────
    call_zones: Dict[str, Dict] = {}
    put_zones: Dict[str, Dict] = {}

    for p in parsed:
        key = f"{p['strike']}_{p['expiration']}"
        zones = call_zones if p["option_type"] == "CALL" else put_zones

        if key not in zones:
            zones[key] = {
                "strike": p["strike"],
                "expiration": p["expiration"],
                "total_volume": 0,
                "total_oi": 0,
                "total_premium": 0.0,
                "direction": p["option_type"],
            }
        zones[key]["total_volume"] += p["volume"]
        zones[key]["total_oi"] += p["open_interest"]
        zones[key]["total_premium"] += p["last_price"] * p["volume"]

    call_zone_list = sorted(call_zones.values(), key=lambda x: x["total_volume"], reverse=True)[:limit]
    put_zone_list = sorted(put_zones.values(), key=lambda x: x["total_volume"], reverse=True)[:limit]

    accumulation = {
        "calls": [
            StrikeZone(
                strike=z["strike"],
                expiration=z["expiration"],
                total_volume=z["total_volume"],
                total_oi=z["total_oi"],
                avg_price=round(z["total_premium"] / max(z["total_volume"], 1), 2),
                direction="CALL",
            ) for z in call_zone_list if z["total_volume"] > 0
        ],
        "puts": [
            StrikeZone(
                strike=z["strike"],
                expiration=z["expiration"],
                total_volume=z["total_volume"],
                total_oi=z["total_oi"],
                avg_price=round(z["total_premium"] / max(z["total_volume"], 1), 2),
                direction="PUT",
            ) for z in put_zone_list if z["total_volume"] > 0
        ],
    }

    return OptionsFlowResponse(
        symbol=symbol,
        most_active=most_active,
        unusual_activity=unusual[:limit],
        call_put_ratio=call_put_ratio,
        accumulation_zones=accumulation,
        sweeps=[],  # CBOE delayed data doesn't include real-time sweep detection
        source="cboe",
        timestamp=datetime.now(),
    )
