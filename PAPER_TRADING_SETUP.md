# 📊 LIVE PAPER TRADING SETUP GUIDE

## **🎯 What You're Getting:**

A **fully-automated, live paper trading system** that:
- ✅ Monitors SPY & QQQ in real-time during market hours
- ✅ Generates institutional + technical signals
- ✅ Executes paper trades automatically via Alpaca
- ✅ Manages positions with stop loss / take profit
- ✅ Logs every trade and P&L
- ✅ Sends alerts (console, CSV, Slack)

---

## **⚡ QUICK START (5 Minutes):**

### **Step 1: Get Alpaca Paper Trading Account (FREE)**

1. Go to: https://alpaca.markets/
2. Click "Sign Up" (top right)
3. Choose **"Paper Trading Account"** (no credit card needed!)
4. Verify your email
5. Log in to dashboard

### **Step 2: Get Your API Keys**

1. In Alpaca dashboard, click your name (top right)
2. Go to **"API Keys"**
3. Click **"Generate New Key"** for **Paper Trading**
4. **SAVE THESE** (you won't see them again!):
   - API Key ID: `PKxxxxxxxxxxxxxxxxxx`
   - Secret Key: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### **Step 3: Set Environment Variables**

**On Mac/Linux:**
```bash
export ALPACA_API_KEY='PKxxxxxxxxxxxxxxxxxx'
export ALPACA_SECRET_KEY='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
```

**On Windows (PowerShell):**
```powershell
$env:ALPACA_API_KEY='PKxxxxxxxxxxxxxxxxxx'
$env:ALPACA_SECRET_KEY='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
```

**Or add to `.env` file:**
```bash
# In project root, create .env file
echo "ALPACA_API_KEY=PKxxxxxxxxxxxxxxxxxx" >> .env
echo "ALPACA_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" >> .env
```

### **Step 4: Install Alpaca SDK**

```bash
pip install alpaca-py
```

### **Step 5: Test Connection**

```bash
python3 live_monitoring/trading/paper_trader.py
```

You should see:
```
✅ Alpaca Paper Trading connected
   Account: PA3XXXXXXXXXX
   Buying Power: $100,000.00
   Cash: $100,000.00
   Portfolio Value: $100,000.00
```

### **Step 6: RUN IT! 🚀**

```bash
python3 run_live_paper_trading.py
```

---

## **📋 What Happens Next:**

### **During Market Hours (9:30 AM - 4:00 PM ET):**

1. **Every 60 seconds:**
   - Fetches institutional data (DP, short interest, options)
   - Fetches technical data (price, volume, indicators)
   - Runs both strategies

2. **When MASTER SIGNAL detected (75%+ confidence):**
   - Automatically submits order to Alpaca
   - Sets stop loss and take profit
   - Logs trade to CSV

3. **Every 60 seconds (for open positions):**
   - Checks current price
   - If stop loss hit → closes position
   - If take profit hit → closes position
   - Updates P&L

4. **Every 15 minutes:**
   - Prints summary to console

### **Outside Market Hours:**
- System waits and checks every minute

### **When You Stop (Ctrl+C):**
- Prints final summary
- All trades logged to `logs/paper_trading/trades_YYYYMMDD.jsonl`

---

## **🎛️ Configuration:**

Edit `live_monitoring/config/monitoring_config.py`:

```python
# Trading parameters
MAX_POSITION_SIZE_PCT = 0.02  # 2% per trade
MAX_DAILY_DRAWDOWN_PCT = 0.05  # 5% max loss per day
MASTER_SIGNAL_CONFIDENCE_THRESHOLD = 0.75  # 75% min confidence

# Monitoring
POLLING_INTERVAL_SECONDS = 60  # Check every 60 seconds
SYMBOLS = ['SPY', 'QQQ']  # Which tickers to trade

# Market hours
RTH_START_HOUR = 9  # 9:30 AM ET (actual start is 9:30, but we use hour 9)
RTH_END_HOUR = 16    # 4:00 PM ET
```

---

## **📊 Monitoring Your Trades:**

### **Console Output:**
- Real-time alerts when signals fire
- Order confirmations
- Position updates
- P&L tracking

### **CSV Logs:**
- `logs/live_monitoring/signals.csv` - All signals
- `logs/paper_trading/trades_YYYYMMDD.jsonl` - All trades

### **Alpaca Dashboard:**
- Go to: https://app.alpaca.markets/paper/dashboard
- See all your paper trades in real-time!

---

## **⚠️ IMPORTANT NOTES:**

1. **This is PAPER TRADING** - No real money involved!
2. **Start small** - Watch it for a few days before trusting it
3. **Tune thresholds** - Adjust confidence levels based on performance
4. **Check logs daily** - Review what worked and what didn't
5. **Market conditions vary** - A good strategy isn't 100% win rate!

---

## **🔧 Troubleshooting:**

### **"Not connected to Alpaca"**
- Check API keys are set correctly
- Verify they're for **Paper Trading** (not live)
- Run test: `python3 live_monitoring/trading/paper_trader.py`

### **"No signals generated"**
- Normal! Strict 75% confidence threshold means few signals
- Lower threshold in config if needed (but expect more noise)
- Check data fetching is working (look for API errors in logs)

### **"Position already open"**
- System won't open duplicate positions
- Wait for current position to close (stop loss / take profit)

---

## **🎯 Next Steps After Running:**

1. **Watch for 1-2 days** - See what signals fire
2. **Review P&L** - Are we profitable?
3. **Tune parameters** - Adjust confidence, position size, etc.
4. **Add more signal types** - Expand technical strategies
5. **Scale up** - Add more tickers (but slowly!)

---

## **🚀 READY TO LAUNCH:**

```bash
# Make sure you're in project root
cd /path/to/ai-hedge-fund-main

# Set API keys (if not in .env)
export ALPACA_API_KEY='your_key'
export ALPACA_SECRET_KEY='your_secret'

# Install dependencies
pip install alpaca-py

# TEST IT
python3 live_monitoring/trading/paper_trader.py

# RUN IT (when market open)
python3 run_live_paper_trading.py
```

---

**🔥 LET'S MAKE SOME (PAPER) MONEY! 💰**



