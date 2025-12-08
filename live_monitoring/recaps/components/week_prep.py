"""
🎯 WEEK PREP COMPONENT
Prepares for the upcoming week with key levels, events, and narratives
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WeekPrepResult:
    """Result of week prep"""
    week_start: str
    week_end: str
    key_levels: List[Dict[str, Any]]
    upcoming_events: List[Dict[str, Any]]
    market_context: str
    watch_list: List[str]
    preparation_notes: List[str]
    summary: str


class WeekPrep:
    """
    Prepares for the upcoming week.
    
    What it does:
    - Identifies key levels to watch
    - Lists upcoming economic events
    - Provides market context
    - Creates watch list
    - Generates preparation notes
    """
    
    def __init__(self):
        """Initialize week prep"""
        pass
    
    def generate_prep(self, week_start: Optional[str] = None) -> WeekPrepResult:
        """
        Generate preparation for upcoming week.
        
        Args:
            week_start: Start date (YYYY-MM-DD), defaults to next Monday
        
        Returns:
            WeekPrepResult with preparation
        """
        # Calculate next week dates
        today = datetime.now()
        next_monday = today + timedelta(days=(7 - today.weekday()) % 7)
        if next_monday <= today:
            next_monday += timedelta(days=7)
        
        next_friday = next_monday + timedelta(days=4)
        
        if week_start:
            week_start_date = datetime.strptime(week_start, '%Y-%m-%d')
        else:
            week_start_date = next_monday
        
        week_end_date = week_start_date + timedelta(days=4)
        
        week_start_str = week_start_date.strftime('%Y-%m-%d')
        week_end_str = week_end_date.strftime('%Y-%m-%d')
        
        logger.info(f"🎯 Generating week prep: {week_start_str} to {week_end_str}")
        
        # Gather data
        key_levels = self._get_key_levels()
        upcoming_events = self._get_upcoming_events(week_start_str, week_end_str)
        market_context = self._get_market_context()
        watch_list = self._get_watch_list()
        preparation_notes = self._generate_preparation_notes(key_levels, upcoming_events, market_context)
        
        # Generate summary
        summary = self._generate_summary(key_levels, upcoming_events, market_context, watch_list, preparation_notes)
        
        return WeekPrepResult(
            week_start=week_start_str,
            week_end=week_end_str,
            key_levels=key_levels,
            upcoming_events=upcoming_events,
            market_context=market_context,
            watch_list=watch_list,
            preparation_notes=preparation_notes,
            summary=summary
        )
    
    def _get_key_levels(self) -> List[Dict[str, Any]]:
        """Get key levels to watch from DP learning database"""
        try:
            from pathlib import Path
            import sqlite3
            
            base_path = Path(__file__).parent.parent.parent.parent
            db_path = base_path / "data" / "dp_learning.db"
            
            if not db_path.exists():
                logger.warning("⚠️  DP learning database not found")
                return []
            
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Get recent key levels (high volume, recent)
            cursor.execute('''
                SELECT DISTINCT
                    symbol,
                    level_price,
                    level_volume,
                    level_type
                FROM dp_interactions
                WHERE level_volume > 1000000
                ORDER BY timestamp DESC
                LIMIT 20
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            # Group by symbol and level, take highest volume
            level_map = {}
            for symbol, level, volume, level_type in rows:
                key = (symbol, level)
                if key not in level_map or volume > level_map[key]['volume']:
                    level_map[key] = {
                        'symbol': symbol,
                        'level': level,
                        'volume': volume,
                        'type': level_type or 'UNKNOWN',
                        'strength': 'HIGH' if volume > 2000000 else 'MEDIUM'
                    }
            
            # Sort by volume and return top 10
            key_levels = sorted(level_map.values(), key=lambda x: x['volume'], reverse=True)[:10]
            
            logger.info(f"   Found {len(key_levels)} key levels from database")
            return key_levels
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to fetch key levels: {e}")
            return []
    
    def _get_upcoming_events(self, week_start: str, week_end: str) -> List[Dict[str, Any]]:
        """Get upcoming economic events"""
        try:
            from live_monitoring.enrichment.apis.event_loader import EventLoader
            
            loader = EventLoader()
            events = []
            
            current_date = datetime.strptime(week_start, '%Y-%m-%d')
            end_date = datetime.strptime(week_end, '%Y-%m-%d')
            
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                events_dict = loader.load_events(date_str, min_impact="medium")
                
                if isinstance(events_dict, dict):
                    macro_events = events_dict.get('macro_events', [])
                    for event in macro_events:
                        events.append({
                            'name': event.get('name', 'Unknown'),
                            'date': date_str,
                            'time': event.get('time', ''),
                            'impact': event.get('impact', 'medium')
                        })
                
                current_date += timedelta(days=1)
            
            return events
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to fetch upcoming events: {e}")
            return []
    
    def _get_market_context(self) -> str:
        """Get current market context"""
        # This would integrate with narrative brain
        return "Market context will be loaded from narrative system"
    
    def _get_watch_list(self) -> List[str]:
        """Get symbols to watch"""
        # Default watch list
        return ['SPY', 'QQQ', 'DIA', 'IWM']
    
    def _generate_preparation_notes(self, levels: List[Dict], events: List[Dict],
                                   context: str) -> List[str]:
        """Generate preparation notes"""
        notes = []
        
        if levels:
            notes.append(f"Watch {len(levels)} key DP levels this week")
        
        if events:
            high_impact = [e for e in events if e.get('impact') == 'high']
            if high_impact:
                notes.append(f"{len(high_impact)} high-impact events scheduled")
        
        notes.append("Monitor narrative shifts throughout the week")
        notes.append("Track institutional flow for accumulation/distribution")
        
        return notes
    
    def _generate_summary(self, levels: List[Dict], events: List[Dict],
                        context: str, watch_list: List[str], notes: List[str]) -> str:
        """Generate human-readable summary"""
        summary = f"**Week Preparation:**\n\n"
        
        if levels:
            summary += f"🎯 **Key Levels to Watch ({len(levels)}):**\n"
            for level in levels[:8]:  # Show top 8
                symbol = level.get('symbol', 'SPY')
                level_price = level.get('level', 0)
                volume = level.get('volume', 0)
                level_type = level.get('type', 'UNKNOWN')
                strength = level.get('strength', 'MEDIUM')
                summary += f"   • {symbol} @ ${level_price:.2f} ({level_type}, {volume:,} shares, {strength})\n"
            summary += "\n"
        else:
            summary += f"🎯 **Key Levels to Watch:** {len(levels)}\n"
        
        if events:
            summary += f"📅 **Upcoming Events ({len(events)}):**\n"
            for event in events[:5]:  # Show top 5
                summary += f"   • {event.get('name', 'Unknown')} ({event.get('date', '')} {event.get('time', '')}) - {event.get('impact', 'medium')} impact\n"
            summary += "\n"
        else:
            summary += f"📅 **Upcoming Events:** {len(events)}\n"
        
        summary += f"👀 **Watch List:** {', '.join(watch_list)}\n\n"
        
        if notes:
            summary += f"📝 **Preparation Notes:**\n"
            for note in notes:
                summary += f"   • {note}\n"
        
        return summary

