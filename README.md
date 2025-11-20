# AI Hedge Fund - Core Signals System

## 🎯 Overview

A real-time market intelligence system that detects institutional breakouts and reversals using dark pool (DP) data confirmation. The system prioritizes **institutional flow validation** over retail signals to avoid traps and identify high-probability moves.

## 🏗️ Architecture

### Core Components

```
core/
├── core_signals_runner.py          # Main orchestration system
├── data/                           # Data connectors
│   ├── chartexchange_api_client.py # ChartExchange DP data API
│   ├── real_breakout_reversal_detector_yahoo_direct.py # Yahoo Direct scraper
│   └── production_rate_limit_solver.py # Rate limiting utilities
├── detectors/                      # Signal detection
│   ├── live_high_resolution_detector.py
│   └── real_breakout_reversal_detector_yahoo_direct.py
└── filters/                        # Signal filtering
    └── dp_aware_signal_filter.py  # DP-aware signal validation
```

### Data Flow

1. **Price Data**: Yahoo Direct API (no rate limits)
2. **DP Data**: ChartExchange API (Tier 3, 1000 req/min)
3. **Signal Detection**: Breakout/reversal detection with rolling windows
4. **DP Filtering**: Institutional confirmation required
5. **Output**: Timestamped signals with confidence scores

## 🚀 Quick Start

### Prerequisites

```bash
pip install requests numpy yfinance
```

### Configuration

Create `configs/chartexchange_config.py`:
```python
CHARTEXCHANGE_API_KEY = "your_api_key_here"
CHARTEXCHANGE_TIER = 3
```

### Run Core System

```bash
# Test the system
python3 tests/test_core_system.py

# Run live signals (RTH only)
python3 core/core_signals_runner.py
```

## 📊 APIs & Data Sources

### 1. ChartExchange API (Primary DP Data)

**Endpoints:**
- `/data/dark-pool-levels/` - DP support/resistance levels
- `/data/dark-pool-prints/` - Real-time DP transactions

**Usage:**
```python
from core.data.chartexchange_api_client import ChartExchangeAPI
from configs.chartexchange_config import CHARTEXCHANGE_API_KEY

api = ChartExchangeAPI(CHARTEXCHANGE_API_KEY, tier=3)
dp_levels = api.get_dark_pool_levels('SPY', days_back=1)
dp_prints = api.get_dark_pool_prints('SPY', days_back=1)
```

**Rate Limits:**
- Tier 1: 60 req/min
- Tier 2: 250 req/min  
- Tier 3: 1000 req/min

### 2. Yahoo Direct API (Price Data)

**Features:**
- No rate limits
- Real-time quotes
- Historical data
- Options chains

**Usage:**
```python
from core.detectors.real_breakout_reversal_detector_yahoo_direct import YahooDirectDataProvider

provider = YahooDirectDataProvider()
data = provider.get_market_data('SPY')
```

### 3. DP-Aware Signal Filter

**Purpose:** Only trigger signals when institutional flow confirms the move

**Key Features:**
- DP level proximity detection
- Institutional battleground avoidance
- Risk level calculation
- Signal tightening based on DP agreement

**Usage:**
```python
from core.filters.dp_aware_signal_filter import DPAwareSignalFilter

filter = DPAwareSignalFilter()
signals = await filter.filter_signals_with_dp_confirmation('SPY')
```

## 🔍 Signal Detection Logic

### Breakout Detection
- **Rolling Windows**: 5, 10, 20, 30 minutes
- **Thresholds**: 0.2% - 1.5% price movement
- **Volume Confirmation**: Above average volume
- **DP Confirmation**: Price above DP resistance levels

### Reversal Detection  
- **Support Levels**: DP support level proximity
- **Mean Reversion**: Price below DP support
- **Volume Confirmation**: Above average volume
- **DP Confirmation**: Price near DP support levels

### DP Structure Analysis
- **Support Levels**: Price levels with high DP volume below current price
- **Resistance Levels**: Price levels with high DP volume above current price
- **Battlegrounds**: High-volume DP levels (>1M shares or >10K contracts)
- **Strength Score**: Normalized DP volume (0-1 scale)

## 📈 Signal Output Format

```json
{
  "ticker": "SPY",
  "action": "BUY",
  "entry_price": 664.39,
  "confidence": 0.75,
  "risk_level": "HIGH",
  "dp_agreement": 0.30,
  "breakout": false,
  "mean_reversion": true,
  "dp_factors": ["near_support"],
  "timestamp": "2025-10-17T23:00:12Z"
}
```

## 🎛️ Configuration Parameters

### DP Filter Settings
```python
# DP structure thresholds
dp_support_threshold = 0.7      # 70% of volume at support
dp_resistance_threshold = 0.7    # 70% of volume at resistance  
battleground_threshold = 0.8     # 80% institutional ratio = battleground
breakout_confirmation_threshold = 0.25  # 25% above magnet for breakout
mean_reversion_threshold = 0.15  # 15% below DP support for mean reversion

# Signal tightening parameters
min_dp_agreement = 0.3          # Minimum DP agreement (lowered for testing)
min_composite_confidence = 0.75 # 75% composite signal confidence
max_risk_level = "MEDIUM"       # Maximum risk level allowed
```

### Detection Windows
```python
# Rolling window sizes (minutes)
windows = [5, 10, 20, 30]

# Breakout thresholds (%)
breakout_thresholds = [0.2, 0.5, 1.0, 1.5]

# Volume multipliers
volume_multipliers = [1.5, 2.0, 2.5, 3.0]
```

## 🚨 Risk Management

### Risk Levels
- **LOW**: Strong DP confirmation, low volatility
- **MEDIUM**: Moderate DP confirmation, normal volatility  
- **HIGH**: Weak DP confirmation, high volatility

### DP Agreement Factors
- **near_support**: Price within 3% of DP support level
- **near_resistance**: Price within 3% of DP resistance level
- **battleground**: Price near institutional battleground
- **volume_confirmation**: Above-average volume
- **momentum_alignment**: Price momentum aligns with DP structure

## 📊 Monitoring & Logging

### Log Files
- `logs/core_signals.csv` - Signal history
- `logs/core_signals.jsonl` - Detailed signal logs

### Key Metrics
- Signal frequency
- DP agreement scores
- Risk level distribution
- Win/loss ratios
- Drawdown periods

## 🔧 Troubleshooting

### Common Issues

1. **No DP Data**: Check ChartExchange API key and tier
2. **Rate Limits**: Verify API tier limits
3. **No Signals**: Check DP agreement thresholds
4. **Import Errors**: Verify folder structure and paths

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📚 Examples

### Basic Signal Detection
```python
import asyncio
from core.filters.dp_aware_signal_filter import DPAwareSignalFilter

async def detect_signals():
    filter = DPAwareSignalFilter()
    signals = await filter.filter_signals_with_dp_confirmation('SPY')
    
    for signal in signals:
        print(f"{signal.action} {signal.ticker} @ ${signal.entry_price:.2f}")
        print(f"Risk: {signal.risk_level}, DP Agreement: {signal.dp_agreement:.2f}")

asyncio.run(detect_signals())
```

### DP Structure Analysis
```python
import asyncio
from core.filters.dp_aware_signal_filter import DPAwareSignalFilter

async def analyze_dp_structure():
    filter = DPAwareSignalFilter()
    structure = await filter.analyze_dp_structure('SPY')
    
    print(f"Support Levels: {len(structure.dp_support_levels)}")
    print(f"Resistance Levels: {len(structure.dp_resistance_levels)}")
    print(f"Battlegrounds: {len(structure.institutional_battlegrounds)}")
    print(f"DP Strength: {structure.dp_strength_score:.2f}")

asyncio.run(analyze_dp_structure())
```

## 🎯 Performance

### Current Status
- **DP Data**: ✅ Real ChartExchange integration
- **Price Data**: ✅ Yahoo Direct (no rate limits)
- **Signal Detection**: ✅ Breakout/reversal logic
- **DP Filtering**: ✅ Institutional confirmation
- **Risk Management**: ✅ Multi-level risk assessment

### Test Results
```
✅ DP structure analyzed successfully
   Support levels: 56
   Resistance levels: 99  
   Battlegrounds: 5
   DP strength: 1.00

✅ Signals detected!
  1. BUY @ $664.39 - Risk: HIGH
```

## 🔮 Roadmap

### Phase 1: Core System ✅
- [x] DP data integration
- [x] Signal detection
- [x] DP filtering
- [x] Risk management

### Phase 2: Enhancement
- [ ] Multi-timeframe analysis
- [ ] Sector rotation detection
- [ ] Options flow integration
- [ ] News sentiment analysis

### Phase 3: Production
- [ ] Live trading integration
- [ ] Portfolio management
- [ ] Performance analytics
- [ ] Alert systems

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review log files for errors
3. Verify API configurations
4. Test with `tests/test_core_system.py`

---

**Built for institutional-grade market intelligence** 🚀