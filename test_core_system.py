#!/usr/bin/env python3
"""
TEST CORE SYSTEM
- Test the organized core system with real DP data
- Verify DP filter integration works
"""

import asyncio
import sys
import os

# Add core directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))

import logging
from filters.dp_aware_signal_filter import DPAwareSignalFilter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_core_system():
    """Test the core system"""
    print('🎯 TESTING CORE SYSTEM')
    print('=' * 50)
    
    try:
        # Test DP filter
        print('\n📊 Testing DP Filter...')
        dp_filter = DPAwareSignalFilter()
        
        # Test DP structure analysis
        dp_structure = await dp_filter.analyze_dp_structure('SPY')
        
        if dp_structure:
            print(f'✅ DP structure analyzed successfully')
            print(f'   Support levels: {len(dp_structure.dp_support_levels)}')
            print(f'   Resistance levels: {len(dp_structure.dp_resistance_levels)}')
            print(f'   Battlegrounds: {len(dp_structure.institutional_battlegrounds)}')
            print(f'   DP strength: {dp_structure.dp_strength_score:.2f}')
        else:
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
        else:
            print('❌ No signals detected (this is expected if no DP confirmation)')
        
        print('\n🎯 Core system test complete!')
        
    except Exception as e:
        print(f'❌ Error testing core system: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_core_system())


