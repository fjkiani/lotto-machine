# 🔍 PRODUCTION DIAGNOSTICS SYSTEM

**Built into the backtesting framework to diagnose production issues**

---

## 🚀 QUICK START

### **Diagnose Today:**
```bash
python3 diagnose_production.py
```

### **Diagnose Specific Date:**
```bash
python3 diagnose_production.py --date 2025-12-11
```

### **Diagnose Date Range:**
```bash
python3 diagnose_production.py --date-range 2025-12-10 2025-12-11
```

---

## 📊 WHAT IT DIAGNOSES

### **1. Signal Timing Analysis**
- RTH signals (9:30 AM - 4:00 PM) vs Non-RTH
- Identifies if signals only fire outside market hours
- Peak hour detection

### **2. Data Availability**
- **DP Data**: Checks API and database
- **Price Data**: Verifies yfinance connectivity
- **Fed Data**: Checks if Fed alerts fired
- **Economic Data**: Checks economic calendar
- **Market Hours**: Verifies if date is a trading day

### **3. Threshold Analysis**
- Synthesis signal count (RTH vs non-RTH)
- Narrative Brain count
- DP alert count
- Average confluence scores

### **4. Market Conditions**
- Signals per hour during RTH
- Peak activity hours
- Signal distribution by hour

### **5. Issue Identification**
- No RTH signals
- Data availability problems
- Unified mode failures
- Threshold issues
- Signal quality problems

### **6. Actionable Recommendations**
- Specific fixes for identified issues
- Data source troubleshooting
- Threshold adjustments
- Configuration fixes

---

## 📋 EXAMPLE OUTPUT

```
================================================================================
🔍 PRODUCTION DIAGNOSTICS: 2025-12-11
================================================================================

📊 SIGNAL SUMMARY:
--------------------------------------------------------------------------------
  RTH Signals (9:30 AM - 4:00 PM): 0
  Non-RTH Signals: 105
  Total Signals: 105

  ⚠️  CRITICAL: NO SIGNALS DURING MARKET HOURS!

📡 DATA AVAILABILITY:
--------------------------------------------------------------------------------
  ✅ Dp Data: Available
  ✅ Price Data: Available
  ❌ Fed Data: NOT AVAILABLE
  ✅ Market Hours: Available

  📊 API Check Details:
    DP Levels: 0 found (CHARTEXCHANGE_API_KEY not set)
    DP Prints: 0 found (CHARTEXCHANGE_API_KEY not set)
    Price Data: 1 bars
    Market Day: True (Thursday)

🚨 IDENTIFIED ISSUES:
--------------------------------------------------------------------------------
  ❌ NO SIGNALS DURING RTH (9:30 AM - 4:00 PM)
  ⚠️  105 signals fired OUTSIDE market hours
     → System running but not generating RTH signals
  ⚠️  Thresholds may be too high for RTH conditions

💡 RECOMMENDATIONS:
--------------------------------------------------------------------------------
  🔧 CHECK DATA SOURCES:
     1. Verify DP API is returning data for current date
     2. Check API rate limits haven't been hit
     3. Verify market hours detection is working
     4. Check if DP levels exist for SPY/QQQ today
  🔧 LOWER THRESHOLDS:
     1. Reduce synthesis confluence threshold (currently 60%+)
     2. Reduce narrative brain threshold (currently 70%+)
```

---

## 🔧 ARCHITECTURE

### **Components:**

1. **`ProductionDiagnostics`** (`backtesting/analysis/diagnostics.py`)
   - Main diagnostic engine
   - Analyzes signals, data, thresholds
   - Identifies issues
   - Generates recommendations

2. **`DataAvailabilityChecker`** (`backtesting/analysis/data_checker.py`)
   - Checks actual API availability
   - Tests DP API, price data, market hours
   - Returns detailed error messages

3. **`DiagnosticReportGenerator`** (`backtesting/reports/diagnostic_report.py`)
   - Formats diagnostic results
   - Generates comprehensive reports
   - Saves to `backtesting/reports/`

4. **`diagnose_production.py`**
   - Command-line interface
   - Flexible date/range selection

---

## 🎯 USE CASES

### **1. Daily Production Check**
```bash
# Run after market close to diagnose the day
python3 diagnose_production.py
```

### **2. Troubleshooting No Signals**
```bash
# Why didn't signals fire today?
python3 diagnose_production.py --date 2025-12-11
```

### **3. Historical Analysis**
```bash
# Compare multiple days
python3 diagnose_production.py --date-range 2025-12-10 2025-12-11
```

### **4. Data Source Verification**
The diagnostic automatically checks:
- DP API connectivity
- Price data availability
- Market hours detection
- API key configuration

---

## ✅ BENEFITS

### **✅ Integrated into Framework**
- Uses same architecture patterns
- Extends backtesting capabilities
- Reusable components

### **✅ Production-Ready**
- Handles real production data
- Robust error handling
- Actionable recommendations

### **✅ Comprehensive**
- Checks all data sources
- Analyzes thresholds
- Identifies root causes

### **✅ Actionable**
- Specific recommendations
- Clear issue identification
- Fix guidance

---

## 🔍 DEC 11 DIAGNOSIS RESULTS

**Root Cause Found:**
- ✅ System WAS running
- ✅ Market day detected correctly (Thursday)
- ✅ Price data available
- ❌ **DP API key not set** (CHARTEXCHANGE_API_KEY missing)
- ❌ **No RTH signals** (0 during 9:30-4:00 PM)
- ⚠️ **105 signals fired AFTER market close** (8:00-11:00 PM)

**Why signals fired after hours:**
- System was running but using **stale/cached DP data** from Dec 10
- No fresh DP data during RTH (API key issue)
- Thresholds may be too high for actual market conditions

**Fix:**
1. Set `CHARTEXCHANGE_API_KEY` environment variable
2. Verify API returns data for current date
3. Check if data is T+1 delayed (use yesterday's date)
4. Lower thresholds if market conditions don't meet current criteria

---

## 📁 FILES

- `backtesting/analysis/diagnostics.py` - Main diagnostic engine
- `backtesting/analysis/data_checker.py` - API availability checker
- `backtesting/reports/diagnostic_report.py` - Report generator
- `diagnose_production.py` - CLI tool
- `backtesting/reports/diagnostic_*.txt` - Generated reports

---

**Now you can diagnose ANY production issue with one command!** 🚀


