"""
🕵️ Insider Trades Monitor
==========================
Uses Diffbot to extract tables from OpenInsider or EDGAR Form 4 filings.
Identifies massive executive buys or highly suspicious timing.
"""

import logging
from typing import List, Dict, Any

from live_monitoring.enrichment.apis.diffbot_extractor import DiffbotExtractor

logger = logging.getLogger(__name__)

class InsiderMonitor:
    """Tracks Corporate Insider stock trades cleanly via Diffbot."""
    
    def __init__(self):
        self.extractor = DiffbotExtractor()
        
        self.insider_sources = [
            "http://openinsider.com/latest-cluster-buys"
        ]

    def poll_latest_trades(self) -> List[Dict[str, Any]]:
        """
        Extract recent insider trades as structured JSON.
        Diffbot automatically pulls the HTML table into clean dictionary rows.
        """
        trades = []
        for url in self.insider_sources:
            try:
                logger.info(f"🕵️ Sweeping {url} for insider cluster buys...")
                # OpenInsider is pure static HTML. BS4 is 10x faster and more reliable than JS rendering here.
                # We target class 'tinytable' which is standard on OpenInsider.
                rows = self.extractor.extract_table_bs4(url, table_class="tinytable")
                
                if rows:
                    logger.info(f"   ✅ Found {len(rows)} insider trades!")
                    trades.extend(rows[:10]) # Limiting to 10 for sample
                else:
                    logger.warning(f"   ⚠️ No tables found or extraction failed for {url}")
            except Exception as e:
                logger.error(f"Error polling insider trades from {url}: {e}")
                
        return trades
