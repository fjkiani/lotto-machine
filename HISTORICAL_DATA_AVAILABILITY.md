# 📊 Historical Data Availability & Extended Backtesting

**Date:** 2026-01-04  
**Purpose:** Understand data limits and how to backtest over months/years

---

## 🔍 DATA SOURCE LIMITATIONS

### **yfinance (Free Tier) - Price Data**

| Interval | Availability | Use Case |
|----------|-------------|----------|
| **1-minute** | Last **30 days** only | Intraday signals, precise entry/exit |
| **5-minute** | Last **60 days** only | Intraday signals, less precise |
| **15-minute** | Last **60 days** only | Intraday signals, less precise |
| **Daily (1d)** | **Years of history** | Long-term patterns, swing trading |

**Key Limitation:**
- ❌ Cannot get 1-minute data for dates >30 days ago
- ❌ Cannot get 5-minute data for dates >60 days ago
- ✅ Can get daily data going back years

---

## 📅 WHAT THIS MEANS FOR BACKTESTING

### **Short-Term Backtests (Last 30 Days)**
- ✅ **1-minute data available**
- ✅ **Most accurate** for intraday signals
- ✅ **Precise entry/exit timing**
- ✅ **Current backtest period** (Dec 29 - Jan 2) works perfectly

### **Medium-Term Backtests (30-60 Days)**
- ⚠️ **5-minute data only** (less precise)
- ⚠️ **Entry/exit timing less accurate**
- ⚠️ **Signals may be less reliable**
- ✅ **Still usable** for validation

### **Long-Term Backtests (60+ Days)**
- ❌ **Daily data only** (not suitable for intraday signals)
- ❌ **Cannot test intraday entry/exit**
- ✅ **Can test longer-term patterns**
- ✅ **Can validate overall strategy direction**

---

## 💾 STORED HISTORICAL DATA

### **Institutional Context Data (ChartExchange)**
**Location:** `data/historical/institutional_contexts/`

**Available Dates:**
- **SPY:** Sept 18 - Oct 17, 2025 (20 trading days)
- **QQQ:** Sept 18 - Oct 17, 2025 (20 trading days)
- **Also:** One file from Oct 17, 2024 (SPY)

**What's Stored:**
- Dark pool levels & prints
- Short interest & volume
- Options chain summaries
- Exchange volume breakdowns
- FTD data
- Borrow fees

**Usage:** Can be used for backtesting with stored institutional context

---

## 🎯 RECOMMENDED BACKTESTING APPROACHES

### **Option 1: Rolling 30-Day Windows** ✅ RECOMMENDED
**How it works:**
- Backtest last 30 days (1-minute data)
- Then backtest previous 30 days
- Continue rolling backward
- Aggregate results

**Pros:**
- ✅ Most accurate (1-minute data)
- ✅ Precise entry/exit timing
- ✅ Validates intraday signals

**Cons:**
- ⚠️ Requires multiple runs
- ⚠️ Cannot test single 90-day period

**Example:**
```bash
# Last 30 days
python3 -m backtesting.simulation.date_range_backtest --start 2025-12-05 --end 2026-01-04

# Previous 30 days
python3 -m backtesting.simulation.date_range_backtest --start 2025-11-05 --end 2025-12-04

# Continue...
```

### **Option 2: 60-Day Backtest (5-Minute Data)**
**How it works:**
- Backtest last 60 days using 5-minute data
- Less precise but still usable

**Pros:**
- ✅ Single run for 60 days
- ✅ Still intraday data (5-minute)

**Cons:**
- ⚠️ Less precise entry/exit timing
- ⚠️ May miss some signals

**Example:**
```bash
python3 -m backtesting.simulation.date_range_backtest --start 2025-11-05 --end 2026-01-04
```

### **Option 3: Daily Data for Long-Term Patterns**
**How it works:**
- Use daily data for 90+ day periods
- Test overall strategy direction
- Not suitable for intraday signals

**Pros:**
- ✅ Can test months/years of data
- ✅ Validates long-term patterns

**Cons:**
- ❌ Cannot test intraday entry/exit
- ❌ Signals less reliable
- ❌ Not suitable for current strategy (intraday)

**Example:**
```bash
# Would need to modify detector to use daily data
# Not recommended for intraday signals
```

### **Option 4: Use Stored Historical Data**
**How it works:**
- Use stored institutional contexts (Sept-Oct 2025)
- Fetch price data for those dates (if within 30 days)
- Run backtest with full institutional context

**Pros:**
- ✅ Full institutional context available
- ✅ Can test DP confluence, options flow, etc.

**Cons:**
- ⚠️ Limited to stored dates (Sept-Oct 2025)
- ⚠️ Price data may not be available if >30 days old

---

## 📊 PRACTICAL RECOMMENDATIONS

### **For Current Strategy (Intraday Signals):**

**Best Approach: Rolling 30-Day Windows**
1. Backtest last 30 days (most recent, most relevant)
2. If results good, backtest previous 30 days
3. Continue until you have 3-6 months of rolling windows
4. Aggregate results for statistical significance

**Why This Works:**
- ✅ Uses 1-minute data (most accurate)
- ✅ Tests recent market conditions (most relevant)
- ✅ Can aggregate multiple windows for larger sample
- ✅ Each window is statistically independent

### **For Validation:**

**Minimum Sample Size:**
- **30 trades** for basic validation
- **100+ trades** for statistical confidence
- **Multiple market regimes** (bull, bear, chop)

**Current Status:**
- ✅ Last 5 days: 46 trades (with filters: 23 trades)
- ⏳ Need: 30-60 more days for 100+ trades

---

## 🚀 IMPLEMENTATION PLAN

### **Phase 1: Last 30 Days (Current)**
```bash
# Already done - Dec 29 to Jan 2
# Results: 45.7% WR, +0.37% P&L (unfiltered)
# Results: 47.8% WR, +0.72% P&L (filtered)
```

### **Phase 2: Previous 30 Days**
```bash
# Nov 5 to Dec 4, 2025
python3 -m backtesting.simulation.date_range_backtest --start 2025-11-05 --end 2025-12-04 --only-profitable
```

### **Phase 3: Continue Rolling**
```bash
# Oct 6 to Nov 4, 2025 (5-minute data)
python3 -m backtesting.simulation.date_range_backtest --start 2025-10-06 --end 2025-11-04 --only-profitable
```

### **Phase 4: Aggregate Results**
- Combine all rolling windows
- Calculate overall win rate, P&L, Sharpe
- Validate edge across multiple periods

---

## 📈 EXPECTED TIMELINE

| Period | Days | Data Type | Trades Expected | Status |
|--------|------|-----------|-----------------|--------|
| **Dec 5 - Jan 4** | 30 | 1-minute | ~200-300 | ✅ Can run now |
| **Nov 5 - Dec 4** | 30 | 1-minute | ~200-300 | ✅ Can run now |
| **Oct 6 - Nov 4** | 30 | 5-minute | ~200-300 | ⚠️ Less precise |
| **Sept 6 - Oct 5** | 30 | 5-minute | ~200-300 | ⚠️ Less precise |
| **Total** | **120** | Mixed | **800-1200** | ✅ Statistical significance |

---

## ⚠️ IMPORTANT NOTES

1. **Data Freshness:**
   - yfinance data is free but has strict limits
   - 1-minute data only for last 30 days
   - For longer periods, need to use daily data (less accurate)

2. **Institutional Data:**
   - ChartExchange API has historical data
   - But we only stored Sept-Oct 2025
   - Could populate more historical data if needed

3. **Alternative Data Sources:**
   - **Alpaca API:** Free tier, 1-minute data for last 30 days
   - **Polygon.io:** Paid, but more historical data
   - **Alpha Vantage:** Free tier, limited
   - **IEX Cloud:** Paid, good historical data

4. **Best Practice:**
   - Use rolling 30-day windows for accuracy
   - Aggregate results for larger sample
   - Focus on recent data (most relevant to current market)

---

## 🎯 SUMMARY

**What We Can Do:**
- ✅ Backtest last 30 days with 1-minute data (most accurate)
- ✅ Backtest last 60 days with 5-minute data (less precise)
- ✅ Use stored institutional data (Sept-Oct 2025)
- ✅ Run rolling 30-day windows for months of coverage

**What We Cannot Do:**
- ❌ Get 1-minute data for dates >30 days ago
- ❌ Get 5-minute data for dates >60 days ago
- ❌ Run single 90-day backtest with intraday precision

**Recommendation:**
- **Use rolling 30-day windows** for best accuracy
- **Aggregate results** for statistical significance
- **Focus on recent data** (most relevant)

---

**STATUS: READY TO RUN EXTENDED BACKTESTS WITH ROLLING WINDOWS** 🚀📊

