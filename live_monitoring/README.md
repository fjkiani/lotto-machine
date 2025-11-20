# Live Signal Monitoring System

**Production-grade, modular signal monitoring for SPY/QQQ institutional intelligence.**

## 🎯 Features

- ✅ **Real-time monitoring** during RTH (9:30 AM - 4:00 PM ET)
- ✅ **Multi-factor signal generation** (DP + short + options + gamma)
- ✅ **Master signal filtering** (75%+ confidence threshold)
- ✅ **Multi-channel alerts** (Console, CSV, Slack)
- ✅ **Modular architecture** (easy to extend)
- ✅ **Production-grade logging** (full audit trail)
- ✅ **Intelligent caching** (fallback when API rate-limited)

---

## 📁 Architecture

```
live_monitoring/
├── core/
│   ├── data_fetcher.py          # Data acquisition with caching
│   ├── signal_generator.py      # Signal generation logic
│   └── risk_manager.py          # (Future) Risk management
│
├── alerting/
│   ├── alert_router.py          # Route to multiple channels
│   ├── console_alerter.py       # Beautiful terminal output
│   ├── csv_logger.py            # Audit trail
│   └── slack_alerter.py         # Slack webhook integration
│
├── monitoring/
│   ├── live_monitor.py          # Main orchestrator
│   └── position_tracker.py      # (Future) Track open positions
│
└── config/
    └── monitoring_config.py      # All settings centralized
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure (Optional)
Edit `live_monitoring/config/monitoring_config.py`:
- Set your Slack webhook URL (if using Slack)
- Adjust monitoring intervals
- Modify risk parameters

### 3. Run
```bash
python3 run_live_monitor.py
```

---

## ⚙️ Configuration

### Trading Parameters
```python
symbols = ["SPY", "QQQ"]            # Universe
max_position_size_pct = 0.02        # 2% per trade
max_daily_drawdown_pct = 0.05       # 5% daily limit
min_master_confidence = 0.75        # 75%+ for master signals
```

### Monitoring Settings
```python
market_open_hour = 9
market_open_minute = 30
market_close_hour = 16
market_close_minute = 0
check_interval_seconds = 60          # Check every 1 minute
```

### Alert Channels
```python
console_enabled = True               # Terminal output
csv_enabled = True                   # CSV audit log
slack_enabled = False                # Slack (set webhook first)
```

---

## 📊 Signal Types

### 1. SQUEEZE Signal
**Criteria:**
- Short interest >15%
- Borrow fee >5%
- At DP support
- High buying pressure

**Target:** 3:1 R/R

### 2. GAMMA_RAMP Signal
**Criteria:**
- P/C ratio <0.8
- High call OI
- Max pain above price
- At DP support

**Target:** Max pain level

### 3. BREAKOUT Signal
**Criteria:**
- Clean break above DP resistance
- Volume >2x average
- Strong momentum
- Institutional buying

**Target:** Next DP resistance

### 4. BOUNCE Signal
**Criteria:**
- At DP battleground support
- Volume spike
- Reversal momentum
- Institutional buying

**Target:** 2:1 R/R

---

## 📝 Output Examples

### Console Alert
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

### CSV Log
```csv
timestamp,symbol,action,signal_type,current_price,entry_price,stop_loss,take_profit,confidence,risk_reward,position_pct,dp_level,institutional_score,is_master,primary_reason,supporting_factors
2025-10-18 10:30:00,SPY,BUY,BREAKOUT,665.20,665.20,664.50,666.60,0.87,2.0,0.02,665.00,0.82,True,BREAKOUT above institutional resistance $665.00 (2.5M shares),Volume 2.3x avg | Momentum +0.65% | Regime UPTREND
```

---

## 🔧 Extending the System

### Add a New Alert Channel
1. Create new alerter in `alerting/`:
```python
class EmailAlerter:
    def alert_signal(self, signal: LiveSignal):
        # Send email
        pass
```

2. Register in `monitoring/live_monitor.py`:
```python
if config.ALERTS.email_enabled:
    self.alert_router.add_alerter(EmailAlerter())
```

### Add Custom Signal Logic
Edit `core/signal_generator.py`:
```python
def _create_custom_signal(self, symbol, price, context):
    # Your logic here
    return LiveSignal(...)
```

---

## 📈 Performance Tracking

All signals are logged to CSV for analysis:
```bash
# View signals
cat logs/live_monitoring/signals.csv

# Count by type
cut -d',' -f4 logs/live_monitoring/signals.csv | sort | uniq -c

# Master signals only
grep "True" logs/live_monitoring/signals.csv
```

---

## ⚠️ Important Notes

1. **Market Hours Only**: System automatically pauses outside RTH
2. **API Rate Limits**: Uses caching to avoid hitting ChartExchange limits
3. **No Auto-Execution**: Signals are alerts only - YOU decide when to trade
4. **Paper Trade First**: Run for 20+ signals before using real capital

---

## 🐛 Troubleshooting

### "Could not load ChartExchange API key"
- Ensure `configs/chartexchange_config.py` exists with your API key

### "Could not fetch institutional context"
- Check API key validity
- Check internet connection
- System will use cached data as fallback

### "No signals generated"
- This is NORMAL - most cycles will have no signals
- High-quality signals are rare (5-10 per day expected)

### Slack not working
- Set `slack_webhook_url` in config
- Set `slack_enabled = True`
- Test webhook with: `curl -X POST $WEBHOOK_URL -d '{"text":"test"}'`

---

## 📊 Expected Signal Frequency

**SPY + QQQ combined:**
- Master signals (75%+): 3-5 per day
- High confidence (60-74%): 5-10 per day
- Total actionable: 8-15 per day

**Most cycles (>90%) will generate NO signals - this is correct behavior!**

---

## 🔐 Security

- API keys stored locally only
- No data sent to external services (except configured alerts)
- All signals logged locally for audit

---

## 📜 License

Part of AI Hedge Fund project - see main README

---

**REMEMBER:** *"A mediocre signal is worse than no signal. Every alert from this system has been rigorously filtered."*



