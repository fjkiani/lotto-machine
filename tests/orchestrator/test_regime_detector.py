"""
Tests for RegimeDetector module.
"""

import unittest
from unittest.mock import patch, MagicMock
from live_monitoring.orchestrator.regime_detector import RegimeDetector


class TestRegimeDetector(unittest.TestCase):
    """Test RegimeDetector functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.detector = RegimeDetector()
    
    @patch('live_monitoring.orchestrator.regime_detector.yf')
    def test_regime_detection(self, mock_yf):
        """Test regime detection."""
        # Mock yfinance data
        import pandas as pd
        mock_ticker = MagicMock()
        mock_hist = pd.DataFrame({
            'Open': [100, 101, 102, 103, 104, 105],
            'Close': [101, 102, 103, 104, 105, 106],
            'High': [101.5, 102.5, 103.5, 104.5, 105.5, 106.5],
            'Low': [100.5, 101.5, 102.5, 103.5, 104.5, 105.5]
        })
        mock_ticker.history.return_value = mock_hist
        mock_yf.Ticker.return_value = mock_ticker
        
        # Test detection
        regime = self.detector.detect(106.0, 'SPY')
        
        # Should return a valid regime
        self.assertIn(regime, ["STRONG_UPTREND", "UPTREND", "DOWNTREND", "STRONG_DOWNTREND", "CHOPPY"])
    
    @patch('live_monitoring.orchestrator.regime_detector.yf')
    def test_insufficient_data(self, mock_yf):
        """Test regime detection with insufficient data."""
        import pandas as pd
        mock_ticker = MagicMock()
        mock_hist = pd.DataFrame()  # Empty
        mock_ticker.history.return_value = mock_hist
        mock_yf.Ticker.return_value = mock_ticker
        
        # Should default to CHOPPY
        regime = self.detector.detect(100.0, 'SPY')
        self.assertEqual(regime, "CHOPPY")


if __name__ == '__main__':
    unittest.main()


