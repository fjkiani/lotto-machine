"""
🧠 DP Learning Engine - Main Orchestrator
==========================================
The brain that coordinates detection, tracking, learning, and prediction.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Callable

from .models import (
    DPInteraction, DPOutcome, DPPrediction, DPPattern,
    Outcome, LevelType, ApproachDirection
)
from .database import DPDatabase
from .tracker import OutcomeTracker
from .learner import PatternLearner

logger = logging.getLogger(__name__)


class DPLearningEngine:
    """
    🧠 Dark Pool Learning Engine
    
    This is the main orchestrator that:
    1. Logs interactions when alerts fire
    2. Tracks outcomes over time
    3. Learns patterns from historical data
    4. Makes predictions for new interactions
    
    Usage:
        engine = DPLearningEngine()
        engine.start()
        
        # When an alert fires:
        prediction = engine.log_interaction(
            symbol="SPY",
            level_price=685.34,
            level_volume=725664,
            ...
        )
        
        # prediction contains: bounce_probability, suggested_action, etc.
    """
    
    def __init__(self, on_outcome: Callable = None, on_prediction: Callable = None):
        """
        Initialize the learning engine.
        
        Args:
            on_outcome: Callback when an outcome is determined
            on_prediction: Callback when a prediction is made
        """
        self.db = DPDatabase()
        self.learner = PatternLearner(self.db)
        self.tracker = OutcomeTracker(self.db, on_outcome=self._on_outcome_detected)
        
        self.on_outcome = on_outcome
        self.on_prediction = on_prediction
        
        # Track touch counts per level
        self._touch_counts: Dict[str, int] = {}  # "SPY_685.34" -> count
        
        # Learn from existing data
        self.learner.learn(min_samples=3)
        
        logger.info("🧠 DPLearningEngine initialized")
        logger.info(f"   Database: {self.db.db_path}")
        logger.info(f"   Patterns: {len(self.learner.patterns)}")
    
    def start(self):
        """Start the outcome tracker background thread."""
        self.tracker.start()
        logger.info("🚀 DPLearningEngine started")
    
    def stop(self):
        """Stop the outcome tracker."""
        self.tracker.stop()
        logger.info("🛑 DPLearningEngine stopped")
    
    def log_interaction(
        self,
        symbol_or_interaction,  # Can be str (symbol) or DPInteraction object
        level_price: float = None,
        level_volume: int = None,
        level_type: str = None,  # "SUPPORT" or "RESISTANCE"
        level_date: str = None,
        approach_price: float = None,
        distance_pct: float = None,
        market_trend: str = "UNKNOWN",
        volume_vs_avg: float = 1.0,
        momentum_pct: float = 0.0,
        vix_level: float = 0.0
    ) -> Optional[DPPrediction]:
        """
        Log a new interaction and get a prediction.
        
        This should be called when an alert fires.
        Accepts either individual arguments or a DPInteraction object.
        
        Returns:
            DPPrediction with confidence and suggested action
        """
        # Handle DPInteraction object passed as first argument
        if hasattr(symbol_or_interaction, 'symbol'):
            # It's a DPInteraction object
            interaction_obj = symbol_or_interaction
            symbol = interaction_obj.symbol
            level_price = interaction_obj.level_price
            level_volume = interaction_obj.level_volume
            # Handle level_type which might be enum or string
            if hasattr(interaction_obj.level_type, 'value'):
                level_type = interaction_obj.level_type.value
            else:
                level_type = str(interaction_obj.level_type)
            level_date = interaction_obj.level_date
            approach_price = interaction_obj.approach_price
            distance_pct = getattr(interaction_obj, 'distance_pct', 0.0) or 0.0
            market_trend = getattr(interaction_obj, 'market_trend', 'UNKNOWN') or 'UNKNOWN'
            volume_vs_avg = getattr(interaction_obj, 'volume_vs_avg', 1.0) or 1.0
            momentum_pct = getattr(interaction_obj, 'momentum_pct', 0.0) or 0.0
            vix_level = getattr(interaction_obj, 'vix_level', 0.0) or 0.0
        else:
            # Individual arguments
            symbol = symbol_or_interaction
        
        # Determine level type
        lt = LevelType.RESISTANCE if level_type.upper() == "RESISTANCE" else LevelType.SUPPORT
        
        # Determine approach direction
        if lt == LevelType.RESISTANCE:
            direction = ApproachDirection.FROM_BELOW  # Approaching resistance from below
        else:
            direction = ApproachDirection.FROM_ABOVE  # Approaching support from above
        
        # Calculate touch count
        level_key = f"{symbol}_{level_price:.2f}"
        self._touch_counts[level_key] = self._touch_counts.get(level_key, 0) + 1
        touch_count = self._touch_counts[level_key]
        
        # Determine time of day
        hour = datetime.now().hour
        if 9 <= hour < 11:
            time_of_day = "MORNING"
        elif 11 <= hour < 14:
            time_of_day = "MIDDAY"
        else:
            time_of_day = "AFTERNOON"
        
        # Create interaction
        interaction = DPInteraction(
            timestamp=datetime.now(),
            symbol=symbol,
            level_price=level_price,
            level_volume=level_volume,
            level_type=lt,
            level_date=level_date,
            approach_price=approach_price,
            approach_direction=direction,
            distance_pct=distance_pct,
            touch_count=touch_count,
            market_trend=market_trend,
            volume_vs_avg=volume_vs_avg,
            momentum_pct=momentum_pct,
            vix_level=vix_level,
            time_of_day=time_of_day
        )
        
        # Save to database
        interaction_id = self.db.save_interaction(interaction)
        
        # Start tracking for outcome
        self.tracker.track_interaction(interaction, interaction_id)
        
        # Make prediction
        prediction = self.learner.predict(interaction)
        
        logger.info(f"📊 Logged #{interaction_id}: {symbol} @ ${level_price:.2f}")
        logger.info(f"   Touch #{touch_count} | {time_of_day} | {level_type}")
        logger.info(f"   Prediction: {prediction.predicted_outcome.value} ({prediction.bounce_probability:.1%} bounce)")
        logger.info(f"   Confidence: {prediction.confidence} | Action: {prediction.suggested_action}")
        
        # Call prediction callback
        if self.on_prediction:
            try:
                self.on_prediction(prediction)
            except Exception as e:
                logger.error(f"❌ Prediction callback error: {e}")
        
        return prediction
    
    def _on_outcome_detected(self, interaction_id: int, outcome: DPOutcome):
        """Called when an outcome is determined."""
        logger.info(f"🎯 Outcome detected for #{interaction_id}: {outcome.outcome.value}")
        
        # Re-learn patterns with new data
        self.learner.learn(min_samples=3)
        
        # Call external callback
        if self.on_outcome:
            try:
                self.on_outcome(interaction_id, outcome)
            except Exception as e:
                logger.error(f"❌ Outcome callback error: {e}")
    
    def get_status(self) -> dict:
        """Get current engine status."""
        stats = self.db.get_stats()
        active_jobs = self.tracker.get_active_jobs()
        
        return {
            'database': stats,
            'patterns': self.learner.get_patterns_summary(),
            'tracking': {
                'active_jobs': len(active_jobs),
                'jobs': active_jobs
            }
        }
    
    def get_prediction_for_level(
        self,
        symbol: str,
        level_price: float,
        level_volume: int,
        level_type: str
    ) -> DPPrediction:
        """
        Get a prediction without logging an interaction.
        
        Useful for "what-if" analysis or pre-alert estimation.
        """
        lt = LevelType.RESISTANCE if level_type.upper() == "RESISTANCE" else LevelType.SUPPORT
        direction = ApproachDirection.FROM_BELOW if lt == LevelType.RESISTANCE else ApproachDirection.FROM_ABOVE
        
        hour = datetime.now().hour
        if 9 <= hour < 11:
            time_of_day = "MORNING"
        elif 11 <= hour < 14:
            time_of_day = "MIDDAY"
        else:
            time_of_day = "AFTERNOON"
        
        level_key = f"{symbol}_{level_price:.2f}"
        touch_count = self._touch_counts.get(level_key, 0) + 1
        
        interaction = DPInteraction(
            timestamp=datetime.now(),
            symbol=symbol,
            level_price=level_price,
            level_volume=level_volume,
            level_type=lt,
            approach_direction=direction,
            touch_count=touch_count,
            time_of_day=time_of_day
        )
        
        return self.learner.predict(interaction)
    
    def manual_outcome(self, interaction_id: int, outcome_str: str, notes: str = ""):
        """
        Manually set an outcome for an interaction.
        
        Args:
            interaction_id: The interaction ID
            outcome_str: "BOUNCE", "BREAK", or "FADE"
            notes: Optional notes
        """
        outcome = Outcome[outcome_str.upper()]
        
        dp_outcome = DPOutcome(
            interaction_id=interaction_id,
            outcome=outcome,
            max_move_pct=0,  # Unknown for manual
            time_to_outcome_min=0
        )
        
        self.db.update_outcome(interaction_id, dp_outcome)
        
        # Re-learn
        self.learner.learn(min_samples=3)
        
        logger.info(f"📝 Manual outcome set for #{interaction_id}: {outcome_str}")


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    engine = DPLearningEngine()
    engine.start()
    
    # Simulate an alert
    prediction = engine.log_interaction(
        symbol="SPY",
        level_price=685.34,
        level_volume=725664,
        level_type="RESISTANCE",
        level_date="2025-12-04",
        approach_price=685.27,
        distance_pct=0.01
    )
    
    print(f"\nPrediction: {prediction}")
    print(f"\nStatus: {engine.get_status()}")
    
    engine.stop()

