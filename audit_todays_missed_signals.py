#!/usr/bin/env python3
"""
🔥 AUDIT TODAY'S MISSED SIGNALS
What signals should have fired today and at what times?
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add paths
base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)
sys.path.insert(0, os.path.join(base_path, 'core'))
sys.path.insert(0, os.path.join(base_path, 'core', 'data'))
sys.path.insert(0, os.path.join(base_path, 'live_monitoring'))

# Load .env
from dotenv import load_dotenv
load_dotenv()

def audit_signals():
    """
    Audit what signals SHOULD have fired today.
    """
    print("=" * 100)
    print("🔥 AUDIT: WHAT SIGNALS DID WE MISS TODAY?")
    print("=" * 100)
    print()
    
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"📅 Date: {today}")
    print(f"⏰ Current Time: {datetime.now().strftime('%H:%M:%S')}")
    print()
    
    # Initialize API client
    api_key = os.getenv('CHARTEXCHANGE_API_KEY')
    if not api_key:
        print("❌ CHARTEXCHANGE_API_KEY not set!")
        return
    
    from ultimate_chartexchange_client import UltimateChartExchangeClient
    client = UltimateChartExchangeClient(api_key)
    
    # Get price history for timing analysis
    import yfinance as yf
    
    results = {
        'dark_pool': [],
        'selloff_rally': [],
        'gamma': [],
        'squeeze': [],
        'reddit': [],
        'premarket_gap': [],
        'options_flow': [],
    }
    
    # ==========================================================================
    # 1. DARK POOL SIGNALS
    # ==========================================================================
    print("=" * 100)
    print("1️⃣  DARK POOL BATTLEGROUND SIGNALS")
    print("=" * 100)
    
    for symbol in ['SPY', 'QQQ']:
        print(f"\n📊 {symbol}:")
        print("-" * 80)
        
        try:
            # Get DP levels
            levels = client.get_dark_pool_levels(symbol, today)
            if not levels:
                levels = client.get_dark_pool_levels(symbol, yesterday)
                print(f"   ⚠️  Using yesterday's DP data (T+1 delay)")
            
            if not levels:
                print(f"   ❌ No DP levels found")
                continue
            
            # Get price history
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='5m')
            
            if hist.empty:
                print(f"   ❌ No price data")
                continue
            
            # Sort levels by volume
            sorted_levels = sorted(levels, key=lambda x: int(x.get('volume', 0)), reverse=True)[:10]
            
            print(f"   📊 Top 10 DP Levels:")
            
            # Check each level against price history
            for level in sorted_levels:
                level_price = float(level.get('level', level.get('price', 0)))
                level_volume = int(level.get('volume', 0))
                
                # Find when price was near this level
                touches = []
                for idx, row in hist.iterrows():
                    price_low = row['Low']
                    price_high = row['High']
                    
                    # Check if price touched the level (within 0.1%)
                    if abs(price_low - level_price) / level_price < 0.001 or \
                       abs(price_high - level_price) / level_price < 0.001 or \
                       (price_low <= level_price <= price_high):
                        touches.append(idx)
                
                status = "✅ TOUCHED" if touches else "⚠️  Not touched"
                touch_times = [t.strftime('%H:%M') for t in touches[:3]] if touches else []
                
                print(f"      ${level_price:.2f} ({level_volume:,} shares) - {status}")
                if touch_times:
                    print(f"         → Times: {', '.join(touch_times)}")
                    results['dark_pool'].append({
                        'symbol': symbol,
                        'level': level_price,
                        'volume': level_volume,
                        'touch_times': touch_times,
                        'signal_type': 'BATTLEGROUND'
                    })
                    
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # ==========================================================================
    # 2. SELLOFF/RALLY SIGNALS
    # ==========================================================================
    print()
    print("=" * 100)
    print("2️⃣  SELLOFF/RALLY MOMENTUM SIGNALS")
    print("=" * 100)
    
    for symbol in ['SPY', 'QQQ']:
        print(f"\n📊 {symbol}:")
        print("-" * 80)
        
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='1m')
            
            if hist.empty:
                print(f"   ❌ No price data")
                continue
            
            # Calculate from open
            day_open = hist['Open'].iloc[0]
            
            selloffs = []
            rallies = []
            
            for idx, row in hist.iterrows():
                pct_from_open = ((row['Close'] - day_open) / day_open) * 100
                
                if pct_from_open <= -0.25:
                    selloffs.append({
                        'time': idx.strftime('%H:%M'),
                        'pct': pct_from_open,
                        'price': row['Close']
                    })
                elif pct_from_open >= 0.25:
                    rallies.append({
                        'time': idx.strftime('%H:%M'),
                        'pct': pct_from_open,
                        'price': row['Close']
                    })
            
            # Dedupe (only first occurrence of each threshold)
            if selloffs:
                first_selloff = selloffs[0]
                print(f"   🔴 SELLOFF DETECTED: {first_selloff['time']} ({first_selloff['pct']:.2f}% from open)")
                print(f"      → Price: ${first_selloff['price']:.2f} (Open: ${day_open:.2f})")
                results['selloff_rally'].append({
                    'symbol': symbol,
                    'type': 'SELLOFF',
                    'time': first_selloff['time'],
                    'pct': first_selloff['pct']
                })
            else:
                print(f"   ⚪ No selloff detected (threshold: -0.25%)")
            
            if rallies:
                first_rally = rallies[0]
                print(f"   🟢 RALLY DETECTED: {first_rally['time']} (+{first_rally['pct']:.2f}% from open)")
                print(f"      → Price: ${first_rally['price']:.2f} (Open: ${day_open:.2f})")
                results['selloff_rally'].append({
                    'symbol': symbol,
                    'type': 'RALLY',
                    'time': first_rally['time'],
                    'pct': first_rally['pct']
                })
            else:
                print(f"   ⚪ No rally detected (threshold: +0.25%)")
            
            # Show current status
            current_price = hist['Close'].iloc[-1]
            current_pct = ((current_price - day_open) / day_open) * 100
            print(f"   📊 Current: ${current_price:.2f} ({current_pct:+.2f}% from open)")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # ==========================================================================
    # 3. GAMMA SIGNALS
    # ==========================================================================
    print()
    print("=" * 100)
    print("3️⃣  GAMMA FLIP SIGNALS")
    print("=" * 100)
    
    for symbol in ['SPY', 'QQQ']:
        print(f"\n📊 {symbol}:")
        print("-" * 80)
        
        try:
            # Get options data
            options = client.get_options_chain_summary(symbol, today)
            
            if not options:
                print(f"   ⚠️  No options data (API may require premium tier)")
                continue
            
            max_pain = options.get('max_pain', 0)
            total_call_oi = options.get('total_call_oi', 0)
            total_put_oi = options.get('total_put_oi', 0)
            pc_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 0
            
            print(f"   📊 Max Pain: ${max_pain:.2f}")
            print(f"   📊 P/C Ratio: {pc_ratio:.2f}")
            print(f"   📊 Call OI: {total_call_oi:,} | Put OI: {total_put_oi:,}")
            
            # Get current price
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='5m')
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                distance_to_max_pain = ((max_pain - current_price) / current_price) * 100
                print(f"   📊 Distance to Max Pain: {distance_to_max_pain:+.2f}%")
                
                if abs(distance_to_max_pain) < 0.5:
                    print(f"   🎲 GAMMA SIGNAL: Price near max pain!")
                    results['gamma'].append({
                        'symbol': symbol,
                        'max_pain': max_pain,
                        'pc_ratio': pc_ratio,
                        'distance': distance_to_max_pain
                    })
                    
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # ==========================================================================
    # 4. SQUEEZE SIGNALS
    # ==========================================================================
    print()
    print("=" * 100)
    print("4️⃣  SHORT SQUEEZE SIGNALS")
    print("=" * 100)
    
    squeeze_candidates = ['GME', 'AMC', 'TSLA', 'NVDA']
    
    for symbol in squeeze_candidates:
        print(f"\n📊 {symbol}:")
        print("-" * 80)
        
        try:
            short_data = client.get_short_interest(symbol, today)
            
            if not short_data:
                print(f"   ⚠️  No short data available")
                continue
            
            short_interest = short_data.get('short_interest', 0)
            short_ratio = short_data.get('short_ratio', 0)
            days_to_cover = short_data.get('days_to_cover', 0)
            
            print(f"   📊 Short Interest: {short_interest:,} shares")
            print(f"   📊 Short Ratio: {short_ratio:.2f}%")
            print(f"   📊 Days to Cover: {days_to_cover:.1f}")
            
            # Check for squeeze setup
            if short_ratio > 15 or days_to_cover > 3:
                print(f"   🔥 SQUEEZE CANDIDATE!")
                results['squeeze'].append({
                    'symbol': symbol,
                    'short_ratio': short_ratio,
                    'days_to_cover': days_to_cover
                })
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # ==========================================================================
    # SUMMARY
    # ==========================================================================
    print()
    print("=" * 100)
    print("📊 SUMMARY: SIGNALS THAT SHOULD HAVE FIRED TODAY")
    print("=" * 100)
    
    total_signals = 0
    
    print("\n🔒 DARK POOL BATTLEGROUND TOUCHES:")
    for sig in results['dark_pool']:
        print(f"   {sig['symbol']} @ ${sig['level']:.2f} ({sig['volume']:,} shares) - Times: {', '.join(sig['touch_times'])}")
        total_signals += 1
    
    print("\n🚨 SELLOFF/RALLY MOMENTUM:")
    for sig in results['selloff_rally']:
        emoji = "🔴" if sig['type'] == 'SELLOFF' else "🟢"
        print(f"   {emoji} {sig['symbol']} {sig['type']} @ {sig['time']} ({sig['pct']:+.2f}%)")
        total_signals += 1
    
    print("\n🎲 GAMMA FLIP:")
    for sig in results['gamma']:
        print(f"   {sig['symbol']} - Max Pain: ${sig['max_pain']:.2f}, P/C: {sig['pc_ratio']:.2f}")
        total_signals += 1
    
    print("\n🔥 SQUEEZE CANDIDATES:")
    for sig in results['squeeze']:
        print(f"   {sig['symbol']} - Short Ratio: {sig['short_ratio']:.2f}%, DTC: {sig['days_to_cover']:.1f}")
        total_signals += 1
    
    print()
    print("=" * 100)
    print(f"🎯 TOTAL MISSED SIGNALS: {total_signals}")
    print("=" * 100)
    
    # ==========================================================================
    # BACKTESTING COVERAGE MATRIX
    # ==========================================================================
    print()
    print("=" * 100)
    print("📊 BACKTESTING COVERAGE MATRIX")
    print("=" * 100)
    
    coverage = {
        'Fed Watch': {'has_backtest': False, 'file': None, 'notes': 'No dedicated backtest - uses diagnostics'},
        'Trump Intel': {'has_backtest': False, 'file': None, 'notes': 'No dedicated backtest'},
        'Economic AI': {'has_backtest': False, 'file': None, 'notes': 'Uses economic_intelligence pattern learning'},
        'Selloff/Rally': {'has_backtest': True, 'file': 'backtesting/simulation/reddit_momentum_backtest.py', 'notes': 'Partial - tests momentum'},
        'Dark Pool': {'has_backtest': True, 'file': 'backtesting/simulation/current_system.py', 'notes': 'Full DP backtest'},
        'Reddit Exploiter': {'has_backtest': True, 'file': 'backtesting/simulation/reddit_enhanced_backtest.py', 'notes': 'Full with DP synthesis'},
        'Squeeze Detector': {'has_backtest': True, 'file': 'backtesting/simulation/squeeze_detector.py', 'notes': 'Full backtest'},
        'Gamma Tracker': {'has_backtest': True, 'file': 'backtesting/simulation/gamma_detector.py', 'notes': 'Full backtest'},
        'Short Interest': {'has_backtest': False, 'file': None, 'notes': 'Part of squeeze detector'},
        'Pre-Market Gap': {'has_backtest': False, 'file': None, 'notes': 'NEW - needs backtest'},
        'Options Flow': {'has_backtest': False, 'file': None, 'notes': 'NEW - needs backtest'},
        'Gamma Flip': {'has_backtest': False, 'file': None, 'notes': 'NEW - needs backtest'},
        'Signal Brain': {'has_backtest': True, 'file': 'backtesting/simulation/narrative_brain.py', 'notes': 'Full backtest'},
    }
    
    print(f"\n{'Signal Type':<20} {'Backtest?':<12} {'Notes':<50}")
    print("-" * 82)
    
    for signal, info in coverage.items():
        status = "✅ YES" if info['has_backtest'] else "❌ NO"
        print(f"{signal:<20} {status:<12} {info['notes']:<50}")
    
    backtest_count = sum(1 for info in coverage.values() if info['has_backtest'])
    print()
    print(f"📊 Backtest Coverage: {backtest_count}/{len(coverage)} ({backtest_count/len(coverage)*100:.0f}%)")
    print()
    
    # Signals needing backtest
    needs_backtest = [k for k, v in coverage.items() if not v['has_backtest']]
    print(f"⚠️  SIGNALS NEEDING BACKTEST: {', '.join(needs_backtest)}")
    

if __name__ == "__main__":
    audit_signals()

