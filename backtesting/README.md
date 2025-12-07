# 🎯 BACKTESTING FRAMEWORK

**Modular, reusable backtesting system for DP alerts**

---

## 📁 ARCHITECTURE

```
backtesting/
├── __init__.py              # Main exports
├── config/
│   └── trading_params.py    # Configurable parameters
├── data/
│   └── loader.py            # Load DP alerts from database
├── simulation/
│   ├── trade_simulator.py   # Simulate individual trades
│   ├── current_system.py    # Current system logic
│   └── narrative_brain.py   # Narrative Brain logic
├── analysis/
│   └── performance.py       # Calculate metrics
└── reports/
    └── generator.py          # Generate reports
```

---

## 🚀 QUICK START

### **Backtest a Single Session:**
```bash
python3 backtest_session.py --date 2025-12-05
```

### **Backtest with Custom Times:**
```bash
python3 backtest_session.py --date 2025-12-05 --start-time 09:30 --end-time 16:00
```

### **Backtest Date Range:**
```bash
python3 backtest_session.py --date-range 2025-12-01 2025-12-05
```

### **Custom Trading Parameters:**
```bash
python3 backtest_session.py --date 2025-12-05 --stop-loss 0.20 --take-profit 0.30
```

---

## 📊 USAGE EXAMPLES

### **Example 1: Thursday Session**
```bash
python3 backtest_session.py --date 2025-12-05
```

**Output:**
- Current system performance
- Narrative Brain performance
- Comparison metrics
- Trade-by-trade breakdown

### **Example 2: Custom Thresholds**
```bash
python3 backtest_session.py --date 2025-12-05 --narrative-threshold 65.0
```

**Tests Narrative Brain with 65% confluence threshold instead of 70%**

### **Example 3: Week-Long Backtest**
```bash
python3 backtest_session.py --date-range 2025-12-01 2025-12-05
```

**Tests across multiple days**

---

## 🔧 PROGRAMMATIC USAGE

```python
from backtesting import (
    DataLoader,
    TradeSimulator,
    CurrentSystemSimulator,
    NarrativeBrainSimulator,
    PerformanceAnalyzer,
    ReportGenerator,
    TradingParams
)

# Load data
loader = DataLoader()
alerts = loader.load_session("2025-12-05")

# Configure
params = TradingParams(
    stop_loss_pct=0.25,
    take_profit_pct=0.40,
    narrative_min_confluence=70.0
)

# Simulate
trade_sim = TradeSimulator(params)
current_sim = CurrentSystemSimulator(trade_sim, params)
narrative_sim = NarrativeBrainSimulator(trade_sim, params)

current_trades = current_sim.simulate(alerts)
narrative_trades = narrative_sim.simulate(alerts)

# Analyze
analyzer = PerformanceAnalyzer()
current_metrics = analyzer.analyze(current_trades)
narrative_metrics = analyzer.analyze(narrative_trades)

# Report
report = ReportGenerator.generate_report(
    date="2025-12-05",
    current_metrics=current_metrics,
    narrative_metrics=narrative_metrics,
    comparison=analyzer.compare(current_metrics, narrative_metrics)
)
print(report)
```

---

## ⚙️ CONFIGURATION

### **TradingParams**

All configurable parameters:

```python
TradingParams(
    stop_loss_pct=0.25,              # Stop loss %
    take_profit_pct=0.40,             # Take profit %
    position_size_pct=2.0,            # Position size %
    synthesis_interval_seconds=120,    # Synthesis frequency
    narrative_min_confluence=70.0,     # Min confluence to send
    narrative_min_alerts=3,            # Min alerts for confirmation
    narrative_critical_mass=5,        # Critical mass threshold
    narrative_exceptional_confluence=80.0  # Exceptional threshold
)
```

---

## 📊 OUTPUT METRICS

### **PerformanceMetrics includes:**
- `total_trades`: Number of trades executed
- `winning_trades`: Number of winning trades
- `losing_trades`: Number of losing trades
- `win_rate`: Win rate percentage
- `avg_pnl_per_trade`: Average P&L per trade
- `total_pnl`: Total P&L
- `avg_win`: Average winning trade size
- `avg_loss`: Average losing trade size
- `profit_factor`: Total wins / Total losses
- `max_drawdown`: Maximum drawdown
- `sharpe_ratio`: Risk-adjusted return
- `trades`: List of all trades

---

## 🎯 KEY FEATURES

### **✅ DRY (Don't Repeat Yourself)**
- Reusable components
- No hard-coding dates
- Configurable parameters

### **✅ Modular**
- Each component is independent
- Easy to extend
- Clean separation of concerns

### **✅ Flexible**
- Test any date or date range
- Custom trading parameters
- Custom thresholds

### **✅ Comprehensive**
- Full performance metrics
- Trade-by-trade breakdown
- Comparison analysis

---

## 🔄 EXTENDING THE FRAMEWORK

### **Add New System Simulator:**

1. Create new file: `backtesting/simulation/my_system.py`
2. Implement `simulate(alerts: List[DPAlert]) -> List[Trade]`
3. Use in main script:

```python
from backtesting.simulation.my_system import MySystemSimulator

my_sim = MySystemSimulator(trade_sim, params)
my_trades = my_sim.simulate(alerts)
```

### **Add New Metrics:**

1. Extend `PerformanceAnalyzer.analyze()`
2. Add to `PerformanceMetrics` dataclass
3. Update `ReportGenerator` to display

---

## 📝 NOTES

- Uses real historical data from `data/dp_learning.db`
- Simulates realistic trading with stops/targets
- Calculates confluence from alert data
- Supports any date with data in database

---

**Ready to backtest any session with one command!** 🚀

