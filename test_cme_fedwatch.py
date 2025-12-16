#!/usr/bin/env python3
"""
Test CME FedWatch Intraday REST API Client

Uses Google Cloud Workload Identity Federation authentication.
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

from live_monitoring.enrichment.apis.cme_fedwatch_client import CMEFedWatchClient

# Credential configuration
CREDENTIAL_CONFIG = {
    "universe_domain": "googleapis.com",
    "type": "external_account",
    "audience": "//iam.googleapis.com/projects/282603793014/locations/global/workloadIdentityPools/iamwip-cmegroup/providers/customer-federation",
    "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
    "token_url": "https://sts.googleapis.com/v1/token",
    "credential_source": {
        "file": "/tmp/token",
        "format": {
            "type": "json",
            "subject_token_field_name": "id_token"
        }
    },
    "token_info_url": "https://sts.googleapis.com/v1/introspect"
}

# CME API credentials
CME_API_ID = "api_fjk"
CME_TOKEN = "552615"
CME_ACCESS_CODE = "093639"

def test_cme_fedwatch():
    """Test CME FedWatch Intraday API"""
    print("=" * 70)
    print("🧪 TESTING CME FEDWATCH INTRADAY REST API")
    print("=" * 70)
    
    # Check token file
    print("\n📋 STEP 1: Check Token File")
    print("-" * 50)
    token_file = "/tmp/token"
    if Path(token_file).exists():
        print(f"   ✅ Token file exists: {token_file}")
        try:
            with open(token_file, 'r') as f:
                token_data = json.load(f)
            if 'id_token' in token_data:
                token_preview = token_data['id_token'][:50] + "..."
                print(f"   ✅ Token found: {token_preview}")
            else:
                print(f"   ⚠️ Token file missing 'id_token' field")
                print(f"   Available keys: {list(token_data.keys())}")
        except Exception as e:
            print(f"   ❌ Failed to read token file: {e}")
    else:
        print(f"   ⚠️ Token file not found: {token_file}")
        print(f"   Please ensure the token file exists at this path")
    
    # Initialize client
    print("\n📋 STEP 2: Initialize CME FedWatch Client")
    print("-" * 50)
    
    try:
        client = CMEFedWatchClient(
            credential_config=CREDENTIAL_CONFIG,
            token_file=token_file,
            api_id=CME_API_ID,
            token=CME_TOKEN,
            access_code=CME_ACCESS_CODE
        )
        print("   ✅ Client initialized")
        print(f"   API ID: {CME_API_ID}")
    except Exception as e:
        print(f"   ❌ Failed to initialize: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test access token
    print("\n📋 STEP 3: Get Access Token")
    print("-" * 50)
    
    try:
        access_token = client._get_access_token()
        if access_token:
            token_preview = access_token[:50] + "..."
            print(f"   ✅ Access token obtained: {token_preview}")
        else:
            print(f"   ⚠️ No access token available")
    except Exception as e:
        print(f"   ❌ Failed to get access token: {e}")
    
    # Test FedWatch Intraday API
    print("\n📋 STEP 4: Fetch FedWatch Intraday Data")
    print("-" * 50)
    
    try:
        data = client.get_fedwatch_intraday()
        if data:
            print(f"   ✅ Successfully fetched FedWatch Intraday data")
            print(f"   Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            # Try to parse probabilities
            probs = client.parse_probabilities(data)
            if probs:
                print(f"   ✅ Parsed probabilities:")
                for key, value in probs.items():
                    print(f"      {key}: {value:.1f}%")
                
                # Get cut probability
                cut_prob = client.get_cut_probability()
                if cut_prob is not None:
                    print(f"   ✅ Combined cut probability: {cut_prob:.1f}%")
            else:
                print(f"   ⚠️ Could not parse probabilities")
                print(f"   Raw data sample: {json.dumps(data, indent=2)[:500]}")
        else:
            print(f"   ❌ Failed to fetch FedWatch Intraday data")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test FedWatch EOD API
    print("\n📋 STEP 5: Fetch FedWatch End-of-Day Data")
    print("-" * 50)
    
    try:
        eod_data = client.get_fedwatch_eod()
        if eod_data:
            print(f"   ✅ Successfully fetched FedWatch EOD data")
            print(f"   Data keys: {list(eod_data.keys()) if isinstance(eod_data, dict) else 'Not a dict'}")
        else:
            print(f"   ❌ Failed to fetch FedWatch EOD data")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE")
    print("=" * 70)
    print("\n📝 Note: If endpoints fail, check:")
    print("   1. Actual API endpoint URLs in CME documentation")
    print("   2. Token file contains valid id_token")
    print("   3. IP address is whitelisted for API access")
    print("   4. API ID, Token, Access Code are correct")

if __name__ == "__main__":
    test_cme_fedwatch()

