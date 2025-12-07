#!/usr/bin/env python3
"""
Test Current Alert System Reality Check

Purpose: Understand what the current system actually sends vs. what I claimed
"""

import os
import sys
from pathlib import Path

# Add paths
base_path = Path(__file__).parent
sys.path.insert(0, str(base_path))

# Load environment
from dotenv import load_dotenv
load_dotenv()

def test_current_alert_system():
    """Test what the current system actually does"""
    print("🧪 TESTING CURRENT ALERT SYSTEM REALITY")
    print("=" * 60)

    # Mock Discord webhook to capture what would be sent
    sent_messages = []

    class MockDiscord:
        def __init__(self):
            self.messages = []

        def send(self, payload):
            self.messages.append(payload)
            content = payload.get('content', '')
            embed_title = payload.get('embeds', [{}])[0].get('title', '') if payload.get('embeds') else ''
            print(f"📤 MOCK DISCORD: {content[:50]}... | {embed_title[:50]}...")

    mock_discord = MockDiscord()

    try:
        # Import and initialize the monitor
        from run_all_monitors import UnifiedAlphaMonitor

        # Create monitor with mock discord
        monitor = UnifiedAlphaMonitor()
        monitor.discord_webhook = "mock"  # Will prevent real sending

        # Override discord sending to capture messages
        original_send_discord = monitor.send_discord

        def mock_send_discord(embed, content=None):
            payload = {'embeds': [embed]} if embed else {}
            if content:
                payload['content'] = content
            mock_discord.send(payload)
            return True  # Pretend it succeeded

        monitor.send_discord = mock_send_discord

        # Check if unified mode is enabled
        print(f"🔧 Unified Mode: {getattr(monitor, 'unified_mode', 'Not set')}")
        print(f"🧠 Brain Enabled: {getattr(monitor, 'brain_enabled', 'Not set')}")
        print(f"📚 Narrative Enabled: {getattr(monitor, 'narrative_enabled', 'Not set')}")

        # Simulate some DP alerts to see what happens
        print("\\n🔒 SIMULATING DP ALERTS...")

        # Create a mock DP alert
        from live_monitoring.agents.dp_monitor.models import DPAlert, Battleground, TradeSetup, AlertType, AlertPriority, LevelType, TradeDirection
        from datetime import datetime

        mock_bg = Battleground(
            symbol="SPY",
            price=685.50,
            volume=1000000,
            date="2025-12-04",
            level_type=LevelType.SUPPORT
        )

        mock_ts = TradeSetup(
            direction=TradeDirection.LONG,
            entry=685.50,
            stop=684.00,
            target=687.00,
            risk_reward=2.0,
            hold_time_min=5,
            hold_time_max=60
        )

        mock_alert = DPAlert(
            symbol="SPY",
            battleground=mock_bg,
            alert_type=AlertType.AT_LEVEL,
            priority=AlertPriority.HIGH,
            timestamp=datetime.now(),
            trade_setup=mock_ts,
            ai_prediction=0.78,
            ai_confidence="HIGH",
            ai_patterns=["touch_1", "support", "vol_1m"]
        )

        # Add to recent alerts (this is what actually happens)
        monitor.recent_dp_alerts = [mock_alert]

        print(f"📊 Added mock DP alert: {mock_alert.symbol} @ ${mock_bg.price:.2f}")

        # Test synthesis
        print("\\n🧠 TESTING SIGNAL BRAIN SYNTHESIS...")
        try:
            monitor.check_synthesis()
            print("✅ Signal Brain synthesis completed")
        except Exception as e:
            print(f"❌ Signal Brain synthesis failed: {e}")

        # Test narrative brain
        print("\\n📖 TESTING NARRATIVE BRAIN...")
        if hasattr(monitor, 'narrative_brain') and monitor.narrative_brain:
            try:
                # Test pre-market outlook generation
                outlook = monitor.narrative_brain.generate_pre_market_outlook()
                if outlook:
                    print("✅ Narrative Brain generated pre-market outlook")
                    print(f"   Title: {outlook.title}")
                    print(f"   Type: {outlook.alert_type.value}")
                else:
                    print("⚠️ Narrative Brain returned no pre-market outlook")

                # Test intelligence processing
                test_data = {'fed_watch': {'cut_prob': 75}}
                update = monitor.narrative_brain.process_intelligence_update("test", test_data)
                if update:
                    print("✅ Narrative Brain processed intelligence update")
                    print(f"   Type: {update.alert_type.value}")
                else:
                    print("⚠️ Narrative Brain filtered out intelligence update")

            except Exception as e:
                print(f"❌ Narrative Brain test failed: {e}")
        else:
            print("❌ Narrative Brain not initialized")

        # Summary
        print("\\n📊 CURRENT SYSTEM STATUS:")
        print(f"   Unified Mode: {getattr(monitor, 'unified_mode', False)}")
        print(f"   Signal Brain Active: {getattr(monitor, 'brain_enabled', False)}")
        print(f"   Narrative Brain Active: {hasattr(monitor, 'narrative_brain') and monitor.narrative_brain is not None}")
        print(f"   Recent DP Alerts Buffered: {len(getattr(monitor, 'recent_dp_alerts', []))}")

        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_current_alert_system()
    print(f"\\n🎯 RESULT: {'SUCCESS' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
