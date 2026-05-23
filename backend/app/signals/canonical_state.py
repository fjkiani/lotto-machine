"""
Canonical Kill Chain / GEX / DVR snapshot — single SQLite row per compute cycle.

Written from compute_kill_chain() so cold starts, /signals inject fallback, and
DarkPoolTrend can share the same stamped numbers.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB_LOCK = threading.Lock()
# Bumped on each oracle persist so /api/v1/signals cache key invalidates.
_ORACLE_SIGNAL_BUMP = 0

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = _ROOT / "data" / "kill_chain_canonical.db"


def _db_path() -> Path:
    return DEFAULT_DB_PATH


def _connect() -> sqlite3.Connection:
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate_canonical(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS canonical_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL,
            spy_price REAL,
            gex_net REAL,
            gex_regime TEXT,
            gex_symbol TEXT,
            dvr_pct REAL,
            dvr_triggered INTEGER,
            cot_specs_net INTEGER,
            kill_chain_score INTEGER,
            kill_chain_verdict TEXT,
            kill_chain_direction TEXT,
            confluence TEXT,
            vix REAL,
            war_status INTEGER,
            oil_wti REAL,
            macro_regime TEXT,
            zo_directive TEXT,
            payload_json TEXT NOT NULL
        )
        """
    )
    cur = conn.execute("PRAGMA table_info(canonical_snapshots)")
    have = {r[1] for r in cur.fetchall()}
    for col, typ in (
        ("spy_price", "REAL"),
        ("war_status", "INTEGER"),
        ("oil_wti", "REAL"),
        ("macro_regime", "TEXT"),
        ("zo_directive", "TEXT"),
    ):
        if col not in have:
            conn.execute(f"ALTER TABLE canonical_snapshots ADD COLUMN {col} {typ}")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS oracle_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            slug TEXT NOT NULL,
            title TEXT,
            action TEXT,
            confidence REAL,
            risk_level TEXT,
            strategy_json TEXT,
            kill_chain_score INTEGER,
            kill_chain_verdict TEXT,
            payload_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_oracle_created "
        "ON oracle_signals(created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_canonical_captured "
        "ON canonical_snapshots(captured_at DESC)"
    )
    _migrate_oracle_unique_slug(conn)


def _migrate_oracle_unique_slug(conn: sqlite3.Connection) -> None:
    """One row per slug — enables UPSERT and stops duplicate ORACLE rows in /signals."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_oracle_unique_slug'"
    )
    if cur.fetchone():
        return
    try:
        conn.execute(
            """
            DELETE FROM oracle_signals WHERE id NOT IN (
                SELECT MAX(id) FROM oracle_signals GROUP BY slug
            )
            """
        )
    except sqlite3.OperationalError:
        pass
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_oracle_unique_slug "
        "ON oracle_signals(slug)"
    )


def oracle_signal_cache_bump() -> int:
    return _ORACLE_SIGNAL_BUMP


def init_canonical_db() -> None:
    with _connect() as c:
        _migrate_canonical(c)
        c.commit()


def persist_from_kill_chain(result: Dict[str, Any], raw: Dict[str, Any]) -> None:
    """Persist after a full compute_kill_chain() result dict is built."""
    init_canonical_db()
    captured = datetime.now(timezone.utc).isoformat()
    layer1 = result.get("layer_1") or {}
    layer2 = result.get("layer_2") or {}
    layer3 = result.get("layer_3") or {}
    # layer_4 = AXLFI Wall Position (SPY price vs call/put walls) — NOT macro
    # layer_macro = Macro Overlay (war_status, oil_wti, macro_regime) — correct source
    layer4 = result.get("layer_4") or {}
    layer_macro = result.get("layer_macro") or {}

    gex_net = float(layer2.get("raw_value") or raw.get("gex_total") or 0.0)
    gex_regime = str(layer2.get("signal") or raw.get("gex_regime") or "")
    gex_symbol = str(layer2.get("symbol") or "SPY")
    dvr_pct = float(layer3.get("value") or raw.get("sv_pct") or 0.0)
    dvr_triggered = 1 if layer3.get("triggered") else 0
    try:
        cot_specs = int(layer1.get("value") or raw.get("cot_specs_net") or 0)
    except (TypeError, ValueError):
        cot_specs = 0

    # FIX: war_status comes from layer_macro.value, NOT layer_4.value (which is SPY spot price)
    war_status = int(layer_macro.get("value") or result.get("war_status") or 0)
    # FIX: oil_wti comes from layer_macro, NOT layer_4
    oil_wti = layer_macro.get("oil_wti")
    if oil_wti is not None:
        try:
            oil_wti = float(oil_wti)
        except (TypeError, ValueError):
            oil_wti = None
    # FIX: macro_regime comes from layer_macro.signal, NOT layer_4.signal (which is ABOVE_CALL_WALL etc.)
    macro_regime = (
        str(layer_macro.get("signal") or "")
        or str(result.get("macro_regime") or "")
    ) or None

    # FIX: spy_price comes from raw["spot"] (live GEX spot) or layer_4.value (AXLFI spot),
    # NOT position.entry_price (which is the KC position entry from a prior activation)
    spy_price = None
    try:
        spot_candidates = [
            raw.get("axlfi_spot"),  # kill_chain.py line 407: raw["axlfi_spot"] = current_spot
            layer4.get("value"),    # AXLFI layer_4 also stores current_spot as value
            raw.get("spot"),        # nested signal dicts use this key
            raw.get("gex_spot"),
        ]
        for candidate in spot_candidates:
            if candidate and float(candidate) > 100:  # sanity: SPY > 00
                spy_price = round(float(candidate), 2)
                break
    except (TypeError, ValueError):
        pass

    zo_directive = f"{result.get('verdict')}|{result.get('direction')}|{result.get('confluence')}"
    veto_reason = layer_macro.get("veto_reason") or layer4.get("veto_reason")
    if veto_reason:
        zo_directive = f"{zo_directive}|{veto_reason}"

    payload = {
        "kill_chain": result,
        "raw": raw,
        "gex": None,
    }
    try:
        from backend.app.utils.gex_canonical import canonical_gex_as_dict

        payload["gex"] = canonical_gex_as_dict(gex_symbol)
    except Exception:
        pass

    row = (
        captured,
        spy_price,
        gex_net,
        gex_regime,
        gex_symbol,
        dvr_pct,
        dvr_triggered,
        cot_specs,
        int(result.get("score") or 0),
        str(result.get("verdict") or "NEUTRAL"),
        str(result.get("direction") or "MIXED"),
        str(result.get("confluence") or "WAITING"),
        None,
        war_status,
        oil_wti,
        macro_regime,
        zo_directive[:2000] if zo_directive else None,
        json.dumps(payload, default=str),
    )

    with _DB_LOCK:
        with _connect() as c:
            c.execute(
                """
                INSERT INTO canonical_snapshots (
                    captured_at, spy_price, gex_net, gex_regime, gex_symbol,
                    dvr_pct, dvr_triggered, cot_specs_net,
                    kill_chain_score, kill_chain_verdict, kill_chain_direction,
                    confluence, vix, war_status, oil_wti, macro_regime, zo_directive,
                    payload_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                row,
            )
            c.commit()


def load_latest_row() -> Optional[Dict[str, Any]]:
    init_canonical_db()
    with _connect() as c:
        cur = c.execute(
            "SELECT * FROM canonical_snapshots ORDER BY id DESC LIMIT 1"
        )
        r = cur.fetchone()
        if not r:
            return None
        return dict(r)


def load_latest_kill_chain_for_inject(max_age_sec: float = 120.0) -> Optional[Dict[str, Any]]:
    """
    Minimal kill-chain dict for _inject_kill_chain when live compute times out.
    Rejects snapshots older than max_age_sec to avoid stale score/verdict inject.
    """
    row = load_latest_row()
    if not row:
        return None
    cap = _parse_captured_at(str(row.get("captured_at") or ""))
    if cap:
        age = (datetime.now(timezone.utc) - cap).total_seconds()
        if age > max_age_sec:
            import logging

            logging.getLogger(__name__).warning(
                "canonical inject skipped: snapshot age %.0fs > max %.0fs",
                age,
                max_age_sec,
            )
            return None
    try:
        payload = json.loads(row["payload_json"])
        kc = payload.get("kill_chain")
        if isinstance(kc, dict) and "verdict" in kc and "score" in kc:
            kc = dict(kc)
            kc["_inject_source"] = "canonical_sqlite"
            kc["_canonical_captured_at"] = row.get("captured_at")
            return kc
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return {
        "score": row.get("kill_chain_score") or 0,
        "verdict": row.get("kill_chain_verdict") or "NEUTRAL",
        "direction": row.get("kill_chain_direction") or "MIXED",
        "confluence": row.get("confluence"),
        "layer_1": {},
        "layer_2": {},
        "layer_3": {},
        "position": {},
        "signals": [],
        "layers": {},
        "_inject_source": "canonical_sqlite_minimal",
        "_canonical_captured_at": row.get("captured_at"),
    }


def _parse_captured_at(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        cap = datetime.fromisoformat(s)
        if cap.tzinfo is None:
            cap = cap.replace(tzinfo=timezone.utc)
        return cap
    except (ValueError, TypeError):
        return None


def get_stamped_gex_for_symbol(symbol: str, max_age_sec: float = 600.0) -> Optional[Dict[str, Any]]:
    """
    GEX dict from the latest canonical snapshot (same stamp as compute_kill_chain / DarkPoolTrend).

    Returns None if no row, stale (> max_age_sec), symbol mismatch, or payload has no gex block.
    """
    row = load_latest_row()
    if not row:
        return None
    cap = _parse_captured_at(str(row.get("captured_at") or ""))
    if not cap:
        return None
    age = (datetime.now(timezone.utc) - cap).total_seconds()
    if age > max_age_sec:
        return None

    sym = (symbol or "SPY").upper()
    row_sym = (row.get("gex_symbol") or "SPY").upper()
    wall = sym if sym in ("SPY", "QQQ", "IWM") else "SPY"
    if row_sym != wall:
        return None

    try:
        payload = json.loads(row["payload_json"])
        gex = payload.get("gex")
        if isinstance(gex, dict):
            out = dict(gex)
            out["gex_captured_at"] = row["captured_at"]
            out["gex_stamp_source"] = "canonical_sqlite"
            return out
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return None


def _confidence_is_master(confidence: float) -> bool:
    """Oracle confidence may be 0–100 (ZO) or 0–10; align with /signals master (75%)."""
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return False
    if c > 10:
        return c >= 75.0
    return c >= 7.5


def persist_oracle_signal(
    *,
    slug: Optional[str],
    title: Optional[str],
    action: Optional[str],
    confidence: float,
    risk_level: Optional[str],
    strategy: Optional[Dict[str, Any]],
    kill_chain_snapshot: Optional[Any],
) -> None:
    global _ORACLE_SIGNAL_BUMP
    init_canonical_db()
    kc_score = None
    kc_verdict = None
    if kill_chain_snapshot is not None:
        try:
            kc_score = int(getattr(kill_chain_snapshot, "score", None) or 0)
            kc_verdict = str(getattr(kill_chain_snapshot, "verdict", "") or "")
        except Exception:
            pass
    slug = slug or "unknown"
    payload = {
        "slug": slug,
        "title": title,
        "action": action,
        "confidence": confidence,
        "risk_level": risk_level,
        "strategy": strategy,
        "kill_chain_score": kc_score,
        "kill_chain_verdict": kc_verdict,
    }
    strat_json = json.dumps(strategy, default=str) if strategy else None
    created = datetime.now(timezone.utc).isoformat()
    row = (
        created,
        slug,
        title,
        action,
        float(confidence),
        risk_level,
        strat_json,
        kc_score,
        kc_verdict,
        json.dumps(payload, default=str),
    )
    with _DB_LOCK:
        with _connect() as c:
            _migrate_oracle_unique_slug(c)
            c.execute(
                """
                INSERT INTO oracle_signals (
                    created_at, slug, title, action, confidence, risk_level,
                    strategy_json, kill_chain_score, kill_chain_verdict, payload_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(slug) DO UPDATE SET
                    created_at=excluded.created_at,
                    title=excluded.title,
                    action=excluded.action,
                    confidence=excluded.confidence,
                    risk_level=excluded.risk_level,
                    strategy_json=excluded.strategy_json,
                    kill_chain_score=excluded.kill_chain_score,
                    kill_chain_verdict=excluded.kill_chain_verdict,
                    payload_json=excluded.payload_json
                """,
                row,
            )
            c.commit()
    _ORACLE_SIGNAL_BUMP += 1


def load_recent_oracle_signals(max_age_hours: float = 4.0) -> List[Dict[str, Any]]:
    init_canonical_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    cutoff_s = cutoff.isoformat()
    out: List[Dict[str, Any]] = []
    with _connect() as c:
        rows = c.execute(
            """
            SELECT * FROM oracle_signals
            WHERE created_at >= ?
            ORDER BY id DESC
            LIMIT 50
            """,
            (cutoff_s,),
        ).fetchall()
    for r in rows:
        d = dict(r)
        try:
            payload = json.loads(d.get("payload_json") or "{}")
        except json.JSONDecodeError:
            payload = {}
        slug = str(d.get("slug") or payload.get("slug") or "unknown")
        conf = float(d.get("confidence") or 0)
        conf_display = int(round(conf)) if conf > 10 else int(round(conf * 10))
        created = str(d.get("created_at") or "")
        day = created[:10] if len(created) >= 10 else "unknown"
        master = _confidence_is_master(conf)
        out.append(
            {
                "id": f"oracle_{slug}_{day}",
                "symbol": "SPY",
                "source": "ORACLE",
                "is_master": master,
                "is_primary": master,
                "action": (d.get("action") or payload.get("action") or "WATCH"),
                "confidence": conf_display,
                "confidence_raw": conf,
                "title": d.get("title") or payload.get("title"),
                "slug": slug,
                "kill_chain_verdict": d.get("kill_chain_verdict")
                or payload.get("kill_chain_verdict"),
                "kill_chain_score": d.get("kill_chain_score")
                or payload.get("kill_chain_score"),
                "risk_level": d.get("risk_level"),
                "created_at": created,
            }
        )
    # One row per slug (ORDER BY id DESC → first wins = newest)
    seen_slug = set()
    unique: List[Dict[str, Any]] = []
    for s in out:
        sl = str(s.get("slug") or "unknown")
        if sl in seen_slug:
            continue
        seen_slug.add(sl)
        unique.append(s)
    return unique


def _row_to_trend_slice(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not row:
        return {}
    return {
        "score": row.get("kill_chain_score"),
        "verdict": row.get("kill_chain_verdict"),
        "direction": row.get("kill_chain_direction"),
        "gex_regime": row.get("gex_regime"),
        "dvr_pct": row.get("dvr_pct"),
        "cot_net": row.get("cot_specs_net"),
    }


def get_trend_summary(n: int = 5) -> Dict[str, Any]:
    init_canonical_db()
    lim = max(2, min(int(n), 50))
    with _connect() as c:
        rows = c.execute(
            """
            SELECT * FROM canonical_snapshots
            ORDER BY id DESC
            LIMIT ?
            """,
            (lim,),
        ).fetchall()
    rlist = [dict(x) for x in rows]
    current = dict(rlist[0]) if rlist else {}
    previous = dict(rlist[1]) if len(rlist) > 1 else {}
    cur_s = _row_to_trend_slice(current)
    prev_s = _row_to_trend_slice(previous)
    drift = "STABLE"
    try:
        cs = cur_s.get("score")
        ps = prev_s.get("score")
        if cs is not None and ps is not None:
            if int(cs) > int(ps):
                drift = "IMPROVING"
            elif int(cs) < int(ps):
                drift = "DETERIORATING"
    except (TypeError, ValueError):
        pass
    return {
        "current": cur_s,
        "previous": prev_s,
        "drift_direction": drift,
        "zo_directive": (current.get("zo_directive") or ""),
        "captured_at": current.get("captured_at") or "",
        "_sample_rows": len(rlist),
    }


def list_snapshots(
    limit: int = 20,
    since: Optional[str] = None,
    symbol: Optional[str] = None,
) -> Dict[str, Any]:
    init_canonical_db()
    lim = max(1, min(int(limit), 200))
    clauses: List[str] = []
    params: List[Any] = []
    if since:
        clauses.append("captured_at >= ?")
        params.append(since)
    if symbol:
        clauses.append("UPPER(IFNULL(gex_symbol,'')) = UPPER(?)")
        params.append(symbol.strip())
    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    q_params = tuple(params) + (lim,)
    with _connect() as c:
        cur = c.execute(
            f"""
            SELECT captured_at, spy_price, gex_regime, gex_net, dvr_pct,
                   cot_specs_net AS cot_net, kill_chain_score AS score,
                   kill_chain_verdict AS verdict, kill_chain_direction AS direction,
                   zo_directive
            FROM canonical_snapshots
            {where_sql}
            ORDER BY id DESC
            LIMIT ?
            """,
            q_params,
        )
        snaps = [dict(r) for r in cur.fetchall()]
    times = [s.get("captured_at") for s in snaps if s.get("captured_at")]
    return {
        "snapshots": snaps,
        "count": len(snaps),
        "oldest": min(times) if times else None,
        "newest": max(times) if times else None,
    }
