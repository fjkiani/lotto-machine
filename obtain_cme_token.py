#!/usr/bin/env python3
"""
Obtain CME FedWatch API Token using Google Cloud Workload Identity Federation

This script:
1. Uses Google Cloud SDK or API to authenticate
2. Exchanges credentials for access token
3. Tests the token with CME API
4. Saves token for later use
"""

import sys
import json
import os
import subprocess
import logging
import requests
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# CME API Configuration
CME_BASE_URL = "https://markets.api.cmegroup.com/fedwatch/v1"
CME_API_ID = "api_fjk"
CME_TOKEN = "552615"
CME_ACCESS_CODE = "093639"

# Google Cloud WIF Configuration
GOOGLE_WIF_AUDIENCE = "//iam.googleapis.com/projects/282603793014/locations/global/workloadIdentityPools/iamwip-cmegroup/providers/customer-federation"
TOKEN_FILE = "/tmp/token"


def method1_gcloud_cli() -> Optional[str]:
    """
    Method 1: Use gcloud CLI to get identity token
    """
    logger.info("🔐 METHOD 1: Using gcloud CLI to get identity token")
    
    try:
        # Check if gcloud is installed
        result = subprocess.run(['which', 'gcloud'], capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install")
            return None
        
        # Get identity token using gcloud
        cmd = [
            'gcloud', 'auth', 'print-identity-token',
            '--audiences', GOOGLE_WIF_AUDIENCE
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            id_token = result.stdout.strip()
            if id_token:
                logger.info("✅ Successfully obtained identity token from gcloud")
                
                # Save to token file
                token_data = {"id_token": id_token}
                with open(TOKEN_FILE, 'w') as f:
                    json.dump(token_data, f, indent=2)
                os.chmod(TOKEN_FILE, 0o600)
                logger.info(f"✅ Token saved to {TOKEN_FILE}")
                
                return id_token
        else:
            logger.warning(f"gcloud command failed: {result.stderr}")
            
    except FileNotFoundError:
        logger.warning("gcloud CLI not found")
    except subprocess.TimeoutExpired:
        logger.warning("gcloud command timed out")
    except Exception as e:
        logger.warning(f"gcloud method error: {e}")
    
    return None


def method2_google_auth_library() -> Optional[str]:
    """
    Method 2: Use Google Auth library with service account or default credentials
    """
    logger.info("🔐 METHOD 2: Using Google Auth library")
    
    try:
        from google.auth import default
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
        import google.auth.external_account
        
        # Try to use default credentials
        try:
            credentials, project = default()
            logger.info("✅ Loaded default Google Cloud credentials")
            
            # Request identity token
            request = Request()
            id_token = credentials.id_token
            if not id_token:
                # Try to refresh to get id_token
                credentials.refresh(request)
                id_token = getattr(credentials, 'id_token', None)
            
            if id_token:
                logger.info("✅ Successfully obtained identity token from default credentials")
                
                # Save to token file
                token_data = {"id_token": id_token}
                with open(TOKEN_FILE, 'w') as f:
                    json.dump(token_data, f, indent=2)
                os.chmod(TOKEN_FILE, 0o600)
                logger.info(f"✅ Token saved to {TOKEN_FILE}")
                
                return id_token
                
        except Exception as e:
            logger.debug(f"Default credentials failed: {e}")
        
        # Try external account (Workload Identity Federation)
        try:
            config = {
                "type": "external_account",
                "audience": GOOGLE_WIF_AUDIENCE,
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
            
            # If token file doesn't exist, we need to get it first
            if not os.path.exists(TOKEN_FILE):
                logger.warning(f"Token file {TOKEN_FILE} doesn't exist. Need to obtain id_token first.")
                return None
            
            credentials = google.auth.external_account.from_info(config)
            request = Request()
            credentials.refresh(request)
            
            access_token = credentials.token
            if access_token:
                logger.info("✅ Successfully obtained access token from external account")
                return access_token
                
        except Exception as e:
            logger.debug(f"External account method failed: {e}")
            import traceback
            traceback.print_exc()
            
    except ImportError:
        logger.warning("google-auth library not installed. Install: pip install google-auth")
    except Exception as e:
        logger.warning(f"Google Auth library method error: {e}")
        import traceback
        traceback.print_exc()
    
    return None


def method3_exchange_id_token_for_access_token(id_token: str) -> Optional[str]:
    """
    Method 3: Exchange id_token for access token via Google STS
    """
    logger.info("🔐 METHOD 3: Exchanging id_token for access token")
    
    try:
        from google.auth.transport.requests import Request
        
        # Use Google STS to exchange id_token for access token
        sts_url = "https://sts.googleapis.com/v1/token"
        
        data = {
            'grant_type': 'urn:ietf:params:oauth:grant-type:token-exchange',
            'subject_token': id_token,
            'subject_token_type': 'urn:ietf:params:oauth:token-type:jwt',
            'audience': GOOGLE_WIF_AUDIENCE,
            'scope': 'https://www.googleapis.com/auth/cloud-platform'
        }
        
        response = requests.post(sts_url, data=data, timeout=15)
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            if access_token:
                logger.info("✅ Successfully exchanged id_token for access token")
                return access_token
        else:
            logger.warning(f"Token exchange failed: {response.status_code} - {response.text[:200]}")
            
    except Exception as e:
        logger.warning(f"Token exchange error: {e}")
        import traceback
        traceback.print_exc()
    
    return None


def test_cme_api(access_token: str) -> bool:
    """
    Test the access token with CME FedWatch API
    """
    logger.info("🧪 Testing access token with CME FedWatch API...")
    
    try:
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Try /meetings endpoint first (simpler)
        url = f"{CME_BASE_URL}/meetings"
        logger.info(f"   Testing: GET {url}")
        
        response = requests.get(url, headers=headers, timeout=15)
        
        logger.info(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("✅ SUCCESS! CME API responded with 200 OK")
            try:
                data = response.json()
                logger.info(f"   Response type: {type(data)}")
                if isinstance(data, dict):
                    logger.info(f"   Keys: {list(data.keys())[:10]}")
                    logger.info(f"   Sample: {json.dumps(data, indent=2)[:500]}")
                elif isinstance(data, list):
                    logger.info(f"   List length: {len(data)}")
                    if len(data) > 0:
                        logger.info(f"   First item: {json.dumps(data[0], indent=2)[:300]}")
            except:
                logger.info(f"   Response text: {response.text[:500]}")
            
            # Save access token for later use
            token_file = "/tmp/cme_access_token.txt"
            with open(token_file, 'w') as f:
                f.write(access_token)
            os.chmod(token_file, 0o600)
            logger.info(f"✅ Access token saved to {token_file}")
            
            return True
        elif response.status_code == 401:
            logger.error("❌ 401 Unauthorized - Token is invalid or expired")
            logger.error(f"   Response: {response.text[:200]}")
        elif response.status_code == 403:
            logger.error("❌ 403 Forbidden - Check IP whitelist or API permissions")
            logger.error(f"   Response: {response.text[:200]}")
        else:
            logger.warning(f"⚠️ API returned {response.status_code}")
            logger.warning(f"   Response: {response.text[:300]}")
            
    except Exception as e:
        logger.error(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
    
    return False


def main():
    """Main function"""
    print("=" * 70)
    print("🔑 OBTAINING CME FEDWATCH API TOKEN")
    print("=" * 70)
    print()
    
    access_token = None
    id_token = None
    
    # Step 1: Get id_token
    print("📋 STEP 1: Get Identity Token")
    print("-" * 50)
    
    # Try gcloud CLI first
    id_token = method1_gcloud_cli()
    
    if not id_token:
        # Try Google Auth library
        id_token = method2_google_auth_library()
    
    if not id_token and os.path.exists(TOKEN_FILE):
        # Try reading from existing token file
        try:
            with open(TOKEN_FILE, 'r') as f:
                token_data = json.load(f)
            id_token = token_data.get('id_token')
            if id_token and id_token != "YOUR_ID_TOKEN_HERE":
                logger.info(f"✅ Loaded id_token from existing {TOKEN_FILE}")
        except Exception as e:
            logger.warning(f"Failed to read token file: {e}")
    
    if not id_token:
        print("\n⚠️ Could not obtain id_token automatically")
        print("\n📝 Manual Steps:")
        print("   1. Use Google Cloud Console or CLI to authenticate")
        print("   2. Get identity token for audience:")
        print(f"      {GOOGLE_WIF_AUDIENCE}")
        print("   3. Save to /tmp/token as:")
        print('      {"id_token": "<your_identity_token>"}')
        print("\n   Or run:")
        print(f"   gcloud auth print-identity-token --audiences {GOOGLE_WIF_AUDIENCE}")
        return
    
    # Step 2: Exchange id_token for access token
    print("\n📋 STEP 2: Exchange Identity Token for Access Token")
    print("-" * 50)
    
    # Try using Google Auth library to get access token
    try:
        from google.auth import load_credentials_from_dict
        from google.auth.transport.requests import Request
        
        config = {
            "universe_domain": "googleapis.com",
            "type": "external_account",
            "audience": GOOGLE_WIF_AUDIENCE,
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
            logger.info("✅ Successfully obtained access token")
    except Exception as e:
        logger.warning(f"Failed to get access token via Google Auth: {e}")
        # Try direct exchange
        access_token = method3_exchange_id_token_for_access_token(id_token)
    
    if not access_token:
        print("\n⚠️ Could not obtain access token")
        print("   The id_token may need to be exchanged manually")
        return
    
    # Step 3: Test with CME API
    print("\n📋 STEP 3: Test Access Token with CME API")
    print("-" * 50)
    
    if test_cme_api(access_token):
        print("\n" + "=" * 70)
        print("✅ SUCCESS! CME FEDWATCH API IS LIVE!")
        print("=" * 70)
        print("\n📝 Next Steps:")
        print("   1. Access token saved to /tmp/cme_access_token.txt")
        print("   2. Use CMEFedWatchClient to fetch data")
        print("   3. Run: python3 test_cme_fedwatch.py")
    else:
        print("\n" + "=" * 70)
        print("⚠️ TOKEN OBTAINED BUT API TEST FAILED")
        print("=" * 70)
        print("\n📝 Troubleshooting:")
        print("   1. Check if IP address is whitelisted")
        print("   2. Verify API ID, Token, Access Code are correct")
        print("   3. Check CME documentation for exact endpoint URLs")
        print("   4. Contact CME support if needed")


if __name__ == "__main__":
    main()



