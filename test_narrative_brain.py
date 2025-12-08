#!/usr/bin/env python3
"""
Test Narrative Brain Integration
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

def test_narrative_brain():
    """Test basic narrative brain functionality"""
    print("🧠 TESTING NARRATIVE BRAIN")
    print("=" * 50)

    try:
        from live_monitoring.agents.narrative_brain import NarrativeBrain
        from live_monitoring.agents.narrative_brain.models import AlertType, NarrativePriority

        # Initialize
        brain = NarrativeBrain()
        print("✅ NarrativeBrain initialized")

        # Test memory
        context = brain.memory.get_context()
        print(f"📚 Memory loaded: {context is not None}")

        # Test pre-market outlook (simulate morning)
        print("\\n🌅 Testing pre-market outlook...")
        update = brain.generate_pre_market_outlook()
        if update:
            print("✅ Pre-market outlook generated")
            print(f"   Title: {update.title}")
            print(f"   Priority: {update.priority.value}")
        else:
            print("⚠️ Pre-market outlook not generated (not morning time)")

        # Test intelligence processing
        print("\\n🎯 Testing intelligence processing...")
        test_data = {
            'fed_watch': {'cut_prob': 75, 'sentiment': 'DOVISH'},
            'dp_monitor': {'active_levels': [{'price': 685.50, 'volume': 1000000}], 'institutional_bias': 'bullish'}
        }

        update = brain.process_intelligence_update("test_source", test_data)
        if update:
            print("✅ Intelligence update processed")
            print(f"   Type: {update.alert_type.value}")
            print(f"   Priority: {update.priority.value}")
        else:
            print("⚠️ No update generated (filtered out)")

        # Test current context
        context = brain.get_current_context()
        print(f"\\n📊 Current context: {len(context)} sources integrated")

        print("\\n🎉 NARRATIVE BRAIN TESTS PASSED!")
        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_narrative_brain()
    sys.exit(0 if success else 1)



