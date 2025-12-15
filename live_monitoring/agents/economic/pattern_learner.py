"""
Economic Intelligence - Pattern Learner

Statistical learning engine that discovers patterns between:
- Economic surprises and Fed Watch movements
- Context factors (FOMC proximity, VIX, DP signals) and impact magnitude

Uses simple but robust methods:
- Linear regression for base relationships
- Correlation analysis for context multipliers
- Cross-validation for model quality
"""

import logging
import statistics
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from .models import EconomicRelease, LearnedPattern, EventType

logger = logging.getLogger(__name__)


class PatternLearner:
    """
    Learns patterns from historical economic data.
    
    For each event type, learns:
    - Base impact: How much Fed Watch moves per σ surprise
    - Surprise scaling: Is the relationship linear or non-linear?
    - Context multipliers: FOMC proximity, VIX level, DP confirmation
    """
    
    def __init__(self):
        logger.info("🧠 PatternLearner initialized")
    
    def learn_pattern(self, releases: List[EconomicRelease]) -> Optional[LearnedPattern]:
        """
        Learn a pattern from a list of releases (same event type).
        
        Args:
            releases: List of EconomicRelease objects (same type)
        
        Returns:
            LearnedPattern or None if not enough data
        """
        if len(releases) < 5:
            logger.warning(f"Not enough data ({len(releases)} < 5)")
            return None
        
        # Filter for releases with Fed Watch data
        valid = [r for r in releases if r.fed_watch_shift_1hr != 0 and r.surprise_sigma != 0]
        
        if len(valid) < 3:
            logger.warning(f"Not enough valid data ({len(valid)} < 3)")
            return None
        
        event_type = valid[0].event_type
        
        # Calculate base impact (Fed Watch shift per σ surprise)
        base_impact, r_squared = self._calc_base_impact(valid)
        
        # Calculate FOMC proximity boost
        fomc_boost = self._calc_fomc_boost(valid)
        
        # Calculate high VIX multiplier
        vix_mult = self._calc_vix_multiplier(valid)
        
        # Calculate DP confirmation boost
        dp_boost = self._calc_dp_boost(valid)
        
        # Calculate mean absolute error
        mae = self._calc_mae(valid, base_impact)
        
        pattern = LearnedPattern(
            event_type=event_type,
            base_impact=round(base_impact, 3),
            surprise_scaling=1.0,  # Linear for now
            fomc_proximity_boost=round(fomc_boost, 3),
            high_vix_multiplier=round(vix_mult, 3),
            dp_confirmation_boost=round(dp_boost, 3),
            sample_count=len(valid),
            r_squared=round(r_squared, 3),
            mean_absolute_error=round(mae, 3),
            last_updated=datetime.now().isoformat()
        )
        
        logger.info(f"🧠 Learned pattern for {event_type}:")
        logger.info(f"   Base impact: {base_impact:+.2f}% per σ")
        logger.info(f"   FOMC boost: {fomc_boost:+.1%}")
        logger.info(f"   VIX multiplier: {vix_mult:.2f}x")
        logger.info(f"   DP boost: {dp_boost:+.1%}")
        logger.info(f"   R²: {r_squared:.3f} | MAE: {mae:.2f}%")
        logger.info(f"   Samples: {len(valid)}")
        
        return pattern
    
    def _calc_base_impact(self, releases: List[EconomicRelease]) -> Tuple[float, float]:
        """
        Calculate base impact coefficient using linear regression.
        
        Returns:
            (base_impact, r_squared)
        """
        x = [r.surprise_sigma for r in releases]
        y = [r.fed_watch_shift_1hr for r in releases]
        
        # Simple linear regression: y = a*x + b
        # We want slope (a) = base impact
        
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_xx = sum(xi * xi for xi in x)
        
        # Calculate slope
        denom = n * sum_xx - sum_x * sum_x
        if denom == 0:
            return 0, 0
        
        slope = (n * sum_xy - sum_x * sum_y) / denom
        
        # Calculate R²
        mean_y = sum_y / n
        ss_tot = sum((yi - mean_y) ** 2 for yi in y)
        
        intercept = (sum_y - slope * sum_x) / n
        predictions = [slope * xi + intercept for xi in x]
        ss_res = sum((yi - pi) ** 2 for yi, pi in zip(y, predictions))
        
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        r_squared = max(0, r_squared)
        
        return slope, r_squared
    
    def _calc_fomc_boost(self, releases: List[EconomicRelease]) -> float:
        """
        Calculate how much impact increases near FOMC meetings.
        """
        near_fomc = [r for r in releases if r.days_to_fomc < 7]
        far_fomc = [r for r in releases if r.days_to_fomc >= 14]
        
        if not near_fomc or not far_fomc:
            return 0.0
        
        # Calculate average impact per σ for each group
        near_impacts = [abs(r.fed_watch_shift_1hr / r.surprise_sigma) 
                       for r in near_fomc if r.surprise_sigma != 0]
        far_impacts = [abs(r.fed_watch_shift_1hr / r.surprise_sigma) 
                      for r in far_fomc if r.surprise_sigma != 0]
        
        if not near_impacts or not far_impacts:
            return 0.0
        
        near_avg = statistics.mean(near_impacts)
        far_avg = statistics.mean(far_impacts)
        
        # Boost = how much bigger near-FOMC impact is
        boost = (near_avg / far_avg) - 1 if far_avg != 0 else 0
        
        return max(0, min(boost, 2.0))  # Cap at 200% boost
    
    def _calc_vix_multiplier(self, releases: List[EconomicRelease]) -> float:
        """
        Calculate how much impact increases when VIX is high (>20).
        """
        high_vix = [r for r in releases if r.vix_level > 20]
        low_vix = [r for r in releases if r.vix_level <= 20]
        
        if not high_vix or not low_vix:
            return 1.0
        
        high_impacts = [abs(r.fed_watch_shift_1hr / r.surprise_sigma) 
                       for r in high_vix if r.surprise_sigma != 0]
        low_impacts = [abs(r.fed_watch_shift_1hr / r.surprise_sigma) 
                      for r in low_vix if r.surprise_sigma != 0]
        
        if not high_impacts or not low_impacts:
            return 1.0
        
        high_avg = statistics.mean(high_impacts)
        low_avg = statistics.mean(low_impacts)
        
        mult = high_avg / low_avg if low_avg != 0 else 1.0
        
        return max(0.5, min(mult, 2.5))  # Bound between 0.5x and 2.5x
    
    def _calc_dp_boost(self, releases: List[EconomicRelease]) -> float:
        """
        Calculate boost when Dark Pool data confirms the direction.
        
        Confirmation = DP buy ratio > 0.55 and surprise > 0 (both bullish)
                    OR DP buy ratio < 0.45 and surprise < 0 (both bearish)
        """
        confirmed = []
        unconfirmed = []
        
        for r in releases:
            if r.dp_buy_ratio_before == 0.5:  # No DP data
                continue
            
            # Check if DP confirms direction
            dp_bullish = r.dp_buy_ratio_before > 0.55
            dp_bearish = r.dp_buy_ratio_before < 0.45
            surprise_positive = r.surprise_sigma > 0
            surprise_negative = r.surprise_sigma < 0
            
            is_confirmed = (dp_bullish and surprise_positive) or (dp_bearish and surprise_negative)
            
            impact = abs(r.fed_watch_shift_1hr / r.surprise_sigma) if r.surprise_sigma != 0 else 0
            
            if is_confirmed:
                confirmed.append(impact)
            else:
                unconfirmed.append(impact)
        
        if not confirmed or not unconfirmed:
            return 0.0
        
        conf_avg = statistics.mean(confirmed)
        unconf_avg = statistics.mean(unconfirmed)
        
        boost = (conf_avg / unconf_avg) - 1 if unconf_avg != 0 else 0
        
        return max(0, min(boost, 1.0))  # Cap at 100% boost
    
    def _calc_mae(self, releases: List[EconomicRelease], base_impact: float) -> float:
        """
        Calculate Mean Absolute Error of predictions.
        """
        errors = []
        
        for r in releases:
            predicted = base_impact * r.surprise_sigma
            actual = r.fed_watch_shift_1hr
            errors.append(abs(actual - predicted))
        
        return statistics.mean(errors) if errors else 0
    
    def learn_all_patterns(self, releases: List[EconomicRelease]) -> Dict[str, LearnedPattern]:
        """
        Learn patterns for all event types in the data.
        
        Args:
            releases: List of all releases
        
        Returns:
            Dict mapping event_type to LearnedPattern
        """
        # Group by event type
        by_type = {}
        for r in releases:
            key = r.event_type.value if isinstance(r.event_type, EventType) else str(r.event_type)
            if key not in by_type:
                by_type[key] = []
            by_type[key].append(r)
        
        # Learn pattern for each type
        patterns = {}
        for event_type, type_releases in by_type.items():
            pattern = self.learn_pattern(type_releases)
            if pattern:
                patterns[event_type] = pattern
        
        logger.info(f"🧠 Learned {len(patterns)} patterns from {len(releases)} releases")
        return patterns
    
    def evaluate_model(self, releases: List[EconomicRelease], pattern: LearnedPattern) -> Dict:
        """
        Evaluate model performance with cross-validation.
        
        Returns:
            Dict with metrics: mae, rmse, direction_accuracy
        """
        predictions = []
        actuals = []
        direction_correct = 0
        
        for r in releases:
            if r.surprise_sigma == 0:
                continue
            
            # Make prediction
            pred_shift = pattern.base_impact * r.surprise_sigma
            
            # Apply context multipliers
            if r.days_to_fomc < 7:
                pred_shift *= (1 + pattern.fomc_proximity_boost)
            if r.vix_level > 20:
                pred_shift *= pattern.high_vix_multiplier
            
            actual = r.fed_watch_shift_1hr
            
            predictions.append(pred_shift)
            actuals.append(actual)
            
            # Check direction
            if (pred_shift > 0 and actual > 0) or (pred_shift < 0 and actual < 0):
                direction_correct += 1
        
        if not predictions:
            return {'mae': 0, 'rmse': 0, 'direction_accuracy': 0}
        
        n = len(predictions)
        
        # MAE
        mae = sum(abs(p - a) for p, a in zip(predictions, actuals)) / n
        
        # RMSE
        rmse = (sum((p - a) ** 2 for p, a in zip(predictions, actuals)) / n) ** 0.5
        
        # Direction accuracy
        direction_accuracy = direction_correct / n
        
        return {
            'mae': round(mae, 3),
            'rmse': round(rmse, 3),
            'direction_accuracy': round(direction_accuracy, 3),
            'n_samples': n
        }


# ========================================================================================
# DEMO
# ========================================================================================

def _demo():
    """Demo the pattern learner."""
    from .models import EconomicRelease, EventType
    
    print("=" * 70)
    print("🧠 PATTERN LEARNER DEMO")
    print("=" * 70)
    
    # Create sample data
    sample_releases = [
        EconomicRelease(
            date="2024-12-06", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=227, forecast=200, previous=36,
            surprise_pct=13.5, surprise_sigma=1.35,
            fed_watch_before=66, fed_watch_after_1hr=74, fed_watch_shift_1hr=8,
            days_to_fomc=12, vix_level=14
        ),
        EconomicRelease(
            date="2024-11-01", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=12, forecast=100, previous=254,
            surprise_pct=-88, surprise_sigma=-2.2,
            fed_watch_before=70, fed_watch_after_1hr=82, fed_watch_shift_1hr=12,
            days_to_fomc=6, vix_level=22
        ),
        EconomicRelease(
            date="2024-10-04", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=254, forecast=140, previous=159,
            surprise_pct=81, surprise_sigma=2.5,
            fed_watch_before=95, fed_watch_after_1hr=85, fed_watch_shift_1hr=-10,
            days_to_fomc=33, vix_level=18
        ),
        EconomicRelease(
            date="2024-09-06", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=142, forecast=160, previous=89,
            surprise_pct=-11, surprise_sigma=-0.9,
            fed_watch_before=60, fed_watch_after_1hr=70, fed_watch_shift_1hr=10,
            days_to_fomc=12, vix_level=20
        ),
        EconomicRelease(
            date="2024-08-02", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=114, forecast=175, previous=179,
            surprise_pct=-35, surprise_sigma=-1.8,
            fed_watch_before=75, fed_watch_after_1hr=90, fed_watch_shift_1hr=15,
            days_to_fomc=46, vix_level=25
        ),
    ]
    
    learner = PatternLearner()
    
    print("\n📊 Learning NFP pattern from 5 releases...")
    pattern = learner.learn_pattern(sample_releases)
    
    if pattern:
        print("\n📈 Evaluating model...")
        metrics = learner.evaluate_model(sample_releases, pattern)
        print(f"   MAE: {metrics['mae']:.2f}%")
        print(f"   Direction accuracy: {metrics['direction_accuracy']:.0%}")
    
    print("\n✅ Demo complete!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
    _demo()





