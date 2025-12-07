# 📚 MODULE QUICK REFERENCE - THE LOTTO MACHINE

**Quick guide to each module, what it does, and how to test it**

---

## 🎯 CORE MODULES

### 1. Dark Pool Intelligence
**File:** `core/ultra_institutional_engine.py`  
**Test:** `python3 test_capabilities.py --module dp`  
**Edge:** Institutional positioning visibility  
**What It Does:** Identifies battlegrounds, calculates buy/sell ratio, measures DP %

### 2. Signal Generation
**File:** `live_monitoring/core/signal_generator.py` (1,253 lines - MONOLITHIC)  
**Test:** `python3 test_capabilities.py --module signals`  
**Edge:** Multi-factor signal confirmation  
**What It Does:** Combines DP, short, options, gamma into signals

### 3. Volume Profile Timing
**File:** `live_monitoring/core/volume_profile.py`  
**Test:** `python3 test_capabilities.py --module volume`  
**Edge:** Optimal entry timing  
**What It Does:** Identifies peak institutional times

### 4. Stock Screener
**File:** `live_monitoring/core/stock_screener.py`  
**Test:** `python3 test_capabilities.py --module screener`  
**Edge:** Ticker discovery  
**What It Does:** Finds high-flow tickers beyond SPY/QQQ

### 5. Gamma Exposure
**File:** `live_monitoring/core/gamma_exposure.py`  
**Test:** `python3 test_capabilities.py --module gamma`  
**Edge:** Dealer positioning awareness  
**What It Does:** Calculates gamma regime, identifies flip levels

### 6. Volatility Expansion
**File:** `live_monitoring/core/volatility_expansion.py`  
**Test:** `python3 test_capabilities.py --module vol`  
**Edge:** Pre-move detection  
**What It Does:** Detects IV compression → expansion

### 7. ZeroDTE Strategy
**File:** `live_monitoring/core/zero_dte_strategy.py`  
**Test:** `python3 test_capabilities.py --module 0dte`  
**Edge:** Options leverage for lottery plays  
**What It Does:** Converts signals to 0DTE options

### 8. Narrative Enrichment
**File:** `live_monitoring/enrichment/narrative_agent.py`  
**Test:** `python3 test_capabilities.py --module narrative`  
**Edge:** Market context understanding  
**What It Does:** LLM explains WHY market is moving

### 9. Price Action Filter
**File:** `live_monitoring/core/price_action_filter.py`  
**Test:** `python3 test_capabilities.py --module price`  
**Edge:** Real-time confirmation  
**What It Does:** Confirms signals with price action

### 10. Risk Manager
**File:** `live_monitoring/core/risk_manager.py`  
**Test:** `python3 test_capabilities.py --module risk`  
**Edge:** Capital preservation  
**What It Does:** Enforces risk limits, position sizing

---

## 🔧 TESTING COMMANDS

```bash
# Test all modules
python3 test_capabilities.py

# Test specific module
python3 test_capabilities.py --module dp
python3 test_capabilities.py --module signals
python3 test_capabilities.py --module gamma

# View results
cat logs/capability_results.json
```

---

## 📊 MODULE STATUS

| Module | Status | Edge | Testable |
|--------|--------|------|----------|
| Dark Pool Intelligence | ✅ Working | High | Yes |
| Signal Generation | ⚠️ Monolithic | High | Partial |
| Volume Profile | ✅ Working | Medium | Yes |
| Stock Screener | ⚠️ API Issues | Medium | Partial |
| Gamma Exposure | ✅ Working | High | Yes |
| Volatility Expansion | ✅ Working | High | Yes |
| ZeroDTE Strategy | ✅ Working | High | Yes |
| Narrative Enrichment | ⚠️ API Issues | Medium | Partial |
| Price Action Filter | ✅ Working | Medium | Yes |
| Risk Manager | ✅ Working | Critical | Yes |

---

## 🎯 HOW THEY COMBINE

```
Stock Screener → Discovers tickers
    ↓
Volume Profile → Optimal timing
    ↓
Dark Pool Intelligence → Battlegrounds & sentiment
    ↓
Gamma Exposure → Dealer positioning
    ↓
Volatility Expansion → Pre-move detection
    ↓
Signal Generation → Multi-factor signals
    ↓
Narrative Enrichment → Context & confidence
    ↓
Price Action Filter → Real-time confirmation
    ↓
ZeroDTE Strategy → Convert to lottery plays
    ↓
Risk Manager → Position sizing & limits
    ↓
ALERT / EXECUTE
```

---

## 🔥 THE EDGE

**Each module provides 5-15% edge improvement.**

**Combined = Multiplicative edge (not additive)**

**The lotto machine = Compound edge from all modules working together**

---

**See `CAPABILITY_EDGE_ANALYSIS.md` for detailed edge breakdown**


