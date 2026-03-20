"""
🔒 Supabase Persistent Storage for Zeta Signal Engine
=====================================================
Replaces ephemeral SQLite with cloud-hosted Supabase PostgreSQL.

This module is a **drop-in companion** to persistent_storage.py.
When `SUPABASE_URL` + `SUPABASE_KEY` env vars are set, all signal
reads/writes go to Supabase instead of local SQLite.

Tables:
  - alerts             (signal alert history)
  - dp_interactions     (dark pool level interactions)
  - dp_patterns         (pattern win rates)
  - signal_outcomes     (P&L tracking)
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ── Lazy client (only init when needed) ──────────────────────────
_client = None


def _get_client():
    """Get or init Supabase client. Returns None if credentials missing."""
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        logger.info(f"✅ Supabase connected: {url[:30]}...")
        return _client
    except Exception as e:
        logger.warning(f"⚠️ Supabase init failed: {e}")
        return None


def is_supabase_available() -> bool:
    """Check if Supabase is configured and reachable."""
    return _get_client() is not None


# ═══════════════════════════════════════════════════════════════════
# ALERTS (signal history)
# ═══════════════════════════════════════════════════════════════════

def write_alert(alert: Dict[str, Any]) -> bool:
    """Write a signal alert to Supabase. Returns True on success."""
    client = _get_client()
    if not client:
        return False
    try:
        row = {
            "timestamp": alert.get("timestamp", datetime.utcnow().isoformat()),
            "alert_type": alert.get("alert_type", "signal"),
            "title": alert.get("title", ""),
            "description": alert.get("description", ""),
            "content": alert.get("content", ""),
            "embed_json": json.dumps(alert.get("embed_json", {})) if isinstance(alert.get("embed_json"), dict) else alert.get("embed_json", ""),
            "source": alert.get("source", ""),
            "symbol": alert.get("symbol", ""),
        }
        client.table("alerts").insert(row).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase write_alert failed: {e}")
        return False


def read_alerts(limit: int = 100, alert_type: Optional[str] = None,
                symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    """Read alerts from Supabase. Returns list of alert dicts."""
    client = _get_client()
    if not client:
        return []
    try:
        query = client.table("alerts").select("*").order("timestamp", desc=True).limit(limit)
        if alert_type:
            query = query.eq("alert_type", alert_type)
        if symbol:
            query = query.eq("symbol", symbol)
        result = query.execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Supabase read_alerts failed: {e}")
        return []


def read_alerts_since(since_hours: int = 24) -> List[Dict[str, Any]]:
    """Read alerts from the last N hours."""
    client = _get_client()
    if not client:
        return []
    try:
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(hours=since_hours)).isoformat()
        result = (client.table("alerts")
                  .select("*")
                  .gte("timestamp", cutoff)
                  .order("timestamp", desc=True)
                  .execute())
        return result.data or []
    except Exception as e:
        logger.error(f"Supabase read_alerts_since failed: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════
# SIGNAL OUTCOMES (P&L tracking)
# ═══════════════════════════════════════════════════════════════════

def write_signal_outcome(outcome: Dict[str, Any]) -> bool:
    """Write a signal outcome to Supabase."""
    client = _get_client()
    if not client:
        return False
    try:
        row = {
            "signal_id": outcome.get("signal_id"),
            "symbol": outcome.get("symbol", ""),
            "direction": outcome.get("direction", ""),
            "entry_price": outcome.get("entry_price", 0),
            "stop_pct": outcome.get("stop_pct"),
            "target_pct": outcome.get("target_pct"),
            "confidence": outcome.get("confidence"),
            "source": outcome.get("source", ""),
            "regime": outcome.get("regime", ""),
            "bias": outcome.get("bias", ""),
            "sizing": outcome.get("sizing"),
            "entry_time": outcome.get("entry_time", datetime.utcnow().isoformat()),
            "outcome": outcome.get("outcome", "PENDING"),
        }
        client.table("signal_outcomes").upsert(row, on_conflict="signal_id").execute()
        return True
    except Exception as e:
        logger.error(f"Supabase write_signal_outcome failed: {e}")
        return False


def read_signal_outcomes(limit: int = 100, outcome_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Read signal outcomes from Supabase."""
    client = _get_client()
    if not client:
        return []
    try:
        query = client.table("signal_outcomes").select("*").order("entry_time", desc=True).limit(limit)
        if outcome_filter:
            query = query.eq("outcome", outcome_filter)
        result = query.execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Supabase read_signal_outcomes failed: {e}")
        return []


def update_signal_outcome(signal_id: str, updates: Dict[str, Any]) -> bool:
    """Update a signal outcome (e.g., mark as WIN/LOSS with P&L)."""
    client = _get_client()
    if not client:
        return False
    try:
        client.table("signal_outcomes").update(updates).eq("signal_id", signal_id).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase update_signal_outcome failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════
# DP INTERACTIONS (dark pool learning)
# ═══════════════════════════════════════════════════════════════════

def write_dp_interaction(interaction: Dict[str, Any]) -> bool:
    """Write a dark pool interaction to Supabase."""
    client = _get_client()
    if not client:
        return False
    try:
        row = {
            "timestamp": interaction.get("timestamp", datetime.utcnow().isoformat()),
            "symbol": interaction.get("symbol", ""),
            "level_price": interaction.get("level_price", 0),
            "level_volume": interaction.get("level_volume", 0),
            "level_type": interaction.get("level_type", ""),
            "level_date": interaction.get("level_date"),
            "approach_price": interaction.get("approach_price"),
            "approach_direction": interaction.get("approach_direction"),
            "distance_pct": interaction.get("distance_pct"),
            "touch_count": interaction.get("touch_count", 1),
            "market_trend": interaction.get("market_trend"),
            "volume_vs_avg": interaction.get("volume_vs_avg"),
            "momentum_pct": interaction.get("momentum_pct"),
            "vix_level": interaction.get("vix_level"),
            "time_of_day": interaction.get("time_of_day"),
            "outcome": interaction.get("outcome", "PENDING"),
            "outcome_timestamp": interaction.get("outcome_timestamp"),
            "max_move_pct": interaction.get("max_move_pct", 0),
            "time_to_outcome_min": interaction.get("time_to_outcome_min", 0),
            "price_at_5min": interaction.get("price_at_5min"),
            "price_at_15min": interaction.get("price_at_15min"),
            "price_at_30min": interaction.get("price_at_30min"),
            "price_at_60min": interaction.get("price_at_60min"),
            "notes": interaction.get("notes"),
        }
        client.table("dp_interactions").insert(row).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase write_dp_interaction failed: {e}")
        return False


def read_dp_interactions(symbol: Optional[str] = None, days: int = 7,
                         limit: int = 200) -> List[Dict[str, Any]]:
    """Read dark pool interactions from Supabase."""
    client = _get_client()
    if not client:
        return []
    try:
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        query = (client.table("dp_interactions")
                 .select("*")
                 .gte("timestamp", cutoff)
                 .order("timestamp", desc=True)
                 .limit(limit))
        if symbol:
            query = query.eq("symbol", symbol)
        result = query.execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Supabase read_dp_interactions failed: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════
# DP PATTERNS (win rate learning)
# ═══════════════════════════════════════════════════════════════════

def upsert_dp_pattern(pattern: Dict[str, Any]) -> bool:
    """Upsert a DP pattern to Supabase."""
    client = _get_client()
    if not client:
        return False
    try:
        row = {
            "pattern_name": pattern.get("pattern_name", ""),
            "total_samples": pattern.get("total_samples", 0),
            "bounce_count": pattern.get("bounce_count", 0),
            "break_count": pattern.get("break_count", 0),
            "fade_count": pattern.get("fade_count", 0),
            "last_updated": datetime.utcnow().isoformat(),
        }
        client.table("dp_patterns").upsert(row, on_conflict="pattern_name").execute()
        return True
    except Exception as e:
        logger.error(f"Supabase upsert_dp_pattern failed: {e}")
        return False


def read_dp_patterns() -> List[Dict[str, Any]]:
    """Read all DP patterns from Supabase."""
    client = _get_client()
    if not client:
        return []
    try:
        result = client.table("dp_patterns").select("*").execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Supabase read_dp_patterns failed: {e}")
        return []
