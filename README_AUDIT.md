# Production Signal Audit System

## Overview

The audit system checks what **SHOULD** have triggered by calling live APIs, not just reading stored signals.

## Design Philosophy

❌ **WRONG APPROACH**: Read database to see what we stored
```python
# This only shows what we already know
signals = load_from_database(date)
```

✅ **RIGHT APPROACH**: Call APIs to see what exists in the market
```python
# This shows what opportunities existed
dp_levels = client.get_darkpool_levels(symbol)
short_data = client.get_short_interest(symbol)
reddit_mentions = client.get_reddit_mentions(symbol)
# Then run signal generators to see what SHOULD trigger
```

## Why This Matters

1. **Find Missed Opportunities**: What existed but we didn't detect?
2. **Validate System Health**: Is our monitoring catching everything?
3. **Tune Thresholds**: Are we being too strict/loose?
4. **Real-time Intelligence**: What's happening RIGHT NOW?

## Usage

```bash
# Audit today's market
python3 run_production_audit.py

# Audit specific date
python3 run_production_audit.py 2025-12-17

# Audit specific symbols
python3 run_production_audit.py --symbols TSLA NVDA AAPL

# Full audit (all modules)
python3 run_production_audit.py --symbols SPY QQQ TSLA NVDA
```

## What Gets Audited

### 1. Dark Pool Intelligence
- DP levels (support/resistance battlegrounds)
- DP print volume (institutional flow)
- Proximity to key levels
- Should we have signaled a breakout/bounce?

### 2. Short Interest
- Current short interest %
- Squeeze potential
- Borrow fees
- Should we have flagged a squeeze setup?

### 3. Reddit Sentiment
- Mention velocity (is it hot?)
- Sentiment score
- Pump/dump risk
- Should we have generated a Reddit signal?

### 4. Gamma Exposure
- Max pain levels
- Dealer positioning
- Pin risk
- Should we have flagged a gamma ramp?

## Output

The audit produces:
1. **Market State**: What exists RIGHT NOW
2. **Signals That Should Exist**: Based on current data
3. **Comparison**: What we generated vs what we should have
4. **Recommendations**: Tune thresholds, fix bugs, etc.

## Integration with Backtesting

This is **different** from backtesting:
- **Backtesting**: Run historical data through signal generators
- **Auditing**: Check if live system caught everything it should have

Both are needed for a complete validation system.

## Files

- `run_production_audit.py` - Main audit script (API-based)
- `backtesting/analysis/reddit_signal_analyzer.py` - Analyze stored Reddit signals
- `backtesting/reports/reddit_signal_report.py` - Generate reports from stored data

## Requirements

- `CHARTEXCHANGE_API_KEY` environment variable
- Tier 3 ChartExchange subscription (for full DP/Reddit data)
- Internet connection (calls live APIs)

## Examples

**Example 1: Find Missed Squeeze**
```
🔥 AUDITING SHORT INTEREST...
📊 TSLA:
   Short Interest: 18.5%
   🔥 SQUEEZE POTENTIAL - High short interest!
   
🎯 SIGNALS THAT SHOULD EXIST:
   Squeeze: 1 (TSLA at $489.88)
   
⚠️  BUT WE DIDN'T GENERATE IT - WHY?
   → Check squeeze detector thresholds
   → Validate data was available at the time
```

**Example 2: Validate Reddit Signal**
```
📱 AUDITING REDDIT SENTIMENT...
📊 TSLA:
   Velocity: 9.2x
   Sentiment: +0.08
   🚨 HOT TICKER - High mention velocity!
   
✅ WE DID GENERATE A SIGNAL (CONFIRMED_MOMENTUM)
   → System working correctly
```

