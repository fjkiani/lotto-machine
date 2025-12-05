"""
Economic Calendar Event Loader (V2 - Baby-Pips API)
Fetches structured macro/earnings events with built-in importance filtering.

API: economic-trading-forex-events-calendar.p.rapidapi.com/baby-pips
- Has `impact` field (low/medium/high) - perfect for filtering!
- Clean actual/forecast/previous data
- US country filter built-in

Manager's Doctrine:
"Only reference economic events from the provided event_schedule.
Do not invent events or times; if not present, say 'No Scheduled Event'."
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class EventLoader:
    """
    Loads economic calendar events with built-in importance filtering.
    
    Truth oracle for narrative agents – prevents hallucinating events.
    """
    
    def __init__(self, rapidapi_key: str = None):
        """
        Initialize EventLoader.
        
        Args:
            rapidapi_key: RapidAPI key (reads from env if not provided)
        """
        self.rapidapi_key = rapidapi_key or os.getenv('RAPIDAPI_KEY')
        if not self.rapidapi_key:
            logger.warning("⚠️  RAPIDAPI_KEY not set – EventLoader will fail")
        
        self.base_url = "https://economic-trading-forex-events-calendar.p.rapidapi.com/baby-pips"
        self.headers = {
            'x-rapidapi-host': 'economic-trading-forex-events-calendar.p.rapidapi.com',
            'x-rapidapi-key': self.rapidapi_key
        }
        
        logger.info("📅 EventLoader initialized (Baby-Pips API)")
    
    def load_events(self, date: str = None, min_impact: str = "medium") -> Dict:
        """
        Load economic calendar events for a given date.
        
        Args:
            date: Date in YYYY-MM-DD format (defaults to today)
            min_impact: Minimum impact level ("low", "medium", "high")
        
        Returns:
            {
                "macro_events": [
                    {
                        "name": "Nonfarm Payrolls",
                        "time": "08:30",
                        "actual": "119.0k",
                        "forecast": "50.0k",
                        "previous": "22.0k",
                        "impact": "high",
                        "surprise_sigma": +1.38,
                        "country": "US",
                        "currency": "USD"
                    }
                ],
                "earnings": [],  # Future: earnings calendar
                "opex": False,   # Future: options expiration detection
                "has_events": True
            }
        """
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"📅 Loading events for {date} (min_impact={min_impact})")
        
        try:
            macro_events = self._fetch_macro_events(date, min_impact)
            
            # Future: Detect OPEX (3rd Friday of month)
            opex = self._is_opex_day(date)
            
            result = {
                "date": date,
                "macro_events": macro_events,
                "earnings": [],  # TODO: add earnings calendar
                "opex": opex,
                "has_events": len(macro_events) > 0 or opex
            }
            
            logger.info(f"✅ Loaded {len(macro_events)} macro events (impact>={min_impact}), OPEX: {opex}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error loading events for {date}: {e}")
            return {
                "date": date,
                "macro_events": [],
                "earnings": [],
                "opex": False,
                "has_events": False,
                "error": str(e)
            }
    
    def _fetch_macro_events(self, date_str: str, min_impact: str) -> List[Dict]:
        """
        Fetch macro economic events from Baby-Pips API.
        
        Returns:
            List of event dicts filtered by impact level
        """
        try:
            response = requests.get(
                self.base_url, 
                headers=self.headers, 
                timeout=10
            )
            
            if response.status_code != 200:
                logger.warning(f"⚠️  Baby-Pips API returned {response.status_code}")
                return []
            
            data = response.json()
            all_events = data.get('events', [])
            
            # Parse target date
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Filter events
            filtered_events = []
            impact_rank = {"low": 0, "medium": 1, "high": 2}
            min_rank = impact_rank.get(min_impact.lower(), 1)
            
            for event in all_events:
                # Filter by country (US only for now)
                if event.get('country') != 'US':
                    continue
                
                # Filter by impact
                event_impact = event.get('impact', 'low').lower()
                if impact_rank.get(event_impact, 0) < min_rank:
                    continue
                
                # Filter by date
                starts_at = event.get('starts_at')
                if not starts_at:
                    continue
                
                try:
                    event_datetime = datetime.fromisoformat(starts_at.replace('Z', '+00:00'))
                    event_date = event_datetime.date()
                    
                    if event_date != target_date:
                        continue
                    
                    # Process event
                    processed = self._process_event(event, event_datetime)
                    if processed:
                        filtered_events.append(processed)
                        
                except Exception as e:
                    logger.debug(f"Error parsing event datetime: {e}")
                    continue
            
            return filtered_events
                
        except Exception as e:
            logger.error(f"❌ Error fetching macro events: {e}")
            return []
    
    def _process_event(self, raw_event: Dict, event_datetime: datetime) -> Optional[Dict]:
        """
        Process raw event data and calculate surprise scoring.
        
        Surprise scoring:
        - sigma = (actual - forecast) / abs(forecast) * scale_factor
        - For jobs data: 1% miss = 1σ, 2% miss = 2σ, etc.
        """
        try:
            name = raw_event.get('name', '').strip()
            time = event_datetime.strftime('%H:%M')
            actual = raw_event.get('actual')
            forecast = raw_event.get('forecast')
            previous = raw_event.get('previous')
            impact = raw_event.get('impact', 'low').lower()
            country = raw_event.get('country', 'US')
            currency = raw_event.get('currency_code', 'USD')
            
            if not name:
                return None
            
            # Calculate surprise if actual and forecast exist
            surprise_sigma = None
            if actual is not None and forecast is not None:
                try:
                    # Parse values (handle "k", "M", "%")
                    actual_val = self._parse_value(str(actual))
                    forecast_val = self._parse_value(str(forecast))
                    
                    if actual_val is not None and forecast_val is not None and forecast_val != 0:
                        # Calculate % surprise
                        surprise_pct = abs((actual_val - forecast_val) / forecast_val)
                        
                        # Rough sigma estimation
                        # >10% miss = 1σ, >20% = 2σ, >30% = 3σ
                        if surprise_pct > 0.30:
                            surprise_sigma = 3.0 if actual_val > forecast_val else -3.0
                        elif surprise_pct > 0.20:
                            surprise_sigma = 2.0 if actual_val > forecast_val else -2.0
                        elif surprise_pct > 0.10:
                            surprise_sigma = 1.0 if actual_val > forecast_val else -1.0
                        else:
                            surprise_sigma = round((actual_val - forecast_val) / abs(forecast_val) * 10, 2)
                            
                except Exception as e:
                    logger.debug(f"Error calculating surprise: {e}")
            
            return {
                "name": name,
                "time": time,
                "actual": str(actual) if actual is not None else "Pending",
                "forecast": str(forecast) if forecast is not None else "N/A",
                "previous": str(previous) if previous is not None else "N/A",
                "impact": impact,
                "surprise_sigma": surprise_sigma,
                "country": country,
                "currency": currency
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing event: {e}")
            return None
    
    def _parse_value(self, value_str: str) -> Optional[float]:
        """
        Parse economic value string to float.
        
        Handles:
        - "3.5%" -> 3.5
        - "250.0k" -> 250000
        - "1.2M" -> 1200000
        """
        if not value_str or value_str in ['-', 'N/A', 'None']:
            return None
        
        try:
            # Remove % sign
            value_str = value_str.replace('%', '')
            
            # Handle K/M suffixes
            if 'k' in value_str.lower():
                return float(value_str.lower().replace('k', '')) * 1000
            elif 'm' in value_str.lower():
                return float(value_str.lower().replace('m', '')) * 1000000
            else:
                return float(value_str)
        except:
            return None
    
    def _is_opex_day(self, date_str: str) -> bool:
        """
        Check if date is monthly options expiration (3rd Friday).
        
        Args:
            date_str: Date in YYYY-MM-DD format
        
        Returns:
            True if OPEX day
        """
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            
            # Check if Friday (weekday 4)
            if date.weekday() != 4:
                return False
            
            # Check if 3rd week of month (day 15-21)
            if 15 <= date.day <= 21:
                return True
            
            return False
            
        except:
            return False
    
    def get_event_summary(self, events: Dict) -> str:
        """
        Generate human-readable summary of events.
        
        Args:
            events: Output from load_events()
        
        Returns:
            String summary for logging/display
        """
        if not events.get('has_events'):
            return "No scheduled events today"
        
        lines = []
        
        # Macro events
        macro = events.get('macro_events', [])
        if macro:
            lines.append(f"📊 {len(macro)} High-Impact US Events:")
            for event in macro:
                surprise_str = ""
                if event.get('surprise_sigma'):
                    sigma = event['surprise_sigma']
                    surprise_str = f" (Surprise: {sigma:+.2f}σ)"
                
                lines.append(
                    f"  • {event['time']} - {event['name']:40} | {event['impact'].upper():6} | "
                    f"Act: {event['actual']:8} | Fcst: {event['forecast']:8}{surprise_str}"
                )
        
        # OPEX
        if events.get('opex'):
            lines.append("🎯 Monthly OPEX (3rd Friday)")
        
        return "\n".join(lines)


# ========================================================================================
# DEMO / TEST
# ========================================================================================

def _demo():
    """Test EventLoader with today's data."""
    print("=" * 120)
    print("🧪 TESTING EVENT LOADER (BABY-PIPS API - WITH FILTERING)")
    print("=" * 120)
    
    loader = EventLoader()
    
    # Test with today - HIGH impact only
    print("\n📅 Loading HIGH impact US events for today...")
    events_high = loader.load_events(min_impact="high")
    
    print("\n" + loader.get_event_summary(events_high))
    
    # Test with today - MEDIUM+ impact
    print("\n" + "=" * 120)
    print("📅 Loading MEDIUM+ impact US events for today...")
    events_medium = loader.load_events(min_impact="medium")
    
    print("\n" + loader.get_event_summary(events_medium))
    
    # Show full JSON
    print("\n" + "=" * 120)
    print("📋 Full JSON (HIGH impact events):")
    import json
    print(json.dumps(events_high, indent=2))
    
    print("\n" + "=" * 120)
    print("✅ EventLoader test complete!")
    print("=" * 120)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    _demo()
