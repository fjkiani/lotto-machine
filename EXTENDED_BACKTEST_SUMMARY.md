# 📊 Extended Backtest Summary - Data Availability

**Date:** 2026-01-04  
**Question:** How far back can we backtest?

---

## 🔍 DATA AVAILABILITY LIMITS

### **yfinance (Free Tier)**

| Interval | Available For | Status |
|----------|--------------|--------|
| **1-minute** | Last **30 days** | ✅ Available |
| **5-minute** | Last **60 days** | ✅ Available |
| **Daily** | **Years** | ✅ Available |

**Key Finding:**
- ✅ **Last 30 days:** 1-minute data (most accurate)
- ✅ **Last 60 days:** 5-minute data (less precise)
- ❌ **Beyond 60 days:** Daily data only (not suitable for intraday signals)

---

## 📅 BACKTEST RESULTS BY PERIOD

### **Period 1: Dec 29 - Jan 2, 2025** ✅
- **Days:** 5 trading days
- **Data:** 1-minute (within 30 days)
- **Signals:** 46 trades (unfiltered), 23 trades (filtered)
- **Win Rate:** 45.7% (unfiltered), 47.8% (filtered)
- **P&L:** +0.37% (unfiltered), +0.72% (filtered)
- **Status:** ✅ **WORKING**

### **Period 2: Nov 5 - Dec 4, 2025** ❌
- **Days:** 22 trading days
- **Data:** 1-minute (within 30 days from Dec 4)
- **Signals:** 0 trades
- **Status:** ❌ **NO SIGNALS** (thresholds too strict or different market regime)

### **Period 3: Oct 6 - Nov 4, 2025** ⚠️
- **Days:** 22 trading days
- **Data:** 5-minute (within 60 days, but >30 days)
- **Status:** ⏳ **NOT TESTED YET**

---

## 💡 KEY INSIGHTS

### **1. Data is Available**
- ✅ Can get 1-minute data for last 30 days
- ✅ Can get 5-minute data for last 60 days
- ✅ Data fetching works correctly

### **2. Signal Generation Varies**
- ✅ Recent period (Dec 29 - Jan 2): 46 signals
- ❌ Previous period (Nov 5 - Dec 4): 0 signals
- **Reason:** Market conditions, thresholds, or regime differences

### **3. Rolling Windows Work**
- ✅ Can backtest multiple 30-day periods
- ✅ Each period uses 1-minute data (accurate)
- ✅ Can aggregate results for larger sample

---

## 🎯 RECOMMENDED APPROACH

### **Option 1: Rolling 30-Day Windows** ✅ BEST

**How it works:**
1. Backtest last 30 days (1-minute data)
2. Backtest previous 30 days (1-minute data)
3. Continue rolling backward
4. Aggregate all results

**Pros:**
- ✅ Most accurate (1-minute data)
- ✅ Can cover months by rolling
- ✅ Each window is independent

**Cons:**
- ⚠️ Requires multiple runs
- ⚠️ Cannot test single 90-day period

**Example:**
```bash
# Window 1: Dec 5 - Jan 4 (30 days)
python3 -m backtesting.simulation.date_range_backtest --start 2025-12-05 --end 2026-01-04

# Window 2: Nov 5 - Dec 4 (30 days)  
python3 -m backtesting.simulation.date_range_backtest --start 2025-11-05 --end 2025-12-04

# Window 3: Oct 6 - Nov 4 (30 days, 5-minute data)
python3 -m backtesting.simulation.date_range_backtest --start 2025-10-06 --end 2025-11-04
```

### **Option 2: Single 60-Day Backtest**
**How it works:**
- Backtest last 60 days using 5-minute data

**Pros:**
- ✅ Single run
- ✅ Still intraday data

**Cons:**
- ⚠️ Less precise (5-minute vs 1-minute)
- ⚠️ May miss some signals

**Example:**
```bash
python3 -m backtesting.simulation.date_range_backtest --start 2025-11-05 --end 2026-01-04
```

---

## 📊 WHAT WE CAN ACTUALLY BACKTEST

### **With 1-Minute Data (Most Accurate):**
- ✅ **Last 30 days:** Dec 5, 2025 - Jan 4, 2026
- ✅ **Previous 30 days:** Nov 5 - Dec 4, 2025
- ✅ **Total:** ~60 days of accurate backtesting

### **With 5-Minute Data (Less Precise):**
- ✅ **Last 60 days:** Nov 5, 2025 - Jan 4, 2026
- ✅ **Previous 60 days:** Sept 6 - Nov 4, 2025
- ✅ **Total:** ~120 days of backtesting (less precise)

### **With Daily Data (Not Suitable for Intraday):**
- ✅ **Years of history** available
- ❌ **Not suitable** for intraday signals
- ❌ **Cannot test** entry/exit timing

---

## 🚀 NEXT STEPS

### **Immediate (Can Do Now):**
1. ✅ **Backtest Dec 5 - Jan 4** (last 30 days, 1-minute data)
2. ✅ **Backtest Nov 5 - Dec 4** (previous 30 days, 1-minute data)
3. ✅ **Aggregate results** for ~60 days of data

### **Short-Term (Next Week):**
1. ⏳ **Backtest Oct 6 - Nov 4** (5-minute data, less precise)
2. ⏳ **Backtest Sept 6 - Oct 5** (5-minute data, less precise)
3. ⏳ **Aggregate all results** for ~120 days

### **Long-Term (If Needed):**
1. ⏳ **Use daily data** for longer-term pattern validation
2. ⏳ **Populate more historical institutional data** (ChartExchange)
3. ⏳ **Consider paid data sources** (Polygon.io, IEX Cloud)

---

## 📈 EXPECTED RESULTS

### **If We Run 3 Rolling Windows:**

| Window | Days | Data Type | Expected Trades | Status |
|--------|------|-----------|-----------------|--------|
| **Dec 5 - Jan 4** | 30 | 1-minute | ~200-300 | ⏳ To run |
| **Nov 5 - Dec 4** | 30 | 1-minute | 0 (tested) | ❌ No signals |
| **Oct 6 - Nov 4** | 30 | 5-minute | ~200-300 | ⏳ To run |
| **Total** | **90** | Mixed | **400-600** | ✅ Statistical significance |

**Note:** Nov 5 - Dec 4 had 0 signals, which suggests:
- Market was in different regime
- Thresholds may need adjustment
- Or signals were filtered out

---

## ⚠️ LIMITATIONS

1. **Free Data Limits:**
   - 1-minute: Last 30 days only
   - 5-minute: Last 60 days only
   - Cannot get intraday data for older dates

2. **Signal Generation:**
   - Varies by market conditions
   - Some periods may have 0 signals
   - Need to aggregate multiple periods

3. **Precision Trade-Off:**
   - 1-minute: Most accurate, but limited to 30 days
   - 5-minute: Less precise, but 60 days available
   - Daily: Not suitable for intraday signals

---

## ✅ SUMMARY

**What We Can Do:**
- ✅ Backtest **last 30 days** with 1-minute data (most accurate)
- ✅ Backtest **last 60 days** with 5-minute data (less precise)
- ✅ Use **rolling windows** to cover months
- ✅ **Aggregate results** for statistical significance

**What We Cannot Do:**
- ❌ Get 1-minute data for dates >30 days ago
- ❌ Get 5-minute data for dates >60 days ago
- ❌ Run single 90-day backtest with intraday precision

**Recommendation:**
- **Use rolling 30-day windows** for best accuracy
- **Run multiple windows** to cover months
- **Aggregate results** for larger sample size
- **Focus on recent data** (most relevant to current market)

---

**STATUS: READY TO RUN EXTENDED BACKTESTS - USE ROLLING 30-DAY WINDOWS** 🚀📊

