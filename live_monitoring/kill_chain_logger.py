"""
🐺 Kill Chain Signal Logger — Tracks Triple Confluence Daily

Runs as a daemon thread. Every check_interval (default 30min during market hours):
1. Pulls COT divergence state (weekly, from latest CFTC report)
2. Computes GEX proxy (VIX/VIX3M term structure)
3. Computes Down-Volume Ratio (10-day rolling)
4. Detects triple confluence (all 3 active)
5. Logs state changes + fires Discord alerts on activation/deactivation

Backtest results (2018-2026):
  Triple confluence → 78.6% 20d win rate, +2.54% avg return
  OOS (2023-2026): 82.3% win rate (N=96)
  
This IS the edge. Log everything.
"""

import os
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).parent / 'data' / 'kill_chain'
LOG_FILE = LOG_DIR / 'kill_chain_signal_log.json'
STATE_FILE = LOG_DIR / 'kill_chain_state.json'

_signal_log: List[Dict] = []
_lock = threading.Lock()


def get_kill_chain_signals() -> List[Dict]:
    """Return kill chain signal log (called by health endpoint)."""
    with _lock:
        return list(_signal_log)


def _load_log():
    """Load signal log from disk."""
    global _signal_log
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE) as f:
                _signal_log = json.load(f)
            logger.info(f"📋 Loaded {len(_signal_log)} kill chain signal entries")
        except Exception as e:
            logger.warning(f"Could not load kill chain log: {e}")
            _signal_log = []


def _save_log():
    """Persist signal log to disk."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(LOG_FILE, 'w') as f:
            json.dump(_signal_log, f, indent=2, default=str)
    except Exception as e:
        logger.warning(f"Could not save kill chain log: {e}")


def _save_state(state: Dict):
    """Persist current state for resume after restart."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        logger.warning(f"Could not save kill chain state: {e}")


def _load_state() -> Dict:
    """Load last known state."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"triple_active": False, "last_check": None}


def _send_discord(message: str):
    """Send kill chain alert to Discord."""
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        logger.debug("No DISCORD_WEBHOOK_URL set")
        return
    try:
        import requests
        payload = {"content": message}
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            logger.info("🔔 Kill chain alert sent to Discord")
        else:
            logger.warning(f"Discord returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Discord send failed: {e}")


class KillChainLogger:
    """
    Monitors the 3 kill chain layers and logs state changes.
    
    Layers:
      1. COT Divergence: specs NET SHORT + commercials NET LONG
      2. GEX Proxy: VIX/VIX3M < 1.0 (contango = positive gamma)
      3. Dark Pool Proxy: Down-Volume Ratio > 0.55 (selling pressure)
    
    Triple confluence = all 3 active simultaneously.
    """
    
    def __init__(self, check_interval_min: int = 30):
        self.check_interval = check_interval_min * 60
        self._running = False
        
        # Layer states
        self.cot_divergence = False
        self.cot_specs_net = 0
        self.cot_comm_net = 0
        self.cot_date = None
        
        self.gex_positive = False
        self.vix_ratio = 0.0
        self.vix = 0.0
        
        self.dp_selling = False
        self.dvr = 0.0
        
        self.triple_active = False
        self.spy_price = 0.0
        
        _load_log()
        
        # Resume from saved state
        saved = _load_state()
        self.triple_active = saved.get('triple_active', False)
        logger.info(f"🐺 KillChainLogger initialized | resumed triple={self.triple_active}")
    
    def _check_cot(self):
        """Check latest COT report for specs/comm divergence."""
        try:
            from cot_reports import cot_year
            year = datetime.now().year
            data = cot_year(year, cot_report_type='legacy_fut')
            if data is None or len(data) == 0:
                return
            
            sp = data[data['Market and Exchange Names'].str.contains(
                'E-MINI S&P 500', case=False, na=False
            )].copy()
            
            if len(sp) == 0:
                return
            
            import pandas as pd
            sp['date'] = pd.to_datetime(sp['As of Date in Form YYYY-MM-DD'])
            sp = sp.sort_values('date')
            latest = sp.iloc[-1]
            
            specs_long = float(pd.to_numeric(latest['Noncommercial Positions-Long (All)'], errors='coerce') or 0)
            specs_short = float(pd.to_numeric(latest['Noncommercial Positions-Short (All)'], errors='coerce') or 0)
            comm_long = float(pd.to_numeric(latest['Commercial Positions-Long (All)'], errors='coerce') or 0)
            comm_short = float(pd.to_numeric(latest['Commercial Positions-Short (All)'], errors='coerce') or 0)
            
            self.cot_specs_net = specs_long - specs_short
            self.cot_comm_net = comm_long - comm_short
            self.cot_date = str(latest['date'].date()) if hasattr(latest['date'], 'date') else str(latest['date'])
            self.cot_divergence = (self.cot_specs_net < 0) and (self.cot_comm_net > 0)
            
            logger.info(f"📋 COT: specs={self.cot_specs_net:,.0f} comm={self.cot_comm_net:,.0f} "
                        f"div={'✅' if self.cot_divergence else '❌'} (report: {self.cot_date})")
        except Exception as e:
            logger.warning(f"COT check failed: {e}")
    
    def _check_gex_and_dvr(self):
        """Check GEX proxy (VIX term structure) and DVR."""
        try:
            import yfinance as yf
            import pandas as pd
            import numpy as np
            import warnings
            warnings.filterwarnings('ignore')
            
            # Pull recent data
            end = datetime.now()
            start = end - timedelta(days=30)
            
            spy = yf.download('SPY', start=start, end=end, progress=False)
            vix = yf.download('^VIX', start=start, end=end, progress=False)
            vix3m = yf.download('^VIX3M', start=start, end=end, progress=False)
            
            def flat(s):
                if hasattr(s, 'columns'): return s.iloc[:, 0]
                return s
            
            spy_c = flat(spy['Close'])
            spy_v = flat(spy['Volume'])
            vix_c = flat(vix['Close'])
            vix3m_c = flat(vix3m['Close'])
            
            df = pd.DataFrame({
                'close': spy_c, 'volume': spy_v,
                'vix': vix_c, 'vix3m': vix3m_c,
            }).dropna()
            
            if len(df) < 10:
                logger.warning("Not enough data for GEX/DVR check")
                return
            
            # DVR (10-day rolling down-volume ratio)
            df['ret'] = df['close'].pct_change()
            df['is_down'] = (df['ret'] < 0).astype(float)
            df['down_vol'] = (df['volume'] * df['is_down']).rolling(10).sum()
            df['total_vol'] = df['volume'].rolling(10).sum()
            df['dvr'] = df['down_vol'] / df['total_vol']
            
            latest = df.dropna().iloc[-1]
            
            # GEX proxy
            self.vix = float(latest['vix'])
            self.vix_ratio = float(latest['vix']) / float(latest['vix3m']) if float(latest['vix3m']) > 0 else 1.0
            self.gex_positive = self.vix_ratio < 1.0
            
            # DVR
            self.dvr = float(latest['dvr'])
            self.dp_selling = self.dvr > 0.55
            
            # SPY price
            self.spy_price = float(latest['close'])
            
            logger.info(f"⚡ GEX: VIX={self.vix:.1f} ratio={self.vix_ratio:.3f} "
                        f"pos={'✅' if self.gex_positive else '❌'}")
            logger.info(f"🏴 DVR: {self.dvr:.3f} selling={'✅' if self.dp_selling else '❌'}")
            logger.info(f"📈 SPY: ${self.spy_price:.2f}")
        except Exception as e:
            logger.warning(f"GEX/DVR check failed: {e}")
    
    def _check_triple(self):
        """Evaluate triple confluence and log state changes."""
        was_active = self.triple_active
        self.triple_active = self.cot_divergence and self.gex_positive and self.dp_selling
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        entry = {
            "timestamp": now,
            "type": "check",
            "triple_active": self.triple_active,
            "layers": {
                "cot_divergence": self.cot_divergence,
                "cot_specs_net": self.cot_specs_net,
                "cot_comm_net": self.cot_comm_net,
                "cot_date": self.cot_date,
                "gex_positive": self.gex_positive,
                "vix": self.vix,
                "vix_ratio": round(self.vix_ratio, 4),
                "dp_selling": self.dp_selling,
                "dvr": round(self.dvr, 4),
            },
            "spy_price": round(self.spy_price, 2),
        }
        
        # Detect state changes
        if self.triple_active and not was_active:
            entry["type"] = "ACTIVATION"
            entry["event"] = "🔥 TRIPLE CONFLUENCE ACTIVATED"
            logger.info(f"🔥🔥🔥 KILL CHAIN TRIPLE ACTIVATED at SPY=${self.spy_price:.2f}")
            
            msg = (f"🐺🔥 **KILL CHAIN TRIPLE ACTIVATED**\n"
                   f"SPY: ${self.spy_price:.2f}\n"
                   f"COT: Specs {self.cot_specs_net:,.0f} / Comm {self.cot_comm_net:,.0f}\n"
                   f"GEX: Positive (VIX ratio {self.vix_ratio:.3f})\n"
                   f"DVR: {self.dvr:.3f} (selling pressure)\n"
                   f"Historical: **78.6% win rate over 20 trading days**\n"
                   f"Median return: +2.08%")
            _send_discord(msg)
            
        elif not self.triple_active and was_active:
            entry["type"] = "DEACTIVATION"
            entry["event"] = "⚪ TRIPLE CONFLUENCE DEACTIVATED"
            logger.info(f"⚪ Kill chain triple deactivated at SPY=${self.spy_price:.2f}")
            
            # Find activation entry to compute P&L
            activation_price = None
            for e in reversed(_signal_log):
                if e.get("type") == "ACTIVATION":
                    activation_price = e.get("spy_price")
                    break
            
            if activation_price:
                pnl = (self.spy_price - activation_price) / activation_price * 100
                entry["pnl_pct"] = round(pnl, 4)
                entry["activation_price"] = activation_price
                
                msg = (f"🐺⚪ **KILL CHAIN TRIPLE DEACTIVATED**\n"
                       f"Entry: ${activation_price:.2f} → Exit: ${self.spy_price:.2f}\n"
                       f"P&L: {pnl:+.2f}%\n"
                       f"Result: {'✅ WIN' if pnl > 0 else '❌ LOSS'}")
                _send_discord(msg)
        
        # Always log
        with _lock:
            _signal_log.append(entry)
            _save_log()
        
        # Save state for restart recovery
        _save_state({
            "triple_active": self.triple_active,
            "last_check": now,
            "spy_price": self.spy_price,
        })
    
    def run_single_check(self):
        """Run one check cycle (useful for testing)."""
        logger.info("🐺 Kill chain check starting...")
        self._check_cot()
        self._check_gex_and_dvr()
        self._check_triple()
        
        status = "🔥 ACTIVE" if self.triple_active else "⚪ INACTIVE"
        layers = sum([self.cot_divergence, self.gex_positive, self.dp_selling])
        logger.info(f"🐺 Kill chain: {status} ({layers}/3 layers)")
        
        return {
            "triple_active": self.triple_active,
            "layers_active": layers,
            "cot": self.cot_divergence,
            "gex": self.gex_positive,
            "dvr": self.dp_selling,
            "spy": self.spy_price,
        }
    
    def run_forever(self):
        """Main loop — checks every interval during market hours."""
        self._running = True
        logger.info(f"🐺 Kill Chain Logger started | interval={self.check_interval//60}min")
        
        # Run first check immediately
        try:
            self.run_single_check()
        except Exception as e:
            logger.error(f"Initial kill chain check failed: {e}")
        
        while self._running:
            try:
                time.sleep(self.check_interval)
                
                # Only check during extended market hours (7 AM - 5 PM ET)
                from zoneinfo import ZoneInfo
                et = datetime.now(ZoneInfo('US/Eastern'))
                hour = et.hour
                weekday = et.weekday()
                
                if weekday >= 5:  # Weekend
                    logger.debug("Weekend — skipping kill chain check")
                    continue
                
                if hour < 7 or hour >= 17:  # Outside market hours
                    logger.debug("Outside market hours — skipping")
                    continue
                
                self.run_single_check()
                
            except Exception as e:
                logger.error(f"Kill chain check error: {e}", exc_info=True)
                time.sleep(60)  # Back off on error
    
    def stop(self):
        self._running = False


def start_kill_chain_logger_thread(check_interval_min: int = 30):
    """Start the kill chain logger as a daemon thread."""
    kc_logger = KillChainLogger(check_interval_min=check_interval_min)
    thread = threading.Thread(target=kc_logger.run_forever, daemon=True, name="kill-chain-logger")
    thread.start()
    logger.info("🐺 Kill Chain Logger thread started")
    return thread, kc_logger
