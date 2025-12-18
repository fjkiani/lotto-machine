#!/usr/bin/env python3
"""
Simple Trading Economics Data Test
===================================

Quick test to understand the data structure and identify issues.
"""

import asyncio
import json
from datetime import datetime

# Import the MCP client
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'trading-Economics', 'trading_economics_calendar_mcp-main'))

from trading_economics_calendar.client import fetch_calendar_events, TradingEconomicsClient


async def test_basic_queries():
    """Test basic queries to understand data structure"""

    print("🔍 TESTING TRADING ECONOMICS DATA STRUCTURE")
    print("=" * 50)

    # Test 1: Get all events this week
    print("\n1️⃣ Testing: All events this week")
    try:
        all_events = await fetch_calendar_events()
        print(f"✅ Found {len(all_events)} total events")

        # Show first 5 events
        print("\n📋 First 5 events:")
        for i, event in enumerate(all_events[:5]):
            print(f"{i+1}. {event}")

        # Analyze structure of first event
        if all_events:
            first_event = all_events[0]
            print(f"\n🔍 Event structure analysis:")
            print(f"Type: {type(first_event)}")
            if isinstance(first_event, dict):
                print(f"Keys: {list(first_event.keys())}")
                for key, value in first_event.items():
                    print(f"  {key}: {value} ({type(value).__name__})")
            else:
                print(f"Event content: {first_event}")

    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 2: Try different filtering
    print("\n2️⃣ Testing: Country filtering")
    test_countries = ["United States", "US", "united_states"]

    for country in test_countries:
        try:
            print(f"\nTesting country filter: '{country}'")
            events = await fetch_calendar_events(countries=[country])
            print(f"✅ Found {len(events)} events for {country}")
            if events:
                print(f"Sample: {events[0]}")
        except Exception as e:
            print(f"❌ Error with {country}: {e}")

    # Test 3: Try importance filtering
    print("\n3️⃣ Testing: Importance filtering")
    for importance in ["high", "medium", "low"]:
        try:
            print(f"\nTesting importance: '{importance}'")
            events = await fetch_calendar_events(importance=importance)
            print(f"✅ Found {len(events)} {importance} importance events")
            if events:
                # Check actual importance values
                importance_values = [e.get('importance', 'N/A') if isinstance(e, dict) else 'N/A' for e in events[:5]]
                print(f"Sample importance values: {importance_values}")
        except Exception as e:
            print(f"❌ Error with {importance}: {e}")

    # Test 4: Raw client access
    print("\n4️⃣ Testing: Raw client access")
    try:
        client = TradingEconomicsClient()
        raw_events = client.get_calendar_events()
        print(f"✅ Raw client found {len(raw_events)} events")

        # Show raw structure
        if raw_events:
            print(f"\n🔍 Raw event structure:")
            raw_event = raw_events[0]
            print(f"Type: {type(raw_event)}")
            if isinstance(raw_event, dict):
                print(f"Keys: {list(raw_event.keys())}")
                for key, value in raw_event.items():
                    print(f"  {key}: {repr(value)}")
            else:
                print(f"Raw content: {repr(raw_event)}")

    except Exception as e:
        print(f"❌ Raw client error: {e}")

    print("\n" + "=" * 50)
    print("📊 ANALYSIS COMPLETE")

    # Save sample data
    try:
        sample_data = {
            'timestamp': datetime.now().isoformat(),
            'total_events_found': len(all_events) if 'all_events' in locals() else 0,
            'sample_events': all_events[:10] if 'all_events' in locals() and all_events else [],
            'filter_tests': {
                'countries_tested': test_countries,
                'importance_levels': ['high', 'medium', 'low']
            }
        }

        with open('trading_economics_sample_data.json', 'w') as f:
            json.dump(sample_data, f, indent=2, default=str)

        print(f"💾 Sample data saved to: trading_economics_sample_data.json")

    except Exception as e:
        print(f"❌ Error saving data: {e}")


if __name__ == "__main__":
    asyncio.run(test_basic_queries())




