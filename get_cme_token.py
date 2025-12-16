#!/usr/bin/env python3
"""
Get CME FedWatch API Token

Attempts multiple authentication methods:
1. Direct OAuth 2.0 with CME API credentials
2. Google Cloud Workload Identity Federation
3. Manual token file creation
"""

import sys
import json
import os
import logging
import requests
from pathlib import Path
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# CME API Credentials
CME_API_ID = "api_fjk"
CME_TOKEN = "552615"
CME_ACCESS_CODE = "093639"

# Google Cloud WIF Config
GOOGLE_WIF_CONFIG = {
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

# CME API Endpoints
CME_TOKEN_ENDPOINT = "https://api.cmegroup.com/oauth/token"  # May need to verify
CME_BASE_URL = "https://markets.api.cmegroup.com/fedwatch/v1"


def method1_direct_oauth() -> Optional[str]:
    """
    Method 1: Try direct OAuth 2.0 authentication with CME credentials
    
    Some APIs support direct client credentials flow.
    """
    logger.info("🔐 METHOD 1: Direct OAuth 2.0 with CME Credentials")
    
    try:
        # Try client credentials grant
        data = {
            'grant_type': 'client_credentials',
            'client_id': CME_API_ID,
            'client_secret': CME_TOKEN,
            'scope': 'fedwatch'
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        response = requests.post(CME_TOKEN_ENDPOINT, data=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            if access_token:
                logger.info("✅ Direct OAuth successful!")
                return access_token
        else:
            logger.warning(f"Direct OAuth failed: {response.status_code} - {response.text[:200]}")
            
    except Exception as e:
        logger.debug(f"Direct OAuth error: {e}")
    
    return None


def method2_google_wif() -> Optional[str]:
    """
    Method 2: Use Google Cloud Workload Identity Federation
    
    Requires token file at /tmp/token with id_token
    """
    logger.info("🔐 METHOD 2: Google Cloud Workload Identity Federation")
    
    try:
        from google.auth import load_credentials_from_dict
        from google.auth.transport.requests import Request
        
        # Check if token file exists
        token_file = "/tmp/token"
        if not os.path.exists(token_file):
            logger.warning(f"Token file not found: {token_file}")
            logger.info("   Creating template token file...")
            template = {"id_token": "YOUR_ID_TOKEN_HERE"}
            with open(token_file, 'w') as f:
                json.dump(template, f, indent=2)
            logger.info(f"   ✅ Created template at {token_file}")
            logger.info("   Please replace 'YOUR_ID_TOKEN_HERE' with actual id_token")
            return None
        
        # Load token file
        with open(token_file, 'r') as f:
            token_data = json.load(f)
        
        id_token = token_data.get('id_token')
        if not id_token or id_token == "YOUR_ID_TOKEN_HERE":
            logger.warning("Token file contains placeholder or missing id_token")
            return None
        
        # Update config with token file path
        config = GOOGLE_WIF_CONFIG.copy()
        config['credential_source']['file'] = token_file
        
        # Load credentials
        credentials, _ = load_credentials_from_dict(config)
        
        # Refresh to get access token
        if not credentials.valid:
            credentials.refresh(Request())
        
        access_token = credentials.token
        if access_token:
            logger.info("✅ Google WIF successful!")
            return access_token
            
    except ImportError:
        logger.warning("google-auth library not installed. Install: pip install google-auth")
    except Exception as e:
        logger.warning(f"Google WIF error: {e}")
        import traceback
        traceback.print_exc()
    
    return None


def method3_cme_direct_auth() -> Optional[str]:
    """
    Method 3: Try CME API direct authentication
    
    Some APIs use API ID + Token + Access Code directly in headers
    """
    logger.info("🔐 METHOD 3: CME Direct Authentication (API ID + Token + Access Code)")
    
    # Test if we can make a request with credentials in headers
    try:
        headers = {
            'X-CME-API-ID': CME_API_ID,
            'X-CME-TOKEN': CME_TOKEN,
            'X-CME-ACCESS-CODE': CME_ACCESS_CODE,
            'Accept': 'application/json'
        }
        
        # Try a simple endpoint
        test_url = f"{CME_BASE_URL}/meetings"
        response = requests.get(test_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ Direct authentication successful!")
            # Return a placeholder - direct auth doesn't need token
            return "DIRECT_AUTH"
        elif response.status_code == 401:
            logger.warning("Direct auth failed: 401 Unauthorized")
        else:
            logger.warning(f"Direct auth returned: {response.status_code}")
            
    except Exception as e:
        logger.debug(f"Direct auth error: {e}")
    
    return None


def method4_manual_token() -> Optional[str]:
    """
    Method 4: Manual token file creation guide
    """
    logger.info("🔐 METHOD 4: Manual Token File Setup")
    
    token_file = "/tmp/token"
    
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            token_data = json.load(f)
        
        id_token = token_data.get('id_token')
        if id_token and id_token != "YOUR_ID_TOKEN_HERE":
            logger.info(f"✅ Token file exists with id_token")
            logger.info("   You can use this with Google WIF (Method 2)")
            return id_token
    
    logger.info("📝 To get id_token, you need to:")
    logger.info("   1. Use Google Cloud CLI or API to authenticate")
    logger.info("   2. Exchange credentials for id_token")
    logger.info("   3. Save to /tmp/token as: {\"id_token\": \"<your_token>\"}")
    logger.info("")
    logger.info("   Or contact CME support for token generation instructions")
    
    return None


def test_token(access_token: str) -> bool:
    """
    Test if the access token works with CME API
    """
    logger.info("🧪 Testing access token with CME API...")
    
    try:
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        # Try /meetings endpoint
        url = f"{CME_BASE_URL}/meetings"
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            logger.info("✅ Token test successful! API responded with 200 OK")
            try:
                data = response.json()
                logger.info(f"   Response keys: {list(data.keys()) if isinstance(data, dict) else 'List/Array'}")
                logger.info(f"   Sample: {json.dumps(data, indent=2)[:300]}")
            except:
                logger.info(f"   Response: {response.text[:300]}")
            return True
        elif response.status_code == 401:
            logger.error("❌ Token test failed: 401 Unauthorized")
            logger.error(f"   Response: {response.text[:200]}")
        elif response.status_code == 403:
            logger.error("❌ Token test failed: 403 Forbidden")
            logger.error(f"   Response: {response.text[:200]}")
        else:
            logger.warning(f"⚠️ Token test returned: {response.status_code}")
            logger.warning(f"   Response: {response.text[:200]}")
            
    except Exception as e:
        logger.error(f"❌ Token test error: {e}")
        import traceback
        traceback.print_exc()
    
    return False


def main():
    """Main function to get and test CME token"""
    print("=" * 70)
    print("🔑 CME FEDWATCH API TOKEN ACQUISITION")
    print("=" * 70)
    print()
    
    access_token = None
    
    # Try Method 1: Direct OAuth
    access_token = method1_direct_oauth()
    if access_token:
        if test_token(access_token):
            print("\n✅ SUCCESS! Using Method 1 (Direct OAuth)")
            save_token_to_file(access_token)
            return
    
    # Try Method 2: Google WIF
    access_token = method2_google_wif()
    if access_token:
        if test_token(access_token):
            print("\n✅ SUCCESS! Using Method 2 (Google WIF)")
            return
    
    # Try Method 3: Direct Auth
    access_token = method3_cme_direct_auth()
    if access_token == "DIRECT_AUTH":
        print("\n✅ SUCCESS! Using Method 3 (Direct Auth - no token needed)")
        return
    
    # Method 4: Manual guide
    method4_manual_token()
    
    print("\n" + "=" * 70)
    print("📝 NEXT STEPS:")
    print("=" * 70)
    print("1. Check CME documentation for exact authentication method")
    print("2. Verify API credentials are correct")
    print("3. Check if IP whitelist is required")
    print("4. Contact CME support if needed")
    print()


def save_token_to_file(token: str, filepath: str = "/tmp/cme_access_token.txt"):
    """Save access token to file for later use"""
    try:
        with open(filepath, 'w') as f:
            f.write(token)
        os.chmod(filepath, 0o600)
        logger.info(f"✅ Token saved to {filepath}")
    except Exception as e:
        logger.warning(f"Failed to save token: {e}")


if __name__ == "__main__":
    main()



