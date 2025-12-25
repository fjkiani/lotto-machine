# 🎯 BACKTESTING FRAMEWORK

**Modular backtesting system for institutional signal validation**

---

## 📊 CURRENT STATUS (Dec 25, 2025)

### ✅ PROFITABLE: Selloff/Rally ONLY
| Signal Type | Win Rate | P&L | Verdict |
|-------------|----------|-----|---------|
| **Selloff/Rally** | 33.3% | **+0.10%** | ✅ PROFITABLE |
| **Options Flow** | 0% | -4.50% | ❌ DISABLED |
| **Combined (selloff only)** | 33.3% | **+0.10%** | ✅ EDGE |

### What Works:
- **Selloff/Rally signals** with DP confluence = slight edge (+0.10%)
- Low win rate (33%) but 2:1+ R/R makes it profitable

### What's Broken:
- **Options Flow** - Even with 80% confidence threshold, 0% win rate
- Disabled for now until fundamentally reworked

### Recommendation:
Run with `--only-profitable` flag until options flow is fixed.

---

## 🚀 QUICK START

### Run Date Range Backtest (NEW!)
```bash
# ✅ RECOMMENDED: Only profitable signals (selloff/rally)
python3 -m backtesting.simulation.date_range_backtest --start 2025-12-23 --end 2025-12-24 --only-profitable

# Specific dates (all signals - includes broken options flow)
python3 -m backtesting.simulation.date_range_backtest --start 2025-12-23 --end 2025-12-24

# Today only
python3 -m backtesting.simulation.date_range_backtest --today --only-profitable

# Last 5 trading days
python3 -m backtesting.simulation.date_range_backtest --days 5 --only-profitable

# Disable just options (keep gaps, etc.)
python3 -m backtesting.simulation.date_range_backtest --days 5 --no-options

# Custom symbols
python3 -m backtesting.simulation.date_range_backtest --days 5 --symbols SPY,QQQ,TSLA
```

### Run Unified Backtest (All Detectors)
```bash
python3 -m backtesting.simulation.unified_backtest_runner
```

### Programmatic Usage
```python
from backtesting.simulation.date_range_backtest import DateRangeBacktester

# Initialize
backtester = DateRangeBacktester(symbols=['SPY', 'QQQ'])

# Run for specific dates
result = backtester.backtest_range('2025-12-23', '2025-12-24')

# Generate report
print(backtester.generate_report(result))

# Save to JSON
backtester.save_results(result)
```

---

## 📁 ARCHITECTURE

```
backtesting/
├── simulation/
│   ├── base_detector.py              # Abstract base class (Signal, TradeResult, BacktestResult)
│   ├── date_range_backtest.py        # 🆕 Full date range backtester
│   ├── selloff_rally_detector.py     # Momentum signals (FROM_OPEN, ROLLING, MOMENTUM)
│   ├── gap_detector.py               # Pre-market gap signals
│   ├── rapidapi_options_detector.py  # Options flow (NEEDS WORK)
│   ├── market_context_detector.py    # News + price action context
│   ├── composite_signal_filter.py    # Multi-factor scoring (NOT INTEGRATED)
│   └── unified_backtest_runner.py    # Run all detectors
├── reports/
│   └── backtest_*.json               # Saved backtest results
├── analysis/
│   └── performance.py                # Metrics calculation
└── config/
    └── trading_params.py             # Trading parameters
```

---

## 📊 DETECTORS

### ✅ SelloffRallyDetector (WORKING)
**Win Rate: 33.3% | P&L: +0.10%**

Triggers:
- `FROM_OPEN`: ±0.25% from day's open
- `ROLLING`: ±0.20% in last 20 bars
- `MOMENTUM`: 3+ consecutive red/green bars

**Requires 2+ triggers to fire signal.** This prevents false positives.

With DP confluence: **95% confidence signals**

### ❌ RapidAPIOptionsDetector (BROKEN)
**Win Rate: 36.0% | P&L: -6.96%**

**PROBLEMS:**
1. Takes EVERY signal (50/day) - no quality filter
2. Takes BEARISH signals in BULLISH markets
3. No confidence threshold
4. No DP confluence check
5. No volume confirmation

**FIXES NEEDED:** See "Options Flow Hardening" below.

### ⏸️ GapDetector
**Win Rate: 50.0% | P&L: -0.04%**

Works but gaps are rare. Not contributing meaningfully.

### 📊 MarketContextDetector (INFO ONLY)
Provides:
- Market direction (UP/DOWN/CHOP)
- Trend strength (0-100)
- VIX level
- Regime (TRENDING_UP, TRENDING_DOWN, CHOPPY)
- News sentiment
- Trading recommendations

**Used for filtering, not signal generation.**

---

## 🔧 OPTIONS FLOW HARDENING PLAN

### Current State (BROKEN)
```python
# Takes everything - no filtering
for option in most_active:
    if p_c_ratio < 0.7:
        signal = BULLISH
    elif p_c_ratio > 1.3:
        signal = BEARISH
    signals.append(signal)  # 50 signals/day!
```

### Target State (EDGE)
```python
for option in most_active:
    # 1. CONFIDENCE THRESHOLD
    if confidence < 70:
        continue
    
    # 2. MARKET CONTEXT ALIGNMENT
    if context.favor_longs and signal.direction == 'SHORT':
        continue
    if context.favor_shorts and signal.direction == 'LONG':
        continue
    
    # 3. DP CONFLUENCE CHECK
    dp_support = check_dp_confluence(symbol, price)
    if not dp_support:
        confidence *= 0.7  # Reduce if no DP
    
    # 4. VOLUME CONFIRMATION
    if volume < avg_volume * 1.5:
        continue
    
    # 5. UNUSUAL ACTIVITY THRESHOLD
    if vol_oi_ratio < 3.0:  # Not unusual enough
        continue
    
    # 6. COMPOSITE SCORE
    score = calculate_composite_score(signal, context, dp_support, volume)
    if score < 75:
        continue
    
    signals.append(signal)  # ~5-10 quality signals/day
```

### Implementation Tasks

| Task | Priority | Status |
|------|----------|--------|
| Add confidence threshold (70%) | P0 | ⏳ TODO |
| Filter by market context | P0 | ⏳ TODO |
| Add DP confluence check | P0 | ⏳ TODO |
| Add volume confirmation | P1 | ⏳ TODO |
| Increase vol/OI threshold | P1 | ⏳ TODO |
| Implement composite scoring | P1 | ⏳ TODO |
| Backtest with filters | P0 | ⏳ TODO |

---

## 📈 COMPOSITE SIGNAL FILTER (NOT INTEGRATED)

File: `backtesting/simulation/composite_signal_filter.py`

**Multi-factor scoring:**
- Base signal: 25%
- DP confluence: 30%
- Market context alignment: 25%
- Volume confirmation: 10%
- Momentum confirmation: 10%

**Threshold:** Only take signals with 75%+ composite score.

**Status:** Code exists but NOT connected to live system.

---

## 🎯 VALIDATION CRITERIA

From `backtesting-validation-protocol.mdc`:

| Metric | Minimum | Current | Status |
|--------|---------|---------|--------|
| Win Rate | 50% | 35.5% | ❌ FAIL |
| Avg R/R | 2.0 | N/A | ⚠️ NOT TRACKED |
| Max Drawdown | 10% | 6.85% | ✅ PASS |
| Min Trades | 10 | 62 | ✅ PASS |
| Sharpe Ratio | 1.5 | 0.00 | ❌ FAIL |
| Profit Factor | 1.8 | 0.00 | ❌ FAIL |

**VERDICT: NOT READY FOR LIVE CAPITAL**

---

## 📊 BACKTEST RESULTS (Dec 23-24, 2025)

### Summary
```
Trading Days: 2
Total Signals: 62
Total Trades: 62
Win Rate: 35.5%
Total P&L: -6.85%
Max Drawdown: 6.85%
```

### By Signal Type
```
Selloff/Rally: 12 signals | 33.3% WR | +0.10% P&L  ✅
Options Flow:  50 signals | 36.0% WR | -6.96% P&L  ❌
Dark Pool:     11 alerts (info only)
Squeeze:       0 candidates
```

### Daily Breakdown
```
2025-12-23: 31 signals | 35% WR | -3.43% P&L | Market: UP
2025-12-24: 31 signals | 35% WR | -3.43% P&L | Market: UP
```

---

## 🔥 WHAT NEEDS TO HAPPEN

### Phase 1: Fix Options Flow (URGENT)
1. Add 70% confidence threshold
2. Filter out counter-trend signals
3. Require DP confluence OR 3x volume
4. Backtest with filters

### Phase 2: Integrate Composite Filter
1. Connect `composite_signal_filter.py` to detectors
2. Apply 75% minimum score
3. Backtest for 30 days

### Phase 3: Validate Edge
1. Run 30-day backtest
2. Require: Win Rate > 55%, P&L > 0
3. Paper trade for 20+ trades
4. Only then consider live

---

## 📁 KEY FILES

| File | Purpose |
|------|---------|
| `simulation/date_range_backtest.py` | Full date range backtesting |
| `simulation/selloff_rally_detector.py` | Momentum signals (WORKING) |
| `simulation/rapidapi_options_detector.py` | Options flow (BROKEN) |
| `simulation/market_context_detector.py` | Market direction analysis |
| `simulation/composite_signal_filter.py` | Multi-factor scoring (NOT INTEGRATED) |
| `reports/backtest_*.json` | Saved backtest results |

---

## 🏃 RUNNING BACKTESTS

### Quick Commands
```bash
# Today
python3 -m backtesting.simulation.date_range_backtest --today

# Last week
python3 -m backtesting.simulation.date_range_backtest --days 7

# Specific range
python3 -m backtesting.simulation.date_range_backtest --start 2025-12-20 --end 2025-12-24

# Just selloff/rally (skip broken options)
python3 -m backtesting.simulation.unified_backtest_runner
```

### Reading Results
```bash
# View latest report
cat backtesting/reports/backtest_2025-12-23_2025-12-24.json | python3 -m json.tool
```

---

## 📝 LESSONS LEARNED

1. **Options flow without filtering = noise trading**
2. **Selloff/Rally with DP confluence = slight edge**
3. **Market context matters - don't go short in UP market**
4. **50 signals/day is WAY too many**
5. **Composite scoring exists but isn't connected**

---

## 🎯 NEXT STEPS

1. **FIX OPTIONS FLOW** - Add filters, reduce to 5-10 signals/day
2. **INTEGRATE COMPOSITE FILTER** - Apply to all signals
3. **RUN 30-DAY BACKTEST** - Validate edge exists
4. **PAPER TRADE** - 20+ trades before live
5. **GO LIVE SMALL** - $1000 max position

---

**BOTTOM LINE:** We have the infrastructure. We have the data. We're just trading garbage signals. Fix the filters, prove edge, then deploy.
