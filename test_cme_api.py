#!/usr/bin/env python3
"""
Test CME API Client with provided credentials
"""

import sys
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Add paths
sys.path.insert(0, str(Path(__file__).parent))

from live_monitoring.enrichment.apis.cme_api_client import CMEAPIClient

# CME API Credentials from user
CME_API_ID = "api_fjk"
CME_TOKEN = "552615"
CME_ACCESS_CODE = "093639"

def test_cme_api():
    """Test CME API client"""
    print("=" * 70)
    print("🧪 TESTING CME API CLIENT")
    print("=" * 70)
    
    # Initialize client with provided credentials
    print("\n📋 STEP 1: Initialize CME API Client")
    print("-" * 50)
    
    try:
        client = CMEAPIClient(
            api_id=CME_API_ID,
            token=CME_TOKEN,
            access_code=CME_ACCESS_CODE
        )
        print("   ✅ Client initialized")
        print(f"   API ID: {CME_API_ID}")
        print(f"   Token: {'*' * len(CME_TOKEN)}")
        print(f"   Access Code: {'*' * len(CME_ACCESS_CODE)}")
    except Exception as e:
        print(f"   ❌ Failed to initialize: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Check authentication header
    print("\n📋 STEP 2: Check Authentication")
    print("-" * 50)
    if client.auth_header:
        print(f"   ✅ Auth header generated: {client.auth_header[:30]}...")
    else:
        print(f"   ⚠️ Auth header not generated - check credentials")
    
    # Test FedWatch probabilities
    print("\n📋 STEP 3: Fetch FedWatch Probabilities")
    print("-" * 50)
    
    try:
        data = client.get_fedwatch_probabilities()
        if data:
            print(f"   ✅ Successfully fetched FedWatch data")
            print(f"   Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            # Try to parse
            probs = client.parse_fedwatch_probabilities(data)
            if probs:
                print(f"   ✅ Parsed probabilities:")
                for key, value in probs.items():
                    print(f"      {key}: {value:.1f}%")
            
            # Get cut probability
            cut_prob = client.get_cut_probability()
            if cut_prob is not None:
                print(f"   ✅ Combined cut probability: {cut_prob:.1f}%")
            else:
                print(f"   ⚠️ Could not calculate cut probability")
        else:
            print(f"   ❌ Failed to fetch FedWatch data")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test FedWatch tool data
    print("\n📋 STEP 4: Fetch FedWatch Tool Data")
    print("-" * 50)
    
    try:
        tool_data = client.get_fedwatch_tool_data()
        if tool_data:
            print(f"   ✅ Successfully fetched FedWatch tool data")
            print(f"   Data keys: {list(tool_data.keys()) if isinstance(tool_data, dict) else 'Not a dict'}")
        else:
            print(f"   ❌ Failed to fetch FedWatch tool data")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    test_cme_api()

