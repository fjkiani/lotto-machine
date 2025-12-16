"""
Tests for MomentumDetector module.
"""

import unittest
from unittest.mock import MagicMock, patch
from live_monitoring.orchestrator.momentum_detector import MomentumDetector


class TestMomentumDetector(unittest.TestCase):
    """Test MomentumDetector functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_signal_generator = MagicMock()
        self.mock_institutional_engine = MagicMock()
        self.detector = MomentumDetector(
            signal_generator=self.mock_signal_generator,
            institutional_engine=self.mock_institutional_engine
        )
    
    @patch('live_monitoring.orchestrator.momentum_detector.yf')
    def test_selloff_detection(self, mock_yf):
        """Test selloff detection."""
        import pandas as pd
        import numpy as np
        
        # Create mock data with selloff pattern (price dropping)
        dates = pd.date_range('2024-12-15 09:30', periods=30, freq='1min')
        prices = np.linspace(100, 99, 30)  # Dropping price
        volumes = np.random.randint(1000000, 2000000, 30)
        volumes[-1] = 3000000  # Volume spike
        
        mock_hist = pd.DataFrame({
            'Close': prices,
            'Volume': volumes
        })
        
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_hist
        mock_yf.Ticker.return_value = mock_ticker
        
        # Mock signal generator to return a selloff signal
        mock_signal = MagicMock()
        mock_signal.action.value = "SELL"
        mock_signal.confidence = 0.75
        mock_signal.rationale = "Selloff detected"
        mock_signal.entry_price = 99.0
        mock_signal.stop_price = 100.0
        mock_signal.target_price = 98.0
        self.mock_signal_generator._detect_realtime_selloff.return_value = mock_signal
        
        # Test
        signals = self.detector.check_selloffs(['SPY'])
        
        # Should detect selloff
        self.assertGreater(len(signals), 0)
        self.assertEqual(signals[0]['symbol'], 'SPY')
    
    @patch('live_monitoring.orchestrator.momentum_detector.yf')
    def test_rally_detection(self, mock_yf):
        """Test rally detection."""
        import pandas as pd
        import numpy as np
        
        # Create mock data with rally pattern (price rising)
        dates = pd.date_range('2024-12-15 09:30', periods=30, freq='1min')
        prices = np.linspace(100, 101, 30)  # Rising price
        volumes = np.random.randint(1000000, 2000000, 30)
        volumes[-1] = 3000000  # Volume spike
        
        mock_hist = pd.DataFrame({
            'Close': prices,
            'Volume': volumes
        })
        
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_hist
        mock_yf.Ticker.return_value = mock_ticker
        
        # Mock signal generator to return a rally signal
        mock_signal = MagicMock()
        mock_signal.action.value = "BUY"
        mock_signal.confidence = 0.75
        mock_signal.rationale = "Rally detected"
        mock_signal.entry_price = 101.0
        mock_signal.stop_price = 100.0
        mock_signal.target_price = 102.0
        self.mock_signal_generator._detect_realtime_rally.return_value = mock_signal
        
        # Test
        signals = self.detector.check_rallies(['SPY'])
        
        # Should detect rally
        self.assertGreater(len(signals), 0)
        self.assertEqual(signals[0]['symbol'], 'SPY')


if __name__ == '__main__':
    unittest.main()


