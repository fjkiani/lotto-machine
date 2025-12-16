#!/usr/bin/env python3
"""
🔥 FIND SQUEEZE CANDIDATES
Scans for stocks with actual squeeze characteristics right now.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
from live_monitoring.exploitation.squeeze_detector import SqueezeDetector
import logging

logging.basicConfig(level=logging.WARNING)  # Suppress info logs

def find_squeeze_candidates():
    """Find stocks with actual squeeze characteristics"""
    
    api_key = os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
    if not api_key:
        print("❌ No API key!")
        return
    
    client = UltimateChartExchangeClient(api_key, tier=3)
    detector = SqueezeDetector(client)
    
    # Known squeeze candidates + high SI stocks
    candidates = [
        'GME', 'AMC', 'BBBY', 'SPRT', 'EXPR', 'NAKD', 'SNDL',  # Meme stocks
        'TSLA', 'NVDA', 'AMD', 'PLTR', 'RBLX',  # High SI tech
        'RIVN', 'LCID', 'F', 'NIO',  # EV stocks
    ]
    
    print("="*70)
    print("🔥 SCANNING FOR SQUEEZE CANDIDATES")
    print("="*70)
    print()
    
    results = []
    
    for symbol in candidates:
        try:
            signal = detector.analyze(symbol)
            
            if signal:
                results.append({
                    'symbol': symbol,
                    'score': signal.score,
                    'si_pct': signal.short_interest_pct,
                    'borrow_fee': signal.borrow_fee_pct,
                    'ftd_spike': signal.ftd_spike_ratio,
                    'entry': signal.entry_price,
                    'target': signal.target_price,
                    'rr': signal.risk_reward_ratio
                })
                print(f"✅ {symbol}: Score {signal.score:.1f}/100")
                print(f"   SI: {signal.short_interest_pct:.1f}% | Borrow: {signal.borrow_fee_pct:.1f}% | FTD: {signal.ftd_spike_ratio:.2f}x")
                print(f"   Entry: ${signal.entry_price:.2f} | Target: ${signal.target_price:.2f} | R/R: {signal.risk_reward_ratio:.1f}:1")
                print()
            else:
                # Get raw data to see why no signal
                si_data = client.get_short_interest_daily(symbol)
                borrow_data = client.get_borrow_fee(symbol)
                
                si_pct = 0
                if si_data and isinstance(si_data, list) and len(si_data) > 0:
                    si_pct = float(si_data[0].get('short_interest', 0))
                
                borrow_fee = borrow_data.fee_rate if borrow_data else 0
                
                print(f"❌ {symbol}: SI={si_pct:.1f}%, Borrow={borrow_fee:.1f}% (below threshold)")
        
        except Exception as e:
            print(f"⚠️  {symbol}: Error - {e}")
    
    print("="*70)
    print(f"📊 RESULTS: {len(results)} squeeze signals found")
    print("="*70)
    
    if results:
        print("\n🔥 TOP SQUEEZE CANDIDATES:")
        results.sort(key=lambda x: x['score'], reverse=True)
        for i, r in enumerate(results[:5], 1):
            print(f"{i}. {r['symbol']}: Score {r['score']:.1f}/100")
            print(f"   SI: {r['si_pct']:.1f}% | Borrow: {r['borrow_fee']:.1f}% | Entry: ${r['entry']:.2f}")
    
    return results

if __name__ == "__main__":
    find_squeeze_candidates()


