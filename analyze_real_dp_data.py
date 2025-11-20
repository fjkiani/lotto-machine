#!/usr/bin/env python3
"""
ANALYZE REAL DP DATA FROM 10/16
- Process the actual ChartExchange DP levels data
- Identify key support/resistance levels
- Calculate institutional battlegrounds
- Validate our DP filter logic
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json

def analyze_real_dp_data():
    """Analyze the real DP data from 10/16"""
    print('🎯 ANALYZING REAL DP DATA FROM 10/16')
    print('=' * 60)
    
    # Load the CSV data
    df = pd.read_csv('data/cx_dark_pool_levels_nyse-spy_2025-10-16_17607558648217.csv')
    
    print(f'📊 Total DP levels: {len(df)}')
    print(f'📊 Price range: ${df["level"].min():.2f} - ${df["level"].max():.2f}')
    print(f'📊 Total volume: {df["volume"].sum():,} shares')
    print(f'📊 Total trades: {df["trades"].sum():,}')
    
    # Sort by volume (highest first)
    df_sorted = df.sort_values('volume', ascending=False)
    
    print('\n🔥 TOP 10 DP LEVELS BY VOLUME:')
    print('-' * 50)
    for i, row in df_sorted.head(10).iterrows():
        print(f'{row["level"]:8.2f} | {row["volume"]:8,} shares | {row["trades"]:4} trades | ${row["premium"]:12,.0f}')
    
    # Identify institutional battlegrounds (>1M shares)
    battlegrounds = df[df['volume'] > 1000000].sort_values('volume', ascending=False)
    print(f'\n⚔️ INSTITUTIONAL BATTLEGROUNDS (>1M shares): {len(battlegrounds)}')
    print('-' * 60)
    for i, row in battlegrounds.iterrows():
        print(f'{row["level"]:8.2f} | {row["volume"]:8,} shares | {row["trades"]:4} trades')
    
    # Calculate support/resistance levels
    current_price = 664.39  # SPY current price
    
    support_levels = df[df['level'] < current_price].sort_values('level', ascending=False)
    resistance_levels = df[df['level'] > current_price].sort_values('level', ascending=True)
    
    print(f'\n📈 SUPPORT LEVELS (below ${current_price}): {len(support_levels)}')
    print('-' * 50)
    for i, row in support_levels.head(10).iterrows():
        distance = current_price - row['level']
        print(f'{row["level"]:8.2f} | ${distance:5.2f} below | {row["volume"]:8,} shares')
    
    print(f'\n📉 RESISTANCE LEVELS (above ${current_price}): {len(resistance_levels)}')
    print('-' * 50)
    for i, row in resistance_levels.head(10).iterrows():
        distance = row['level'] - current_price
        print(f'{row["level"]:8.2f} | ${distance:5.2f} above | {row["volume"]:8,} shares')
    
    # Find levels near current price (within 3%)
    near_levels = df[abs(df['level'] - current_price) / current_price <= 0.03].sort_values('volume', ascending=False)
    print(f'\n🎯 LEVELS NEAR CURRENT PRICE (within 3%): {len(near_levels)}')
    print('-' * 60)
    for i, row in near_levels.head(5).iterrows():
        distance = row['level'] - current_price
        pct_distance = (distance / current_price) * 100
        print(f'{row["level"]:8.2f} | ${distance:+6.2f} ({pct_distance:+4.1f}%) | {row["volume"]:8,} shares')
    
    # Calculate DP strength metrics
    total_volume = df['volume'].sum()
    avg_volume_per_level = df['volume'].mean()
    max_volume = df['volume'].max()
    
    print(f'\n📊 DP STRENGTH METRICS:')
    print('-' * 30)
    print(f'Total Volume: {total_volume:,} shares')
    print(f'Average per Level: {avg_volume_per_level:,.0f} shares')
    print(f'Max Volume: {max_volume:,} shares')
    print(f'DP Strength Score: {min(total_volume / 10000000, 1.0):.2f}')
    
    # Save analysis results
    analysis = {
        'date': '2025-10-16',
        'total_levels': len(df),
        'price_range': {
            'min': float(df['level'].min()),
            'max': float(df['level'].max())
        },
        'total_volume': int(total_volume),
        'total_trades': int(df['trades'].sum()),
        'battlegrounds': battlegrounds[['level', 'volume', 'trades']].to_dict('records'),
        'support_levels': support_levels[['level', 'volume', 'trades']].head(20).to_dict('records'),
        'resistance_levels': resistance_levels[['level', 'volume', 'trades']].head(20).to_dict('records'),
        'near_levels': near_levels[['level', 'volume', 'trades']].head(10).to_dict('records'),
        'dp_strength_score': float(min(total_volume / 10000000, 1.0))
    }
    
    with open('analysis_results/dp_analysis_10_16.json', 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f'\n💾 Analysis saved to: analysis_results/dp_analysis_10_16.json')
    
    return analysis

if __name__ == '__main__':
    analyze_real_dp_data()