"""
AXLFI Dark Pool & Market Intelligence Client
(formerly Stockgrid — rebranded March 2026)

All endpoints discovered via Playwright network interception.
All data accessible via plain requests with browser-like headers.

Full API Surface:
  /api/dashboard/all           — 365KB master feed (movers, signals, strategy, VIX regime)
  /api/dark_pools/leaderboard  — 200 tickers by dark pool position
  /api/dark_pools/symbol       — per-ticker daily DP + short volume history
  /api/option_walls/data       — SPY/QQQ/IWM call/put walls + POC + expirations
  /api/option_walls/market_snapshot — current market summary
  /api/option_walls/symbols    — available option wall tickers
  /api/clusters/table          — 214KB universe (SP500, NASDAQ100, all)
  /api/symbols/info            — ticker metadata (price, sector, vol, 52w)
"""
import logging
import time
import json
import os
import requests
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


# ─── Data Models ────────────────────────────────────────────────────────────

@dataclass
class DarkPoolPosition:
    """A single ticker's dark pool summary."""
    ticker: str
    date: str = ""
    dp_position_shares: float = 0.0
    dp_position_dollars: float = 0.0
    net_short_volume: float = 0.0
    net_short_dollars: float = 0.0
    short_volume: float = 0.0
    short_volume_pct: float = 0.0
    company: str = ""
    sector: str = ""


@dataclass
class OptionWall:
    """Option wall levels for a given date."""
    date: str
    call_wall: float = 0.0
    call_wall_2: float = 0.0
    call_wall_3: float = 0.0
    put_wall: float = 0.0
    put_wall_2: float = 0.0
    put_wall_3: float = 0.0
    poc: float = 0.0


@dataclass
class DarkPoolSummary:
    """Combined dark pool intelligence."""
    top_positions: List[DarkPoolPosition] = field(default_factory=list)
    spy_detail: Optional[DarkPoolPosition] = None
    qqq_detail: Optional[DarkPoolPosition] = None
    timestamp: str = ""
    source: str = "axlfi.com (ex-stockgrid)"


# ─── AXLFI Client ──────────────────────────────────────────────────────────

class StockgridClient:
    """
    Dark pool flow + option wall + market intelligence from AXLFI.
    
    Uses plain requests with browser-like headers (no auth needed).
    """

    BASE = "https://axlfi.com/axlfi-app-backend/api"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://axlfi.com/dashboard",
        "Origin": "https://axlfi.com",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, cache_ttl: int = 300, max_retries: int = 3):
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}
        self._cache_ttl = cache_ttl
        self._max_retries = max_retries
        self._data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data")
        self._disk_cache_dir = "/tmp/axlfi_cache"
        os.makedirs(self._disk_cache_dir, exist_ok=True)
        logger.info("📊 StockgridClient initialized (AXLFI pure-requests mode, disk cache ON)")

    # ── Internal helpers ─────────────────────────────────────────────────

    def _is_cached(self, key: str) -> bool:
        return key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < self._cache_ttl

    def _set_cache(self, key: str, data: Any):
        self._cache[key] = data
        self._cache_ts[key] = time.time()

    def _disk_cache_key(self, path: str, params: dict = None) -> str:
        """Generate a safe filename for disk cache."""
        key = path.replace("/", "_").strip("_")
        if params:
            key += "_" + "_".join(f"{k}={v}" for k, v in sorted(params.items()))
        return key.replace(" ", "") + ".json"

    def _read_disk_cache(self, cache_file: str) -> Optional[dict]:
        """Read stale data from disk cache (last known good)."""
        try:
            fpath = os.path.join(self._disk_cache_dir, cache_file)
            if os.path.exists(fpath):
                with open(fpath) as f:
                    data = json.load(f)
                age = time.time() - os.path.getmtime(fpath)
                logger.info(f"📂 Disk cache hit: {cache_file} (age: {age:.0f}s)")
                return data
        except Exception as e:
            logger.warning(f"Disk cache read error: {e}")
        return None

    def _write_disk_cache(self, cache_file: str, data: Any):
        """Write successful response to disk cache."""
        try:
            fpath = os.path.join(self._disk_cache_dir, cache_file)
            with open(fpath, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Disk cache write error: {e}")

    def _get(self, path: str, params: dict = None) -> Optional[dict]:
        """Make a GET request with retries + disk-backed cache fallback."""
        url = f"{self.BASE}{path}"
        disk_key = self._disk_cache_key(path, params)

        for attempt in range(self._max_retries):
            try:
                r = requests.get(url, headers=self.HEADERS, params=params, timeout=25)
                if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
                    data = r.json()
                    self._write_disk_cache(disk_key, data)
                    return data
                logger.warning(f"⚠️ {path}: status={r.status_code} (attempt {attempt+1})")
            except Exception as e:
                logger.warning(f"⚠️ {path}: {e} (attempt {attempt+1})")
            time.sleep(2 * (attempt + 1))  # exponential backoff: 2s, 4s, 6s

        # All retries failed — fall back to disk cache (stale but better than None)
        logger.warning(f"⚠️ {path}: all {self._max_retries} retries failed, checking disk cache")
        return self._read_disk_cache(disk_key)

    def _save_to_disk(self, key: str, data: Any):
        try:
            os.makedirs(self._data_dir, exist_ok=True)
            with open(os.path.join(self._data_dir, f"axlfi_{key}.json"), "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    # ── Dark Pool Endpoints ──────────────────────────────────────────────

    def get_top_positions(self, limit: int = 200, sort_by: str = "Dark Pools Position $") -> List[DarkPoolPosition]:
        """Get top tickers by dark pool position (200 available)."""
        cache_key = f"leaderboard_{limit}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        data = self._get("/dark_pools/leaderboard", {
            "metric": "dark_pool_position_dollars",
            "sort": "desc",
            "limit": str(limit),
        })
        if not data:
            return []

        positions = []
        for item in data.get("data", []):
            positions.append(DarkPoolPosition(
                ticker=item.get("ticker", ""),
                date=item.get("date", data.get("as_of_date", "")),
                dp_position_shares=float(item.get("dp_position", 0) or 0),
                dp_position_dollars=float(item.get("dollar_dp_position", 0) or 0),
                net_short_volume=float(item.get("net_volume", 0) or 0),
                net_short_dollars=float(item.get("dollar_net_volume", 0) or 0),
                short_volume=float(item.get("short_volume", 0) or 0),
                short_volume_pct=float(item.get("short_volume_percent", 0) or 0),
                company=item.get("company", ""),
                sector=item.get("sector", ""),
            ))

        self._set_cache(cache_key, positions)
        return positions

    def get_ticker_detail(self, ticker: str = "SPY", window: int = 252) -> Optional["DarkPoolPosition"]:
        """
        Get latest dark pool position for a ticker.
        Returns a DarkPoolPosition dataclass (backward compatible with all consumers).
        Use get_ticker_detail_raw() for the full historical dict.
        """
        return self.get_ticker_latest(ticker)

    def get_ticker_detail_raw(self, ticker: str = "SPY", window: int = 252) -> Optional[dict]:
        """
        Get full dark pool history for a ticker.
        Returns raw dict with: individual_dark_pool_position_data, individual_short_volume_table,
        latest, prices, symbol.
        """
        cache_key = f"detail_raw_{ticker}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        data = self._get("/dark_pools/symbol", {"symbol": ticker, "window": str(window)})
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_ticker_latest(self, ticker: str) -> Optional[DarkPoolPosition]:
        """Get latest dark pool position for a single ticker."""
        data = self.get_ticker_detail_raw(ticker)
        if not data:
            return None

        dp = data.get("individual_dark_pool_position_data", {})
        dates = dp.get("dates", [])
        if not dates:
            return None

        dps = dp.get("dp_position", [])
        ddp = dp.get("dollar_dp_position", [])
        dnv = dp.get("dollar_net_volume", [])

        sv_items = []
        sv_raw = data.get("individual_short_volume_table", {})
        if isinstance(sv_raw, dict):
            sv_items = sv_raw.get("data", [])
        elif isinstance(sv_raw, list):
            sv_items = sv_raw

        sv_pct = 0.0
        sv_vol = 0.0
        # Sort by date to ensure [-1] picks the most recent row
        if sv_items:
            sv_items = sorted(sv_items, key=lambda x: x.get("date", "") if isinstance(x, dict) else "")
        if sv_items and isinstance(sv_items[-1], dict):
            last_sv = sv_items[-1]
            # API returns key as 'short_volume_pct' (already a %) or 'short_volume%' (ratio 0-1)
            raw_sv = float(last_sv.get("short_volume_pct",
                           last_sv.get("short_volume%",
                           last_sv.get("short_volume_percent", 0))) or 0)
            # If it's a ratio (0-1), convert to percentage; if already % (>1), keep as-is
            sv_pct = raw_sv if raw_sv > 1.0 else raw_sv * 100.0
            sv_vol = float(last_sv.get("short_volume", 0) or 0)

        # dollar_dp_position from per-ticker API is in millions ($36,811 = $36.8B)
        raw_ddp = float(ddp[-1] or 0) if ddp else 0
        dp_dollars = raw_ddp * 1e6 if abs(raw_ddp) < 1e6 else raw_ddp

        return DarkPoolPosition(
            ticker=ticker,
            date=dates[-1],
            dp_position_shares=float(dps[-1] or 0) if dps else 0,
            dp_position_dollars=dp_dollars,
            net_short_dollars=float(dnv[-1] or 0) if dnv else 0,
            short_volume=sv_vol,
            short_volume_pct=sv_pct,
        )

    # ── Option Walls ─────────────────────────────────────────────────────

    def get_option_walls(self, symbol: str = "SPY") -> Optional[dict]:
        """
        Get option wall data for SPY/QQQ/IWM.
        Returns: {as_of_date, expirations, option_minmax, option_walls, symbol}
        option_walls is keyed by date with call_wall, put_wall, poc, etc.
        """
        cache_key = f"walls_{symbol}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        data = self._get("/option_walls/data", {"symbol": symbol})
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_option_walls_today(self, symbol: str = "SPY") -> Optional[OptionWall]:
        """Get today's option wall levels."""
        data = self.get_option_walls(symbol)
        if not data:
            return None

        walls = data.get("option_walls", {})
        if not walls:
            return None

        # Get the most recent date
        latest_date = sorted(walls.keys())[-1] if walls else None
        if not latest_date:
            return None

        w = walls[latest_date]
        return OptionWall(
            date=latest_date,
            call_wall=float(w.get("call_wall", 0)),
            call_wall_2=float(w.get("call_wall_2", 0)),
            call_wall_3=float(w.get("call_wall_3", 0)),
            put_wall=float(w.get("put_wall", 0)),
            put_wall_2=float(w.get("put_wall_2", 0)),
            put_wall_3=float(w.get("put_wall_3", 0)),
            poc=float(w.get("poc", 0)),
        )

    def get_market_snapshot(self) -> Optional[dict]:
        """Get option walls market snapshot (SPY/QQQ/IWM current prices)."""
        return self._get("/option_walls/market_snapshot")

    # ── Dashboard / Strategy ─────────────────────────────────────────────

    def get_dashboard(self) -> Optional[dict]:
        """
        Get the master dashboard feed (365KB).
        Returns: index_returns, movers, signal_symbols, spy_history,
                 status, strategy_metrics, tactical_allocation
        """
        cache_key = "dashboard"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        data = self._get("/dashboard/all")
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_signal_symbols(self) -> List[dict]:
        """Get current signal symbols (from dashboard)."""
        dash = self.get_dashboard()
        if dash:
            return dash.get("signal_symbols", [])
        return []

    def get_volatility_regime(self) -> Optional[dict]:
        """Get current VIX climax / volatility regime."""
        dash = self.get_dashboard()
        if dash:
            # AXLFI returns this under "market_regime", NOT "volatility_regime"
            return dash.get("strategy_metrics", {}).get("market_regime")
        return None

    def get_movers(self) -> Optional[dict]:
        """Get today's market movers."""
        dash = self.get_dashboard()
        if dash:
            return dash.get("movers", {})
        return None

    # ── Cluster Universe ─────────────────────────────────────────────────

    def get_clusters(self) -> Optional[dict]:
        """Get cluster table (SP500, NASDAQ100, all universes)."""
        cache_key = "clusters"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        data = self._get("/clusters/table")
        if data:
            self._set_cache(cache_key, data)
        return data

    # ── Symbol Info ──────────────────────────────────────────────────────

    def get_symbol_info(self, ticker: str) -> Optional[dict]:
        """Get ticker metadata (price, sector, volatility, 52w range)."""
        return self._get("/symbols/info", {"symbol": ticker})

    # ── Summary/Narrative (backward compat) ──────────────────────────────

    def get_summary(self) -> DarkPoolSummary:
        """Get combined dark pool summary with SPY + QQQ detail."""
        top = self.get_top_positions(limit=10)
        spy = self.get_ticker_latest("SPY")
        qqq = self.get_ticker_latest("QQQ")
        return DarkPoolSummary(
            top_positions=top,
            spy_detail=spy,
            qqq_detail=qqq,
            timestamp=top[0].date if top else "",
        )

    def get_narrative(self) -> str:
        """Generate narrative-ready text for agents/systems."""
        try:
            summary = self.get_summary()
            parts = []
            if summary.spy_detail:
                s = summary.spy_detail
                parts.append(f"SPY DP: {s.dp_position_shares:,.0f} shares (${s.dp_position_dollars/1e9:.1f}B)")
            if summary.qqq_detail:
                q = summary.qqq_detail
                parts.append(f"QQQ DP: {q.dp_position_shares:,.0f} shares (${q.dp_position_dollars/1e9:.1f}B)")
            if summary.top_positions:
                top3 = [f"{p.ticker}(${p.dp_position_dollars/1e9:.1f}B)" for p in summary.top_positions[:3]]
                parts.append(f"Top: {', '.join(top3)}")
            return " | ".join(parts) if parts else "Dark pool data unavailable"
        except Exception as e:
            logger.error(f"❌ Narrative error: {e}")
            return "Dark pool data unavailable"

    # ── Earnings-Specific Intelligence ───────────────────────────────────

    def get_earnings_intel(self, tickers: List[str]) -> Dict[str, dict]:
        """
        Pull consolidated dark pool + option wall intelligence for earnings targets.
        Returns {ticker: {dp data, trend, option walls, info}} for each ticker.
        """
        intel = {}

        for ticker in tickers:
            detail = self.get_ticker_detail_raw(ticker)
            info = self.get_symbol_info(ticker)
            sym_info = info.get("symbol", {}) if info else {}

            if not detail:
                intel[ticker] = {"status": "no_data"}
                continue

            dp = detail.get("individual_dark_pool_position_data", {})
            dates = dp.get("dates", [])
            dps = dp.get("dp_position", [])
            ddp = dp.get("dollar_dp_position", [])
            dnv = dp.get("dollar_net_volume", [])

            sv_raw = detail.get("individual_short_volume_table", {})
            sv_items = sv_raw.get("data", []) if isinstance(sv_raw, dict) else sv_raw if isinstance(sv_raw, list) else []

            # 5-day trend
            trend = []
            for i in range(max(0, len(dates) - 5), len(dates)):
                trend.append({
                    "date": dates[i],
                    "shares": dps[i] if i < len(dps) else None,
                    "dollars": ddp[i] if i < len(ddp) else None,
                    "net_vol": dnv[i] if i < len(dnv) else None,
                })

            sv_pct = 0.0
            if sv_items:
                # Sort by date to ensure we get the newest row (table order is NOT guaranteed)
                sv_sorted = sorted([r for r in sv_items if isinstance(r, dict)],
                                   key=lambda x: x.get("date", ""), reverse=True)
                if sv_sorted:
                    newest = sv_sorted[0]
                    # API uses key 'short_volume_pct' and value is already a % (e.g. 46.11)
                    raw_sv = newest.get("short_volume_pct",
                             newest.get("short_volume%",
                             newest.get("short_volume_percent", 0)))
                    sv_pct = float(raw_sv or 0)
                    # Guard: if ratio (0-1) format, scale to percentage
                    if 0 < sv_pct <= 1.0:
                        sv_pct *= 100

            intel[ticker] = {
                "status": "live",
                "as_of": detail.get("as_of_date", ""),
                "close": sym_info.get("close"),
                "change_pct": sym_info.get("change_pct"),
                "company": sym_info.get("company", ""),
                "sector": sym_info.get("sector", ""),
                "industry": sym_info.get("industry", ""),
                "volatility": sym_info.get("volatility"),
                "52w_range": f"${sym_info.get('52_week_low','?')}-${sym_info.get('52_week_high','?')}",
                "latest_dp_shares": dps[-1] if dps else None,
                "latest_dp_dollars": ddp[-1] if ddp else None,
                "latest_net_vol": dnv[-1] if dnv else None,
                "short_volume_pct": sv_pct,
                "trend_5d": trend,
            }

        # Add option walls for SPY/QQQ context
        for sym in ["SPY", "QQQ"]:
            wall = self.get_option_walls_today(sym)
            if wall:
                intel[f"{sym}_walls"] = {
                    "date": wall.date,
                    "call_wall": wall.call_wall,
                    "put_wall": wall.put_wall,
                    "poc": wall.poc,
                }

        # Add volatility regime
        regime = self.get_volatility_regime()
        if regime:
            intel["_regime"] = regime

        # Add signal symbols
        signals = self.get_signal_symbols()
        if signals:
            intel["_signals"] = signals

        return intel


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = StockgridClient()

    print("=" * 60)
    print("🐺 AXLFI Market Intelligence — Full Test")
    print("=" * 60)

    # Earnings targets
    intel = client.get_earnings_intel(["ADBE", "ORCL", "LEN"])
    for key, data in intel.items():
        if key.startswith("_"):
            continue
        print(f"\n{'─'*50}")
        if "_walls" in key:
            print(f"  📊 {key}: call={data['call_wall']} put={data['put_wall']} poc={data['poc']}")
        elif data.get("status") == "live":
            print(f"  🎯 {key}: ${data.get('close')} ({data.get('change_pct')}%)")
            print(f"     {data.get('company')} | {data.get('sector')}")
            s = data.get("latest_dp_shares")
            if s: print(f"     DP Shares: {s:>12,.0f}")
            print(f"     SV%: {data.get('short_volume_pct',0):.1f}%")
            for d in data.get("trend_5d", []):
                shares = d.get("shares", 0) or 0
                print(f"       {d['date']}: {shares:>12,.0f} shares")

    # Regime
    regime = intel.get("_regime", {})
    print(f"\n  ⚡ VIX Regime: {regime.get('tier_label', '?')} (level {regime.get('current_regime', '?')})")

    # Signals
    signals = intel.get("_signals", [])
    if signals:
        tickers = [s["symbol"] for s in signals if s.get("dir") == 1]
        print(f"  📡 Bullish Signals: {', '.join(tickers)}")


# ─── Backward Compatibility Aliases ─────────────────────────────────────────

# dp_snapshot_recorder.py imports StockGridClient (capital G)
StockGridClient = StockgridClient
