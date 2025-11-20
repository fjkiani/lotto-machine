#!/usr/bin/env python3
"""
TEST HISTORICAL DATA FETCH
- Quick test to fetch a few days of data
"""

import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / 'core' / 'data'))
sys.path.append(str(Path(__file__).parent / 'configs'))

from historical_data_pipeline import HistoricalDataPipeline
import chartexchange_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("🧪 TESTING HISTORICAL DATA FETCH")
    logger.info("=" * 80)
    
    pipeline = HistoricalDataPipeline(
        api_key=chartexchange_config.CHARTEXCHANGE_API_KEY,
        data_dir="data/historical_test"
    )
    
    # Fetch just 3 days for SPY
    logger.info("\n📊 Fetching SPY data for 10/14 - 10/16...")
    
    results = pipeline.fetch_date_range(
        symbol="SPY",
        start_date="2025-10-14",
        end_date="2025-10-16",
        data_types=['dp_levels', 'dp_prints', 'short', 'exchange_vol']
    )
    
    logger.info("\n✅ RESULTS:")
    logger.info(f"   Dates processed: {results['dates_processed']}")
    logger.info(f"   DP Levels: {results['dp_levels_fetched']}")
    logger.info(f"   DP Prints: {results['dp_prints_fetched']}")
    logger.info(f"   Short Data: {results['short_data_fetched']}")
    logger.info(f"   Exchange Vol: {results['exchange_vol_fetched']}")
    
    # Test loading
    logger.info("\n🔍 Testing data loading...")
    
    dp_levels = pipeline.load_dp_levels("SPY", "2025-10-16")
    logger.info(f"   Loaded {len(dp_levels)} DP levels for 10/16")
    
    if not dp_levels.empty:
        battlegrounds = dp_levels[dp_levels['volume'].astype(float) >= 1000000]
        logger.info(f"   Found {len(battlegrounds)} battlegrounds:")
        for _, bg in battlegrounds.head(5).iterrows():
            logger.info(f"      ${float(bg['level']):.2f} - {int(float(bg['volume'])):,} shares")
    
    logger.info("\n✅ TEST COMPLETE!")

if __name__ == "__main__":
    main()



