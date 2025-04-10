import os
import logging
import requests
import time
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Force reload environment variables
load_dotenv(override=True)

class YahooFinanceInsightsConnector:
    """Connector for Yahoo Finance Real-Time Insights API from RapidAPI."""
    
    BASE_URL = "https://yahoo-finance-real-time1.p.rapidapi.com"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the connector with API credentials."""
        # Force reload environment variables
        load_dotenv(override=True)
        
        self.api_key = api_key or os.getenv("RAPIDAPI_KEY")
        if not self.api_key:
            raise ValueError("RapidAPI key is required. Set RAPIDAPI_KEY environment variable or pass to constructor.")
        
        # Log the first few characters of the API key for verification
        logger.info(f"Using RapidAPI key starting with: {self.api_key[:8]}...")
        
        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "yahoo-finance-real-time1.p.rapidapi.com"
        }
        
        # Clear any existing cache
        self._cache = {}
        self._cache_timestamps = {}
        logger.info("Cache cleared on initialization")
    
    def _get_from_cache(self, key: str, max_age_seconds: int = 300) -> Optional[Dict]:
        """Get data from cache if it exists and is not expired."""
        if key in self._cache:
            timestamp = self._cache_timestamps.get(key, 0)
            if time.time() - timestamp < max_age_seconds:
                return self._cache[key]
        return None
    
    def _store_in_cache(self, key: str, data: Dict) -> None:
        """Store data in cache with current timestamp."""
        self._cache[key] = data
        self._cache_timestamps[key] = time.time()
    
    def _fetch_data(self, endpoint: str, params: Dict = None) -> Dict:
        """Fetch data from the API."""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            error_msg = f"Error fetching data from {endpoint}: {e.response.status_code}"
            if e.response.text:
                error_msg += f" - {e.response.text}"
            logger.error(error_msg)
            return {"error": f"API request failed with status {e.response.status_code}"}
        except requests.RequestException as e:
            logger.error(f"Error fetching data from {endpoint}: {str(e)}")
            return {"error": f"API request failed: {str(e)}"}
        except ValueError as e:
            logger.error(f"Error parsing response from {endpoint}: {str(e)}")
            return {"error": f"Failed to parse API response: {str(e)}"}
    
    def get_stock_insights(self, symbol: str, region: str = "US", lang: str = "en-US") -> Dict:
        """
        Get detailed insights for a stock including technical patterns, key statistics,
        analyst recommendations, and upcoming events.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "SPY")
            region: Region code (default "US")
            lang: Language code (default "en-US")
            
        Returns:
            Dictionary containing stock insights data
        """
        cache_key = f"stock_insights_{symbol}_{region}_{lang}"
        cached_data = self._get_from_cache(cache_key, 900)  # Cache for 15 minutes
        if cached_data:
            return cached_data
        
        params = {
            "symbol": symbol,
            "region": region,
            "lang": lang
        }
        
        response = self._fetch_data("/stock/get-insights", params)
        
        self._store_in_cache(cache_key, response)
        return response
        
    def extract_key_insights(self, insights_data: Dict) -> Dict:
        """
        Extract and organize key insights from the API response.
        
        Args:
            insights_data: Raw API response from get_stock_insights
            
        Returns:
            Dictionary with organized key insights
        """
        if "error" in insights_data:
            return {"error": insights_data["error"]}
        
        result = {
            "technical_events": {},
            "key_technicals": {},
            "valuation": {},
            "recommendation": {},
            "upcoming_events": {},
            "risk": {}
        }
        
        # Process response data - updated based on actual API response structure
        try:
            # The actual path in the JSON is finance > result (object, not array)
            instrument_info = insights_data.get("finance", {}).get("result", {}).get("instrumentInfo", {})
            
            # Extract technical events data
            tech_events = instrument_info.get("technicalEvents", {})
            if tech_events:
                # Updated to match the actual response structure
                short_term = tech_events.get("shortTermOutlook", {})
                mid_term = tech_events.get("intermediateTermOutlook", {})
                long_term = tech_events.get("longTermOutlook", {})
                
                result["technical_events"] = {
                    "short_term": short_term.get("direction", "") + " - " + short_term.get("scoreDescription", ""),
                    "mid_term": mid_term.get("direction", "") + " - " + mid_term.get("scoreDescription", ""),
                    "long_term": long_term.get("direction", "") + " - " + long_term.get("scoreDescription", "")
                }
            
            # Extract key technicals
            key_tech = instrument_info.get("keyTechnicals", {})
            if key_tech:
                result["key_technicals"] = {
                    "support": key_tech.get("support", ""),
                    "resistance": key_tech.get("resistance", ""),
                    "stop_loss": key_tech.get("stopLoss", "")
                }
            
            # Extract valuation data
            valuation = instrument_info.get("valuation", {})
            if valuation:
                result["valuation"] = {
                    "description": valuation.get("description", ""),
                    "provider": valuation.get("provider", "")
                }
            
            # Extract events for upcoming events
            events = insights_data.get("finance", {}).get("result", {}).get("events", [])
            if events:
                result["upcoming_events"]["events"] = []
                for event in events:
                    result["upcoming_events"]["events"].append({
                        "type": event.get("eventType", ""),
                        "start_date": event.get("startDate", ""),
                        "end_date": event.get("endDate", "")
                    })
            
            # Extract reports for recommendations and analysis
            reports = insights_data.get("finance", {}).get("result", {}).get("reports", [])
            if reports and len(reports) > 0:
                latest_report = reports[0]  # Get the most recent report
                result["recommendation"] = {
                    "provider": latest_report.get("provider", ""),
                    "rating": latest_report.get("investmentRating", ""),
                    "target_price": latest_report.get("targetPrice", ""),
                    "title": latest_report.get("title", ""),
                    "date": latest_report.get("reportDate", "")
                }
                
                # Add all reports for more detailed analysis
                result["reports"] = []
                for report in reports[:5]:  # Limit to 5 most recent reports
                    result["reports"].append({
                        "provider": report.get("provider", ""),
                        "rating": report.get("investmentRating", ""),
                        "target_price": report.get("targetPrice", ""),
                        "title": report.get("title", ""),
                        "date": report.get("reportDate", "")
                    })
            
        except Exception as e:
            logger.error(f"Error extracting insights data: {str(e)}")
            return {"error": f"Failed to extract insights: {str(e)}"}
        
        return result
    
    def get_condensed_insights(self, symbol: str) -> Dict:
        """
        Get condensed, analysis-ready insights for a stock.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "SPY")
            
        Returns:
            Dictionary with key insights in an analysis-friendly format
        """
        insights = self.get_stock_insights(symbol)
        if "error" in insights:
            return insights
        
        return self.extract_key_insights(insights) 