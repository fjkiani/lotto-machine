# DP-AWARE SIGNAL ENGINE REFACTORING PLAN

## CURRENT STATE (HALF-ASS IMPLEMENTATION)
- ✅ Real DP data loaded (1,161 levels from 10/16)
- ✅ Basic signal detection when price is near level
- ❌ No minute-by-minute replay with DP interaction tracking
- ❌ No magnet approach detection
- ❌ No proper cycle-by-cycle logging
- ❌ No regime-aware decision making
- ❌ Missing institutional flow confirmation

## TARGET STATE (INSTITUTIONAL-GRADE)

### 1. DP MAGNET TRACKING MODULE
**Purpose:** Track price distance to key DP levels in real-time

**Features:**
- Identify "active magnets" (levels within 1-2% of current price)
- Calculate approach velocity (how fast price is moving toward level)
- Detect "bounce zones" (price rejected from level)
- Alert BEFORE price hits the level (predictive)

**Output:**
```json
{
  "timestamp": "2025-10-17T10:30:00",
  "price": 662.50,
  "nearest_support": 660.70,
  "distance": -1.80,
  "distance_pct": -0.27,
  "approach_velocity": -0.15,
  "magnet_strength": 3192097,
  "status": "APPROACHING_SUPPORT",
  "eta_minutes": 8
}
```

### 2. MINUTE-BY-MINUTE REPLAY ENGINE
**Purpose:** Validate signals against actual 10/17 session

**Features:**
- Load intraday price/volume data for 10/17
- Process minute-by-minute with real DP levels from 10/16
- Log EVERY cycle's decision (signal/no signal/await)
- Track regime changes throughout the day
- Identify actual DP level interactions

**Output:**
- CSV log with every minute's state
- Summary of signals fired vs missed
- DP level hit/bounce/break statistics

### 3. INSTITUTIONAL FLOW CONFIRMATION
**Purpose:** Only signal when DP + volume + momentum align

**Logic:**
```python
def should_signal(price, dp_structure, volume, momentum):
    # 1. Check if at DP level
    at_level = is_near_dp_level(price, dp_structure.battlegrounds)
    
    # 2. Check volume confirmation
    volume_spike = volume > avg_volume * 1.5
    
    # 3. Check momentum alignment
    if at_support:
        momentum_aligned = momentum > 0  # Bouncing up
    else:
        momentum_aligned = momentum < 0  # Rejecting down
    
    # 4. Check for DP magnet breakout
    if price > dp_level + (dp_level * 0.002):  # 0.2% above
        return "BREAKOUT"
    
    # ALL conditions must align
    return at_level and volume_spike and momentum_aligned
```

### 4. CYCLE-BY-CYCLE LOGGING
**Purpose:** Log EVERY decision with full reasoning

**Format:**
```
[2025-10-17 10:30:00] CYCLE_START
Price: $662.50 | Volume: 1.2M | Regime: DOWNTREND
Nearest DP Support: $660.70 (-$1.80, -0.27%)
Approach Velocity: -$0.15/min (ETA: 8min)
Volume vs Avg: 0.8x (BELOW_AVG)
Momentum: -0.45 (BEARISH)
Decision: NO_SIGNAL - Awaiting level, volume not confirmed
---
```

### 5. REGIME-AWARE THRESHOLDS
**Purpose:** Adjust signal sensitivity based on market regime

**Regimes:**
- **STRONG_TREND**: Tight stops, quick exits
- **WEAK_TREND**: Normal thresholds
- **CHOP**: Wide stops, fewer signals
- **BREAKOUT**: Aggressive entry, trailing stops

**Threshold Adjustments:**
```python
if regime == "STRONG_TREND":
    distance_threshold = 0.001  # 0.1% (tighter)
    volume_multiplier = 1.3     # Lower bar
elif regime == "CHOP":
    distance_threshold = 0.005  # 0.5% (wider)
    volume_multiplier = 2.0     # Higher bar
```

## IMPLEMENTATION PRIORITY

### PHASE 1: REPLAY ENGINE (IMMEDIATE)
1. Build minute replay for 10/17 with 10/16 DP data
2. Log every cycle's state and decision
3. Identify actual DP level interactions
4. Validate signal logic

### PHASE 2: MAGNET TRACKING (NEXT)
1. Add approach velocity calculation
2. Implement "awaiting level" status
3. Add predictive alerting

### PHASE 3: FLOW CONFIRMATION (THEN)
1. Add volume spike detection
2. Add momentum alignment check
3. Implement composite signal logic

### PHASE 4: REGIME-AWARE (FINAL)
1. Calculate regime from price action
2. Adjust thresholds dynamically
3. Add regime change logging

## SUCCESS CRITERIA

✅ **Every minute logged** with full state
✅ **Signals fire AT DP levels** with volume/momentum confirmation
✅ **No false signals** away from DP levels
✅ **Clear "awaiting level" states** when approaching
✅ **Regime detected** and logged each cycle
✅ **Replay validates** against actual 10/17 session

## FILES TO CREATE/MODIFY

### New Files:
- `core/detectors/dp_magnet_tracker.py` - Magnet approach detection
- `core/replay_engine.py` - Minute-by-minute replay
- `core/regime_detector.py` - Regime classification
- `validate_10_17_session.py` - Run full validation

### Modified Files:
- `core/filters/dp_aware_signal_filter.py` - Add flow confirmation
- `core/core_signals_runner.py` - Integrate new modules
- `configs/signal_config.py` - Configurable thresholds

## NEXT IMMEDIATE ACTION

**BUILD THE REPLAY ENGINE** to validate 10/17 session with real 10/16 DP data and see where signals SHOULD have fired vs where they actually fired!

---

**NO MORE HALF-ASS WORK. WE BUILD THIS RIGHT.** 🔥


