"""
Economic Intelligence Engine - Main Orchestrator

The main entry point that coordinates:
1. Data collection (historical economic data)
2. Pattern learning (statistical correlations)
3. Prediction (Fed Watch forecasting)
4. Alert generation (proactive positioning alerts)

Usage:
    engine = EconomicIntelligenceEngine()
    engine.train()  # Collect data and learn patterns
    
    prediction = engine.predict("NFP", surprise_sigma=-2.0)
    alert = engine.get_pre_event_alert("CPI", "2024-12-11", "08:30")
"""

import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Optional

from .models import (
    EconomicRelease, LearnedPattern, Prediction, PreEventAlert,
    EventType, TrainingData, DarkPoolContext
)
from .database import EconomicDatabase
from .data_collector import EconomicDataCollector
from .pattern_learner import PatternLearner
from .predictor import FedWatchPredictor

logger = logging.getLogger(__name__)


class EconomicIntelligenceEngine:
    """
    Main orchestrator for the Economic Intelligence system.
    
    A LEARNING system that predicts Fed Watch movements from economic data.
    Integrates Dark Pool signals for institutional positioning context.
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize the engine.
        
        Args:
            db_path: Path to SQLite database (defaults to data/economic_intelligence.db)
        """
        # Initialize components
        self.db = EconomicDatabase(db_path)
        self.collector = EconomicDataCollector()
        self.learner = PatternLearner()
        self.predictor = FedWatchPredictor()
        
        # Load existing patterns
        self._load_patterns()
        
        logger.info("🧠 EconomicIntelligenceEngine initialized")
        logger.info(f"   Database: {self.db.db_path}")
        logger.info(f"   Patterns loaded: {len(self.predictor.patterns)}")
    
    def _load_patterns(self):
        """Load patterns from database."""
        patterns = self.db.get_all_patterns()
        if patterns:
            self.predictor.set_patterns(patterns)
    
    # ========================================================================
    # TRAINING
    # ========================================================================
    
    def train(self, 
              start_date: str = "2023-01-01",
              event_types: List[EventType] = None,
              include_market_data: bool = True,
              include_dp_data: bool = False) -> TrainingData:
        """
        Train the engine on historical data.
        
        Steps:
        1. Collect economic releases from FRED
        2. Enrich with market reaction data
        3. (Optional) Enrich with Dark Pool data
        4. Learn patterns from the data
        5. Save to database
        
        Args:
            start_date: Start date for historical data
            event_types: Event types to train on (defaults to all)
            include_market_data: Fetch market reactions (slower)
            include_dp_data: Fetch Dark Pool data (much slower)
        
        Returns:
            TrainingData with stats
        """
        logger.info("=" * 60)
        logger.info("🎓 TRAINING ECONOMIC INTELLIGENCE ENGINE")
        logger.info("=" * 60)
        
        # Collect data
        releases = self.collector.collect_comprehensive_data(
            event_types=event_types,
            start_date=start_date,
            include_market=include_market_data,
            include_dp=include_dp_data
        )
        
        if not releases:
            logger.error("❌ No data collected! Check API keys.")
            return TrainingData(releases=[])
        
        # Save to database
        logger.info("💾 Saving to database...")
        self.db.save_releases_batch(releases)
        
        # Learn patterns
        logger.info("🧠 Learning patterns...")
        patterns = self.learner.learn_all_patterns(releases)
        
        # Save patterns
        for pattern in patterns.values():
            self.db.save_pattern(pattern)
        
        # Update predictor
        self.predictor.set_patterns(patterns)
        
        # Create training data summary
        training_data = TrainingData(releases=releases)
        
        logger.info("=" * 60)
        logger.info(f"✅ TRAINING COMPLETE")
        logger.info(f"   Total releases: {training_data.total_count}")
        logger.info(f"   Patterns learned: {len(patterns)}")
        logger.info(f"   Date range: {training_data.date_range}")
        logger.info("=" * 60)
        
        return training_data
    
    def add_historical_data(self, releases: List[EconomicRelease]):
        """
        Add historical releases manually.
        
        Use this to add curated historical data with accurate Fed Watch values.
        """
        self.db.save_releases_batch(releases)
        
        # Re-learn patterns
        all_releases = self.db.get_all_releases()
        patterns = self.learner.learn_all_patterns(all_releases)
        
        for pattern in patterns.values():
            self.db.save_pattern(pattern)
        
        self.predictor.set_patterns(patterns)
        
        logger.info(f"✅ Added {len(releases)} releases, re-learned {len(patterns)} patterns")
    
    # ========================================================================
    # PREDICTION
    # ========================================================================
    
    def predict(
        self,
        event_type: str,
        surprise_sigma: float,
        current_fed_watch: float = 89.0,
        days_to_fomc: int = 30,
        vix_level: float = 15.0,
        symbol: str = "SPY"
    ) -> Prediction:
        """
        Predict Fed Watch movement from an economic surprise.
        
        Args:
            event_type: Event type (e.g., "nfp", "cpi")
            surprise_sigma: Surprise in standard deviations
            current_fed_watch: Current cut probability
            days_to_fomc: Days until next FOMC
            vix_level: Current VIX level
            symbol: Symbol for DP context (default SPY)
        
        Returns:
            Prediction object
        """
        # Normalize event type
        event_type_enum = self._normalize_event_type(event_type)
        
        # Try to get DP context
        dp_context = None
        if self.collector.chartexchange_key:
            dp_context = self.collector.fetch_dp_context(symbol, datetime.now().strftime('%Y-%m-%d'))
        
        return self.predictor.predict(
            event_type=event_type_enum,
            surprise_sigma=surprise_sigma,
            current_fed_watch=current_fed_watch,
            days_to_fomc=days_to_fomc,
            vix_level=vix_level,
            dp_context=dp_context
        )
    
    def get_pre_event_alert(
        self,
        event_type: str,
        event_date: str,
        event_time: str = "08:30",
        current_fed_watch: float = 89.0,
        days_to_fomc: int = 30
    ) -> PreEventAlert:
        """
        Generate a pre-event alert for an upcoming release.
        
        Args:
            event_type: Event type (e.g., "nfp", "cpi")
            event_date: Date of release (YYYY-MM-DD)
            event_time: Time of release (HH:MM)
            current_fed_watch: Current cut probability
            days_to_fomc: Days until next FOMC
        
        Returns:
            PreEventAlert object
        """
        event_type_enum = self._normalize_event_type(event_type)
        
        return self.predictor.generate_pre_event_alert(
            event_type=event_type_enum,
            event_date=event_date,
            event_time=event_time,
            current_fed_watch=current_fed_watch,
            days_to_fomc=days_to_fomc
        )
    
    def _normalize_event_type(self, event_type: str) -> EventType:
        """Convert string to EventType enum."""
        if isinstance(event_type, EventType):
            return event_type
        
        type_lower = event_type.lower().replace(' ', '_')
        
        mapping = {
            'nfp': EventType.NFP,
            'nonfarm': EventType.NFP,
            'nonfarm_payrolls': EventType.NFP,
            'unemployment': EventType.UNEMPLOYMENT,
            'cpi': EventType.CPI,
            'core_cpi': EventType.CORE_CPI,
            'ppi': EventType.PPI,
            'core_ppi': EventType.CORE_PPI,
            'pce': EventType.PCE,
            'core_pce': EventType.CORE_PCE,
            'gdp': EventType.GDP,
            'retail': EventType.RETAIL_SALES,
            'retail_sales': EventType.RETAIL_SALES,
            'ism': EventType.ISM_MANUFACTURING,
            'ism_manufacturing': EventType.ISM_MANUFACTURING,
            'jobless': EventType.JOBLESS_CLAIMS,
            'jobless_claims': EventType.JOBLESS_CLAIMS,
            'initial_jobless_claims': EventType.JOBLESS_CLAIMS,
        }
        
        return mapping.get(type_lower, EventType.NFP)
    
    # ========================================================================
    # RECORDING OUTCOMES
    # ========================================================================
    
    def record_release(
        self,
        event_type: str,
        date: str,
        actual: float,
        forecast: float,
        previous: float,
        fed_watch_before: float,
        fed_watch_after: float,
        spy_change: float = 0,
        tlt_change: float = 0,
        vix_change: float = 0
    ):
        """
        Record a new economic release and update patterns.
        
        Call this after each major release to continuously learn!
        """
        event_type_enum = self._normalize_event_type(event_type)
        
        surprise_pct = ((actual - forecast) / forecast * 100) if forecast != 0 else 0
        surprise_sigma = surprise_pct / 10  # Rough estimate
        
        release = EconomicRelease(
            date=date,
            time=datetime.now().strftime("%H:%M"),
            event_type=event_type_enum,
            event_name=event_type_enum.value.replace('_', ' ').title(),
            actual=actual,
            forecast=forecast,
            previous=previous,
            surprise_pct=surprise_pct,
            surprise_sigma=surprise_sigma,
            fed_watch_before=fed_watch_before,
            fed_watch_after_1hr=fed_watch_after,
            fed_watch_shift_1hr=fed_watch_after - fed_watch_before,
            spy_change_1hr=spy_change,
            tlt_change_1hr=tlt_change,
            vix_change_1hr=vix_change,
            source="manual"
        )
        
        # Save
        self.db.save_release(release)
        
        # Re-learn pattern for this type
        releases = self.db.get_releases_by_type(event_type_enum)
        if len(releases) >= 5:
            pattern = self.learner.learn_pattern(releases)
            if pattern:
                self.db.save_pattern(pattern)
                self.predictor.patterns[event_type_enum.value] = pattern
        
        logger.info(f"📊 Recorded: {event_type_enum.value} = {actual} (forecast: {forecast})")
        logger.info(f"   Fed Watch: {fed_watch_before}% → {fed_watch_after}% ({fed_watch_after - fed_watch_before:+.1f}%)")
    
    # ========================================================================
    # STATUS & STATS
    # ========================================================================
    
    def get_status(self) -> Dict:
        """Get engine status and learned patterns."""
        stats = self.db.get_stats()
        
        patterns_summary = {}
        for name, pattern in self.predictor.patterns.items():
            patterns_summary[name] = {
                "base_impact": pattern.base_impact,
                "samples": pattern.sample_count,
                "r_squared": pattern.r_squared,
                "confidence": pattern.get_confidence()
            }
        
        return {
            "database": stats,
            "learned_patterns": patterns_summary,
            "engine_status": "READY" if stats['complete_releases'] >= 10 else "NEEDS_MORE_DATA"
        }
    
    def print_status(self):
        """Print status to console."""
        status = self.get_status()
        
        print("\n" + "=" * 60)
        print("🧠 ECONOMIC INTELLIGENCE ENGINE STATUS")
        print("=" * 60)
        
        print(f"\n📊 DATABASE:")
        print(f"   Total releases: {status['database']['total_releases']}")
        print(f"   Complete (with Fed Watch): {status['database']['complete_releases']}")
        print(f"   Patterns learned: {status['database']['learned_patterns']}")
        
        print(f"\n🧠 LEARNED PATTERNS:")
        for name, info in status['learned_patterns'].items():
            print(f"   {name}: {info['base_impact']:+.2f}% per σ")
            print(f"      R²={info['r_squared']:.2f}, n={info['samples']}, conf={info['confidence']:.0%}")
        
        print(f"\n🚦 STATUS: {status['engine_status']}")
        print("=" * 60)


# ========================================================================================
# DEMO
# ========================================================================================

def _demo():
    """Demo the full engine."""
    print("=" * 70)
    print("🧠 ECONOMIC INTELLIGENCE ENGINE - FULL DEMO")
    print("=" * 70)
    
    # Initialize
    engine = EconomicIntelligenceEngine()
    
    # Add some curated historical data
    historical = [
        EconomicRelease(
            date="2024-12-06", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=227, forecast=200, previous=36,
            surprise_pct=13.5, surprise_sigma=1.35,
            fed_watch_before=66, fed_watch_after_1hr=74, fed_watch_shift_1hr=8,
            spy_change_1hr=0.3, tlt_change_1hr=0.5, days_to_fomc=12
        ),
        EconomicRelease(
            date="2024-11-01", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=12, forecast=100, previous=254,
            surprise_pct=-88, surprise_sigma=-2.2,
            fed_watch_before=70, fed_watch_after_1hr=82, fed_watch_shift_1hr=12,
            spy_change_1hr=0.8, days_to_fomc=6
        ),
        EconomicRelease(
            date="2024-10-04", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=254, forecast=140, previous=159,
            surprise_pct=81, surprise_sigma=2.5,
            fed_watch_before=95, fed_watch_after_1hr=85, fed_watch_shift_1hr=-10,
            days_to_fomc=33
        ),
        EconomicRelease(
            date="2024-09-06", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=142, forecast=160, previous=89,
            surprise_pct=-11, surprise_sigma=-0.9,
            fed_watch_before=60, fed_watch_after_1hr=70, fed_watch_shift_1hr=10,
            days_to_fomc=12
        ),
        EconomicRelease(
            date="2024-08-02", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=114, forecast=175, previous=179,
            surprise_pct=-35, surprise_sigma=-1.8,
            fed_watch_before=75, fed_watch_after_1hr=90, fed_watch_shift_1hr=15,
            days_to_fomc=46
        ),
        EconomicRelease(
            date="2024-11-13", time="08:30", event_type=EventType.CPI,
            event_name="CPI", actual=2.6, forecast=2.6, previous=2.4,
            surprise_pct=0, surprise_sigma=0,
            fed_watch_before=62, fed_watch_after_1hr=65, fed_watch_shift_1hr=3,
            days_to_fomc=35
        ),
        EconomicRelease(
            date="2024-10-10", time="08:30", event_type=EventType.CPI,
            event_name="CPI", actual=2.4, forecast=2.3, previous=2.5,
            surprise_pct=4.3, surprise_sigma=0.43,
            fed_watch_before=85, fed_watch_after_1hr=83, fed_watch_shift_1hr=-2,
            days_to_fomc=27
        ),
    ]
    
    print("\n📊 Adding curated historical data...")
    engine.add_historical_data(historical)
    
    # Show status
    engine.print_status()
    
    # Make a prediction
    print("\n" + "=" * 70)
    print("🔮 PREDICTION: If NFP misses by 2σ tomorrow")
    print("=" * 70)
    
    pred = engine.predict("nfp", surprise_sigma=-2.0, current_fed_watch=89, days_to_fomc=10)
    
    print(f"\n   Current Fed Watch: {pred.current_fed_watch}%")
    print(f"   Predicted shift: {pred.predicted_shift:+.1f}%")
    print(f"   Predicted Fed Watch: {pred.predicted_fed_watch}%")
    print(f"   Direction: {pred.direction.value}")
    print(f"   Confidence: {pred.confidence:.0%}")
    print(f"\n   📝 {pred.rationale}")
    
    # Pre-event alert
    print("\n" + "=" * 70)
    print("🚨 PRE-EVENT ALERT: Tomorrow's CPI")
    print("=" * 70)
    
    alert = engine.get_pre_event_alert("cpi", "2024-12-11", "08:30", current_fed_watch=89)
    
    print(f"\n   Event: {alert.event_name}")
    print(f"   Time: {alert.event_date} {alert.event_time}")
    print(f"   Max swing: {alert.max_swing:.1f}%")
    
    print(f"\n   📈 SCENARIOS:")
    print(f"      WEAK: Fed Watch {alert.weak_scenario.predicted_fed_watch:.0f}% ({alert.weak_scenario.predicted_fed_watch_shift:+.1f}%)")
    print(f"         → {alert.weak_scenario.trade_action} {', '.join(alert.weak_scenario.trade_symbols)}")
    print(f"      STRONG: Fed Watch {alert.strong_scenario.predicted_fed_watch:.0f}% ({alert.strong_scenario.predicted_fed_watch_shift:+.1f}%)")
    print(f"         → {alert.strong_scenario.trade_action} {', '.join(alert.strong_scenario.trade_symbols)}")
    
    print(f"\n   🎯 RECOMMENDATION:")
    print(f"      {alert.recommended_positioning}")
    
    print("\n" + "=" * 70)
    print("✅ Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
    _demo()


