#!/usr/bin/env python3
"""
HISTORICAL DATA PIPELINE
- Programmatically fetch and store ALL institutional data
- Dark pool levels, prints, short data, options, FTDs
- Build complete historical database
- Enable backtesting and replay
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import os
from pathlib import Path
import time

from ultimate_chartexchange_client import UltimateChartExchangeClient

logger = logging.getLogger(__name__)

class HistoricalDataPipeline:
    """Pipeline to fetch and store historical institutional data"""
    
    def __init__(self, api_key: str, data_dir: str = "data/historical"):
        self.client = UltimateChartExchangeClient(api_key, tier=3)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.data_dir / "dark_pool").mkdir(exist_ok=True)
        (self.data_dir / "short_data").mkdir(exist_ok=True)
        (self.data_dir / "options").mkdir(exist_ok=True)
        (self.data_dir / "ftds").mkdir(exist_ok=True)
        (self.data_dir / "exchange_volume").mkdir(exist_ok=True)
        (self.data_dir / "borrow_fees").mkdir(exist_ok=True)
        
        logger.info(f"📊 Historical Data Pipeline initialized")
        logger.info(f"   Data directory: {self.data_dir}")
    
    def fetch_date_range(self, symbol: str, start_date: str, end_date: str,
                         data_types: List[str] = None) -> Dict[str, Any]:
        """
        Fetch all institutional data for a date range
        
        Args:
            symbol: Stock symbol (e.g., 'SPY')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            data_types: List of data types to fetch. If None, fetch all.
                       Options: ['dp_levels', 'dp_prints', 'short', 'options', 
                                'ftds', 'exchange_vol', 'borrow_fee']
        
        Returns:
            Dictionary with counts of fetched data
        """
        if data_types is None:
            data_types = ['dp_levels', 'dp_prints', 'short', 'exchange_vol', 'borrow_fee', 'ftds']
        
        logger.info(f"🔍 Fetching {symbol} data from {start_date} to {end_date}")
        logger.info(f"   Data types: {', '.join(data_types)}")
        
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        results = {
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date,
            'dates_processed': 0,
            'dp_levels_fetched': 0,
            'dp_prints_fetched': 0,
            'short_data_fetched': 0,
            'options_fetched': 0,
            'ftds_fetched': 0,
            'exchange_vol_fetched': 0,
            'borrow_fees_fetched': 0
        }
        
        current = start
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            
            # Skip weekends
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue
            
            logger.info(f"\n📅 Processing {date_str}...")
            
            try:
                # Dark Pool Levels
                if 'dp_levels' in data_types:
                    dp_levels = self.fetch_and_save_dp_levels(symbol, date_str)
                    results['dp_levels_fetched'] += len(dp_levels)
                    logger.info(f"   ✅ DP Levels: {len(dp_levels)}")
                
                # Dark Pool Prints
                if 'dp_prints' in data_types:
                    dp_prints = self.fetch_and_save_dp_prints(symbol, date_str)
                    results['dp_prints_fetched'] += len(dp_prints)
                    logger.info(f"   ✅ DP Prints: {len(dp_prints)}")
                
                # Short Data
                if 'short' in data_types:
                    short_data = self.fetch_and_save_short_data(symbol, date_str)
                    results['short_data_fetched'] += len(short_data)
                    logger.info(f"   ✅ Short Data: {len(short_data)}")
                
                # Exchange Volume
                if 'exchange_vol' in data_types:
                    exchange_vol = self.fetch_and_save_exchange_volume(symbol, date_str)
                    results['exchange_vol_fetched'] += len(exchange_vol)
                    logger.info(f"   ✅ Exchange Volume: {len(exchange_vol)}")
                
                # Borrow Fee
                if 'borrow_fee' in data_types:
                    borrow_fee = self.fetch_and_save_borrow_fee(symbol, date_str)
                    if borrow_fee:
                        results['borrow_fees_fetched'] += 1
                        logger.info(f"   ✅ Borrow Fee: {borrow_fee.fee_rate:.2f}%")
                
                # FTDs (less frequent, only fetch once for range)
                if 'ftds' in data_types and current == start:
                    ftds = self.fetch_and_save_ftds(symbol, date_str)
                    results['ftds_fetched'] += len(ftds)
                    logger.info(f"   ✅ FTDs: {len(ftds)}")
                
                results['dates_processed'] += 1
                
                # Rate limiting - small delay between dates
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"   ❌ Error processing {date_str}: {e}")
            
            current += timedelta(days=1)
        
        # Save summary
        self._save_fetch_summary(results)
        
        logger.info(f"\n✅ FETCH COMPLETE:")
        logger.info(f"   Dates processed: {results['dates_processed']}")
        logger.info(f"   DP Levels: {results['dp_levels_fetched']}")
        logger.info(f"   DP Prints: {results['dp_prints_fetched']}")
        logger.info(f"   Short Data: {results['short_data_fetched']}")
        logger.info(f"   Exchange Vol: {results['exchange_vol_fetched']}")
        logger.info(f"   Borrow Fees: {results['borrow_fees_fetched']}")
        logger.info(f"   FTDs: {results['ftds_fetched']}")
        
        return results
    
    def fetch_and_save_dp_levels(self, symbol: str, date: str) -> List[Dict]:
        """Fetch and save dark pool levels"""
        levels = self.client.get_dark_pool_levels(symbol, date)
        
        if levels:
            # Convert to DataFrame and save
            df = pd.DataFrame(levels)
            filename = self.data_dir / "dark_pool" / f"{symbol}_{date}_levels.csv"
            df.to_csv(filename, index=False)
        
        return levels
    
    def fetch_and_save_dp_prints(self, symbol: str, date: str) -> List[Dict]:
        """Fetch and save dark pool prints"""
        prints = self.client.get_dark_pool_prints(symbol, date)
        
        if prints:
            df = pd.DataFrame(prints)
            filename = self.data_dir / "dark_pool" / f"{symbol}_{date}_prints.csv"
            df.to_csv(filename, index=False)
        
        return prints
    
    def fetch_and_save_short_data(self, symbol: str, date: str) -> List[Any]:
        """Fetch and save short volume data"""
        short_data = self.client.get_short_volume(symbol, date)
        
        if short_data:
            # Convert to dict for saving
            data_dicts = [
                {
                    'symbol': s.symbol,
                    'date': s.date,
                    'short_volume': s.short_volume,
                    'total_volume': s.total_volume,
                    'short_pct': s.short_pct
                }
                for s in short_data
            ]
            df = pd.DataFrame(data_dicts)
            filename = self.data_dir / "short_data" / f"{symbol}_{date}_short.csv"
            df.to_csv(filename, index=False)
        
        return short_data
    
    def fetch_and_save_exchange_volume(self, symbol: str, date: str) -> List[Any]:
        """Fetch and save exchange volume breakdown"""
        exchange_vol = self.client.get_exchange_volume(symbol, date)
        
        if exchange_vol:
            data_dicts = [
                {
                    'symbol': ev.symbol,
                    'timestamp': ev.timestamp.isoformat(),
                    'exchange': ev.exchange,
                    'volume': ev.volume,
                    'pct_of_total': ev.pct_of_total
                }
                for ev in exchange_vol
            ]
            df = pd.DataFrame(data_dicts)
            filename = self.data_dir / "exchange_volume" / f"{symbol}_{date}_exchange.csv"
            df.to_csv(filename, index=False)
        
        return exchange_vol
    
    def fetch_and_save_borrow_fee(self, symbol: str, date: str) -> Optional[Any]:
        """Fetch and save borrow fee"""
        borrow_fee = self.client.get_borrow_fee(symbol, date)
        
        if borrow_fee:
            data_dict = {
                'symbol': borrow_fee.symbol,
                'date': borrow_fee.date,
                'fee_rate': borrow_fee.fee_rate,
                'available_shares': borrow_fee.available_shares
            }
            df = pd.DataFrame([data_dict])
            filename = self.data_dir / "borrow_fees" / f"{symbol}_{date}_borrow.csv"
            df.to_csv(filename, index=False)
        
        return borrow_fee
    
    def fetch_and_save_ftds(self, symbol: str, start_date: str) -> List[Any]:
        """Fetch and save FTD data"""
        ftds = self.client.get_failure_to_deliver(symbol, start_date)
        
        if ftds:
            data_dicts = [
                {
                    'symbol': ftd.symbol,
                    'date': ftd.date,
                    'quantity': ftd.quantity,
                    'price': ftd.price
                }
                for ftd in ftds
            ]
            df = pd.DataFrame(data_dicts)
            filename = self.data_dir / "ftds" / f"{symbol}_ftds.csv"
            df.to_csv(filename, index=False)
        
        return ftds
    
    def _save_fetch_summary(self, results: Dict[str, Any]):
        """Save fetch summary to JSON"""
        summary_file = self.data_dir / f"{results['symbol']}_{results['start_date']}_{results['end_date']}_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(results, f, indent=4)
    
    def load_dp_levels(self, symbol: str, date: str) -> pd.DataFrame:
        """Load saved dark pool levels"""
        filename = self.data_dir / "dark_pool" / f"{symbol}_{date}_levels.csv"
        if filename.exists():
            return pd.read_csv(filename)
        return pd.DataFrame()
    
    def load_dp_prints(self, symbol: str, date: str) -> pd.DataFrame:
        """Load saved dark pool prints"""
        filename = self.data_dir / "dark_pool" / f"{symbol}_{date}_prints.csv"
        if filename.exists():
            return pd.read_csv(filename)
        return pd.DataFrame()
    
    def load_short_data(self, symbol: str, date: str) -> pd.DataFrame:
        """Load saved short data"""
        filename = self.data_dir / "short_data" / f"{symbol}_{date}_short.csv"
        if filename.exists():
            return pd.read_csv(filename)
        return pd.DataFrame()
    
    def load_exchange_volume(self, symbol: str, date: str) -> pd.DataFrame:
        """Load saved exchange volume"""
        filename = self.data_dir / "exchange_volume" / f"{symbol}_{date}_exchange.csv"
        if filename.exists():
            return pd.read_csv(filename)
        return pd.DataFrame()
    
    def load_borrow_fee(self, symbol: str, date: str) -> Optional[Dict]:
        """Load saved borrow fee"""
        filename = self.data_dir / "borrow_fees" / f"{symbol}_{date}_borrow.csv"
        if filename.exists():
            df = pd.read_csv(filename)
            if not df.empty:
                return df.iloc[0].to_dict()
        return None
    
    def load_ftds(self, symbol: str) -> pd.DataFrame:
        """Load saved FTDs"""
        filename = self.data_dir / "ftds" / f"{symbol}_ftds.csv"
        if filename.exists():
            return pd.read_csv(filename)
        return pd.DataFrame()
    
    def bulk_fetch_symbols(self, symbols: List[str], start_date: str, 
                          end_date: str, data_types: List[str] = None):
        """
        Fetch data for multiple symbols
        """
        logger.info(f"🚀 BULK FETCH: {len(symbols)} symbols")
        
        all_results = {}
        
        for i, symbol in enumerate(symbols, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"[{i}/{len(symbols)}] Processing {symbol}")
            logger.info(f"{'='*80}")
            
            try:
                results = self.fetch_date_range(symbol, start_date, end_date, data_types)
                all_results[symbol] = results
            except Exception as e:
                logger.error(f"❌ Failed to process {symbol}: {e}")
                all_results[symbol] = {'error': str(e)}
            
            # Rate limiting between symbols
            if i < len(symbols):
                logger.info("   Waiting 2s before next symbol...")
                time.sleep(2)
        
        # Save bulk summary
        bulk_summary_file = self.data_dir / f"bulk_fetch_{start_date}_{end_date}_summary.json"
        with open(bulk_summary_file, 'w') as f:
            json.dump(all_results, f, indent=4)
        
        logger.info(f"\n{'='*80}")
        logger.info("✅ BULK FETCH COMPLETE!")
        logger.info(f"   Summary saved to: {bulk_summary_file}")
        logger.info(f"{'='*80}")
        
        return all_results
    
    def get_available_dates(self, symbol: str) -> List[str]:
        """Get list of dates with available data for a symbol"""
        dark_pool_dir = self.data_dir / "dark_pool"
        files = list(dark_pool_dir.glob(f"{symbol}_*_levels.csv"))
        
        dates = []
        for file in files:
            # Extract date from filename: SYMBOL_YYYY-MM-DD_levels.csv
            parts = file.stem.split('_')
            if len(parts) >= 4:
                date = parts[1] + '-' + parts[2] + '-' + parts[3]
                dates.append(date)
        
        return sorted(dates)



