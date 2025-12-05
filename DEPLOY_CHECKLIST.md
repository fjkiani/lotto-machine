# ✅ RENDER DEPLOYMENT CHECKLIST

## Pre-Deployment

- [ ] Code is pushed to GitHub
- [ ] Discord webhook URL ready
- [ ] ChartExchange API key ready

## Render Setup (5 Minutes)

### 1. Create Account
- [ ] Go to [render.com](https://render.com)
- [ ] Sign up with GitHub
- [ ] Authorize Render access

### 2. Create Background Worker
- [ ] Click **"New +"** → **"Background Worker"**
- [ ] Connect GitHub repo: `ai-hedge-fund-main`
- [ ] Configure:

**Settings:**
- [ ] Name: `alpha-signal-monitor`
- [ ] Environment: `Python 3`
- [ ] Region: `US East` (or closest)
- [ ] Branch: `main`
- [ ] Build Command: `pip install -r requirements.txt`
- [ ] Start Command: `python3 run_production_monitor.py`

**Environment Variables:**
- [ ] `DISCORD_WEBHOOK_URL` = `https://discord.com/api/webhooks/YOUR_URL`
- [ ] `CHARTEXCHANGE_API_KEY` = `your_api_key_here`

**Plan:**
- [ ] Start with **Free** (750 hours/month)
- [ ] Upgrade to **Starter** ($7/month) for 24/7 uptime

### 3. Deploy
- [ ] Click **"Create Background Worker"**
- [ ] Wait for build to complete (~2-3 minutes)
- [ ] Check logs for: `🚀 PRODUCTION SIGNAL MONITOR STARTING`

## Verification

- [ ] Logs show: `✅ Discord webhook: Configured`
- [ ] Logs show: `📊 Checking SPY...`
- [ ] No errors in logs
- [ ] Test during market hours (9:30 AM - 4:00 PM ET)
- [ ] Receive Discord notification when signal generated

## Post-Deployment

- [ ] Monitor logs for first day
- [ ] Verify signals are being sent
- [ ] Check performance logs in Render
- [ ] Upgrade to Starter plan if needed (for 24/7)

---

**That's it! Your monitor is now running in the cloud! 🚀**

