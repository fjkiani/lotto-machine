"""
Economic Learning & Prediction Engine 🧠

A LEARNING system that:
1. Collects historical economic data + Fed Watch movements
2. Learns correlations between events and Fed Watch shifts
3. Predicts future Fed Watch movements based on learned patterns
4. Generates proactive alerts with scenario planning

NOT static rules - LEARNED patterns that adapt over time!
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging
import statistics

# Add parent paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)


# ========================================================================================
# DATA MODELS
# ========================================================================================

@dataclass
class EconomicRelease:
    """A single economic data release."""
    date: str
    time: str
    event_name: str
    actual: float
    forecast: float
    previous: float
    surprise_pct: float  # (actual - forecast) / forecast * 100
    surprise_sigma: float  # Normalized surprise
    
    # Fed Watch at time of release
    fed_watch_before: float  # Cut probability before
    fed_watch_after: float   # Cut probability after (1hr later)
    fed_watch_shift: float   # Change in cut probability
    
    # Market reaction
    spy_change_1hr: float = 0.0
    tlt_change_1hr: float = 0.0
    vix_change_1hr: float = 0.0
    
    # Context
    days_to_fomc: int = 30  # Days until next FOMC meeting
    current_rate: float = 4.5  # Current Fed Funds rate


@dataclass
class LearnedPattern:
    """A learned correlation between an event and Fed Watch movement."""
    event_type: str  # "nfp", "cpi", "ppi", etc.
    
    # Learned coefficients
    base_impact: float  # Average Fed Watch shift for 1σ surprise
    surprise_multiplier: float  # How much each additional σ adds
    fomc_proximity_boost: float  # Extra impact when close to FOMC
    
    # Confidence metrics
    sample_count: int
    r_squared: float  # How well does our model explain variance?
    avg_prediction_error: float
    
    # Recent performance
    last_5_predictions: List[Dict] = field(default_factory=list)
    last_updated: str = ""


@dataclass
class FedWatchPrediction:
    """Prediction for Fed Watch movement."""
    event_name: str
    event_date: str
    event_time: str
    
    # Current state
    current_cut_prob: float
    
    # Scenarios
    scenarios: Dict[str, Dict]  # "weak", "inline", "strong"
    
    # Recommendation
    base_case: str
    recommended_action: str
    confidence: float
    rationale: str
    
    # Timing
    alert_generated: str
    hours_until_event: float


# ========================================================================================
# DATABASE
# ========================================================================================

class EconomicDatabase:
    """
    SQLite database for storing economic releases and learned patterns.
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(__file__), 
                '..', '..', 'data', 'economic_learning.db'
            )
        
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()
        
        logger.info(f"📊 EconomicDatabase initialized: {db_path}")
    
    def _init_db(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Economic releases table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS economic_releases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                time TEXT,
                event_name TEXT NOT NULL,
                actual REAL,
                forecast REAL,
                previous REAL,
                surprise_pct REAL,
                surprise_sigma REAL,
                fed_watch_before REAL,
                fed_watch_after REAL,
                fed_watch_shift REAL,
                spy_change_1hr REAL,
                tlt_change_1hr REAL,
                vix_change_1hr REAL,
                days_to_fomc INTEGER,
                current_rate REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, event_name)
            )
        """)
        
        # Learned patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT UNIQUE NOT NULL,
                base_impact REAL,
                surprise_multiplier REAL,
                fomc_proximity_boost REAL,
                sample_count INTEGER,
                r_squared REAL,
                avg_prediction_error REAL,
                last_5_predictions TEXT,
                last_updated TEXT
            )
        """)
        
        # Fed Watch history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fed_watch_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cut_prob REAL,
                hold_prob REAL,
                hike_prob REAL,
                meeting_date TEXT,
                source TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_release(self, release: EconomicRelease):
        """Save an economic release."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO economic_releases
            (date, time, event_name, actual, forecast, previous, 
             surprise_pct, surprise_sigma, fed_watch_before, fed_watch_after,
             fed_watch_shift, spy_change_1hr, tlt_change_1hr, vix_change_1hr,
             days_to_fomc, current_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            release.date, release.time, release.event_name,
            release.actual, release.forecast, release.previous,
            release.surprise_pct, release.surprise_sigma,
            release.fed_watch_before, release.fed_watch_after, release.fed_watch_shift,
            release.spy_change_1hr, release.tlt_change_1hr, release.vix_change_1hr,
            release.days_to_fomc, release.current_rate
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"💾 Saved release: {release.event_name} on {release.date}")
    
    def get_releases_by_event(self, event_type: str, limit: int = 50) -> List[EconomicRelease]:
        """Get historical releases for an event type."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM economic_releases
            WHERE LOWER(event_name) LIKE ?
            ORDER BY date DESC
            LIMIT ?
        """, (f"%{event_type.lower()}%", limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        releases = []
        for row in rows:
            releases.append(EconomicRelease(
                date=row[1], time=row[2], event_name=row[3],
                actual=row[4] or 0, forecast=row[5] or 0, previous=row[6] or 0,
                surprise_pct=row[7] or 0, surprise_sigma=row[8] or 0,
                fed_watch_before=row[9] or 50, fed_watch_after=row[10] or 50,
                fed_watch_shift=row[11] or 0,
                spy_change_1hr=row[12] or 0, tlt_change_1hr=row[13] or 0,
                vix_change_1hr=row[14] or 0,
                days_to_fomc=row[15] or 30, current_rate=row[16] or 4.5
            ))
        
        return releases
    
    def save_pattern(self, pattern: LearnedPattern):
        """Save a learned pattern."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO learned_patterns
            (event_type, base_impact, surprise_multiplier, fomc_proximity_boost,
             sample_count, r_squared, avg_prediction_error, last_5_predictions, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pattern.event_type, pattern.base_impact, pattern.surprise_multiplier,
            pattern.fomc_proximity_boost, pattern.sample_count, pattern.r_squared,
            pattern.avg_prediction_error, json.dumps(pattern.last_5_predictions),
            pattern.last_updated
        ))
        
        conn.commit()
        conn.close()
    
    def get_pattern(self, event_type: str) -> Optional[LearnedPattern]:
        """Get learned pattern for an event type."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM learned_patterns WHERE event_type = ?
        """, (event_type.lower(),))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return LearnedPattern(
            event_type=row[1],
            base_impact=row[2] or 0,
            surprise_multiplier=row[3] or 1,
            fomc_proximity_boost=row[4] or 0,
            sample_count=row[5] or 0,
            r_squared=row[6] or 0,
            avg_prediction_error=row[7] or 0,
            last_5_predictions=json.loads(row[8] or '[]'),
            last_updated=row[9] or ''
        )
    
    def save_fed_watch(self, cut_prob: float, hold_prob: float, hike_prob: float = 0, meeting_date: str = None):
        """Save Fed Watch snapshot."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO fed_watch_history
            (timestamp, cut_prob, hold_prob, hike_prob, meeting_date, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            cut_prob, hold_prob, hike_prob,
            meeting_date or "December 2025",
            "perplexity"
        ))
        
        conn.commit()
        conn.close()
    
    def get_fed_watch_history(self, hours: int = 24) -> List[Dict]:
        """Get Fed Watch history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute("""
            SELECT timestamp, cut_prob, hold_prob, hike_prob
            FROM fed_watch_history
            WHERE timestamp > ?
            ORDER BY timestamp DESC
        """, (since,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {"timestamp": r[0], "cut": r[1], "hold": r[2], "hike": r[3]}
            for r in rows
        ]
    
    def get_stats(self) -> Dict:
        """Get database statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM economic_releases")
        release_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM learned_patterns")
        pattern_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM fed_watch_history")
        fed_watch_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "releases": release_count,
            "patterns": pattern_count,
            "fed_watch_snapshots": fed_watch_count
        }


# ========================================================================================
# PATTERN LEARNER
# ========================================================================================

class PatternLearner:
    """
    Learns patterns from historical economic data.
    
    For each event type, learns:
    - Base impact (average Fed Watch shift for 1σ surprise)
    - Surprise multiplier (how impact scales with surprise magnitude)
    - FOMC proximity boost (extra impact when close to FOMC)
    """
    
    def __init__(self, db: EconomicDatabase):
        self.db = db
        logger.info("🧠 PatternLearner initialized")
    
    def learn_pattern(self, event_type: str) -> Optional[LearnedPattern]:
        """
        Learn pattern for an event type from historical data.
        
        Uses simple linear regression:
        fed_watch_shift = base_impact * surprise_sigma * fomc_multiplier
        """
        releases = self.db.get_releases_by_event(event_type, limit=100)
        
        if len(releases) < 5:
            logger.warning(f"Not enough data for {event_type} (only {len(releases)} releases)")
            return None
        
        # Filter releases with valid Fed Watch data
        valid_releases = [
            r for r in releases 
            if r.fed_watch_shift != 0 and r.surprise_sigma != 0
        ]
        
        if len(valid_releases) < 3:
            logger.warning(f"Not enough valid data for {event_type}")
            return None
        
        # Calculate correlations
        surprises = [r.surprise_sigma for r in valid_releases]
        shifts = [r.fed_watch_shift for r in valid_releases]
        fomc_days = [r.days_to_fomc for r in valid_releases]
        
        # Simple regression: shift = base * surprise
        # Base impact = average shift per unit surprise
        base_impacts = [s / (su + 0.001) for s, su in zip(shifts, surprises) if abs(su) > 0.3]
        base_impact = statistics.mean(base_impacts) if base_impacts else 0
        
        # Calculate how impact varies with FOMC proximity
        # Near FOMC (< 7 days): should see bigger moves
        near_fomc = [(s, su) for s, su, d in zip(shifts, surprises, fomc_days) if d < 7]
        far_fomc = [(s, su) for s, su, d in zip(shifts, surprises, fomc_days) if d >= 14]
        
        near_avg = statistics.mean([s/su for s, su in near_fomc if abs(su) > 0.3]) if near_fomc else base_impact
        far_avg = statistics.mean([s/su for s, su in far_fomc if abs(su) > 0.3]) if far_fomc else base_impact
        
        fomc_boost = (near_avg / far_avg) - 1 if far_avg != 0 else 0
        fomc_boost = max(0, min(fomc_boost, 2))  # Cap at 200% boost
        
        # Calculate surprise multiplier (how impact scales)
        # For now, assume linear scaling
        surprise_multiplier = 1.0
        
        # Calculate R² (how well model fits)
        predictions = [base_impact * s for s in surprises]
        ss_res = sum((a - p) ** 2 for a, p in zip(shifts, predictions))
        ss_tot = sum((s - statistics.mean(shifts)) ** 2 for s in shifts)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        r_squared = max(0, r_squared)
        
        # Average prediction error
        errors = [abs(a - p) for a, p in zip(shifts, predictions)]
        avg_error = statistics.mean(errors) if errors else 0
        
        pattern = LearnedPattern(
            event_type=event_type.lower(),
            base_impact=round(base_impact, 3),
            surprise_multiplier=round(surprise_multiplier, 3),
            fomc_proximity_boost=round(fomc_boost, 3),
            sample_count=len(valid_releases),
            r_squared=round(r_squared, 3),
            avg_prediction_error=round(avg_error, 3),
            last_5_predictions=[],
            last_updated=datetime.now().isoformat()
        )
        
        # Save pattern
        self.db.save_pattern(pattern)
        
        logger.info(f"🧠 Learned pattern for {event_type}:")
        logger.info(f"   Base impact: {pattern.base_impact:+.2f}% per σ")
        logger.info(f"   FOMC boost: {pattern.fomc_proximity_boost:+.1%}")
        logger.info(f"   R²: {pattern.r_squared:.3f}")
        logger.info(f"   Samples: {pattern.sample_count}")
        
        return pattern
    
    def learn_all_patterns(self) -> Dict[str, LearnedPattern]:
        """Learn patterns for all major event types."""
        event_types = [
            "nonfarm payrolls", "unemployment", "cpi", "core cpi",
            "ppi", "pce", "core pce", "retail sales", "gdp",
            "ism manufacturing", "initial jobless claims"
        ]
        
        patterns = {}
        for event_type in event_types:
            pattern = self.learn_pattern(event_type)
            if pattern:
                patterns[event_type] = pattern
        
        return patterns


# ========================================================================================
# PREDICTOR
# ========================================================================================

class FedWatchPredictor:
    """
    Predicts Fed Watch movements based on learned patterns.
    """
    
    def __init__(self, db: EconomicDatabase, learner: PatternLearner):
        self.db = db
        self.learner = learner
        logger.info("🔮 FedWatchPredictor initialized")
    
    def predict_impact(
        self,
        event_type: str,
        surprise_sigma: float,
        current_cut_prob: float,
        days_to_fomc: int = 30
    ) -> Dict:
        """
        Predict Fed Watch impact from an economic surprise.
        
        Args:
            event_type: Type of economic event (e.g., "nfp")
            surprise_sigma: Size of surprise in standard deviations
            current_cut_prob: Current Fed Watch cut probability
            days_to_fomc: Days until next FOMC meeting
        
        Returns:
            {
                "predicted_shift": -3.5,
                "predicted_cut_prob": 85.5,
                "confidence": 0.72,
                "rationale": "..."
            }
        """
        # Get learned pattern
        pattern = self.db.get_pattern(event_type)
        
        if not pattern:
            # Try to learn it
            pattern = self.learner.learn_pattern(event_type)
        
        if not pattern:
            # Fallback to default estimates
            pattern = LearnedPattern(
                event_type=event_type,
                base_impact=2.0,  # Default: 2% per σ
                surprise_multiplier=1.0,
                fomc_proximity_boost=0.5,
                sample_count=0,
                r_squared=0,
                avg_prediction_error=5.0,
                last_updated=""
            )
        
        # Calculate FOMC proximity multiplier
        fomc_mult = 1.0
        if days_to_fomc < 7:
            fomc_mult = 1 + pattern.fomc_proximity_boost
        elif days_to_fomc < 14:
            fomc_mult = 1 + (pattern.fomc_proximity_boost * 0.5)
        
        # Calculate predicted shift
        base_shift = pattern.base_impact * surprise_sigma * pattern.surprise_multiplier
        predicted_shift = base_shift * fomc_mult
        
        # Bound the prediction (Fed Watch can't go below 0 or above 100)
        max_up = 100 - current_cut_prob
        max_down = current_cut_prob
        
        if predicted_shift > 0:
            predicted_shift = min(predicted_shift, max_up * 0.8)  # Cap at 80% of max
        else:
            predicted_shift = max(predicted_shift, -max_down * 0.8)
        
        predicted_cut_prob = current_cut_prob + predicted_shift
        predicted_cut_prob = max(0, min(100, predicted_cut_prob))
        
        # Calculate confidence
        # Based on: R², sample size, surprise magnitude
        confidence = 0.5  # Base confidence
        
        if pattern.sample_count > 10:
            confidence += 0.1
        if pattern.sample_count > 25:
            confidence += 0.1
        if pattern.r_squared > 0.3:
            confidence += 0.1
        if pattern.r_squared > 0.5:
            confidence += 0.1
        if 0.5 < abs(surprise_sigma) < 3:
            confidence += 0.1  # Middle-range surprises are more predictable
        
        confidence = min(confidence, 0.95)
        
        # Generate rationale
        direction = "DOVISH (more cuts)" if predicted_shift > 0 else "HAWKISH (fewer cuts)"
        rationale = (
            f"{event_type.upper()} surprise of {surprise_sigma:+.2f}σ → "
            f"Expected Fed Watch shift: {predicted_shift:+.1f}% "
            f"({direction}). "
            f"Based on {pattern.sample_count} historical samples (R²={pattern.r_squared:.2f})."
        )
        
        if days_to_fomc < 14:
            rationale += f" FOMC in {days_to_fomc} days = higher impact."
        
        return {
            "predicted_shift": round(predicted_shift, 2),
            "predicted_cut_prob": round(predicted_cut_prob, 2),
            "confidence": round(confidence, 2),
            "rationale": rationale,
            "pattern_used": asdict(pattern)
        }
    
    def generate_scenarios(
        self,
        event_type: str,
        current_cut_prob: float,
        forecast: float = None,
        days_to_fomc: int = 30
    ) -> Dict[str, Dict]:
        """
        Generate bull/base/bear scenarios for an upcoming release.
        
        Returns:
            {
                "strong": {...},  # Data beats (hawkish)
                "inline": {...},  # Data meets
                "weak": {...}     # Data misses (dovish)
            }
        """
        scenarios = {}
        
        # Strong data scenario (+1.5σ surprise)
        strong = self.predict_impact(event_type, +1.5, current_cut_prob, days_to_fomc)
        scenarios["strong"] = {
            **strong,
            "description": f"Strong {event_type}: Beats forecast significantly",
            "market_reaction": "Risk-off: Fewer cuts = headwinds for stocks/bonds",
            "trade_idea": "Consider reducing SPY/QQQ, sell TLT"
        }
        
        # Inline data scenario (0σ surprise)
        inline = self.predict_impact(event_type, 0, current_cut_prob, days_to_fomc)
        scenarios["inline"] = {
            **inline,
            "description": f"Inline {event_type}: Meets forecast",
            "market_reaction": "Neutral: No change to rate cut expectations",
            "trade_idea": "Hold current positions"
        }
        
        # Weak data scenario (-1.5σ surprise)
        weak = self.predict_impact(event_type, -1.5, current_cut_prob, days_to_fomc)
        scenarios["weak"] = {
            **weak,
            "description": f"Weak {event_type}: Misses forecast significantly",
            "market_reaction": "Risk-on: More cuts = tailwind for stocks/bonds",
            "trade_idea": "Consider BUY SPY/QQQ, buy TLT"
        }
        
        return scenarios


# ========================================================================================
# PROACTIVE ALERT ENGINE
# ========================================================================================

class ProactiveAlertEngine:
    """
    Generates proactive alerts BEFORE economic events.
    """
    
    def __init__(self, predictor: FedWatchPredictor, db: EconomicDatabase):
        self.predictor = predictor
        self.db = db
        logger.info("🚨 ProactiveAlertEngine initialized")
    
    def generate_pre_event_alert(
        self,
        event_name: str,
        event_date: str,
        event_time: str,
        current_cut_prob: float,
        days_to_fomc: int = 30
    ) -> FedWatchPrediction:
        """
        Generate a proactive alert for an upcoming event.
        """
        # Normalize event name
        event_type = event_name.lower()
        for key in ["nonfarm", "cpi", "ppi", "pce", "retail", "gdp", "ism", "jobless"]:
            if key in event_type:
                event_type = key
                break
        
        # Generate scenarios
        scenarios = self.predictor.generate_scenarios(
            event_type, current_cut_prob, days_to_fomc=days_to_fomc
        )
        
        # Determine most likely scenario (base case is inline)
        base_case = "inline"
        
        # Calculate hours until event
        try:
            event_dt = datetime.strptime(f"{event_date} {event_time}", "%Y-%m-%d %H:%M")
            hours_until = (event_dt - datetime.now()).total_seconds() / 3600
        except:
            hours_until = 24
        
        # Generate recommendation
        weak_shift = scenarios["weak"]["predicted_shift"]
        strong_shift = scenarios["strong"]["predicted_shift"]
        avg_confidence = statistics.mean([s["confidence"] for s in scenarios.values()])
        
        if abs(weak_shift - strong_shift) > 5:
            recommended_action = (
                f"HIGH IMPACT EVENT. Prepare for {abs(weak_shift - strong_shift):.1f}% Fed Watch swing. "
                f"If WEAK: Buy TLT/SPY. If STRONG: Reduce exposure."
            )
        else:
            recommended_action = (
                f"Moderate impact expected ({abs(weak_shift - strong_shift):.1f}% swing). "
                f"Wait for release to confirm direction."
            )
        
        rationale = (
            f"{event_name} at {event_time} ET could move Fed Watch {abs(weak_shift - strong_shift):.1f}%. "
            f"Weak data = +{weak_shift:.1f}% cuts, Strong data = {strong_shift:.1f}% cuts. "
            f"Position accordingly."
        )
        
        return FedWatchPrediction(
            event_name=event_name,
            event_date=event_date,
            event_time=event_time,
            current_cut_prob=current_cut_prob,
            scenarios=scenarios,
            base_case=base_case,
            recommended_action=recommended_action,
            confidence=avg_confidence,
            rationale=rationale,
            alert_generated=datetime.now().isoformat(),
            hours_until_event=hours_until
        )


# ========================================================================================
# MAIN ENGINE
# ========================================================================================

class EconomicLearningEngine:
    """
    Main orchestrator for the Economic Learning & Prediction system.
    """
    
    def __init__(self, db_path: str = None):
        self.db = EconomicDatabase(db_path)
        self.learner = PatternLearner(self.db)
        self.predictor = FedWatchPredictor(self.db, self.learner)
        self.alerter = ProactiveAlertEngine(self.predictor, self.db)
        
        logger.info("🧠 EconomicLearningEngine fully initialized")
    
    def seed_historical_data(self):
        """
        Seed database with known historical economic events and Fed Watch movements.
        
        This provides the initial training data for pattern learning.
        """
        # Recent major releases with approximate Fed Watch impacts
        historical_data = [
            # December 2024 - January 2025 releases
            EconomicRelease(
                date="2024-12-06", time="08:30", event_name="Nonfarm Payrolls",
                actual=227, forecast=200, previous=36,
                surprise_pct=13.5, surprise_sigma=1.35,
                fed_watch_before=66, fed_watch_after=74, fed_watch_shift=8,
                spy_change_1hr=0.3, tlt_change_1hr=0.5, days_to_fomc=12
            ),
            EconomicRelease(
                date="2024-11-27", time="08:30", event_name="Core PCE",
                actual=2.8, forecast=2.8, previous=2.7,
                surprise_pct=0, surprise_sigma=0,
                fed_watch_before=66, fed_watch_after=66, fed_watch_shift=0,
                spy_change_1hr=0.1, tlt_change_1hr=0.1, days_to_fomc=21
            ),
            EconomicRelease(
                date="2024-11-13", time="08:30", event_name="CPI",
                actual=2.6, forecast=2.6, previous=2.4,
                surprise_pct=0, surprise_sigma=0,
                fed_watch_before=62, fed_watch_after=65, fed_watch_shift=3,
                spy_change_1hr=0.2, tlt_change_1hr=0.3, days_to_fomc=35
            ),
            EconomicRelease(
                date="2024-11-01", time="08:30", event_name="Nonfarm Payrolls",
                actual=12, forecast=100, previous=254,
                surprise_pct=-88, surprise_sigma=-2.2,
                fed_watch_before=70, fed_watch_after=82, fed_watch_shift=12,
                spy_change_1hr=0.8, tlt_change_1hr=1.2, days_to_fomc=6
            ),
            EconomicRelease(
                date="2024-10-10", time="08:30", event_name="CPI",
                actual=2.4, forecast=2.3, previous=2.5,
                surprise_pct=4.3, surprise_sigma=0.43,
                fed_watch_before=85, fed_watch_after=83, fed_watch_shift=-2,
                spy_change_1hr=-0.2, tlt_change_1hr=-0.3, days_to_fomc=27
            ),
            EconomicRelease(
                date="2024-10-04", time="08:30", event_name="Nonfarm Payrolls",
                actual=254, forecast=140, previous=159,
                surprise_pct=81, surprise_sigma=2.5,
                fed_watch_before=95, fed_watch_after=85, fed_watch_shift=-10,
                spy_change_1hr=-0.5, tlt_change_1hr=-1.0, days_to_fomc=33
            ),
            EconomicRelease(
                date="2024-09-11", time="08:30", event_name="CPI",
                actual=2.5, forecast=2.5, previous=2.9,
                surprise_pct=0, surprise_sigma=0,
                fed_watch_before=70, fed_watch_after=73, fed_watch_shift=3,
                spy_change_1hr=0.3, tlt_change_1hr=0.4, days_to_fomc=7
            ),
            EconomicRelease(
                date="2024-09-06", time="08:30", event_name="Nonfarm Payrolls",
                actual=142, forecast=160, previous=89,
                surprise_pct=-11, surprise_sigma=-0.9,
                fed_watch_before=60, fed_watch_after=70, fed_watch_shift=10,
                spy_change_1hr=0.4, tlt_change_1hr=0.8, days_to_fomc=12
            ),
            # Add more historical data for better learning
            EconomicRelease(
                date="2024-08-02", time="08:30", event_name="Nonfarm Payrolls",
                actual=114, forecast=175, previous=179,
                surprise_pct=-35, surprise_sigma=-1.8,
                fed_watch_before=75, fed_watch_after=90, fed_watch_shift=15,
                spy_change_1hr=-1.0, tlt_change_1hr=1.5, days_to_fomc=46
            ),
            EconomicRelease(
                date="2024-07-11", time="08:30", event_name="CPI",
                actual=3.0, forecast=3.1, previous=3.3,
                surprise_pct=-3.2, surprise_sigma=-0.8,
                fed_watch_before=70, fed_watch_after=78, fed_watch_shift=8,
                spy_change_1hr=0.6, tlt_change_1hr=0.9, days_to_fomc=20
            ),
        ]
        
        for release in historical_data:
            self.db.save_release(release)
        
        logger.info(f"💾 Seeded {len(historical_data)} historical releases")
        
        # Now learn patterns from this data
        self.learner.learn_all_patterns()
    
    def record_release(
        self,
        event_name: str,
        actual: float,
        forecast: float,
        previous: float,
        fed_watch_before: float,
        fed_watch_after: float,
        spy_change: float = 0,
        tlt_change: float = 0
    ):
        """
        Record a new economic release and update patterns.
        """
        # Calculate surprise
        surprise_pct = ((actual - forecast) / forecast * 100) if forecast != 0 else 0
        
        # Estimate sigma (rough)
        surprise_sigma = surprise_pct / 10  # Rough: 10% miss = 1σ
        
        release = EconomicRelease(
            date=datetime.now().strftime("%Y-%m-%d"),
            time=datetime.now().strftime("%H:%M"),
            event_name=event_name,
            actual=actual,
            forecast=forecast,
            previous=previous,
            surprise_pct=surprise_pct,
            surprise_sigma=surprise_sigma,
            fed_watch_before=fed_watch_before,
            fed_watch_after=fed_watch_after,
            fed_watch_shift=fed_watch_after - fed_watch_before,
            spy_change_1hr=spy_change,
            tlt_change_1hr=tlt_change
        )
        
        self.db.save_release(release)
        
        # Re-learn pattern with new data
        self.learner.learn_pattern(event_name)
        
        logger.info(f"📊 Recorded release: {event_name} = {actual} (forecast: {forecast})")
        logger.info(f"   Fed Watch: {fed_watch_before}% → {fed_watch_after}% ({release.fed_watch_shift:+.1f}%)")
    
    def get_prediction(
        self,
        event_type: str,
        surprise_sigma: float,
        current_cut_prob: float
    ) -> Dict:
        """
        Get prediction for Fed Watch impact.
        """
        return self.predictor.predict_impact(
            event_type, surprise_sigma, current_cut_prob
        )
    
    def get_pre_event_alert(
        self,
        event_name: str,
        event_date: str,
        event_time: str,
        current_cut_prob: float
    ) -> FedWatchPrediction:
        """
        Generate proactive alert for upcoming event.
        """
        return self.alerter.generate_pre_event_alert(
            event_name, event_date, event_time, current_cut_prob
        )
    
    def get_status(self) -> Dict:
        """Get engine status and learned patterns."""
        stats = self.db.get_stats()
        
        # Get all patterns
        patterns = {}
        for event_type in ["nonfarm payrolls", "cpi", "pce", "ppi"]:
            pattern = self.db.get_pattern(event_type)
            if pattern:
                patterns[event_type] = {
                    "base_impact": pattern.base_impact,
                    "samples": pattern.sample_count,
                    "r_squared": pattern.r_squared
                }
        
        return {
            "database": stats,
            "learned_patterns": patterns,
            "engine_status": "READY" if stats["releases"] > 5 else "NEEDS_DATA"
        }


# ========================================================================================
# CLI / DEMO
# ========================================================================================

def display_prediction(pred: Dict):
    """Display a prediction."""
    print(f"\n📊 PREDICTION:")
    print(f"   Expected shift: {pred['predicted_shift']:+.2f}%")
    print(f"   New cut prob: {pred['predicted_cut_prob']:.1f}%")
    print(f"   Confidence: {pred['confidence']:.0%}")
    print(f"   {pred['rationale']}")


def display_alert(alert: FedWatchPrediction):
    """Display a proactive alert."""
    print("\n" + "=" * 80)
    print(f"🚨 PRE-EVENT ALERT: {alert.event_name}")
    print("=" * 80)
    print(f"   Date: {alert.event_date} at {alert.event_time} ET")
    print(f"   Hours until: {alert.hours_until_event:.1f}")
    print(f"   Current Fed Watch: {alert.current_cut_prob:.1f}% cut probability")
    
    print(f"\n📈 SCENARIOS:")
    for name, scenario in alert.scenarios.items():
        print(f"\n   {name.upper()}:")
        print(f"      {scenario['description']}")
        print(f"      Fed Watch shift: {scenario['predicted_shift']:+.1f}%")
        print(f"      New cut prob: {scenario['predicted_cut_prob']:.1f}%")
        print(f"      Trade idea: {scenario['trade_idea']}")
    
    print(f"\n🎯 RECOMMENDATION:")
    print(f"   {alert.recommended_action}")
    print(f"   Confidence: {alert.confidence:.0%}")
    print("=" * 80)


def _demo():
    """Demo the Economic Learning Engine."""
    print("=" * 80)
    print("🧠 ECONOMIC LEARNING ENGINE DEMO")
    print("=" * 80)
    
    # Initialize engine
    engine = EconomicLearningEngine()
    
    # Seed with historical data
    print("\n📊 Seeding historical data...")
    engine.seed_historical_data()
    
    # Show status
    status = engine.get_status()
    print(f"\n📈 ENGINE STATUS:")
    print(f"   Releases: {status['database']['releases']}")
    print(f"   Patterns: {status['database']['patterns']}")
    print(f"   Status: {status['engine_status']}")
    
    print(f"\n🧠 LEARNED PATTERNS:")
    for event, pattern in status['learned_patterns'].items():
        print(f"   {event}: {pattern['base_impact']:+.2f}% per σ (R²={pattern['r_squared']:.2f}, n={pattern['samples']})")
    
    # Test prediction
    print("\n" + "=" * 80)
    print("🔮 TEST PREDICTION: NFP comes in weak (-2σ surprise)")
    print("=" * 80)
    
    pred = engine.get_prediction(
        event_type="nonfarm payrolls",
        surprise_sigma=-2.0,
        current_cut_prob=89
    )
    display_prediction(pred)
    
    # Generate pre-event alert
    print("\n" + "=" * 80)
    print("🚨 PRE-EVENT ALERT: Upcoming CPI release")
    print("=" * 80)
    
    alert = engine.get_pre_event_alert(
        event_name="CPI (Consumer Price Index)",
        event_date=datetime.now().strftime("%Y-%m-%d"),
        event_time="08:30",
        current_cut_prob=89
    )
    display_alert(alert)
    
    print("\n✅ Demo complete!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    _demo()

