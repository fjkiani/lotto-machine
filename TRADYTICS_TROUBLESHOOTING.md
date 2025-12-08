# 🔧 TRADYTICS WEBHOOK TROUBLESHOOTING GUIDE

## 🚨 **PROBLEM: No Alerts Received**

### **Step 1: Verify Webhook URLs Were Changed**

**Check if you actually replaced the URLs in Tradytics settings:**

1. Go to your Tradytics service/dashboard
2. Check webhook URL configuration
3. Verify it shows: `https://lotto-machine.onrender.com/tradytics-forward`
4. **NOT** the old Discord URLs like `https://discord.com/api/webhooks/...`

**If URLs weren't changed:**
- Tradytics is still sending directly to Discord
- Our system never receives the alerts
- **Solution:** Replace all 13 webhook URLs NOW

---

### **Step 2: Check System Configuration**

**Visit:** `https://lotto-machine.onrender.com/webhook-debug`

**Should show:**
```json
{
  "configuration": {
    "discord_webhook_url_set": true,
    "tradytics_ecosystem_available": true,
    "agents_loaded": 2,
    "synthesis_engine_ready": true
  }
}
```

**If `discord_webhook_url_set: false`:**
- ❌ `DISCORD_WEBHOOK_URL` environment variable not set
- **Fix:** Set it in Render Dashboard → Environment Variables

**If `tradytics_ecosystem_available: false`:**
- ❌ Tradytics agents failed to load
- **Fix:** Check Render logs for import errors

---

### **Step 3: Check Render Logs**

**Go to:** Render Dashboard → Your Service → Logs Tab

**Look for these messages:**

**✅ GOOD (System is receiving webhooks):**
```
📥 Received Tradytics webhook at /tradytics-forward: {"content":"..."}
📊 Parsed alert content: SPY Darkpool Signal...
🤖 Selected agent: DarkpoolAgent
📊 Agent processing result: success=True, confidence=100.0%
🧠 Synthesis generated: direction=bullish
✅ Forwarded Darkpool alert to Discord
✅ Synthesized analysis sent to Discord
```

**❌ BAD (No webhooks received):**
```
[No "📥 Received Tradytics webhook" messages]
```
**This means:** Tradytics isn't sending to our endpoint (URLs not changed)

**❌ BAD (Webhooks received but failing):**
```
📥 Received Tradytics webhook...
❌ Webhook processing error: [error message]
```
**This means:** System is receiving but has an error (check error message)

---

### **Step 4: Test the Endpoint Manually**

**Test with curl:**
```bash
curl -X POST https://lotto-machine.onrender.com/tradytics-forward \
  -H "Content-Type: application/json" \
  -d '{
    "content": "SPY Darkpool Signal - Large Darkpool Activity - Price: 685.831 - Shares: 1.4M - Amount: 960.16M",
    "username": "Darkpool"
  }'
```

**Expected Response:**
```json
{
  "status": "processed",
  "agent": "DarkpoolAgent",
  "synthesis_generated": true
}
```

**If this works:**
- ✅ System is working
- ❌ Tradytics isn't sending to our endpoint (URLs not changed)

**If this fails:**
- ❌ System has an error (check response for error message)

---

## 🔍 **COMMON ISSUES:**

### **Issue 1: "No alerts received"**

**Possible Causes:**
1. ❌ Webhook URLs not changed in Tradytics settings
2. ❌ Tradytics service not sending webhooks
3. ❌ Network/firewall blocking requests

**Solutions:**
1. ✅ Verify URLs are changed: Check Tradytics dashboard
2. ✅ Check Tradytics service status
3. ✅ Test endpoint manually (see Step 4 above)

---

### **Issue 2: "Alerts received but no Discord messages"**

**Possible Causes:**
1. ❌ `DISCORD_WEBHOOK_URL` not set
2. ❌ Discord webhook URL invalid/expired
3. ❌ Discord rate limiting

**Solutions:**
1. ✅ Check `/webhook-debug` endpoint - should show `discord_webhook_url_set: true`
2. ✅ Verify Discord webhook URL in Render environment variables
3. ✅ Test Discord webhook directly:
   ```bash
   curl -X POST YOUR_DISCORD_WEBHOOK_URL \
     -H "Content-Type: application/json" \
     -d '{"content": "Test message"}'
   ```

---

### **Issue 3: "Analysis failed"**

**Possible Causes:**
1. ❌ Agent couldn't parse alert format
2. ❌ Tradytics ecosystem not loaded
3. ❌ Content format unexpected

**Solutions:**
1. ✅ Check Render logs for specific error message
2. ✅ Verify `/webhook-debug` shows `tradytics_ecosystem_available: true`
3. ✅ Check if alert content is in expected format

---

## 📊 **DIAGNOSTIC ENDPOINTS:**

### **1. Webhook Debug:**
```
GET https://lotto-machine.onrender.com/webhook-debug
```
Shows configuration status and troubleshooting info

### **2. Test Tradytics:**
```
GET https://lotto-machine.onrender.com/test-tradytics
```
Tests agent processing with sample alert

### **3. Health Check:**
```
GET https://lotto-machine.onrender.com/health
```
Shows if service is running

---

## 🎯 **QUICK DIAGNOSIS:**

**Run these checks in order:**

1. **Check configuration:**
   ```bash
   curl https://lotto-machine.onrender.com/webhook-debug
   ```

2. **Test endpoint manually:**
   ```bash
   curl -X POST https://lotto-machine.onrender.com/tradytics-forward \
     -H "Content-Type: application/json" \
     -d '{"content":"Test alert","username":"TestBot"}'
   ```

3. **Check Render logs:**
   - Look for "📥 Received Tradytics webhook" messages
   - Look for error messages

4. **Verify Tradytics URLs:**
   - Check Tradytics dashboard
   - Verify all URLs point to our endpoint

---

## ✅ **EXPECTED WORKFLOW:**

```
1. Tradytics sends alert → https://lotto-machine.onrender.com/tradytics-forward
   ↓
2. Render logs show: "📥 Received Tradytics webhook"
   ↓
3. System parses: "📊 Parsed alert content: ..."
   ↓
4. Agent selected: "🤖 Selected agent: DarkpoolAgent"
   ↓
5. Analysis: "📊 Agent processing result: success=True"
   ↓
6. Discord forward: "✅ Forwarded Darkpool alert to Discord"
   ↓
7. Synthesis: "✅ Synthesized analysis sent to Discord"
   ↓
8. You see in Discord: Original alert + Analysis
```

**If any step is missing, check the troubleshooting section above!**
