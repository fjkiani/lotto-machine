# 🚀 MODULAR MIGRATION GUIDE

## ✅ What We Built

**Before:** 1691-line monolith (`run_all_monitors.py`)  
**After:** Modular pipeline with testable components

## 📁 New Structure

```
live_monitoring/pipeline/
├── config.py                    # ALL configuration (no more hardcoded values!)
├── orchestrator.py              # Main coordinator
│
├── components/                  # Individual capabilities
│   ├── dp_fetcher.py           # DP data fetching (configurable threshold!)
│   ├── synthesis_engine.py     # Signal synthesis logic
│   └── alert_manager.py        # Alert routing & formatting
│
└── tests/                      # Component tests
    ├── test_dp_fetcher.py
    ├── test_synthesis.py
    └── test_integration.py
```

## 🎯 Key Improvements

### 1. **Centralized Configuration**
**Before:** Volume threshold hardcoded as `500000` in multiple places  
**After:** `PipelineConfig.dp.min_volume = 100_000` (one place!)

```python
from live_monitoring.pipeline import PipelineConfig

config = PipelineConfig()
config.dp.min_volume = 50_000  # Easy to adjust!
config.synthesis.min_confluence = 0.40  # Easy to tune!
```

### 2. **Testable Components**
**Before:** Can't test DP fetching without running entire system  
**After:** Each component independently testable

```python
from live_monitoring.pipeline.components import DPFetcher

fetcher = DPFetcher(api_key="...", min_volume=100_000)
levels = fetcher.fetch_levels('SPY')  # Test in isolation!
```

### 3. **Clear Separation of Concerns**
- **DPFetcher**: Only fetches DP data
- **SynthesisEngine**: Only synthesizes signals
- **AlertManager**: Only formats & sends alerts
- **Orchestrator**: Only coordinates timing

### 4. **Easy to Debug**
**Before:** "Why isn't DP loading?" → Search 1691 lines  
**After:** Check `dp_fetcher.py` → See exact logic → Fix threshold

## 🚀 Usage

### Run New Modular Pipeline
```bash
python3 run_pipeline.py
```

### Adjust Configuration
Edit `run_pipeline.py`:
```python
config = PipelineConfig()
config.dp.min_volume = 50_000  # Lower threshold
config.synthesis.min_confluence = 0.40  # Lower confluence
```

### Run Tests
```bash
python3 -m pytest live_monitoring/pipeline/tests/
```

## 🔄 Migration Strategy

**Phase 1:** ✅ Created modular structure  
**Phase 2:** ⏳ Test new pipeline alongside old one  
**Phase 3:** ⏳ Gradually migrate features  
**Phase 4:** ⏳ Deprecate old `run_all_monitors.py`

## 📊 Configuration Reference

### DP Configuration
```python
config.dp.min_volume = 100_000      # Minimum volume threshold
config.dp.interval = 60             # Check every 60 seconds
config.dp.debounce_minutes = 30     # Don't alert same level within 30 min
config.dp.symbols = ['SPY', 'QQQ']  # Symbols to monitor
```

### Synthesis Configuration
```python
config.synthesis.min_confluence = 0.50  # Minimum 50% to send
config.synthesis.unified_mode = True    # Suppress individual alerts
config.synthesis.cross_asset_weight = 1.0
config.synthesis.macro_weight = 0.6
config.synthesis.dp_weight = 0.6
config.synthesis.timing_weight = 0.4
```

### Monitoring Intervals
```python
config.intervals.fed_watch = 300    # 5 minutes
config.intervals.trump_intel = 180 # 3 minutes
config.intervals.economic = 3600   # 1 hour
config.intervals.dark_pool = 60    # 1 minute
```

## 🧪 Testing

Each component has tests:
- `test_dp_fetcher.py` - Tests volume filtering, error handling
- `test_synthesis.py` - Tests confluence calculation, thresholds
- `test_integration.py` - Tests full pipeline flow

## 🐛 Debugging

**Problem:** "No DP levels loading"  
**Solution:** Check `dp_fetcher.py` → See `min_volume` → Adjust in config

**Problem:** "No alerts being sent"  
**Solution:** Check `synthesis_engine.py` → See `min_confluence` → Adjust in config

**Problem:** "Volume threshold too high"  
**Solution:** Change `config.dp.min_volume` → ONE place, not scattered!

## ✅ Benefits

1. ✅ **Testable** - Each component independently testable
2. ✅ **Configurable** - All thresholds in one place
3. ✅ **Debuggable** - Clear separation of concerns
4. ✅ **Scalable** - Easy to add new components
5. ✅ **Maintainable** - Small, focused files


