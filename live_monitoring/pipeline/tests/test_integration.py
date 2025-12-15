"""
Integration Tests - Full Pipeline

Tests the entire pipeline end-to-end with mock data.
"""

import unittest
from unittest.mock import Mock, patch
from live_monitoring.pipeline import PipelineOrchestrator, PipelineConfig
from live_monitoring.pipeline.components.synthesis_engine import SynthesisResult


class TestPipelineIntegration(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        config = PipelineConfig()
        config.dp.min_volume = 100_000
        config.synthesis.min_confluence = 0.50
        self.orchestrator = PipelineOrchestrator(config=config)
    
    @patch('live_monitoring.pipeline.orchestrator.DPFetcher')
    @patch('live_monitoring.pipeline.orchestrator.SynthesisEngine')
    @patch('live_monitoring.pipeline.orchestrator.AlertManager')
    def test_pipeline_flow(self, mock_alert, mock_synthesis, mock_dp):
        """Test that pipeline flows correctly"""
        # Mock components
        mock_dp_instance = Mock()
        mock_dp_instance.fetch_multiple.return_value = {
            'SPY': [{'price': 100.0, 'volume': 200_000}]
        }
        self.orchestrator.dp_fetcher = mock_dp_instance
        
        mock_synthesis_instance = Mock()
        mock_synthesis_instance.synthesize.return_value = SynthesisResult(
            confluence_score=0.60,
            direction='BEARISH',
            action='SHORT',
            reasoning='Test',
            confidence=0.60
        )
        self.orchestrator.synthesis_engine = mock_synthesis_instance
        
        # Run one cycle
        self.orchestrator._check_dp_levels()
        self.orchestrator._run_synthesis()
        
        # Verify components were called
        mock_dp_instance.fetch_multiple.assert_called_once()
        mock_synthesis_instance.synthesize.assert_called_once()


if __name__ == '__main__':
    unittest.main()


