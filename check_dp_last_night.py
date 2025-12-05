#!/usr/bin/env python3
"""
Check Dark Pool data from last night (Dec 4, 2025)
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '.')
from core.ultra_institutional_engine import UltraInstitutionalEngine
from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
from datetime import datetime, timedelta

api_key = os.getenv('CHARTEXCHANGE_API_KEY')
if not api_key:
    print('❌ CHARTEXCHANGE_API_KEY not set')
    sys.exit(1)

print('=' * 80)
print('🔒 DARK POOL DATA - DECEMBER 4, 2025 (LAST NIGHT)')
print('=' * 80)

client = UltimateChartExchangeClient(api_key)
engine = UltraInstitutionalEngine(api_key)

# Get yesterday's date
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
print(f'\n📅 Date: {yesterday}')
print(f'📊 Symbol: SPY')
print()

# Fetch dark pool data
print('📥 Fetching Dark Pool Levels...')
dp_levels = client.get_dark_pool_levels('SPY', yesterday)

if dp_levels:
    print(f'   ✅ Found {len(dp_levels)} dark pool levels')
    
    # Calculate totals
    total_dp_vol = 0
    for l in dp_levels:
        vol = l.get('total_vol', l.get('volume', l.get('total_volume', l.get('shares', 0))))
        if isinstance(vol, (int, float)):
            total_dp_vol += vol
        elif isinstance(vol, str):
            try:
                total_dp_vol += float(vol.replace(',', ''))
            except:
                pass
    
    print(f'   📊 Total DP Volume: {total_dp_vol:,} shares')
    
    # Show top levels
    if len(dp_levels) > 0:
        print(f'\n   🔝 TOP 5 DARK POOL LEVELS:')
        def get_vol(level):
            vol = level.get('total_vol', level.get('volume', level.get('total_volume', level.get('shares', 0))))
            if isinstance(vol, str):
                try:
                    return float(vol.replace(',', ''))
                except:
                    return 0
            return float(vol) if vol else 0
        
        sorted_levels = sorted(dp_levels, key=get_vol, reverse=True)[:5]
        for i, level in enumerate(sorted_levels, 1):
            price = level.get('level', level.get('price', 0))
            if isinstance(price, str):
                try:
                    price = float(price)
                except:
                    price = 0
            vol = get_vol(level)
            print(f'      {i}. ${float(price):.2f} - {vol:,.0f} shares')
else:
    print('   ⚠️ No dark pool levels found')

# Fetch dark pool prints
print(f'\n📥 Fetching Dark Pool Prints...')
dp_prints = client.get_dark_pool_prints('SPY', yesterday)

if dp_prints:
    print(f'   ✅ Found {len(dp_prints)} dark pool prints')
    
    # Calculate buy/sell (prints use 'size' not 'volume')
    buy_vol = 0
    sell_vol = 0
    for p in dp_prints:
        side = p.get('side', '').upper()
        size = p.get('size', p.get('volume', p.get('shares', 0)))
        if isinstance(size, str):
            try:
                size = float(size.replace(',', ''))
            except:
                size = 0
        else:
            size = float(size) if size else 0
        
        # Handle side codes: 'B' or 'BUY' = buy, 'S' or 'SELL' = sell
        if side == 'B' or side == 'BUY':
            buy_vol += size
        elif side == 'S' or side == 'SELL':
            sell_vol += size
        # 'M' or 'MARKET' - skip for now (can't determine direction)
    
    total_print_vol = buy_vol + sell_vol
    
    if total_print_vol > 0:
        buy_ratio = buy_vol / total_print_vol
        print(f'   📊 Buy Volume: {buy_vol:,.0f} shares ({buy_ratio:.1%})')
        print(f'   📊 Sell Volume: {sell_vol:,.0f} shares ({1-buy_ratio:.1%})')
        print(f'   📊 Buy/Sell Ratio: {buy_ratio:.2f}')
        
        if buy_ratio > 0.55:
            print(f'   🟢 BULLISH: Institutions buying ({buy_ratio:.1%})')
        elif buy_ratio < 0.45:
            print(f'   🔴 BEARISH: Institutions selling ({buy_ratio:.1%})')
        else:
            print(f'   ⚪ NEUTRAL: Balanced flow')
    
    # Show largest prints
    if dp_prints:
        print(f'\n   🔝 TOP 5 LARGEST PRINTS:')
        def get_value(print_data):
            val = print_data.get('value', print_data.get('notional', 0))
            if isinstance(val, str):
                try:
                    return float(val.replace(',', '').replace('$', ''))
                except:
                    return 0
            return float(val) if val else 0
        
        sorted_prints = sorted(dp_prints, key=get_value, reverse=True)[:5]
        for i, p in enumerate(sorted_prints, 1):
            side = p.get('side', 'unknown').upper()
            price = p.get('price', 0)
            if isinstance(price, str):
                try:
                    price = float(price)
                except:
                    price = 0
            size = p.get('size', p.get('volume', p.get('shares', 0)))
            if isinstance(size, str):
                try:
                    size = float(size.replace(',', ''))
                except:
                    size = 0
            else:
                size = float(size) if size else 0
            value = get_value(p)
            print(f'      {i}. {side} @ ${float(price):.2f} - {size:,.0f} shares (${value:,.0f})')
else:
    print('   ⚠️ No dark pool prints found')

# Build institutional context
print(f'\n📊 Building Institutional Context...')
context = engine.build_institutional_context('SPY', yesterday)

if context:
    print(f'   ✅ Context built!')
    print(f'\n   📈 INSTITUTIONAL SUMMARY:')
    print(f'      Dark Pool %: {context.dark_pool_pct:.2f}%')
    print(f'      Battlegrounds: {len(context.dp_battlegrounds)}')
    print(f'      Buying Pressure: {context.institutional_buying_pressure:.1%}')
    print(f'      DP Buy/Sell Ratio: {context.dp_buy_sell_ratio:.2f}')
    
    if context.dp_battlegrounds:
        print(f'\n   🎯 KEY BATTLEGROUNDS:')
        for bg in context.dp_battlegrounds[:5]:
            # Battlegrounds are just price levels (floats)
            print(f'      ${float(bg):.2f}')
    
    # Interpretation
    print(f'\n   💡 INTERPRETATION:')
    if context.dark_pool_pct > 50:
        print(f'      🔒 HIGH DP ACTIVITY ({context.dark_pool_pct:.1f}%) - Institutions very active!')
    else:
        print(f'      📊 Normal DP activity ({context.dark_pool_pct:.1f}%)')
    
    if context.institutional_buying_pressure > 0.6:
        print(f'      🟢 STRONG BUYING ({context.institutional_buying_pressure:.1%}) - Bullish!')
    elif context.institutional_buying_pressure < 0.4:
        print(f'      🔴 STRONG SELLING ({context.institutional_buying_pressure:.1%}) - Bearish!')
    else:
        print(f'      ⚪ Balanced flow ({context.institutional_buying_pressure:.1%})')
    
    # What this means for today
    print(f'\n   🎯 WHAT THIS MEANS FOR TODAY:')
    bg_prices = [f"${float(bg):.2f}" for bg in context.dp_battlegrounds[:3]]
    if context.institutional_buying_pressure > 0.6:
        print(f'      → Institutions were BUYING last night')
        print(f'      → Expect support at battlegrounds: {bg_prices}')
        print(f'      → BULLISH bias for today')
    elif context.institutional_buying_pressure < 0.4:
        print(f'      → Institutions were SELLING last night')
        print(f'      → Expect resistance at battlegrounds: {bg_prices}')
        print(f'      → BEARISH bias for today')
    else:
        print(f'      → Balanced institutional flow')
        print(f'      → Watch battlegrounds: {bg_prices}')
else:
    print('   ❌ Could not build context')

print('\n' + '=' * 80)

