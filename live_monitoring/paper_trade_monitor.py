"""
📊 Paper Trade Monitor — Live Release Detection + Logging

Uses our existing pipeline:
  TECalendarScraper → ReleaseDetector → SurpriseEngine.compute_with_macro()

Polls for releases, runs the engine, pulls Alpaca 30m bars, logs results.

Usage:
  # Housing today (10:00 AM ET):
  python -m live_monitoring.paper_trade_monitor --target "Existing Home" --release-time 10:00

  # CPI tomorrow (8:30 AM ET):  
  python -m live_monitoring.paper_trade_monitor --target "CPI" --release-time 08:30
  
  # Or just watch everything:
  python -m live_monitoring.paper_trade_monitor
"""

import os
import sys
import json
import logging
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = Path(__file__).parent / 'data' / 'paper_trades'
LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_vix_now():
    """Get current VIX from yfinance."""
    try:
        import yfinance as yf
        vix = yf.download('^VIX', period='1d', interval='1m', progress=False)
        if len(vix) > 0:
            return round(float(vix['Close'].iloc[-1].iloc[0] if hasattr(vix['Close'].iloc[-1], 'iloc') else vix['Close'].iloc[-1]), 2)
    except Exception as e:
        logger.warning(f"VIX fetch failed: {e}")
    return None


def get_alpaca_30m_reaction(symbol, release_dt_et):
    """Get 30-min post-release SPY/TLT reaction from Alpaca."""
    from dotenv import load_dotenv
    load_dotenv()
    
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    import pytz
    
    client = StockHistoricalDataClient(
        os.getenv('ALPACA_API_KEY'),
        os.getenv('ALPACA_SECRET_KEY'),
    )
    
    et = pytz.timezone('US/Eastern')
    start = release_dt_et
    end = release_dt_et + timedelta(minutes=45)
    
    try:
        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
        )
        bars = client.get_stock_bars(request)
        bar_list = bars[symbol] if symbol in bars else []
        
        if len(bar_list) < 2:
            return None, None
        
        open_price = bar_list[0].open
        
        # Find 30-min mark
        price_30m = None
        for bar in bar_list:
            bar_et = bar.timestamp.astimezone(et)
            mins = (bar_et - release_dt_et).total_seconds() / 60
            if 29 <= mins <= 31:
                price_30m = bar.close
                break
        
        if price_30m is None and len(bar_list) >= 30:
            price_30m = bar_list[29].close
        
        pct_30m = round((price_30m - open_price) / open_price * 100, 4) if price_30m else None
        return pct_30m, round(float(open_price), 2)
    
    except Exception as e:
        logger.warning(f"Alpaca {symbol} fetch failed: {e}")
        return None, None


def run_monitor(target_event=None, release_time='08:30', poll_interval=60, max_wait_min=45):
    """Poll for a release, run the engine, log paper trade result."""
    from dotenv import load_dotenv
    load_dotenv()
    
    from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
    from live_monitoring.enrichment.apis.release_detector import ReleaseDetector
    
    logger.info(f"{'═'*60}")
    logger.info(f"📊 PAPER TRADE MONITOR")
    logger.info(f"   Target: {target_event or 'ALL releases'}")
    logger.info(f"   Release time: {release_time} ET")
    logger.info(f"   Polling every {poll_interval}s for {max_wait_min} min")
    logger.info(f"{'═'*60}")
    
    detector = ReleaseDetector()
    
    # Get VIX before release
    vix = get_vix_now()
    logger.info(f"📈 Pre-release VIX: {vix or 'unavailable'}")
    
    # Poll loop
    start_time = time.time()
    detected = []
    
    while time.time() - start_time < max_wait_min * 60:
        try:
            alerts = detector.check_for_releases()
            
            for alert in alerts:
                # Filter if target specified
                if target_event and target_event.lower() not in alert.event_name.lower():
                    continue
                
                logger.info(f"\n{'🔥'*20}")
                logger.info(f"🎯 RELEASE DETECTED: {alert.event_name}")
                logger.info(f"   Actual:    {alert.actual}")
                logger.info(f"   Consensus: {alert.consensus}")
                logger.info(f"   Surprise:  {alert.surprise_pct:+.2f}%")
                logger.info(f"   Signal:    {alert.signal}")
                logger.info(f"   Confidence:{alert.confidence:.2f}")
                logger.info(f"   Direction: {alert.directions}")
                logger.info(f"   Category:  {alert.category}")
                logger.info(f"   Macro filt:{alert.debug.get('macro_dovish_suppressed', False)}")
                logger.info(f"{'🔥'*20}\n")
                
                detected.append(alert)
            
            if detected:
                break
            
            elapsed = int(time.time() - start_time)
            logger.info(f"⏳ No release yet ({elapsed}s elapsed). Polling again in {poll_interval}s...")
            time.sleep(poll_interval)
            
        except Exception as e:
            logger.error(f"Poll error: {e}")
            time.sleep(poll_interval)
    
    if not detected:
        logger.warning("⚠️ No matching release detected within polling window.")
        return
    
    # Wait 35 minutes for 30-min bar to form
    alert = detected[0]
    logger.info(f"\n⏰ Release detected. Waiting 35 min for 30-min bar to form...")
    
    import pytz
    et = pytz.timezone('US/Eastern')
    release_dt = et.localize(datetime.strptime(
        f"{datetime.now(et).strftime('%Y-%m-%d')} {release_time}",
        '%Y-%m-%d %H:%M'
    ))
    
    # Calculate how long to wait
    now_et = datetime.now(et)
    time_since_release = (now_et - release_dt).total_seconds()
    wait_needed = max(0, 35 * 60 - time_since_release)
    
    if wait_needed > 0:
        logger.info(f"   Waiting {wait_needed:.0f}s until 30m mark...")
        time.sleep(wait_needed)
    
    # Pull 30-min reactions
    spy_30m, spy_open = get_alpaca_30m_reaction('SPY', release_dt)
    tlt_30m, tlt_open = get_alpaca_30m_reaction('TLT', release_dt)
    
    logger.info(f"\n{'═'*60}")
    logger.info(f"📊 30-MIN REACTION:")
    logger.info(f"   SPY: {spy_30m:+.4f}% (open={spy_open})" if spy_30m else "   SPY: unavailable")
    logger.info(f"   TLT: {tlt_30m:+.4f}% (open={tlt_open})" if tlt_30m else "   TLT: unavailable")
    
    # Check if direction was correct
    pred_spy = alert.directions.get('SPY', '?')
    correct = None
    if spy_30m is not None and pred_spy != '?':
        correct = (pred_spy == '↓' and spy_30m < 0) or (pred_spy == '↑' and spy_30m > 0)
        logger.info(f"   Prediction: SPY{pred_spy} → {'✅ CORRECT' if correct else '❌ WRONG'}")
    
    # Is this macro-filtered?
    is_filtered = alert.debug.get('macro_dovish_suppressed', False)
    
    # Log paper trade
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
        'tlt_30m_pct': tlt_30m,
        'pred_spy': pred_spy,
        'correct': correct,
        'debug': {k: v for k, v in alert.debug.items() if not callable(v)},
    }
    
    # Append to log
    log_file = LOG_DIR / 'paper_trade_log.json'
    existing = []
    if log_file.exists():
        with open(log_file) as f:
            existing = json.load(f)
    existing.append(paper_trade)
    with open(log_file, 'w') as f:
        json.dump(existing, f, indent=2, default=str)
    
    logger.info(f"\n💾 Paper trade logged to: {log_file}")
    logger.info(f"   Total paper trades: {len(existing)}")
    
    # Print running accuracy
    trades_with_result = [t for t in existing if t.get('correct') is not None]
    clean_trades = [t for t in trades_with_result if not t.get('macro_filtered')]
    if clean_trades:
        wins = sum(1 for t in clean_trades if t['correct'])
        logger.info(f"   Running accuracy (clean): {wins}/{len(clean_trades)} = {wins/len(clean_trades)*100:.0f}%")
    
    logger.info(f"\n{'═'*60}")
    logger.info(f"📊 PAPER TRADE COMPLETE")
    logger.info(f"{'═'*60}")
    
    return paper_trade


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Paper Trade Monitor')
    parser.add_argument('--target', type=str, default=None, help='Target event keyword (e.g., "CPI", "Home")')
    parser.add_argument('--release-time', type=str, default='08:30', help='Release time in ET (HH:MM)')
    parser.add_argument('--poll', type=int, default=60, help='Poll interval in seconds')
    parser.add_argument('--max-wait', type=int, default=45, help='Max wait in minutes')
    
    args = parser.parse_args()
    
    run_monitor(
        target_event=args.target,
        release_time=args.release_time,
        poll_interval=args.poll,
        max_wait_min=args.max_wait,
    )
