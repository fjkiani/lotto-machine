# ITERATION 2: Data Layer & APIs Map

**Date:** 2025-12-05  
**Status:** COMPLETE

---

## Data Connectors Catalog

### Primary Data Sources (ACTIVE - 3)

#### 1. ChartExchange API (Tier 3)
**Client:** `core/data/ultimate_chartexchange_client.py` (464 lines)  
**Used By:** `live_monitoring/core/data_fetcher.py`  
**Status:** ✅ WORKING

**Endpoints:**
- `/data/dark-pool-levels/` - DP battleground levels
- `/data/dark-pool-prints/` - DP trades
- `/data/short-interest/` - Short interest
- `/data/short-volume/` - Short volume %
- `/data/options/chain-summary/` - Options summary
- `/data/stocks/exchange-volume-intraday/` - 30-min volume
- `/data/borrow-fees/` - Borrow fees
- `/data/ftd/` - Failure to Deliver
- `/screener/stocks/` - Stock screener

**Rate Limits:** 1000 req/min (Tier 3)  
**Data Availability:** T+1 (end of day)

#### 2. Yahoo Finance (yfinance)
**Library:** `yfinance` (Python package)  
**Used By:** Multiple systems (direct calls)  
**Status:** ✅ WORKING

**Purpose:**
- Price data (real-time, 1-minute bars)
- Options chains (full chain with Greeks)
- VIX data
- Historical data

**Rate Limits:** ~2000 req/hour (unofficial)  
**Data Availability:** Real-time

#### 3. Alpaca API
**Client:** `live_monitoring/trading/paper_trader.py`  
**Used By:** Paper trading system  
**Status:** ✅ READY (requires setup)

**Purpose:**
- Trade execution (paper/live)
- Account management
- Position tracking

**Rate Limits:** Varies by plan  
**Data Availability:** Real-time

---

### Secondary Data Sources (PARTIAL/ORPHANED - 4)

#### 4. RapidAPI Yahoo Finance
**Client:** `src/data/connectors/yahoo_finance.py`  
**Used By:** Streamlit app  
**Status:** ⚠️ PARTIAL (has fallback to yfinance)

**Purpose:**
- Market quotes
- Options chains
- Historical data

**Fallback:** Direct yfinance if RapidAPI fails

#### 5. Real-Time Finance (RapidAPI)
**Client:** `src/data/connectors/real_time_finance.py`  
**Used By:** Streamlit app  
**Status:** ⚠️ PARTIAL

**Endpoints:**
- `/search` - Stock search
- `/market-trends` - Gainers/losers
- `/stock-time-series-yahoo-finance` - Historical data
- `/stock-news` - News articles

#### 6. Technical Indicators (RapidAPI)
**Client:** `src/data/connectors/technical_indicators_rapidapi.py`  
**Used By:** `src/analysis/technical_analyzer.py`  
**Status:** ⚠️ PARTIAL

**Purpose:**
- SMA, RSI, MACD, ADX indicators
- Historical indicator data

#### 7. Alpha Vantage
**Client:** `core/data/alpha_vantage_client.py` + `src/data/connectors/alpha_vantage.py`  
**Used By:** None (orphaned)  
**Status:** ❌ ORPHANED

---

## Data Flow Map

### Live Monitoring System
```
ChartExchange API
    ↓
ultimate_chartexchange_client.py
    ↓
data_fetcher.py (with caching)
    ↓
signal_generator.py
    ↓
alerts/trading

yfinance (direct)
    ↓
price_action_filter.py, risk_manager.py
```

### Streamlit System
```
YahooFinanceConnector (RapidAPI)
    ↓
analysis modules
    ↓
UI components

RealTimeFinanceConnector
    ↓
analysis modules

TechnicalIndicatorsConnector
    ↓
technical_analyzer.py
```

### Multi-Agent System
```
No direct data fetching
    ↓
Uses LangGraph state
    ↓
Agents fetch data as needed
```

---

## Duplicate Data Fetching Logic

### Yahoo Finance (3 implementations)
1. Direct `yfinance` calls (scattered)
2. `src/data/connectors/yahoo_finance.py` (RapidAPI wrapper)
3. `core/data/real_yahoo_finance_api.py` (direct scraper)

### ChartExchange (2 implementations)
1. `core/data/ultimate_chartexchange_client.py` (primary)
2. `core/data/chartexchange_api_client.py` (older version?)

### Alpha Vantage (2 implementations)
1. `core/data/alpha_vantage_client.py` (orphaned)
2. `src/data/connectors/alpha_vantage.py` (orphaned)

---

## Rate Limits & Dependencies

| API | Rate Limit | Current Usage | Risk |
|-----|------------|---------------|------|
| ChartExchange (Tier 3) | 1000/min | High | ⚠️ Medium |
| yfinance | ~2000/hour | Medium | ⚠️ Medium |
| RapidAPI | Varies | Low | ✅ Low |
| Alpaca | Varies | Low | ✅ Low |

**Mitigation:**
- Caching in `data_fetcher.py`
- Exponential backoff
- Fallback to yfinance

---

## Recommendations

1. **Consolidate Yahoo Finance** - Use single implementation
2. **Standardize data layer** - Create unified `data_layer/` package
3. **Remove orphaned connectors** - Delete Alpha Vantage clients
4. **Document rate limits** - Add to configuration
5. **Implement rate limit monitoring** - Track usage

---

**Deliverable:** ✅ Data source map showing which systems use which APIs

