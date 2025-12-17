# 🚨 CRITICAL BUG: Selloff/Rally Signals Not Triggering

**Date:** Dec 17, 2025  
**Severity:** CRITICAL - Missed major selloff today (-1% SPY, -1.6% QQQ)  
**Status:** ROOT CAUSE IDENTIFIED

---

## 📊 Evidence

### Today's Market Action (Dec 17, 2025):

**SPY:**
- Open: $679.89
- Low: $673.00  
- Change: **-1.01% from open**
- ✅ SHOULD HAVE TRIGGERED selloff alert

**QQQ:**
- Open: $613.09
- Low: $602.72
- Change: **-1.64% from open**
- ✅ SHOULD HAVE TRIGGERED selloff alert

### Signal Criteria (from `signal_generator.py`):

**METHOD 1 - FROM OPEN:**
- Threshold: -0.25% from day open
- SPY: -1.01% ✅ PASSES
- QQQ: -1.64% ✅ PASSES

**METHOD 2 - MOMENTUM:**
- Threshold: 3+ consecutive red bars
- Both tickers had 3-4 red bars ✅ PASSES

**RESULT: Both signals SHOULD have triggered but DIDN'T!**

---

## 🐛 ROOT CAUSE

### The Bug Chain:

1. **`momentum_detector.py` (lines 38-46):**
   ```python
   hist = ticker.history(period='1d', interval='1m')
   minute_bars = hist.tail(30)  # ❌ BUG: Only last 30 minutes!
   ```

2. **`signal_generator.py` (line 326):**
   ```python
   day_open = float(minute_bars["Open"].iloc[0])  # ❌ Uses wrong open!
   ```

### Why It Fails:

- `hist.tail(30)` returns only the **last 30 minutes** of trading
- `minute_bars["Open"].iloc[0]` becomes the open of the LAST 30 MIN, not the DAY
- **Today's example:**
  - True day open: $679.89
  - Last 30 min open: $674.39 ❌ OFF BY $5.50!
  
- FROM OPEN detection calculates: `(673.06 - 674.39) / 674.39 = -0.20%`
- This is BELOW the -0.25% threshold, so it doesn't trigger!
- **But the REAL move was -0.99% from day open!**

### Variable Name Collision Bug:

Additionally, `signal_generator.py` has TWO uses of `recent_closes`:
1. Line 331-337: Defined for momentum detection (last 30 bars)
2. Line 364: Redefined for rolling window (last 10 bars)

This causes the first definition to be overwritten before Method 2 uses it!

---

## ✅ THE FIX

### Part 1: Pass Full Day Data (`momentum_detector.py`)

```python
# BEFORE (line 45):
minute_bars = hist.tail(30)  # ❌ Wrong!

# AFTER:
minute_bars = hist  # ✅ Pass full day data
```

### Part 2: Use Recent Bars for Momentum (`signal_generator.py`)

```python
# After line 328, ADD:
# For momentum detection, use only recent bars (last 30)
if len(minute_bars) > 30:
    recent_bars_for_momentum = minute_bars.tail(30)
    momentum_closes = recent_bars_for_momentum["Close"]
    momentum_volumes = recent_bars_for_momentum["Volume"]
else:
    momentum_closes = closes
    momentum_volumes = volumes

# Then in METHOD 2 (line 351), CHANGE:
for i in range(len(closes) - 1, max(0, len(closes) - 10), -1):
# TO:
for i in range(len(momentum_closes) - 1, max(0, len(momentum_closes) - 10), -1):

# And change all `closes.iloc[i]` to `momentum_closes.iloc[i]`

# Similarly for METHOD 3 (line 364), CHANGE:
recent_closes = closes.tail(lookback)
recent_volumes = volumes.tail(lookback)
# TO:
rolling_closes = momentum_closes.tail(lookback)
rolling_volumes = momentum_volumes.tail(lookback)
```

### Part 3: Apply Same Fix to Rally Detection

Repeat the same changes in `_detect_realtime_rally()` method.

---

## 🧪 Testing Protocol

### Test 1: Historical Replay (Dec 17, 2025)

```bash
python3 test_selloff_detection_today.py
```

**Expected Output:**
- ✅ SPY selloff detected with -0.99% from open
- ✅ QQQ selloff detected with -1.64% from open
- Confidence: 70-80% (2 triggers: FROM_OPEN + MOMENTUM)

### Test 2: Live Monitoring

Deploy fix and monitor next trading day. Should detect:
- Any move >0.25% from day open
- Any 3+ consecutive bars in same direction
- Any 0.2% move in 10 bars

### Test 3: Backtest (30 days)

Run comprehensive backtest on Dec 1-17:
```bash
python3 backtest_selloff_signals.py --days 30
```

Expected: 10-15 selloff signals, 10-15 rally signals per month for SPY/QQQ combined.

---

## 📋 Action Items

- [ ] Fix `momentum_detector.py` (pass full day data)
- [ ] Fix `signal_generator.py` (separate momentum/rolling variables)
- [ ] Apply same fix to `_detect_realtime_rally()`  
- [ ] Test on Dec 17 data
- [ ] Deploy to production
- [ ] Monitor next trading day
- [ ] Run 30-day backtest
- [ ] Update `.cursorrules` with lesson learned

---

## 💡 Lessons Learned

1. **Always validate with REAL market data, not just unit tests**
2. **Be careful with `.tail()` - it changes the reference frame**
3. **Variable name collisions are dangerous - use unique names**
4. **Test edge cases: what if we join mid-day? Does day_open work?**

---

## 🎯 Impact

**Missed Opportunities Today:**
- SPY selloff: -$6.87 (-1.01%)
- QQQ selloff: -$9.89 (-1.61%)

If system had alerted at 9:40 AM (first signal), traders could have:
- Shorted SPY/QQQ
- Bought puts
- Hedged long positions
- **Potential profit: 1-2% on capital deployed**

**This is EXACTLY why we built this system!**

---

**STATUS: BUG IDENTIFIED, FIX IN PROGRESS** 🚨🔧

