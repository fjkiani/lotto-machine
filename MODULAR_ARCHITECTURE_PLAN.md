# 🏗️ MODULAR ARCHITECTURE PLAN - Alpha Intelligence Pipeline

## 🎯 Goal
Break down `run_all_monitors.py` (1691 lines) into modular, testable components.

## 📊 Current Problems
1. **1691 lines in one file** - Impossible to debug
2. **Hardcoded thresholds** - Volume 500k scattered everywhere
3. **Mixed responsibilities** - DP fetching + synthesis + alerts all mixed
4. **No tests** - Can't verify components work
5. **Configuration scattered** - Thresholds, intervals hardcoded

## 🏗️ New Architecture

```
live_monitoring/pipeline/
├── __init__.py
├── orchestrator.py          # Main coordinator (replaces UnifiedAlphaMonitor)
├── config.py                # ALL configuration centralized
│
├── components/              # Individual capabilities
│   ├── __init__.py
│   ├── dp_fetcher.py       # DP data fetching (configurable thresholds)
│   ├── dp_monitor.py        # DP level monitoring & alerts
│   ├── synthesis_engine.py # Signal synthesis logic
│   ├── alert_manager.py     # Alert routing & formatting
│   ├── fed_monitor.py       # Fed Watch monitoring
│   ├── trump_monitor.py     # Trump intelligence
│   ├── economic_monitor.py  # Economic calendar
│   └── narrative_brain.py   # Narrative brain integration
│
└── tests/                   # Component tests
    ├── __init__.py
    ├── test_dp_fetcher.py
    ├── test_synthesis.py
    └── test_integration.py
```

## 🔧 Component Responsibilities

### 1. `config.py` - Centralized Configuration
```python
@dataclass
class PipelineConfig:
    # DP Configuration
    dp_min_volume: int = 100_000  # Configurable threshold!
    dp_interval: int = 60  # seconds
    dp_debounce_minutes: int = 30
    
    # Synthesis Configuration
    min_confluence: float = 0.50  # 50% minimum
    unified_mode: bool = True
    
    # Monitoring Intervals
    fed_interval: int = 300
    trump_interval: int = 180
    econ_interval: int = 3600
    
    # Symbols
    symbols: List[str] = field(default_factory=lambda: ['SPY', 'QQQ'])
```

### 2. `components/dp_fetcher.py` - DP Data Fetching
**Responsibility:** Fetch DP levels with configurable thresholds
- Takes config (min_volume)
- Returns standardized level format
- Handles errors gracefully
- Testable independently

### 3. `components/synthesis_engine.py` - Signal Synthesis
**Responsibility:** Combine all signals into one analysis
- Takes DP levels, macro context, etc.
- Returns synthesis result
- No hardcoded thresholds
- Testable with mock data

### 4. `components/alert_manager.py` - Alert Routing
**Responsibility:** Format and send alerts
- Takes synthesis result
- Formats for Discord
- Routes to channels
- Testable independently

### 5. `orchestrator.py` - Main Coordinator
**Responsibility:** Orchestrate all components
- Initializes components
- Runs monitoring loops
- Coordinates timing
- Handles errors

## ✅ Benefits

1. **Testable** - Each component can be tested independently
2. **Configurable** - All thresholds in one place
3. **Debuggable** - Clear separation of concerns
4. **Scalable** - Easy to add new components
5. **Maintainable** - Small, focused files

## 🚀 Migration Strategy

1. **Phase 1:** Create structure + config
2. **Phase 2:** Extract DP fetcher (most critical)
3. **Phase 3:** Extract synthesis engine
4. **Phase 4:** Extract alert manager
5. **Phase 5:** Refactor orchestrator
6. **Phase 6:** Add tests
7. **Phase 7:** Update run_all_monitors.py to use new structure

## 🧪 Testing Strategy

Each component gets:
- Unit tests (mock dependencies)
- Integration tests (real dependencies)
- Performance tests (timing, memory)


