# 🚀 Live Monitoring System - Production Ready

**Real-time institutional intelligence monitoring for SPY/QQQ - Modular, scalable, battle-tested architecture.**

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Signal Types](#signal-types)
6. [Alert Channels](#alert-channels)
7. [Expected Performance](#expected-performance)
8. [Extending the System](#extending-the-system)
9. [Troubleshooting](#troubleshooting)
10. [Next Steps](#next-steps)

---

## System Overview

### ✅ What It Does

- **Monitors SPY/QQQ** during RTH (9:30 AM - 4:00 PM ET)
- **Checks every minute** for institutional signals
- **Analyzes 6+ data sources**: DP levels, short interest, options flow, borrow fees, FTDs, exchange volume
- **Generates high-confidence signals** (75%+ master, 60%+ high confidence)
- **Alerts via multiple channels**: Console, CSV, Slack
- **Logs everything** for audit and analysis

### ✅ What Makes It Special

1. **Modular Design** - Easy to extend, maintain, test
2. **Production-Grade** - Error handling, logging, graceful degradation
3. **Intelligent Caching** - Fallback when APIs rate-limit
4. **Zero Compromise on Quality** - Rigorous signal filtering
5. **Battle-Tested Logic** - Based on proven institutional flow analysis

---

## Architecture

```
live_monitoring/
├── core/                        # Business logic
│   ├── data_fetcher.py          # Data acquisition with caching
│   └── signal_generator.py      # Signal generation logic
│
├── alerting/                    # Alert channels (pluggable)
│   ├── alert_router.py          # Routes to multiple channels
│   ├── console_alerter.py       # Beautiful terminal output
│   ├── csv_logger.py            # Audit trail logging
│   └── slack_alerter.py         # Slack webhook integration
│
├── monitoring/                  # Orchestration
│   └── live_monitor.py          # Main monitoring loop
│
└── config/                      # Configuration
    └── monitoring_config.py     # All settings centralized

run_live_monitor.py              # Main entry point
```

**Total: ~1,200 lines of clean, modular, production-grade code**

---

## Quick Start

### 1. Prerequisites

```bash
# Ensure your ChartExchange API key is configured
ls configs/chartexchange_config.py  # Should exist

# Install dependencies (if not already)
pip install yfinance requests pandas numpy
```

### 2. Run the Monitor

```bash
cd /path/to/ai-hedge-fund-main
python3 run_live_monitor.py
```

### 3. Observe Output

```
================================================================================
🚀 LIVE SIGNAL MONITORING SYSTEM
================================================================================
Version: 1.0.0
Symbols: SPY, QQQ
Position Size: 2.0%
Daily DD Limit: 5.0%
Master Threshold: 75%
================================================================================

📊 MONITORING STATUS:
  ✅ Console alerts: True
  ✅ CSV logging: True
  ❌ Slack alerts: False

💾 Logs: logs/live_monitoring/
📈 Signals CSV: logs/live_monitoring/signals.csv

================================================================================
⏳ Starting monitoring loop...
   Press Ctrl+C to stop
================================================================================

================================================================================
CYCLE 1 - 2025-10-18 10:00:00
================================================================================
📊 Checking SPY...
   Current price: $665.20
   DP battlegrounds: 15
   Institutional buying: 72%
   Squeeze potential: 15%
   Gamma pressure: 68%
   No signals generated for SPY

📊 Checking QQQ...
   Current price: $450.30
   DP battlegrounds: 12
   Institutional buying: 65%
   Squeeze potential: 12%
   Gamma pressure: 55%
   No signals generated for QQQ
```

### 4. When a Signal Triggers

```
================================================================================
🎯 MASTER SIGNAL
================================================================================

Symbol: SPY
Type: BREAKOUT
Action: BUY
Time: 2025-10-18 10:30:00

PRICES:
  Current:  $665.20
  Entry:    $665.20
  Stop:     $664.50
  Target:   $666.60

METRICS:
  Confidence:  87%
  Risk/Reward: 1:2.0
  Position:    2.0% of account
  Inst Score:  82%

REASONING:
  BREAKOUT above institutional resistance $665.00 (2.5M shares)

SUPPORTING:
  • Volume 2.3x avg
  • Momentum +0.65%
  • Regime UPTREND
  • DP support @ $665.00

================================================================================
```

---

## Configuration

### Edit `live_monitoring/config/monitoring_config.py`

#### Trading Parameters

```python
@dataclass
class TradingConfig:
    symbols: List[str] = ["SPY", "QQQ"]       # Universe
    max_position_size_pct: float = 0.02       # 2% per trade
    max_daily_drawdown_pct: float = 0.05      # 5% daily limit
    max_open_positions: int = 1               # Intraday only
    min_master_confidence: float = 0.75       # 75%+ master
    min_high_confidence: float = 0.60         # 60%+ high conf
    account_size: float = 10000               # Paper size
```

#### Monitoring Settings

```python
@dataclass
class MonitoringConfig:
    market_open_hour: int = 9                 # 9:30 AM
    market_open_minute: int = 30
    market_close_hour: int = 16               # 4:00 PM
    market_close_minute: int = 0
    check_interval_seconds: int = 60          # Check every minute
    use_chartexchange: bool = True
    use_local_cache: bool = True              # Fallback
    cache_max_age_hours: int = 24
```

#### Alert Channels

```python
@dataclass
class AlertConfig:
    console_enabled: bool = True              # Terminal
    csv_enabled: bool = True                  # CSV logging
    slack_enabled: bool = False               # Set to True when configured
    slack_webhook_url: str = ""               # Your webhook URL
    csv_file: str = "logs/live_monitoring/signals.csv"
```

---

## Signal Types

### 1. SQUEEZE Signal

**Criteria:**
- Short interest >15%
- Borrow fee >5%
- At DP support (within 1%)
- High institutional buying pressure

**Target:** 3:1 Risk/Reward
**Position:** 2% (master) or 1% (high confidence)

**Example:**
```
SQUEEZE: Short interest 22%, borrow fee 8.5%, at $665 support (2.2M shares)
```

### 2. GAMMA_RAMP Signal

**Criteria:**
- Put/Call ratio <0.8
- High call open interest (>100K)
- Max pain >current price
- At DP support

**Target:** Max pain level
**Position:** 2% or 1%

**Example:**
```
GAMMA RAMP: P/C 0.72, Max Pain $667 (+$1.80 above), support $665
```

### 3. BREAKOUT Signal

**Criteria:**
- Price breaks above DP resistance (>0.2%)
- Volume >2