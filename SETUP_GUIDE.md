# Setup Guide

## 🚀 Quick Setup

### 1. Prerequisites
```bash
# Python 3.9+
python3 --version

# Required packages
pip install requests numpy yfinance
```

### 2. Configuration
```bash
# Create config file
cp configs/chartexchange_config.py.example configs/chartexchange_config.py

# Edit with your API key
nano configs/chartexchange_config.py
```

### 3. Test Installation
```bash
# Run core system test
python3 tests/test_core_system.py
```

## 📋 Detailed Setup

### Step 1: Clone Repository
```bash
git clone <repository-url>
cd ai-hedge-fund-main
```

### Step 2: Install Dependencies
```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### Step 3: Configure APIs

#### ChartExchange API
1. Sign up at [ChartExchange](https://chartexchange.com)
2. Get your API key
3. Update `configs/chartexchange_config.py`:
```python
CHARTEXCHANGE_API_KEY = "your_api_key_here"
CHARTEXCHANGE_TIER = 3  # Your tier level
```

#### Yahoo Direct (No setup required)
- Uses direct scraping, no API key needed
- No rate limits

### Step 4: Verify Installation
```bash
# Test ChartExchange API
python3 tests/test_chartexchange_api.py

# Test DP filter
python3 tests/test_dp_filter.py

# Test full system
python3 tests/test_core_system.py
```

## 🔧 Configuration Options

### DP Filter Settings
Edit `core/filters/dp_aware_signal_filter.py`:
```python
# DP structure thresholds
self.dp_support_threshold = 0.7      # 70% of volume at support
self.dp_resistance_threshold = 0.7    # 70% of volume at resistance
self.battleground_threshold = 0.8     # 80% institutional ratio
self.breakout_confirmation_threshold = 0.25  # 25% above magnet
self.mean_reversion_threshold = 0.15  # 15% below DP support

# Signal tightening parameters
self.min_dp_agreement = 0.3          # Minimum DP agreement
self.min_composite_confidence = 0.75 # Composite signal confidence
self.max_risk_level = "MEDIUM"       # Maximum risk level
```

### Detection Windows
Edit `core/core_signals_runner.py`:
```python
# Rolling window sizes (minutes)
WINDOWS = [5, 10, 20, 30]

# Breakout thresholds (%)
BREAKOUT_THRESHOLDS = [0.2, 0.5, 1.0, 1.5]

# Volume multipliers
VOLUME_MULTIPLIERS = [1.5, 2.0, 2.5, 3.0]
```

## 🎯 Running the System

### Live Signals (RTH Only)
```bash
# Run during market hours (09:30-16:00 ET)
python3 core/core_signals_runner.py
```

### Replay Session
```bash
# Replay today's session
python3 core/replay_intraday_spy.py
```

### Demo Mode
```bash
# Run demos
python3 demos/demo_enhanced_analysis.py
python3 demos/demo_intelligence_system.py
```

## 📊 Monitoring

### Log Files
```bash
# View signal logs
tail -f logs/core_signals.csv

# View detailed logs
tail -f logs/core_signals.jsonl

# View errors
tail -f logs/errors.log
```

### Performance Metrics
```bash
# Check system performance
python3 tests/test_performance.py
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
# Error: ModuleNotFoundError
# Solution: Check Python path and folder structure
export PYTHONPATH="${PYTHONPATH}:$(pwd)/core"
```

#### 2. API Errors
```bash
# Error: ChartExchange API failed
# Solution: Check API key and tier
python3 tests/test_chartexchange_api.py
```

#### 3. No Signals
```bash
# Error: No signals detected
# Solution: Check DP agreement thresholds
# Lower min_dp_agreement for testing
```

#### 4. Rate Limits
```bash
# Error: Rate limit exceeded
# Solution: Check API tier limits
# Upgrade tier or reduce request frequency
```

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Verbose Logging
```bash
# Run with debug logging
PYTHONPATH=. python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from core.core_signals_runner import main
main()
"
```

## 🔒 Security

### API Key Protection
```bash
# Don't commit API keys
echo "configs/chartexchange_config.py" >> .gitignore

# Use environment variables
export CHARTEXCHANGE_API_KEY="your_key_here"
```

### Rate Limiting
```python
# Built-in rate limiting
# ChartExchange: Automatic based on tier
# Yahoo Direct: No limits
```

## 📈 Performance Optimization

### Caching
```python
# Enable caching for repeated requests
# Built into ChartExchange API client
```

### Parallel Processing
```python
# Run multiple tickers in parallel
tickers = ["SPY", "QQQ", "AAPL"]
await asyncio.gather(*[
    filter_signals_with_dp_confirmation(ticker) 
    for ticker in tickers
])
```

### Memory Management
```python
# Clear old data periodically
# Built into system
```

## 🧪 Testing

### Unit Tests
```bash
# Run all tests
python3 -m pytest tests/

# Run specific test
python3 tests/test_core_system.py
```

### Integration Tests
```bash
# Test API integration
python3 tests/test_chartexchange_integration.py

# Test DP filter
python3 tests/test_dp_filter_integration.py
```

### Performance Tests
```bash
# Test system performance
python3 tests/test_performance.py
```

## 📚 Documentation

### API Reference
- See `API_REFERENCE.md` for detailed API documentation

### Code Examples
- See `demos/` folder for usage examples

### Troubleshooting
- See main `README.md` for common issues

## 🆘 Support

### Getting Help
1. Check troubleshooting section
2. Review log files
3. Run test scripts
4. Check API status

### Reporting Issues
1. Include error logs
2. Specify configuration
3. Describe steps to reproduce
4. Include system information

---

**Ready to detect institutional breakouts!** 🚀


