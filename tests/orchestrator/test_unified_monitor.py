"""
Tests for UnifiedAlphaMonitor (modular version).
"""

import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)

from live_monitoring.orchestrator.unified_monitor import UnifiedAlphaMonitor


class TestUnifiedAlphaMonitor(unittest.TestCase):
    """Test UnifiedAlphaMonitor functionality."""
    
    @patch.dict(os.environ, {
        'DISCORD_WEBHOOK_URL': 'https://test.webhook.url',
        'CHARTEXCHANGE_API_KEY': 'test_key'
    })
    @patch('live_monitoring.orchestrator.monitor_initializer.MonitorInitializer')
    def test_initialization(self, mock_initializer_class):
        """Test monitor initialization."""
        # Mock the initializer
        mock_initializer = MagicMock()
        mock_initializer.initialize_all.return_value = {
            'fed': {'enabled': True, 'fed_watch': MagicMock(), 'fed_officials': MagicMock()},
            'trump': {'enabled': True, 'trump_pulse': MagicMock(), 'trump_news': MagicMock()},
            'dark_pool': {'enabled': True, 'dp_client': MagicMock(), 'dp_engine': MagicMock()},
            'dp_learning': {'enabled': False, 'dp_learning': None},
            'dp_monitor_engine': {'enabled': False, 'dp_monitor_engine': None},
            'signal_brain': {'enabled': False, 'signal_brain': None, 'macro_provider': None},
            'narrative_brain': {'enabled': False, 'narrative_brain': None, 'narrative_scheduler': None},
            'economic': {'enabled': True, 'econ_engine': MagicMock(), 'econ_calendar': MagicMock(), 'econ_calendar_type': 'static'},
            'tradytics': {'enabled': False, 'llm_available': False}
        }
        mock_initializer_class.return_value = mock_initializer
        
        # Mock signal generator
        with patch('live_monitoring.orchestrator.unified_monitor.SignalGenerator'):
            monitor = UnifiedAlphaMonitor()
            
            # Check components initialized
            self.assertIsNotNone(monitor.alert_manager)
            self.assertIsNotNone(monitor.regime_detector)
            self.assertIsNotNone(monitor.momentum_detector)
            self.assertTrue(monitor.fed_enabled)
            self.assertTrue(monitor.trump_enabled)
    
    def test_alert_delegation(self):
        """Test that alerts delegate to AlertManager."""
        with patch.dict(os.environ, {'DISCORD_WEBHOOK_URL': 'test'}):
            with patch('live_monitoring.orchestrator.monitor_initializer.MonitorInitializer'):
                monitor = UnifiedAlphaMonitor()
                
                # Mock alert manager
                monitor.alert_manager = MagicMock()
                monitor.alert_manager.send_discord.return_value = True
                
                # Send alert
                embed = {"title": "Test"}
                result = monitor.send_discord(embed, alert_type="test")
                
                # Should delegate to alert manager
                monitor.alert_manager.send_discord.assert_called_once()
                self.assertTrue(result)
    
    def test_regime_delegation(self):
        """Test that regime detection delegates to RegimeDetector."""
        with patch.dict(os.environ, {'DISCORD_WEBHOOK_URL': 'test'}):
            with patch('live_monitoring.orchestrator.monitor_initializer.MonitorInitializer'):
                monitor = UnifiedAlphaMonitor()
                
                # Mock regime detector
                monitor.regime_detector = MagicMock()
                monitor.regime_detector.detect.return_value = "UPTREND"
                monitor.regime_detector.get_regime_details.return_value = {'regime': 'UPTREND'}
                
                # Detect regime
                regime = monitor._detect_market_regime(100.0)
                
                # Should delegate to regime detector
                monitor.regime_detector.detect.assert_called_once_with(100.0)
                self.assertEqual(regime, "UPTREND")


if __name__ == '__main__':
    unittest.main()


