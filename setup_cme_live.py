#!/usr/bin/env python3
"""
Setup CME FedWatch API - Get Token and Bring Live

This script attempts multiple methods to authenticate with CME API
"""

import sys
import json
import os
import requests
import logging
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# CME Configuration
CME_API_ID = "api_fjk"
CME_TOKEN = "552615"
CME_ACCESS_CODE = "093639"
CME_BASE_URL = "https://markets.api.cmegroup.com/fedwatch/v1"

# Token file
TOKEN_FILE = "/tmp/token"


def try_cme_oauth() -> Optional[str]:
    """
    Try to get OAuth token from CME using API credentials
    """
    logger.info("🔐 Attempting CME OAuth 2.0 authentication...")
    
    # Common OAuth endpoints to try
    oauth_endpoints = [
        "https://api.cmegroup.com/oauth/token",
        "https://www.cmegroup.com/api/oauth/token",
        "https://markets.api.cmegroup.com/oauth/token",
        "https://api.cmegroup.com/auth/token",
    ]
    
    for endpoint in oauth_endpoints:
        try:
            # Try client credentials grant
            data = {
                'grant_type': 'client_credentials',
                'client_id': CME_API_ID,
                'client_secret': CME_TOKEN,
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            logger.info(f"   Trying: {endpoint}")
            response = requests.post(endpoint, data=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token')
                if access_token:
                    logger.info(f"✅ Success! Got token from {endpoint}")
                    return access_token
            else:
                logger.debug(f"   {endpoint}: {response.status_code}")
                
        except Exception as e:
            logger.debug(f"   {endpoint} error: {e}")
    
    return None


def try_direct_api_call() -> bool:
    """
    Try making API call with credentials in headers (some APIs work this way)
    """
    logger.info("🔐 Attempting direct API call with credentials in headers...")
    
    headers = {
        'X-CME-API-ID': CME_API_ID,
        'X-CME-TOKEN': CME_TOKEN,
        'X-CME-ACCESS-CODE': CME_ACCESS_CODE,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    # Try /meetings endpoint
    url = f"{CME_BASE_URL}/meetings"
    
    try:
        logger.info(f"   Calling: GET {url}")
        response = requests.get(url, headers=headers, timeout=15)
        
        logger.info(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("✅ SUCCESS! Direct authentication works!")
            data = response.json()
            logger.info(f"   Response: {json.dumps(data, indent=2)[:500]}")
            return True
        else:
            logger.warning(f"   Response: {response.text[:200]}")
            
    except Exception as e:
        logger.warning(f"   Error: {e}")
    
    return False


def test_with_bearer_token(token: str) -> bool:
    """
    Test API call with Bearer token
    """
    logger.info("🧪 Testing Bearer token with CME API...")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    url = f"{CME_BASE_URL}/meetings"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        logger.info(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("✅ SUCCESS! Bearer token works!")
            data = response.json()
            logger.info(f"   Response keys: {list(data.keys()) if isinstance(data, dict) else 'List'}")
            logger.info(f"   Sample: {json.dumps(data, indent=2)[:500]}")
            
            # Save token
            with open("/tmp/cme_access_token.txt", 'w') as f:
                f.write(token)
            os.chmod("/tmp/cme_access_token.txt", 0o600)
            logger.info("✅ Token saved to /tmp/cme_access_token.txt")
            
            return True
        else:
            logger.warning(f"   Response: {response.text[:200]}")
            
    except Exception as e:
        logger.error(f"   Error: {e}")
    
    return False


def check_token_file() -> Optional[str]:
    """
    Check if token file exists and has valid token
    """
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                data = json.load(f)
            id_token = data.get('id_token')
            if id_token and id_token != "YOUR_ID_TOKEN_HERE":
                logger.info(f"✅ Found id_token in {TOKEN_FILE}")
                return id_token
        except Exception as e:
            logger.warning(f"Failed to read token file: {e}")
    
    return None


def use_google_wif(id_token: str) -> Optional[str]:
    """
    Use Google Workload Identity Federation to get access token
    """
    logger.info("🔐 Using Google WIF to exchange id_token for access token...")
    
    try:
        from google.auth import load_credentials_from_dict
        from google.auth.transport.requests import Request
        
        config = {
            "universe_domain": "googleapis.com",
            "type": "external_account",
            "audience": "//iam.googleapis.com/projects/282603793014/locations/global/workloadIdentityPools/iamwip-cmegroup/providers/customer-federation",
            "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
            "token_url": "https://sts.googleapis.com/v1/token",
            "credential_source": {
                "file": TOKEN_FILE,
                "format": {
                    "type": "json",
                    "subject_token_field_name": "id_token"
                }
            }
        }
        
        credentials, _ = load_credentials_from_dict(config)
        
        if not credentials.valid:
            credentials.refresh(Request())
        
        access_token = credentials.token
        if access_token:
            logger.info("✅ Got access token from Google WIF")
            return access_token
            
    except Exception as e:
        logger.warning(f"Google WIF failed: {e}")
        import traceback
        traceback.print_exc()
    
    return None


def main():
    """Main function"""
    print("=" * 70)
    print("🚀 SETTING UP CME FEDWATCH API - BRINGING IT LIVE")
    print("=" * 70)
    print()
    
    access_token = None
    
    # Method 1: Try direct API call (no token needed)
    print("📋 METHOD 1: Direct API Call with Credentials")
    print("-" * 50)
    if try_direct_api_call():
        print("\n✅ SUCCESS! CME API is live with direct authentication!")
        print("\n📝 No token needed - credentials work directly in headers")
        return
    
    # Method 2: Try CME OAuth
    print("\n📋 METHOD 2: CME OAuth 2.0")
    print("-" * 50)
    access_token = try_cme_oauth()
    if access_token:
        if test_with_bearer_token(access_token):
            print("\n✅ SUCCESS! CME API is live with OAuth token!")
            return
    
    # Method 3: Check for existing token file
    print("\n📋 METHOD 3: Google Cloud Workload Identity Federation")
    print("-" * 50)
    id_token = check_token_file()
    if id_token:
        access_token = use_google_wif(id_token)
        if access_token:
            if test_with_bearer_token(access_token):
                print("\n✅ SUCCESS! CME API is live with Google WIF token!")
                return
    
    # If all methods fail, provide instructions
    print("\n" + "=" * 70)
    print("⚠️ COULD NOT AUTOMATICALLY AUTHENTICATE")
    print("=" * 70)
    print("\n📝 To get the token manually:")
    print("\n1. **Using gcloud CLI (if installed):**")
    print(f"   gcloud auth print-identity-token --audiences //iam.googleapis.com/projects/282603793014/locations/global/workloadIdentityPools/iamwip-cmegroup/providers/customer-federation")
    print(f"   Then save to {TOKEN_FILE} as:")
    print('   {"id_token": "<token_from_gcloud>"}')
    print("\n2. **Using Google Cloud Console:**")
    print("   - Go to Google Cloud Console")
    print("   - Navigate to IAM & Admin > Workload Identity Federation")
    print("   - Generate identity token for the audience above")
    print(f"   - Save to {TOKEN_FILE}")
    print("\n3. **Contact CME Support:**")
    print("   - Ask for OAuth token generation instructions")
    print("   - Verify API ID, Token, Access Code are correct")
    print("   - Check if IP whitelist is required")
    print("\n4. **Check CME Documentation:**")
    print("   https://cmegroupclientsite.atlassian.net/wiki/display/EPICSANDBOX/CME+FedWatch+API")
    print()


if __name__ == "__main__":
    main()



