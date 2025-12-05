"""
Economic Calendar - Standalone Module

Knows ALL major US economic events:
- Release dates (recurring schedules)
- Release times (8:30 AM ET for most)
- Importance levels (HIGH/MEDIUM/LOW)
- Fed Watch impact potential

Sources:
1. Static schedule (known recurring events)
2. Perplexity (for upcoming specific dates)
3. BLS/Fed websites (future: direct scraping)

Usage:
    from live_monitoring.agents.economic.calendar import EconomicCalendar
    
    calendar = EconomicCalendar()
    events = calendar.get_upcoming_events(days=7)
    today = calendar.get_today_events()
"""

import os
import sys
import logging
import re
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class Importance(Enum):
    """Event importance level."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EventCategory(Enum):
    """Event category."""
    EMPLOYMENT = "employment"
    INFLATION = "inflation"
    GROWTH = "growth"
    CONSUMER = "consumer"
    MANUFACTURING = "manufacturing"
    HOUSING = "housing"
    FED = "fed"
    OTHER = "other"


@dataclass
class CalendarEvent:
    """A scheduled economic event."""
    name: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM ET
    importance: Importance
    category: EventCategory
    
    # Release details
    release_frequency: str = "monthly"  # monthly, weekly, quarterly
    typical_surprise_impact: float = 0.0  # Typical Fed Watch shift for 1σ surprise
    
    # Consensus data (if available)
    forecast: Optional[str] = None
    previous: Optional[str] = None
    
    # Metadata
    source: str = "static"
    confirmed: bool = False  # True if date confirmed from external source
    
    def hours_until(self) -> float:
        """Calculate hours until this event."""
        try:
            event_dt = datetime.strptime(f"{self.date} {self.time}", "%Y-%m-%d %H:%M")
            return (event_dt - datetime.now()).total_seconds() / 3600
        except:
            return -1


# ============================================================================
# STATIC ECONOMIC CALENDAR - KNOWN SCHEDULES
# ============================================================================

# US Economic Calendar - Known recurring events
# Source: BLS, Fed, Census Bureau release schedules

KNOWN_EVENTS = {
    # =========================================================================
    # EMPLOYMENT (First Friday of month)
    # =========================================================================
    "NFP": {
        "name": "Nonfarm Payrolls",
        "time": "08:30",
        "importance": Importance.HIGH,
        "category": EventCategory.EMPLOYMENT,
        "frequency": "monthly",
        "schedule": "first_friday",
        "typical_impact": 5.0,  # Fed Watch can move 5% on big surprise
        "description": "Jobs added/lost. Weak = more cuts. THE most important release."
    },
    "UNEMPLOYMENT": {
        "name": "Unemployment Rate",
        "time": "08:30",
        "importance": Importance.HIGH,
        "category": EventCategory.EMPLOYMENT,
        "frequency": "monthly",
        "schedule": "first_friday",  # Same as NFP
        "typical_impact": 3.0,
        "description": "% of labor force unemployed. High = more cuts."
    },
    "JOBLESS_CLAIMS": {
        "name": "Initial Jobless Claims",
        "time": "08:30",
        "importance": Importance.MEDIUM,
        "category": EventCategory.EMPLOYMENT,
        "frequency": "weekly",
        "schedule": "thursday",
        "typical_impact": 1.5,
        "description": "Weekly unemployment filings. Rising = weak labor market."
    },
    "ADP": {
        "name": "ADP Employment Change",
        "time": "08:15",
        "importance": Importance.MEDIUM,
        "category": EventCategory.EMPLOYMENT,
        "frequency": "monthly",
        "schedule": "two_days_before_nfp",
        "typical_impact": 2.0,
        "description": "Private payrolls preview. Hint at NFP."
    },
    
    # =========================================================================
    # INFLATION (CPI: ~12th-15th, PPI: ~12th, PCE: last Friday)
    # =========================================================================
    "CPI": {
        "name": "Consumer Price Index (CPI)",
        "time": "08:30",
        "importance": Importance.HIGH,
        "category": EventCategory.INFLATION,
        "frequency": "monthly",
        "schedule": "mid_month",  # Usually 12th-15th
        "typical_impact": 4.0,
        "description": "Consumer inflation. Hot = fewer cuts. Fed watches this!"
    },
    "CORE_CPI": {
        "name": "Core CPI (ex Food & Energy)",
        "time": "08:30",
        "importance": Importance.HIGH,
        "category": EventCategory.INFLATION,
        "frequency": "monthly",
        "schedule": "mid_month",  # Same as CPI
        "typical_impact": 4.0,
        "description": "Core inflation. Fed's preferred measure."
    },
    "PPI": {
        "name": "Producer Price Index (PPI)",
        "time": "08:30",
        "importance": Importance.MEDIUM,
        "category": EventCategory.INFLATION,
        "frequency": "monthly",
        "schedule": "mid_month",
        "typical_impact": 2.5,
        "description": "Wholesale inflation. Leads CPI."
    },
    "PCE": {
        "name": "Personal Consumption Expenditures (PCE)",
        "time": "08:30",
        "importance": Importance.HIGH,
        "category": EventCategory.INFLATION,
        "frequency": "monthly",
        "schedule": "last_friday",
        "typical_impact": 5.0,
        "description": "Fed's PREFERRED inflation measure. Super important!"
    },
    "CORE_PCE": {
        "name": "Core PCE (ex Food & Energy)",
        "time": "08:30",
        "importance": Importance.HIGH,
        "category": EventCategory.INFLATION,
        "frequency": "monthly",
        "schedule": "last_friday",
        "typical_impact": 5.5,
        "description": "Fed's #1 metric. THIS is what they target."
    },
    
    # =========================================================================
    # GROWTH (GDP: end of month, Retail Sales: mid-month)
    # =========================================================================
    "GDP": {
        "name": "Gross Domestic Product (GDP)",
        "time": "08:30",
        "importance": Importance.HIGH,
        "category": EventCategory.GROWTH,
        "frequency": "quarterly",
        "schedule": "end_month",
        "typical_impact": 3.0,
        "description": "Economic growth. Weak = more cuts."
    },
    "RETAIL_SALES": {
        "name": "Retail Sales",
        "time": "08:30",
        "importance": Importance.MEDIUM,
        "category": EventCategory.CONSUMER,
        "frequency": "monthly",
        "schedule": "mid_month",
        "typical_impact": 2.0,
        "description": "Consumer spending. 70% of economy!"
    },
    
    # =========================================================================
    # MANUFACTURING & SERVICES
    # =========================================================================
    "DURABLES": {
        "name": "Durable Goods Orders",
        "time": "08:30",
        "importance": Importance.MEDIUM,
        "category": EventCategory.MANUFACTURING,
        "frequency": "monthly",
        "schedule": "end_month",  # Usually last week of month
        "typical_impact": 2.0,
        "description": "Big-ticket item orders. Leading indicator of manufacturing."
    },
    "ISM_MFG": {
        "name": "ISM Manufacturing PMI",
        "time": "10:00",
        "importance": Importance.MEDIUM,
        "category": EventCategory.MANUFACTURING,
        "frequency": "monthly",
        "schedule": "first_business_day",
        "typical_impact": 2.0,
        "description": "Manufacturing health. <50 = contraction."
    },
    "ISM_SVC": {
        "name": "ISM Services PMI",
        "time": "10:00",
        "importance": Importance.MEDIUM,
        "category": EventCategory.MANUFACTURING,
        "frequency": "monthly",
        "schedule": "third_business_day",
        "typical_impact": 1.5,
        "description": "Services health. 80% of economy!"
    },
    
    # =========================================================================
    # FED EVENTS
    # =========================================================================
    "FOMC": {
        "name": "FOMC Rate Decision",
        "time": "14:00",
        "importance": Importance.HIGH,
        "category": EventCategory.FED,
        "frequency": "6_weeks",
        "schedule": "fomc",  # Known FOMC dates
        "typical_impact": 10.0,
        "description": "THE event. Rate decision + statement + projections."
    },
    "FOMC_MINUTES": {
        "name": "FOMC Meeting Minutes",
        "time": "14:00",
        "importance": Importance.MEDIUM,
        "category": EventCategory.FED,
        "frequency": "6_weeks",
        "schedule": "3_weeks_after_fomc",
        "typical_impact": 2.0,
        "description": "Details from last FOMC. Can reveal dissent."
    },
}

# FOMC Meeting dates for 2024-2025
FOMC_DATES = [
    # 2024
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
    "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-11-05", "2025-12-17",
]


class EconomicCalendar:
    """
    Economic Calendar - Knows all major US economic events.
    
    Combines:
    1. Static schedule (known recurring events)
    2. Perplexity (for upcoming specific dates/forecasts)
    3. Manual overrides (for confirmed dates)
    """
    
    def __init__(self, perplexity_key: str = None):
        """
        Initialize calendar.
        
        Args:
            perplexity_key: Optional Perplexity API key for fetching forecasts
        """
        self.perplexity_key = perplexity_key or os.getenv('PERPLEXITY_API_KEY')
        self.perplexity_client = None
        
        if self.perplexity_key:
            try:
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from enrichment.apis.perplexity_search import PerplexitySearchClient
                self.perplexity_client = PerplexitySearchClient(api_key=self.perplexity_key)
            except Exception as e:
                logger.warning(f"Perplexity not available: {e}")
        
        logger.info("📅 EconomicCalendar initialized")
        logger.info(f"   Perplexity: {'✅' if self.perplexity_client else '❌'}")
    
    # ========================================================================
    # STATIC SCHEDULE CALCULATION
    # ========================================================================
    
    def _get_first_friday(self, year: int, month: int) -> datetime:
        """Get first Friday of a month."""
        first_day = datetime(year, month, 1)
        # Find days until Friday (weekday 4)
        days_until_friday = (4 - first_day.weekday()) % 7
        return first_day + timedelta(days=days_until_friday)
    
    def _get_last_friday(self, year: int, month: int) -> datetime:
        """Get last Friday of a month."""
        # Start from first day of NEXT month and go back
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)
        
        last_day = next_month - timedelta(days=1)
        # Go back to Friday
        days_since_friday = (last_day.weekday() - 4) % 7
        return last_day - timedelta(days=days_since_friday)
    
    def _get_mid_month(self, year: int, month: int) -> datetime:
        """Get mid-month date (typically 12th-15th for releases)."""
        # Most mid-month releases are around 12th-15th
        return datetime(year, month, 12)
    
    def _get_next_thursday(self, from_date: datetime) -> datetime:
        """Get next Thursday from a date."""
        days_until_thursday = (3 - from_date.weekday()) % 7
        if days_until_thursday == 0:
            days_until_thursday = 7  # Next week's Thursday
        return from_date + timedelta(days=days_until_thursday)
    
    def _calculate_event_date(self, event_key: str, event_info: Dict, 
                               target_month: int, target_year: int) -> Optional[datetime]:
        """Calculate the date for an event based on its schedule."""
        schedule = event_info.get('schedule', '')
        
        if schedule == 'first_friday':
            return self._get_first_friday(target_year, target_month)
        
        elif schedule == 'last_friday':
            return self._get_last_friday(target_year, target_month)
        
        elif schedule == 'mid_month':
            return self._get_mid_month(target_year, target_month)
        
        elif schedule == 'thursday':  # Weekly (Jobless Claims)
            # Return next Thursday
            return self._get_next_thursday(datetime.now())
        
        elif schedule == 'first_business_day':
            first = datetime(target_year, target_month, 1)
            while first.weekday() >= 5:  # Skip weekend
                first += timedelta(days=1)
            return first
        
        elif schedule == 'third_business_day':
            first = datetime(target_year, target_month, 1)
            business_days = 0
            while business_days < 3:
                if first.weekday() < 5:
                    business_days += 1
                first += timedelta(days=1)
            return first - timedelta(days=1)
        
        elif schedule == 'fomc':
            # Find next FOMC date
            today = datetime.now().strftime('%Y-%m-%d')
            for fomc_date in FOMC_DATES:
                if fomc_date >= today:
                    return datetime.strptime(fomc_date, '%Y-%m-%d')
            return None
        
        return None
    
    # ========================================================================
    # EVENT RETRIEVAL
    # ========================================================================
    
    def get_events_for_month(self, year: int, month: int, 
                              min_importance: Importance = Importance.MEDIUM) -> List[CalendarEvent]:
        """
        Get all events for a specific month.
        
        Args:
            year: Year
            month: Month (1-12)
            min_importance: Minimum importance level
        
        Returns:
            List of CalendarEvent objects
        """
        events = []
        importance_rank = {Importance.LOW: 0, Importance.MEDIUM: 1, Importance.HIGH: 2}
        min_rank = importance_rank.get(min_importance, 1)
        
        for key, info in KNOWN_EVENTS.items():
            # Filter by importance
            event_importance = info.get('importance', Importance.MEDIUM)
            if importance_rank.get(event_importance, 0) < min_rank:
                continue
            
            # Calculate date
            event_date = self._calculate_event_date(key, info, month, year)
            
            if event_date:
                event = CalendarEvent(
                    name=info['name'],
                    date=event_date.strftime('%Y-%m-%d'),
                    time=info.get('time', '08:30'),
                    importance=event_importance,
                    category=info.get('category', EventCategory.OTHER),
                    release_frequency=info.get('frequency', 'monthly'),
                    typical_surprise_impact=info.get('typical_impact', 0),
                    source="static"
                )
                events.append(event)
        
        # Sort by date
        events.sort(key=lambda e: e.date)
        
        return events
    
    def get_upcoming_events(self, days: int = 7, 
                            min_importance: Importance = Importance.MEDIUM) -> List[CalendarEvent]:
        """
        Get upcoming events for the next N days.
        
        Args:
            days: Number of days to look ahead
            min_importance: Minimum importance level
        
        Returns:
            List of CalendarEvent objects
        """
        events = []
        today = datetime.now()
        end_date = today + timedelta(days=days)
        
        # Check current and next month
        current_month = today.month
        current_year = today.year
        
        for month_offset in range(2):  # Current and next month
            month = current_month + month_offset
            year = current_year
            if month > 12:
                month -= 12
                year += 1
            
            month_events = self.get_events_for_month(year, month, min_importance)
            
            for event in month_events:
                event_date = datetime.strptime(event.date, '%Y-%m-%d')
                
                if today.date() <= event_date.date() <= end_date.date():
                    events.append(event)
        
        # Add weekly events (Jobless Claims - every Thursday)
        next_thursday = self._get_next_thursday(today)
        if next_thursday.date() <= end_date.date():
            events.append(CalendarEvent(
                name="Initial Jobless Claims",
                date=next_thursday.strftime('%Y-%m-%d'),
                time="08:30",
                importance=Importance.MEDIUM,
                category=EventCategory.EMPLOYMENT,
                release_frequency="weekly",
                typical_surprise_impact=1.5,
                source="static"
            ))
        
        # Remove duplicates and sort
        seen = set()
        unique_events = []
        for e in events:
            key = (e.name, e.date)
            if key not in seen:
                seen.add(key)
                unique_events.append(e)
        
        unique_events.sort(key=lambda e: (e.date, e.time))
        
        return unique_events
    
    def get_today_events(self, min_importance: Importance = Importance.LOW) -> List[CalendarEvent]:
        """Get events for today."""
        return [e for e in self.get_upcoming_events(days=1, min_importance=min_importance)
                if e.date == datetime.now().strftime('%Y-%m-%d')]
    
    def get_tomorrow_events(self, min_importance: Importance = Importance.LOW) -> List[CalendarEvent]:
        """Get events for tomorrow."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        return [e for e in self.get_upcoming_events(days=2, min_importance=min_importance)
                if e.date == tomorrow]
    
    # ========================================================================
    # PERPLEXITY ENRICHMENT
    # ========================================================================
    
    def enrich_with_forecasts(self, events: List[CalendarEvent]) -> List[CalendarEvent]:
        """
        Enrich events with consensus forecasts from Perplexity.
        """
        if not self.perplexity_client:
            return events
        
        for event in events:
            try:
                query = f"""
                What is the consensus forecast for {event.name} on {event.date}?
                Give me:
                1. Forecast value
                2. Previous value
                Format: Forecast: XX, Previous: YY
                """
                
                result = self.perplexity_client.search(query)
                
                if result and 'answer' in result:
                    answer = result['answer']
                    
                    # Parse forecast
                    forecast_match = re.search(r'forecast[:\s]+([0-9.,]+)', answer.lower())
                    if forecast_match:
                        event.forecast = forecast_match.group(1)
                    
                    # Parse previous
                    previous_match = re.search(r'previous[:\s]+([0-9.,]+)', answer.lower())
                    if previous_match:
                        event.previous = previous_match.group(1)
                    
                    event.confirmed = True
                    
            except Exception as e:
                logger.debug(f"Forecast fetch error: {e}")
        
        return events
    
    # ========================================================================
    # DISPLAY
    # ========================================================================
    
    def print_upcoming(self, days: int = 7):
        """Print upcoming economic calendar."""
        events = self.get_upcoming_events(days=days)
        
        print("\n" + "=" * 80)
        print(f"📅 ECONOMIC CALENDAR - Next {days} Days")
        print("=" * 80)
        
        if not events:
            print("   No high-impact events scheduled")
            return
        
        current_date = None
        
        for event in events:
            # Print date header if new date
            if event.date != current_date:
                current_date = event.date
                day_name = datetime.strptime(event.date, '%Y-%m-%d').strftime('%A')
                print(f"\n📆 {event.date} ({day_name}):")
            
            # Importance indicator
            imp_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "⚪"}
            imp = imp_emoji.get(event.importance.value, "⚪")
            
            # Hours until
            hours = event.hours_until()
            time_str = f"in {hours:.0f}h" if hours > 0 else "PASSED"
            
            print(f"   {imp} {event.time} ET | {event.name}")
            print(f"      {event.category.value.upper()} | Impact: ±{event.typical_surprise_impact:.1f}% Fed Watch | {time_str}")
            
            if event.forecast:
                print(f"      📊 Forecast: {event.forecast} | Previous: {event.previous}")
        
        print("\n" + "=" * 80)


# ============================================================================
# DEMO
# ============================================================================

def _demo():
    """Demo the economic calendar."""
    print("=" * 80)
    print("📅 ECONOMIC CALENDAR - DEMO")
    print("=" * 80)
    
    calendar = EconomicCalendar()
    
    # Show upcoming events
    calendar.print_upcoming(days=14)
    
    # Show today
    print("\n📆 TODAY'S EVENTS:")
    today_events = calendar.get_today_events()
    if today_events:
        for e in today_events:
            print(f"   {e.time} | {e.name} | {e.importance.value}")
    else:
        print("   No events today")
    
    # Show next week's HIGH importance
    print("\n🔴 HIGH IMPORTANCE (Next 7 days):")
    high_events = calendar.get_upcoming_events(days=7, min_importance=Importance.HIGH)
    for e in high_events:
        print(f"   {e.date} {e.time} | {e.name}")
    
    print("\n✅ Demo complete!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
    _demo()

