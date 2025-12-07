"""
Economic Intelligence - Predictor

Makes predictions for Fed Watch movements based on:
1. Learned patterns
2. Current context (FOMC proximity, VIX, etc.)
3. Dark Pool signals (institutional positioning)

Generates scenarios (weak/inline/strong) for upcoming events.
"""

import logging
from datetime import datetime
from typing import Dict, Optional

from .models import (
    EconomicRelease, LearnedPattern, Prediction, Scenario, PreEventAlert,
    EventType, ImpactDirection, DarkPoolContext
)

logger = logging.getLogger(__name__)


class FedWatchPredictor:
    """
    Predicts Fed Watch movements from economic surprises.
    
    Uses learned patterns + context to generate predictions.
    """
    
    def __init__(self, patterns: Dict[str, LearnedPattern] = None):
        """
        Initialize predictor.
        
        Args:
            patterns: Dict of learned patterns by event type
        """
        self.patterns = patterns or {}
        logger.info(f"🔮 FedWatchPredictor initialized with {len(self.patterns)} patterns")
    
    def set_patterns(self, patterns: Dict[str, LearnedPattern]):
        """Update patterns."""
        self.patterns = patterns
        logger.info(f"🔮 Updated with {len(patterns)} patterns")
    
    def predict(
        self,
        event_type: EventType,
        surprise_sigma: float,
        current_fed_watch: float,
        days_to_fomc: int = 30,
        vix_level: float = 15,
        dp_context: Optional[DarkPoolContext] = None
    ) -> Prediction:
        """
        Predict Fed Watch movement from an economic surprise.
        
        Args:
            event_type: Type of economic event
            surprise_sigma: Size of surprise in σ
            current_fed_watch: Current Fed Watch cut probability
            days_to_fomc: Days until next FOMC
            vix_level: Current VIX level
            dp_context: Dark Pool context (if available)
        
        Returns:
            Prediction object
        """
        type_key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        
        # Get pattern
        pattern = self.patterns.get(type_key)
        
        if not pattern:
            # Fallback to default
            pattern = LearnedPattern(
                event_type=event_type,
                base_impact=-4.0,  # Default: weak data = more cuts
                surprise_scaling=1.0,
                fomc_proximity_boost=0.3,
                high_vix_multiplier=1.2,
                dp_confirmation_boost=0.2,
                sample_count=0,
                r_squared=0,
                mean_absolute_error=5.0
            )
        
        # Calculate base shift
        base_shift = pattern.base_impact * surprise_sigma * pattern.surprise_scaling
        
        # Apply FOMC proximity boost
        if days_to_fomc < 7:
            base_shift *= (1 + pattern.fomc_proximity_boost)
        elif days_to_fomc < 14:
            base_shift *= (1 + pattern.fomc_proximity_boost * 0.5)
        
        # Apply VIX multiplier
        if vix_level > 20:
            base_shift *= pattern.high_vix_multiplier
        
        # Check DP confirmation
        dp_signal = None
        dp_confirmation = False
        
        if dp_context:
            dp_signal = dp_context.get_signal()
            
            # Check if DP confirms the direction
            surprise_direction = ImpactDirection.DOVISH if surprise_sigma < 0 else ImpactDirection.HAWKISH
            if dp_signal == surprise_direction:
                base_shift *= (1 + pattern.dp_confirmation_boost)
                dp_confirmation = True
        
        # Bound prediction
        max_up = 100 - current_fed_watch
        max_down = current_fed_watch
        
        if base_shift > 0:
            predicted_shift = min(base_shift, max_up * 0.8)
        else:
            predicted_shift = max(base_shift, -max_down * 0.8)
        
        predicted_fed_watch = current_fed_watch + predicted_shift
        predicted_fed_watch = max(0, min(100, predicted_fed_watch))
        
        # Determine direction
        direction = ImpactDirection.DOVISH if predicted_shift > 0 else ImpactDirection.HAWKISH
        if abs(predicted_shift) < 1:
            direction = ImpactDirection.NEUTRAL
        
        # Calculate confidence
        confidence = pattern.get_confidence()
        if dp_confirmation:
            confidence = min(confidence + 0.1, 0.95)
        
        # Generate rationale
        rationale = self._generate_rationale(
            event_type, surprise_sigma, predicted_shift, direction,
            days_to_fomc, vix_level, dp_confirmation, pattern
        )
        
        return Prediction(
            event_type=event_type,
            event_name=type_key.replace('_', ' ').title(),
            surprise_sigma=surprise_sigma,
            current_fed_watch=current_fed_watch,
            predicted_shift=round(predicted_shift, 2),
            predicted_fed_watch=round(predicted_fed_watch, 2),
            confidence=round(confidence, 2),
            direction=direction,
            dp_signal=dp_signal,
            dp_confirmation=dp_confirmation,
            days_to_fomc=days_to_fomc,
            vix_level=vix_level,
            rationale=rationale
        )
    
    def _generate_rationale(
        self, event_type: EventType, surprise_sigma: float, shift: float,
        direction: ImpactDirection, days_to_fomc: int, vix_level: float,
        dp_confirmation: bool, pattern: LearnedPattern
    ) -> str:
        """Generate human-readable rationale."""
        
        type_name = event_type.value.replace('_', ' ').title() if isinstance(event_type, EventType) else str(event_type)
        
        parts = [
            f"{type_name} surprise of {surprise_sigma:+.2f}σ",
            f"→ Expected Fed Watch shift: {shift:+.1f}%",
            f"({direction.value.upper()})"
        ]
        
        if pattern.sample_count > 0:
            parts.append(f"Based on {pattern.sample_count} historical samples (R²={pattern.r_squared:.2f})")
        
        if days_to_fomc < 14:
            parts.append(f"⚠️ FOMC in {days_to_fomc} days = higher impact")
        
        if vix_level > 20:
            parts.append(f"⚠️ VIX at {vix_level:.0f} = elevated volatility")
        
        if dp_confirmation:
            parts.append("✅ Dark Pool confirms direction")
        
        return ". ".join(parts)
    
    def generate_scenarios(
        self,
        event_type: EventType,
        current_fed_watch: float,
        days_to_fomc: int = 30,
        vix_level: float = 15
    ) -> Dict[str, Scenario]:
        """
        Generate weak/inline/strong scenarios for an upcoming event.
        
        Returns:
            Dict with "weak", "inline", "strong" scenarios
        """
        scenarios = {}
        
        # Weak scenario (-1.5σ surprise)
        weak_pred = self.predict(event_type, -1.5, current_fed_watch, days_to_fomc, vix_level)
        scenarios["weak"] = Scenario(
            name="weak",
            description=f"Weak {event_type.value.replace('_', ' ')}: Misses forecast significantly",
            assumed_surprise_sigma=-1.5,
            predicted_fed_watch_shift=weak_pred.predicted_shift,
            predicted_fed_watch=weak_pred.predicted_fed_watch,
            predicted_spy_move=0.3 if weak_pred.predicted_shift > 0 else -0.2,  # Estimate
            predicted_tlt_move=0.5 if weak_pred.predicted_shift > 0 else -0.3,
            trade_action="BUY" if weak_pred.predicted_shift > 3 else "HOLD",
            trade_symbols=["SPY", "QQQ", "TLT"] if weak_pred.predicted_shift > 3 else [],
            confidence=weak_pred.confidence
        )
        
        # Inline scenario (0σ surprise)
        inline_pred = self.predict(event_type, 0, current_fed_watch, days_to_fomc, vix_level)
        scenarios["inline"] = Scenario(
            name="inline",
            description=f"Inline {event_type.value.replace('_', ' ')}: Meets forecast",
            assumed_surprise_sigma=0,
            predicted_fed_watch_shift=inline_pred.predicted_shift,
            predicted_fed_watch=inline_pred.predicted_fed_watch,
            predicted_spy_move=0,
            predicted_tlt_move=0,
            trade_action="HOLD",
            trade_symbols=[],
            confidence=inline_pred.confidence
        )
        
        # Strong scenario (+1.5σ surprise)
        strong_pred = self.predict(event_type, +1.5, current_fed_watch, days_to_fomc, vix_level)
        scenarios["strong"] = Scenario(
            name="strong",
            description=f"Strong {event_type.value.replace('_', ' ')}: Beats forecast significantly",
            assumed_surprise_sigma=+1.5,
            predicted_fed_watch_shift=strong_pred.predicted_shift,
            predicted_fed_watch=strong_pred.predicted_fed_watch,
            predicted_spy_move=-0.2 if strong_pred.predicted_shift < 0 else 0.3,
            predicted_tlt_move=-0.3 if strong_pred.predicted_shift < 0 else 0.2,
            trade_action="SELL" if strong_pred.predicted_shift < -3 else "HOLD",
            trade_symbols=["TLT"] if strong_pred.predicted_shift < -3 else [],
            confidence=strong_pred.confidence
        )
        
        return scenarios
    
    def generate_pre_event_alert(
        self,
        event_type: EventType,
        event_date: str,
        event_time: str,
        current_fed_watch: float,
        days_to_fomc: int = 30,
        vix_level: float = 15,
        dp_context: Optional[DarkPoolContext] = None
    ) -> PreEventAlert:
        """
        Generate a comprehensive pre-event alert.
        """
        # Calculate hours until event
        try:
            event_dt = datetime.strptime(f"{event_date} {event_time}", "%Y-%m-%d %H:%M")
            hours_until = (event_dt - datetime.now()).total_seconds() / 3600
        except:
            hours_until = 24
        
        # Generate scenarios
        scenarios = self.generate_scenarios(event_type, current_fed_watch, days_to_fomc, vix_level)
        
        # Calculate max swing
        weak_shift = scenarios["weak"].predicted_fed_watch_shift
        strong_shift = scenarios["strong"].predicted_fed_watch_shift
        max_swing = abs(weak_shift - strong_shift)
        
        # Check DP positioning
        dp_signal = dp_context.get_signal() if dp_context else None
        
        # Generate recommendation
        if max_swing > 10:
            positioning = "🚨 HIGH IMPACT: Position cautiously or stay flat into release"
        elif max_swing > 5:
            positioning = "⚠️ MODERATE IMPACT: Consider reducing position size before release"
        else:
            positioning = "📊 LOW IMPACT: Normal position sizing appropriate"
        
        if dp_signal and dp_signal != ImpactDirection.NEUTRAL:
            positioning += f"\n📍 DP Signal: Institutions are {dp_signal.value} (may front-run result)"
        
        return PreEventAlert(
            event_type=event_type,
            event_name=event_type.value.replace('_', ' ').title() if isinstance(event_type, EventType) else str(event_type),
            event_date=event_date,
            event_time=event_time,
            hours_until=hours_until,
            current_fed_watch=current_fed_watch,
            weak_scenario=scenarios["weak"],
            inline_scenario=scenarios["inline"],
            strong_scenario=scenarios["strong"],
            max_swing=round(max_swing, 1),
            dp_context=dp_context,
            dp_positioning_signal=dp_signal,
            recommended_positioning=positioning,
            confidence=(scenarios["weak"].confidence + scenarios["strong"].confidence) / 2
        )


# ========================================================================================
# DEMO
# ========================================================================================

def _demo():
    """Demo the predictor."""
    from .models import EventType, LearnedPattern
    
    print("=" * 70)
    print("🔮 FED WATCH PREDICTOR DEMO")
    print("=" * 70)
    
    # Create a sample pattern
    pattern = LearnedPattern(
        event_type=EventType.NFP,
        base_impact=-4.6,
        surprise_scaling=1.0,
        fomc_proximity_boost=0.3,
        high_vix_multiplier=1.2,
        dp_confirmation_boost=0.2,
        sample_count=10,
        r_squared=0.45,
        mean_absolute_error=2.5
    )
    
    predictor = FedWatchPredictor({"nonfarm_payrolls": pattern})
    
    # Make a prediction
    print("\n🔮 Predicting: NFP misses by 2σ, FOMC in 5 days")
    pred = predictor.predict(
        event_type=EventType.NFP,
        surprise_sigma=-2.0,
        current_fed_watch=89,
        days_to_fomc=5,
        vix_level=18
    )
    
    print(f"\n   Predicted shift: {pred.predicted_shift:+.1f}%")
    print(f"   Fed Watch: {pred.current_fed_watch}% → {pred.predicted_fed_watch}%")
    print(f"   Direction: {pred.direction.value}")
    print(f"   Confidence: {pred.confidence:.0%}")
    print(f"\n   {pred.rationale}")
    
    # Generate scenarios
    print("\n" + "=" * 70)
    print("📊 Generating scenarios for upcoming CPI...")
    
    cpi_pattern = LearnedPattern(
        event_type=EventType.CPI,
        base_impact=-3.0,
        sample_count=8,
        r_squared=0.35
    )
    predictor.set_patterns({"cpi": cpi_pattern})
    
    scenarios = predictor.generate_scenarios(EventType.CPI, current_fed_watch=89)
    
    for name, scenario in scenarios.items():
        print(f"\n   {name.upper()}:")
        print(f"      {scenario.description}")
        print(f"      Fed Watch shift: {scenario.predicted_fed_watch_shift:+.1f}%")
        print(f"      Trade: {scenario.trade_action} {', '.join(scenario.trade_symbols)}")
    
    print("\n✅ Demo complete!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
    _demo()


