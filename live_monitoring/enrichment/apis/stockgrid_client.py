"""
AXLFI Dark Pool & Market Intelligence Client
(formerly Stockgrid — rebranded March 2026; API moved again Nov 2026)

Nov 2026 surface (current) — BASE https://axlfi.com/api
  PUBLIC (live 200 without cookie):
    GET /options/walls?ticker=SPY
    GET /market/movers | /market/volatility | /market/update
    GET /market/sectors | /market/themes | /market/breadth | /market/members
    GET /short-interest/ticker?ticker=SPY | /short-interest/leaderboard
    GET /short-interest/fails | /short-interest/fails/ticker?ticker= (may 500 → None)
    GET /clusters/scan | /clusters/stock/{ticker}
    GET /congress/trades | /congress/activity
    GET /earnings/upcoming | /earnings/ticker?ticker=
    GET /leadership | /search/tickers?q=
    GET /institutions/overview | /institutions/ticker?ticker=
    GET /events/overview
    GET /breadth/signals
    GET /contracts/overview | /contracts/ticker?ticker=
  PRO-gated (403 without cookie → fail-closed / PAYWALL_FALLBACK — NOT SELLABLE):
    GET /darkpools/leaderboard (metric=position_usd)
    GET /darkpools/ticker?ticker=SPY&window=252
    GET /darkpools/sectors
    GET /insiders/overview | /insiders/ticker?ticker=
  Do NOT wire Bearer auth (auth probe CLOSED). Cookie header only when env set.

Legacy `axlfi-app-backend/api/*` routes return the Nuxt HTML shell — DEAD. Do not use.
"""
from __future__ import annotations

import logging
import time
import json
import os
from live_monitoring.enrichment.apis._http import get_session
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from urllib.parse import urlencode

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
    Dark pool flow + option wall + market intelligence from AXLFI v2 API.
    """

    BASE = "https://axlfi.com/api"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://axlfi.com/darkpools",
        "Origin": "https://axlfi.com",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, cache_ttl: int = 300, max_retries: int = 2):
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}
        self._cache_ttl = cache_ttl
        self._max_retries = max_retries
        self._data_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data"
        )
        self._disk_cache_dir = "/tmp/axlfi_cache"
        os.makedirs(self._disk_cache_dir, exist_ok=True)
        self._repo_cache_path = os.path.join(self._data_dir, "axlfi_v2_live_cache.json")
        self._repo_cache: Optional[dict] = None
        # Last HTTP fetch provenance for honesty labels (LIVE vs PAYWALL_FALLBACK).
        self.last_fetch_meta: Dict[str, Any] = {
            "path": None,
            "http_status": None,
            "source": None,  # live | browser | disk | repo | legacy | none
            "paywall": False,
            "base": self.BASE,
        }
        logger.info("📊 StockgridClient initialized (AXLFI v2 API + disk/repo cache)")

    # ── Internal helpers ─────────────────────────────────────────────────

    @staticmethod
    def _session_cookie() -> Optional[str]:
        """
        Optional Pro session cookie for /darkpools/* (Cookie header).
        Prefer AXLFI_SESSION_COOKIE; fall back to AXLFI_PRO_COOKIE.
        Empty / unset → no Cookie header (bare requests stay paywalled).
        """
        for key in ("AXLFI_SESSION_COOKIE", "AXLFI_PRO_COOKIE"):
            val = (os.environ.get(key) or "").strip()
            if val:
                return val
        return None

    def _request_headers(self) -> Dict[str, str]:
        """Browser headers + optional Pro Cookie when env is set."""
        headers = dict(self.HEADERS)
        cookie = self._session_cookie()
        if cookie:
            headers["Cookie"] = cookie
        return headers

    def _is_cached(self, key: str) -> bool:
        return key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < self._cache_ttl

    def _set_cache(self, key: str, data: Any):
        self._cache[key] = data
        self._cache_ts[key] = time.time()

    def _disk_cache_key(self, path: str, params: dict = None) -> str:
        key = path.replace("/", "_").strip("_")
        if params:
            key += "_" + "_".join(f"{k}={v}" for k, v in sorted(params.items()))
        return key.replace(" ", "") + ".json"

    def _read_disk_cache(self, cache_file: str) -> Optional[dict]:
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
        try:
            fpath = os.path.join(self._disk_cache_dir, cache_file)
            with open(fpath, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Disk cache write error: {e}")

    def _load_repo_cache(self) -> dict:
        if self._repo_cache is not None:
            return self._repo_cache
        try:
            if os.path.exists(self._repo_cache_path):
                with open(self._repo_cache_path) as f:
                    self._repo_cache = json.load(f)
                    logger.info(
                        "📂 Loaded repo AXLFI v2 cache (%s keys)",
                        len([k for k in self._repo_cache if str(k).startswith("http")]),
                    )
                    return self._repo_cache
        except Exception as e:
            logger.warning(f"Repo cache load failed: {e}")
        self._repo_cache = {}
        return self._repo_cache

    def _repo_cache_lookup(self, path: str, params: dict = None) -> Optional[dict]:
        """Match a repo-bundled URL for path+params (best-effort)."""
        bundle = self._load_repo_cache()
        if not bundle:
            return None
        query = f"?{urlencode(params)}" if params else ""
        target_suffix = f"{path}{query}"
        # Exact / suffix match
        for url, body in bundle.items():
            if not isinstance(url, str) or not isinstance(body, dict):
                continue
            if url.endswith(target_suffix) or target_suffix in url:
                # Prefer non-empty payload
                if body.get("detail"):
                    continue
                logger.info(f"📂 Repo cache hit for {path}")
                return body
        # Soft match by resource family
        if path.startswith("/darkpools/ticker") and params and params.get("ticker"):
            ticker = str(params["ticker"]).upper()
            for url, body in bundle.items():
                if (
                    isinstance(body, dict)
                    and body.get("ticker") == ticker
                    and isinstance(body.get("points"), list)
                    and body["points"]
                ):
                    logger.info(f"📂 Repo cache soft-hit ticker={ticker}")
                    return body
        if path.startswith("/options/walls") and params and params.get("ticker"):
            ticker = str(params["ticker"]).upper()
            for url, body in bundle.items():
                if isinstance(body, dict) and body.get("ticker") == ticker and body.get("expiries"):
                    logger.info(f"📂 Repo cache soft-hit walls={ticker}")
                    return body
        if path.startswith("/darkpools/leaderboard"):
            for url, body in bundle.items():
                if isinstance(body, dict) and isinstance(body.get("rows"), list) and body["rows"]:
                    logger.info("📂 Repo cache soft-hit leaderboard")
                    return body
        return None

    def _browser_get(self, path: str, params: dict = None) -> Optional[dict]:
        """
        Optional Playwright capture for Pro-gated dark-pool routes.
        Returns None if Playwright unavailable or capture fails.
        """
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            return None

        query = f"?{urlencode(params)}" if params else ""
        full = f"{self.BASE}{path}{query}"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=self.HEADERS["User-Agent"])
                page = context.new_page()
                hit: Dict[str, Any] = {"body": None}

                def on_response(response):
                    if response.url.split("?")[0] != full.split("?")[0]:
                        # match path family for ticker/leaderboard
                        if path not in response.url:
                            return
                    try:
                        ct = response.headers.get("content-type", "")
                        if response.status == 200 and "json" in ct:
                            body = response.json()
                            if isinstance(body, dict) and not body.get("detail"):
                                hit["body"] = body
                    except Exception:
                        pass

                page.on("response", on_response)
                # Warm page so free-visit darkpool XHRs fire
                warm = "https://axlfi.com/darkpools" if "darkpools" in path else "https://axlfi.com/option-walls"
                page.goto(warm, wait_until="networkidle", timeout=45000)
                time.sleep(1.5)
                # Direct in-page fetch (works for public walls; DP may 403 after free visit)
                try:
                    direct = page.evaluate(
                        """async (url) => {
                            const r = await fetch(url, {headers:{Accept:'application/json'}});
                            const ct = r.headers.get('content-type') || '';
                            const text = await r.text();
                            return {status:r.status, ct, text};
                        }""",
                        full,
                    )
                    if (
                        direct
                        and direct.get("status") == 200
                        and "json" in (direct.get("ct") or "")
                    ):
                        body = json.loads(direct["text"])
                        if isinstance(body, dict) and not body.get("detail"):
                            hit["body"] = body
                except Exception as e:
                    logger.debug(f"browser direct fetch failed: {e}")
                browser.close()
                if hit["body"]:
                    logger.info(f"🌐 Playwright AXLFI hit: {path}")
                return hit["body"]
        except Exception as e:
            logger.warning(f"Playwright AXLFI fetch failed for {path}: {e}")
            return None

    def _get(self, path: str, params: dict = None) -> Optional[dict]:
        """GET with retries → Playwright (optional) → disk → repo cache."""
        url = f"{self.BASE}{path}"
        disk_key = self._disk_cache_key(path, params)
        last_status: Optional[int] = None
        saw_paywall = False

        for attempt in range(self._max_retries):
            try:
                r = get_session().get(url, headers=self._request_headers(), params=params, timeout=25)
                ct = r.headers.get("content-type", "")
                last_status = r.status_code
                if r.status_code == 200 and "json" in ct:
                    data = r.json()
                    if isinstance(data, dict) and data.get("detail"):
                        detail = str(data.get("detail") or "")
                        if "pro" in detail.lower():
                            saw_paywall = True
                        logger.warning(f"⚠️ {path}: API detail={data.get('detail')} (attempt {attempt+1})")
                    else:
                        self._write_disk_cache(disk_key, data)
                        self.last_fetch_meta = {
                            "path": path,
                            "http_status": 200,
                            "source": "live",
                            "paywall": False,
                            "base": self.BASE,
                        }
                        return data
                elif r.status_code == 403:
                    saw_paywall = True
                    try:
                        detail = r.json().get("detail", "")
                        if "pro" in str(detail).lower():
                            saw_paywall = True
                    except Exception:
                        pass
                    logger.warning(f"⚠️ {path}: status=403 (attempt {attempt+1})")
                    # Pro paywall will not clear on retry — fall through to cache immediately
                    if saw_paywall:
                        break
                elif "html" in ct:
                    logger.warning(f"⚠️ {path}: HTML shell (legacy route dead) attempt {attempt+1}")
                else:
                    logger.warning(f"⚠️ {path}: status={r.status_code} (attempt {attempt+1})")
            except Exception as e:
                logger.warning(f"⚠️ {path}: {e} (attempt {attempt+1})")
            time.sleep(1 * (attempt + 1))

        # Pro-gated darkpools: try browser once
        if path.startswith("/darkpools/"):
            browser_data = self._browser_get(path, params)
            if browser_data:
                self._write_disk_cache(disk_key, browser_data)
                self.last_fetch_meta = {
                    "path": path,
                    "http_status": last_status,
                    "source": "browser",
                    "paywall": saw_paywall,
                    "base": self.BASE,
                }
                return browser_data

        disk = self._read_disk_cache(disk_key)
        if disk:
            self.last_fetch_meta = {
                "path": path,
                "http_status": last_status,
                "source": "disk",
                "paywall": saw_paywall or (last_status == 403),
                "base": self.BASE,
            }
            return disk

        repo = self._repo_cache_lookup(path, params)
        if repo:
            self.last_fetch_meta = {
                "path": path,
                "http_status": last_status,
                "source": "repo",
                "paywall": saw_paywall or (last_status == 403),
                "base": self.BASE,
            }
            return repo

        # Last resort: existing production dump used by dp_bearish_checker / synthesis
        legacy = self._legacy_live_file_lookup(path, params)
        self.last_fetch_meta = {
            "path": path,
            "http_status": last_status,
            "source": "legacy" if legacy else "none",
            "paywall": saw_paywall or (last_status == 403),
            "base": self.BASE,
        }
        return legacy

    def _legacy_live_file_lookup(self, path: str, params: dict = None) -> Optional[dict]:
        """
        Serve data/axlfi_dark_pool_live.json when live AXLFI + disk/repo caches miss.
        File is URL-keyed legacy payloads already consumed elsewhere in the repo.
        """
        legacy_path = os.path.join(self._data_dir, "axlfi_dark_pool_live.json")
        if not os.path.exists(legacy_path):
            return None
        try:
            with open(legacy_path) as f:
                bundle = json.load(f)
        except Exception as e:
            logger.warning(f"Legacy axlfi_dark_pool_live.json load failed: {e}")
            return None

        params = params or {}
        # Per-ticker: match symbol=SPY (legacy) or ticker=SPY (v2) keys
        if path.startswith("/darkpools/ticker"):
            ticker = str(params.get("ticker") or "").upper()
            if not ticker:
                return None
            for url, body in bundle.items():
                if not isinstance(body, dict):
                    continue
                u = str(url)
                if f"symbol={ticker}" in u or f"ticker={ticker}" in u:
                    if "individual_dark_pool_position_data" in body or body.get("points"):
                        logger.info(f"📂 Legacy live-file hit ticker={ticker}")
                        return body
            # Also accept dp_SPY style keys written by some dumpers
            for key in (f"dp_{ticker}", ticker):
                body = bundle.get(key)
                if isinstance(body, dict) and (
                    "individual_dark_pool_position_data" in body or body.get("points")
                ):
                    logger.info(f"📂 Legacy live-file soft-hit key={key}")
                    return body
            return None

        if path.startswith("/darkpools/leaderboard"):
            for url, body in bundle.items():
                if not isinstance(body, dict):
                    continue
                if "leaderboard" in str(url) and (
                    isinstance(body.get("data"), list) or isinstance(body.get("rows"), list)
                ):
                    logger.info("📂 Legacy live-file hit leaderboard")
                    return body
        return None

    # ── Schema adapters (v2 → legacy consumer shapes) ─────────────────────

    @staticmethod
    def _normalize_ticker_payload(data: dict) -> dict:
        """
        Convert AXLFI v2 /darkpools/ticker payload into the legacy shape
        expected by DarkPoolTrend / darkpool_source / earnings intel.
        """
        if not data:
            return {}
        # Already legacy?
        if "individual_dark_pool_position_data" in data:
            return data

        points = data.get("points") or []
        summary = data.get("summary") or {}
        dates, dps, ddp, dnv, prices = [], [], [], [], []
        sv_rows = []
        for p in points:
            if not isinstance(p, dict):
                continue
            d = p.get("d") or p.get("date") or ""
            dates.append(d)
            # Consumers treat dp_position as the trendable series — use $ position.
            pos = float(p.get("position_usd") or p.get("dp_position") or 0)
            dps.append(pos)
            ddp.append(pos)
            dnv.append(float(p.get("net_usd") or p.get("dollar_net_volume") or 0))
            prices.append(float(p.get("close") or 0))
            sv_rows.append(
                {
                    "date": d,
                    "short_volume": float(p.get("short_volume") or 0),
                    "short_exempt_volume": float(p.get("short_exempt_volume") or 0),
                    "total_volume": float(p.get("total_volume") or 0),
                    "short_volume_pct": float(p.get("short_pct") or 0),
                    "net_short_volume": float(p.get("net_volume") or 0),
                }
            )

        return {
            "as_of_date": data.get("as_of") or (dates[-1] if dates else ""),
            "symbol": data.get("ticker") or data.get("symbol") or "",
            "state": data.get("state"),
            "summary": summary,
            "individual_dark_pool_position_data": {
                "dates": dates,
                "dp_position": dps,
                "dollar_dp_position": ddp,
                "dollar_net_volume": dnv,
            },
            "individual_short_volume_table": {"data": sv_rows},
            "individual_short_volume": {
                "dates": dates,
                "short_volume": [r["short_volume"] for r in sv_rows],
                "total_volume": [r["total_volume"] for r in sv_rows],
            },
            "prices": {"dates": dates, "prices": prices, "close": prices},
            "latest": {
                "date": dates[-1] if dates else "",
                "dp_position_dollars": dps[-1] if dps else 0,
                "short_volume_pct": sv_rows[-1]["short_volume_pct"] if sv_rows else 0,
                "net_short_dollars": dnv[-1] if dnv else 0,
                "close": prices[-1] if prices else 0,
            },
            "_source": "axlfi_v2",
            "_raw": data,
        }

    @staticmethod
    def _normalize_walls_payload(data: dict) -> dict:
        """
        Convert AXLFI v2 /options/walls into legacy option_walls keyed-by-date shape.
        """
        if not data:
            return {}
        if "option_walls" in data and isinstance(data.get("option_walls"), dict):
            return data

        expiries = data.get("expiries") or []
        option_walls: Dict[str, dict] = {}
        for exp in expiries:
            if not isinstance(exp, dict):
                continue
            d = exp.get("d") or exp.get("date")
            walls = exp.get("walls") or {}
            call_walls = walls.get("call_walls") or [0, 0, 0]
            put_walls = walls.get("put_walls") or [0, 0, 0]
            # pad
            while len(call_walls) < 3:
                call_walls.append(0)
            while len(put_walls) < 3:
                put_walls.append(0)
            option_walls[str(d)] = {
                "call_wall": float(call_walls[0] or 0),
                "call_wall_2": float(call_walls[1] or 0),
                "call_wall_3": float(call_walls[2] or 0),
                "put_wall": float(put_walls[0] or 0),
                "put_wall_2": float(put_walls[1] or 0),
                "put_wall_3": float(put_walls[2] or 0),
                "poc": float(walls.get("peak") or call_walls[0] or 0),
                "call_total": walls.get("call_total"),
                "put_total": walls.get("put_total"),
                "balance_pct": walls.get("balance_pct"),
            }

        return {
            "as_of_date": data.get("as_of"),
            "symbol": data.get("ticker"),
            "spot": data.get("spot"),
            "spot_change_pct": data.get("spot_change_pct"),
            "expirations": [e.get("d") for e in expiries if isinstance(e, dict)],
            "option_walls": option_walls,
            "option_minmax": {
                "calls": [
                    (option_walls[d]["call_wall"] if d in option_walls else None)
                    for d in sorted(option_walls.keys())
                ],
                "puts": [
                    (option_walls[d]["put_wall"] if d in option_walls else None)
                    for d in sorted(option_walls.keys())
                ],
            },
            "strikes": data.get("strikes"),
            "_source": "axlfi_v2",
            "_raw": data,
        }

    # ── Dark Pool Endpoints ──────────────────────────────────────────────

    def get_top_positions(self, limit: int = 200, sort_by: str = "Dark Pools Position $") -> List[DarkPoolPosition]:
        """Get top tickers by dark pool position."""
        cache_key = f"leaderboard_{limit}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        data = self._get(
            "/darkpools/leaderboard",
            {
                "metric": "position_usd",
                "sort": "desc",
                "universe": "us_large_cap_500",
                "limit": str(min(limit, 200)),
            },
        )
        if not data:
            return []

        rows = data.get("rows") or data.get("data") or []
        positions = []
        for item in rows[:limit]:
            if not isinstance(item, dict):
                continue
            # v2 fields: position_usd, short_pct, net_usd
            positions.append(
                DarkPoolPosition(
                    ticker=item.get("ticker", ""),
                    date=item.get("date", data.get("as_of") or data.get("as_of_date", "")),
                    dp_position_shares=float(item.get("dp_position") or 0),
                    dp_position_dollars=float(
                        item.get("position_usd")
                        or item.get("dollar_dp_position")
                        or 0
                    ),
                    net_short_volume=float(item.get("net_volume") or 0),
                    net_short_dollars=float(item.get("net_usd") or item.get("dollar_net_volume") or 0),
                    short_volume=float(item.get("short_volume") or 0),
                    short_volume_pct=float(
                        item.get("short_pct") or item.get("short_volume_percent") or 0
                    ),
                    company=item.get("name") or item.get("company") or "",
                    sector=item.get("sector") or "",
                )
            )

        self._set_cache(cache_key, positions)
        return positions

    def get_ticker_detail(self, ticker: str = "SPY", window: int = 252) -> Optional["DarkPoolPosition"]:
        return self.get_ticker_latest(ticker)

    def get_ticker_detail_raw(self, ticker: str = "SPY", window: int = 252) -> Optional[dict]:
        cache_key = f"detail_raw_{ticker}_{window}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        data = self._get(
            "/darkpools/ticker",
            {"ticker": ticker.upper(), "window": str(window)},
        )
        if not data:
            return None
        normalized = self._normalize_ticker_payload(data)
        self._set_cache(cache_key, normalized)
        return normalized

    def get_ticker_latest(self, ticker: str) -> Optional[DarkPoolPosition]:
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
        if sv_items:
            sv_items = sorted(
                sv_items, key=lambda x: x.get("date", "") if isinstance(x, dict) else ""
            )
        if sv_items and isinstance(sv_items[-1], dict):
            last_sv = sv_items[-1]
            raw_sv = float(
                last_sv.get(
                    "short_volume_pct",
                    last_sv.get("short_volume%", last_sv.get("short_volume_percent", 0)),
                )
                or 0
            )
            sv_pct = raw_sv if raw_sv > 1.0 else raw_sv * 100.0
            sv_vol = float(last_sv.get("short_volume", 0) or 0)

        raw_ddp = float(ddp[-1] or 0) if ddp else 0
        # v2 already stores full USD; legacy sometimes used millions
        dp_dollars = raw_ddp * 1e6 if 0 < abs(raw_ddp) < 1e6 else raw_ddp

        net_vol = 0.0
        if sv_items and isinstance(sv_items[-1], dict):
            net_vol = float(sv_items[-1].get("net_short_volume") or 0)
        return DarkPoolPosition(
            ticker=ticker.upper(),
            date=dates[-1],
            dp_position_shares=float(dps[-1] or 0) if dps else 0,
            dp_position_dollars=dp_dollars,
            net_short_volume=net_vol,
            net_short_dollars=float(dnv[-1] or 0) if dnv else 0,
            short_volume=sv_vol,
            short_volume_pct=sv_pct,
        )

    def get_darkpool_sectors(self) -> Optional[dict]:
        """
        Pro-gated sector dark-pool aggregate.
        403 / paywall → None (fail-closed). Never invent sector DP numbers.
        """
        cache_key = "darkpool_sectors"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/darkpools/sectors")
        if not data:
            return None
        if self.last_fetch_meta.get("paywall") or self.last_fetch_meta.get("http_status") == 403:
            return None
        self._set_cache(cache_key, data)
        return data

    # ── Option Walls ─────────────────────────────────────────────────────

    def get_option_walls(self, symbol: str = "SPY") -> Optional[dict]:
        cache_key = f"walls_{symbol}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        data = self._get("/options/walls", {"ticker": symbol.upper()})
        if not data:
            return None
        normalized = self._normalize_walls_payload(data)
        self._set_cache(cache_key, normalized)
        return normalized

    def get_option_walls_today(self, symbol: str = "SPY") -> Optional[OptionWall]:
        data = self.get_option_walls(symbol)
        if not data:
            return None

        walls = data.get("option_walls", {})
        if not walls:
            return None

        latest_date = sorted(walls.keys())[0] if walls else None  # nearest expiry first chronologically
        # Prefer soonest dated expiry (>= today-ish): sorted ascending
        if not latest_date:
            return None
        # Use nearest expiry (smallest date string among future/near)
        nearest = sorted(walls.keys())[0]
        w = walls[nearest]
        return OptionWall(
            date=nearest,
            call_wall=float(w.get("call_wall", 0) or 0),
            call_wall_2=float(w.get("call_wall_2", 0) or 0),
            call_wall_3=float(w.get("call_wall_3", 0) or 0),
            put_wall=float(w.get("put_wall", 0) or 0),
            put_wall_2=float(w.get("put_wall_2", 0) or 0),
            put_wall_3=float(w.get("put_wall_3", 0) or 0),
            poc=float(w.get("poc", 0) or 0),
        )

    def get_market_snapshot(self) -> Optional[dict]:
        """Build SPY/QQQ/IWM snapshot from public option-walls endpoints."""
        snap = {}
        for sym in ("SPY", "QQQ", "IWM"):
            walls = self.get_option_walls(sym)
            if walls and walls.get("spot") is not None:
                snap[sym] = {
                    "close": walls.get("spot"),
                    "change_pct": walls.get("spot_change_pct"),
                    "as_of": walls.get("as_of_date"),
                }
        if not snap:
            return None
        return {"market_snapshot": snap, "symbols": list(snap.keys())}

    # ── Dashboard / Strategy ─────────────────────────────────────────────

    def get_dashboard(self) -> Optional[dict]:
        """Best-effort dashboard from public market endpoints (v2 has no /dashboard/all)."""
        cache_key = "dashboard"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        movers = self._get("/market/movers") or {}
        snap = self.get_market_snapshot() or {}
        data = {
            "movers": movers,
            "signal_symbols": [],  # Pro/legacy — unavailable on free v2 surface
            "strategy_metrics": {"market_regime": None},
            "market_snapshot": snap.get("market_snapshot"),
            "_source": "axlfi_v2_public",
        }
        self._set_cache(cache_key, data)
        return data

    def get_signal_symbols(self) -> List[dict]:
        dash = self.get_dashboard()
        if dash:
            return dash.get("signal_symbols", []) or []
        return []

    def get_volatility_regime(self) -> Optional[dict]:
        dash = self.get_dashboard()
        if dash:
            return dash.get("strategy_metrics", {}).get("market_regime")
        return None

    def get_movers(self) -> Optional[dict]:
        dash = self.get_dashboard()
        if dash:
            return dash.get("movers", {})
        return self._get("/market/movers")

    def get_market_volatility(self, ticker: str = "SPY") -> Optional[dict]:
        """PUBLIC — realized vol windows for a ticker."""
        cache_key = f"market_vol_{ticker.upper()}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/market/volatility", {"ticker": ticker.upper()})
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_market_update(self) -> Optional[dict]:
        """PUBLIC — narrative/recap market update feed."""
        cache_key = "market_update"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/market/update")
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_market_sectors(self) -> Optional[list]:
        """PUBLIC — sector performance list."""
        cache_key = "market_sectors"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/market/sectors")
        if data is None:
            return None
        rows = data if isinstance(data, list) else data.get("rows") or data.get("sectors") or []
        self._set_cache(cache_key, rows)
        return rows

    def get_market_themes(self) -> Optional[list]:
        """PUBLIC — thematic baskets."""
        cache_key = "market_themes"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/market/themes")
        if data is None:
            return None
        rows = data if isinstance(data, list) else data.get("rows") or data.get("themes") or []
        self._set_cache(cache_key, rows)
        return rows

    def get_market_breadth(self) -> Optional[dict]:
        """PUBLIC — market breadth (% above MAs, adv/dec, etc.)."""
        cache_key = "market_breadth"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/market/breadth")
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_leadership(self) -> Optional[dict]:
        """PUBLIC — leadership screen."""
        cache_key = "leadership"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/leadership")
        if data:
            self._set_cache(cache_key, data)
        return data

    # ── Short Interest (PUBLIC) ──────────────────────────────────────────

    def get_short_interest_ticker(self, ticker: str = "SPY") -> Optional[dict]:
        """PUBLIC — short-interest history for a ticker (not Pro darkpools)."""
        cache_key = f"si_ticker_{ticker.upper()}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/short-interest/ticker", {"ticker": ticker.upper()})
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_short_interest_leaderboard(self) -> Optional[dict]:
        """PUBLIC — short-interest leaderboard."""
        cache_key = "si_leaderboard"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/short-interest/leaderboard")
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_short_interest_fails(self) -> Optional[dict]:
        """PUBLIC — short-interest fails overview (no cookie required)."""
        cache_key = "si_fails"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/short-interest/fails")
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_short_interest_fails_ticker(self, ticker: str = "SPY") -> Optional[dict]:
        """
        PUBLIC — short-interest fails for a ticker.
        Upstream may 500; fail-closed → None (never invent fails data).
        """
        t = ticker.upper()
        cache_key = f"si_fails_ticker_{t}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/short-interest/fails/ticker", {"ticker": t})
        if not data:
            return None
        # Non-200 / empty upstream → already None; refuse paywall bleed
        if self.last_fetch_meta.get("http_status") not in (None, 200):
            return None
        self._set_cache(cache_key, data)
        return data

    # ── Institutions / Events / Breadth / Contracts (PUBLIC) ─────────────

    def get_institutions_overview(self) -> Optional[dict]:
        """PUBLIC — institutions overview (live 200 without cookie)."""
        cache_key = "institutions_overview"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/institutions/overview")
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_institutions_ticker(self, ticker: str = "SPY") -> Optional[dict]:
        """PUBLIC — institutions positioning for a ticker."""
        t = ticker.upper()
        cache_key = f"institutions_ticker_{t}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/institutions/ticker", {"ticker": t})
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_events_overview(self) -> Optional[dict]:
        """PUBLIC — events overview calendar / catalysts."""
        cache_key = "events_overview"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/events/overview")
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_breadth_signals(self) -> Optional[dict]:
        """PUBLIC — breadth signals feed."""
        cache_key = "breadth_signals"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/breadth/signals")
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_contracts_overview(self) -> Optional[dict]:
        """PUBLIC — contracts overview."""
        cache_key = "contracts_overview"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/contracts/overview")
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_contracts_ticker(self, ticker: str = "SPY") -> Optional[dict]:
        """PUBLIC — contracts for a ticker."""
        t = ticker.upper()
        cache_key = f"contracts_ticker_{t}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/contracts/ticker", {"ticker": t})
        if data:
            self._set_cache(cache_key, data)
        return data

    # ── Insiders (PRO — fail-closed / PAYWALL_FALLBACK) ───────────────────

    def get_insiders_overview(self) -> Optional[dict]:
        """
        PRO-gated insiders overview.
        403 / paywall → None (PAYWALL_FALLBACK). Never invent insider data.
        """
        cache_key = "insiders_overview"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/insiders/overview")
        if not data:
            return None
        if self.last_fetch_meta.get("paywall") or self.last_fetch_meta.get("http_status") == 403:
            return None
        self._set_cache(cache_key, data)
        return data

    def get_insiders_ticker(self, ticker: str = "SPY") -> Optional[dict]:
        """
        PRO-gated insiders for a ticker.
        403 / paywall → None (PAYWALL_FALLBACK). Never invent insider data.
        """
        t = ticker.upper()
        cache_key = f"insiders_ticker_{t}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/insiders/ticker", {"ticker": t})
        if not data:
            return None
        if self.last_fetch_meta.get("paywall") or self.last_fetch_meta.get("http_status") == 403:
            return None
        self._set_cache(cache_key, data)
        return data

    # ── Clusters (PUBLIC) ────────────────────────────────────────────────

    def get_clusters(self) -> Optional[dict]:
        cache_key = "clusters"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        # Prefer live scan; fall back to members universe
        data = self._get("/clusters/scan")
        if not data:
            data = self._get("/market/members", {"universe": "us_large_cap_500"})
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_clusters_scan(self) -> Optional[dict]:
        """PUBLIC — cluster scan table + regime stats."""
        cache_key = "clusters_scan"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/clusters/scan")
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_cluster_stock(self, ticker: str) -> Optional[dict]:
        """PUBLIC — per-ticker cluster membership / horizons."""
        t = ticker.upper()
        cache_key = f"cluster_stock_{t}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get(f"/clusters/stock/{t}")
        if data:
            self._set_cache(cache_key, data)
        return data

    # ── Congress / Earnings (PUBLIC) ─────────────────────────────────────

    def get_congress_trades(self) -> Optional[dict]:
        """PUBLIC — recent congressional trades."""
        cache_key = "congress_trades"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/congress/trades")
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_congress_activity(self) -> Optional[dict]:
        """PUBLIC — congress activity aggregates."""
        cache_key = "congress_activity"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/congress/activity")
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_earnings_upcoming(self) -> Optional[dict]:
        """PUBLIC — upcoming earnings calendar."""
        cache_key = "earnings_upcoming"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/earnings/upcoming")
        if data:
            self._set_cache(cache_key, data)
        return data

    def get_earnings_ticker(self, ticker: str) -> Optional[dict]:
        """PUBLIC — earnings history / reaction stats for a ticker."""
        t = ticker.upper()
        cache_key = f"earnings_ticker_{t}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        data = self._get("/earnings/ticker", {"ticker": t})
        if data:
            self._set_cache(cache_key, data)
        return data

    def search_tickers(self, query: str) -> Optional[dict]:
        """PUBLIC — ticker/theme search."""
        q = (query or "").strip()
        if not q:
            return None
        return self._get("/search/tickers", {"q": q})

    # ── Symbol Info ──────────────────────────────────────────────────────

    def get_symbol_info(self, ticker: str) -> Optional[dict]:
        # Prefer ticker payload summary
        raw = self.get_ticker_detail_raw(ticker, window=5)
        if not raw:
            return None
        latest = raw.get("latest") or {}
        summary = raw.get("summary") or {}
        return {
            "symbol": {
                "symbol": ticker.upper(),
                "close": latest.get("close") or summary.get("close"),
                "company": (raw.get("_raw") or {}).get("name", ""),
                "sector": (raw.get("_raw") or {}).get("sector", ""),
                "short_volume_pct": latest.get("short_volume_pct"),
            }
        }

    # ── Summary/Narrative (backward compat) ──────────────────────────────

    def get_summary(self) -> DarkPoolSummary:
        top = self.get_top_positions(limit=10)
        spy = self.get_ticker_latest("SPY")
        qqq = self.get_ticker_latest("QQQ")
        return DarkPoolSummary(
            top_positions=top,
            spy_detail=spy,
            qqq_detail=qqq,
            timestamp=top[0].date if top else (spy.date if spy else ""),
        )

    def get_narrative(self) -> str:
        try:
            summary = self.get_summary()
            parts = []
            if summary.spy_detail:
                s = summary.spy_detail
                parts.append(
                    f"SPY DP: ${s.dp_position_dollars/1e9:.1f}B (SV {s.short_volume_pct:.1f}%)"
                )
            if summary.qqq_detail:
                q = summary.qqq_detail
                parts.append(
                    f"QQQ DP: ${q.dp_position_dollars/1e9:.1f}B (SV {q.short_volume_pct:.1f}%)"
                )
            if summary.top_positions:
                top3 = [
                    f"{p.ticker}(${p.dp_position_dollars/1e9:.1f}B)"
                    for p in summary.top_positions[:3]
                ]
                parts.append(f"Top: {', '.join(top3)}")
            return " | ".join(parts) if parts else "Dark pool data unavailable"
        except Exception as e:
            logger.error(f"❌ Narrative error: {e}")
            return "Dark pool data unavailable"

    # ── Earnings-Specific Intelligence ───────────────────────────────────

    def get_earnings_intel(self, tickers: List[str]) -> Dict[str, dict]:
        intel: Dict[str, dict] = {}

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
            sv_items = (
                sv_raw.get("data", [])
                if isinstance(sv_raw, dict)
                else sv_raw
                if isinstance(sv_raw, list)
                else []
            )

            trend = []
            for i in range(max(0, len(dates) - 5), len(dates)):
                trend.append(
                    {
                        "date": dates[i],
                        "shares": dps[i] if i < len(dps) else None,
                        "dollars": ddp[i] if i < len(ddp) else None,
                        "net_vol": dnv[i] if i < len(dnv) else None,
                    }
                )

            sv_pct = 0.0
            if sv_items:
                sv_sorted = sorted(
                    [r for r in sv_items if isinstance(r, dict)],
                    key=lambda x: x.get("date", ""),
                    reverse=True,
                )
                if sv_sorted:
                    newest = sv_sorted[0]
                    raw_sv = newest.get(
                        "short_volume_pct",
                        newest.get("short_volume%", newest.get("short_volume_percent", 0)),
                    )
                    sv_pct = float(raw_sv or 0)
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
                "state": detail.get("state"),
            }

        for sym in ["SPY", "QQQ"]:
            wall = self.get_option_walls_today(sym)
            if wall:
                intel[f"{sym}_walls"] = {
                    "date": wall.date,
                    "call_wall": wall.call_wall,
                    "put_wall": wall.put_wall,
                    "poc": wall.poc,
                }

        regime = self.get_volatility_regime()
        if regime:
            intel["_regime"] = regime

        signals = self.get_signal_symbols()
        if signals:
            intel["_signals"] = signals

        return intel


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = StockgridClient()

    print("=" * 60)
    print("🐺 AXLFI v2 Market Intelligence — Smoke Test")
    print("=" * 60)

    walls = client.get_option_walls_today("SPY")
    print("SPY walls:", walls)

    raw = client.get_ticker_detail_raw("SPY", window=30)
    if raw:
        dp = raw["individual_dark_pool_position_data"]
        print("SPY as_of", raw.get("as_of_date"), "points", len(dp.get("dates") or []))
        print("last5 pos", (dp.get("dp_position") or [])[-5:])
    else:
        print("SPY ticker: NONE")

    top = client.get_top_positions(limit=5)
    print("top", [(p.ticker, round(p.dp_position_dollars / 1e9, 2)) for p in top])


# ─── Backward Compatibility Aliases ─────────────────────────────────────────

StockGridClient = StockgridClient
