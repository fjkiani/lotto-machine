"""
AlertDB source — reads alerts_history.db and maps alert rows to signal dicts.

Anti-slop rules:
    - classify_alert() is used for ALL direction decisions — no inline hardcoding
    - Entry/stop/target are always computed from the live price at read time
    - Outcome tracking registration is best-effort (never blocks the response)
"""
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from backend.app.signals.classifier import classify_alert
from backend.app.signals.price_cache import get_live_price

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 7  # Covers full earnings cycle + survives weekend restarts


def _resolve_db_path() -> Optional[Path]:
    """Find alerts_history.db across known locations."""
    candidates = [
        Path("data/alerts_history.db"),
        Path("/tmp/alerts_history.db"),
    ]
    try:
        from core.utils.persistent_storage import get_database_path
        candidates.insert(0, get_database_path("alerts_history.db"))
    except Exception:
        pass

    for p in candidates:
        if Path(p).exists():
            return Path(p)
    return None


def _build_levels(action: str, entry: float, target_pct: float = 1.5, stop_pct: float = 0.5) -> dict:
    if action == "LONG":
        target = round(entry * (1 + target_pct / 100), 2)
        stop = round(entry * (1 - stop_pct / 100), 2)
    elif action == "SHORT":
        target = round(entry * (1 - target_pct / 100), 2)
        stop = round(entry * (1 + stop_pct / 100), 2)
    else:
        # WATCH — show nearest support/resistance references
        target = round(entry * 1.01, 2)
        stop = round(entry * 0.99, 2)

    risk = abs(entry - stop)
    reward = abs(target - entry)
    rr = round(reward / risk, 1) if risk > 0 else 0

    t_pct = round(abs(target - entry) / entry * 100, 2) if entry else 0
    s_pct = round(abs(stop - entry) / entry * 100, 2) if entry else 0

    return {
        "target_price": target,
        "stop_price": stop,
        "risk_reward": rr,
        "target_pct_str": f"+{t_pct}%" if action == "LONG" else f"-{t_pct}%",
        "stop_pct_str": f"-{s_pct}%" if action == "LONG" else f"+{s_pct}%",
    }


def fetch_alert_db_signals(
    symbol: Optional[str] = None,
    master_only: bool = False,
    lookback_days: int = _LOOKBACK_DAYS,
) -> List[dict]:
    """Read alerts_history.db and return classified signal dicts.

    Returns empty list if DB not found. Never raises.
    """
    results = []
    db_path = _resolve_db_path()
    if not db_path:
        logger.debug("alerts_history.db not found — skipping AlertDB source")
        return results

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        rows = conn.execute(
            """SELECT *, MAX(timestamp) as latest_ts
               FROM alerts
               WHERE timestamp >= ?
               GROUP BY alert_type, symbol, title
               ORDER BY latest_ts DESC
               LIMIT 50""",
            (cutoff,),
        ).fetchall()
        conn.close()
    except Exception as exc:
        logger.warning(f"fetch_alert_db_signals DB error: {exc}")
        rows = []

    # ── Supabase fallback / augmentation ──────────────────────────────────
    # If SQLite returned nothing (Render ephemeral disk wiped after redeploy),
    # pull from Supabase. If both have data, merge and dedup.
    supabase_rows: List[dict] = []
    try:
        from core.utils.supabase_storage import is_supabase_available, read_alerts
        if is_supabase_available():
            sb = read_alerts(limit=50)
            if sb:
                logger.info(f"📡 Supabase: {len(sb)} alerts available")
                supabase_rows = sb
    except Exception as exc:
        logger.warning(f"Supabase fallback in alert_db_source failed: {exc}")

    # Dedup key: (alert_type, symbol, title) — same logic as SQLite GROUP BY
    seen: set = set()
    raw_rows: List[dict] = []

    for row in rows:
        d = dict(row)
        key = (d.get("alert_type", ""), d.get("symbol", ""), d.get("title", ""))
        if key not in seen:
            seen.add(key)
            raw_rows.append(d)

    for d in supabase_rows:
        key = (d.get("alert_type", ""), d.get("symbol", ""), d.get("title", ""))
        if key not in seen:
            seen.add(key)
            raw_rows.append(d)

    if not raw_rows:
        return results

    for row in raw_rows:
        try:
            r = dict(row)
            alert_type = r.get("alert_type", "")
            alert_symbol = r.get("symbol") or "SPY"

            if symbol and alert_symbol != symbol:
                continue

            description = str(r.get("description", ""))
            action, confidence = classify_alert(alert_type, description)

            if action is None:
                continue  # Infrastructure noise — excluded

            if master_only and (confidence or 0) < 75:
                continue

            entry_price = get_live_price(alert_symbol)
            if entry_price <= 0:
                logger.warning(f"Could not get live price for {alert_symbol} — skipping signal")
                continue

            levels = _build_levels(action, entry_price)

            # Build reasoning from all available text fields
            title = r.get("title", alert_type)
            reasoning = [title] if title else []
            if description and description != title:
                reasoning.append(description)

            # Parse embed_json for structured fields
            embed_fields = []
            try:
                embed_raw = r.get("embed_json", "")
                if embed_raw:
                    embed_data = json.loads(embed_raw) if isinstance(embed_raw, str) else embed_raw
                    for field in embed_data.get("fields", []):
                        fname, fval = field.get("name", ""), field.get("value", "")
                        if fname and fval:
                            embed_fields.append({"label": fname, "value": fval})
                            if any(k in fname.lower() for k in ("signal", "action", "thesis", "catalyst", "reason")):
                                reasoning.append(f"{fname}: {fval}")
            except Exception:
                pass

            # Time horizon from alert_type keywords
            time_horizon = "intraday"
            if "overnight" in alert_type.lower():
                time_horizon = "overnight"
            elif "earnings" in alert_type.lower():
                time_horizon = "event (earnings)"
            elif "swing" in alert_type.lower() or "weekly" in alert_type.lower():
                time_horizon = "swing (2-5 days)"

            signal = {
                "id": f"alert_{r.get('id', 0)}",
                "symbol": alert_symbol,
                "type": alert_type,
                "action": action,
                "confidence": confidence,
                "entry_price": entry_price,
                "stop_price": levels["stop_price"],
                "target_price": levels["target_price"],
                "risk_reward": levels["risk_reward"],
                "reasoning": reasoning[:10],
                "warnings": [],
                "timestamp": r.get("timestamp", datetime.now().isoformat()),
                "source": f"AlertDB:{r.get('source', 'checker')}",
                "is_master": (confidence or 0) >= 75,
                "technical_context": {
                    "trigger_source": "alert_monitor",
                    "time_horizon": time_horizon,
                    "levels": {
                        "entry": entry_price,
                        "target": levels["target_price"],
                        "stop": levels["stop_price"],
                        "target_pct": levels["target_pct_str"],
                        "stop_pct": levels["stop_pct_str"],
                    },
                    "risk_profile": {
                        "risk_reward": levels["risk_reward"],
                        "max_loss_pct": round(abs(entry_price - levels["stop_price"]) / entry_price * 100, 2),
                        "position_size_pct": 2.0 if (confidence or 0) >= 75 else 1.0,
                    },
                    "embed_fields": embed_fields[:8],
                },
            }
            results.append(signal)

            # Best-effort outcome tracking registration
            if action in ("LONG", "SHORT"):
                try:
                    from live_monitoring.core.signal_outcome_tracker import register_signal
                    register_signal(
                        signal_id=signal["id"],
                        symbol=alert_symbol,
                        action=action,
                        entry_price=entry_price,
                        target_price=levels["target_price"],
                        stop_price=levels["stop_price"],
                        timestamp=signal["timestamp"],
                        reasoning="; ".join(reasoning[:3]),
                    )
                except Exception:
                    pass

        except Exception as exc:
            logger.warning(f"fetch_alert_db_signals row error: {exc}")
            continue

    return results
