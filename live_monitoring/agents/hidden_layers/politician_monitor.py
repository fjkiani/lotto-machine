"""
🏛️ Politician Trades Monitor
=============================
Uses Diffbot to extract clean tables from QuiverQuant or CapitolTrades.
Detects unusual or perfectly timed congressional trades before they hit the wire.
"""

import logging
from typing import List, Dict, Any

from live_monitoring.enrichment.apis.diffbot_extractor import DiffbotExtractor

logger = logging.getLogger(__name__)

class PoliticianMonitor:
    """Tracks Congressional stock trades cleanly via Diffbot."""
    
    def __init__(self):
        self.extractor = DiffbotExtractor()
        
        # Sources to sweep
        self.trade_sources = [
            "https://www.capitoltrades.com/trades",
            # QuiverQuant specific pages could go here
        ]

    def poll_latest_trades(self) -> List[Dict[str, Any]]:
        """
        Extract recent politician trades as structured JSON using Diffbot.
        Falls back to BeautifulSoup for static tables if JS parsing fails.
        """
        trades = []
        for url in self.trade_sources:
            try:
                logger.info(f"🏛️ Sweeping {url} for new congressional trades...")
                
                # 1. Try Diffbot Analyze API with 30s JS timeout
                data = self.extractor.extract_analyze(url, js_timeout=30000)
                
                found_diffbot = False
                if data and "tables" in data and len(data["tables"]) > 0:
                    logger.info(f"   ✅ Diffbot extracted {len(data['tables'])} tables!")
                    for table in data["tables"]:
                        if "rows" in table:
                            trades.extend(table["rows"][:10])
                            found_diffbot = True
                
                # 2. Fallback to BS4 if Diffbot failed on a JS-heavy page
                if not found_diffbot:
                    logger.info(f"   ⚠️ Diffbot returned empty tables for {url}. Attempting BS4 fallback...")
                    # QuiverQuant often uses simpler tables disguised in divs
                    rows = self.extractor.extract_table_bs4(url)
                    if rows:
                        logger.info(f"   ✅ BS4 extracted {len(rows)} trades!")
                        trades.extend(rows[:10])
                    else:
                        logger.warning(f"   ❌ Both Diffbot & BS4 failed extraction on {url}")
                        
            except Exception as e:
                logger.error(f"Error polling politician trades from {url}: {e}")
                
        return trades
