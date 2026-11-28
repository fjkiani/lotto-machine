#!/usr/bin/env python3
"""
AXLFI live dark-pool probe — SPY + QQQ + 1 leaderboard single-name.

Fail-closed (Pro / darkpools):
  - Neither AXLFI_SESSION_COOKIE nor AXLFI_PRO_COOKIE set → darkpools HARD_BLOCK
  - Never invents DP numbers / never labels darkpools LIVE without HTTP 200 Pro
  - Never prints cookie values (bool presence only)
  - Overall pack remains NOT SELLABLE without cookie + LIVE Pro universe

PUBLIC enrichment (no Pro) always attempted via StockgridClient #16 methods:
  - get_option_walls / get_short_interest_ticker / get_clusters_scan / get_market_update
  - Labeled LIVE only on HTTP 200; shown honestly even when overall NOT SELLABLE

Writes HF_SIGNAL_PACK_<UTC>.json + HF_SIGNAL_STATUS.md.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ARTIFACTS_DIR = Path("/opt/cursor/artifacts")
STATUS_PATH = ARTIFACTS_DIR / "HF_SIGNAL_STATUS.md"

INDEXISH = {"SPY", "QQQ", "IWM", "DIA", "VOO", "IVV", "SPX", "NDX"}


def _cookie_flags() -> Dict[str, bool]:
    session = bool(os.environ.get("AXLFI_SESSION_COOKIE", "").strip())
    pro = bool(os.environ.get("AXLFI_PRO_COOKIE", "").strip())
    return {
        "AXLFI_SESSION_COOKIE": session,
        "AXLFI_PRO_COOKIE": pro,
        "cookie_env_present": session or pro,
    }


def _envfile_cookie_flags() -> Dict[str, bool]:
    """Bool-only check of .env keys — never returns values."""
    session = False
    pro = False
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, _, v = s.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k == "AXLFI_SESSION_COOKIE":
                session = bool(v)
            elif k == "AXLFI_PRO_COOKIE":
                pro = bool(v)
    return {
        "AXLFI_SESSION_COOKIE": session,
        "AXLFI_PRO_COOKIE": pro,
        "cookie_env_present": session or pro,
    }


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _classify_freshness(fetch_meta: Dict[str, Any]) -> str:
    """Honesty labels from StockgridClient.last_fetch_meta only."""
    source = (fetch_meta or {}).get("source")
    paywall = bool((fetch_meta or {}).get("paywall"))
    http_status = (fetch_meta or {}).get("http_status")
    if paywall or http_status == 403:
        return "PAYWALL_FALLBACK"
    if source in ("live", "browser") and http_status == 200 and not paywall:
        return "LIVE"
    if source in ("disk", "repo", "legacy"):
        return "PAYWALL_FALLBACK"
    return "PAYWALL_FALLBACK"


def _leaderboard_single_name(client) -> Optional[str]:
    try:
        rows = client.get_top_positions(limit=20) or []
    except Exception:
        return None
    for p in rows:
        t = getattr(p, "ticker", None) or (p.get("ticker") if isinstance(p, dict) else None)
        if t and str(t).upper() not in INDEXISH:
            return str(t).upper()
    return None


def _probe_ticker(client, symbol: str) -> Dict[str, Any]:
    """Probe /darkpools/ticker. Never invents DP series numbers."""
    raw = None
    err = None
    try:
        raw = client.get_ticker_detail_raw(symbol, window=10)
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
    meta = dict(getattr(client, "last_fetch_meta", {}) or {})
    freshness = _classify_freshness(meta)
    http_status = meta.get("http_status")
    has_series = False
    as_of = None
    if isinstance(raw, dict):
        dp = raw.get("individual_dark_pool_position_data") or {}
        positions = dp.get("dp_position") or []
        dates = dp.get("dates") or []
        has_series = len(positions) > 0 and len(dates) > 0
        as_of = raw.get("as_of_date") or (dates[-1] if dates else None)
        if as_of is not None:
            as_of = str(as_of)[:10]

    live_ok = (
        http_status == 200
        and freshness == "LIVE"
        and has_series
        and not meta.get("paywall")
    )
    return {
        "symbol": symbol,
        "http_status": http_status,
        "source": meta.get("source"),
        "paywall": bool(meta.get("paywall")),
        "data_freshness": freshness,
        "as_of_data": as_of,
        "has_dp_series": has_series,
        "live_ok": live_ok,
        "error": err,
        # Intentionally omit raw DP arrays — honesty labels only, no invented numbers.
    }


def _write_status(
    *,
    cookie_flags: Dict[str, bool],
    envfile_flags: Dict[str, bool],
    pack_path: Path,
    verdict: str,
    blocker: str,
    gate_rows: List[Dict[str, Any]],
    branch: str,
) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# HF_SIGNAL_STATUS",
        f"Verdict: {verdict}",
        f"Blocker: {blocker}",
        f"Pack: {pack_path}",
        f"cookie_env_present={str(cookie_flags['cookie_env_present']).lower()}",
        f"AXLFI_SESSION_COOKIE(env)={str(cookie_flags['AXLFI_SESSION_COOKIE']).lower()}",
        f"AXLFI_PRO_COOKIE(env)={str(cookie_flags['AXLFI_PRO_COOKIE']).lower()}",
        f"AXLFI_SESSION_COOKIE(.env)={str(envfile_flags['AXLFI_SESSION_COOKIE']).lower()}",
        f"AXLFI_PRO_COOKIE(.env)={str(envfile_flags['AXLFI_PRO_COOKIE']).lower()}",
        f"Branch: {branch}",
        "",
        "## Gate table",
        "",
        "| Gate | Result | Notes |",
        "|---|---|---|",
    ]
    for row in gate_rows:
        lines.append(
            f"| {row['gate']} | {row['result']} | {row.get('notes', '')} |"
        )
    lines.append("")
    STATUS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _hard_block_pack(
    *,
    stamp: str,
    cookie_flags: Dict[str, bool],
    envfile_flags: Dict[str, bool],
    public_enrichment: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from backend.app.signals.sources.public_enrichment import darkpools_hard_block_layer

    public = public_enrichment or {}
    public_live = bool(public.get("public_live_ok"))
    return {
        "pack_id": f"HF_SIGNAL_PACK_{stamp}",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "NOT_SELLABLE",
        "blocker": (
            "HARD_BLOCK LIVE — neither AXLFI_SESSION_COOKIE nor AXLFI_PRO_COOKIE "
            "present (env and .env). Keep PAYWALL_FALLBACK / NOT SELLABLE. "
            "Public layers may still be LIVE."
        ),
        "cookie_env_present": False,
        "cookie_flags": {
            "env": {
                "AXLFI_SESSION_COOKIE": cookie_flags["AXLFI_SESSION_COOKIE"],
                "AXLFI_PRO_COOKIE": cookie_flags["AXLFI_PRO_COOKIE"],
            },
            "envfile": {
                "AXLFI_SESSION_COOKIE": envfile_flags["AXLFI_SESSION_COOKIE"],
                "AXLFI_PRO_COOKIE": envfile_flags["AXLFI_PRO_COOKIE"],
            },
        },
        # Pack-level freshness stays PAYWALL for Pro/darkpools gate honesty
        "data_freshness": "PAYWALL_FALLBACK",
        "strategy": "DarkPoolTrend",
        "universe": {
            "SPY": {
                "status": "HARD_BLOCK",
                "freshness": "PAYWALL_FALLBACK",
                "reason": "No Pro session cookie — live /darkpools/ticker not attempted",
            },
            "QQQ": {
                "status": "HARD_BLOCK",
                "freshness": "PAYWALL_FALLBACK",
                "reason": "No Pro session cookie — live /darkpools/ticker not attempted",
            },
            "single_name": {
                "status": "HARD_BLOCK",
                "freshness": "PAYWALL_FALLBACK",
                "reason": "No Pro session cookie — leaderboard single-name probe skipped",
            },
        },
        "public_enrichment": public,
        "layers": {
            **(public.get("layers") or {}),
            "darkpools": darkpools_hard_block_layer(
                reason="cookie_env_present=false — Pro /darkpools/* not attempted"
            ),
        },
        "gate_A_stockgrid": {
            "BASE": "https://axlfi.com/api",
            "darkpools_ticker_http": None,
            "probe_skipped": True,
            "reason": "cookie_env_present=false",
            "public_live_ok": public_live,
            "public_live_count": public.get("public_live_count", 0),
            "public_methods": [
                "get_option_walls",
                "get_short_interest_ticker",
                "get_clusters_scan",
                "get_market_update",
            ],
        },
        "sellable": False,
        "hard_block": True,
    }


def _live_pack(
    *,
    stamp: str,
    cookie_flags: Dict[str, bool],
    probes: List[Dict[str, Any]],
    single_name: Optional[str],
    public_enrichment: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    by_sym = {p["symbol"]: p for p in probes}
    all_live = all(p.get("live_ok") for p in probes) and len(probes) >= 3
    freshness_set = {p.get("data_freshness") for p in probes}
    if all_live and freshness_set == {"LIVE"}:
        pack_freshness = "LIVE"
        verdict = "SELLABLE"
        sellable = True
        blocker = None
    else:
        # Prefer PAYWALL if any probe hit it; else CACHE/unknown → not sellable
        if "PAYWALL_FALLBACK" in freshness_set or any(
            p.get("http_status") == 403 for p in probes
        ):
            pack_freshness = "PAYWALL_FALLBACK"
        elif "LIVE" in freshness_set:
            pack_freshness = "LIVE"  # partial — still NOT sellable without full universe
        else:
            pack_freshness = "PAYWALL_FALLBACK"
        verdict = "NOT_SELLABLE"
        sellable = False
        bad = [p for p in probes if not p.get("live_ok")]
        blocker = (
            "Universe not fully LIVE HTTP 200 Pro: "
            + "; ".join(
                f"{p['symbol']} http={p.get('http_status')} freshness={p.get('data_freshness')}"
                for p in bad
            )
        )

    universe: Dict[str, Any] = {}
    for sym in ("SPY", "QQQ"):
        p = by_sym.get(sym)
        if not p:
            universe[sym] = {
                "status": "HARD_BLOCK",
                "freshness": "PAYWALL_FALLBACK",
                "reason": "probe missing",
            }
        elif p.get("live_ok"):
            universe[sym] = {
                "status": "OK",
                "freshness": p["data_freshness"],
                "http_status": p.get("http_status"),
                "as_of_data": p.get("as_of_data"),
            }
        else:
            universe[sym] = {
                "status": "HARD_BLOCK",
                "freshness": p.get("data_freshness", "PAYWALL_FALLBACK"),
                "http_status": p.get("http_status"),
                "as_of_data": p.get("as_of_data"),
                "reason": p.get("error")
                or f"http={p.get('http_status')} source={p.get('source')}",
            }

    sn_key = f"single_name_{single_name}" if single_name else "single_name"
    if single_name and single_name in by_sym:
        p = by_sym[single_name]
        if p.get("live_ok"):
            universe[sn_key] = {
                "status": "OK",
                "freshness": p["data_freshness"],
                "http_status": p.get("http_status"),
                "as_of_data": p.get("as_of_data"),
                "ticker": single_name,
            }
        else:
            universe[sn_key] = {
                "status": "HARD_BLOCK",
                "freshness": p.get("data_freshness", "PAYWALL_FALLBACK"),
                "http_status": p.get("http_status"),
                "ticker": single_name,
                "reason": p.get("error")
                or f"http={p.get('http_status')} source={p.get('source')}",
            }
    else:
        universe[sn_key] = {
            "status": "HARD_BLOCK",
            "freshness": "PAYWALL_FALLBACK",
            "reason": "No non-index leaderboard single-name resolved",
        }

    spy = by_sym.get("SPY", {})
    public = public_enrichment or {}
    # Darkpools layer: LIVE only if SPY probe live_ok (HTTP 200 Pro + series)
    if spy.get("live_ok"):
        dp_layer: Dict[str, Any] = {
            "name": "darkpools",
            "method": "get_ticker_detail_raw",
            "path": "/darkpools/ticker",
            "status": "LIVE",
            "freshness": "LIVE",
            "http_status": spy.get("http_status"),
            "live_ok": True,
        }
    else:
        from backend.app.signals.sources.public_enrichment import darkpools_hard_block_layer

        dp_layer = darkpools_hard_block_layer(
            reason=spy.get("error")
            or f"http={spy.get('http_status')} freshness={spy.get('data_freshness')}",
            http_status=spy.get("http_status"),
        )

    return {
        "pack_id": f"HF_SIGNAL_PACK_{stamp}",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "blocker": blocker,
        "cookie_env_present": True,
        "cookie_flags": {
            "env": {
                "AXLFI_SESSION_COOKIE": cookie_flags["AXLFI_SESSION_COOKIE"],
                "AXLFI_PRO_COOKIE": cookie_flags["AXLFI_PRO_COOKIE"],
            }
        },
        "data_freshness": pack_freshness,
        "strategy": "DarkPoolTrend",
        "ticker": "SPY",
        "as_of_data": spy.get("as_of_data"),
        "universe": universe,
        "probes": probes,  # meta only — no invented DP arrays
        "public_enrichment": public,
        "layers": {
            **(public.get("layers") or {}),
            "darkpools": dp_layer,
        },
        "gate_A_stockgrid": {
            "BASE": "https://axlfi.com/api",
            "darkpools_ticker_http": spy.get("http_status"),
            "probe_skipped": False,
            "public_live_ok": bool(public.get("public_live_ok")),
            "public_live_count": public.get("public_live_count", 0),
            "public_methods": [
                "get_option_walls",
                "get_short_interest_ticker",
                "get_clusters_scan",
                "get_market_update",
            ],
        },
        "sellable": sellable,
        "hard_block": not sellable,
    }


def _public_gate_rows(public: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    layers = (public or {}).get("layers") or {}
    for key in ("options_walls", "short_interest", "clusters", "market_update"):
        layer = layers.get(key) or {}
        rows.append(
            {
                "gate": f"PUBLIC {key}",
                "result": "LIVE" if layer.get("live_ok") else "HARD_BLOCK",
                "notes": (
                    f"method={layer.get('method')} http={layer.get('http_status')} "
                    f"path={layer.get('path')}"
                ),
            }
        )
    return rows


def main() -> int:
    cookie_flags = _cookie_flags()
    envfile_flags = _envfile_cookie_flags()
    # Present if either process env OR non-empty .env key is set
    present = cookie_flags["cookie_env_present"] or envfile_flags["cookie_env_present"]

    print("AXLFI_SESSION_COOKIE", cookie_flags["AXLFI_SESSION_COOKIE"])
    print("AXLFI_PRO_COOKIE", cookie_flags["AXLFI_PRO_COOKIE"])
    print("cookie_env_present", present)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _utc_stamp()
    pack_path = ARTIFACTS_DIR / f"HF_SIGNAL_PACK_{stamp}.json"
    branch = os.environ.get("GIT_BRANCH") or "cursor/hf-public-pack-enrich-0041"

    from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
    from backend.app.signals.sources.public_enrichment import fetch_public_enrichment

    # Public enrichment always runs (no Pro cookie required)
    client = StockgridClient(cache_ttl=0, max_retries=1)
    public = fetch_public_enrichment(client, "SPY")
    print(
        "public_live",
        public.get("public_live_count"),
        "/",
        len(public.get("layers") or {}),
        "layers=",
        public.get("live_layer_names"),
    )

    if not present:
        pack = _hard_block_pack(
            stamp=stamp,
            cookie_flags=cookie_flags,
            envfile_flags=envfile_flags,
            public_enrichment=public,
        )
        pack_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
        gate_rows = [
            {
                "gate": "cookie_env_present",
                "result": "FAIL",
                "notes": "SESSION=false PRO=false (env+.env)",
            },
            *_public_gate_rows(public),
            {
                "gate": "LIVE /darkpools/ticker",
                "result": "HARD_BLOCK",
                "notes": "probe skipped — fail closed (no Pro cookie)",
            },
            {
                "gate": "universe SPY+QQQ+1",
                "result": "HARD_BLOCK",
                "notes": "NOT SELLABLE / PAYWALL_FALLBACK",
            },
            {
                "gate": "sellable",
                "result": "NO",
                "notes": "requires HTTP 200 Pro + LIVE freshness (public LIVE alone insufficient)",
            },
        ]
        _write_status(
            cookie_flags={**cookie_flags, "cookie_env_present": present},
            envfile_flags=envfile_flags,
            pack_path=pack_path,
            verdict="NOT SELLABLE",
            blocker=(
                "HARD_BLOCK LIVE — cookie_env_present=false "
                "(set AXLFI_SESSION_COOKIE or AXLFI_PRO_COOKIE); "
                f"public_live_count={public.get('public_live_count', 0)}"
            ),
            gate_rows=gate_rows,
            branch=branch,
        )
        print(f"STATUS: HARD_BLOCK → {STATUS_PATH}")
        print(f"PACK: {pack_path}")
        return 1

    # Cookie present — Pro darkpools live probe
    probes: List[Dict[str, Any]] = []
    for sym in ("SPY", "QQQ"):
        probes.append(_probe_ticker(client, sym))

    single = _leaderboard_single_name(client)
    if single and single not in ("SPY", "QQQ"):
        probes.append(_probe_ticker(client, single))
    else:
        single = None

    pack = _live_pack(
        stamp=stamp,
        cookie_flags=cookie_flags,
        probes=probes,
        single_name=single,
        public_enrichment=public,
    )
    pack_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")

    gate_rows = [
        {
            "gate": "cookie_env_present",
            "result": "PASS",
            "notes": "SESSION or PRO true",
        },
        *_public_gate_rows(public),
    ]
    for p in probes:
        gate_rows.append(
            {
                "gate": f"LIVE /darkpools/ticker {p['symbol']}",
                "result": "PASS" if p.get("live_ok") else "FAIL",
                "notes": (
                    f"http={p.get('http_status')} freshness={p.get('data_freshness')} "
                    f"source={p.get('source')}"
                ),
            }
        )
    gate_rows.append(
        {
            "gate": "sellable",
            "result": "YES" if pack.get("sellable") else "NO",
            "notes": pack.get("blocker") or "HTTP 200 Pro + LIVE universe",
        }
    )
    _write_status(
        cookie_flags={**cookie_flags, "cookie_env_present": present},
        envfile_flags=envfile_flags,
        pack_path=pack_path,
        verdict="SELLABLE" if pack.get("sellable") else "NOT SELLABLE",
        blocker=pack.get("blocker") or "none",
        gate_rows=gate_rows,
        branch=branch,
    )
    print(f"STATUS: {'SELLABLE' if pack.get('sellable') else 'NOT SELLABLE'} → {STATUS_PATH}")
    print(f"PACK: {pack_path}")
    return 0 if pack.get("sellable") else 2


if __name__ == "__main__":
    sys.exit(main())
