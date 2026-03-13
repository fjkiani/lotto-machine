"""
Pre-Market Scheduler — Restart-resilient automated pipeline.

Runs 3 stages on a schedule (US/Eastern):
  Stage 1 (INGEST):     06:00–07:30 — pulls DP, walls, SV data, caches to disk
  Stage 2 (CONFLUENCE):  07:30–07:45 — runs SignalIntelEngine, writes gate_signals_today.json
  Stage 3 (BRIEF):       07:45–08:00 — generates morning_brief.json

RESTART RESILIENCE:
  Each stage writes a day-stamp file: /tmp/premarket_stages/{YYYY-MM-DD}_{stage}.done
  On startup, the scheduler checks which stages ran today and re-runs any missed ones.
  If Render restarts at 07:32, it sees INGEST.done exists but CONFLUENCE.done doesn't,
  so it re-runs CONFLUENCE + BRIEF immediately.

Also runs a 16:05 ET post-close brief update (captures close defense data).
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, date
from typing import Optional

logger = logging.getLogger(__name__)

STAGE_DIR = "/tmp/premarket_stages"
BRIEF_DIR = "/tmp/morning_briefs"
CACHE_DIR = "/tmp/premarket_cache"


def _et_now():
    """Current time in US/Eastern."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("US/Eastern"))
    except ImportError:
        try:
            import pytz
            return datetime.now(pytz.timezone("US/Eastern"))
        except ImportError:
            # Render fallback: UTC - 4 (EDT) or UTC - 5 (EST)
            from datetime import timedelta
            utc_now = datetime.utcnow()
            # Simple DST check (March-Nov = EDT)
            month = utc_now.month
            offset = 4 if 3 <= month <= 11 else 5
            return utc_now - timedelta(hours=offset)


def _stage_done(stage: str) -> bool:
    """Check if a stage already ran today."""
    today = date.today().isoformat()
    return os.path.exists(os.path.join(STAGE_DIR, f"{today}_{stage}.done"))


def _mark_stage(stage: str):
    """Mark a stage as complete for today."""
    os.makedirs(STAGE_DIR, exist_ok=True)
    today = date.today().isoformat()
    path = os.path.join(STAGE_DIR, f"{today}_{stage}.done")
    with open(path, "w") as f:
        f.write(datetime.now().isoformat())
    logger.info(f"✅ Stage {stage} marked done for {today}")


def run_ingest() -> dict:
    """Stage 1: Pull and cache all data sources."""
    logger.info("📡 INGEST: Starting data pull...")
    results = {}

    # Pull DP snapshots for SPY/QQQ/IWM
    try:
        from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
        client = StockgridClient(cache_ttl=60)
        for sym in ["SPY", "QQQ", "IWM"]:
            dp = client.get_ticker_latest(sym)
            if dp:
                results[f"dp_{sym}"] = {"sv_pct": dp.short_volume_pct, "date": dp.date}
        # Option walls
        for sym in ["SPY", "QQQ", "IWM"]:
            walls = client.get_option_walls_today(sym)
            if walls:
                results[f"walls_{sym}"] = {"call": walls.call_wall, "put": walls.put_wall, "poc": walls.poc}
        results["ingest_status"] = "ok"
    except Exception as e:
        logger.error(f"INGEST failed: {e}")
        results["ingest_status"] = f"error: {e}"

    # Write cache
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"{date.today().isoformat()}_ingest.json")
    with open(cache_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    _mark_stage("ingest")
    logger.info(f"📡 INGEST complete: {len(results)} items cached")
    return results


def run_confluence() -> dict:
    """Stage 2: Run SignalIntelEngine, write gated signals."""
    logger.info("🔄 CONFLUENCE: Running signal intel engine...")
    try:
        from live_monitoring.enrichment.apis.signal_intel_engine import SignalIntelEngine
        engine = SignalIntelEngine()
        report = engine.generate_report()

        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, f"{date.today().isoformat()}_confluence.json")
        with open(path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        _mark_stage("confluence")
        logger.info(f"🔄 CONFLUENCE complete: verdict={report.get('verdict', {}).get('signal', '?')}")
        return report
    except Exception as e:
        logger.error(f"CONFLUENCE failed: {e}", exc_info=True)
        return {"error": str(e)}


def run_brief(force: bool = False) -> dict:
    """Stage 3: Generate morning brief with DP divergence gating."""
    logger.info("📋 BRIEF: Generating morning brief...")
    try:
        from live_monitoring.enrichment.apis.morning_brief_generator import MorningBriefGenerator
        gen = MorningBriefGenerator()
        brief = gen.generate(force=force)

        _mark_stage("brief")
        logger.info(f"📋 BRIEF complete: verdict={brief.get('verdict')} | approved={len(brief.get('approved_tickers', []))} | blocked={len(brief.get('blocked_tickers', []))}")
        return brief
    except Exception as e:
        logger.error(f"BRIEF failed: {e}", exc_info=True)
        return {"error": str(e)}


def run_all_stages(force: bool = False):
    """Run all stages, skipping any already done today (unless force=True)."""
    logger.info("🚀 Pre-market pipeline starting...")
    et = _et_now()
    logger.info(f"   Current ET: {et.strftime('%H:%M:%S')} | Date: {date.today().isoformat()}")

    if force or not _stage_done("ingest"):
        run_ingest()
    else:
        logger.info("⏭️ INGEST already done today, skipping")

    if force or not _stage_done("confluence"):
        run_confluence()
    else:
        logger.info("⏭️ CONFLUENCE already done today, skipping")

    if force or not _stage_done("brief"):
        run_brief(force=force)
    else:
        logger.info("⏭️ BRIEF already done today, skipping")

    logger.info("✅ Pre-market pipeline complete")


def scheduler_loop():
    """
    Main scheduler loop. Checks every 5 minutes if any stage is due.

    Schedule (ET):
      06:00  → run INGEST (if not done)
      07:30  → run CONFLUENCE (if not done)
      07:45  → run BRIEF (if not done)
      16:05  → run BRIEF again (post-close update with close defense)

    On startup: immediately run any missed stages for today.
    """
    # ── STARTUP: catch up any missed stages ──────────────────────────
    et = _et_now()
    h = et.hour
    logger.info(f"📅 Scheduler starting at {et.strftime('%H:%M ET')}. Checking for missed stages...")

    # If it's past 6:00 ET and ingest hasn't run, run it now
    if h >= 6 and not _stage_done("ingest"):
        logger.info("🔁 Missed INGEST — running now (restart recovery)")
        try:
            run_ingest()
        except Exception as e:
            logger.error(f"Recovery INGEST failed: {e}")

    # If it's past 7:30 ET and confluence hasn't run, run it now
    if h >= 7 and not _stage_done("confluence"):
        logger.info("🔁 Missed CONFLUENCE — running now (restart recovery)")
        try:
            run_confluence()
        except Exception as e:
            logger.error(f"Recovery CONFLUENCE failed: {e}")

    # If it's past 7:45 ET and brief hasn't run, run it now
    if h >= 7 and not _stage_done("brief"):
        logger.info("🔁 Missed BRIEF — running now (restart recovery)")
        try:
            run_brief(force=True)
        except Exception as e:
            logger.error(f"Recovery BRIEF failed: {e}")

    # ── MAIN LOOP ────────────────────────────────────────────────────
    while True:
        try:
            time.sleep(300)  # Check every 5 minutes
            et = _et_now()
            h, m = et.hour, et.minute

            # 06:00–06:10 ET → INGEST
            if h == 6 and m < 10 and not _stage_done("ingest"):
                run_ingest()

            # 07:30–07:40 ET → CONFLUENCE
            if h == 7 and 30 <= m < 40 and not _stage_done("confluence"):
                run_confluence()

            # 07:45–07:55 ET → BRIEF
            if h == 7 and 45 <= m < 55 and not _stage_done("brief"):
                run_brief()

            # 16:05–16:15 ET → POST-CLOSE BRIEF UPDATE
            if h == 16 and 5 <= m < 15 and not _stage_done("postclose"):
                logger.info("🔔 Post-close brief update...")
                run_brief(force=True)
                _mark_stage("postclose")

            # ── INTRADAY GUARDIAN — every 15 min during market hours ──
            if (h == 9 and m >= 30) or (10 <= h <= 15) or (h == 16 and m == 0):
                if m % 15 < 5:  # scheduler checks every 5 min, catch 15-min marks
                    try:
                        from live_monitoring.intraday_guardian import IntradayGuardian
                        guardian = IntradayGuardian()
                        snapshot = guardian.check()
                        logger.info(
                            f"🛡️ Guardian: thesis={'VALID' if snapshot.get('thesis_valid') else 'INVALID'} "
                            f"| SPY=${snapshot.get('spy_price')} | wall={snapshot.get('wall_status')}"
                        )
                    except Exception as e:
                        logger.error(f"Guardian failed: {e}")

        except Exception as e:
            logger.error(f"Scheduler loop error: {e}", exc_info=True)
            time.sleep(60)


def start_scheduler_thread() -> threading.Thread:
    """Start the scheduler as a daemon thread."""
    t = threading.Thread(target=scheduler_loop, name="premarket_scheduler", daemon=True)
    t.start()
    logger.info("📅 Pre-market scheduler thread started")
    return t
