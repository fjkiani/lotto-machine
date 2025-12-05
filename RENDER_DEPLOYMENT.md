# 🚀 DEPLOY TO RENDER.COM - COMPLETE GUIDE

## Quick Deploy (5 Minutes)

### Step 1: Push to GitHub

```bash
# Make sure your code is on GitHub
git add .
git commit -m "Add production monitor for Render deployment"
git push origin main
```

### Step 2: Create Render Account

1. Go to [render.com](https://render.com)
2. Sign up with GitHub (easiest)
3. Authorize Render to access your repos

### Step 3: Create Background Worker

1. In Render dashboard, click **"New +"** → **"Background Worker"**
2. Connect your GitHub repo (`ai-hedge-fund-main`)
3. Configure:

**Basic Settings:**
- **Name:** `alpha-signal-monitor`
- **Environment:** `Python 3`
- **Region:** Choose closest to you (US East recommended)
- **Branch:** `main`
- **Root Directory:** Leave empty (or `.` if needed)
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python3 run_production_monitor.py`

**Environment Variables:**
Click **"Add Environment Variable"** and add:

```
DISCORD_WEBHOOK_URL = https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
CHARTEXCHANGE_API_KEY = your_chartexchange_api_key
```

**Plan:**
- Start with **Free** tier (750 hours/month)
- Upgrade to **Starter** ($7/month) if you need more uptime

### Step 4: Deploy!

Click **"Create Background Worker"** and Render will:
1. Clone your repo
2. Install dependencies
3. Start the monitor
4. Keep it running 24/7

---

## Alternative: Use render.yaml (Infrastructure as Code)

If you prefer, you can use the `render.yaml` file I created:

1. In Render dashboard, click **"New +"** → **"Blueprint"**
2. Connect your GitHub repo
3. Render will detect `render.yaml` and create the service
4. **Still need to set environment variables in dashboard!**

---

## Verify It's Working

### Check Logs

1. In Render dashboard, click on your service
2. Go to **"Logs"** tab
3. You should see:
   ```
   🚀 PRODUCTION SIGNAL MONITOR STARTING
   ✅ Discord webhook: Configured
   📊 Checking SPY...
   ```

### Test Discord

1. Wait for market hours (9:30 AM - 4:00 PM ET)
2. Check your Discord channel
3. You should receive signals when they're generated

---

## Monitoring & Maintenance

### View Logs

Render dashboard → Your service → **Logs** tab

### Restart Service

Render dashboard → Your service → **Manual Deploy** → **Clear build cache & deploy**

### Update Code

Just push to GitHub - Render auto-deploys (if enabled):
- Settings → **Auto-Deploy** → Enable

---

## Cost

**Free Tier:**
- 750 hours/month (enough for 24/7 for ~30 days)
- Perfect for testing

**Starter Plan ($7/month):**
- Unlimited hours
- Better performance
- Recommended for production

---

## Troubleshooting

### "Service keeps crashing"

**Check logs:**
1. Render dashboard → Logs
2. Look for error messages
3. Common issues:
   - Missing environment variables
   - API rate limits
   - Import errors

**Fix:**
```bash
# Test locally first
export DISCORD_WEBHOOK_URL="your_webhook"
export CHARTEXCHANGE_API_KEY="your_key"
python3 run_production_monitor.py
```

### "No signals being sent"

**Check:**
1. Is it market hours? (9:30 AM - 4:00 PM ET, weekdays)
2. Check logs for "No signals generated" (this is normal)
3. Verify Discord webhook URL is correct

### "Service stopped"

**Free tier limits:**
- Service sleeps after 15 min inactivity
- Upgrade to Starter for always-on

**Solution:**
- Upgrade to Starter ($7/month)
- Or use a health check endpoint (future enhancement)

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_WEBHOOK_URL` | ✅ Yes | Discord webhook URL |
| `CHARTEXCHANGE_API_KEY` | ✅ Yes | ChartExchange API key |

**How to set:**
1. Render dashboard → Your service
2. **Environment** tab
3. Click **"Add Environment Variable"**
4. Enter key and value
5. Click **"Save Changes"**
6. Service will auto-restart

---

## Next Steps

1. ✅ Deploy to Render
2. ✅ Test during market hours
3. ✅ Monitor logs for 1 week
4. ✅ Track signal performance
5. ✅ Adjust thresholds if needed

---

## Support

- Render Docs: https://render.com/docs
- Render Status: https://status.render.com
- Your logs: Render dashboard → Logs tab

**Questions?** Check the logs first - they're very detailed!

