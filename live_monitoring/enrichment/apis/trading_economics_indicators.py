"""
Trading Economics Indicators Discovery
======================================

Discovers and maps available indicators from Trading Economics API.
"""

import logging
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class TradingEconomicsIndicatorDiscovery:
    """
    Discover available indicators from Trading Economics.
    
    Maps indicators by category and allows keyword search.
    """
    
    API_BASE_URL = "https://api.tradingeconomics.com/indicators"
    
    def __init__(self, api_credentials: str = "guest:guest"):
        """
        Initialize indicator discovery.
        
        Args:
            api_credentials: API credentials (format: "key:secret" or "guest:guest")
        """
        self.credentials = api_credentials
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        logger.info("✅ TradingEconomicsIndicatorDiscovery initialized")
    
    def discover_indicators(self, country: str = "united states") -> List[Dict[str, Any]]:
        """
        Discover indicators for a country.
        
        Args:
            country: Country name (e.g., "united states", "germany")
        
        Returns:
            List of indicator categories
        """
        params = {'c': self.credentials, 's': country}
        
        try:
            response = self.session.get(self.API_BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching indicators: {e}")
            return []
    
    def map_by_category(self, country: str = "united states") -> Dict[str, List[str]]:
        """
        Map indicators by category group.
        
        Args:
            country: Country name
        
        Returns:
            Dictionary mapping category groups to indicator lists
        """
        indicators = self.discover_indicators(country)
        
        category_map = {}
        for ind in indicators:
            group = ind.get('CategoryGroup', 'Other')
            if group not in category_map:
                category_map[group] = []
            category_map[group].append(ind.get('Category'))
        
        return category_map
    
    def find_indicators_by_keyword(self, keyword: str, country: str = "united states") -> List[Dict[str, Any]]:
        """
        Find indicators matching a keyword.
        
        Args:
            keyword: Search keyword (e.g., "inflation", "gdp", "employment")
            country: Country name
        
        Returns:
            List of matching indicators
        """
        indicators = self.discover_indicators(country)
        
        matching = []
        keyword_lower = keyword.lower()
        
        for ind in indicators:
            category = ind.get('Category', '').lower()
            group = ind.get('CategoryGroup', '').lower()
            
            if keyword_lower in category or keyword_lower in group:
                matching.append(ind)
        
        return matching
    
    def get_category_groups(self, country: str = "united states") -> List[str]:
        """
        Get list of available category groups.
        
        Args:
            country: Country name
        
        Returns:
            List of category group names
        """
        indicators = self.discover_indicators(country)
        
        groups = set()
        for ind in indicators:
            group = ind.get('CategoryGroup')
            if group:
                groups.add(group)
        
        return sorted(list(groups))
    
    def get_indicators_by_group(self, group: str, country: str = "united states") -> List[str]:
        """
        Get indicators for a specific category group.
        
        Args:
            group: Category group name (e.g., "Money", "Housing", "Employment")
            country: Country name
        
        Returns:
            List of indicator names in that group
        """
        indicators = self.discover_indicators(country)
        
        matching = []
        for ind in indicators:
            if ind.get('CategoryGroup', '').lower() == group.lower():
                matching.append(ind.get('Category'))
        
        return matching


# Test when run directly
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("📊 TESTING TRADING ECONOMICS INDICATOR DISCOVERY")
    print("=" * 70)
    
    discovery = TradingEconomicsIndicatorDiscovery()
    
    print("\n1️⃣ Testing: Discover Indicators (US)")
    indicators = discovery.discover_indicators("united states")
    print(f"✅ Found {len(indicators)} indicator categories")
    
    if indicators:
        print(f"\n📊 Sample Indicators:")
        for ind in indicators[:10]:
            print(f"   {ind.get('Category')} ({ind.get('CategoryGroup')})")
    
    print("\n2️⃣ Testing: Map by Category")
    category_map = discovery.map_by_category("united states")
    print(f"✅ Found {len(category_map)} category groups:")
    for group, indicators_list in list(category_map.items())[:5]:
        print(f"   {group}: {len(indicators_list)} indicators")
    
    print("\n3️⃣ Testing: Find by Keyword (inflation)")
    inflation_indicators = discovery.find_indicators_by_keyword("inflation", "united states")
    print(f"✅ Found {len(inflation_indicators)} inflation-related indicators")
    for ind in inflation_indicators[:5]:
        print(f"   {ind.get('Category')}")
    
    print("\n4️⃣ Testing: Get Category Groups")
    groups = discovery.get_category_groups("united states")
    print(f"✅ Available category groups: {', '.join(groups[:10])}")
    
    print("\n" + "=" * 70)
    print("✅ INDICATOR DISCOVERY TEST COMPLETE")





