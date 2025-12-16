"""
Tests for AlertManager module.
"""

import unittest
import os
import tempfile
import shutil
from live_monitoring.orchestrator.alert_manager import AlertManager


class TestAlertManager(unittest.TestCase):
    """Test AlertManager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_alerts.db")
        self.manager = AlertManager(
            discord_webhook=None,  # No webhook for testing
            alert_db_path=self.db_path
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_alert_hash_generation(self):
        """Test alert hash generation for deduplication."""
        embed1 = {
            "title": "Test Alert",
            "description": "Test description",
            "fields": [{"name": "Price", "value": "$100.00"}]
        }
        
        embed2 = {
            "title": "Test Alert",
            "description": "Test description",
            "fields": [{"name": "Price", "value": "$100.00"}]
        }
        
        hash1 = self.manager._generate_alert_hash(embed1, "content", "test", "source", "SPY")
        hash2 = self.manager._generate_alert_hash(embed2, "content", "test", "source", "SPY")
        
        # Same alert should generate same hash
        self.assertEqual(hash1, hash2)
    
    def test_deduplication(self):
        """Test alert deduplication."""
        embed = {
            "title": "Test Alert",
            "description": "Test"
        }
        
        # First send should work
        result1 = self.manager.send_discord(embed, alert_type="test", source="test")
        # Should return False (no webhook) but not crash
        
        # Second send should be deduplicated
        result2 = self.manager.send_discord(embed, alert_type="test", source="test")
        # Should also return False but be logged as duplicate
    
    def test_database_logging(self):
        """Test database logging."""
        embed = {
            "title": "Test Alert",
            "description": "Test description"
        }
        
        # Send alert (will log to DB even without webhook)
        self.manager.send_discord(embed, alert_type="test", source="test", symbol="SPY")
        
        # Check database was created
        self.assertTrue(os.path.exists(self.db_path))


if __name__ == '__main__':
    unittest.main()


