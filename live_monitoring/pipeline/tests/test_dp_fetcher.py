"""
Test DPFetcher Component

Tests:
- Volume threshold filtering
- Multiple symbol fetching
- Error handling
"""

import unittest
from unittest.mock import Mock, patch
from live_monitoring.pipeline.components.dp_fetcher import DPFetcher


class TestDPFetcher(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.api_key = "test_key"
        self.fetcher = DPFetcher(api_key=self.api_key, min_volume=100_000)
    
    def test_fetch_levels_filters_by_volume(self):
        """Test that levels are filtered by volume threshold"""
        # Mock API response
        mock_client = Mock()
        mock_client.get_dark_pool_levels.return_value = [
            {'level': '100.00', 'volume': '150000'},  # Above threshold
            {'level': '101.00', 'volume': '50000'},   # Below threshold
            {'level': '102.00', 'volume': '200000'},  # Above threshold
        ]
        self.fetcher._dp_client = mock_client
        
        # Fetch levels
        levels = self.fetcher.fetch_levels('SPY')
        
        # Should only return levels >= 100k
        self.assertEqual(len(levels), 2)
        self.assertEqual(levels[0]['price'], 100.00)
        self.assertEqual(levels[1]['price'], 102.00)
    
    def test_fetch_levels_handles_empty_response(self):
        """Test handling of empty API response"""
        mock_client = Mock()
        mock_client.get_dark_pool_levels.return_value = []
        self.fetcher._dp_client = mock_client
        
        levels = self.fetcher.fetch_levels('SPY')
        self.assertEqual(len(levels), 0)
    
    def test_min_volume_configurable(self):
        """Test that min_volume is configurable"""
        fetcher_50k = DPFetcher(api_key=self.api_key, min_volume=50_000)
        fetcher_500k = DPFetcher(api_key=self.api_key, min_volume=500_000)
        
        self.assertEqual(fetcher_50k.min_volume, 50_000)
        self.assertEqual(fetcher_500k.min_volume, 500_000)


if __name__ == '__main__':
    unittest.main()

