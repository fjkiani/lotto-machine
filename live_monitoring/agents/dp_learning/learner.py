"""
🧠 DP Learning Engine - Pattern Learner
=======================================
Learns patterns from historical interactions to predict future outcomes.
"""

import logging
from typing import Dict, List, Optional
from collections import defaultdict

from .models import DPInteraction, DPPattern, DPPrediction, Outcome, LevelType
from .database import DPDatabase

logger = logging.getLogger(__name__)


class PatternLearner:
    """
    Learns patterns from historical dark pool interactions.
    
    Patterns analyzed:
    - By volume bracket (500K, 1M, 2M+)
    - By time of day (morning, midday, afternoon)
    - By touch count (1st, 2nd, 3rd+)
    - By level type (support vs resistance)
    - By market trend (up, down, chop)
    """
    
    # Volume brackets
    VOLUME_BRACKETS = [
        ('vol_500k', 500_000, 1_000_000),
        ('vol_1m', 1_000_000, 2_000_000),
        ('vol_2m_plus', 2_000_000, float('inf'))
    ]
    
    # Time of day ranges (ET)
    TIME_BRACKETS = [
        ('morning', 9, 11),      # 9:30 - 11:00
        ('midday', 11, 14),      # 11:00 - 2:00
        ('afternoon', 14, 16)    # 2:00 - 4:00
    ]
    
    def __init__(self, database: DPDatabase):
        self.db = database
        self.patterns: Dict[str, DPPattern] = {}
        
        logger.info("🧠 PatternLearner initialized")
    
    def learn(self, min_samples: int = 5):
        """
        Learn patterns from all completed interactions.
        
        Args:
            min_samples: Minimum samples needed to form a pattern
        """
        interactions = self.db.get_completed_interactions(limit=1000)
        
        if len(interactions) < min_samples:
            logger.info(f"⚠️ Not enough data yet ({len(interactions)} < {min_samples})")
            return
        
        logger.info(f"🧠 Learning from {len(interactions)} interactions...")
        
        # Reset patterns
        self.patterns = {}
        
        # Learn by volume
        self._learn_by_volume(interactions, min_samples)
        
        # Learn by time of day
        self._learn_by_time(interactions, min_samples)
        
        # Learn by touch count
        self._learn_by_touch_count(interactions, min_samples)
        
        # Learn by level type
        self._learn_by_level_type(interactions, min_samples)
        
        # Learn combined patterns
        self._learn_combined(interactions, min_samples)
        
        logger.info(f"🧠 Learned {len(self.patterns)} patterns")
    
    def _learn_by_volume(self, interactions: List[DPInteraction], min_samples: int):
        """Learn patterns by volume bracket."""
        for bracket_name, min_vol, max_vol in self.VOLUME_BRACKETS:
            pattern = DPPattern(pattern_name=bracket_name)
            
            for i in interactions:
                if min_vol <= i.level_volume < max_vol:
                    pattern.total_samples += 1
                    if i.outcome == Outcome.BOUNCE:
                        pattern.bounce_count += 1
                    elif i.outcome == Outcome.BREAK:
                        pattern.break_count += 1
                    else:
                        pattern.fade_count += 1
            
            if pattern.total_samples >= min_samples:
                self.patterns[bracket_name] = pattern
                logger.info(f"   {bracket_name}: {pattern.bounce_rate:.1%} bounce ({pattern.total_samples} samples)")
    
    def _learn_by_time(self, interactions: List[DPInteraction], min_samples: int):
        """Learn patterns by time of day."""
        for bracket_name, start_hour, end_hour in self.TIME_BRACKETS:
            pattern = DPPattern(pattern_name=bracket_name)
            
            for i in interactions:
                hour = i.timestamp.hour
                if start_hour <= hour < end_hour:
                    pattern.total_samples += 1
                    if i.outcome == Outcome.BOUNCE:
                        pattern.bounce_count += 1
                    elif i.outcome == Outcome.BREAK:
                        pattern.break_count += 1
                    else:
                        pattern.fade_count += 1
            
            if pattern.total_samples >= min_samples:
                self.patterns[bracket_name] = pattern
                logger.info(f"   {bracket_name}: {pattern.bounce_rate:.1%} bounce ({pattern.total_samples} samples)")
    
    def _learn_by_touch_count(self, interactions: List[DPInteraction], min_samples: int):
        """Learn patterns by touch count."""
        for touch in [1, 2, 3]:
            pattern_name = f"touch_{touch}" if touch < 3 else "touch_3_plus"
            pattern = DPPattern(pattern_name=pattern_name)
            
            for i in interactions:
                match = (i.touch_count == touch) if touch < 3 else (i.touch_count >= 3)
                if match:
                    pattern.total_samples += 1
                    if i.outcome == Outcome.BOUNCE:
                        pattern.bounce_count += 1
                    elif i.outcome == Outcome.BREAK:
                        pattern.break_count += 1
                    else:
                        pattern.fade_count += 1
            
            if pattern.total_samples >= min_samples:
                self.patterns[pattern_name] = pattern
                logger.info(f"   {pattern_name}: {pattern.bounce_rate:.1%} bounce ({pattern.total_samples} samples)")
    
    def _learn_by_level_type(self, interactions: List[DPInteraction], min_samples: int):
        """Learn patterns by level type (support vs resistance)."""
        for level_type in [LevelType.SUPPORT, LevelType.RESISTANCE]:
            pattern_name = level_type.value.lower()
            pattern = DPPattern(pattern_name=pattern_name)
            
            for i in interactions:
                if i.level_type == level_type:
                    pattern.total_samples += 1
                    if i.outcome == Outcome.BOUNCE:
                        pattern.bounce_count += 1
                    elif i.outcome == Outcome.BREAK:
                        pattern.break_count += 1
                    else:
                        pattern.fade_count += 1
            
            if pattern.total_samples >= min_samples:
                self.patterns[pattern_name] = pattern
                logger.info(f"   {pattern_name}: {pattern.bounce_rate:.1%} bounce ({pattern.total_samples} samples)")
    
    def _learn_combined(self, interactions: List[DPInteraction], min_samples: int):
        """Learn combined patterns (e.g., morning + high volume)."""
        # Morning + High Volume
        pattern = DPPattern(pattern_name="morning_high_vol")
        for i in interactions:
            if 9 <= i.timestamp.hour < 11 and i.level_volume >= 1_000_000:
                pattern.total_samples += 1
                if i.outcome == Outcome.BOUNCE:
                    pattern.bounce_count += 1
                elif i.outcome == Outcome.BREAK:
                    pattern.break_count += 1
                else:
                    pattern.fade_count += 1
        
        if pattern.total_samples >= min_samples:
            self.patterns["morning_high_vol"] = pattern
            logger.info(f"   morning_high_vol: {pattern.bounce_rate:.1%} bounce ({pattern.total_samples} samples)")
        
        # 2nd touch + resistance (classic rejection pattern)
        pattern = DPPattern(pattern_name="2nd_touch_resistance")
        for i in interactions:
            if i.touch_count == 2 and i.level_type == LevelType.RESISTANCE:
                pattern.total_samples += 1
                if i.outcome == Outcome.BOUNCE:
                    pattern.bounce_count += 1
                elif i.outcome == Outcome.BREAK:
                    pattern.break_count += 1
                else:
                    pattern.fade_count += 1
        
        if pattern.total_samples >= min_samples:
            self.patterns["2nd_touch_resistance"] = pattern
            logger.info(f"   2nd_touch_resistance: {pattern.bounce_rate:.1%} bounce ({pattern.total_samples} samples)")
    
    def predict(self, interaction: DPInteraction) -> DPPrediction:
        """
        Make a prediction for a new interaction based on learned patterns.
        
        Args:
            interaction: The new interaction to predict
            
        Returns:
            DPPrediction with probability estimates
        """
        matching_patterns = []
        total_bounce_weight = 0
        total_break_weight = 0
        total_weight = 0
        
        # Check each pattern
        for pattern_name, pattern in self.patterns.items():
            if self._matches_pattern(interaction, pattern_name):
                matching_patterns.append(pattern_name)
                
                # Weight by sample size (more samples = more weight)
                weight = min(pattern.total_samples / 10, 3)  # Cap at 3x weight
                
                total_bounce_weight += pattern.bounce_rate * weight
                total_break_weight += pattern.break_rate * weight
                total_weight += weight
        
        # Calculate probabilities
        if total_weight > 0:
            bounce_prob = total_bounce_weight / total_weight
            break_prob = total_break_weight / total_weight
        else:
            # No matching patterns, use 50/50
            bounce_prob = 0.5
            break_prob = 0.5
        
        # Determine predicted outcome
        if bounce_prob > 0.6:
            predicted = Outcome.BOUNCE
            expected_move = -0.3 if interaction.level_type == LevelType.RESISTANCE else 0.3
            action = "SHORT" if interaction.level_type == LevelType.RESISTANCE else "LONG"
        elif break_prob > 0.6:
            predicted = Outcome.BREAK
            expected_move = 0.3 if interaction.level_type == LevelType.RESISTANCE else -0.3
            action = "LONG" if interaction.level_type == LevelType.RESISTANCE else "SHORT"
        else:
            predicted = Outcome.FADE
            expected_move = 0
            action = "WAIT"
        
        # Determine confidence
        if len(matching_patterns) >= 3 and max(bounce_prob, break_prob) > 0.7:
            confidence = "HIGH"
        elif len(matching_patterns) >= 1 and max(bounce_prob, break_prob) > 0.6:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
        
        return DPPrediction(
            symbol=interaction.symbol,
            level_price=interaction.level_price,
            predicted_outcome=predicted,
            bounce_probability=bounce_prob,
            break_probability=break_prob,
            confidence=confidence,
            supporting_patterns=matching_patterns,
            expected_move_pct=expected_move,
            suggested_action=action
        )
    
    def _matches_pattern(self, interaction: DPInteraction, pattern_name: str) -> bool:
        """Check if an interaction matches a pattern."""
        
        # Volume patterns
        if pattern_name == 'vol_500k':
            return 500_000 <= interaction.level_volume < 1_000_000
        elif pattern_name == 'vol_1m':
            return 1_000_000 <= interaction.level_volume < 2_000_000
        elif pattern_name == 'vol_2m_plus':
            return interaction.level_volume >= 2_000_000
        
        # Time patterns
        elif pattern_name == 'morning':
            return 9 <= interaction.timestamp.hour < 11
        elif pattern_name == 'midday':
            return 11 <= interaction.timestamp.hour < 14
        elif pattern_name == 'afternoon':
            return 14 <= interaction.timestamp.hour < 16
        
        # Touch count patterns
        elif pattern_name == 'touch_1':
            return interaction.touch_count == 1
        elif pattern_name == 'touch_2':
            return interaction.touch_count == 2
        elif pattern_name == 'touch_3_plus':
            return interaction.touch_count >= 3
        
        # Level type patterns
        elif pattern_name == 'support':
            return interaction.level_type == LevelType.SUPPORT
        elif pattern_name == 'resistance':
            return interaction.level_type == LevelType.RESISTANCE
        
        # Combined patterns
        elif pattern_name == 'morning_high_vol':
            return 9 <= interaction.timestamp.hour < 11 and interaction.level_volume >= 1_000_000
        elif pattern_name == '2nd_touch_resistance':
            return interaction.touch_count == 2 and interaction.level_type == LevelType.RESISTANCE
        
        return False
    
    def get_patterns_summary(self) -> Dict[str, dict]:
        """Get a summary of all learned patterns."""
        return {
            name: {
                'samples': p.total_samples,
                'bounce_rate': f"{p.bounce_rate:.1%}",
                'break_rate': f"{p.break_rate:.1%}",
                'confidence': p.confidence
            }
            for name, p in self.patterns.items()
        }


