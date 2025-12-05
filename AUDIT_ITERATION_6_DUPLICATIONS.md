# ITERATION 6: Duplications & Overlaps Report

**Date:** 2025-12-05  
**Status:** COMPLETE

---

## Signal Generation Duplication

### THREE SEPARATE IMPLEMENTATIONS

#### 1. `live_monitoring/core/signal_generator.py` (1,253 lines)
**Status:** ✅ PRIMARY (used by lotto machine)  
**Features:**
- Multi-factor signals (squeeze, gamma, breakout, bounce, selloff)
- Narrative enrichment
- Price action filtering
- Lottery mode (0DTE options)
- Risk/reward calculation

#### 2. `core/rigorous_dp_signal_engine.py` (508 lines)
**Status:** ⚠️ STANDALONE (not integrated)  
**Features:**
- DP-aware signals
- Never acts on first touch
- Regime-aware thresholds
- Adaptive stops

#### 3. `core/master_signal_generator.py` (290 lines)
**Status:** ⚠️ STANDALONE (filter only)  
**Features:**
- 0-1 scoring system
- Weighted factors
- Master signal filtering (75%+)

**Recommendation:** Merge into single canonical system

---

## Data Fetching Duplication

### FIVE DIFFERENT APPROACHES

#### 1. `live_monitoring/core/data_fetcher.py` (240 lines)
**Status:** ✅ PRIMARY (unified fetcher with caching)  
**Used By:** Live monitoring system

#### 2. `core/data/ultimate_chartexchange_client.py` (464 lines)
**Status:** ✅ ACTIVE (ChartExchange client)  
**Used By:** Data fetcher, core systems

#### 3. `src/data/connectors/yahoo_finance.py` (500+ lines)
**Status:** ✅ ACTIVE (RapidAPI wrapper)  
**Used By:** Streamlit app

#### 4. `core/data/real_yahoo_finance_api.py` (unknown lines)
**Status:** ⚠️ ORPHANED (direct scraper)  
**Used By:** None

#### 5. Direct `yfinance` calls (scattered)
**Status:** ⚠️ INCONSISTENT  
**Used By:** Multiple systems (direct calls)

**Recommendation:** Standardize on unified data layer

---

## Analysis Duplication

### Technical Analysis (3 implementations)

1. **`live_monitoring/core/`** - Real-time, momentum-based
2. **`src/analysis/technical_analyzer.py`** - LLM-powered, historical
3. **`src/agents/technicals.py`** - Agent-based, LangGraph

### Options Analysis (3 implementations)

1. **`live_monitoring/core/gamma_exposure.py`** - Gamma tracking
2. **`src/analysis/options_analyzer.py`** - Full options analysis
3. **`src/agents/options_analyst.py`** - Agent-based options

### Signal Generation (3 implementations)

1. **`live_monitoring/core/signal_generator.py`** - Multi-factor
2. **`core/rigorous_dp_signal_engine.py`** - DP-aware
3. **`core/master_signal_generator.py`** - Filter only

---

## Dead/Unused Code

### Orphaned Files

1. **`core/data/alpha_vantage_client.py`** - Not used
2. **`src/data/connectors/alpha_vantage.py`** - Not used
3. **`core/data/real_data_scraper*.py`** - Replaced by ChartExchange
4. **`core/data/real_yahoo_finance_api.py`** - Replaced by yfinance
5. **Multiple Streamlit apps** - Only 1 confirmed active

### Unused Imports

- Scattered throughout codebase
- Need cleanup

---

## Canonical Implementations

### Signal Generation
**Canonical:** `live_monitoring/core/signal_generator.py`  
**Reason:** Integrated with live monitoring, most features

### Data Fetching
**Canonical:** `live_monitoring/core/data_fetcher.py`  
**Reason:** Unified with caching, used by primary system

### Analysis
**Canonical:** `src/analysis/*` (for Streamlit)  
**Reason:** Most complete, LLM-powered

---

## Consolidation Priority

### High Priority:
1. **Signal Generation** - Merge 3 implementations
2. **Data Fetching** - Standardize on unified layer
3. **Yahoo Finance** - Single implementation

### Medium Priority:
1. **Analysis Modules** - Create shared library
2. **Remove Orphaned Code** - Clean up unused files

### Low Priority:
1. **Streamlit Apps** - Deprecate unused variants
2. **Import Cleanup** - Remove unused imports

---

## Recommendations

1. **Merge signal generators** - Single canonical system
2. **Create unified data layer** - One access point
3. **Create shared analysis library** - Reuse across systems
4. **Remove orphaned code** - Clean up unused files
5. **Document canonical implementations** - Clear guidance

---

**Deliverable:** ✅ Duplication report with recommendations

