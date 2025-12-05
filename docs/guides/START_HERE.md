# 🚀 START HERE: Lotto Machine Implementation

**Current Status:** All planning complete, ready to build  
**Time to Production:** 4-6 weeks  
**Your Role:** Direct agents to execute the plan  

---

## 📋 QUICK START (5 Minutes)

### **Step 1: Review the Plan**
```bash
# Read the complete deployment plan
cat .cursor/rules/AGENT_DEPLOYMENT_PLAN.mdc

# Read the agentic architecture (from feedback.mdc lines 813-1301)
head -n 1301 .cursor/rules/feedback.mdc | tail -n 488
```

### **Step 2: Create Folder Structure**
```bash
# Run this NOW to set up the project structure
cd /Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main

mkdir -p agents/{data_providers,context,analysis,decision,orchestrator,scripts}
touch agents/__init__.py
touch agents/data_providers/__init__.py
touch agents/context/__init__.py
touch agents/analysis/__init__.py
touch agents/decision/__init__.py
touch agents/orchestrator/__init__.py
```

### **Step 3: Create Data Contracts**
```bash
# Define all agent interfaces (this is critical - do this FIRST)
cat > agents/contracts.py << 'EOF'
"""
Agent Data Contracts
All agents use these standardized dataclasses for communication
"""
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum
import pandas as pd

# ============================================================================
# LAYER 1: DATA PROVIDER OUTPUTS
# ============================================================================

@dataclass
class MarketDataOutput:
    """Output from Market Data Agent"""
    symbol: str
    current_price: float
    minute_bars: Optional[pd.DataFrame]  # 1m OHLCV
    daily_bars: Optional[pd.DataFrame]   # Daily history
    volume_profile: Dict[str, Any]       # Intraday volume by time
    timestamp: datetime
    status: str = "SUCCESS"
    errors: List[str] = field(default_factory=list)

@dataclass
class InstitutionalFlowOutput:
    """Output from Institutional Flow Agent"""
    symbol: str
    date: str
    dp_levels: List[Dict]                # DP battlegrounds
    dp_prints: List[Dict]                # DP trades
    dark_pool_pct: float                 # % off-exchange
    dp_buy_sell_ratio: float             # Buy pressure
    short_volume_pct: float
    short_interest: Optional[int]
    borrow_fee_rate: float
    max_pain: Optional[float]
    put_call_ratio: float
    total_option_oi: int
    gamma_exposure: Dict[str, Any]
    status: str = "SUCCESS"
    errors: List[str] = field(default_factory=list)

@dataclass
class MacroEventOutput:
    """Output from Macro Event Agent"""
    symbol: str
    date: str
    events_today: List[Dict]             # Fed, CPI, earnings
    binary_event: bool                   # High-impact event?
    catalyst_type: Optional[str]         # "FED_SPEECH", "CPI", "EARNINGS"
    event_sentiment: str                 # "BULLISH", "BEARISH", "NEUTRAL"
    confidence_modifier: float           # 0.5-1.5
    status: str = "SUCCESS"
    errors: List[str] = field(default_factory=list)

@dataclass
class SentimentOutput:
    """Output from Sentiment Agent"""
    symbol: str
    reddit_regime: str                   # "HYPE", "FEAR", "NEUTRAL", "STEALTH"
    sentiment_score: float               # -1.0 to +1.0
    sentiment_ok: bool                   # Approve/veto signals
    news_narrative: str                  # Mainstream story
    narrative_type: str                  # "BULLISH_HYPE", "DISTRIBUTION_TRAP"
    status: str = "SUCCESS"
    errors: List[str] = field(default_factory=list)

@dataclass
class CrossAssetOutput:
    """Output from Cross-Asset Agent"""
    date: str
    btc_price: float
    btc_change_pct: float
    vix_level: float
    vix_change_pct: float
    risk_regime: str                     # "RISK_ON", "RISK_OFF", "MIXED"
    equity_crypto_corr: float            # -1.0 to +1.0
    override_signal: Optional[str]       # "VETO_LONGS", "VETO_SHORTS"
    status: str = "SUCCESS"
    errors: List[str] = field(default_factory=list)

# ============================================================================
# LAYER 2: CONTEXT BUILDER OUTPUT
# ============================================================================

@dataclass
class InstitutionalContext:
    """Aggregated institutional intelligence"""
    symbol: str
    date: str
    
    # From Institutional Flow Agent
    dp_battlegrounds: List[float]
    dark_pool_pct: float
    dp_buy_sell_ratio: float
    short_volume_pct: float
    borrow_fee_rate: float
    max_pain: Optional[float]
    put_call_ratio: float
    dp_total_volume: int
    short_interest: Optional[int]
    days_to_cover: Optional[float]
    dp_avg_print_size: float
    total_option_oi: int
    
    # Composite scores
    institutional_buying_pressure: float  # 0-100
    squeeze_potential: float              # 0-100
    gamma_pressure: float                 # -100 to +100
    
    # From other agents
    liquidity_regime: Optional[str] = None
    sentiment_regime: Optional[str] = None
    risk_regime: Optional[str] = None
    binary_event: bool = False
    
    # Metadata
    data_completeness: float = 1.0        # 0-100%
    warnings: List[str] = field(default_factory=list)

# ============================================================================
# LAYER 3: ANALYSIS AGENT OUTPUTS
# ============================================================================

@dataclass
class LiquidityRegimeOutput:
    """Output from Liquidity Agent"""
    symbol: str
    time_of_day: str                     # "09:30", "10:00", etc.
    liquidity_regime: str                # "THIN", "NORMAL", "HEAVY"
    off_exchange_pct: float              # Current 30m window
    liquidity_ok: bool                   # Trade now?
    reason: str                          # Explanation
    status: str = "SUCCESS"
    errors: List[str] = field(default_factory=list)

@dataclass
class DPStructureOutput:
    """Output from DP Filter Agent"""
    approved: bool                       # DP structure agrees?
    risk_level: str                      # "LOW", "MEDIUM", "HIGH"
    adjusted_stop: Optional[float]       # Tightened stop
    adjusted_target: Optional[float]     # Adjusted target
    dp_reasoning: str                    # Explanation
    magnet_alert: Optional[str]          # "APPROACHING", "BREAKING", "BOUNCING"
    status: str = "SUCCESS"
    errors: List[str] = field(default_factory=list)

@dataclass
class SignalOutput:
    """Output from Signal Agent"""
    signals: List[Any]                   # List of LiveSignal objects
    lottery_signals: List[Any]           # List of LotterySignal objects
    best_signal: Optional[Any]           # Highest confidence signal
    signal_count: int
    confidence_distribution: Dict[str, int]
    status: str = "SUCCESS"
    errors: List[str] = field(default_factory=list)

@dataclass
class NarrativeOutput:
    """Output from Narrative Agent"""
    date: str
    symbol: str
    institutional_narrative: str
    macro_narrative: str
    crypto_narrative: str
    web_narrative: str
    divergence_detected: bool
    narrative_aligns: bool
    final_story: str
    status: str = "SUCCESS"
    errors: List[str] = field(default_factory=list)

@dataclass
class ValidationOutput:
    """Output from Validation Agent"""
    validated: bool
    conflicts: List[str]
    overrides: List[str]
    confidence_adjustment: float         # -0.3 to +0.3
    final_verdict: str                   # "APPROVED", "VETOED", "DEGRADED"
    status: str = "SUCCESS"
    errors: List[str] = field(default_factory=list)

# ============================================================================
# LAYER 4: DECISION OUTPUT
# ============================================================================

class TradeAction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"

@dataclass
class TradeRecommendation:
    """Final output from Decision Synthesis Agent"""
    action: TradeAction
    symbol: str
    entry: Optional[float]
    stop: Optional[float]
    target: Optional[float]
    confidence: float                    # 0-100
    size_pct: float                      # % of account (0-5%)
    signal_type: str                     # "SQUEEZE", "DP_BREAKOUT", etc.
    reasoning: str                       # Multi-line explanation
    narrative: str                       # Full story
    warnings: List[str]
    timestamp: datetime
    
    # Rich context for debugging
    context: Optional[InstitutionalContext] = None
    all_signals: Optional[List[Any]] = None

# ============================================================================
# AGENT MESSAGE PROTOCOL
# ============================================================================

@dataclass
class AgentMessage:
    """Standardized message wrapper for all agent communications"""
    agent_id: str                        # "market_data_agent"
    status: str                          # "SUCCESS", "FAILED", "DEGRADED"
    output: Any                          # Agent-specific output
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
EOF
```

---

## 🎯 AGENT TASKS (Assign These Now)

### **TASK 1: Market Data Agent** (2-3 hours)
**File:** `agents/data_providers/market_data_agent.py`

**Command for agent:**
```
Create agents/data_providers/market_data_agent.py that:
1. Wraps AlphaVantageClient from core/data/alpha_vantage_client.py
2. Implements async fetch(symbol, date) method
3. Returns MarketDataOutput from agents/contracts.py
4. Handles errors gracefully (if AlphaVantage fails, try ChartExchange bars as fallback)
5. Adds basic unit tests

Expected output contract: MarketDataOutput(symbol, current_price, minute_bars, daily_bars, volume_profile, timestamp)
```

### **TASK 2: Institutional Flow Agent** (3-4 hours)
**File:** `agents/data_providers/institutional_flow_agent.py`

**Command for agent:**
```
Create agents/data_providers/institutional_flow_agent.py that:
1. Wraps UltimateChartExchangeClient calls for DP/short/options data
2. Implements async fetch(symbol, date) method
3. Calls: get_dark_pool_levels, get_dark_pool_prints, get_dark_pool_summary, get_short_volume, get_short_interest, get_borrow_fee, get_options_chain_summary
4. Returns InstitutionalFlowOutput from agents/contracts.py
5. Handles missing data gracefully (set defaults, log warnings)
6. Adds basic unit tests

Expected output contract: InstitutionalFlowOutput(symbol, date, dp_levels, dp_prints, dark_pool_pct, etc.)
```

### **TASK 3: Context Builder Agent** (2-3 hours)
**File:** `agents/context/context_builder_agent.py`

**Command for agent:**
```
Create agents/context/context_builder_agent.py that:
1. Takes InstitutionalFlowOutput from Task 2
2. Calls UltraInstitutionalEngine.build_institutional_context() (or rebuilds the logic)
3. Returns InstitutionalContext from agents/contracts.py
4. Calculates composite scores (institutional_buying_pressure, squeeze_potential, gamma_pressure)
5. Tracks data_completeness (% of fields successfully fetched)
6. Adds basic unit tests

Expected output contract: InstitutionalContext(symbol, date, dp_battlegrounds, composite scores, etc.)
```

### **TASK 4: Liquidity Agent (NEW)** (4-5 hours)
**File:** `agents/analysis/liquidity_agent.py`

**Command for agent:**
```
Create agents/analysis/liquidity_agent.py that:
1. Calls ChartExchange /data/stocks/exchange-volume-intraday/ for SPY/QQQ
2. Parses 30-minute volume windows
3. Calculates lit vs off-exchange percentages per window
4. Determines liquidity regime:
   - THIN: off-exchange >70% OR volume <50% of average
   - HEAVY: off-exchange 30-50% AND volume >150% of average
   - NORMAL: everything else
5. Returns LiquidityRegimeOutput(liquidity_ok=True if NORMAL/HEAVY, False if THIN)
6. Adds reasoning: "Peak institutional flow" or "Avoid: lunch chop" etc.
7. Adds basic unit tests

Expected output contract: LiquidityRegimeOutput(symbol, time_of_day, liquidity_regime, liquidity_ok, reason)
```

### **TASK 5: Signal Agent Refactor** (3-4 hours)
**File:** `agents/analysis/signal_agent.py`

**Command for agent:**
```
Refactor live_monitoring/core/signal_generator.py into agents/analysis/signal_agent.py:
1. Keep all signal generation logic (squeeze, gamma, DP breakout/bounce, selloff, lottery)
2. Simplify interface: async analyze(context: InstitutionalContext, minute_bars: pd.DataFrame, account_value: float)
3. Remove narrative enrichment (move to separate narrative agent)
4. Remove sentiment filtering (keep as optional input, don't call RedditSentimentAnalyzer directly)
5. Return SignalOutput(signals, lottery_signals, best_signal, signal_count, confidence_distribution)
6. Adds basic unit tests

Expected output contract: SignalOutput(signals, best_signal, etc.)
```

### **TASK 6: Orchestrator** (5-6 hours)
**File:** `agents/orchestrator/lotto_orchestrator.py`

**Command for agent:**
```
Create agents/orchestrator/lotto_orchestrator.py that:
1. Implements 5-layer async execution:
   - Layer 1: Parallel data fetch (market_data, inst_flow, macro, sentiment, cross_asset)
   - Layer 2: Sequential context build
   - Layer 3: Parallel analysis (liquidity, dp_filter, signal, narrative, validation)
   - Layer 4: Sequential decision synthesis
   - Layer 5: UI formatting
2. Uses asyncio.gather() for parallel execution
3. Wraps each agent call in AgentMessage for error tracking
4. Implements graceful degradation (if agent fails, continue with degraded data)
5. Adds caching (narrative cached per symbol/day, context cached per symbol/date)
6. Adds execution time tracking
7. Returns TradeRecommendation

Entry point: async run_lotto(symbol: str) -> TradeRecommendation
```

---

## 📦 UTILITIES TO CREATE

### **Util 1: Agent Base Class**
```bash
cat > agents/base_agent.py << 'EOF'
"""Base class for all agents"""
import logging
from abc import ABC, abstractmethod
from typing import Any
from datetime import datetime
from agents.contracts import AgentMessage

class BaseAgent(ABC):
    """Base class with error handling and logging"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.logger = logging.getLogger(agent_id)
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Each agent implements this"""
        pass
    
    async def run(self, *args, **kwargs) -> AgentMessage:
        """Wrapper with error handling"""
        start_time = datetime.now()
        
        try:
            output = await self.execute(*args, **kwargs)
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return AgentMessage(
                agent_id=self.agent_id,
                status="SUCCESS",
                output=output,
                execution_time_ms=execution_time,
                timestamp=datetime.now()
            )
        except Exception as e:
            self.logger.error(f"Agent {self.agent_id} failed: {e}")
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return AgentMessage(
                agent_id=self.agent_id,
                status="FAILED",
                output=None,
                errors=[str(e)],
                execution_time_ms=execution_time,
                timestamp=datetime.now()
            )
EOF
```

---

## 🧪 TESTING FRAMEWORK

### **Create Test Structure**
```bash
mkdir -p tests/agents/{data_providers,context,analysis,orchestrator}
touch tests/__init__.py
touch tests/agents/__init__.py

# Create sample test
cat > tests/agents/test_market_data_agent.py << 'EOF'
"""Tests for Market Data Agent"""
import pytest
from agents.data_providers.market_data_agent import MarketDataAgent
from agents.contracts import MarketDataOutput

@pytest.mark.asyncio
async def test_market_data_agent_success():
    agent = MarketDataAgent()
    result = await agent.fetch("SPY", "2025-11-20")
    
    assert isinstance(result, MarketDataOutput)
    assert result.symbol == "SPY"
    assert result.current_price > 0
    assert result.minute_bars is not None

@pytest.mark.asyncio
async def test_market_data_agent_handles_errors():
    agent = MarketDataAgent()
    result = await agent.fetch("INVALID_SYMBOL", "2025-11-20")
    
    assert result.status == "FAILED" or result.status == "DEGRADED"
    assert len(result.errors) > 0
EOF
```

---

## ⚡ IMMEDIATE NEXT STEPS (DO THIS NOW)

**Step 1:** Run folder structure command above ✅  
**Step 2:** Create `agents/contracts.py` (done above) ✅  
**Step 3:** Create `agents/base_agent.py` (done above) ✅  

**Step 4:** **Assign TASK 1-3 to 3 different agents in parallel**
- Agent A: Market Data Agent (TASK 1)
- Agent B: Institutional Flow Agent (TASK 2)  
- Agent C: Context Builder Agent (TASK 3)

**Step 5:** Once TASK 1-3 complete, assign TASK 4-5 in parallel
- Agent D: Liquidity Agent (TASK 4)
- Agent E: Signal Agent (TASK 5)

**Step 6:** Once TASK 1-5 complete, assign TASK 6
- Agent F: Orchestrator (TASK 6)

---

## 📊 PROGRESS TRACKING

Create this file to track progress:

```bash
cat > PROGRESS.md << 'EOF'
# Lotto Machine Implementation Progress

## Phase 1: Modularization (Week 1-2)
- [ ] Folder structure created
- [ ] Data contracts defined
- [ ] Base agent class created
- [ ] Market Data Agent (TASK 1)
- [ ] Institutional Flow Agent (TASK 2)
- [ ] Context Builder Agent (TASK 3)
- [ ] Liquidity Agent (TASK 4)
- [ ] Signal Agent (TASK 5)

## Phase 2: Orchestration (Week 2-3)
- [ ] Orchestrator created (TASK 6)
- [ ] Layer 1-5 async execution working
- [ ] Error handling complete
- [ ] Caching implemented

## Phase 3: User Interface (Week 3-4)
- [ ] CLI commands working
- [ ] Discord bot working
- [ ] Web UI working

## Phase 4: Testing (Week 4-5)
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Backtest validates edge
- [ ] Historical replay works

## Phase 5: Production (Week 5-6)
- [ ] Production orchestrator deployed
- [ ] Monitoring dashboard live
- [ ] User can run /lotto in production
EOF
```

---

## 🎯 YOUR COMMAND TO AGENTS

**Copy-paste this to assign work:**

```
AGENT A: Implement TASK 1 (Market Data Agent)
File: agents/data_providers/market_data_agent.py
Reference: agents/contracts.py for MarketDataOutput
Source code: core/data/alpha_vantage_client.py (wrap this)
Deadline: 2-3 hours
Tests: tests/agents/test_market_data_agent.py

AGENT B: Implement TASK 2 (Institutional Flow Agent)  
File: agents/data_providers/institutional_flow_agent.py
Reference: agents/contracts.py for InstitutionalFlowOutput
Source code: core/data/ultimate_chartexchange_client.py (use this)
Deadline: 3-4 hours
Tests: tests/agents/test_institutional_flow_agent.py

AGENT C: Implement TASK 3 (Context Builder Agent)
File: agents/context/context_builder_agent.py
Reference: agents/contracts.py for InstitutionalContext
Source code: core/ultra_institutional_engine.py (rebuild this logic)
Deadline: 2-3 hours
Tests: tests/agents/test_context_builder_agent.py
```

---

**STATUS: READY TO LAUNCH** 🚀  
**Next:** Run the folder structure command, then assign TASK 1-3 to agents  
**Expected Result:** Agents will build the foundation in 1-2 weeks, then we orchestrate and deploy  

💰🎯✨

