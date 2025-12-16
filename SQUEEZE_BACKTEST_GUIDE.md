# 🔥 SQUEEZE DETECTOR BACKTEST GUIDE

## Overview

The `backtest_squeeze_detector.py` script validates the squeeze detector on historical data to prove edge before risking capital.

---

## 🚀 Quick Start

```bash
# Basic backtest (30 days, SPY/QQQ)
python3 backtest_squeeze_detector.py

# Custom date range and symbols
python3 backtest_squeeze_detector.py --days 60 --symbols SPY QQQ GME AMC

# Test specific squeeze candidates
python3 backtest_squeeze_detector.py --days 90 --symbols GME AMC BBBY
```

---

## 📊 What It Does

1. **For each trading day in range:**
   - Fetches historical short interest, borrow fee, FTD data
   - Fetches historical DP levels/prints
   - Runs squeeze detector (as if it was that date)
   - If signal generated (score > 70), simulates trade using intraday prices

2. **Trade Simulation:**
   - Entry: Market open (9:30 AM ET) or first available bar
   - Exit: Stop hit, target hit, or end of day (4:00 PM ET)
   - Uses actual intraday price data (1-minute bars)

3. **Performance Metrics:**
   - Win rate, avg R/R, profit factor
   - Max drawdown, Sharpe ratio
   - Squeeze-specific metrics (avg score, SI%, borrow fee)
   - Performance by score range (70-74, 75-79, 80-100)

---

## ✅ Success Criteria

The backtest **PASSES** if ALL criteria are met:

| Criteria | Threshold | Why |
|----------|-----------|-----|
| **Win Rate** | >55% | More winners than losers |
| **Avg R/R** | >2.0 | Risk/reward is profitable |
| **Max Drawdown** | <10% | Manageable risk |
| **Sharpe Ratio** | >1.5 | Risk-adjusted returns |
| **Profit Factor** | >1.8 | Wins > losses |
| **Min Trades** | 10+ | Statistical significance |

---

## 📈 Example Output

```
======================================================================
🔥 SQUEEZE DETECTOR BACKTEST RESULTS
======================================================================

📊 OVERALL PERFORMANCE
----------------------------------------------------------------------
   Total Trades:     15
   Winning Trades:   9 (60.0%)
   Losing Trades:    6
   Total P&L:        $1,234.56 (12.35%)

📈 RISK METRICS
----------------------------------------------------------------------
   Avg Win:          8.5%
   Avg Loss:         -3.2%
   Avg R/R:          2.65:1
   Profit Factor:    2.12
   Max Drawdown:     $456.78 (4.57%)
   Sharpe Ratio:     1.87

🔥 SQUEEZE METRICS
----------------------------------------------------------------------
   Avg Squeeze Score: 75.3/100
   Avg SI%:           22.4%
   Avg Borrow Fee:    45.2%

📊 PERFORMANCE BY SCORE RANGE
----------------------------------------------------------------------
   70-74: 5 trades, 40.0% win rate
   75-79: 7 trades, 71.4% win rate
   80-100: 3 trades, 100.0% win rate

✅ VALIDATION CRITERIA
----------------------------------------------------------------------
   ✅ PASS: Win Rate >55%
   ✅ PASS: Avg R/R >2.0
   ✅ PASS: Max DD <10%
   ✅ PASS: Sharpe >1.5
   ✅ PASS: Profit Factor >1.8
   ✅ PASS: Min 10 Trades

   RESULT: 6/6 criteria passed
   🎉 BACKTEST PASSED - READY FOR PAPER TRADING!
======================================================================
```

---

## ⚠️ Current Limitations

### 1. **Historical Data Availability**

**Issue:** The squeeze detector currently uses **current data** as a proxy for historical data.

**Why:** ChartExchange API methods accept `date` parameters, but the `SqueezeDetector.analyze()` method doesn't currently accept a date parameter.

**Impact:** 
- Backtest uses current SI/borrow/FTD data for all historical dates
- This is **not ideal** but demonstrates the framework
- For accurate backtesting, we need to modify `SqueezeDetector` to accept date parameter

**Fix Needed:**
```python
# Modify SqueezeDetector.analyze() to accept date:
def analyze(self, symbol: str, current_price: Optional[float] = None, 
            date: Optional[datetime] = None) -> Optional[SqueezeSignal]:
    # Pass date to all API calls:
    short_data = self.client.get_short_interest(symbol, date=date)
    borrow_data = self.client.get_borrow_fee(symbol, date=date)
    # etc...
```

### 2. **SPY/QQQ Won't Generate Signals**

**Why:** SPY and QQQ are highly liquid ETFs with:
- Low SI% (~10%)
- Zero borrow fee (easy to short)
- No FTD spikes
- Score ~26/100 (below 70 threshold)

**Solution:** Test with actual squeeze candidates:
- **Meme stocks:** GME, AMC, BBBY
- **High SI stocks:** Use screener to find >20% SI
- **Hard-to-borrow:** Stocks with >50% borrow fee

### 3. **Intraday Data Availability**

**Issue:** yfinance intraday data may not be available for all dates.

**Impact:** Some trades may be skipped if intraday data unavailable.

**Workaround:** Falls back to daily data (less accurate).

---

## 🔧 How to Improve

### 1. **Add Date Parameter to SqueezeDetector**

Modify `live_monitoring/exploitation/squeeze_detector.py`:

```python
def analyze(self, symbol: str, current_price: Optional[float] = None,
            date: Optional[datetime] = None) -> Optional[SqueezeSignal]:
    """Analyze with optional historical date"""
    date_str = date.strftime('%Y-%m-%d') if date else None
    
    short_data = self._fetch_short_interest(symbol, date=date_str)
    borrow_data = self._fetch_borrow_fee(symbol, date=date_str)
    # etc...
```

### 2. **Use Historical Data Pipeline**

If we have historical data saved:
- Load from `data/historical/` directory
- Use saved short interest, borrow fee, FTD snapshots
- More accurate than API calls

### 3. **Test Known Squeeze Events**

Backtest on historical squeeze dates:
- **GME Jan 2021:** Score should be 90+ before squeeze
- **AMC June 2021:** High SI + borrow fee
- **BBBY Aug 2022:** FTD spike + high SI

---

## 📋 Next Steps

1. **Run backtest on squeeze candidates:**
   ```bash
   python3 backtest_squeeze_detector.py --days 90 --symbols GME AMC
   ```

2. **If backtest passes:**
   - ✅ Ready for paper trading
   - Monitor live signals during RTH
   - Track performance vs backtest

3. **If backtest fails:**
   - ⚠️ Tune thresholds (lower score requirement?)
   - ⚠️ Adjust scoring weights
   - ⚠️ Add more filters (regime, volume, etc.)

4. **Enhance backtest:**
   - Add date parameter support
   - Use historical data pipeline
   - Test on known squeeze events

---

## 🎯 Expected Results

**For SPY/QQQ:**
- ❌ No signals (correct - not squeeze candidates)
- Score ~20-30/100 (below threshold)

**For GME/AMC (during squeeze periods):**
- ✅ Multiple signals
- Score 75-90/100
- High win rate if timed correctly

**For High SI Stocks:**
- ✅ Signals when SI >20%, borrow fee >30%
- Score 70-85/100
- Validate edge exists

---

## 📄 Report Output

Backtest saves report to: `backtest_squeeze_YYYYMMDD.txt`

Includes:
- All performance metrics
- Pass/fail validation
- Recommendations

---

**THE BACKTEST FRAMEWORK IS READY - NOW WE NEED TO TEST ON ACTUAL SQUEEZE CANDIDATES!** 🔥💰


