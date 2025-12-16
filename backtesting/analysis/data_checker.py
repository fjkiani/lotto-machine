"""
🔍 DATA AVAILABILITY CHECKER
Checks if data sources are actually returning data
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

class DataAvailabilityChecker:
    """Checks actual data availability from APIs"""
    
    def __init__(self):
        self.results = {}
    
    def check_all_sources(self, date: str, symbol: str = "SPY") -> Dict[str, any]:
        """Check all data sources for a specific date"""
        checks = {
            'dp_levels': self._check_dp_levels(date, symbol),
            'dp_prints': self._check_dp_prints(date, symbol),
            'price_data': self._check_price_data(date, symbol),
            'market_hours': self._check_market_hours(date),
        }
        
        return checks
    
    def _check_dp_levels(self, date: str, symbol: str) -> Dict[str, any]:
        """Check if DP levels are available"""
        try:
            from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
            import os
            
            api_key = os.getenv('CHARTEXCHANGE_API_KEY')
            if not api_key:
                return {
                    'available': False,
                    'error': 'CHARTEXCHANGE_API_KEY not set',
                    'count': 0
                }
            
            client = UltimateChartExchangeClient(api_key)
            levels = client.get_dark_pool_levels(symbol, date)
            
            return {
                'available': len(levels) > 0,
                'count': len(levels),
                'error': None if len(levels) > 0 else 'No levels returned'
            }
        except Exception as e:
            return {
                'available': False,
                'error': str(e),
                'count': 0
            }
    
    def _check_dp_prints(self, date: str, symbol: str) -> Dict[str, any]:
        """Check if DP prints are available"""
        try:
            from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
            import os
            
            api_key = os.getenv('CHARTEXCHANGE_API_KEY')
            if not api_key:
                return {
                    'available': False,
                    'error': 'CHARTEXCHANGE_API_KEY not set',
                    'count': 0
                }
            
            client = UltimateChartExchangeClient(api_key)
            prints = client.get_dark_pool_prints(symbol, date)
            
            return {
                'available': len(prints) > 0,
                'count': len(prints),
                'error': None if len(prints) > 0 else 'No prints returned'
            }
        except Exception as e:
            return {
                'available': False,
                'error': str(e),
                'count': 0
            }
    
    def _check_price_data(self, date: str, symbol: str) -> Dict[str, any]:
        """Check if price data is available"""
        try:
            import yfinance as yf
            from datetime import datetime
            
            ticker = yf.Ticker(symbol)
            # Try to get data for the date
            hist = ticker.history(start=date, end=(datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d'))
            
            return {
                'available': len(hist) > 0,
                'count': len(hist),
                'error': None if len(hist) > 0 else 'No price data returned'
            }
        except Exception as e:
            return {
                'available': False,
                'error': str(e),
                'count': 0
            }
    
    def _check_market_hours(self, date: str) -> Dict[str, any]:
        """Check if date is a market day"""
        try:
            from datetime import datetime
            import pytz
            
            check_date = datetime.strptime(date, '%Y-%m-%d')
            
            # Check if it's a weekday
            is_weekday = check_date.weekday() < 5
            
            # Check if it's a market holiday (simplified - would need actual holiday list)
            # For now, just check weekday
            
            return {
                'is_market_day': is_weekday,
                'day_of_week': check_date.strftime('%A'),
                'error': None
            }
        except Exception as e:
            return {
                'is_market_day': False,
                'error': str(e)
            }


