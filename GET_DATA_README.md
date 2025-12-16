# 🔥 GET EXPLOITATION DATA - Simple Script

## Purpose

Just fetch the data we need from ChartExchange APIs using our existing client.
NO TESTS - JUST GET THE DATA.

## Usage

```bash
# Set API key
export CHARTEXCHANGE_API_KEY='your_key_here'

# Run data fetcher
python3 tests/exploitation/test_get_exploitation_data.py
```

## What It Does

Uses `UltimateChartExchangeClient` to fetch:

**Phase 1 (Short Squeeze):**
- Short Interest
- Short Interest Daily
- Borrow Fee (IB)
- Failure to Deliver

**Phase 2 (Options Flow):**
- Options Chain Summary (max pain, P/C ratio)

**Phase 3 (Scanner):**
- Stock Screener (high short interest filter)

**Phase 5 (Reddit):**
- Reddit Mentions (daily)

## Output

- Console: Shows what data was fetched
- `exploitation_data.json`: All data saved to JSON

## What's Missing?

If any endpoints fail, the script will tell you what methods need to be added to `UltimateChartExchangeClient`.

