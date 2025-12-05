"""
🧠 DP Learning Engine - Outcome Tracker
=======================================
Monitors price after alert to detect bounce vs break.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable

import yfinance as yf

from .models import DPInteraction, DPOutcome, Outcome, LevelType
from .database import DPDatabase

logger = logging.getLogger(__name__)


class OutcomeTracker:
    """
    Tracks interactions after alert to determine outcome.
    
    After an alert fires:
    1. Track price at 5min, 15min, 30min, 60min
    2. Determine if BOUNCE, BREAK, or FADE
    3. Update database with outcome
    """
    
    # Thresholds for determining outcome
    BOUNCE_THRESHOLD = 0.002   # 0.2% reversal = bounce
    BREAK_THRESHOLD = 0.003    # 0.3% continuation = break
    
    def __init__(self, database: DPDatabase, on_outcome: Callable = None):
        self.db = database
        self.on_outcome = on_outcome  # Callback when outcome determined
        
        # Active tracking jobs
        self.tracking_jobs: Dict[int, dict] = {}  # interaction_id -> job info
        
        # Background thread for tracking
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        logger.info("⏱️ OutcomeTracker initialized")
    
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
            'prices': {},  # Will store price at each checkpoint
            'outcome': None
        }
        
        logger.info(f"⏱️ Started tracking interaction #{interaction_id}: {interaction.symbol} @ ${interaction.level_price:.2f}")
    
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
        
        for interaction_id, job in self.tracking_jobs.items():
            try:
                elapsed = (datetime.now() - job['start_time']).total_seconds() / 60  # minutes
                
                # Get current price
                current_price = self._get_current_price(job['symbol'])
                if current_price is None:
                    continue
                
                # Record price at checkpoints
                if elapsed >= 5 and 'price_5min' not in job['prices']:
                    job['prices']['price_5min'] = current_price
                    logger.debug(f"   #{interaction_id} 5min: ${current_price:.2f}")
                
                if elapsed >= 15 and 'price_15min' not in job['prices']:
                    job['prices']['price_15min'] = current_price
                    logger.debug(f"   #{interaction_id} 15min: ${current_price:.2f}")
                
                if elapsed >= 30 and 'price_30min' not in job['prices']:
                    job['prices']['price_30min'] = current_price
                    logger.debug(f"   #{interaction_id} 30min: ${current_price:.2f}")
                
                if elapsed >= 60 and 'price_60min' not in job['prices']:
                    job['prices']['price_60min'] = current_price
                    logger.debug(f"   #{interaction_id} 60min: ${current_price:.2f}")
                
                # Try to determine outcome
                outcome = self._determine_outcome(job, current_price)
                
                # If outcome determined or 60 min passed, finalize
                if outcome is not None or elapsed >= 60:
                    self._finalize_job(interaction_id, job, outcome or Outcome.FADE)
                    completed_ids.append(interaction_id)
                    
            except Exception as e:
                logger.error(f"❌ Error checking job #{interaction_id}: {e}")
        
        # Remove completed jobs
        for interaction_id in completed_ids:
            del self.tracking_jobs[interaction_id]
    
    def _determine_outcome(self, job: dict, current_price: float) -> Optional[Outcome]:
        """
        Determine if we have a clear BOUNCE or BREAK.
        
        Returns:
            Outcome if clear, None if still developing
        """
        level_price = job['level_price']
        start_price = job['start_price']
        level_type = job['level_type']
        
        # Calculate move from level
        move_pct = (current_price - level_price) / level_price
        
        if level_type == LevelType.RESISTANCE:
            # For resistance: bounce = price drops, break = price rises through
            if move_pct < -self.BOUNCE_THRESHOLD:
                return Outcome.BOUNCE  # Rejected at resistance, going down
            elif move_pct > self.BREAK_THRESHOLD:
                return Outcome.BREAK   # Broke through resistance, going up
        else:  # SUPPORT
            # For support: bounce = price rises, break = price drops through
            if move_pct > self.BOUNCE_THRESHOLD:
                return Outcome.BOUNCE  # Bounced off support, going up
            elif move_pct < -self.BREAK_THRESHOLD:
                return Outcome.BREAK   # Broke through support, going down
        
        return None  # Still developing
    
    def _finalize_job(self, interaction_id: int, job: dict, outcome: Outcome):
        """Finalize a tracking job and update the database."""
        
        # Calculate max move
        prices_seen = list(job['prices'].values()) + [job['start_price']]
        if job.get('level_type') == LevelType.RESISTANCE:
            # For resistance, positive = break, negative = bounce
            max_move = max(prices_seen) - job['level_price']
        else:
            # For support, negative = break, positive = bounce
            max_move = min(prices_seen) - job['level_price']
        
        max_move_pct = max_move / job['level_price'] * 100
        
        elapsed = (datetime.now() - job['start_time']).total_seconds() / 60
        
        # Create outcome object
        dp_outcome = DPOutcome(
            interaction_id=interaction_id,
            outcome=outcome,
            max_move_pct=max_move_pct,
            time_to_outcome_min=int(elapsed),
            price_at_5min=job['prices'].get('price_5min', 0),
            price_at_15min=job['prices'].get('price_15min', 0),
            price_at_30min=job['prices'].get('price_30min', 0),
            price_at_60min=job['prices'].get('price_60min', 0)
        )
        
        # Update database
        self.db.update_outcome(interaction_id, dp_outcome)
        
        logger.info(f"✅ Outcome #{interaction_id}: {outcome.value} | Max move: {max_move_pct:.2f}% | Time: {elapsed:.0f}min")
        
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
                'elapsed_min': (datetime.now() - v['start_time']).total_seconds() / 60,
                'checkpoints': list(v['prices'].keys())
            }
            for k, v in self.tracking_jobs.items()
        }

