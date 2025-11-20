# Data Sources - Complete Overview

**Last Updated:** 2025-01-XX  
**Status:** Production System

---

## 🎯 PRIMARY DATA SOURCES

### **1. ChartExchange API (Tier 3)** - PRIMARY INSTITUTIONAL DATA
**Base URL:** `https://chartexchange.com/api/v1`  
**Rate Limit:** 1000 requests/minute (Tier 3)  
**API Key:** Required (configured in `configs/chartexchange_config.py`)

#### **Endpoints Used:**

**Dark Pool Data:**
- `/data/dark-pool-levels/` - DP battleground levels with volume
- `/data/dark-pool-prints/` - Individual DP trades (buy/sell, size, time)

**Short Data:**
- `/data/short-interest/` - Short interest, days to cover
- `/data/short-volume/` - Short volume percentage

**Options Data:**
- `/data/options/chain-summary/` - Max pain, put/call ratio, OI totals

**Exchange Volume:**
- `/data/stocks/exchange-volume-intraday/` - 30-minute volume breakdown by exchange
- `/data/stocks/exchange-volume/` - Daily exchange volume totals

**Other:**
- `/data/borrow-fees/` - Interactive Brokers borrow fees
- `/data/ftd/` - Failure to Deliver data
- `/screener/stocks/` - Stock screener for high-flow tickers

**What We Get:**
- ✅ Dark pool battlegrounds (institutional support/resistance)
- ✅ DP buy/sell flow (institutional sentiment)
- ✅ Short interest & days to cover (squeeze potential)
- ✅ Options max pain & P/C ratio (gamma pressure)
- ✅ Exchange volume breakdown (on/off exchange %)
- ✅ Borrow fees (squeeze cost)
- ✅ FTD data (regulatory pressure)

**Client:** `core/data/ultimate_chartexchange_client.py`

---

### **2. Yahoo Finance (yfinance)** - PRIMARY PRICE DATA
**Library:** `yfinance` (Python package)  
**Rate Limit:** ~2000 requests/hour (unofficial, can be rate-limited)  
**Cost:** FREE

#### **What We Get:**

**Price Data:**
- Current price (real-time, 1-minute bars)
- Historical prices (daily, intraday)
- OHLCV data
- Volume

**Options Data:**
- Full options chain (all strikes, expirations)
- Open interest, volume, IV, Greeks (gamma, delta, etc.)
- Used for gamma exposure calculation

**VIX Data:**
- VIX level (volatility index)
- Used for volatility filtering

**What We Use It For:**
- ✅ Current price fetching (`DataFetcher.get_current_price()`)
- ✅ Minute bars for volume/momentum (`DataFetcher.get_minute_bars()`)
- ✅ Options chain for gamma exposure (`GammaExposureTracker`)
- ✅ ATR calculation for stop loss (`RiskManager`)
- ✅ VIX level for volatility filtering (`PriceActionFilter`)

**Used In:**
- `live_monitoring/core/data_fetcher.py`
- `live_monitoring/core/gamma_exposure.py`
- `live_monitoring/core/risk_manager.py`
- `live_monitoring/core/price_action_filter.py`

---

### **3. Alpaca Paper Trading API** - EXECUTION
**Base URL:** `https://paper-api.alpaca.markets`  
**Rate Limit:** Varies by plan (free tier: 200 requests/minute)  
**Cost:** FREE (paper trading)

#### **What We Get:**
- Account balance & positions
- Order execution (market, limit)
- Position management
- Trade history

**What We Use It For:**
- ✅ Paper trading execution (`PaperTrader`)
- ✅ Position tracking
- ✅ P&L calculation

**Used In:**
- `live_monitoring/trading/paper_trader.py`

**Setup Required:**
- Alpaca account (free signup)
- API keys: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`

---

## 🔄 FALLBACK DATA SOURCES (Not Currently Active)

### **4. RapidAPI (Yahoo Finance)** - FALLBACK
**Status:** ⏳ Available but not actively used  
**Rate Limit:** Varies by plan  
**Cost:** Free tier available

**What It Provides:**
- Market quotes
- Options data
- Historical prices

**When Used:**
- Fallback if yfinance fails (in `production_rate_limit_solver.py`)

---

### **5. Yahoo Finance Direct API** - FALLBACK
**Status:** ⏳ Available but not actively used  
**Rate Limit:** Unofficial, can be blocked  
**Cost:** FREE

**What It Provides:**
- Direct market data scraping
- Options chain

**When Used:**
- Last resort fallback (in `production_rate_limit_solver.py`)

---

## 📊 DATA FLOW SUMMARY

### **Live Monitoring System:**

```
ChartExchange API (Tier 3)
    ↓
UltimateChartExchangeClient
    ↓
UltraInstitutionalEngine → InstitutionalContext
    ↓
SignalGenerator → LiveSignal
    ↓
PriceActionFilter (uses yfinance for price confirmation)
    ↓
RiskManager (uses yfinance for ATR)
    ↓
PaperTrader (uses Alpaca for execution)
```

### **Data Types by Source:**

| Data Type | Source | Frequency | Cached? |
|-----------|--------|-----------|---------|
| Dark Pool Levels | ChartExchange | Daily (EOD) | ✅ Yes |
| Dark Pool Prints | ChartExchange | Daily (EOD) | ✅ Yes |
| Short Interest | ChartExchange | Daily (EOD) | ✅ Yes |
| Options Summary | ChartExchange | Daily (EOD) | ✅ Yes |
| Exchange Volume | ChartExchange | Daily (EOD) | ✅ Yes |
| Current Price | yfinance | Real-time (1-min) | ❌ No |
| Options Chain (Full) | yfinance | Real-time | ❌ No |
| VIX Level | yfinance | Real-time (5-min cache) | ✅ Yes |
| ATR (for stops) | yfinance | On-demand | ❌ No |
| Trade Execution | Alpaca | Real-time | ❌ No |

---

## 🔧 CONFIGURATION

### **ChartExchange API:**
```python
# configs/chartexchange_config.py
CHARTEXCHANGE_API_KEY = "your_api_key_here"
CHARTEXCHANGE_TIER = 3  # Tier 3 = 1000 req/min
```

### **Alpaca API:**
```bash
export ALPACA_API_KEY="your_api_key"
export ALPACA_SECRET_KEY="your_secret_key"
```

### **yfinance:**
No configuration needed - just install:
```bash
pip install yfinance
```

---

## ⚠️ RATE LIMITS & CONSIDERATIONS

### **ChartExchange (Tier 3):**
- **Limit:** 1000 requests/minute
- **Strategy:** Rate limiting built into `UltimateChartExchangeClient`
- **Caching:** Institutional context cached for 24 hours

### **yfinance:**
- **Limit:** ~2000 requests/hour (unofficial)
- **Strategy:** Used sparingly, cached where possible
- **Risk:** Can be rate-limited if overused

### **Alpaca:**
- **Limit:** 200 requests/minute (free tier)
- **Strategy:** Only used for execution, not data fetching
- **Risk:** Low (execution is infrequent)

---

## 🚨 DATA AVAILABILITY NOTES

### **T+1 Delay:**
- **Dark Pool Data:** Available EOD (end of day)
- **Short Interest:** Available EOD
- **Options Summary:** Available EOD
- **Exchange Volume:** Available EOD

**Impact:** We use yesterday's institutional data for today's signals (today's data forms at EOD)

### **Real-Time Data:**
- **Price:** Real-time via yfinance
- **Options Chain:** Real-time via yfinance (for gamma)
- **VIX:** Real-time via yfinance

### **Missing Endpoints:**
- ❌ **Intraday Trades:** Not available in ChartExchange (order flow uses DP prints as proxy)
- ❌ **Reddit Sentiment:** Endpoint returns 404 (handled gracefully)
- ❌ **Full Options Chain:** ChartExchange only has summary (use yfinance for full chain)

---

## 📁 KEY FILES

### **Data Clients:**
- `core/data/ultimate_chartexchange_client.py` - ChartExchange API client
- `live_monitoring/core/data_fetcher.py` - Unified data fetcher with caching
- `live_monitoring/trading/paper_trader.py` - Alpaca execution client

### **Data Usage:**
- `live_monitoring/core/signal_generator.py` - Uses institutional context
- `live_monitoring/core/gamma_exposure.py` - Uses yfinance for options
- `live_monitoring/core/price_action_filter.py` - Uses yfinance for price/VIX
- `live_monitoring/core/risk_manager.py` - Uses yfinance for ATR

---

## 🎯 SUMMARY

**Primary Sources:**
1. **ChartExchange (Tier 3)** - Institutional data (DP, short, options summary, volume)
2. **yfinance** - Price data, full options chain, VIX
3. **Alpaca** - Trade execution (paper trading)

**Data Strategy:**
- Institutional data: ChartExchange (cached, T+1)
- Price data: yfinance (real-time)
- Execution: Alpaca (real-time)
- Fallbacks: RapidAPI, Yahoo Direct (not actively used)

**Total Data Sources:** 3 active, 2 fallback

---

**STATUS: All data sources operational and integrated** ✅

