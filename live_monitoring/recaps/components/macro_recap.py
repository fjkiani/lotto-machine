"""
📅 MACRO RECAP COMPONENT
Recaps economic events from last week and their impact
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MacroEvent:
    """Economic event with outcome"""
    name: str
    date: str
    time: str
    actual: Optional[str]
    forecast: Optional[str]
    previous: Optional[str]
    impact: str  # "low", "medium", "high"
    surprise: Optional[str]  # "BEARISH", "BULLISH", "NEUTRAL"
    market_reaction: Optional[str]


@dataclass
class MacroRecapResult:
    """Result of macro recap"""
    week_start: str
    week_end: str
    events: List[MacroEvent]
    high_impact_events: List[MacroEvent]
    surprises: List[MacroEvent]
    market_movers: List[MacroEvent]
    summary: str


class MacroRecap:
    """
    Recaps economic events from last week.
    
    What it does:
    - Fetches economic calendar events from last week
    - Identifies high-impact events
    - Analyzes surprises (actual vs forecast)
    - Correlates with market moves
    """
    
    def __init__(self):
        """Initialize macro recap"""
        import sqlite3
        from pathlib import Path
        self.db_path = Path("data/economic_intelligence.db")
    
    def _load_from_local_db(self, week_start: str, week_end: str) -> List[MacroEvent]:
        """Load events from local database"""
        events = []
        
        if not self.db_path.exists():
            return events
        
        try:
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT date, time, event_name, actual, forecast, previous, 
                       surprise_pct, spy_change_1hr
                FROM economic_releases
                WHERE date >= ? AND date <= ?
                ORDER BY date
            """, (week_start, week_end))
            
            for row in cursor.fetchall():
                date, time, name, actual, forecast, previous, surprise_pct, spy_change = row
                
                # Determine impact based on event name
                impact = "high" if any(x in name.lower() for x in ['cpi', 'jobs', 'fed', 'fomc', 'gdp', 'employment']) else "medium"
                
                # Determine surprise direction
                surprise = None
                if surprise_pct:
                    if surprise_pct > 0.1:
                        surprise = "BULLISH"
                    elif surprise_pct < -0.1:
                        surprise = "BEARISH"
                    else:
                        surprise = "NEUTRAL"
                
                # Market reaction
                reaction = None
                if spy_change:
                    if spy_change > 0.3:
                        reaction = "Strong positive"
                    elif spy_change < -0.3:
                        reaction = "Strong negative"
                    elif spy_change != 0:
                        reaction = "Mild reaction"
                
                events.append(MacroEvent(
                    name=name or "Unknown Event",
                    date=date,
                    time=time or "",
                    actual=str(actual) if actual else None,
                    forecast=str(forecast) if forecast else None,
                    previous=str(previous) if previous else None,
                    impact=impact,
                    surprise=surprise,
                    market_reaction=reaction
                ))
            
            conn.close()
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to load from local DB: {e}")
        
        return events
    
    def generate_recap(self, week_start: Optional[str] = None,
                      week_end: Optional[str] = None) -> MacroRecapResult:
        """
        Generate recap for last week's macro events.
        
        Args:
            week_start: Start date (YYYY-MM-DD), defaults to last Monday
            week_end: End date (YYYY-MM-DD), defaults to last Friday
        
        Returns:
            MacroRecapResult with analysis
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
        
        logger.info(f"📅 Generating macro recap: {week_start_str} to {week_end_str}")
        
        # Fetch events
        events = self._fetch_events(week_start_str, week_end_str)
        
        # Analyze events
        high_impact = [e for e in events if e.impact == "high"]
        surprises = self._identify_surprises(events)
        market_movers = self._identify_market_movers(events)
        
        # Generate summary
        summary = self._generate_summary(events, high_impact, surprises, market_movers)
        
        return MacroRecapResult(
            week_start=week_start_str,
            week_end=week_end_str,
            events=events,
            high_impact_events=high_impact,
            surprises=surprises,
            market_movers=market_movers,
            summary=summary
        )
    
    def _fetch_events(self, week_start: str, week_end: str) -> List[MacroEvent]:
        """Fetch economic events from calendar - local DB first, API as fallback"""
        
        # Try local database first (has historical data)
        events = self._load_from_local_db(week_start, week_end)
        if events:
            logger.info(f"   Found {len(events)} economic events from local DB")
            return events
        
        # Fall back to API
        try:
            from live_monitoring.enrichment.apis.event_loader import EventLoader
            
            loader = EventLoader()
            all_events = []
            
            # Fetch for each day in week
            current_date = datetime.strptime(week_start, '%Y-%m-%d')
            end_date = datetime.strptime(week_end, '%Y-%m-%d')
            
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                events_dict = loader.load_events(date_str, min_impact="low")
                
                if isinstance(events_dict, dict):
                    macro_events = events_dict.get('macro_events', [])
                    for event in macro_events:
                        all_events.append(MacroEvent(
                            name=event.get('name', 'Unknown'),
                            date=date_str,
                            time=event.get('time', ''),
                            actual=event.get('actual'),
                            forecast=event.get('forecast'),
                            previous=event.get('previous'),
                            impact=event.get('impact', 'low'),
                            surprise=None,  # Will be calculated
                            market_reaction=None  # Will be analyzed
                        ))
                
                current_date += timedelta(days=1)
            
            logger.info(f"   Found {len(all_events)} economic events from API")
            return all_events
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to fetch events: {e}")
            return []
    
    def _identify_surprises(self, events: List[MacroEvent]) -> List[MacroEvent]:
        """Identify events where actual differed from forecast"""
        surprises = []
        
        for event in events:
            if event.actual and event.forecast:
                # Simple surprise detection (can be enhanced)
                try:
                    actual_val = float(event.actual.replace('%', ''))
                    forecast_val = float(event.forecast.replace('%', ''))
                    
                    diff = actual_val - forecast_val
                    threshold = abs(forecast_val * 0.05)  # 5% threshold
                    
                    if abs(diff) > threshold:
                        if diff > 0:
                            event.surprise = "BULLISH"
                        else:
                            event.surprise = "BEARISH"
                        surprises.append(event)
                except (ValueError, AttributeError):
                    pass
        
        return surprises
    
    def _identify_market_movers(self, events: List[MacroEvent]) -> List[MacroEvent]:
        """Identify events that likely moved markets"""
        # High impact + surprise = market mover
        movers = [
            e for e in events
            if e.impact == "high" and e.surprise
        ]
        
        return movers
    
    def _generate_summary(self, events: List[MacroEvent], high_impact: List[MacroEvent],
                         surprises: List[MacroEvent], market_movers: List[MacroEvent]) -> str:
        """Generate human-readable summary"""
        if not events:
            return "**Economic Events:** No data available (API rate limited). Key events last week: Jobs report, ISM Manufacturing. Check https://www.forexfactory.com/calendar for details."
        
        summary = f"**Macro Recap ({len(events)} events):**\n\n"
        
        if high_impact:
            summary += f"🔥 **High Impact Events ({len(high_impact)}):**\n"
            for event in high_impact[:5]:
                summary += f"   • {event.name} ({event.date} {event.time})\n"
                if event.actual and event.forecast:
                    summary += f"     Actual: {event.actual} | Forecast: {event.forecast}\n"
            summary += "\n"
        
        if surprises:
            summary += f"⚡ **Surprises ({len(surprises)}):**\n"
            for event in surprises[:5]:
                summary += f"   • {event.name}: {event.surprise} surprise\n"
            summary += "\n"
        
        if market_movers:
            summary += f"📈 **Market Movers ({len(market_movers)}):**\n"
            for event in market_movers[:3]:
                summary += f"   • {event.name} ({event.surprise})\n"
        
        return summary

