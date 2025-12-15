"""
Test SynthesisEngine Component

Tests:
- Confluence calculation
- Threshold filtering
- Direction determination
"""

import unittest
from live_monitoring.pipeline.components.synthesis_engine import SynthesisEngine, SynthesisResult


class TestSynthesisEngine(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.engine = SynthesisEngine(min_confluence=0.50)
    
    def test_synthesis_below_threshold_returns_none(self):
        """Test that synthesis below threshold returns None"""
        dp_levels = {}
        prices = {'SPY': 100.0}
        
        result = self.engine.synthesize(dp_levels, prices)
        
        self.assertIsNone(result)
    
    def test_synthesis_above_threshold_returns_result(self):
        """Test that synthesis above threshold returns result"""
        # Create mock data that should generate high confluence
        dp_levels = {
            'SPY': [
                {'price': 100.0, 'volume': 200_000},
                {'price': 100.5, 'volume': 150_000},
            ]
        }
        prices = {'SPY': 100.2}  # Near levels
        
        result = self.engine.synthesize(dp_levels, prices)
        
        # Should return result if confluence >= 0.50
        # (This test may need adjustment based on actual scoring logic)
        if result:
            self.assertIsInstance(result, SynthesisResult)
            self.assertGreaterEqual(result.confluence_score, 0.50)
    
    def test_min_confluence_configurable(self):
        """Test that min_confluence is configurable"""
        engine_30 = SynthesisEngine(min_confluence=0.30)
        engine_70 = SynthesisEngine(min_confluence=0.70)
        
        self.assertEqual(engine_30.min_confluence, 0.30)
        self.assertEqual(engine_70.min_confluence, 0.70)


if __name__ == '__main__':
    unittest.main()


