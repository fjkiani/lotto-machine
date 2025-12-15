"""
Trading Economics Calendar Integration
======================================

Clean wrapper for Trading Economics MCP client with:
- Fixed column parsing
- Country code mapping
- Importance normalization
- US-focused filtering
- Caching layer

This replaces the broken hard-coded EconomicCalendar!
"""

import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json
import hashlib

logger = logging.getLogger(__name__)

# Use Trading Economics API directly (superior to HTML scraping)
import requests


class Importance(Enum):
    """Event importance levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class EventCategory(Enum):
    """Economic event categories"""
    INFLATION = "inflation"
    EMPLOYMENT = "employment"
    GROWTH = "growth"
    CONSUMER = "consumer"
    MANUFACTURING = "manufacturing"
    HOUSING = "housing"
    CENTRAL_BANK = "central_bank"
    TRADE = "trade"
    OTHER = "other"


@dataclass
class EconomicEvent:
    """Normalized economic event"""
    date: str  # YYYY-MM-DD
    time: str  # HH:MM (24h)
    country: str  # Full country name
    country_code: str  # 2-letter code
    event: str  # Event name
    importance: Importance
    category: EventCategory
    actual: Optional[str] = None
    forecast: Optional[str] = None
    previous: Optional[str] = None
    surprise: Optional[float] = None  # Calculated after release
    
    def hours_until(self) -> float:
        """Calculate hours until event"""
        try:
            # Parse time (handle AM/PM format)
            time_str = self.time
            if 'AM' in time_str or 'PM' in time_str:
                # Convert 12h to 24h
                time_obj = datetime.strptime(time_str, "%I:%M %p")
                time_24h = time_obj.strftime("%H:%M")
            else:
                time_24h = self.time
            
            event_dt = datetime.strptime(f"{self.date} {time_24h}", "%Y-%m-%d %H:%M")
            delta = event_dt - datetime.now()
            return delta.total_seconds() / 3600
        except Exception:
            return -1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'date': self.date,
            'time': self.time,
            'country': self.country,
            'country_code': self.country_code,
            'event': self.event,
            'importance': self.importance.value,
            'category': self.category.value,
            'actual': self.actual,
            'forecast': self.forecast,
            'previous': self.previous,
            'surprise': self.surprise
        }


class TradingEconomicsWrapper:
    """
    Clean wrapper for Trading Economics data.
    
    Fixes parsing issues and provides normalized events.
    """
    
    # Country code to full name mapping
    COUNTRY_CODES = {
        'US': 'United States',
        'CN': 'China',
        'JP': 'Japan',
        'DE': 'Germany',
        'GB': 'United Kingdom',
        'UK': 'United Kingdom',
        'FR': 'France',
        'IT': 'Italy',
        'CA': 'Canada',
        'AU': 'Australia',
        'BR': 'Brazil',
        'IN': 'India',
        'RU': 'Russia',
        'KR': 'South Korea',
        'ES': 'Spain',
        'MX': 'Mexico',
        'NL': 'Netherlands',
        'CH': 'Switzerland',
        'BE': 'Belgium',
        'SE': 'Sweden',
        'AT': 'Austria',
        'EA': 'Euro Area',
        'EU': 'European Union',
        'ID': 'Indonesia',
        'SA': 'Saudi Arabia',
        'TR': 'Turkey',
        'NO': 'Norway',
        'NZ': 'New Zealand',
        'SG': 'Singapore',
        'HK': 'Hong Kong',
    }
    
    # Event name to category mapping
    CATEGORY_KEYWORDS = {
        EventCategory.INFLATION: ['inflation', 'cpi', 'ppi', 'pce', 'price'],
        EventCategory.EMPLOYMENT: ['payroll', 'employment', 'unemployment', 'jobless', 'jobs', 'labor', 'adp'],
        EventCategory.GROWTH: ['gdp', 'growth', 'output'],
        EventCategory.CONSUMER: ['retail', 'consumer', 'confidence', 'sentiment', 'spending'],
        EventCategory.MANUFACTURING: ['pmi', 'manufacturing', 'industrial', 'production', 'factory', 'ism'],
        EventCategory.HOUSING: ['housing', 'home', 'building', 'construction', 'mortgage'],
        EventCategory.CENTRAL_BANK: ['fed', 'fomc', 'ecb', 'boe', 'boj', 'rate decision', 'speech', 'minutes'],
        EventCategory.TRADE: ['trade', 'export', 'import', 'balance'],
    }
    
    # High-impact US events
    US_HIGH_IMPACT = [
        'cpi', 'inflation rate', 'non-farm payroll', 'nfp', 'unemployment rate',
        'fomc', 'fed rate', 'gdp', 'retail sales', 'pce price', 'ism manufacturing',
        'ism services', 'consumer confidence', 'producer price', 'ppi'
    ]
    
    def __init__(self, cache_ttl_minutes: int = 30, api_credentials: Optional[str] = None):
        """
        Initialize wrapper using Trading Economics JSON API.
        
        Args:
            cache_ttl_minutes: How long to cache results
            api_credentials: API credentials in format "key:secret" or None for public access
        """
        self.cache_ttl = cache_ttl_minutes
        self._cache: Dict[str, tuple] = {}  # key -> (data, timestamp)
        self.api_credentials = api_credentials or "guest:guest"  # Public access
        self.api_base_url = "https://api.tradingeconomics.com/calendar"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        logger.info("✅ TradingEconomicsWrapper initialized (API-based)")
    
    def _get_cached(self, key: str) -> Optional[List[EconomicEvent]]:
        """Get cached results if still valid"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl * 60:
                return data
        return None
    
    def _set_cache(self, key: str, data: List[EconomicEvent]):
        """Cache results"""
        self._cache[key] = (data, datetime.now())
    
    def _normalize_event_from_api(self, api_event: Dict[str, Any]) -> Optional[EconomicEvent]:
        """
        Normalize an event from Trading Economics API response.
        
        API provides 23 fields with perfect accuracy.
        """
        try:
            # Parse date/time from ISO format
            event_datetime = None
            date_str = None
            time_str = None
            
            if api_event.get('Date'):
                try:
                    dt = datetime.fromisoformat(api_event['Date'].replace('Z', '+00:00'))
                    date_str = dt.strftime('%Y-%m-%d')
                    time_str = dt.strftime('%H:%M')
                    event_datetime = dt
                except:
                    # Fallback parsing
                    date_part = api_event['Date'].split('T')[0] if 'T' in api_event['Date'] else None
                    time_part = api_event['Date'].split('T')[1].split(':')[0:2] if 'T' in api_event['Date'] else None
                    date_str = date_part or datetime.now().strftime('%Y-%m-%d')
                    time_str = ':'.join(time_part) if time_part else ''
            
            if not date_str:
                date_str = datetime.now().strftime('%Y-%m-%d')
            
            # Get country
            country_full = api_event.get('Country', '')
            
            # Map country name to code
            country_code = None
            for code, name in self.COUNTRY_CODES.items():
                if country_full.lower() == name.lower():
                    country_code = code
                    break
            
            # If not found, try to extract from country name
            if not country_code:
                # Try common patterns
                if 'United States' in country_full:
                    country_code = 'US'
                elif 'China' in country_full:
                    country_code = 'CN'
                elif 'Japan' in country_full:
                    country_code = 'JP'
                elif 'Germany' in country_full:
                    country_code = 'DE'
                elif 'United Kingdom' in country_full or 'UK' in country_full:
                    country_code = 'GB'
                elif 'France' in country_full:
                    country_code = 'FR'
                elif 'Italy' in country_full:
                    country_code = 'IT'
                elif 'Canada' in country_full:
                    country_code = 'CA'
                elif 'Australia' in country_full:
                    country_code = 'AU'
                elif 'Brazil' in country_full:
                    country_code = 'BR'
                elif 'India' in country_full:
                    country_code = 'IN'
                elif 'Russia' in country_full:
                    country_code = 'RU'
                elif 'South Korea' in country_full or 'Korea' in country_full:
                    country_code = 'KR'
                elif 'Spain' in country_full:
                    country_code = 'ES'
                elif 'Mexico' in country_full:
                    country_code = 'MX'
                elif 'Netherlands' in country_full:
                    country_code = 'NL'
                elif 'Switzerland' in country_full:
                    country_code = 'CH'
                elif 'Belgium' in country_full:
                    country_code = 'BE'
                elif 'Sweden' in country_full:
                    country_code = 'SE'
                elif 'Austria' in country_full:
                    country_code = 'AT'
                elif 'Euro Area' in country_full or 'European Union' in country_full:
                    country_code = 'EA'
                else:
                    country_code = country_full[:2].upper() if len(country_full) >= 2 else 'XX'
            
            # Get event name
            event_name = api_event.get('Event', '')
            
            # Get importance (API provides numeric 1-3)
            importance_val = api_event.get('Importance', 2)
            try:
                importance = Importance(int(importance_val))
            except:
                importance = Importance.MEDIUM
            
            # Boost importance for known high-impact events
            event_lower = event_name.lower()
            if country_code == 'US':
                for high_impact in self.US_HIGH_IMPACT:
                    if high_impact in event_lower:
                        importance = Importance.HIGH
                        break
            
            # Categorize event
            category = EventCategory.OTHER
            for cat, keywords in self.CATEGORY_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in event_lower:
                        category = cat
                        break
            
            # Get actual/forecast/previous
            actual = api_event.get('Actual', '')
            forecast = api_event.get('Forecast', '')
            previous = api_event.get('Previous', '')
            
            # Clean up values
            if previous:
                previous = previous.replace('®', '').strip()
            
            return EconomicEvent(
                date=date_str,
                time=time_str,
                country=country_full,
                country_code=country_code,
                event=event_name,
                importance=importance,
                category=category,
                actual=actual if actual else None,
                forecast=forecast if forecast else None,
                previous=previous if previous else None
            )
            
        except Exception as e:
            logger.debug(f"Failed to normalize API event: {e}")
            return None
    
    def _normalize_event(self, raw: Dict[str, Any]) -> Optional[EconomicEvent]:
        """
        Normalize a raw event from the parser (legacy method for HTML scraping).
        
        Kept for backward compatibility, but should use _normalize_event_from_api instead.
        """
        # Try to detect if this is an API response
        if 'CalendarId' in raw or 'Country' in raw:
            return self._normalize_event_from_api(raw)
        
        # Legacy HTML parsing normalization
        try:
            # Extract fields (handling misalignment)
            time_str = raw.get('time', '')
            country_code = raw.get('country', '')
            
            # The 'actual' field often contains the event name due to misalignment
            event_name = raw.get('actual', '') or raw.get('event', '')
            
            # Skip header rows
            if 'Wednesday' in time_str or 'Thursday' in time_str or 'Friday' in time_str:
                return None
            if country_code in ['Actual', 'Consensus', 'Forecast']:
                return None
            
            # Map country code to full name
            country_full = self.COUNTRY_CODES.get(country_code, country_code)
            
            # Extract forecast/previous
            forecast = raw.get('forecast')
            previous = raw.get('previous')
            
            # Clean up previous (remove ® symbol)
            if previous:
                previous = previous.replace('®', '').strip()
            
            # Determine importance (default to MEDIUM if not parsed)
            importance_val = raw.get('importance', 2)
            try:
                importance = Importance(int(importance_val))
            except:
                importance = Importance.MEDIUM
            
            # Boost importance for known high-impact events
            event_lower = event_name.lower()
            if country_code == 'US':
                for high_impact in self.US_HIGH_IMPACT:
                    if high_impact in event_lower:
                        importance = Importance.HIGH
                        break
            
            # Categorize event
            category = EventCategory.OTHER
            for cat, keywords in self.CATEGORY_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in event_lower:
                        category = cat
                        break
            
            # Get date
            date = raw.get('date', datetime.now().strftime('%Y-%m-%d'))
            
            return EconomicEvent(
                date=date,
                time=time_str,
                country=country_full,
                country_code=country_code,
                event=event_name,
                importance=importance,
                category=category,
                actual=None,  # Not yet released
                forecast=forecast,
                previous=previous
            )
            
        except Exception as e:
            logger.debug(f"Failed to normalize event: {e}")
            return None
    
    def get_events(
        self,
        date: Optional[str] = None,
        countries: Optional[List[str]] = None,
        importance: Optional[str] = None,
        days_ahead: int = 1
    ) -> List[EconomicEvent]:
        """
        Get economic events from Trading Economics API.
        
        Args:
            date: Specific date (YYYY-MM-DD) or None for today
            countries: List of country codes or names
            importance: 'low', 'medium', or 'high'
            days_ahead: Number of days to fetch
        
        Returns:
            List of normalized EconomicEvent objects
        """
        # Build cache key
        cache_key = hashlib.md5(f"{date}:{countries}:{importance}:{days_ahead}".encode()).hexdigest()
        
        # Check cache
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.debug(f"Using cached results ({len(cached)} events)")
            return cached
        
        try:
            # Determine date range
            if date:
                start_date = date
                end_date = date
            else:
                start_date = datetime.now().strftime('%Y-%m-%d')
                end_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            
            # Build API parameters
            params = {'c': self.api_credentials}
            params['d1'] = start_date
            params['d2'] = end_date
            
            # Importance filtering
            if importance:
                imp_map = {'low': '1', 'medium': '2', 'high': '3'}
                params['importance'] = imp_map.get(importance.lower(), '2')
            
            # Country filtering
            if countries:
                # Normalize country names for API
                country_list = []
                for c in countries:
                    # Try to map to standard name
                    normalized = c.lower().strip()
                    # Check if it's a code
                    if normalized.upper() in self.COUNTRY_CODES:
                        country_list.append(self.COUNTRY_CODES[normalized.upper()].lower())
                    elif normalized in [v.lower() for v in self.COUNTRY_CODES.values()]:
                        country_list.append(normalized)
                    else:
                        country_list.append(normalized)
                
                params['countries'] = ','.join(country_list)
            
            # Fetch from API
            logger.info(f"Fetching events from API: {start_date} to {end_date}")
            response = self.session.get(self.api_base_url, params=params, timeout=30)
            response.raise_for_status()
            
            raw_events = response.json()
            logger.info(f"Fetched {len(raw_events)} raw events from Trading Economics API")
            
            # Normalize events from API response
            events = []
            for raw in raw_events:
                event = self._normalize_event_from_api(raw)
                if event:
                    events.append(event)
            
            # Additional filtering (in case API filtering didn't work perfectly)
            if countries:
                country_filter = set()
                for c in countries:
                    country_filter.add(c.lower())
                    # Also add mapping
                    for code, name in self.COUNTRY_CODES.items():
                        if c.lower() in [code.lower(), name.lower()]:
                            country_filter.add(code.lower())
                            country_filter.add(name.lower())
                
                events = [e for e in events if 
                         e.country_code.lower() in country_filter or
                         e.country.lower() in country_filter]
            
            # Filter by importance
            if importance:
                imp_level = {'low': 1, 'medium': 2, 'high': 3}.get(importance.lower(), 1)
                events = [e for e in events if e.importance.value >= imp_level]
            
            logger.info(f"Normalized to {len(events)} events")
            
            # Cache results
            self._set_cache(cache_key, events)
            
            return events
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch Trading Economics events: {e}")
            return []
    
    def get_us_events(
        self,
        date: Optional[str] = None,
        importance: str = "medium",
        days_ahead: int = 1
    ) -> List[EconomicEvent]:
        """
        Get US-only events.
        
        Args:
            date: Specific date or None for today
            importance: Minimum importance level
            days_ahead: Number of days to fetch
        
        Returns:
            List of US economic events
        """
        return self.get_events(
            date=date,
            countries=['US', 'United States'],
            importance=importance,
            days_ahead=days_ahead
        )
    
    def get_high_impact_events(
        self,
        date: Optional[str] = None,
        days_ahead: int = 3
    ) -> List[EconomicEvent]:
        """
        Get high-impact events across all countries.
        
        Args:
            date: Start date or None for today
            days_ahead: Number of days to fetch
        
        Returns:
            List of high-impact events
        """
        return self.get_events(
            date=date,
            importance="high",
            days_ahead=days_ahead
        )
    
    def get_upcoming_us_events(self, hours_ahead: int = 24) -> List[EconomicEvent]:
        """
        Get upcoming US events within specified hours.
        
        Args:
            hours_ahead: Hours to look ahead
        
        Returns:
            List of upcoming US events sorted by time
        """
        events = self.get_us_events(days_ahead=2)
        
        # Filter to upcoming only
        upcoming = [e for e in events if 0 < e.hours_until() <= hours_ahead]
        
        # Sort by time
        upcoming.sort(key=lambda e: e.hours_until())
        
        return upcoming
    
    def calculate_surprise(self, actual: str, forecast: str, previous: str) -> Optional[float]:
        """
        Calculate surprise magnitude.
        
        surprise = (actual - forecast) / abs(previous) if previous != 0 else (actual - forecast)
        
        Args:
            actual: Actual value (e.g., "0.4%")
            forecast: Forecast value (e.g., "0.3%")
            previous: Previous value (e.g., "0.2%")
        
        Returns:
            Surprise as a float (positive = beat, negative = miss)
        """
        try:
            # Parse percentages
            def parse_pct(s: str) -> float:
                s = s.replace('%', '').replace(',', '').strip()
                return float(s)
            
            actual_val = parse_pct(actual)
            forecast_val = parse_pct(forecast)
            previous_val = parse_pct(previous)
            
            # Calculate surprise
            if abs(previous_val) > 0.001:
                return (actual_val - forecast_val) / abs(previous_val)
            else:
                return actual_val - forecast_val
            
        except Exception as e:
            logger.debug(f"Failed to calculate surprise: {e}")
            return None


# Convenience function
def get_trading_economics() -> TradingEconomicsWrapper:
    """Get or create Trading Economics wrapper instance"""
    if not hasattr(get_trading_economics, '_instance'):
        get_trading_economics._instance = TradingEconomicsWrapper()
    return get_trading_economics._instance


# Test when run directly
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    wrapper = TradingEconomicsWrapper()
    
    print("\n📅 TODAY'S US EVENTS:")
    print("-" * 50)
    us_events = wrapper.get_us_events()
    for event in us_events[:10]:
        print(f"  {event.time} | {event.event} | {event.importance.name}")
        if event.forecast:
            print(f"    Forecast: {event.forecast} | Previous: {event.previous}")
    
    print(f"\n  Total: {len(us_events)} US events")
    
    print("\n📊 HIGH-IMPACT EVENTS (Next 3 Days):")
    print("-" * 50)
    high_impact = wrapper.get_high_impact_events(days_ahead=3)
    for event in high_impact[:10]:
        print(f"  {event.date} {event.time} | {event.country_code} | {event.event}")
    
    print(f"\n  Total: {len(high_impact)} high-impact events")

