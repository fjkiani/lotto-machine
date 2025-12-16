# 🔥 MANAGER ZO REVIEW - PLUMBER TASKS

**Review Date:** 2025-12-15  
**Reviewer:** Zo (Commander AI)  
**Status:** ✅ APPROVED WITH MODIFICATIONS

---

## ✅ TASK 1: Raise Signal Threshold

**Status:** ✅ APPROVED

**Feedback:**
- Good approach - test incrementally (55, 60, 65)
- **IMPORTANT:** After testing, pick the threshold that gives BEST win rate WITHOUT dropping trade count below 5 trades
- If threshold 65 gives only 2 trades → too restrictive, use 60
- **Log the trade count** - we need at least 5 trades for statistical significance

**Modified Table:**
| Threshold | Trades | Win Rate | Profit Factor | Avg R/R | **Decision** |
|-----------|--------|----------|---------------|---------|--------------|
| 50 (current) | 11 | 45.5% | 1.73 | 2.09 | Baseline |
| 55 | ? | ? | ? | ? | **Test this first** |
| 60 | ? | ? | ? | ? | |
| 65 | ? | ? | ? | ? | Only if 60 still <55% win rate |

---

## ✅ TASK 2: Add Regime Filter

**Status:** ✅ APPROVED WITH FIXES

**Issues Found:**
1. ❌ **BUG:** The `_detect_simple_regime()` function uses `period='5d'` which gets LAST 5 days, not 5 days BEFORE the test date
2. ❌ **BUG:** For historical dates, need to calculate 5 days BEFORE that date
3. ⚠️ **EDGE CASE:** What if `regime=None`? Should allow signal (backward compatible)

**CORRECTED CODE:**

```python
# In backtesting/simulation/squeeze_detector.py

def _detect_simple_regime(self, symbol: str, date: datetime) -> str:
    """Simple regime detection based on 5-day price change BEFORE test date"""
    import yfinance as yf
    from datetime import timedelta
    
    ticker = yf.Ticker(symbol)
    
    # Calculate date range: 5 days BEFORE test date
    end_date = date.date()
    start_date = end_date - timedelta(days=6)  # 6 days to get 5 days of data
    
    hist = ticker.history(start=start_date.strftime('%Y-%m-%d'), 
                         end=end_date.strftime('%Y-%m-%d'))
    
    if len(hist) < 2:
        return 'UNKNOWN'
    
    change = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]
    
    if change > 0.03:
        return 'STRONG_UPTREND'
    elif change > 0.01:
        return 'UPTREND'
    elif change < -0.03:
        return 'STRONG_DOWNTREND'
    elif change < -0.01:
        return 'DOWNTREND'
    else:
        return 'CHOPPY'
```

**In `squeeze_detector.py` - Make regime optional:**

```python
def analyze(self, symbol: str, current_price: Optional[float] = None, 
            date: Optional[datetime] = None, regime: Optional[str] = None) -> Optional[SqueezeSignal]:
    """
    ...existing docstring...
    """
    # ADD THIS AT THE START (after date_str calculation):
    # Filter out bearish regimes - squeezes need bullish environment
    # BUT: If regime is None, allow signal (backward compatible)
    if regime is not None and regime in ['DOWNTREND', 'STRONG_DOWNTREND']:
        logger.info(f"   ⏸️ {symbol}: Skipping - bearish regime ({regime})")
        return None
    
    # ... rest of existing code ...
```

---

## ✅ TASK 3: Widen Target (R/R Improvement)

**Status:** ✅ APPROVED

**Feedback:**
- Good idea BUT: Test this AFTER Task 1 & 2
- If win rate improves with threshold/regime, might not need wider targets
- **Test order:** Task 1 → Task 2 → Task 3 (only if still need improvement)

**Alternative:** Instead of fixed 2.5, make it **score-based**:
- Score 50-60: 2.0:1 R/R
- Score 60-70: 2.5:1 R/R  
- Score 70+: 3.0:1 R/R

This rewards higher confidence signals with better R/R.

---

## ⚠️ TASK 4: Add Momentum Filter

**Status:** ⚠️ APPROVED WITH CONCERNS

**Issues Found:**
1. ❌ **BUG:** `period='1d'` gets TODAY's data, not historical date
2. ❌ **BUG:** For backtesting, need to get data BEFORE the test date
3. ⚠️ **PERFORMANCE:** This adds yfinance call for EVERY signal check (slow)

**CORRECTED CODE:**

```python
# In squeeze_detector.py

def _check_momentum(self, symbol: str, date: Optional[datetime] = None) -> bool:
    """
    Check if price has positive momentum (5-bar lookback)
    Only take squeeze signals when momentum is positive
    
    Args:
        symbol: Stock ticker
        date: Historical date (if None, uses today)
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        
        if date:
            # For historical dates, get data up to that date
            # yfinance 1m data only available for last 7 days
            # So for historical dates, use daily data instead
            hist = ticker.history(
                start=(date - timedelta(days=2)).strftime('%Y-%m-%d'),
                end=date.strftime('%Y-%m-%d'),
                interval='1d'
            )
            if len(hist) < 2:
                return True  # Not enough data, allow signal
            recent_close = hist['Close'].iloc[-1]
            past_close = hist['Close'].iloc[0]
        else:
            # Current date - use 5m data
            data = ticker.history(period='1d', interval='5m')
            if len(data) < 6:
                return True  # Not enough data, allow signal
            recent_close = data['Close'].iloc[-1]
            past_close = data['Close'].iloc[-6]  # 30 min ago
        
        momentum = (recent_close - past_close) / past_close
        
        # Require at least 0.1% positive momentum
        return momentum > 0.001
    except Exception as e:
        logger.debug(f"Momentum check failed for {symbol}: {e}")
        return True  # On error, allow signal (fail-safe)
```

**Call It:**

```python
# In analyze() method, BEFORE returning signal (around line 200):
# Check momentum
if not self._check_momentum(symbol, date=date):
    logger.info(f"   ⏸️ {symbol}: Skipping - negative momentum")
    return None
```

**PERFORMANCE NOTE:** This adds latency. Consider caching momentum checks or making it optional.

---

## ✅ TASK 5: Test More Tickers

**Status:** ✅ APPROVED

**Feedback:**
- Good idea BUT: Only test if Tasks 1-4 are complete
- Don't waste API calls testing new tickers before tuning is done
- **Move this to AFTER Task 6** (final validation)

**Updated Priority:**
1. Task 1 (Threshold)
2. Task 2 (Regime)
3. Task 3 (R/R) - if needed
4. Task 4 (Momentum) - if needed
5. Task 6 (30-day backtest)
6. **Task 5 (More tickers)** - Final expansion

---

## ✅ TASK 6: Run 30-Day Backtest

**Status:** ✅ APPROVED

**Feedback:**
- This is the FINAL validation
- Must pass before production deployment
- **Requirement:** Win Rate >55% AND Profit Factor >1.8

---

## 🚨 CRITICAL ISSUES FOUND

### Issue 1: Task Order is Wrong

**Current Order:** 1 → 2 → 3 → 4 → 5 → 6

**CORRECT ORDER:**
1. **Task 1** (Threshold) - Test 55, 60, 65
2. **Task 2** (Regime) - Add filter
3. **Task 3** (R/R) - Only if still need improvement
4. **Task 4** (Momentum) - Only if still need improvement
5. **Task 6** (30-day) - Final validation
6. **Task 5** (More tickers) - Expansion after validation

### Issue 2: Missing Error Handling

**Add to all tasks:**
- What if yfinance fails?
- What if API rate limits?
- What if data is missing?

**Solution:** All filters should fail-safe (return True/allow signal on error)

### Issue 3: Missing Validation Steps

**Add after each task:**
```bash
# After Task 1:
python3 backtest_squeeze.py --symbols LCID GME RIVN --days 5
# Check: Did win rate improve? Did trade count stay reasonable?

# After Task 2:
python3 backtest_squeeze.py --symbols LCID GME RIVN --days 5
# Check: Are we filtering out bad trades? Win rate better?

# After Task 3:
python3 backtest_squeeze.py --symbols LCID GME RIVN --days 5
# Check: Profit factor improved?

# After Task 4:
python3 backtest_squeeze.py --symbols LCID GME RIVN --days 5
# Check: Final metrics before 30-day test
```

---

## 📋 REVISED TASK CHECKLIST

**Plumber must complete in this order:**

- [ ] **Task 1:** Test thresholds 55, 60, 65 → Pick best
- [ ] **Task 2:** Add regime filter (with FIXED code above)
- [ ] **Task 3:** Test R/R 2.5 (only if win rate still <55%)
- [ ] **Task 4:** Add momentum filter (with FIXED code above, only if still <55%)
- [ ] **Task 6:** Run 30-day backtest → Must pass
- [ ] **Task 5:** Test more tickers (expansion)

---

## ✅ APPROVAL CONDITIONS

**Plumber gets approval when:**

1. ✅ Win Rate > 55% (on 5-day backtest)
2. ✅ Profit Factor > 1.8 (on 5-day backtest)
3. ✅ Trade count >= 5 (statistical significance)
4. ✅ 30-day backtest passes (final validation)
5. ✅ All code changes documented
6. ✅ Tests pass: `python3 -m unittest tests.orchestrator.test_unified_monitor`

---

## 🔥 MANAGER ZO'S FINAL NOTES

**Plumber, listen up:**

1. **Test ONE thing at a time** - Don't combine tasks
2. **Use the FIXED code** - Don't use the original code snippets (they have bugs)
3. **Log EVERYTHING** - I need to see the progression
4. **Fail-safe is critical** - If filters break, allow signals (don't block everything)
5. **Performance matters** - Momentum filter adds latency, consider caching

**If you hit issues:**
- API rate limits → Wait 1 minute between backtests
- Missing data → Log it, don't crash
- Win rate drops below 40% → REVERT immediately

**Good luck. Don't fuck this up. 🔧💰**

---

**STATUS: APPROVED WITH MODIFICATIONS - USE REVISED CODE ABOVE**


