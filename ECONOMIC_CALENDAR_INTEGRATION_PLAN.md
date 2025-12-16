# 📅 ECONOMIC CALENDAR INTEGRATION PLAN

## Current State

**BEFORE:**
- `EconomicMonitor` uses `EventLoader` (Baby-Pips API) OR static `EconomicCalendar`
- No forecast/previous values
- Limited event data
- No surprise calculation

**AFTER (Trading Economics):**
- ✅ Real forecast vs previous values
- ✅ 528+ events per day (global)
- ✅ Surprise calculation built-in
- ✅ US-focused filtering
- ✅ Caching layer

---

## 🔌 INTEGRATION ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│              ECONOMIC MONITOR (Pipeline Component)           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  PRIMARY: TradingEconomicsWrapper                           │
│  ├── get_us_events() → 14 US events with forecasts         │
│  ├── get_high_impact_events() → Market movers              │
│  ├── get_upcoming_us_events(hours_ahead=4) → Pre-event     │
│  └── calculate_surprise() → Post-release analysis          │
│                                                              │
│  FALLBACK: EventLoader (Baby-Pips API)                     │
│  └── If Trading Economics fails                            │
│                                                              │
│  FALLBACK 2: Static EconomicCalendar                        │
│  └── If both APIs fail                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 STRATEGY: PROACTIVE PRE-EVENT ANALYSIS

### Phase 1: Event Discovery (Continuous)

**When:** Every hour during market hours

**What:**
1. Fetch upcoming US events (next 24 hours)
2. Filter for HIGH importance only
3. Check if already alerted (deduplication)
4. Store in `pending_events` cache

**Code:**
```python
def discover_upcoming_events(self):
    """Discover events 4-24 hours ahead"""
    upcoming = self.te_wrapper.get_upcoming_us_events(hours_ahead=24)
    
    for event in upcoming:
        if event.importance == Importance.HIGH:
            if event.hours_until() >= 4:  # 4-24 hours ahead
                self.pending_events[event.event] = event
```

### Phase 2: Pre-Event Alerting (4 Hours Before)

**When:** 4 hours before each HIGH importance event

**What:**
1. Get event with forecast/previous
2. Calculate expected Fed Watch impact
3. Check DP levels near current price
4. Generate pre-positioning signal
5. Send alert with actionable recommendation

**Alert Format:**
```
⏰ ECONOMIC EVENT IN 4h

📊 CPI YoY (HIGH)
🕐 Release: 08:30 ET
📈 Forecast: 2.8% | Previous: 2.5%

🧠 ANALYSIS:
→ If BEAT (>2.8%): Fed Watch -3.5% → SHORT TLT
→ If MISS (<2.8%): Fed Watch +2.0% → LONG TLT

💡 SUGGESTED POSITION:
WAIT for release OR pre-position SHORT TLT @ $92.80
Stop: $93.20 | Target: $92.20 | R/R: 1.5:1

📍 DP LEVELS:
SPY @ $685.50 (RESISTANCE) - if CPI hot, expect test
```

### Phase 3: Real-Time Monitoring (During Release Window)

**When:** 30 minutes before → 5 minutes after release

**What:**
1. Poll Trading Economics every 10 seconds
2. Check if `actual` value is available
3. Calculate surprise INSTANTLY
4. Generate instant trade signal
5. Send alert within 1 second of release

**Code:**
```python
async def monitor_release_window(self, event: EconomicEvent):
    """Monitor for actual value during release window"""
    release_time = self._parse_release_time(event)
    start_time = release_time - timedelta(minutes=30)
    end_time = release_time + timedelta(minutes=5)
    
    while datetime.now() < end_time:
        if datetime.now() >= start_time:
            # Check for actual value
            updated_event = self.te_wrapper.get_us_events(date=event.date)
            matching = [e for e in updated_event if e.event == event.event]
            
            if matching and matching[0].actual:
                # DATA RELEASED!
                await self._handle_instant_release(matching[0])
                break
        
        await asyncio.sleep(10)  # Check every 10 seconds
```

### Phase 4: Post-Release Analysis (5-60 Minutes After)

**When:** 5min, 15min, 30min, 60min after release

**What:**
1. Track SPY/TLT reaction
2. Compare to predicted move
3. Validate Fed Watch shift
4. Log outcome for ML training
5. Generate follow-up signal if needed

**Code:**
```python
def track_post_release_reaction(self, event: EconomicEvent, surprise: float):
    """Track market reaction at checkpoints"""
    checkpoints = [5, 15, 30, 60]  # minutes
    
    for checkpoint in checkpoints:
        spy_change = self._get_price_change('SPY', checkpoint)
        tlt_change = self._get_price_change('TLT', checkpoint)
        
        self._log_outcome(
            event=event,
            surprise=surprise,
            checkpoint_min=checkpoint,
            spy_change=spy_change,
            tlt_change=tlt_change,
            predicted_move=self.predicted_move
        )
```

---

## 📊 DATA FLOW

```
1. DISCOVERY (Hourly)
   Trading Economics → get_upcoming_us_events(24h)
   ↓
   Filter HIGH importance
   ↓
   Store in pending_events

2. PRE-EVENT ALERT (4h before)
   pending_events → Check hours_until()
   ↓
   Get forecast/previous
   ↓
   Calculate Fed Watch scenarios
   ↓
   Generate pre-positioning signal
   ↓
   Send Discord alert

3. RELEASE MONITORING (30min before → 5min after)
   Poll Trading Economics every 10s
   ↓
   Detect actual value
   ↓
   Calculate surprise
   ↓
   Generate instant signal
   ↓
   Send Discord alert (<1s latency)

4. POST-RELEASE TRACKING (5-60min after)
   Track SPY/TLT at checkpoints
   ↓
   Log outcomes
   ↓
   Update ML models
```

---

## 🔧 IMPLEMENTATION STEPS

### Step 1: Update EconomicMonitor to Use Trading Economics

**File:** `live_monitoring/pipeline/components/economic_monitor.py`

**Changes:**
1. Replace `EventLoader` with `TradingEconomicsWrapper` as PRIMARY
2. Keep `EventLoader` as FALLBACK 1
3. Keep `EconomicCalendar` as FALLBACK 2
4. Use `EconomicEvent` dataclass from Trading Economics wrapper

### Step 2: Add Pre-Event Discovery Loop

**New Method:**
```python
def discover_upcoming_events(self):
    """Discover events 4-24 hours ahead"""
    # Use Trading Economics
    upcoming = self.te_wrapper.get_upcoming_us_events(hours_ahead=24)
    
    # Filter HIGH importance
    high_impact = [e for e in upcoming if e.importance == Importance.HIGH]
    
    # Store for pre-event alerting
    for event in high_impact:
        if 4 <= event.hours_until() <= 24:
            self.pending_events[event.event] = event
```

### Step 3: Add Release Window Monitoring

**New Method:**
```python
async def monitor_release_window(self, event: EconomicEvent):
    """Monitor for actual value during release window"""
    # Poll every 10 seconds during release window
    # Detect actual value
    # Calculate surprise
    # Generate instant signal
```

### Step 4: Enhance Pre-Event Alerts

**Current:** Basic alert with Fed Watch scenarios
**Enhanced:** Include forecast/previous, DP levels, ML predictions

---

## 📋 ALERT TIMELINE

| Time | Action | Alert Type |
|------|--------|------------|
| **T-24h** | Discover event | None (internal) |
| **T-4h** | Pre-event alert | Pre-positioning signal |
| **T-30min** | Start monitoring | None (internal) |
| **T-0** | Data released | Instant surprise alert |
| **T+5min** | Track reaction | Outcome checkpoint |
| **T+15min** | Track reaction | Outcome checkpoint |
| **T+30min** | Track reaction | Outcome checkpoint |
| **T+60min** | Final outcome | Learning log |

---

## 🎯 KEY FEATURES

### 1. **Forecast/Previous Values**
- Know EXACTLY what market expects
- Calculate surprise magnitude instantly
- Predict Fed Watch shift accurately

### 2. **Proactive Positioning**
- Alert 4h before release
- Pre-position based on forecast
- Exit on release or hold for confirmation

### 3. **Instant Reaction**
- Detect actual value in <1 second
- Calculate surprise immediately
- Generate trade signal instantly

### 4. **Learning Loop**
- Track every outcome
- Compare predicted vs actual
- Retrain ML models weekly

---

## 🚀 EXPECTED EDGE

**Pre-Event Positioning:**
- 4h warning → Position before crowd
- Forecast/previous context → Better entry timing
- **Edge: +5-10% win rate**

**Instant Surprise Detection:**
- <1s latency → Faster than manual
- Automatic calculation → No human error
- **Edge: +10-15% win rate**

**Combined:**
- Pre-position + instant confirmation
- **Total Edge: +15-25% win rate improvement**

---

## 📁 FILES TO UPDATE

1. ✅ `live_monitoring/enrichment/apis/trading_economics.py` - DONE
2. ⏳ `live_monitoring/pipeline/components/economic_monitor.py` - UPDATE
3. ⏳ `live_monitoring/pipeline/orchestrator.py` - UPDATE (use Trading Economics)
4. ⏳ `live_monitoring/agents/economic/pre_event_analyzer.py` - NEW
5. ⏳ `live_monitoring/agents/economic/surprise_detector.py` - NEW

---

**STATUS: READY FOR IMPLEMENTATION! 🚀**

