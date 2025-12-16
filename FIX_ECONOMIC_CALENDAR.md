# Fix: Replace Hard-Coded Economic Calendar with Real API

## 🔧 THE PROBLEM

**Current State:**
- `run_all_monitors.py` uses `EconomicCalendar()` - **HARD-CODED**
- Calculates dates from patterns (first Friday, mid-month, etc.)
- **Doesn't fetch real economic calendar data**

**What We Have:**
- `EventLoader` class - fetches REAL data from Baby-Pips API
- Gets actual/forecast/previous values
- Filters by impact (high/medium/low)
- **NOT being used in run_all_monitors.py**

## ✅ THE FIX

### Step 1: Update `run_all_monitors.py` initialization

**Current (Line 246):**
```python
self.econ_calendar = EconomicCalendar()
```

**Should Be:**
```python
# Try EventLoader first (real API), fallback to EconomicCalendar
try:
    from live_monitoring.enrichment.apis.event_loader import EventLoader
    self.econ_calendar = EventLoader()
    self.econ_calendar_type = "api"  # Track which we're using
    logger.info("   ✅ Economic Calendar: REAL API (EventLoader)")
except Exception as e:
    logger.warning(f"   ⚠️ EventLoader failed, using static calendar: {e}")
    from live_monitoring.agents.economic.calendar import EconomicCalendar
    self.econ_calendar = EconomicCalendar()
    self.econ_calendar_type = "static"
    logger.info("   ⚠️ Economic Calendar: STATIC (fallback)")
```

### Step 2: Update `check_economics()` method

**Current (Line 608-730):**
- Uses `self.econ_calendar.get_upcoming_events()`
- Uses `self.econ_calendar.get_today_events()`

**Should Be:**
```python
def check_economics(self):
    """Check for upcoming economic events - uses REAL API"""
    if not self.econ_enabled:
        return
    
    if not self.econ_calendar:
        return
    
    logger.info("📊 Checking Economic Calendar...")
    
    try:
        # Use EventLoader API if available
        if self.econ_calendar_type == "api":
            # EventLoader returns dict with "macro_events"
            today = datetime.now().strftime('%Y-%m-%d')
            events_data = self.econ_calendar.load_events(date=today, min_impact="medium")
            
            macro_events = events_data.get('macro_events', [])
            
            logger.info(f"   📅 Found {len(macro_events)} events for today (API)")
            
            for event in macro_events:
                event_name = event.get('name', 'Unknown')
                event_time = event.get('time', '08:30')
                impact = event.get('impact', 'medium')
                actual = event.get('actual')
                forecast = event.get('forecast')
                previous = event.get('previous')
                
                # Check if we should alert
                # (same logic as before, but using API data)
                
        else:
            # Fallback to static EconomicCalendar
            from live_monitoring.agents.economic.calendar import Importance
            upcoming = self.econ_calendar.get_upcoming_events(days=2, min_importance=Importance.HIGH)
            # ... existing logic ...
            
    except Exception as e:
        logger.error(f"   ❌ Economic check error: {e}")
```

### Step 3: Test with Dec 10, 2025

```python
# Test EventLoader for Dec 10
from live_monitoring.enrichment.apis.event_loader import EventLoader

loader = EventLoader()
events = loader.load_events("2025-12-10", min_impact="medium")

print(f"Events for Dec 10: {len(events.get('macro_events', []))}")
for event in events.get('macro_events', []):
    print(f"  {event.get('time')} | {event.get('name')} | {event.get('impact')}")
```

## 📊 BENEFITS

1. **Real Data:** Fetches actual economic calendar from API
2. **Actual/Forecast/Previous:** Gets real values, not estimates
3. **Impact Filtering:** Only high/medium impact events
4. **Fallback:** Still works if API fails (uses static calendar)
5. **Historical Dates:** Can fetch any date (Dec 10, 2025, etc.)

## ⚠️ REQUIREMENTS

- `RAPIDAPI_KEY` environment variable must be set
- Baby-Pips API access via RapidAPI
- Falls back gracefully if API unavailable

## 🎯 NEXT STEPS

1. Update `run_all_monitors.py` to use EventLoader
2. Test with today's date
3. Test with Dec 10, 2025 (historical)
4. Verify fallback works if API fails
5. Update documentation

---

**Status:** Ready to implement  
**Priority:** HIGH - We're using hard-coded data instead of real API

