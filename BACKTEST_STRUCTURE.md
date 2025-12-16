# 🎯 BACKTESTING FRAMEWORK STRUCTURE

## 📁 Complete File Organization

```
backtesting/
├── __init__.py                    # Main exports (all components)
│
├── config/                        # Configuration
│   ├── __init__.py
│   └── trading_params.py         # TradingParams dataclass
│
├── data/                          # Data Loading
│   ├── __init__.py
│   ├── loader.py                 # DP alerts loader
│   └── alerts_loader.py          # Production signals loader
│
├── simulation/                    # Trade Simulation
│   ├── __init__.py
│   ├── trade_simulator.py        # Base Trade simulator
│   ├── current_system.py         # Current system logic
│   ├── narrative_brain.py        # Narrative Brain logic
│   ├── squeeze_detector.py       # 🔥 Squeeze detector (NEW)
│   ├── direct_api_test.py        # Direct API testing
│   └── production_replay.py     # Production replay
│
├── analysis/                      # Performance Analysis
│   ├── __init__.py
│   ├── performance.py            # PerformanceAnalyzer
│   ├── signal_analyzer.py        # SignalAnalyzer
│   ├── diagnostics.py            # ProductionDiagnostics
│   ├── production_health.py      # HealthMonitor
│   └── data_checker.py           # DataAvailabilityChecker
│
├── reports/                       # Report Generation
│   ├── __init__.py
│   ├── generator.py              # Base ReportGenerator
│   ├── signal_report.py          # SignalReportGenerator
│   ├── diagnostic_report.py      # DiagnosticReportGenerator
│   ├── health_report.py          # HealthReportGenerator
│   └── squeeze_report.py         # 🔥 SqueezeReportGenerator (NEW)
│
└── monitoring/                    # Production Monitoring
    ├── __init__.py
    └── production_monitor.py     # ProductionMonitor
```

## 🚀 Main Backtest Scripts

```
Root Directory:
├── backtest_squeeze.py           # 🔥 Squeeze detector (MODULAR)
├── backtest_30d_validation.py    # 30-day validation
├── backtest_session.py           # Session replay
├── backtest_narrative_brain.py   # Narrative Brain
└── backtest_squeeze_detector_legacy.py  # Old monolithic (kept for reference)
```

## 📊 Component Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                    MAIN BACKTEST SCRIPT                      │
│              (backtest_squeeze.py, etc.)                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   SIMULATOR  │ │   ANALYZER   │ │   REPORTER   │
│              │ │              │ │              │
│ - Generate   │ │ - Calculate  │ │ - Format     │
│   signals    │ │   metrics    │ │   output     │
│ - Simulate   │ │ - Compare    │ │ - Save file  │
│   trades     │ │   systems    │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
        │               │               │
        └───────────────┼───────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│     DATA     │ │    CONFIG    │ │  MONITORING  │
│              │ │              │ │              │
│ - Load       │ │ - Trading    │ │ - Health     │
│   alerts     │ │   params     │ │   checks     │
│ - Fetch      │ │ - Thresholds │ │ - Diagnostics│
│   prices     │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
```

## 🔥 Squeeze Detector Integration

```
backtest_squeeze.py
    │
    ├──> SqueezeDetectorSimulator
    │       │
    │       ├──> SqueezeDetector (from live_monitoring)
    │       ├──> TradeSimulator (reused)
    │       └──> TradingParams (reused)
    │
    ├──> PerformanceAnalyzer (reused)
    │
    └──> SqueezeReportGenerator
            │
            └──> PerformanceMetrics (reused)
```

## ✅ Modularity Principles

1. **Separation of Concerns**
   - Simulation logic separate from analysis
   - Reporting separate from calculation
   - Data loading separate from processing

2. **Reusability**
   - `TradeSimulator` used by all systems
   - `PerformanceAnalyzer` shared across backtests
   - `TradingParams` configurable for all

3. **Extensibility**
   - Add new simulator: Create file in `simulation/`
   - Add new report: Create file in `reports/`
   - Add new metric: Extend `PerformanceAnalyzer`

4. **Consistency**
   - All simulators follow same pattern
   - All reports use same format
   - All scripts use same structure

## 🎯 Usage Pattern

```python
# 1. Initialize components
simulator = SomeSimulator(detector, params)
analyzer = PerformanceAnalyzer()
reporter = SomeReportGenerator()

# 2. Run simulation
trades = simulator.simulate(symbols, start_date, end_date)

# 3. Analyze
metrics = analyzer.analyze(trades)

# 4. Report
report = reporter.generate_report(metrics)
```

**THIS STRUCTURE SCALES TO INFINITY!** 🔥💰🚀
