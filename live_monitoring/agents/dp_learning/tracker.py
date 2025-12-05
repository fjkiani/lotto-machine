"""
🧠 DP Learning Engine - Outcome Tracker
=======================================
Monitors price after alert to detect bounce vs break.

FIXED: Now properly determines if level HELD or BROKE by:
1. Tracking min/max prices during observation period
2. Waiting minimum 5 minutes before determining outcome
3. Checking if price actually breached the level
4. Better logic for support vs resistance
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, List

import yfinance as yf

from .models import DPInteraction, DPOutcome, Outcome, LevelType
from .database import DPDatabase

logger = logging.getLogger(__name__)


class OutcomeTracker:
    """
    Tracks interactions after alert to determine outcome.
    
    After an alert fires:
    1. Track price continuously for 5-60 minutes
    2. Record min/max prices to see if level was breached
    3. Determine if BOUNCE (level held), BREAK (level breached), or FADE
    4. Update database with outcome
    """
    
    # Minimum time before determining outcome (minutes)
    MIN_TRACKING_TIME = 5
    
    # Maximum tracking time (minutes)
    MAX_TRACKING_TIME = 60
    
    # Thresholds
    BREACH_THRESHOLD = 0.001   # 0.1% through level = breach
    BOUNCE_CONFIRM = 0.002     # 0.2% reversal confirms bounce
    BREAK_CONFIRM = 0.003      # 0.3% continuation confirms break
    
    def __init__(self, database: DPDatabase, on_outcome: Callable = None):
        self.db = database
        self.on_outcome = on_outcome  # Callback when outcome determined
        
        # Active tracking jobs
        self.tracking_jobs: Dict[int, dict] = {}  # interaction_id -> job info
        
        # Background thread for tracking
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        logger.info("⏱️ OutcomeTracker initialized (FIXED version)")
        logger.info(f"   Min tracking time: {self.MIN_TRACKING_TIME} min")
        logger.info(f"   Breach threshold: {self.BREACH_THRESHOLD:.2%}")
    
    def start(self):
        """Start the tracking background thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self._thread.start()
        logger.info("⏱️ Outcome tracking started")
    
    def stop(self):
        """Stop the tracking background thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("⏱️ Outcome tracking stopped")
    
    def track_interaction(self, interaction: DPInteraction, interaction_id: int):
        """
        Start tracking an interaction for outcome.
        
        Args:
            interaction: The DPInteraction that was just alerted
            interaction_id: The database ID of the interaction
        """
        self.tracking_jobs[interaction_id] = {
            'interaction': interaction,
            'start_time': datetime.now(),
            'start_price': interaction.approach_price,
            'level_price': interaction.level_price,
            'level_type': interaction.level_type,
            'symbol': interaction.symbol,
            'checkpoints': {},  # Will store price at each checkpoint
            'price_history': [interaction.approach_price],  # All prices seen
            'min_price': interaction.approach_price,
            'max_price': interaction.approach_price,
            'level_breached': False,
            'outcome': None
        }
        
        logger.info(f"⏱️ Started tracking #{interaction_id}: {interaction.symbol} @ ${interaction.level_price:.2f} ({interaction.level_type.value})")
    
    def _tracking_loop(self):
        """Background loop that checks on tracked interactions."""
        while self._running:
            try:
                self._check_all_jobs()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"❌ Tracking loop error: {e}")
                time.sleep(60)
    
    def _check_all_jobs(self):
        """Check all active tracking jobs."""
        completed_ids = []
        
        for interaction_id, job in list(self.tracking_jobs.items()):
            try:
                elapsed = (datetime.now() - job['start_time']).total_seconds() / 60  # minutes
                
                # Get current price
                current_price = self._get_current_price(job['symbol'])
                if current_price is None:
                    continue
                
                # Update price tracking
                job['price_history'].append(current_price)
                job['min_price'] = min(job['min_price'], current_price)
                job['max_price'] = max(job['max_price'], current_price)
                
                # Check if level was breached
                self._check_breach(job, current_price)
                
                # Record price at checkpoints
                if elapsed >= 5 and 'price_5min' not in job['checkpoints']:
                    job['checkpoints']['price_5min'] = current_price
                    logger.info(f"   #{interaction_id} 5min: ${current_price:.2f} | Min: ${job['min_price']:.2f} | Max: ${job['max_price']:.2f}")
                
                if elapsed >= 15 and 'price_15min' not in job['checkpoints']:
                    job['checkpoints']['price_15min'] = current_price
                    logger.info(f"   #{interaction_id} 15min: ${current_price:.2f}")
                
                if elapsed >= 30 and 'price_30min' not in job['checkpoints']:
                    job['checkpoints']['price_30min'] = current_price
                    logger.info(f"   #{interaction_id} 30min: ${current_price:.2f}")
                
                if elapsed >= 60 and 'price_60min' not in job['checkpoints']:
                    job['checkpoints']['price_60min'] = current_price
                
                # Only try to determine outcome after MIN_TRACKING_TIME
                if elapsed >= self.MIN_TRACKING_TIME:
                    outcome = self._determine_outcome(job, current_price, elapsed)
                    
                    if outcome is not None or elapsed >= self.MAX_TRACKING_TIME:
                        self._finalize_job(interaction_id, job, outcome or Outcome.FADE)
                        completed_ids.append(interaction_id)
                    
            except Exception as e:
                logger.error(f"❌ Error checking job #{interaction_id}: {e}")
        
        # Remove completed jobs
        for interaction_id in completed_ids:
            if interaction_id in self.tracking_jobs:
                del self.tracking_jobs[interaction_id]
    
    def _check_breach(self, job: dict, current_price: float):
        """Check if the level has been breached."""
        level_price = job['level_price']
        level_type = job['level_type']
        
        if level_type == LevelType.SUPPORT:
            # Support breached if price goes BELOW the level
            breach_price = level_price * (1 - self.BREACH_THRESHOLD)
            if job['min_price'] < breach_price:
                if not job['level_breached']:
                    logger.info(f"   ⚠️ LEVEL BREACHED: Min ${job['min_price']:.2f} < Support ${level_price:.2f}")
                job['level_breached'] = True
        else:  # RESISTANCE
            # Resistance breached if price goes ABOVE the level
            breach_price = level_price * (1 + self.BREACH_THRESHOLD)
            if job['max_price'] > breach_price:
                if not job['level_breached']:
                    logger.info(f"   ⚠️ LEVEL BREACHED: Max ${job['max_price']:.2f} > Resistance ${level_price:.2f}")
                job['level_breached'] = True
    
    def _determine_outcome(self, job: dict, current_price: float, elapsed: float) -> Optional[Outcome]:
        """
        Determine if we have a clear BOUNCE or BREAK.
        
        BOUNCE: Level was NOT breached, price moved away in expected direction
        BREAK: Level WAS breached, price continued through
        FADE: Nothing clear happened
        
        Returns:
            Outcome if clear, None if still developing
        """
        level_price = job['level_price']
        level_type = job['level_type']
        level_breached = job['level_breached']
        start_price = job['start_price']
        min_price = job['min_price']
        max_price = job['max_price']
        
        # Calculate current position relative to level
        price_vs_level_pct = (current_price - level_price) / level_price
        
        if level_type == LevelType.SUPPORT:
            # SUPPORT LEVEL
            # BREAK = price went below support and stayed below or continued down
            # BOUNCE = price stayed above support and moved up
            
            if level_breached:
                # Level was breached - check if it's a confirmed break
                if current_price < level_price * (1 - self.BREAK_CONFIRM):
                    return Outcome.BREAK  # Confirmed break below support
                elif current_price > level_price * (1 + self.BOUNCE_CONFIRM):
                    # Breached but recovered - this is actually a BREAK that reversed
                    # Still count as BREAK since the level didn't hold
                    return Outcome.BREAK
                # Still developing
                return None
            else:
                # Level was NOT breached
                if current_price > level_price * (1 + self.BOUNCE_CONFIRM):
                    return Outcome.BOUNCE  # Confirmed bounce off support
                elif elapsed >= 15 and current_price > level_price:
                    # After 15 min, if still above support, call it a bounce
                    return Outcome.BOUNCE
                # Still developing
                return None
                
        else:  # RESISTANCE
            # RESISTANCE LEVEL
            # BREAK = price went above resistance and stayed above or continued up
            # BOUNCE = price stayed below resistance and moved down
            
            if level_breached:
                # Level was breached - check if it's a confirmed break
                if current_price > level_price * (1 + self.BREAK_CONFIRM):
                    return Outcome.BREAK  # Confirmed break above resistance
                elif current_price < level_price * (1 - self.BOUNCE_CONFIRM):
                    # Breached but reversed - still a BREAK since level didn't hold
                    return Outcome.BREAK
                # Still developing
                return None
            else:
                # Level was NOT breached
                if current_price < level_price * (1 - self.BOUNCE_CONFIRM):
                    return Outcome.BOUNCE  # Confirmed bounce off resistance
                elif elapsed >= 15 and current_price < level_price:
                    # After 15 min, if still below resistance, call it a bounce
                    return Outcome.BOUNCE
                # Still developing
                return None
        
        return None  # Still developing
    
    def _finalize_job(self, interaction_id: int, job: dict, outcome: Outcome):
        """Finalize a tracking job and update the database."""
        
        level_price = job['level_price']
        level_type = job['level_type']
        min_price = job['min_price']
        max_price = job['max_price']
        
        # Calculate max adverse move (how far price went against the level)
        if level_type == LevelType.SUPPORT:
            # For support, adverse = how far below the level
            max_move_pct = ((min_price - level_price) / level_price) * 100
        else:  # RESISTANCE
            # For resistance, adverse = how far above the level
            max_move_pct = ((max_price - level_price) / level_price) * 100
        
        elapsed = (datetime.now() - job['start_time']).total_seconds() / 60
        
        # Create outcome object
        dp_outcome = DPOutcome(
            interaction_id=interaction_id,
            outcome=outcome,
            max_move_pct=max_move_pct,
            time_to_outcome_min=int(elapsed),
            price_at_5min=job['checkpoints'].get('price_5min', 0),
            price_at_15min=job['checkpoints'].get('price_15min', 0),
            price_at_30min=job['checkpoints'].get('price_30min', 0),
            price_at_60min=job['checkpoints'].get('price_60min', 0)
        )
        
        # Update database
        self.db.update_outcome(interaction_id, dp_outcome)
        
        # Log with details
        breach_str = "BREACHED" if job['level_breached'] else "HELD"
        logger.info(f"✅ Outcome #{interaction_id}: {outcome.value}")
        logger.info(f"   Level {breach_str} | Min: ${min_price:.2f} | Max: ${max_price:.2f}")
        logger.info(f"   Max move: {max_move_pct:.2f}% | Time: {elapsed:.0f}min")
        
        # Call callback if set
        if self.on_outcome:
            try:
                self.on_outcome(interaction_id, dp_outcome)
            except Exception as e:
                logger.error(f"❌ Outcome callback error: {e}")
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='1m')
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        except Exception as e:
            logger.debug(f"Price fetch error for {symbol}: {e}")
        return None
    
    def get_active_jobs(self) -> Dict[int, dict]:
        """Get info on currently tracked interactions."""
        return {
            k: {
                'symbol': v['symbol'],
                'level': v['level_price'],
                'level_type': v['level_type'].value,
                'elapsed_min': (datetime.now() - v['start_time']).total_seconds() / 60,
                'min_price': v['min_price'],
                'max_price': v['max_price'],
                'level_breached': v['level_breached'],
                'checkpoints': list(v['checkpoints'].keys())
            }
            for k, v in self.tracking_jobs.items()
        }
