# 🚀 PRODUCTION MONITOR SETUP GUIDE

## Quick Start

### 1. Get Discord Webhook URL

1. Open Discord → Your Server
2. Go to **Server Settings** → **Integrations** → **Webhooks**
3. Click **New Webhook**
4. Name it "Alpha Intelligence" (or whatever you want)
5. Choose the channel where you want signals
6. Click **Copy Webhook URL**

### 2. Set Environment Variable

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_URL_HERE"
```

Or add to your `.env` file:
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL_HERE
```

### 3. Run the Monitor

```bash
python3 run_production_monitor.py
```

The monitor will:
- ✅ Run continuously during market hours (9:30 AM - 4:00 PM ET)
- ✅ Check SPY and QQQ every 60 seconds
- ✅ Send signals to Discord (50%+ confidence)
- ✅ Log all signals to `logs/production/signals.csv`
- ✅ Track performance in `logs/production/performance_YYYYMMDD.json`
- ✅ Auto-restart on errors
- ✅ Send daily summary at market close

---

## What You'll See

### Discord Notifications

**Master Signal (75%+ confidence):**
```
🎯 MASTER SIGNAL: SPY
Action: BUY BOUNCE
Confidence: 87%
Entry: $680.57 | Stop: $677.87 | Target: $685.97
Risk/Reward: 1:2.0
```

**High Confidence Signal (50-74%):**
```
📊 HIGH CONFIDENCE SIGNAL: QQQ
Action: BUY BREAKOUT
Confidence: 62%
Entry: $512.30 | Stop: $510.50 | Target: $516.10
Risk/Reward: 1:2.1
```

### Log Files

**Signals Log** (`logs/production/signals.csv`):
- Every signal with timestamp, price, confidence, outcome

**Performance Log** (`logs/production/performance_YYYYMMDD.json`):
- Daily stats: total signals, master signals, win rate

**Monitor Log** (`logs/production/monitor_YYYYMMDD.log`):
- Detailed execution log for debugging

---

## Running in Background

### Using `screen` (recommended):

```bash
# Start a screen session
screen -S alpha_monitor

# Run the monitor
python3 run_production_monitor.py

# Detach: Press Ctrl+A, then D
# Reattach: screen -r alpha_monitor
```

### Using `nohup`:

```bash
nohup python3 run_production_monitor.py > monitor.out 2>&1 &
```

### Using `systemd` (Linux):

Create `/etc/systemd/system/alpha-monitor.service`:

```ini
[Unit]
Description=Alpha Intelligence Signal Monitor
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/ai-hedge-fund-main
Environment="DISCORD_WEBHOOK_URL=your_webhook_url"
ExecStart=/usr/bin/python3 /path/to/ai-hedge-fund-main/run_production_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable alpha-monitor
sudo systemctl start alpha-monitor
sudo systemctl status alpha-monitor
```

---

## Monitoring Performance

### Check Today's Signals

```bash
# View today's performance
cat logs/production/performance_$(date +%Y%m%d).json | jq

# Count signals today
grep -c "$(date +%Y-%m-%d)" logs/production/signals.csv

# View all signals
tail -f logs/production/signals.csv
```

### Track Win Rate

The system logs all signals. After a week, you can analyze:

```python
import pandas as pd
import json

# Load signals
df = pd.read_csv('logs/production/signals.csv')

# Filter to closed trades (you'll need to add outcome tracking)
# For now, signals are just logged - you can manually track outcomes
```

---

## Troubleshooting

### "DISCORD_WEBHOOK_URL not set"
- Make sure you exported the environment variable
- Or add it to `.env` file

### "Could not fetch price"
- Check internet connection
- Check if market is open
- yfinance might be rate-limited (wait a minute)

### "Could not fetch institutional context"
- ChartExchange API might be rate-limited
- Check API key in `configs/chartexchange_config.py`
- Wait for rate limit to reset

### Monitor keeps crashing
- Check `logs/production/monitor_*.log` for errors
- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Check API keys are valid

---

## Configuration

Edit `run_production_monitor.py` to change:

- **Symbols**: Change `symbols = ["SPY", "QQQ"]` to add more
- **Check Interval**: Change `check_interval = 60` (seconds)
- **Confidence Threshold**: Already set to 50% (validated!)

---

## Next Steps

1. ✅ Run for 1 week to collect data
2. ✅ Track which signals win/lose
3. ✅ Adjust thresholds based on results
4. ✅ Scale up to live trading if profitable

---

**Questions?** Check the logs first, then review the code in `run_production_monitor.py`

