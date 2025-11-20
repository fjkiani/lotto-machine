# API Reference Guide

## ChartExchange API

### Dark Pool Levels
```python
GET /data/dark-pool-levels/
```
**Parameters:**
- `symbol`: Stock symbol (e.g., "US:SPY")
- `date`: Date in YYYY-MM-DD format
- `decimals`: Price decimal places (default: 2)
- `page_size`: Results per page (default: 100)
- `ordering`: Sort order (default: "-premium")

**Response:**
```json
[
  {
    "level": 664.18,
    "volume": 1500000,
    "trades": 45,
    "date": "2025-10-17",
    "premium": 0.25
  }
]
```

### Dark Pool Prints
```python
GET /data/dark-pool-prints/
```
**Parameters:**
- `symbol`: Stock symbol (e.g., "US:SPY")
- `date`: Date in YYYY-MM-DD format
- `decimals`: Price decimal places (default: 2)
- `page_size`: Results per page (default: 100)
- `ordering`: Sort order (default: "-time")

**Response:**
```json
[
  {
    "price": 664.28,
    "size": 10000,
    "time": "2025-10-17 15:30:45.123456",
    "side": "B"
  }
]
```

## Yahoo Direct API

### Market Data
```python
def get_market_data(self, ticker: str) -> Dict[str, Any]:
```
**Returns:**
```json
{
  "price": 664.39,
  "volume": 45000000,
  "change": 2.15,
  "change_percent": 0.32,
  "high": 665.20,
  "low": 662.10,
  "open": 662.50,
  "timestamp": "2025-10-17T15:30:00Z"
}
```

### Options Chain
```python
def get_option_chain(self, ticker: str) -> Dict[str, Any]:
```
**Returns:**
```json
{
  "calls": [
    {
      "strike": 665.0,
      "bid": 1.25,
      "ask": 1.30,
      "volume": 1500,
      "open_interest": 25000,
      "implied_volatility": 0.18
    }
  ],
  "puts": [...]
}
```

## DP-Aware Signal Filter

### Analyze DP Structure
```python
async def analyze_dp_structure(self, ticker: str) -> DPStructure:
```
**Returns:**
```python
@dataclass
class DPStructure:
    ticker: str
    current_price: float
    dp_support_levels: List[float]
    dp_resistance_levels: List[float]
    dp_volume_at_levels: Dict[float, int]
    dp_strength_score: float
    institutional_battlegrounds: List[float]
    breakout_levels: List[float]
    mean_reversion_levels: List[float]
    timestamp: datetime
```

### Filter Signals
```python
async def filter_signals_with_dp_confirmation(self, ticker: str) -> List[TightenedSignal]:
```
**Returns:**
```python
@dataclass
class TightenedSignal:
    ticker: str
    action: str  # "BUY" or "SELL"
    entry_price: float
    confidence: float
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    dp_agreement: float
    breakout: bool
    mean_reversion: bool
    dp_factors: List[str]
    timestamp: datetime
```

## Core Signals Runner

### Run Live Signals
```python
async def run_live_signals(tickers: List[str] = ["SPY", "QQQ"]) -> None:
```
**Features:**
- RTH only (09:30-16:00 ET)
- Minute-by-minute processing
- DP confirmation required
- CSV/JSON logging

### Replay Session
```python
async def replay_session(ticker: str, start_time: datetime, end_time: datetime) -> None:
```
**Features:**
- Historical data replay
- Signal detection validation
- Performance analysis
- Chart overlays

## Configuration

### ChartExchange Config
```python
# configs/chartexchange_config.py
CHARTEXCHANGE_API_KEY = "your_api_key_here"
CHARTEXCHANGE_TIER = 3  # 1, 2, or 3
```

### DP Filter Config
```python
# DP structure thresholds
dp_support_threshold = 0.7
dp_resistance_threshold = 0.7
battleground_threshold = 0.8
breakout_confirmation_threshold = 0.25
mean_reversion_threshold = 0.15

# Signal tightening parameters
min_dp_agreement = 0.3
min_composite_confidence = 0.75
max_risk_level = "MEDIUM"
```

## Error Handling

### Common Exceptions
```python
class ChartExchangeAPIError(Exception):
    """ChartExchange API specific errors"""
    pass

class YahooDirectError(Exception):
    """Yahoo Direct API errors"""
    pass

class DPFilterError(Exception):
    """DP filter processing errors"""
    pass
```

### Rate Limiting
```python
# ChartExchange API rate limiting
rate_limits = {
    1: 60,    # req/min
    2: 250,   # req/min
    3: 1000   # req/min
}

# Yahoo Direct has no rate limits
```

## Testing

### Unit Tests
```bash
python3 tests/test_core_system.py
```

### Integration Tests
```bash
python3 tests/test_dp_filter.py
python3 tests/test_chartexchange_api.py
```

### Performance Tests
```bash
python3 tests/test_performance.py
```

## Logging

### Log Levels
- `DEBUG`: Detailed debugging information
- `INFO`: General information about system operation
- `WARNING`: Warning messages for potential issues
- `ERROR`: Error messages for failed operations
- `CRITICAL`: Critical errors that may cause system failure

### Log Files
- `logs/core_signals.csv` - Signal history
- `logs/core_signals.jsonl` - Detailed signal logs
- `logs/errors.log` - Error messages
- `logs/performance.log` - Performance metrics

## Monitoring

### Key Metrics
- Signal frequency per hour
- DP agreement scores
- Risk level distribution
- API response times
- Error rates

### Alerts
- High risk signals
- API failures
- Rate limit warnings
- System errors

---

**For more details, see the main README.md** 📚


Reference


GET
/ref/stocks/exchange/
List of stock exchanges



GET
/ref/stocks/symbol/
List of stock symbols



GET
/ref/crypto/exchange/
List of crypto exchanges



GET
/ref/crypto/symbol/
List of crypto pairs



GET
/ref/forex/symbol/
List of forex pairs



GET
/ref/options/contracts/
List of option contracts



GET
/ref/reddit/subreddits/
List of subreddits that we track


Data


GET
/data/stocks/exchange-volume/
Exchange volume for a given stock



GET
/data/stocks/exchange-volume-intraday/
Historical exchange volume for a given stock at 30 minute intervals



GET
/data/stocks/short-volume/
Short volume for a given stock



GET
/data/stocks/short-interest/
Short Interest for a given stock



GET
/data/stocks/short-interest-daily/
Daily Short Interest for a given stock



GET
/data/stocks/borrow-fee/ib/
Cost-to-borrow from Interactive Brokers



GET
/data/stocks/failure-to-deliver/
FTDs for a given stock



GET
/data/stocks/dividends/
Dividends for a given stock



GET
/data/stocks/splits/
Splits for a given stock



GET
/data/options/chain-summary/
Option chain summary (max pain, ITM/OTM)


Data - Reddit


GET
/data/reddit/mentions/top/
Top mentioned tickers for a given timeframe



GET
/data/reddit/mentions/stock/
Reddit mentions for a given stock



GET
/data/reddit/mentions/daily/stock/
Daily Reddit mention counts for a given stock



GET
/data/reddit/mentions/crypto/
Reddit mentions for a given crypto base



GET
/data/reddit/mentions/daily/crypto/
Daily Reddit mention counts for a given crypto base


Feed


GET
/feed/stocks/quote/
Quote for a given stock



GET
/feed/crypto/quote/
Quote for a given crypto



GET
/feed/forex/quote/
Quote for a given forex


Data - Tier 2


GET
/data/crypto/bars/
Crypto aggregate OHLC bars (k-line)



GET
/data/forex/bars/
Forex aggregate OHLC bars (k-line)



GET
/data/stocks/bars/
Stock aggregate OHLC bars (k-line)



GET
/data/options/bars/
Option aggregate OHLC bars (k-line)



GET
/data/stocks/shares/
Historical Float and Shares Outstanding for a given stock


Data - Tier 3


GET
/data/dark-pool-levels/
Dark Pool Levels for a given stock



GET
/data/dark-pool-prints/
Dark Pool Prints (trades) for a given stock



GET
/data/dark-pool-prints/summary/
Dark Pool Prints (trades) summary for a given stock



GET
/data/crypto/level-2-snapshots/
Crypto level 2 snapshots


Stock Screener - Tier 3


GET
/screener/stocks/
Screen thousands of stocks on numerous fields



GET
/screener/stocks/columns/
List of Columns



GET
/screener/stocks/groups/region/
List of Regions



GET
/screener/stocks/groups/equity-type/
List of EquityTypes



GET
/screener/stocks/groups/exchange/
List of Exchanges



GET
/screener/stocks/groups/currency/
List of Currencies



GET
/screener/stocks/groups/sector/
List of Sectors



GET
/screener/stocks/groups/industry/
List of Industries



GET
/screener/stocks/groups/country/
List of Countries



GET
/screener/stocks/groups/next-earnings/
List of NextEarnings



GET
/screener/stocks/groups/options/
List of Options




