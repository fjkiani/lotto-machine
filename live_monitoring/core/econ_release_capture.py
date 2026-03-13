"""
📊 ECONOMIC RELEASE CAPTURE

Polls FRED for the latest economic releases and:
  1. Writes new releases to economic_releases DB
  2. Creates alerts in alerts_history DB
  3. Calculates surprise vs consensus (when available)

Designed to run as a background thread, polling every 15 min.
Detects CPI, PCE, Core PCE, GDP, PPI, Unemployment, Nonfarm Payrolls, Jobless Claims.
"""

import os
import sqlite3
import logging
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Root of project (data/ dir)
ROOT = Path(__file__).resolve().parent.parent.parent

# FRED series → human names + expected release frequency + consensus source hints
TRACKED_RELEASES = {
    "CPI":          {"fred_id": "CPIAUCSL",  "name": "CPI (All Urban Consumers)",     "type": "cpi",        "freq": "monthly"},
    "CORE_CPI":     {"fred_id": "CPILFESL",  "name": "Core CPI (excl Food & Energy)", "type": "core_cpi",   "freq": "monthly"},
    "PCE":          {"fred_id": "PCEPI",     "name": "PCE Price Index",               "type": "pce",        "freq": "monthly"},
    "CORE_PCE":     {"fred_id": "PCEPILFE",  "name": "Core PCE (excl Food & Energy)", "type": "core_pce",   "freq": "monthly"},
    "GDP":          {"fred_id": "GDP",       "name": "Gross Domestic Product",        "type": "gdp",        "freq": "quarterly"},
    "UNEMPLOYMENT": {"fred_id": "UNRATE",    "name": "Unemployment Rate",             "type": "unemployment","freq": "monthly"},
    "NONFARM":      {"fred_id": "PAYEMS",    "name": "Nonfarm Payrolls",              "type": "nonfarm",    "freq": "monthly"},
    "PPI":          {"fred_id": "PPIACO",    "name": "PPI (All Commodities)",         "type": "ppi",        "freq": "monthly"},
    "RETAIL_SALES": {"fred_id": "RSAFS",     "name": "Retail Sales",                  "type": "retail_sales","freq": "monthly"},
    "HOUSING":      {"fred_id": "EXHOSLUSM495S", "name": "Existing Home Sales",       "type": "housing",    "freq": "monthly"},
    "CLAIMS":       {"fred_id": "ICSA",      "name": "Initial Jobless Claims",        "type": "claims",     "freq": "weekly"},
    "DURABLE":      {"fred_id": "DGORDER",   "name": "Durable Goods Orders",          "type": "durable_goods","freq": "monthly"},
    "FED_FUNDS":    {"fred_id": "FEDFUNDS",  "name": "Federal Funds Rate",            "type": "fed_funds",  "freq": "monthly"},
}


def _econ_db_path() -> Path:
    return ROOT / "data" / "economic_intelligence.db"


def _alerts_db_path() -> Path:
    return ROOT / "data" / "alerts_history.db"


def _get_econ_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_econ_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def _get_alerts_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_alerts_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def _get_last_captured_date(conn: sqlite3.Connection, event_type: str) -> Optional[str]:
    """Get the most recent date we captured for this event type."""
    row = conn.execute(
        "SELECT MAX(date) as latest FROM economic_releases WHERE event_type = ?",
        (event_type,)
    ).fetchone()
    return row['latest'] if row and row['latest'] else None


def _write_release(conn: sqlite3.Connection, release: dict) -> bool:
    """Write a release to economic_releases table. Returns True if new."""
    try:
        conn.execute("""
            INSERT OR IGNORE INTO economic_releases (
                date, time, event_type, event_name,
                actual, previous, surprise_pct,
                source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            release['date'],
            release.get('time', '08:30'),
            release['event_type'],
            release['event_name'],
            release['actual'],
            release.get('previous'),
            release.get('surprise_pct'),
            'fred_capture',
            datetime.now().isoformat(),
        ))
        conn.commit()
        return conn.total_changes > 0
    except sqlite3.IntegrityError:
        return False  # Already exists (UNIQUE constraint)
    except Exception as e:
        logger.error(f"Failed to write release {release['event_name']}: {e}")
        return False


def _write_alert(release: dict):
    """Write an alert to alerts_history.db for the frontend."""
    try:
        conn = _get_alerts_conn()
        conn.execute("""
            INSERT INTO alerts (alert_type, symbol, title, description, source, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            'economic_release',
            'SPY',
            f"📊 ECON DATA: {release['event_name']}",
            f"Actual: {release['actual']} | Previous: {release.get('previous', 'N/A')} | "
            f"Change: {release.get('surprise_pct', 0):+.2f}%",
            'fred_capture',
            datetime.now().isoformat(),
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to write alert for {release['event_name']}: {e}")


def capture_all_releases() -> dict:
    """
    Poll FRED for all tracked economic releases.
    Detect new data and write to DB + create alerts.
    
    Returns summary of what was captured.
    """
    from live_monitoring.enrichment.apis.fred_client import FREDClient

    fred = FREDClient()
    if not fred.api_key:
        logger.warning("⚠️ FRED_API_KEY not set — skipping economic capture")
        return {"status": "no_api_key", "captured": 0}

    econ_conn = _get_econ_conn()
    captured = []
    checked = 0
    errors = []

    for key, meta in TRACKED_RELEASES.items():
        try:
            release = fred.get_indicator(key)
            if not release:
                errors.append(f"{key}: no data from FRED")
                continue

            checked += 1

            # Check if this is newer than what we have
            last_date = _get_last_captured_date(econ_conn, meta['type'])

            if last_date and release.date <= last_date:
                continue  # Already captured this release

            # New release detected!
            release_data = {
                'date': release.date,
                'event_type': meta['type'],
                'event_name': meta['name'],
                'actual': release.value,
                'previous': release.previous_value,
                'surprise_pct': release.change_pct,
            }

            if _write_release(econ_conn, release_data):
                captured.append(release_data)
                _write_alert(release_data)
                logger.info(f"✅ Captured: {meta['name']} = {release.value} ({release.change_pct:+.2f}%) date={release.date}")

        except Exception as e:
            errors.append(f"{key}: {e}")
            logger.error(f"❌ Error capturing {key}: {e}")

    econ_conn.close()

    summary = {
        "status": "ok",
        "checked": checked,
        "captured": len(captured),
        "releases": captured,
        "errors": errors,
        "timestamp": datetime.now().isoformat(),
    }

    if captured:
        logger.info(f"📊 Economic capture: {len(captured)} new releases captured")
    else:
        logger.info(f"📊 Economic capture: no new releases (checked {checked} series)")

    return summary


def _capture_loop(interval_minutes: int = 15):
    """Background loop that polls FRED periodically."""
    logger.info(f"📊 Economic release capture loop started (every {interval_minutes}m)")

    # First capture immediately
    try:
        result = capture_all_releases()
        logger.info(f"📊 Initial capture: {result.get('captured', 0)} new releases")
    except Exception as e:
        logger.error(f"📊 Initial capture failed: {e}")

    while True:
        try:
            time.sleep(interval_minutes * 60)
            capture_all_releases()
        except Exception as e:
            logger.error(f"📊 Capture loop error: {e}")
            time.sleep(60)  # Wait 1 min on error before retry


def start_capture_thread(interval_minutes: int = 15) -> Tuple[threading.Thread, None]:
    """Start the economic release capture as a daemon thread."""
    thread = threading.Thread(
        target=_capture_loop,
        args=(interval_minutes,),
        daemon=True,
        name="econ-release-capture"
    )
    thread.start()
    return thread, None  # Return tuple for consistency with other thread starters
