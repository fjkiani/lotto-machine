"""
CME FedWatch Intraday REST API Client

Uses Google Cloud Workload Identity Federation for authentication.

Documentation:
- https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457087044/CME+Market+Data+REST+APIs
- CME FedWatch Intraday API

Authentication:
- Google Cloud Workload Identity Federation
- Token file at /tmp/token containing id_token
- API ID: api_fjk
- Token: 552615
- Access Code: 093639
"""

import logging
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from google.auth import load_credentials_from_dict
    from google.auth.transport.requests import Request
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False
    logger.warning("google-auth library not available. Install: pip install google-auth")


class CMEFedWatchClient:
    """
    CME FedWatch Intraday REST API Client.
    
    Uses Google Cloud Workload Identity Federation for authentication.
    """
    
    # CME FedWatch API endpoints (from official CME documentation)
    # Base URL: https://markets.api.cmegroup.com/fedwatch/v1
    # Documentation: https://cmegroupclientsite.atlassian.net/wiki/display/EPICSANDBOX/CME+FedWatch+API
    BASE_URL = "https://markets.api.cmegroup.com/fedwatch/v1"
    FEDWATCH_FORECASTS_ENDPOINT = f"{BASE_URL}/forecasts"  # Get forecasts (intraday)
    FEDWATCH_MEETINGS_ENDPOINT = f"{BASE_URL}/meetings"  # Get meetings
    FEDWATCH_INTRADAY_ENDPOINT = FEDWATCH_FORECASTS_ENDPOINT  # Alias for intraday
    FEDWATCH_EOD_ENDPOINT = f"{BASE_URL}/forecasts"  # EOD may use same endpoint with date param
    
    def __init__(
        self,
        credential_config: Optional[Dict] = None,
        token_file: str = "/tmp/token",
        api_id: Optional[str] = None,
        token: Optional[str] = None,
        access_code: Optional[str] = None
    ):
        """
        Initialize CME FedWatch Client.
        
        Args:
            credential_config: Google Cloud Workload Identity Federation config dict
            token_file: Path to token file containing id_token
            api_id: CME API ID (optional, may be needed for some endpoints)
            token: CME Token (optional)
            access_code: CME Access Code (optional)
        """
        self.token_file = token_file
        self.api_id = api_id or os.getenv('CME_API_ID')
        self.token = token or os.getenv('CME_API_TOKEN')
        self.access_code = access_code or os.getenv('CME_ACCESS_CODE')
        
        # Default credential config (can be overridden)
        self.credential_config = credential_config or {
            "universe_domain": "googleapis.com",
            "type": "external_account",
            "audience": "//iam.googleapis.com/projects/282603793014/locations/global/workloadIdentityPools/iamwip-cmegroup/providers/customer-federation",
            "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
            "token_url": "https://sts.googleapis.com/v1/token",
            "credential_source": {
                "file": self.token_file,
                "format": {
                    "type": "json",
                    "subject_token_field_name": "id_token"
                }
            },
            "token_info_url": "https://sts.googleapis.com/v1/introspect"
        }
        
        # Update token file path in config
        self.credential_config['credential_source']['file'] = self.token_file
        
        # Initialize Google Auth credentials
        self.credentials = None
        self._init_credentials()
        
        logger.info("🏦 CME FedWatch Client initialized")
        if self.api_id:
            logger.info(f"   API ID: {self.api_id}")
    
    def _init_credentials(self):
        """Initialize Google Cloud Workload Identity Federation credentials"""
        if not GOOGLE_AUTH_AVAILABLE:
            logger.error("google-auth not available. Install: pip install google-auth")
            # Fallback: Try to read token file directly
            self._load_token_file()
            return
        
        try:
            # Method 1: Try loading credentials from dict (for external accounts)
            try:
                self.credentials, _ = load_credentials_from_dict(self.credential_config)
                logger.info("✅ Loaded Google Cloud Workload Identity Federation credentials")
                
                # Refresh to get access token
                if not self.credentials.valid:
                    self.credentials.refresh(Request())
                logger.info("✅ Credentials refreshed successfully")
                return
            except Exception as e1:
                logger.debug(f"load_credentials_from_dict failed: {e1}")
            
            # Method 2: Fallback - read token file directly
            self._load_token_file()
            
        except Exception as e:
            logger.error(f"Failed to initialize credentials: {e}")
            import traceback
            traceback.print_exc()
            self._load_token_file()
    
    def _load_token_file(self):
        """Load token from file as fallback"""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                id_token = token_data.get('id_token')
                if id_token:
                    logger.info(f"✅ Loaded token from {self.token_file} (fallback method)")
                    self.id_token = id_token
                else:
                    logger.warning(f"Token file {self.token_file} does not contain 'id_token'")
            except Exception as e:
                logger.error(f"Failed to read token file: {e}")
        else:
            logger.warning(f"Token file not found: {self.token_file}")
    
    def _get_access_token(self) -> Optional[str]:
        """Get access token for API calls"""
        try:
            if self.credentials and self.credentials.valid:
                return self.credentials.token
            elif self.credentials:
                # Refresh if needed
                self.credentials.refresh(Request())
                return self.credentials.token
            elif hasattr(self, 'id_token'):
                # Fallback: Use id_token directly
                return self.id_token
        except Exception as e:
            logger.error(f"Failed to get access token: {e}")
        return None
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Make authenticated request to CME API.
        
        Args:
            endpoint: API endpoint URL
            params: Query parameters
        
        Returns:
            Response JSON data or None if failed
        """
        try:
            import requests
            
            # Get access token
            access_token = self._get_access_token()
            if not access_token:
                logger.error("No access token available")
                return None
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'User-Agent': 'CME-FedWatch-Client/1.0'
            }
            
            # Add CME-specific headers if available
            if self.api_id:
                headers['X-CME-API-ID'] = self.api_id
            if self.access_code:
                headers['X-CME-ACCESS-CODE'] = self.access_code
            
            # Make request
            response = requests.get(endpoint, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"✅ Successfully fetched data from {endpoint}")
                    return data
                except json.JSONDecodeError:
                    logger.warning(f"Response is not JSON: {response.text[:200]}")
                    return None
            elif response.status_code == 401:
                logger.error("401 Unauthorized - Check credentials and token file")
                logger.error(f"Response: {response.text[:200]}")
                return None
            elif response.status_code == 403:
                logger.error("403 Forbidden - Check API permissions and IP whitelist")
                logger.error(f"Response: {response.text[:200]}")
                return None
            else:
                logger.warning(f"API returned {response.status_code}: {response.text[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"Request failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_fedwatch_intraday(self, meeting_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get FedWatch Intraday data (forecasts).
        
        Endpoint: GET /forecasts
        Documentation: https://cmegroupclientsite.atlassian.net/wiki/display/EPICSANDBOX/CME+FedWatch+API
        
        Args:
            meeting_date: FOMC meeting date (YYYY-MM-DD). If None, gets current meeting.
        
        Returns:
            Dictionary with FedWatch intraday probability data
        """
        params = {}
        if meeting_date:
            params['meetingDate'] = meeting_date
        
        # Use /forecasts endpoint for intraday data
        return self._make_request(self.FEDWATCH_FORECASTS_ENDPOINT, params)
    
    def get_fedwatch_meetings(self) -> Optional[Dict[str, Any]]:
        """
        Get list of FOMC meetings.
        
        Endpoint: GET /meetings
        
        Returns:
            Dictionary with list of FOMC meetings
        """
        return self._make_request(self.FEDWATCH_MEETINGS_ENDPOINT)
    
    def get_fedwatch_eod(self, meeting_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get FedWatch End-of-Day data.
        
        Note: EOD may use the same /forecasts endpoint with date parameter.
        
        Args:
            meeting_date: FOMC meeting date (YYYY-MM-DD). If None, gets current meeting.
        
        Returns:
            Dictionary with FedWatch EOD probability data
        """
        params = {}
        if meeting_date:
            params['meetingDate'] = meeting_date
        
        # EOD may use same endpoint as intraday
        return self._make_request(self.FEDWATCH_FORECASTS_ENDPOINT, params)
    
    def parse_probabilities(self, data: Dict[str, Any]) -> Dict[str, float]:
        """
        Parse FedWatch probability data into a clean format.
        
        Returns:
            Dictionary with rate change probabilities
        """
        try:
            probabilities = {}
            
            # CME FedWatch API format may vary - handle multiple structures
            if 'probabilities' in data:
                probs = data['probabilities']
            elif 'data' in data and isinstance(data['data'], list):
                probs = data['data']
            elif isinstance(data, list):
                probs = data
            else:
                logger.warning(f"Unknown data format: {list(data.keys())}")
                return {}
            
            for prob in probs:
                # Handle different field names
                rate_change = (
                    prob.get('rateChange') or 
                    prob.get('rate_change') or 
                    prob.get('change') or 
                    '0'
                )
                prob_value = (
                    prob.get('probability') or 
                    prob.get('prob') or 
                    prob.get('value') or 
                    0.0
                )
                
                # Map rate changes to keys
                if rate_change == '-50' or rate_change == '-0.50':
                    probabilities['cut_50bp'] = float(prob_value)
                elif rate_change == '-25' or rate_change == '-0.25':
                    probabilities['cut_25bp'] = float(prob_value)
                elif rate_change == '0' or rate_change == '0.00':
                    probabilities['hold'] = float(prob_value)
                elif rate_change == '25' or rate_change == '0.25':
                    probabilities['hike_25bp'] = float(prob_value)
                elif rate_change == '50' or rate_change == '0.50':
                    probabilities['hike_50bp'] = float(prob_value)
            
            return probabilities
            
        except Exception as e:
            logger.error(f"Failed to parse probabilities: {e}")
            return {}
    
    def get_cut_probability(self, meeting_date: Optional[str] = None) -> Optional[float]:
        """
        Get the probability of a rate cut (25bp or 50bp combined).
        
        Returns:
            Combined probability of rate cut (0-100) or None if failed
        """
        data = self.get_fedwatch_intraday(meeting_date)
        if not data:
            return None
        
        probs = self.parse_probabilities(data)
        
        cut_prob = (
            probs.get('cut_50bp', 0.0) +
            probs.get('cut_25bp', 0.0)
        )
        
        return cut_prob if cut_prob > 0 else None

