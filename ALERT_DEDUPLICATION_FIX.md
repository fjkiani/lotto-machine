# 🛡️ Alert Deduplication Fix

## Problem

Alerts were spamming Discord repeatedly because the system didn't track whether it had already sent a particular alert. The same alerts (NARRATIVE BRAIN SIGNAL, UNIFIED MARKET SYNTHESIS, DARK POOL AT_LEVEL) were being sent every minute.

## Solution

Added a **global deduplication system** in `PipelineOrchestrator` that:

1. **Generates unique hash** for each alert based on:
   - Alert type (synthesis, dp, narrative_brain, etc.)
   - Symbol (SPY, QQQ, etc.)
   - Source (signal_brain, dp_monitor, etc.)
   - Title/content
   - Key embed fields (confluence scores, prices, etc.)

2. **Tracks sent alerts** in memory with timestamps

3. **Enforces 5-minute cooldown** - identical alerts won't be sent again within 5 minutes

4. **Automatic cleanup** - removes entries older than 1 hour to prevent memory bloat

## Implementation

**File:** `live_monitoring/pipeline/orchestrator.py`

**Changes:**
- Added `sent_alerts` dictionary to track sent alerts
- Added `alert_cooldown_seconds = 300` (5 minutes)
- Added `_generate_alert_hash()` method to create unique identifiers
- Modified `alert_callback()` to check for duplicates before sending

## How It Works

```python
# When alert is generated:
alert_hash = self._generate_alert_hash(alert_dict)

# Check if already sent recently:
if alert_hash in self.sent_alerts:
    elapsed = time.time() - self.sent_alerts[alert_hash]
    if elapsed < 300:  # 5 minutes
        return  # Skip duplicate

# Mark as sent and send alert
self.sent_alerts[alert_hash] = time.time()
# ... send to Discord ...
```

## Hash Generation

The hash is created from:
- Alert type + symbol + source
- Title (extracts key numbers like confluence %)
- Content (if contains SPY/QQQ)
- First 4 embed fields (extracts numbers from values)

This ensures that:
- Same signal with same data = same hash = blocked
- Different prices/levels = different hash = allowed
- Different symbols = different hash = allowed

## Configuration

**Cooldown Period:** 5 minutes (300 seconds)
- Can be adjusted in `orchestrator.py`:
  ```python
  self.alert_cooldown_seconds = 300  # Change this
  ```

**Memory Management:**
- Keeps last 100 alert hashes
- Auto-removes entries older than 1 hour
- Prevents memory bloat

## Testing

To verify it's working:

1. **Check logs** for duplicate detection:
   ```
   ⏭️ Alert duplicate (sent 45s ago) - skipping: synthesis SPY
   ```

2. **Monitor Discord** - should see:
   - First alert: ✅ Sent
   - Same alert within 5 min: ❌ Blocked
   - Different alert: ✅ Sent
   - Same alert after 5 min: ✅ Sent (cooldown expired)

## Impact

**Before:**
- Same alert sent every minute
- Discord spam
- No way to know if alert was already sent

**After:**
- Same alert sent once per 5 minutes max
- Clean Discord feed
- Automatic duplicate detection
- Memory-efficient tracking

## Status

✅ **FIXED** - Deduplication system active

The system will now prevent duplicate alerts from spamming Discord while still allowing legitimate new alerts to come through.



