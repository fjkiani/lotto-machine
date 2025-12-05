# 🎯 LOTTO MACHINE - QUICK REFERENCE GUIDE

**For:** Alpha (Commander)  
**Purpose:** Quick lookup of all commands, files, and status  
**Last Updated:** 2025-11-23  

---

## 📁 PROJECT STRUCTURE

```
ai-hedge-fund-main/
├── agents/                          ← NEW: Agentic architecture
│   ├── contracts.py                 ← Data contracts (ALL agents use this)
│   ├── base_agent.py                ← Base class with error handling
│   ├── data_providers/              ← Layer 1: Data fetching
│   │   ├── market_data_agent.py
│   │   ├── institutional_flow_agent.py
│   │   ├── macro_event_agent.py
│   │   ├── sentiment_agent.py
│   │   └── cross_asset_agent.py
│   ├── context/                     ← Layer 2: Aggregation
│   │   └── context_builder_agent.py
│   ├── analysis/                    ← Layer 3: Intelligence
│   │   ├── liquidity_agent.py
│   │   ├── dp_filter_agent.py
│   │   ├── signal_agent.py
│   │   ├── narrative_agent.py
│   │   └── validation_agent.py
│   ├── decision/                    ← Layer 4: Synthesis
│   │   └── synthesis_agent.py
│   └── orchestrator/                ← Layer 5: Coordination
│       └── lotto_orchestrator.py
│
├── core/                            ← EXISTING: Core logic (will be wrapped by agents)
│   ├── ultra_institutional_engine.py
│   ├── master_signal_generator.py
│   ├── data/
│   │   ├── alpha_vantage_client.py
│   │   ├── ultimate_chartexchange_client.py
│   │   └── historical_data_pipeline.py
│   ├── filters/
│   │   └── dp_aware_signal_filter.py
│   └── detectors/
│       └── dp_magnet_tracker.py
│
├── live_monitoring/                 ← EXISTING: Live system (signal_generator.py is KEY)
│   ├── core/
│   │   ├── signal_generator.py      ← PRIMARY SIGNAL ENGINE (1,254 lines)
│   │   ├── data_fetcher.py
│   │   ├── reddit_sentiment.py
│   │   ├── gamma_exposure.py
│   │   ├── volume_profile.py
│   │   └── stock_screener.py
│   ├── enrichment/
│   │   ├── market_narrative_pipeline.py
│   │   └── institutional_narrative.py
│   └── trading/
│       └── paper_trader.py
│
├── .cursor/rules/                   ← PLANNING DOCS
│   ├── feedback.mdc                 ← MASTER DATA + AGENT GUIDELINES (1,301 lines)
│   ├── AGENT_DEPLOYMENT_PLAN.mdc    ← IMPLEMENTATION ROADMAP
│   ├── review-iteration-1.mdc       ← CODEBASE AUDIT
│   └── charexchange.mdc             ← API REFERENCE
│
├── START_HERE.md                    ← YOU ARE HERE (start point for agents)
├── QUICK_REFERENCE.md               ← THIS FILE
└── PROGRESS.md                      ← TRACK IMPLEMENTATION STATUS
```

---

## 🚀 COMMANDS CHEAT SHEET

### **Setup (Run Once)**
```bash
# Navigate to project
cd /Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main

# Create folder structure
mkdir -p agents/{data_providers,context,analysis,decision,orchestrator,scripts}
mkdir -p tests/agents/{data_providers,context,analysis,orchestrator}

# Initialize Python packages
touch agents/__init__.py
touch agents/data_providers/__init__.py
touch agents/context/__init__.py
touch agents/analysis/__init__.py
touch agents/decision/__init__.py
touch agents/orchestrator/__init__.py
touch tests/__init__.py
touch tests/agents/__init__.py

# Create data contracts (already done if you ran START_HERE.md)
# See START_HERE.md Step 3
```

### **Development**
```bash
# Run tests
pytest tests/ -v

# Run specific agent test
pytest tests/agents/test_market_data_agent.py -v

# Run with coverage
pytest tests/ --cov=agents --cov-report=html

# Lint code
flake8 agents/
black agents/

# Type check
mypy agents/
```

### **Running the System**
```bash
# Once orchestrator is built:

# Run lotto machine for SPY
python -m agents.orchestrator.lotto_orchestrator --symbol SPY

# Get narrative only
python -m agents.analysis.narrative_agent --symbol SPY

# Check DP status
python -m agents.analysis.dp_filter_agent --symbol SPY

# Replay historical day
python agents/scripts/replay_day.py --symbol SPY --date 2025-11-20
```

---

## 📋 AGENT TASK STATUS

### **Phase 1: Modularization (Week 1-2)**
- [ ] **TASK 1:** Market Data Agent (2-3 hrs)
- [ ] **TASK 2:** Institutional Flow Agent (3-4 hrs)
- [ ] **TASK 3:** Context Builder Agent (2-3 hrs)
- [ ] **TASK 4:** Liquidity Agent (4-5 hrs)
- [ ] **TASK 5:** Signal Agent Refactor (3-4 hrs)

### **Phase 2: Orchestration (Week 2-3)**
- [ ] **TASK 6:** Orchestrator (5-6 hrs)

### **Phase 3: User Interface (Week 3-4)**
- [ ] CLI commands
- [ ] Discord bot
- [ ] Web UI

### **Phase 4: Testing (Week 4-5)**
- [ ] Backtest validation
- [ ] Historical replay
- [ ] Edge verification

---

## 🎯 KEY FILES TO REVIEW

### **Planning & Architecture**
1. `.cursor/rules/feedback.mdc` (lines 813-1301) - Agent guidelines & contracts
2. `.cursor/rules/AGENT_DEPLOYMENT_PLAN.mdc` - Complete roadmap
3. `START_HERE.md` - Agent task assignments
4. `agents/contracts.py` - All data structures

### **Existing Code (To Wrap/Refactor)**
1. `live_monitoring/core/signal_generator.py` - MAIN SIGNAL LOGIC (refactor to Signal Agent)
2. `core/ultra_institutional_engine.py` - Context builder logic
3. `core/data/ultimate_chartexchange_client.py` - API calls for DP/options/short data
4. `core/data/alpha_vantage_client.py` - Intraday price data
5. `core/filters/dp_aware_signal_filter.py` - DP filter logic

### **New Files (Agents Will Create)**
1. `agents/data_providers/market_data_agent.py`
2. `agents/data_providers/institutional_flow_agent.py`
3. `agents/context/context_builder_agent.py`
4. `agents/analysis/liquidity_agent.py`
5. `agents/analysis/signal_agent.py`
6. `agents/orchestrator/lotto_orchestrator.py`

---

## 📊 DATA FLOW (High-Level)

```
USER: /lotto SPY
    ↓
ORCHESTRATOR (lotto_orchestrator.py)
    ↓
├─→ LAYER 1: Data Providers (parallel)
│   ├─→ Market Data Agent → MarketDataOutput
│   ├─→ Institutional Flow Agent → InstitutionalFlowOutput
│   ├─→ Macro Event Agent → MacroEventOutput
│   ├─→ Sentiment Agent → SentimentOutput
│   └─→ Cross-Asset Agent → CrossAssetOutput
│
├─→ LAYER 2: Context Builder (sequential)
│   └─→ Context Builder Agent → InstitutionalContext
│
├─→ LAYER 3: Analysis (parallel)
│   ├─→ Liquidity Agent → LiquidityRegimeOutput
│   ├─→ DP Filter Agent → DPStructureOutput
│   ├─→ Signal Agent → SignalOutput
│   ├─→ Narrative Agent → NarrativeOutput
│   └─→ Validation Agent → ValidationOutput
│
├─→ LAYER 4: Decision Synthesis (sequential)
│   └─→ Synthesis Agent → TradeRecommendation
│
└─→ LAYER 5: UI Display
    └─→ "BUY SPY @ $660.50, Stop $658.00, Target $665.00, Confidence 87%"

TOTAL TIME: 15-25 seconds
```

---

## 🔑 CRITICAL CONCEPTS

### **Data Contracts (agents/contracts.py)**
- **ALL agents use standardized dataclasses**
- Output includes: data + status + errors + warnings
- Enables graceful degradation (if agent fails, system continues)

### **Agent Message Protocol**
```python
@dataclass
class AgentMessage:
    agent_id: str              # "market_data_agent"
    status: str                # "SUCCESS", "FAILED", "DEGRADED"
    output: Any                # Agent-specific output
    errors: List[str]          # Error messages
    warnings: List[str]        # Warning messages
    execution_time_ms: int     # Performance tracking
    timestamp: datetime        # When executed
```

### **Async Execution**
- **Parallel:** Layer 1 (data) and Layer 3 (analysis) run in parallel using `asyncio.gather()`
- **Sequential:** Layer 2 (context) and Layer 4 (synthesis) run one at a time
- **Total latency:** <25 seconds target

### **Error Handling**
- **Graceful Degradation:** If Market Data Agent fails, try ChartExchange bars
- **Data Completeness:** Track % of data successfully fetched
- **Confidence Scaling:** Lower confidence if data incomplete
- **Never Crash:** System should always return SOMETHING (even if it's "WAIT - insufficient data")

---

## 🧪 TESTING STRATEGY

### **Unit Tests (Each Agent)**
```python
# Test success case
async def test_agent_success():
    agent = MarketDataAgent()
    result = await agent.fetch("SPY", "2025-11-20")
    assert result.status == "SUCCESS"
    assert result.current_price > 0

# Test error handling
async def test_agent_handles_errors():
    agent = MarketDataAgent()
    result = await agent.fetch("INVALID", "2025-11-20")
    assert result.status in ["FAILED", "DEGRADED"]
    assert len(result.errors) > 0
```

### **Integration Tests (Full Flow)**
```python
# Test orchestrator end-to-end
async def test_lotto_orchestrator():
    orchestrator = LottoOrchestrator()
    recommendation = await orchestrator.run_lotto("SPY")
    
    assert recommendation.action in [TradeAction.BUY, TradeAction.SELL, TradeAction.WAIT]
    assert recommendation.confidence >= 0.60
    assert recommendation.symbol == "SPY"
```

### **Backtest Validation (Prove Edge)**
```bash
# Populate 30 days of historical data
python agents/scripts/populate_historical.py --symbols SPY QQQ --days 30

# Run backtest
python agents/scripts/backtest_validation.py --days 30

# Success criteria:
# ✅ Win rate >60%
# ✅ Avg R/R >2.0:1
# ✅ Max DD <10%
# ✅ Sharpe >1.5
```

---

## 💡 QUICK TROUBLESHOOTING

### **Agent Not Running?**
```bash
# Check Python path
export PYTHONPATH=/Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main:$PYTHONPATH

# Check imports
python -c "from agents.contracts import MarketDataOutput; print('OK')"

# Run in debug mode
python -m pdb agents/orchestrator/lotto_orchestrator.py
```

### **Tests Failing?**
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run single test with verbose output
pytest tests/agents/test_market_data_agent.py::test_market_data_agent_success -vv

# Check code coverage
pytest tests/ --cov=agents --cov-report=term-missing
```

### **API Rate Limits?**
- **Alpha Vantage:** 5 calls/min (free), 75 calls/min (premium)
- **ChartExchange:** 1000 calls/min (Tier 3)
- **Solution:** Implement caching (context cached per symbol/date, narrative per symbol/day)

---

## 📞 SUPPORT RESOURCES

### **Documentation**
- **Agent Guidelines:** `.cursor/rules/feedback.mdc` (lines 813-1301)
- **Implementation Plan:** `.cursor/rules/AGENT_DEPLOYMENT_PLAN.mdc`
- **Codebase Audit:** `.cursor/rules/review-iteration-1.mdc`
- **API Reference:** `.cursor/rules/charexchange.mdc`

### **Code Examples**
- **Signal Generation:** `live_monitoring/core/signal_generator.py`
- **Data Fetching:** `core/data/alpha_vantage_client.py`, `core/data/ultimate_chartexchange_client.py`
- **DP Analysis:** `core/ultra_institutional_engine.py`
- **Narrative:** `live_monitoring/enrichment/market_narrative_pipeline.py`

### **Existing Tests**
- **Replay:** `replay_lotto_day.py`
- **Backtest:** `backtest_30d_validation.py`
- **Live Monitor:** `run_live_monitor.py`

---

## 🎯 SUCCESS METRICS

### **Phase 1 Success (Modularization)**
- ✅ All 5 agents created and tested
- ✅ All agents return correct data contracts
- ✅ Unit tests pass

### **Phase 2 Success (Orchestration)**
- ✅ Orchestrator runs end-to-end
- ✅ Latency <25 seconds
- ✅ Error handling works (graceful degradation)

### **Phase 3 Success (User Interface)**
- ✅ User can type `/lotto SPY` and get recommendation
- ✅ Discord/Slack/Web UI works

### **Phase 4 Success (Validation)**
- ✅ Backtest shows >60% win rate, >2:1 R/R, <10% DD, >1.5 Sharpe
- ✅ Historical replay produces valid signals
- ✅ Edge proven

### **Phase 5 Success (Production)**
- ✅ System running in production
- ✅ Monitoring dashboard live
- ✅ Users can run commands 24/7

---

## 🚀 FINAL DEPLOYMENT CHECKLIST

Before going live:
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Backtest validates edge
- [ ] Error handling tested (kill APIs, check graceful degradation)
- [ ] Latency <25 seconds
- [ ] Monitoring dashboard configured
- [ ] Alerting set up (PagerDuty, Slack, email)
- [ ] User documentation written
- [ ] Demo video recorded

---

**STATUS: READY TO LAUNCH** 🚀  
**Next Step:** Run commands in `START_HERE.md` to create folder structure and assign agent tasks  
**Timeline:** 4-6 weeks to full production deployment  

💰🎯✨

