"""
📊 Paper Trade Scheduler — Server-Side Release Monitor

Runs as a daemon thread inside the Render web service.
Auto-detects releases from TE calendar, polls for actuals,
runs SurpriseEngine, pulls Alpaca 30-min bars, logs to Discord.

No manual --target needed. Finds today's CRITICAL/HIGH releases automatically.
"""

import os
import json
import logging
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# Log storage (in-memory since Render free has no persistent disk)
_paper_trade_log: List[Dict] = []
_lock = threading.Lock()

LOG_DIR = Path(__file__).parent / 'data' / 'paper_trades'


def get_paper_trades():
    """Return paper trade log (called by health endpoint)."""
    with _lock:
        return list(_paper_trade_log)


def _get_vix():
    """Get current VIX."""
    try:
        import yfinance as yf
        vix = yf.download('^VIX', period='1d', interval='1m', progress=False)
        if len(vix) > 0:
            val = vix['Close'].iloc[-1]
            return round(float(val.iloc[0] if hasattr(val, 'iloc') else val), 2)
    except Exception as e:
        logger.warning(f"VIX fetch failed: {e}")
    return None


def _get_30m_reaction(symbol, release_dt_et):
    """Pull 30-min post-release reaction from Alpaca."""
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        
        api_key = os.getenv('ALPACA_API_KEY')
        secret = os.getenv('ALPACA_SECRET_KEY')
        if not api_key or not secret:
            logger.warning("Alpaca keys not set — skipping 30m bar")
            return None, None
        
        client = StockHistoricalDataClient(api_key, secret)
        
        end = release_dt_et + timedelta(minutes=45)
        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Minute,
            start=release_dt_et,
            end=end,
        )
        bars = client.get_stock_bars(request)
        bar_list = bars[symbol] if symbol in bars else []
        
        if len(bar_list) < 2:
            return None, None
        
        import pytz
        et = pytz.timezone('US/Eastern')
        open_price = bar_list[0].open
        price_30m = None
        
        for bar in bar_list:
            bar_et = bar.timestamp.astimezone(et)
            mins = (bar_et - release_dt_et).total_seconds() / 60
            if 29 <= mins <= 31:
                price_30m = bar.close
                break
        
        if price_30m is None and len(bar_list) >= 30:
            price_30m = bar_list[29].close
        
        pct = round((price_30m - open_price) / open_price * 100, 4) if price_30m else None
        return pct, round(float(open_price), 2)
    except Exception as e:
        logger.warning(f"Alpaca {symbol} fetch failed: {e}")
        return None, None


def _send_discord(paper_trade):
    """Send paper trade result to Discord webhook."""
    webhook = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook:
        return
    
    try:
        import requests as req
        correct = paper_trade.get('correct')
        emoji = '✅' if correct else ('❌' if correct is False else '⚪')
        filtered = '🛑 FILTERED' if paper_trade.get('macro_filtered') else '🟢 CLEAN'
        
        embed = {
            "title": f"📊 PAPER TRADE {emoji} | {paper_trade['event']}",
            "color": 0x00ff00 if correct else (0xff0000 if correct is False else 0x808080),
            "fields": [
                {"name": "Signal", "value": f"{paper_trade['signal']} ({filtered})", "inline": True},
                {"name": "Surprise", "value": f"{paper_trade['surprise_pct']:+.2f}%", "inline": True},
                {"name": "VIX", "value": f"{paper_trade.get('vix_pre', '?')}", "inline": True},
                {"name": "SPY 30m", "value": f"{paper_trade.get('spy_30m_pct', '?')}%", "inline": True},
                {"name": "Predicted", "value": f"SPY{paper_trade.get('pred_spy', '?')}", "inline": True},
                {"name": "Result", "value": f"{emoji} {'CORRECT' if correct else 'WRONG' if correct is False else 'N/A'}", "inline": True},
            ],
            "footer": {"text": f"Paper Trade #{len(_paper_trade_log)} | {datetime.now().strftime('%Y-%m-%d %H:%M ET')}"}
        }
        
        # Add running accuracy
        clean_trades = [t for t in _paper_trade_log if t.get('correct') is not None and not t.get('macro_filtered')]
        if clean_trades:
            wins = sum(1 for t in clean_trades if t['correct'])
            embed["fields"].append({
                "name": "Running Accuracy (clean)",
                "value": f"{wins}/{len(clean_trades)} = {wins/len(clean_trades)*100:.0f}%",
                "inline": False
            })
        
        req.post(webhook, json={"embeds": [embed]}, timeout=10)
        logger.info("✅ Paper trade sent to Discord")
    except Exception as e:
        logger.error(f"Discord send failed: {e}")


class PaperTradeScheduler:
    """
    Server-side paper trade monitor.
    
    Lifecycle per day:
    1. On startup / each morning: scrape TE calendar for today's CRITICAL/HIGH releases
    2. For each release: poll every 60s until actual appears
    3. Run SurpriseEngine.compute_with_macro()
    4. Wait 35 min, pull Alpaca 30m bar
    5. Log result + send to Discord
    6. Sleep until next release or next day
    """
    
    # Events we care about (keywords to match in TE event names)
    WATCHED_EVENTS = {
        'CPI': {'keywords': ['inflation rate', 'cpi'], 'release_time': '08:30'},
        'Housing': {'keywords': ['existing home sales'], 'release_time': '10:00'},
    }
    
    def __init__(self):
        self.running = False
        self._detector = None
        
    def _get_detector(self):
        """Lazy init to avoid import issues at startup."""
        if self._detector is None:
            try:
                from live_monitoring.enrichment.apis.release_detector import ReleaseDetector
                self._detector = ReleaseDetector()
                logger.info("📊 ReleaseDetector initialized for paper trading")
            except Exception as e:
                logger.error(f"ReleaseDetector init failed: {e}")
        return self._detector
    
    def _find_todays_releases(self):
        """Check TE calendar for today's watched releases."""
        try:
            from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
            scraper = TECalendarScraper()
            today = scraper.get_today()
            
            matches = []
            for event in today:
                for name, config in self.WATCHED_EVENTS.items():
                    for kw in config['keywords']:
                        if kw.lower() in event.event.lower():
                            matches.append({
                                'name': name,
                                'event': event.event,
                                'time': event.time or config['release_time'],
                                'actual': event.actual,
                                'consensus': event.consensus,
                                'forecast': event.forecast,
                                'released': event.has_actual(),
                            })
                            break
            
            return matches
        except Exception as e:
            logger.error(f"Calendar scrape failed: {e}")
            return []
    
    def _poll_for_release(self, target_keyword, max_wait_min=60, poll_interval=60):
        """Poll TE for a specific release until actual appears."""
        detector = self._get_detector()
        if not detector:
            return None
        
        start = time.time()
        while time.time() - start < max_wait_min * 60:
            try:
                alerts = detector.check_for_releases()
                for alert in alerts:
                    if target_keyword.lower() in alert.event_name.lower():
                        logger.info(f"🎯 DETECTED: {alert.event_name} — {alert.signal}")
                        return alert
            except Exception as e:
                logger.error(f"Poll error: {e}")
            
            elapsed = int(time.time() - start)
            logger.info(f"⏳ Waiting for {target_keyword}... ({elapsed}s)")
            time.sleep(poll_interval)
        
        logger.warning(f"⚠️ {target_keyword} not detected within {max_wait_min} min")
        return None
    
    def _process_alert(self, alert, release_time_str):
        """Process a detected alert: wait for 30m bar, log, send to Discord."""
        import pytz
        et = pytz.timezone('US/Eastern')
        now_et = datetime.now(et)
        
        # Get VIX
        vix = _get_vix()
        
        # Calculate release datetime
        try:
            hour, minute = map(int, release_time_str.replace('AM', '').replace('PM', '').strip().split(':'))
            release_dt = et.localize(datetime(now_et.year, now_et.month, now_et.day, hour, minute))
        except:
            release_dt = now_et
        
        # Wait for 30m bar
        time_since = (now_et - release_dt).total_seconds()
        wait_needed = max(0, 35 * 60 - time_since)
        if wait_needed > 0:
            logger.info(f"⏰ Waiting {wait_needed:.0f}s for 30m bar...")
            time.sleep(wait_needed)
        
        # Pull reactions
        spy_30m, spy_open = _get_30m_reaction('SPY', release_dt)
        
        # Check correctness
        pred_spy = alert.directions.get('SPY', '?')
        correct = None
        if spy_30m is not None and pred_spy != '?':
            correct = (pred_spy == '↓' and spy_30m < 0) or (pred_spy == '↑' and spy_30m > 0)
        
        is_filtered = alert.debug.get('macro_dovish_suppressed', False)
        
        paper_trade = {
            'timestamp': datetime.now(et).isoformat(),
            'event': alert.event_name,
            'actual': alert.actual,
            'consensus': alert.consensus,
            'surprise_pct': alert.surprise_pct,
            'signal': str(alert.signal),
            'confidence': alert.confidence,
            'directions': alert.directions,
            'category': alert.category,
            'vix_pre': vix,
            'macro_filtered': is_filtered,
            'spy_open': spy_open,
            'spy_30m_pct': spy_30m,
            'pred_spy': pred_spy,
            'correct': correct,
        }
        
        # Store in memory
        with _lock:
            _paper_trade_log.append(paper_trade)
        
        # Try to persist to disk
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            log_file = LOG_DIR / 'paper_trade_log.json'
            with _lock:
                with open(log_file, 'w') as f:
                    json.dump(_paper_trade_log, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Disk log failed (expected on Render): {e}")
        
        # Send to Discord
        _send_discord(paper_trade)
        
        logger.info(f"📊 Paper trade logged: {alert.event_name} → {'✅' if correct else '❌'}")
        return paper_trade
    
    def run_forever(self):
        """Main loop — runs continuously, checking for releases each day."""
        self.running = True
        
        logger.info("═" * 60)
        logger.info("📊 PAPER TRADE SCHEDULER STARTED")
        logger.info("   Watching: CPI, Housing (Existing Home Sales)")
        logger.info("   Mode: auto-detect from TE calendar")
        logger.info("═" * 60)
        
        # Load any existing log from disk
        try:
            log_file = LOG_DIR / 'paper_trade_log.json'
            if log_file.exists():
                with open(log_file) as f:
                    existing = json.load(f)
                with _lock:
                    _paper_trade_log.extend(existing)
                logger.info(f"📂 Loaded {len(existing)} existing paper trades")
        except Exception:
            pass
        
        while self.running:
            try:
                import pytz
                et = pytz.timezone('US/Eastern')
                now_et = datetime.now(et)
                
                # Only operate during market hours (7 AM - 5 PM ET weekdays)
                if now_et.weekday() >= 5:  # Weekend
                    logger.info("📊 Weekend — sleeping 6 hours")
                    time.sleep(6 * 3600)
                    continue
                
                if now_et.hour < 7:
                    sleep_until_7 = (7 - now_et.hour) * 3600 - now_et.minute * 60
                    logger.info(f"📊 Pre-market — sleeping {sleep_until_7}s until 7 AM ET")
                    time.sleep(max(60, sleep_until_7))
                    continue
                
                if now_et.hour >= 17:
                    logger.info("📊 After hours — sleeping until tomorrow 7 AM ET")
                    time.sleep(14 * 3600)  # ~14 hours
                    continue
                
                # Check today's calendar
                releases = self._find_todays_releases()
                pending = [r for r in releases if not r['released']]
                
                if not pending:
                    logger.info(f"📊 No pending watched releases today. Checking again in 30 min.")
                    time.sleep(1800)
                    continue
                
                logger.info(f"📊 Found {len(pending)} pending release(s): {[r['name'] for r in pending]}")
                
                for release in pending:
                    # Calculate when to start polling (15 min before release)
                    try:
                        time_str = release['time'].replace('AM', '').replace('PM', '').strip()
                        parts = time_str.split(':')
                        release_hour = int(parts[0])
                        release_min = int(parts[1]) if len(parts) > 1 else 0
                        
                        # Handle PM times from TE (they use 24h or AM/PM)
                        if 'PM' in release['time'] and release_hour < 12:
                            release_hour += 12
                        
                        release_dt = et.localize(datetime(now_et.year, now_et.month, now_et.day, release_hour, release_min))
                        poll_start = release_dt - timedelta(minutes=5)
                        
                        if now_et < poll_start:
                            wait = (poll_start - now_et).total_seconds()
                            logger.info(f"📊 {release['name']} at {release['time']} ET — waiting {wait:.0f}s to start polling")
                            time.sleep(max(0, wait))
                    except Exception as e:
                        logger.warning(f"Time parse error for {release['name']}: {e}")
                    
                    # Poll for the release
                    keywords = self.WATCHED_EVENTS[release['name']]['keywords']
                    alert = self._poll_for_release(
                        target_keyword=keywords[0],
                        max_wait_min=60,
                        poll_interval=60,
                    )
                    
                    if alert:
                        self._process_alert(alert, release.get('time', '10:00'))
                    else:
                        logger.warning(f"⚠️ Failed to detect {release['name']}")
                
                # All releases processed — sleep 2 hours before re-checking
                logger.info("📊 All pending releases processed. Sleeping 2 hours.")
                time.sleep(7200)
                
            except Exception as e:
                logger.error(f"📊 Scheduler error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(300)  # Wait 5 min on error
    
    def stop(self):
        self.running = False


def start_scheduler_thread():
    """Start the paper trade scheduler as a daemon thread."""
    scheduler = PaperTradeScheduler()
    thread = threading.Thread(
        target=scheduler.run_forever,
        daemon=True,
        name="PaperTradeScheduler"
    )
    thread.start()
    logger.info("📊 Paper trade scheduler thread started")
    return thread, scheduler
