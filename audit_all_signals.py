#!/usr/bin/env python3
"""
🎯 UNIFIED SIGNAL AUDIT SCRIPT
================================
Run this anytime to audit all signal types and see what should have triggered.

Usage:
    python3 audit_all_signals.py                 # Audit today
    python3 audit_all_signals.py --date 2025-12-18   # Audit specific date
    python3 audit_all_signals.py --days 7        # Audit last 7 days

Author: Zo (Alpha's AI)
"""

import os
import sys
import sqlite3
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Add paths for imports
base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)
sys.path.insert(0, os.path.join(base_path, 'core', 'data'))
sys.path.insert(0, os.path.join(base_path, 'live_monitoring'))
sys.path.insert(0, os.path.join(base_path, 'backtesting', 'simulation'))

# Load environment
from dotenv import load_dotenv
load_dotenv()


class SignalAuditor:
    """Comprehensive signal auditor for all signal types"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('CHARTEXCHANGE_API_KEY')
        self.results = {}
    
    def audit_selloff_rally(self, date: str, symbols: List[str] = ['SPY', 'QQQ']) -> Dict:
        """Audit selloff/rally signals"""
        print("\n" + "=" * 60)
        print("🚨 SELLOFF/RALLY SIGNALS")
        print("=" * 60)
        
        try:
            import yfinance as yf
            
            results = []
            for symbol in symbols:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='5d', interval='1m')
                
                # Filter to specific date
                if not hist.empty:
                    target_date = datetime.strptime(date, '%Y-%m-%d').date()
                    hist = hist[hist.index.date == target_date]
                
                if hist.empty:
                    print(f"   ❌ No data for {symbol} on {date}")
                    continue
                
                day_open = hist['Open'].iloc[0]
                
                # Detect selloff signals
                selloff_times = []
                for idx, row in hist.iterrows():
                    pct = ((row['Close'] - day_open) / day_open) * 100
                    if pct <= -0.25:
                        selloff_times.append({
                            'time': idx,
                            'price': row['Close'],
                            'pct_from_open': pct
                        })
                
                # Detect rally signals  
                rally_times = []
                for idx, row in hist.iterrows():
                    pct = ((row['Close'] - day_open) / day_open) * 100
                    if pct >= 0.25:
                        rally_times.append({
                            'time': idx,
                            'price': row['Close'],
                            'pct_from_open': pct
                        })
                
                if selloff_times:
                    first = selloff_times[0]
                    print(f"   ✅ {symbol} SELLOFF: First at {first['time'].strftime('%H:%M')}")
                    print(f"      Price: ${first['price']:.2f} ({first['pct_from_open']:.2f}% from open)")
                    print(f"      Total triggers: {len(selloff_times)}")
                
                if rally_times:
                    first = rally_times[0]
                    print(f"   ✅ {symbol} RALLY: First at {first['time'].strftime('%H:%M')}")
                    print(f"      Price: ${first['price']:.2f} ({first['pct_from_open']:.2f}% from open)")
                    print(f"      Total triggers: {len(rally_times)}")
                
                if not selloff_times and not rally_times:
                    print(f"   ⚪ {symbol}: No selloff/rally signals (range-bound day)")
                
                results.append({
                    'symbol': symbol,
                    'selloffs': len(selloff_times),
                    'rallies': len(rally_times)
                })
            
            self.results['selloff_rally'] = results
            return results
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {}
    
    def audit_dark_pool(self, date: str, symbols: List[str] = ['SPY', 'QQQ']) -> Dict:
        """Audit dark pool signals"""
        print("\n" + "=" * 60)
        print("🔒 DARK POOL SIGNALS")
        print("=" * 60)
        
        try:
            from ultimate_chartexchange_client import UltimateChartExchangeClient
            
            client = UltimateChartExchangeClient(api_key=self.api_key)
            results = []
            
            for symbol in symbols:
                yesterday = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
                
                dp_data = client.get_dark_pool_levels(symbol, yesterday)
                
                if dp_data and 'levels' in dp_data:
                    levels = dp_data['levels'][:5]  # Top 5
                    print(f"   ✅ {symbol}: {len(dp_data['levels'])} DP levels found")
                    for lvl in levels:
                        price = lvl.get('level') or lvl.get('price', 0)
                        vol = lvl.get('volume', 0)
                        print(f"      ${price:.2f} | {vol:,} shares")
                    
                    results.append({
                        'symbol': symbol,
                        'levels': len(dp_data['levels']),
                        'top_level': levels[0] if levels else None
                    })
                else:
                    print(f"   ⚪ {symbol}: No DP levels (T+1 delay)")
                    results.append({'symbol': symbol, 'levels': 0})
            
            self.results['dark_pool'] = results
            return results
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {}
    
    def audit_gamma(self, date: str, symbols: List[str] = ['SPY', 'QQQ']) -> Dict:
        """Audit gamma flip signals"""
        print("\n" + "=" * 60)
        print("📊 GAMMA FLIP SIGNALS")
        print("=" * 60)
        
        try:
            from core.gamma_exposure import GammaExposureTracker
            
            tracker = GammaExposureTracker(api_key=self.api_key)
            results = []
            
            for symbol in symbols:
                try:
                    flip_level = tracker.find_gamma_flip_level(symbol)
                    
                    if flip_level:
                        print(f"   ✅ {symbol}: Gamma flip at ${flip_level:.2f}")
                        results.append({'symbol': symbol, 'flip_level': flip_level})
                    else:
                        print(f"   ⚪ {symbol}: No gamma flip level calculated")
                        results.append({'symbol': symbol, 'flip_level': None})
                except Exception as e:
                    print(f"   ⚪ {symbol}: {e}")
                    results.append({'symbol': symbol, 'flip_level': None})
            
            self.results['gamma'] = results
            return results
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {}
    
    def audit_reddit(self, date: str) -> Dict:
        """Audit Reddit signals from database"""
        print("\n" + "=" * 60)
        print("📱 REDDIT SIGNALS")
        print("=" * 60)
        
        db_path = 'data/reddit_signal_tracking.db'
        
        if not os.path.exists(db_path):
            print("   ⚪ No Reddit signal database found")
            return {}
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT symbol, signal_type, action, entry_price, timestamp
                FROM signals
                WHERE DATE(timestamp) = ?
                ORDER BY timestamp DESC
            """, (date,))
            
            signals = cursor.fetchall()
            
            if signals:
                print(f"   ✅ {len(signals)} Reddit signals on {date}:")
                for symbol, sig_type, action, price, ts in signals[:10]:
                    print(f"      {ts[:16]} | {symbol} | {sig_type} | {action} @ ${price:.2f}")
            else:
                print(f"   ⚪ No Reddit signals on {date}")
            
            conn.close()
            
            self.results['reddit'] = signals
            return {'signals': signals}
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {}
    
    def audit_alerts(self, date: str) -> Dict:
        """Audit alerts sent from database"""
        print("\n" + "=" * 60)
        print("🔔 ALERTS SENT")
        print("=" * 60)
        
        db_path = 'data/alerts_history.db'
        
        if not os.path.exists(db_path):
            print("   ⚪ No alerts database found")
            return {}
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT alert_type, source, symbol, timestamp
                FROM alerts
                WHERE DATE(timestamp) = ?
                ORDER BY timestamp DESC
            """, (date,))
            
            alerts = cursor.fetchall()
            
            if alerts:
                print(f"   ✅ {len(alerts)} alerts sent on {date}:")
                
                # Group by type
                by_type = {}
                for alert_type, source, symbol, ts in alerts:
                    key = alert_type or source or 'unknown'
                    if key not in by_type:
                        by_type[key] = 0
                    by_type[key] += 1
                
                for alert_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
                    print(f"      {alert_type}: {count}")
            else:
                print(f"   ⚪ No alerts on {date}")
            
            conn.close()
            
            self.results['alerts'] = alerts
            return {'alerts': alerts}
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {}
    
    def audit_dp_learning(self, date: str) -> Dict:
        """Audit DP learning engine interactions"""
        print("\n" + "=" * 60)
        print("🧠 DP LEARNING ENGINE")
        print("=" * 60)
        
        db_path = 'data/dp_learning.db'
        
        if not os.path.exists(db_path):
            print("   ⚪ No DP learning database found")
            return {}
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT symbol, outcome, confidence
                FROM dp_interactions
                WHERE DATE(timestamp) = ?
            """, (date,))
            
            interactions = cursor.fetchall()
            
            if interactions:
                print(f"   ✅ {len(interactions)} DP interactions on {date}:")
                
                # Calculate stats
                bounces = sum(1 for _, o, _ in interactions if o == 'bounce')
                breaks = sum(1 for _, o, _ in interactions if o == 'break')
                total = bounces + breaks
                
                if total > 0:
                    print(f"      Bounces: {bounces} ({bounces/total*100:.0f}%)")
                    print(f"      Breaks: {breaks} ({breaks/total*100:.0f}%)")
            else:
                print(f"   ⚪ No DP interactions on {date}")
            
            conn.close()
            
            self.results['dp_learning'] = interactions
            return {'interactions': interactions}
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {}
    
    def run_full_audit(self, date: str, symbols: List[str] = ['SPY', 'QQQ']) -> Dict:
        """Run complete audit for a date"""
        print("\n" + "=" * 80)
        print(f"🎯 FULL SIGNAL AUDIT: {date}")
        print("=" * 80)
        
        self.audit_selloff_rally(date, symbols)
        self.audit_dark_pool(date, symbols)
        self.audit_gamma(date, symbols)
        self.audit_reddit(date)
        self.audit_alerts(date)
        self.audit_dp_learning(date)
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 AUDIT SUMMARY")
        print("=" * 80)
        
        selloff_count = sum(r.get('selloffs', 0) + r.get('rallies', 0) 
                          for r in self.results.get('selloff_rally', []))
        dp_count = sum(r.get('levels', 0) for r in self.results.get('dark_pool', []))
        reddit_count = len(self.results.get('reddit', []))
        alerts_count = len(self.results.get('alerts', []))
        
        print(f"   Selloff/Rally triggers: {selloff_count}")
        print(f"   Dark Pool levels: {dp_count}")
        print(f"   Reddit signals: {reddit_count}")
        print(f"   Total alerts sent: {alerts_count}")
        
        return self.results


def main():
    parser = argparse.ArgumentParser(description='Audit all signal types')
    parser.add_argument('--date', type=str, help='Date to audit (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, default=1, help='Number of days to audit')
    parser.add_argument('--symbols', nargs='+', default=['SPY', 'QQQ'], help='Symbols to audit')
    
    args = parser.parse_args()
    
    if args.date:
        dates = [args.date]
    else:
        dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') 
                 for i in range(args.days)]
    
    auditor = SignalAuditor()
    
    for date in dates:
        auditor.run_full_audit(date, args.symbols)
        print()


if __name__ == "__main__":
    main()

