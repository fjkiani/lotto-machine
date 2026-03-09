# 📊 30-DAY FULL PIPELINE BACKTEST RESULTS

**Date:** 2026-01-04  
**Period:** Dec 5, 2025 - Jan 4, 2026 (21 trading days)  
**Symbols:** SPY, QQQ  
**All Detectors:** ✅ Enabled (except options_flow - broken)

---

## 📊 OVERALL SUMMARY

| Metric | Value | Status |
|--------|-------|--------|
| **Total Signals** | 238 | ✅ |
| **Total Trades** | 238 | ✅ |
| **Win Rate** | 47.1% | ⚠️ Below 50% threshold |
| **Total P&L** | -1.48% | ❌ Unprofitable |
| **Avg Daily P&L** | -0.07% | ❌ |
| **Max Drawdown** | 2.90% | ✅ Within limits |
| **Sharpe Ratio** | -0.15 | ❌ Negative |
| **Profit Factor** | 0.62 | ❌ < 1.0 |

---

## 🔍 BY DETECTOR TYPE

| Detector | Signals | Trades | Win Rate | P&L | Status |
|----------|---------|--------|----------|-----|--------|
| **Selloff/Rally** | 238 | 238 | 47.1% | -1.48% | ⚠️ Only detector with signals |
| **Options Flow** | 0 | 0 | 0% | 0% | ❌ Disabled (broken) |
| **Gap** | 0 | 0 | 0% | 0% | ⚠️ No signals found |
| **Squeeze** | 0 | 0 | 0% | 0% | ⚠️ No signals found |
| **Gamma** | 0 | 0 | 0% | 0% | ⚠️ No signals found |
| **FTD** | 0 | 0 | 0% | 0% | ⚠️ No signals found |
| **Reddit** | 0 | 0 | 0% | 0% | ⚠️ No signals found |
| **Dark Pool** | 17 alerts | 0 | - | - | ℹ️ Alerts only (no trades) |

---

## ✅ VALIDATION

**Status:** ❌ **FAILED**

**Notes:**
- ✅ 238 trades (meets minimum)
- ❌ Win rate 47.1% < 50.0%
- ✅ Max DD 2.90% (within limits)
- ❌ Unprofitable: -1.48%

---

## 🔍 KEY FINDINGS

### **1. Only Selloff/Rally Generated Signals**
- All 238 trades came from selloff/rally detector
- Other detectors (squeeze, gamma, FTD, reddit) found 0 signals
- **This is expected** - they have higher thresholds and may not fire often

### **2. Performance Issues**
- **Win Rate:** 47.1% (below 50% threshold)
- **P&L:** -1.48% (unprofitable)
- **Profit Factor:** 0.62 (losing money)

### **3. Data Quality**
- ✅ Successfully used 5-minute data for dates >7 days ago
- ✅ Automatically switched from 1m to 5m based on date
- ✅ All 21 trading days processed

---

## 📈 COMPARISON TO FILTERED RESULTS

**From Previous Rolling Windows Backtest:**

| Metric | Original | Filtered | Improvement |
|--------|----------|---------|-------------|
| **Trades** | 522 | 183 | -65% (fewer trades) |
| **Win Rate** | 46.9% | 50.8% | +3.9% ✅ |
| **P&L** | -2.59% | +3.44% | +6.03% ✅ |
| **Profit Factor** | 0.91 | 1.36 | +0.45 ✅ |

**Key Insight:** Filters (SELLOFF only, SHORT only, Afternoon only) dramatically improve performance!

---

## 🎯 RECOMMENDATIONS

### **1. Apply Filters**
- ✅ SELLOFF signals only (not RALLY)
- ✅ SHORT trades only (not LONG)
- ✅ Afternoon only (12-16 ET)
- **Expected:** Win rate → 50%+, P&L → positive

### **2. Investigate Other Detectors**
- Why didn't squeeze/gamma/FTD/reddit fire?
- Are thresholds too high?
- Do they need different market conditions?

### **3. Tune Selloff/Rally**
- Current: 47.1% WR, -1.48% P&L
- With filters: 50.8% WR, +3.44% P&L
- **Action:** Deploy filters to production

---

## 📝 NEXT STEPS

1. **Run filtered backtest** (SELLOFF/SHORT/Afternoon only)
2. **Analyze why other detectors didn't fire**
3. **Deploy filters to production** if results improve
4. **Paper trade** with filters enabled

---

**STATUS: Full pipeline tested, but only selloff/rally generated signals. Filters needed for profitability.** 🎯

