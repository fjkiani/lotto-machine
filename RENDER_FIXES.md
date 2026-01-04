# 🔧 Render Deployment Fixes - Spin-Down & Chat History

## Issues Identified

### 1. **Service Spins Down** ❌
**Problem:** Render free tier spins down after 15 minutes of inactivity. The self-ping mechanism was using `localhost` which doesn't work on Render.

**Solution:** ✅ Fixed self-ping to use actual Render service URL

### 2. **Chat History Lost** ❌
**Problem:** All SQLite databases are stored in ephemeral filesystem (`data/` directory). When Render spins down, the filesystem is wiped and all data is lost.

**Solution:** ✅ Created persistent storage utility with multiple fallback options

---

## Fixes Applied

### 1. Self-Ping Fix (Keep-Alive)

**File:** `run_all_monitors_web.py`

**Changes:**
- Updated `self_ping()` function to use `RENDER_SERVICE_URL` environment variable
- Falls back to localhost for local testing
- Improved logging to show which URL is being used

**How to Use:**
1. In Render dashboard, go to your service → Environment
2. Add environment variable:
   - Key: `RENDER_SERVICE_URL`
   - Value: `https://lotto-machine.onrender.com`
3. Save and redeploy

**Result:** Service will ping itself every 10 minutes to prevent spin-down ✅

---

### 2. Persistent Storage Utility

**File:** `core/utils/persistent_storage.py` (NEW)

**Features:**
- Automatically detects Render persistent disk (paid tier)
- Falls back to project root `/data` directory
- Supports `DATA_DIR` environment variable override
- Logs warnings if using ephemeral storage

**How to Use:**

#### Option A: Upgrade to Render Paid Tier (Recommended)
1. Upgrade your Render service to paid tier ($7/month)
2. In `render.yaml`, uncomment the `disk` section:
```yaml
disk:
  name: persistent-data
  mountPath: /opt/render/project/src/data
  sizeGB: 1
```
3. Redeploy - databases will persist across restarts ✅

#### Option B: Use External Database (Free Alternative)
1. Set up free PostgreSQL database (Render, Supabase, etc.)
2. Update database classes to use PostgreSQL instead of SQLite
3. Set connection string in environment variables

#### Option C: Use External Storage (S3, etc.)
1. Set `DATA_DIR` environment variable to external storage path
2. Mount external storage to that path
3. Databases will be stored externally ✅

---

## Next Steps

### Immediate Actions:

1. **Set RENDER_SERVICE_URL:**
   ```bash
   # In Render dashboard → Environment → Add:
   RENDER_SERVICE_URL = https://alpha-intelligence-monitor.onrender.com
   ```

2. **Update Database Classes:**
   All database classes need to use the persistent storage utility:
   
   **Example:**
   ```python
   # Before:
   db_path = Path(__file__).parent.parent.parent / "data" / "dp_learning.db"
   
   # After:
   from core.utils.persistent_storage import get_database_path
   db_path = get_database_path("dp_learning.db")
   ```

3. **Test Keep-Alive:**
   - Deploy with `RENDER_SERVICE_URL` set
   - Check logs for "✅ Self-ping successful" messages
   - Service should stay awake ✅

### Database Classes to Update:

- [ ] `live_monitoring/agents/dp_learning/database.py`
- [ ] `live_monitoring/agents/trump_database.py`
- [ ] `live_monitoring/agents/economic/database.py`
- [ ] `live_monitoring/agents/fed_officials/database.py`
- [ ] `live_monitoring/exploitation/reddit_exploiter.py` (SentimentHistory)
- [ ] `src/data/memory.py` (AnalysisMemory)
- [ ] Any other SQLite database classes

---

## Verification

### Check Keep-Alive:
```bash
# Check Render logs for:
✅ Self-ping successful (keeping service awake)

# Or manually test:
curl https://lotto-machine.onrender.com/health
```

### Check Persistent Storage:
```bash
# Check Render logs for:
💾 Using Render persistent disk: /opt/render/project/src/data
# OR
⚠️  WARNING: Using ephemeral storage on Render free tier!
```

### Test Chat History:
1. Generate some chat history
2. Wait for service to spin down (or manually restart)
3. Check if history persists after restart

---

## Status

- ✅ Self-ping fix applied
- ✅ Persistent storage utility created
- ⏳ Database classes need to be updated to use utility
- ⏳ `RENDER_SERVICE_URL` needs to be set in Render dashboard
- ⏳ Consider upgrading to paid tier for persistent disk

---

**Next:** Update all database classes to use `get_database_path()` from persistent storage utility.

