# ITERATION 1: Entry Points & Systems Inventory

**Date:** 2025-12-05  
**Status:** COMPLETE

---

## Entry Points Catalog

### Run Scripts (5 files)

| File | Purpose | Status | Dependencies | Lines |
|------|---------|--------|--------------|-------|
| `run_lotto_machine.py` | **MAIN** - Unified market exploitation system | ✅ WORKING | `live_monitoring/`, `core/` | 516 |
| `run_live_monitor.py` | Basic live monitoring (legacy) | ✅ WORKING | `live_monitoring/` | 91 |
| `run_live_paper_trading.py` | Paper trading system with Alpaca | ✅ WORKING | `live_monitoring/`, Alpaca SDK | 219 |
| `run_production_monitor.py` | Production monitoring with Discord alerts | ✅ WORKING | `live_monitoring/`, Discord webhook | 334 |
| `run_combined_strategies.py` | Institutional + Technical combo analysis | ✅ WORKING | `core/`, `live_monitoring/` | 223 |

### Main Entry Points (1 file)

| File | Purpose | Status | Dependencies | Lines |
|------|---------|--------|--------------|-------|
| `src/main.py` | Multi-agent hedge fund (LangGraph) | ✅ WORKING | `src/agents/`, LangGraph | 282 |

### Core Systems (2 files)

| File | Purpose | Status | Dependencies | Lines |
|------|---------|--------|--------------|-------|
| `core/core_signals_runner.py` | Core signals system (minimal, DP-aware) | ✅ WORKING | `core/data/`, `core/filters/` | 534 |
| `core/ultimate_spy_intelligence.py` | Ultimate intelligence synthesis | ✅ WORKING | `core/` | 410 |

### Streamlit Apps (5 files)

| File | Purpose | Status | Dependencies | Lines |
|------|---------|--------|--------------|-------|
| `demos/streamlit_app_llm.py` | **MAIN** - LLM-powered analysis UI | ✅ WORKING | `src/analysis/`, `src/streamlit_app/` | 1090 |
| `demos/streamlit_app_llm_insights.py` | Insights variant | ⚠️ UNKNOWN | Unknown | Unknown |
| `demos/streamlit_app_memory.py` | Memory-enhanced variant | ⚠️ UNKNOWN | Unknown | Unknown |
| `demos/streamlit_app_simple.py` | Simple variant | ⚠️ UNKNOWN | Unknown | Unknown |
| `demos/streamlit_app.py` | Original variant | ⚠️ UNKNOWN | Unknown | Unknown |

---

## System Architecture

### System 1: Live Monitoring System
**Entry Point:** `run_lotto_machine.py`  
**Purpose:** Real-time signal generation + trading  
**Status:** ✅ Production-ready

**Components:**
- `live_monitoring/core/signal_generator.py` - Signal generation
- `live_monitoring/core/data_fetcher.py` - Data acquisition
- `live_monitoring/core/risk_manager.py` - Risk management
- `live_monitoring/alerting/` - Multi-channel alerts
- `live_monitoring/trading/paper_trader.py` - Paper trading

**Dependencies:**
- ChartExchange API (Tier 3)
- yfinance (price data)
- Alpaca API (trading)

### System 2: Multi-Agent System
**Entry Point:** `src/main.py`  
**Purpose:** LLM-powered analysis with agent workflow  
**Status:** ✅ Working

**Components:**
- `src/agents/warren_buffett.py` - Value analysis
- `src/agents/technicals.py` - Technical analysis
- `src/agents/options_analyst.py` - Options analysis
- `src/agents/portfolio_manager.py` - Synthesis
- LangGraph workflow orchestration

**Dependencies:**
- LangGraph
- LLM APIs (OpenAI, Anthropic, etc.)
- No direct data fetching (uses state)

### System 3: Streamlit Analysis UI
**Entry Point:** `demos/streamlit_app_llm.py`  
**Purpose:** Interactive market analysis  
**Status:** ✅ Working

**Components:**
- `src/analysis/options_analyzer.py` - Options analysis
- `src/analysis/technical_analyzer.py` - Technical analysis
- `src/analysis/enhanced_analyzer.py` - Enhanced analysis
- `src/streamlit_app/ui_components.py` - Display components (1880 lines!)

**Dependencies:**
- Streamlit
- `src/data/connectors/` - Data connectors
- LLM APIs (Gemini, etc.)

---

## Key Findings

1. **THREE SEPARATE SYSTEMS** - No integration between them
2. **Multiple entry points** - 8 different ways to run the system
3. **Streamlit apps** - 5 variants, only 1 confirmed working
4. **Core systems** - 2 standalone systems (core_signals_runner, ultimate_intelligence)

---

## Recommendations

1. **Consolidate entry points** - Choose primary system (recommend: `run_lotto_machine.py`)
2. **Deprecate unused apps** - Remove or document status of unknown Streamlit apps
3. **Document system separation** - Explain why systems are separate
4. **Create integration layer** - Connect systems if needed

---

**Deliverable:** ✅ System inventory with entry points, dependencies, and actual capabilities

