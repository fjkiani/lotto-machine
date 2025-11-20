#!/usr/bin/env python3
"""
INTEGRATE REAL DP DATA INTO DP FILTER
- Use the actual 10/16 DP data instead of API calls
- Test signal detection with real institutional levels
- Validate our DP-aware logic
"""

import pandas as pd
import numpy as np
from datetime import datetime
import asyncio
import sys
import os

# Add core directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))

from filters.dp_aware_signal_filter import DPAwareSignalFilter, DPStructure
from dataclasses import dataclass

@dataclass
class RealDPLevel:
    """Real DP level from 10/16 data"""
    price: float
    volume: int
    trades: int
    premium: float

class RealDPDataProvider:
    """Provider for real DP data from 10/16"""
    
    def __init__(self):
        # Load the real DP data
        df = pd.read_csv('data/cx_dark_pool_levels_nyse-spy_2025-10-16_17607558648217.csv')
        
        self.dp_levels = []
        for _, row in df.iterrows():
            level = RealDPLevel(
                price=row['level'],
                volume=int(row['volume']),
                trades=int(row['trades']),
                premium=row['premium']
            )
            self.dp_levels.append(level)
        
        print(f'📊 Loaded {len(self.dp_levels)} real DP levels from 10/16')
    
    def get_dp_levels(self, symbol: str, days_back: int = 1):
        """Return real DP levels (mimics ChartExchange API)"""
        return self.dp_levels
    
    def get_dp_prints(self, symbol: str, days_back: int = 1):
        """Return empty prints (we only have levels data)"""
        return []

class RealDPAwareSignalFilter(DPAwareSignalFilter):
    """DP filter using real 10/16 data"""
    
    def __init__(self):
        # Use Yahoo Direct for price data
        from detectors.real_breakout_reversal_detector_yahoo_direct import YahooDirectDataProvider
        self.yahoo_direct = YahooDirectDataProvider()
        
        # Use real DP data instead of ChartExchange API
        self.real_dp_provider = RealDPDataProvider()
        
        # DP structure thresholds
        self.dp_support_threshold = 0.7
        self.dp_resistance_threshold = 0.7
        self.battleground_threshold = 0.8
        self.breakout_confirmation_threshold = 0.25
        self.mean_reversion_threshold = 0.15
        
        # Signal tightening parameters
        self.min_dp_agreement = 0.3
        self.min_composite_confidence = 0.75
        self.max_risk_level = "MEDIUM"
    
    async def analyze_dp_structure(self, ticker: str) -> DPStructure:
        """Analyze DP structure using real 10/16 data"""
        try:
            print(f'🔍 ANALYZING DP STRUCTURE WITH REAL 10/16 DATA FOR {ticker}')
            
            # Get current price
            market_data = self.yahoo_direct.get_market_data(ticker)
            if not market_data or market_data.get('price', 0) == 0:
                print(f'❌ Failed to get market data for {ticker}')
                return None
            
            current_price = market_data.get('price', 0)
            print(f'📊 Current price: ${current_price:.2f}')
            
            # Get real DP levels
            dp_levels = self.real_dp_provider.get_dp_levels(ticker, days_back=1)
            print(f'📊 Using {len(dp_levels)} real DP levels from 10/16')
            
            # Analyze DP structure
            dp_support_levels = []
            dp_resistance_levels = []
            dp_volume_at_levels = {}
            institutional_battlegrounds = []
            
            # Process real DP levels
            for dp_level in dp_levels:
                price = dp_level.price
                volume = dp_level.volume
                
                if price < current_price:
                    dp_support_levels.append(price)
                else:
                    dp_resistance_levels.append(price)
                
                dp_volume_at_levels[price] = volume
                
                # High volume levels are institutional battlegrounds
                if volume > 1000000:  # 1M+ shares
                    institutional_battlegrounds.append(price)
            
            # Calculate DP strength score
            total_dp_volume = sum(dp_volume_at_levels.values())
            dp_strength_score = min(total_dp_volume / 10000000, 1.0)
            
            # Identify breakout and mean reversion levels
            breakout_levels = [level for level in dp_resistance_levels if level > current_price * 1.01]
            mean_reversion_levels = [level for level in dp_support_levels if level < current_price * 0.99]
            
            dp_structure = DPStructure(
                ticker=ticker,
                current_price=current_price,
                dp_support_levels=sorted(dp_support_levels),
                dp_resistance_levels=sorted(dp_resistance_levels),
                dp_volume_at_levels=dp_volume_at_levels,
                dp_strength_score=dp_strength_score,
                institutional_battlegrounds=sorted(institutional_battlegrounds),
                breakout_levels=sorted(breakout_levels),
                mean_reversion_levels=sorted(mean_reversion_levels),
                timestamp=datetime.now()
            )
            
            print(f'✅ DP structure analyzed with REAL DATA')
            print(f'   Support levels: {len(dp_structure.dp_support_levels)}')
            print(f'   Resistance levels: {len(dp_structure.dp_resistance_levels)}')
            print(f'   Battlegrounds: {len(dp_structure.institutional_battlegrounds)}')
            print(f'   DP strength: {dp_structure.dp_strength_score:.2f}')
            
            # Show key battlegrounds
            if dp_structure.institutional_battlegrounds:
                print(f'   Key battlegrounds: {dp_structure.institutional_battlegrounds[:3]}')
            
            return dp_structure
            
        except Exception as e:
            print(f'❌ Error analyzing DP structure: {e}')
            return None

async def test_real_dp_filter():
    """Test the DP filter with real 10/16 data"""
    print('🎯 TESTING DP FILTER WITH REAL 10/16 DATA')
    print('=' * 60)
    
    # Create filter with real data
    dp_filter = RealDPAwareSignalFilter()
    
    # Test DP structure analysis
    print('\n📊 Testing DP structure analysis...')
    dp_structure = await dp_filter.analyze_dp_structure('SPY')
    
    if not dp_structure:
        print('❌ Failed to analyze DP structure')
        return
    
    # Test signal filtering
    print('\n🔍 Testing signal filtering...')
    signals = await dp_filter.filter_signals_with_dp_confirmation('SPY')
    
    print(f'📊 Signals found: {len(signals)}')
    
    if signals:
        print('✅ Signals detected!')
        for i, signal in enumerate(signals):
            print(f'  {i+1}. {signal.action} @ ${signal.entry_price:.2f} - Risk: {signal.risk_level}')
            print(f'      Confidence: {signal.confidence:.2f}')
            print(f'      Factors: {signal.dp_factors}')
    else:
        print('❌ No signals detected')
    
    print('\n🎯 Test complete!')

if __name__ == '__main__':
    asyncio.run(test_real_dp_filter())
