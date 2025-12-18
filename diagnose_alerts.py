#!/usr/bin/env python3
"""
Diagnostic script to check why alerts aren't firing to Discord
"""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

print("🔍 DIAGNOSING ALERT SYSTEM")
print("=" * 60)

# Check 1: Discord Webhook
discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
if discord_webhook:
    print(f"✅ DISCORD_WEBHOOK_URL is set: {discord_webhook[:20]}...")
else:
    print("❌ DISCORD_WEBHOOK_URL is NOT set!")
    print("   This is why alerts aren't being sent to Discord!")

# Check 2: Test AlertManager
print("\n📦 Testing AlertManager...")
try:
    from live_monitoring.orchestrator.alert_manager import AlertManager
    
    alert_mgr = AlertManager()
    print(f"   AlertManager initialized")
    print(f"   Discord webhook: {'✅ Set' if alert_mgr.discord_webhook else '❌ NOT SET'}")
    
    # Test sending an alert
    test_embed = {
        "title": "🧪 TEST ALERT",
        "description": "This is a test alert to verify Discord integration",
        "color": 3066993,
        "timestamp": "2024-12-18T00:00:00Z"
    }
    
    print("\n📤 Attempting to send test alert...")
    result = alert_mgr.send_discord(test_embed, "🧪 TEST ALERT - If you see this, Discord is working!", "test", "diagnostic")
    
    if result:
        print("   ✅ Test alert sent successfully!")
    else:
        print("   ❌ Test alert failed to send")
        if not alert_mgr.discord_webhook:
            print("   ⚠️  Reason: DISCORD_WEBHOOK_URL not configured")
        
except Exception as e:
    print(f"   ❌ Error testing AlertManager: {e}")
    import traceback
    traceback.print_exc()

# Check 3: Check if checkers are generating alerts
print("\n🔍 Checking if checkers are generating alerts...")
try:
    from live_monitoring.orchestrator.unified_monitor import UnifiedAlphaMonitor
    
    print("   Initializing UnifiedAlphaMonitor...")
    monitor = UnifiedAlphaMonitor()
    
    print(f"   Fed checker: {'✅ Enabled' if monitor.fed_checker else '❌ Disabled'}")
    print(f"   Trump checker: {'✅ Enabled' if monitor.trump_checker else '❌ Disabled'}")
    print(f"   DP checker: {'✅ Enabled' if monitor.dp_checker else '❌ Disabled'}")
    print(f"   Gamma checker: {'✅ Enabled' if monitor.gamma_checker else '❌ Disabled'}")
    
    # Test Fed checker
    if monitor.fed_checker:
        print("\n   Testing Fed checker...")
        alerts = monitor.fed_checker.check()
        print(f"   Fed checker generated {len(alerts)} alerts")
        if alerts:
            for alert in alerts:
                print(f"      - {alert.alert_type} from {alert.source}")
        else:
            print("      ⚠️  No alerts generated (might be normal if no changes)")
    
    # Test Trump checker
    if monitor.trump_checker:
        print("\n   Testing Trump checker...")
        alerts = monitor.trump_checker.check()
        print(f"   Trump checker generated {len(alerts)} alerts")
        if alerts:
            for alert in alerts:
                print(f"      - {alert.alert_type} from {alert.source}")
        else:
            print("      ⚠️  No alerts generated (might be normal if no new Trump news)")
    
except Exception as e:
    print(f"   ❌ Error checking checkers: {e}")
    import traceback
    traceback.print_exc()

# Check 4: Environment variables
print("\n🔑 Environment Variables Check:")
env_vars = [
    'DISCORD_WEBHOOK_URL',
    'CHARTEXCHANGE_API_KEY',
    'PERPLEXITY_API_KEY',
]

for var in env_vars:
    value = os.getenv(var)
    if value:
        print(f"   ✅ {var}: {'*' * 20} (set)")
    else:
        print(f"   ❌ {var}: NOT SET")

print("\n" + "=" * 60)
print("✅ DIAGNOSIS COMPLETE")
print("\n💡 RECOMMENDATIONS:")
if not discord_webhook:
    print("   1. Set DISCORD_WEBHOOK_URL in .env file")
    print("   2. Restart the monitor")
    print("   3. Check Render environment variables if deployed")
