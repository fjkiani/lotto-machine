"""
CME Group API Client

Uses CME Group's API ID, Token, and Access Code authentication.

Authentication:
- API ID: Your CME API identifier
- Token: Your API token (password)
- Access Code: Additional security code

CME API Documentation:
- https://www.cmegroup.com/confluence/display/EPICSANDBOX/CME+Data+Mine+API
"""

import logging
import json
import os
import base64
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class CMEAPIClient:
    """
    CME Group API Client for FedWatch data.
    
    Uses CME API ID, Token, and Access Code authentication.
    """
    
    # CME API base URLs
    BASE_URL = "https://www.cmegroup.com"
    FEDWATCH_ENDPOINT = f"{BASE_URL}/CmeWS/mvc/FedWatchTool/FedWatch"
    FEDWATCH_PROBABILITIES = f"{BASE_URL}/CmeWS/mvc/FedWatchTool/FedWatch/probabilities"
    
    def __init__(
        self,
        api_id: Optional[str] = None,
        token: Optional[str] = None,
        access_code: Optional[str] = None,
        credential_path: Optional[str] = None
    ):
        """
        Initialize CME API Client.
        
        Args:
            api_id: CME API ID
            token: CME API Token
            access_code: CME Access Code
            credential_path: Path to JSON file with credentials
        """
        # Load credentials
        if credential_path and os.path.exists(credential_path):
            self._load_credentials_from_file(credential_path)
        elif api_id and token and access_code:
            self.api_id = api_id
            self.token = token
            self.access_code = access_code
        else:
            # Try environment variables
            self.api_id = os.getenv('CME_API_ID')
            self.token = os.getenv('CME_API_TOKEN')
            self.access_code = os.getenv('CME_ACCESS_CODE')
            
            if not all([self.api_id, self.token, self.access_code]):
                logger.warning("CME credentials not provided. Set CME_API_ID, CME_API_TOKEN, CME_ACCESS_CODE")
        
        # Generate authentication header
        self.auth_header = self._generate_auth_header()
        
        logger.info("🏦 CME API Client initialized")
        if self.api_id:
            logger.info(f"   API ID: {self.api_id}")
    
    def _load_credentials_from_file(self, path: str):
        """Load credentials from JSON file"""
        try:
            with open(path, 'r') as f:
                creds = json.load(f)
            
            self.api_id = creds.get('api_id') or creds.get('API_ID')
            self.token = creds.get('token') or creds.get('TOKEN')
            self.access_code = creds.get('access_code') or creds.get('ACCESS_CODE')
            
            if not all([self.api_id, self.token, self.access_code]):
                logger.error(f"Missing credentials in {path}. Need: api_id, token, access_code")
            else:
                logger.info(f"✅ Loaded credentials from {path}")
                
        except Exception as e:
            logger.error(f"Failed to load credentials from {path}: {e}")
    
    def _generate_auth_header(self) -> Optional[str]:
        """
        Generate CME API authentication header.
        
        CME typically uses Basic Auth or custom header format:
        - Basic Auth: base64(api_id:token)
        - Or custom header with API ID, Token, Access Code
        """
        if not all([self.api_id, self.token]):
            return None
        
        try:
            # Method 1: Basic Auth (API ID:Token)
            credentials = f"{self.api_id}:{self.token}"
            encoded = base64.b64encode(credentials.encode()).decode()
            return f"Basic {encoded}"
        except Exception as e:
            logger.error(f"Failed to generate auth header: {e}")
            return None
    
    def get_fedwatch_probabilities(self, meeting_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get FedWatch probability data.
        
        Args:
            meeting_date: FOMC meeting date (YYYY-MM-DD). If None, gets current probabilities.
        
        Returns:
            Dictionary with probability data or None if failed
        """
        try:
            import requests
            
            # Build URL
            url = self.FEDWATCH_PROBABILITIES
            if meeting_date:
                url += f"?meetingDate={meeting_date}"
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'CME-API-Client/1.0',
                'Content-Type': 'application/json'
            }
            
            # Add authentication
            if self.auth_header:
                headers['Authorization'] = self.auth_header
            
            # Add API ID and Access Code as headers (CME may require this format)
            if self.api_id:
                headers['X-CME-API-ID'] = self.api_id
            if self.access_code:
                headers['X-CME-ACCESS-CODE'] = self.access_code
            
            # Make request
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"✅ Fetched FedWatch probabilities")
                    return data
                except json.JSONDecodeError:
                    # May be HTML or other format
                    logger.warning(f"Response is not JSON: {response.text[:200]}")
                    return None
            else:
                logger.warning(f"⚠️ FedWatch API returned {response.status_code}: {response.text[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to fetch FedWatch probabilities: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_fedwatch_tool_data(self) -> Optional[Dict[str, Any]]:
        """
        Get FedWatch tool data (full tool state).
        
        Returns:
            Dictionary with FedWatch tool data or None if failed
        """
        try:
            import requests
            
            url = self.FEDWATCH_ENDPOINT
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'CME-API-Client/1.0',
                'Content-Type': 'application/json'
            }
            
            # Add authentication
            if self.auth_header:
                headers['Authorization'] = self.auth_header
            
            if self.api_id:
                headers['X-CME-API-ID'] = self.api_id
            if self.access_code:
                headers['X-CME-ACCESS-CODE'] = self.access_code
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"✅ Fetched FedWatch tool data")
                    return data
                except json.JSONDecodeError:
                    logger.warning(f"Response is not JSON: {response.text[:200]}")
                    return None
            else:
                logger.warning(f"⚠️ FedWatch API returned {response.status_code}: {response.text[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to fetch FedWatch tool data: {e}")
            return None
    
    def parse_fedwatch_probabilities(self, data: Dict[str, Any]) -> Dict[str, float]:
        """
        Parse FedWatch probability data into a clean format.
        
        Returns:
            Dictionary with rate change probabilities
            Example: {
                'cut_25bp': 89.0,
                'cut_50bp': 10.0,
                'hold': 1.0,
                'hike_25bp': 0.0
            }
        """
        try:
            probabilities = {}
            
            # CME FedWatch typically returns data in this format:
            # {
            #   "meetingDate": "2025-01-29",
            #   "probabilities": [
            #     {"rateChange": "-50", "probability": 10.0},
            #     {"rateChange": "-25", "probability": 89.0},
            #     {"rateChange": "0", "probability": 1.0}
            #   ]
            # }
            
            if 'probabilities' in data:
                for prob in data['probabilities']:
                    rate_change = prob.get('rateChange', '0')
                    prob_value = prob.get('probability', 0.0)
                    
                    # Map rate changes to keys
                    if rate_change == '-50':
                        probabilities['cut_50bp'] = prob_value
                    elif rate_change == '-25':
                        probabilities['cut_25bp'] = prob_value
                    elif rate_change == '0':
                        probabilities['hold'] = prob_value
                    elif rate_change == '25':
                        probabilities['hike_25bp'] = prob_value
                    elif rate_change == '50':
                        probabilities['hike_50bp'] = prob_value
            
            return probabilities
            
        except Exception as e:
            logger.error(f"Failed to parse FedWatch probabilities: {e}")
            return {}
    
    def get_cut_probability(self, meeting_date: Optional[str] = None) -> Optional[float]:
        """
        Get the probability of a rate cut (25bp or 50bp combined).
        
        Returns:
            Combined probability of rate cut (0-100) or None if failed
        """
        data = self.get_fedwatch_probabilities(meeting_date)
        if not data:
            return None
        
        probs = self.parse_fedwatch_probabilities(data)
        
        cut_prob = (
            probs.get('cut_50bp', 0.0) +
            probs.get('cut_25bp', 0.0)
        )
        
        return cut_prob if cut_prob > 0 else None
