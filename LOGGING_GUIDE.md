# Lotto Machine Logging Guide

**Last Updated:** 2025-01-XX  
**Status:** Active System

---

## 📍 WHERE LOGS ARE WRITTEN

### **1. Console Output (Real-Time)**
**Location:** Terminal/STDOUT  
**Format:** Colored, human-readable  
**Level:** INFO (default)

**What You See:**
- Morning setup (screener results, volume profiles, gamma regime)
- Each monitoring cycle (symbol checks, signals generated)
- Signal alerts (formatted with emojis)
- Risk checks and price action confirmations
- End of day report

**Example:**
```
🎰 LOTTO MACHINE RUNNING
================================================================================
Symbols: QQQ, SPY
Check interval: 60s
Market hours: 09:30 - 16:00
================================================================================

📊 Checking SPY...
   Current price: $662.45
   ✅ Volume profile: High liquidity period (10:00)
   DP battlegrounds: 3
   Institutional buying: 65%
   🎯 MASTER SIGNAL: SPY
   Action: BUY @ $662.45
   ...
```

---

### **2. CSV Signal Log (Audit Trail)**
**Location:** `logs/live_monitoring/signals.csv`  
**Format:** CSV (comma-separated)  
**Updated:** Every time a signal is generated

**Columns:**
- `timestamp` - When signal was generated
- `symbol` - Ticker (SPY, QQQ, etc.)
- `action` - BUY or SELL
- `signal_type` - SQUEEZE, GAMMA_RAMP, BREAKOUT, BOUNCE
- `current_price` - Price when signal fired
- `entry_price` - Recommended entry
- `stop_loss` - Stop loss level
- `take_profit` - Target price
- `confidence` - Confidence score (0-1)
- `risk_reward` - Risk/reward ratio
- `position_pct` - Position size (% of account)
- `dp_level` - Dark pool level
- `institutional_score` - Institutional buying pressure
- `is_master` - True if 75%+ confidence
- `primary_reason` - Why signal was generated
- `supporting_factors` - Additional context

**View Live:**
```bash
# Watch signals in real-time
tail -f logs/live_monitoring/signals.csv

# View all signals
cat logs/live_monitoring/signals.csv

# Count signals today
grep "$(date +%Y-%m-%d)" logs/live_monitoring/signals.csv | wc -l
```

---

### **3. Python Logging (If Configured)**
**Location:** Currently console only (no file handler)  
**Format:** Standard Python logging  
**Level:** INFO

**To Add File Logging:**
```python
# In run_lotto_machine.py, modify:
import logging
from logging.handlers import RotatingFileHandler

# Add file handler
log_file = Path("logs/live_monitoring/lotto_machine.log")
log_file.parent.mkdir(parents=True, exist_ok=True)
file_handler = RotatingFileHandler(
    log_file, maxBytes=10*1024*1024, backupCount=5
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logging.getLogger().addHandler(file_handler)
```

---

## 📊 LOGGING CONFIGURATION

### **Current Setup:**
```python
# run_lotto_machine.py (line 57-60)
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
```

### **Alert Channels:**
- ✅ **Console** - Enabled (real-time output)
- ✅ **CSV** - Enabled (`logs/live_monitoring/signals.csv`)
- ❌ **Slack** - Disabled (set `slack_enabled=True` to enable)
- ❌ **Email** - Disabled

---

## 🔍 HOW TO MONITOR LIVE

### **Option 1: Watch Console Output**
```bash
python3 run_lotto_machine.py
```
- See everything in real-time
- Colored output with emojis
- Best for active monitoring

### **Option 2: Watch CSV File**
```bash
# Terminal 1: Run lotto machine
python3 run_lotto_machine.py > /dev/null 2>&1 &

# Terminal 2: Watch signals
watch -n 1 'tail -20 logs/live_monitoring/signals.csv'
```

### **Option 3: Tail CSV File**
```bash
# Run in background
python3 run_lotto_machine.py &

# Watch signals
tail -f logs/live_monitoring/signals.csv
```

### **Option 4: Parse CSV with Script**
```python
import pandas as pd
import time

while True:
    df = pd.read_csv('logs/live_monitoring/signals.csv')
    latest = df.tail(5)
    print(latest[['timestamp', 'symbol', 'signal_type', 'confidence', 'is_master']])
    time.sleep(60)
```

---

## 📁 LOG FILE LOCATIONS

### **Primary Logs:**
- `logs/live_monitoring/signals.csv` - All signals (CSV)
- Console output - Real-time monitoring

### **Other Logs (if file logging enabled):**
- `logs/live_monitoring/lotto_machine.log` - Full system log (if configured)
- `logs/backtest/` - Backtest results
- `cache/` - Cached institutional data

---

## 🎯 WHAT GETS LOGGED

### **Always Logged:**
- ✅ All signals (master + high confidence)
- ✅ Signal details (price, confidence, R/R)
- ✅ Timestamp of generation

### **Not Logged (by default):**
- ❌ Rejected signals (too noisy)
- ❌ Debug messages (set level=DEBUG to see)
- ❌ API errors (handled gracefully, not logged)

### **To Log Rejected Signals:**
```python
# In monitoring_config.py
ALERTS.alert_on_rejections = True
```

---

## 🔧 CONFIGURATION

### **Log Directory:**
```python
# live_monitoring/config/monitoring_config.py
MONITORING.log_dir = "logs/live_monitoring"
```

### **CSV File:**
```python
# live_monitoring/config/monitoring_config.py
ALERTS.csv_file = "logs/live_monitoring/signals.csv"
```

### **Log Level:**
```python
# live_monitoring/config/monitoring_config.py
MONITORING.log_level = "INFO"  # DEBUG, INFO, WARNING, ERROR
```

---

## 📊 EXAMPLE LOG OUTPUT

### **Console (Real-Time):**
```
================================================================================
CYCLE 1 - 2025-01-XX 11:45:00
================================================================================

📊 Checking SPY...
   Current price: $662.45
   ✅ Volume profile: High liquidity period (10:00)
   DP battlegrounds: 3
   Institutional buying: 65%
   Squeeze potential: 0%
   Gamma pressure: 15%

🎯 MASTER SIGNAL: SPY
Action: BUY @ $662.45
Type: BREAKOUT
Confidence: 87%
Entry: $662.45 | Stop: $661.50 | Target: $664.40
R/R: 1:2.0 | Position: 2.0%
Reasoning: BREAKOUT above institutional resistance $662.00 (2.5M shares)
```

### **CSV (signals.csv):**
```csv
timestamp,symbol,action,signal_type,current_price,entry_price,stop_loss,take_profit,confidence,risk_reward,position_pct,dp_level,institutional_score,is_master,primary_reason,supporting_factors
2025-01-XX 11:45:00,SPY,BUY,BREAKOUT,662.45,662.45,661.50,664.40,0.87,2.00,0.020,662.00,0.65,True,BREAKOUT above institutional resistance $662.00 (2.5M shares),"Volume 2.3x avg | Momentum +0.65% | Regime UPTREND"
```

---

## 🚀 QUICK COMMANDS

### **View Latest Signals:**
```bash
tail -20 logs/live_monitoring/signals.csv
```

### **Count Signals Today:**
```bash
grep "$(date +%Y-%m-%d)" logs/live_monitoring/signals.csv | wc -l
```

### **Watch Live:**
```bash
tail -f logs/live_monitoring/signals.csv
```

### **Filter Master Signals Only:**
```bash
grep "True" logs/live_monitoring/signals.csv
```

### **View by Symbol:**
```bash
grep "SPY" logs/live_monitoring/signals.csv
```

---

## 📝 SUMMARY

**Where to Look:**
1. **Console** - Real-time output (if running in foreground)
2. **`logs/live_monitoring/signals.csv`** - All signals (CSV format)
3. **Background process** - Check with `ps aux | grep lotto_machine`

**What's Logged:**
- ✅ All generated signals (with full details)
- ✅ Signal timestamps
- ✅ Confidence scores
- ✅ Risk/reward ratios

**What's NOT Logged:**
- ❌ Rejected signals (unless `alert_on_rejections=True`)
- ❌ Debug messages (unless `log_level=DEBUG`)

---

**STATUS: Logging to console + CSV file** ✅

