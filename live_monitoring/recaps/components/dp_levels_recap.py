"""
📊 DP LEVELS RECAP COMPONENT
Analyzes which dark pool levels played out last week
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LevelOutcome:
    """Outcome of a DP level interaction"""
    level: float
    volume: int
    interaction_type: str  # "BOUNCE", "BREAK", "REJECTION"
    success: bool
    price_before: float
    price_after: float
    move_pct: float
    timestamp: datetime
    symbol: str = "SPY"  # Added symbol


@dataclass
class DPLevelsRecapResult:
    """Result of DP levels recap"""
    week_start: str
    week_end: str
    total_levels_tracked: int
    levels_that_played: List[LevelOutcome]
    bounce_rate: float
    break_rate: float
    avg_move_on_bounce: float
    avg_move_on_break: float
    key_levels_next_week: List[Dict[str, Any]]
    summary: str


class DPLevelsRecap:
    """
    Analyzes dark pool levels from last week.
    
    What it does:
    - Queries DP interaction database for last week
    - Identifies which levels bounced vs broke
    - Calculates success rates and move sizes
    - Identifies key levels to watch next week
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize DP levels recap.
        
        Args:
            db_path: Path to DP learning database (defaults to data/dp_learning.db)
        """
        if db_path is None:
            from pathlib import Path
            base_path = Path(__file__).parent.parent.parent.parent
            self.db_path = str(base_path / "data" / "dp_learning.db")
        else:
            self.db_path = db_path
    
    def generate_recap(self, week_start: Optional[str] = None, 
                      week_end: Optional[str] = None) -> DPLevelsRecapResult:
        """
        Generate recap for last week's DP levels.
        
        Args:
            week_start: Start date (YYYY-MM-DD), defaults to last Monday
            week_end: End date (YYYY-MM-DD), defaults to last Friday
        
        Returns:
            DPLevelsRecapResult with analysis
        """
        # Calculate week dates
        today = datetime.now()
        last_friday = today - timedelta(days=(today.weekday() + 3) % 7)
        if last_friday > today:
            last_friday -= timedelta(days=7)
        
        last_monday = last_friday - timedelta(days=4)
        
        if week_start:
            week_start_date = datetime.strptime(week_start, '%Y-%m-%d')
        else:
            week_start_date = last_monday
        
        if week_end:
            week_end_date = datetime.strptime(week_end, '%Y-%m-%d')
        else:
            week_end_date = last_friday
        
        week_start_str = week_start_date.strftime('%Y-%m-%d')
        week_end_str = week_end_date.strftime('%Y-%m-%d')
        
        logger.info(f"📊 Generating DP levels recap: {week_start_str} to {week_end_str}")
        
        # Query database
        outcomes = self._query_interactions(week_start_str, week_end_str)
        
        # Analyze outcomes
        levels_that_played = self._analyze_outcomes(outcomes)
        
        # Calculate metrics
        bounce_rate, break_rate = self._calculate_rates(levels_that_played)
        avg_bounce_move, avg_break_move = self._calculate_avg_moves(levels_that_played)
        
        # Identify key levels for next week
        key_levels = self._identify_key_levels(levels_that_played)
        
        # Generate summary
        summary = self._generate_summary(
            levels_that_played, bounce_rate, break_rate,
            avg_bounce_move, avg_break_move, key_levels
        )
        
        return DPLevelsRecapResult(
            week_start=week_start_str,
            week_end=week_end_str,
            total_levels_tracked=len(outcomes),
            levels_that_played=levels_that_played,
            bounce_rate=bounce_rate,
            break_rate=break_rate,
            avg_move_on_bounce=avg_bounce_move,
            avg_move_on_break=avg_break_move,
            key_levels_next_week=key_levels,
            summary=summary
        )
    
    def _query_interactions(self, week_start: str, week_end: str) -> List[Dict]:
        """Query DP interactions from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Query interactions table (using actual schema from dp_learning database)
            cursor.execute('''
                SELECT 
                    timestamp,
                    symbol,
                    level_price,
                    level_volume,
                    level_type,
                    outcome,
                    max_move_pct,
                    approach_price,
                    approach_direction,
                    distance_pct
                FROM dp_interactions
                WHERE date(timestamp) >= date(?)
                  AND date(timestamp) <= date(?)
                  AND outcome != 'PENDING'
                ORDER BY timestamp
            ''', (week_start, week_end))
            
            rows = cursor.fetchall()
            conn.close()
            
            outcomes = []
            for row in rows:
                timestamp_str, symbol, level, volume, level_type, outcome, max_move_pct, approach_price, approach_direction, distance_pct = row
                
                # Map outcome to interaction type
                if outcome == 'BOUNCE':
                    interaction_type = 'BOUNCE'
                    success = max_move_pct > 0 if max_move_pct else False
                elif outcome == 'BREAK':
                    interaction_type = 'BREAK'
                    success = max_move_pct > 0 if max_move_pct else False
                elif outcome == 'FADE':
                    interaction_type = 'REJECTION'
                    success = False
                else:
                    interaction_type = outcome or 'UNKNOWN'
                    success = False
                
                outcomes.append({
                    'timestamp': datetime.fromisoformat(timestamp_str),
                    'symbol': symbol or 'SPY',
                    'level': level,
                    'volume': volume or 0,
                    'interaction_type': interaction_type,
                    'success': success,
                    'price_before': approach_price or level,
                    'price_after': (approach_price or level) * (1 + (max_move_pct or 0) / 100),
                    'move_pct': max_move_pct or 0.0,
                    'level_type': level_type,
                    'outcome': outcome
                })
            
            logger.info(f"   Found {len(outcomes)} DP interactions")
            return outcomes
            
        except sqlite3.OperationalError as e:
            logger.warning(f"⚠️  Database query failed: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Error querying interactions: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def _analyze_outcomes(self, outcomes: List[Dict]) -> List[LevelOutcome]:
        """Convert raw outcomes to LevelOutcome objects"""
        level_outcomes = []
        
        for outcome in outcomes:
            level_outcomes.append(LevelOutcome(
                level=outcome['level'],
                volume=outcome['volume'],
                interaction_type=outcome['interaction_type'],
                success=outcome['success'],
                price_before=outcome['price_before'],
                price_after=outcome['price_after'],
                move_pct=outcome['move_pct'],
                timestamp=outcome['timestamp'],
                symbol=outcome.get('symbol', 'SPY')
            ))
        
        return level_outcomes
    
    def _calculate_rates(self, outcomes: List[LevelOutcome]) -> tuple:
        """Calculate bounce and break rates"""
        if not outcomes:
            return 0.0, 0.0
        
        bounces = [o for o in outcomes if o.interaction_type == "BOUNCE"]
        breaks = [o for o in outcomes if o.interaction_type == "BREAK"]
        
        total = len(outcomes)
        bounce_rate = (len(bounces) / total * 100) if total > 0 else 0.0
        break_rate = (len(breaks) / total * 100) if total > 0 else 0.0
        
        return bounce_rate, break_rate
    
    def _calculate_avg_moves(self, outcomes: List[LevelOutcome]) -> tuple:
        """Calculate average moves on bounce vs break"""
        bounces = [o for o in outcomes if o.interaction_type == "BOUNCE" and o.success]
        breaks = [o for o in outcomes if o.interaction_type == "BREAK" and o.success]
        
        avg_bounce = sum(abs(o.move_pct) for o in bounces) / len(bounces) if bounces else 0.0
        avg_break = sum(abs(o.move_pct) for o in breaks) / len(breaks) if breaks else 0.0
        
        return avg_bounce, avg_break
    
    def _identify_key_levels(self, outcomes: List[LevelOutcome]) -> List[Dict[str, Any]]:
        """Identify key levels to watch next week"""
        # Group by level
        level_groups = {}
        for outcome in outcomes:
            level = outcome.level
            if level not in level_groups:
                level_groups[level] = {
                    'level': level,
                    'volume': outcome.volume,
                    'interactions': [],
                    'bounce_count': 0,
                    'break_count': 0
                }
            level_groups[level]['interactions'].append(outcome)
            if outcome.interaction_type == "BOUNCE":
                level_groups[level]['bounce_count'] += 1
            elif outcome.interaction_type == "BREAK":
                level_groups[level]['break_count'] += 1
        
        # Sort by volume and interaction count
        key_levels = sorted(
            level_groups.values(),
            key=lambda x: (x['volume'], len(x['interactions'])),
            reverse=True
        )[:10]  # Top 10
        
        return [
            {
                'level': level['level'],
                'volume': level['volume'],
                'interactions': len(level['interactions']),
                'bounce_count': level['bounce_count'],
                'break_count': level['break_count'],
                'strength': 'HIGH' if level['volume'] > 1_000_000 else 'MEDIUM'
            }
            for level in key_levels
        ]
    
    def _generate_summary(self, outcomes: List[LevelOutcome], bounce_rate: float,
                         break_rate: float, avg_bounce: float, avg_break: float,
                         key_levels: List[Dict]) -> str:
        """Generate human-readable summary"""
        if not outcomes:
            return "No DP level interactions recorded last week."
        
        summary = f"**DP Levels Recap ({len(outcomes)} interactions):**\n\n"
        summary += f"📊 **Performance:**\n"
        summary += f"   • Bounce Rate: {bounce_rate:.1f}%\n"
        summary += f"   • Break Rate: {break_rate:.1f}%\n"
        summary += f"   • Avg Move on Bounce: {avg_bounce:.2f}%\n"
        summary += f"   • Avg Move on Break: {avg_break:.2f}%\n\n"
        
        # Show recent interactions with context
        recent_outcomes = sorted(outcomes, key=lambda x: x.timestamp, reverse=True)[:5]
        if recent_outcomes:
            summary += f"📈 **Recent Level Tests:**\n"
            for outcome in recent_outcomes:
                symbol = getattr(outcome, 'symbol', 'SPY') if hasattr(outcome, 'symbol') else 'SPY'
                emoji = "✅" if outcome.success else "❌"
                summary += f"   {emoji} {symbol} @ ${outcome.level:.2f} - {outcome.interaction_type} ({outcome.move_pct:+.2f}%)\n"
            summary += "\n"
        
        if key_levels:
            summary += f"🎯 **Key Levels Next Week:**\n"
            for level in key_levels[:5]:
                summary += f"   • ${level['level']:.2f} ({level['volume']:,} shares, {level['strength']} strength)\n"
        
        return summary

