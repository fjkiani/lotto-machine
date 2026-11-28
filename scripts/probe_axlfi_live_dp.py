#!/usr/bin/env python3
"""
AXLFI live dark-pool probe — SPY + QQQ + 1 leaderboard single-name.

Fail-closed:
  - Neither AXLFI_SESSION_COOKIE nor AXLFI_PRO_COOKIE set → HARD_BLOCK, exit 1
  - Never invents DP numbers
  - Never prints cookie values (bool presence only)

When cookies are present, probes StockgridClient /api/darkpools/ticker and
writes HF_SIGNAL_PACK_<UTC>.json with data_freshness LIVE | PAYWALL_FALLBACK
honestly from HTTP results.
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
) -> Dict[str, Any]:
    return {
        "pack_id": f"HF_SIGNAL_PACK_{stamp}",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "NOT_SELLABLE",
        "blocker": (
            "HARD_BLOCK LIVE — neither AXLFI_SESSION_COOKIE nor AXLFI_PRO_COOKIE "
            "present (env and .env). Keep PAYWALL_FALLBACK / NOT SELLABLE."
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
        "gate_A_stockgrid": {
            "BASE": "https://axlfi.com/api",
            "darkpools_ticker_http": None,
            "probe_skipped": True,
            "reason": "cookie_env_present=false",
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
        "gate_A_stockgrid": {
            "BASE": "https://axlfi.com/api",
            "darkpools_ticker_http": spy.get("http_status"),
            "probe_skipped": False,
        },
        "sellable": sellable,
        "hard_block": not sellable,
    }


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
    branch = os.environ.get("GIT_BRANCH") or "cursor/axlfi-live-dp-probe-0041"

    if not present:
        pack = _hard_block_pack(
            stamp=stamp, cookie_flags=cookie_flags, envfile_flags=envfile_flags
        )
        pack_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
        gate_rows = [
            {
                "gate": "cookie_env_present",
                "result": "FAIL",
                "notes": "SESSION=false PRO=false (env+.env)",
            },
            {
                "gate": "LIVE /darkpools/ticker",
                "result": "HARD_BLOCK",
                "notes": "probe skipped — fail closed",
            },
            {
                "gate": "universe SPY+QQQ+1",
                "result": "HARD_BLOCK",
                "notes": "NOT SELLABLE / PAYWALL_FALLBACK",
            },
            {
                "gate": "sellable",
                "result": "NO",
                "notes": "requires HTTP 200 Pro + LIVE freshness",
            },
        ]
        _write_status(
            cookie_flags={**cookie_flags, "cookie_env_present": present},
            envfile_flags=envfile_flags,
            pack_path=pack_path,
            verdict="NOT SELLABLE",
            blocker=(
                "HARD_BLOCK LIVE — cookie_env_present=false "
                "(set AXLFI_SESSION_COOKIE or AXLFI_PRO_COOKIE)"
            ),
            gate_rows=gate_rows,
            branch=branch,
        )
        print(f"STATUS: HARD_BLOCK → {STATUS_PATH}")
        print(f"PACK: {pack_path}")
        return 1

    # Cookie present — live probe
    from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient

    client = StockgridClient(cache_ttl=0, max_retries=1)
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
    )
    pack_path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")

    gate_rows = [
        {
            "gate": "cookie_env_present",
            "result": "PASS",
            "notes": "SESSION or PRO true",
        },
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
