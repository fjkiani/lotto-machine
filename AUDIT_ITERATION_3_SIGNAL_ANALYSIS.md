# ITERATION 3: Signal Generation & Analysis Systems Map

**Date:** 2025-12-05  
**Status:** COMPLETE

---

## Signal Generation Systems (3 DIFFERENT IMPLEMENTATIONS!)

### 1. `live_monitoring/core/signal_generator.py` ⭐ PRIMARY
**Purpose:** Live signal generation for trading  
**Status:** ✅ WORKING (used by lotto machine)  
**Lines:** 1,253

**Input:**
- Institutional context (DP, short, options)
- Current price
- Minute bars (optional)

**Output:**
- `LiveSignal` objects
- `LotterySignal` objects (0DTE options)

**Signal Types:**
- SQUEEZE - Short interest + borrow fees + DP support
- GAMMA_RAMP - P/C ratio + max pain + dealer hedging
- BREAKOUT - Clean break above DP resistance
- BOUNCE - DP battleground support + reversal
- SELLOFF - Rapid decline + volume spike

**Features:**
- Multi-factor confirmation
- Narrative enrichment
- Price action filtering
- Risk/reward calculation
- Lottery mode (0DTE options)

**Used By:**
- `run_lotto_machine.py`
- `run_live_monitor.py`
- `run_production_monitor.py`

---

### 2. `core/rigorous_dp_signal_engine.py`
**Purpose:** DP-aware signal generation (standalone)  
**Status:** ✅ WORKING  
**Lines:** 508

**Input:**
- DP levels + price action
- Volume data
- Momentum data

**Output:**
- DP signals (bounce, break, rejection, testing)

**Key Features:**
- **NEVER acts on first touch** - waits for confirmation
- Regime-aware thresholds (CHOP vs TREND)
- Adaptive stops OUTSIDE battlefield zones
- Complete interaction audit trail

**Used By:**
- `core/core_signals_runner.py`
- Standalone analysis

---

### 3. `core/master_signal_generator.py`
**Purpose:** Master signal filtering (standalone)  
**Status:** ✅ WORKING  
**Lines:** 290

**Input:**
- Raw signals from any source

**Output:**
- Master signals (75%+ confidence)

**Scoring Factors:**
- DP Level Strength (35%)
- Volume Confirmation (25%)
- Momentum Strength (20%)
- Regime Score (10%)
- Magnet Interaction (10%)

**Used By:**
- Standalone filtering
- Not integrated with live monitoring

---

## Analysis Systems

### Live Monitoring Analysis

| Module | Purpose | Status | Lines |
|--------|---------|--------|-------|
| `signal_generator.py` | Multi-factor signals | ✅ | 1,253 |
| `gamma_exposure.py` | Gamma tracking | ✅ | 250 |
| `volatility_expansion.py` | Vol detection | ✅ | 200 |
| `zero_dte_strategy.py` | Lottery plays | ✅ | 300 |
| `volume_profile.py` | Timing optimization | ✅ | 350 |
| `stock_screener.py` | Ticker discovery | ✅ | 329 |
| `reddit_sentiment.py` | Sentiment filtering | ✅ | 384 |

### Streamlit Analysis

| Module | Purpose | Status | Lines |
|--------|---------|--------|-------|
| `options_analyzer.py` | Options analysis | ✅ | 600 |
| `technical_analyzer.py` | Technical analysis | ✅ | 500 |
| `enhanced_analyzer.py` | Enhanced analysis | ✅ | 400 |
| `memory_analyzer.py` | Memory-enhanced | ✅ | 300 |
| `general_analyzer.py` | General analysis | ✅ | 200 |

### Multi-Agent Analysis

| Agent | Purpose | Status | Lines |
|-------|---------|--------|-------|
| `warren_buffett.py` | Value analysis | ✅ | ~200 |
| `technicals.py` | Technical analysis | ✅ | ~200 |
| `options_analyst.py` | Options analysis | ✅ | ~300 |
| `sentiment.py` | Sentiment analysis | ✅ | ~200 |
| `portfolio_manager.py` | Synthesis | ✅ | ~300 |

---

## Overlaps & Differences

### Signal Generation Overlap

**All three systems:**
- Generate trading signals
- Use DP data
- Calculate confidence scores

**Differences:**
- `signal_generator.py`: Integrated with live monitoring, has narrative enrichment
- `rigorous_dp_signal_engine.py`: Standalone, regime-aware, never first touch
- `master_signal_generator.py`: Filter only, no generation

### Analysis Overlap

**Technical Analysis:**
- `live_monitoring/` - Real-time, momentum-based
- `src/analysis/technical_analyzer.py` - LLM-powered, historical
- `src/agents/technicals.py` - Agent-based, LangGraph

**Options Analysis:**
- `live_monitoring/core/gamma_exposure.py` - Gamma tracking
- `src/analysis/options_analyzer.py` - Full options analysis
- `src/agents/options_analyst.py` - Agent-based options

---

## Which Systems Are Actually Used?

### Active (Production):
1. ✅ `live_monitoring/core/signal_generator.py` - Used by lotto machine
2. ✅ `src/analysis/*` - Used by Streamlit app
3. ✅ `src/agents/*` - Used by multi-agent system

### Standalone (Not Integrated):
1. ⚠️ `core/rigorous_dp_signal_engine.py` - Works but not integrated
2. ⚠️ `core/master_signal_generator.py` - Works but not integrated

---

## Recommendations

1. **Consolidate signal generation** - Merge into single canonical system
2. **Integrate standalone systems** - Connect rigorous_dp and master_signal to live monitoring
3. **Create shared analysis library** - Reuse analysis logic across systems
4. **Document which system to use** - Clear guidance for developers

---

**Deliverable:** ✅ Signal/analysis system map with capabilities and usage

