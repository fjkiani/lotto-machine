# Alpha Intelligence Monitor - Deployment Guide

## Quick Start

### Manual Start/Stop
```bash
# Start monitor
./start_monitor.sh

# Check if running
./check_monitor.sh

# Stop monitor
./stop_monitor.sh
```

## Auto-Start Setup (macOS)

### 1. Install launchd service
```bash
# Copy plist to LaunchAgents
cp com.alpha.monitor.plist ~/Library/LaunchAgents/

# Load the service
launchctl load ~/Library/LaunchAgents/com.alpha.monitor.plist

# Check status
launchctl list | grep alpha
```

### 2. Verify it works
The monitor will auto-start at:
- **Monday-Friday at 9:25 AM** (5 minutes before market open)
- Automatically restarts if it crashes
- Logs to `logs/monitor/`

### 3. Manual control
```bash
# Start now (don't wait for scheduled time)
launchctl start com.alpha.monitor

# Stop
launchctl stop com.alpha.monitor

# Unload (disable auto-start)
launchctl unload ~/Library/LaunchAgents/com.alpha.monitor.plist

# Reload after changes
launchctl unload ~/Library/LaunchAgents/com.alpha.monitor.plist
launchctl load ~/Library/LaunchAgents/com.alpha.monitor.plist
```

## Health Checks

### Automated health check (run from cron)
```bash
# Add to crontab (runs every 15 minutes during RTH)
*/15 9-16 * * 1-5 /Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main/check_monitor.sh || /Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main/start_monitor.sh
```

To add:
```bash
crontab -e
```

Then paste:
```
# Alpha Intelligence Monitor health check
*/15 9-16 * * 1-5 /Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main/check_monitor.sh || /Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main/start_monitor.sh
```

## Logs

### View real-time logs
```bash
# Today's log
tail -f logs/monitor/monitor_$(date +%Y%m%d).log

# Launchd logs
tail -f logs/monitor/launchd.log
tail -f logs/monitor/launchd_error.log
```

### Log rotation
Logs are automatically rotated daily (YYYYMMDD format).

## Troubleshooting

### Monitor not starting
```bash
# Check if process is running
ps aux | grep run_all_monitors.py

# Check launchd status
launchctl list | grep alpha

# View error logs
cat logs/monitor/launchd_error.log
```

### Monitor crashed
```bash
# View today's log for errors
tail -100 logs/monitor/monitor_$(date +%Y%m%d).log

# Restart manually
./start_monitor.sh
```

### Environment variables not loaded
The `start_monitor.sh` script loads `.env` automatically. Verify:
```bash
# Check .env exists
ls -la .env

# Test loading
source .env && echo $CHARTEXCHANGE_API_KEY
```

## Production Checklist

- [ ] `.env` file exists with all API keys
- [ ] `start_monitor.sh` is executable (`chmod +x`)
- [ ] `stop_monitor.sh` is executable
- [ ] `check_monitor.sh` is executable
- [ ] `logs/monitor/` directory exists
- [ ] launchd plist is installed
- [ ] launchd service is loaded
- [ ] Health check cron job is set up
- [ ] Discord webhook is configured
- [ ] Test manual start/stop works
- [ ] Test auto-restart works (kill process and wait)

## What Runs When

### 9:25 AM (Mon-Fri)
- launchd starts monitor automatically
- Monitor loads environment variables
- Monitor starts all subsystems:
  - Fed Watch (every 30 min)
  - Trump Intel (every 3 min)
  - Economic AI (every 60 min)
  - Dark Pool (every 60 sec)
  - Synthesis (when 2+ alerts buffer)

### During RTH (9:30 AM - 4:00 PM)
- DP levels checked every 60 seconds
- Synthesis runs when confluence detected
- Alerts sent to Discord immediately
- All alerts logged to database
- Health check runs every 15 minutes

### After Market Close (4:00 PM+)
- Monitor continues Fed/Trump/Economic checks
- DP checks skipped (market closed)
- Synthesis checks skipped (market closed)

### Overnight
- Monitor keeps running (Fed/Trump checks only)
- DP/Synthesis silent until next RTH

## Emergency Stop
```bash
# If monitor is spamming or misbehaving
./stop_monitor.sh

# Or nuclear option
pkill -9 -f run_all_monitors.py
rm monitor.pid
```

## Post-Market Review
```bash
# View today's alerts
sqlite3 data/alerts_history.db "SELECT * FROM alerts WHERE DATE(timestamp) = DATE('now')"

# View today's DP interactions
sqlite3 data/dp_learning.db "SELECT * FROM dp_interactions WHERE DATE(timestamp) = DATE('now')"

# Count alerts by type
sqlite3 data/alerts_history.db "SELECT alert_type, COUNT(*) FROM alerts WHERE DATE(timestamp) = DATE('now') GROUP BY alert_type"
```

## System Requirements

- macOS (for launchd)
- Python 3.8+
- All dependencies installed (`pip install -r requirements.txt`)
- `.env` file with API keys
- Discord webhook URL configured

## Support

If monitor fails repeatedly:
1. Check logs for errors
2. Verify API keys are valid
3. Check network connectivity
4. Verify database files exist and are writable
5. Check Discord webhook URL is valid

Monitor should be 100% reliable now. No excuses.

