#!/usr/bin/env python3
"""
POPULATE HISTORICAL DATA
========================
Fetches 30 days of institutional data for SPY and QQQ and stores as InstitutionalContext objects.

This script:
1. Uses HistoricalDataPipeline to fetch raw data
2. Builds InstitutionalContext objects using UltraInstitutionalEngine
3. Saves contexts to data/historical/institutional_contexts/
4. Enables backtesting with production code

Usage:
    python3 populate_historical_data.py [--symbols SPY QQQ] [--days 30]

Author: Alpha's AI Hedge Fund
Date: 2025-01-XX
"""

import sys
import logging
import pickle
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

# Add paths
sys.path.append(str(Path(__file__).parent / 'core' / 'data'))
sys.path.append(str(Path(__file__).parent / 'core'))
sys.path.append(str(Path(__file__).parent / 'configs'))

from historical_data_pipeline import HistoricalDataPipeline
from ultimate_chartexchange_client import UltimateChartExchangeClient
import chartexchange_config

# Try to import UltraInstitutionalEngine
try:
    from ultra_institutional_engine import UltraInstitutionalEngine, InstitutionalContext
except ImportError:
    # If not found, we'll build contexts manually from raw data
    UltraInstitutionalEngine = None
    InstitutionalContext = None
    print("⚠️ Warning: UltraInstitutionalEngine not found. Will save raw data only.")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HistoricalDataPopulator:
    """Populates historical institutional data for backtesting"""
    
    def __init__(self, api_key: str, data_dir: str = "data/historical"):
        self.api_key = api_key
        self.data_dir = Path(data_dir)
        self.contexts_dir = self.data_dir / "institutional_contexts"
        self.contexts_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize pipeline
        self.pipeline = HistoricalDataPipeline(api_key, data_dir)
        
        # Initialize engine if available
        if UltraInstitutionalEngine:
            self.engine = UltraInstitutionalEngine(api_key)
        else:
            self.engine = None
            logger.warning("⚠️ UltraInstitutionalEngine not available - saving raw data only")
        
        logger.info("📊 Historical Data Populator initialized")
        logger.info(f"   Data directory: {self.data_dir}")
        logger.info(f"   Contexts directory: {self.contexts_dir}")
    
    def populate_symbol(self, symbol: str, days: int = 30) -> dict:
        """
        Populate historical data for a symbol
        
        Args:
            symbol: Ticker symbol
            days: Number of days to fetch
        
        Returns:
            Summary dictionary with counts
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 POPULATING DATA FOR {symbol} ({days} days)")
        logger.info(f"{'='*80}")
        
        # Calculate date range
        end_date = datetime.now() - timedelta(days=1)  # Yesterday (most recent complete day)
        start_date = end_date - timedelta(days=days)
        
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        logger.info(f"Date range: {start_str} to {end_str}")
        
        # Fetch raw data using pipeline
        logger.info("\n🔍 Fetching raw institutional data...")
        fetch_results = self.pipeline.fetch_date_range(
            symbol=symbol,
            start_date=start_str,
            end_date=end_str,
            data_types=['dp_levels', 'dp_prints', 'short', 'exchange_vol', 'borrow_fee', 'ftds']
        )
        
        # Build and save institutional contexts
        logger.info("\n🏗️  Building institutional contexts...")
        context_results = self._build_and_save_contexts(symbol, start_str, end_str)
        
        # Combine results
        summary = {
            'symbol': symbol,
            'start_date': start_str,
            'end_date': end_str,
            'days_requested': days,
            'dates_with_data': context_results['dates_processed'],
            'contexts_saved': context_results['contexts_saved'],
            'fetch_results': fetch_results
        }
        
        # Save summary
        summary_file = self.contexts_dir / f"{symbol}_summary_{start_str}_{end_str}.json"
        import json
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=4, default=str)
        
        logger.info(f"\n✅ COMPLETE FOR {symbol}:")
        logger.info(f"   Dates with data: {summary['dates_with_data']}")
        logger.info(f"   Contexts saved: {summary['contexts_saved']}")
        logger.info(f"   Summary saved: {summary_file}")
        
        return summary
    
    def _build_and_save_contexts(self, symbol: str, start_date: str, end_date: str) -> dict:
        """
        Build InstitutionalContext objects from fetched data and save them
        
        Returns:
            Dictionary with counts
        """
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        results = {
            'dates_processed': 0,
            'contexts_saved': 0,
            'errors': 0
        }
        
        current = start
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            
            # Skip weekends
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue
            
            try:
                # Check if data exists for this date
                dp_levels_file = self.pipeline.data_dir / "dark_pool" / f"{symbol}_{date_str}_levels.csv"
                if not dp_levels_file.exists():
                    logger.debug(f"   ⏭️  Skipping {date_str} - no data")
                    current += timedelta(days=1)
                    continue
                
                # Build context if engine available
                if self.engine:
                    context = self.engine.build_institutional_context(symbol, date_str)
                    
                    if context:
                        # Save context
                        context_file = self.contexts_dir / f"{symbol}_{date_str}_context.pkl"
                        with open(context_file, 'wb') as f:
                            pickle.dump({
                                'context': context,
                                'symbol': symbol,
                                'date': date_str,
                                'saved_at': datetime.now().isoformat()
                            }, f)
                        
                        results['contexts_saved'] += 1
                        logger.info(f"   ✅ {date_str}: Context saved")
                    else:
                        logger.warning(f"   ⚠️  {date_str}: Failed to build context")
                        results['errors'] += 1
                else:
                    # Just mark that data exists
                    logger.info(f"   ✅ {date_str}: Data available (no engine to build context)")
                    results['contexts_saved'] += 1
                
                results['dates_processed'] += 1
                
            except Exception as e:
                logger.error(f"   ❌ Error processing {date_str}: {e}")
                results['errors'] += 1
            
            current += timedelta(days=1)
        
        return results
    
    def populate_multiple_symbols(self, symbols: List[str], days: int = 30) -> dict:
        """
        Populate data for multiple symbols
        
        Args:
            symbols: List of ticker symbols
            days: Number of days to fetch
        
        Returns:
            Combined summary
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 POPULATING DATA FOR {len(symbols)} SYMBOLS")
        logger.info(f"{'='*80}")
        
        all_summaries = {}
        
        for i, symbol in enumerate(symbols, 1):
            logger.info(f"\n[{i}/{len(symbols)}] Processing {symbol}...")
            
            try:
                summary = self.populate_symbol(symbol, days)
                all_summaries[symbol] = summary
            except Exception as e:
                logger.error(f"❌ Failed to populate {symbol}: {e}")
                all_summaries[symbol] = {'error': str(e)}
            
            # Rate limiting between symbols
            if i < len(symbols):
                logger.info("   Waiting 2s before next symbol...")
                import time
                time.sleep(2)
        
        # Save combined summary
        import json
        combined_file = self.contexts_dir / f"combined_summary_{datetime.now().strftime('%Y%m%d')}.json"
        with open(combined_file, 'w') as f:
            json.dump(all_summaries, f, indent=4, default=str)
        
        logger.info(f"\n{'='*80}")
        logger.info("✅ ALL SYMBOLS COMPLETE!")
        logger.info(f"   Combined summary: {combined_file}")
        logger.info(f"{'='*80}")
        
        return all_summaries
    
    def get_available_dates(self, symbol: str) -> List[str]:
        """Get list of dates with saved contexts"""
        files = list(self.contexts_dir.glob(f"{symbol}_*_context.pkl"))
        
        dates = []
        for file in files:
            # Extract date from filename: SYMBOL_YYYY-MM-DD_context.pkl
            parts = file.stem.split('_')
            if len(parts) >= 3:
                date = parts[1]  # YYYY-MM-DD
                dates.append(date)
        
        return sorted(dates)
    
    def load_context(self, symbol: str, date: str) -> Optional[InstitutionalContext]:
        """Load saved institutional context"""
        context_file = self.contexts_dir / f"{symbol}_{date}_context.pkl"
        
        if not context_file.exists():
            return None
        
        try:
            with open(context_file, 'rb') as f:
                data = pickle.load(f)
                return data.get('context')
        except Exception as e:
            logger.error(f"Error loading context: {e}")
            return None


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Populate historical institutional data')
    parser.add_argument('--symbols', nargs='+', default=['SPY', 'QQQ'],
                       help='Symbols to populate (default: SPY QQQ)')
    parser.add_argument('--days', type=int, default=30,
                       help='Number of days to fetch (default: 30)')
    parser.add_argument('--data-dir', type=str, default='data/historical',
                       help='Data directory (default: data/historical)')
    
    args = parser.parse_args()
    
    # Get API key
    api_key = chartexchange_config.CHARTEXCHANGE_API_KEY
    
    if not api_key:
        logger.error("❌ ChartExchange API key not found in configs/chartexchange_config.py")
        return 1
    
    # Initialize populator
    populator = HistoricalDataPopulator(api_key, args.data_dir)
    
    # Populate data
    if len(args.symbols) == 1:
        summary = populator.populate_symbol(args.symbols[0], args.days)
    else:
        summary = populator.populate_multiple_symbols(args.symbols, args.days)
    
    logger.info("\n✅ POPULATION COMPLETE!")
    logger.info(f"   Check {populator.contexts_dir} for saved contexts")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

