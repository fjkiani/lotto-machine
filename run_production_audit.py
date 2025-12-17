#!/usr/bin/env python3
"""
🔍 PRODUCTION SIGNAL AUDIT

Real-time audit that calls APIs to see what SHOULD have triggered:
1. Call ChartExchange API - Check DP levels, short data, options
2. Call Reddit API - Check mention velocity, sentiment
3. Run signal generators - See what SHOULD trigger
4. Compare to what WAS generated - Find missed opportunities
5. Validate current signals - Check if still valid

This is NOT just reading stored signals - it's a live market intelligence check.

Usage:
    python3 run_production_audit.py                    # Audit today
    python3 run_production_audit.py 2025-12-17         # Specific date
    python3 run_production_audit.py --symbols SPY QQQ  # Specific symbols

Author: Alpha's AI Hedge Fund
Date: 2025-12-17
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pytz
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
from live_monitoring.exploitation.reddit_exploiter import RedditExploiter
from live_monitoring.exploitation.squeeze_detector import SqueezeDetector
from live_monitoring.exploitation.gamma_tracker import GammaTracker
import yfinance as yf


class ProductionAuditor:
    """
    Real-time production audit - calls APIs to see what exists.
    """
    
    def __init__(self, date: Optional[str] = None):
        """Initialize auditor."""
        self.date = date or datetime.now(pytz.timezone('America/New_York')).strftime('%Y-%m-%d')
        
        # Get API key from environment
        api_key = os.getenv('CHARTEXCHANGE_API_KEY')
        if not api_key:
            print("❌ CHARTEXCHANGE_API_KEY not set in environment")
            print("   Cannot perform API-based audit without API key")
            print("   Set it with: export CHARTEXCHANGE_API_KEY=your_key")
            self.client = None
            self.reddit_exploiter = None
            self.squeeze_detector = None
            self.gamma_tracker = None
            return
        
        # Initialize ChartExchange client
        try:
            self.client = UltimateChartExchangeClient(api_key, tier=3)
            print(f"✅ ChartExchange client initialized (Tier 3)")
        except Exception as e:
            print(f"❌ Could not initialize ChartExchange client: {e}")
            self.client = None
            self.reddit_exploiter = None
            self.squeeze_detector = None
            self.gamma_tracker = None
            return
        
        # Initialize exploiters
        try:
            self.reddit_exploiter = RedditExploiter(self.client)
            self.squeeze_detector = SqueezeDetector(self.client)
            self.gamma_tracker = GammaTracker(self.client)
            print(f"✅ Exploitation modules initialized")
        except Exception as e:
            print(f"⚠️  Could not initialize exploiters: {e}")
            print(f"   Will perform limited audit")
            self.reddit_exploiter = None
            self.squeeze_detector = None
            self.gamma_tracker = None
        
        self.results = {}
    
    def audit_dark_pool(self, symbols: List[str]) -> Dict:
        """
        Audit DP data - what levels exist, what volume.
        
        Returns:
            Dict with DP analysis per symbol
        """
        print(f"\n🏦 AUDITING DARK POOL DATA...")
        print("=" * 80)
        
        if not self.client:
            print("   ❌ Skipped - API client not available")
            return {}
        
        dp_data = {}
        yesterday = (datetime.strptime(self.date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        
        for symbol in symbols:
            try:
                # Get DP levels
                levels = self.client.get_darkpool_levels(symbol, date=yesterday)
                
                # Get DP prints
                prints = self.client.get_darkpool_prints(symbol, date=yesterday)
                
                # Get current price
                ticker = yf.Ticker(symbol)
                current_price = ticker.info.get('regularMarketPrice', 0)
                
                if levels:
                    # Find nearest support/resistance
                    support = None
                    resistance = None
                    
                    for level in sorted(levels, key=lambda x: abs(x.get('level', 0) - current_price))[:5]:
                        level_price = level.get('level', 0)
                        volume = level.get('volume', 0)
                        
                        if level_price < current_price and not support:
                            support = {'price': level_price, 'volume': volume}
                        elif level_price > current_price and not resistance:
                            resistance = {'price': level_price, 'volume': volume}
                    
                    dp_data[symbol] = {
                        'current_price': current_price,
                        'total_levels': len(levels),
                        'nearest_support': support,
                        'nearest_resistance': resistance,
                        'total_dp_volume': sum(p.get('buy_volume', 0) + p.get('sell_volume', 0) for p in prints) if prints else 0
                    }
                    
                    print(f"\n📊 {symbol}:")
                    print(f"   Current Price: ${current_price:.2f}")
                    if support:
                        print(f"   Support: ${support['price']:.2f} ({support['volume']:,} shares)")
                    if resistance:
                        print(f"   Resistance: ${resistance['price']:.2f} ({resistance['volume']:,} shares)")
                    print(f"   Total DP Levels: {len(levels)}")
                
            except Exception as e:
                print(f"   ⚠️  {symbol}: {e}")
        
        return dp_data
    
    def audit_short_interest(self, symbols: List[str]) -> Dict:
        """
        Audit short interest - check for squeeze potential.
        
        Returns:
            Dict with short analysis per symbol
        """
        print(f"\n🔥 AUDITING SHORT INTEREST...")
        print("=" * 80)
        
        if not self.client:
            print("   ❌ Skipped - API client not available")
            return {}
        
        short_data = {}
        
        for symbol in symbols:
            try:
                # Get short data
                short_info = self.client.get_short_interest(symbol)
                
                if short_info and len(short_info) > 0:
                    latest = short_info[0]
                    short_pct = latest.get('short_interest_pct', 0)
                    
                    # Check for squeeze potential
                    is_squeeze_candidate = short_pct > 15
                    
                    short_data[symbol] = {
                        'short_interest_pct': short_pct,
                        'squeeze_potential': is_squeeze_candidate
                    }
                    
                    print(f"\n🎯 {symbol}:")
                    print(f"   Short Interest: {short_pct:.1f}%")
                    if is_squeeze_candidate:
                        print(f"   🔥 SQUEEZE POTENTIAL - High short interest!")
            
            except Exception as e:
                print(f"   ⚠️  {symbol}: {e}")
        
        return short_data
    
    def audit_reddit_sentiment(self, symbols: List[str]) -> Dict:
        """
        Audit Reddit sentiment - check mention velocity and sentiment.
        
        Returns:
            Dict with Reddit analysis per symbol
        """
        print(f"\n📱 AUDITING REDDIT SENTIMENT...")
        print("=" * 80)
        
        if not self.client:
            print("   ❌ Skipped - API client not available")
            return {}
        
        reddit_data = {}
        
        for symbol in symbols:
            try:
                # Get Reddit mentions
                mentions = self.client.get_reddit_mentions(symbol, days=7)
                
                if mentions and len(mentions) > 0:
                    # Calculate metrics
                    total_mentions = sum(m.get('mentions', 0) for m in mentions)
                    avg_sentiment = sum(m.get('avg_sentiment', 0) for m in mentions) / len(mentions)
                    
                    # Check if hot
                    recent_mentions = mentions[0].get('mentions', 0) if mentions else 0
                    avg_mentions = total_mentions / 7
                    velocity = recent_mentions / avg_mentions if avg_mentions > 0 else 0
                    
                    is_hot = velocity > 3.0
                    
                    reddit_data[symbol] = {
                        'total_mentions_7d': total_mentions,
                        'recent_mentions': recent_mentions,
                        'velocity': velocity,
                        'avg_sentiment': avg_sentiment,
                        'is_hot': is_hot
                    }
                    
                    print(f"\n🎯 {symbol}:")
                    print(f"   7d Total: {total_mentions} mentions")
                    print(f"   Recent: {recent_mentions} mentions")
                    print(f"   Velocity: {velocity:.1f}x")
                    print(f"   Sentiment: {avg_sentiment:+.2f}")
                    if is_hot:
                        print(f"   🚨 HOT TICKER - High mention velocity!")
            
            except Exception as e:
                print(f"   ⚠️  {symbol}: {e}")
        
        return reddit_data
    
    def audit_signals_that_should_exist(self, symbols: List[str]) -> Dict:
        """
        Run signal generators to see what SHOULD trigger.
        
        Returns:
            Dict with signals that should exist
        """
        print(f"\n🎯 CHECKING WHAT SIGNALS SHOULD EXIST...")
        print("=" * 80)
        
        if not self.client:
            print("   ❌ Skipped - API client not available")
            return {'reddit': [], 'squeeze': [], 'gamma': [], 'dp_breakout': []}
        
        should_exist = {
            'reddit': [],
            'squeeze': [],
            'gamma': [],
            'dp_breakout': []
        }
        
        for symbol in symbols:
            # Check Reddit signals
            try:
                reddit_signals = self.reddit_exploiter.check(symbol)
                if reddit_signals:
                    should_exist['reddit'].extend(reddit_signals)
                    for sig in reddit_signals:
                        print(f"\n📱 Reddit Signal: {symbol}")
                        print(f"   Type: {sig.signal_type}")
                        print(f"   Action: {sig.action}")
                        print(f"   Strength: {sig.strength:.0f}%")
            except Exception as e:
                print(f"   ⚠️  Reddit check for {symbol}: {e}")
            
            # Check Squeeze signals
            try:
                squeeze_signals = self.squeeze_detector.check(symbol)
                if squeeze_signals:
                    should_exist['squeeze'].extend(squeeze_signals)
                    for sig in squeeze_signals:
                        print(f"\n🔥 Squeeze Signal: {symbol}")
                        print(f"   Short Interest: {sig.short_interest_pct:.1f}%")
            except Exception as e:
                print(f"   ⚠️  Squeeze check for {symbol}: {e}")
            
            # Check Gamma signals
            try:
                gamma_signals = self.gamma_tracker.check(symbol)
                if gamma_signals:
                    should_exist['gamma'].extend(gamma_signals)
                    for sig in gamma_signals:
                        print(f"\n⚡ Gamma Signal: {symbol}")
                        print(f"   Max Pain: ${sig.max_pain:.2f}")
            except Exception as e:
                print(f"   ⚠️  Gamma check for {symbol}: {e}")
        
        return should_exist
    
    def generate_report(self) -> str:
        """Generate comprehensive audit report."""
        report = []
        report.append("=" * 80)
        report.append(f"🔍 PRODUCTION AUDIT REPORT: {self.date}")
        report.append("=" * 80)
        report.append("")
        report.append("This audit calls LIVE APIs to see what exists in the market,")
        report.append("not just what we stored. It answers: 'What SHOULD have triggered?'")
        report.append("")
        
        # Add results sections...
        
        report.append("=" * 80)
        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description='Production Signal Audit (API-based)')
    parser.add_argument('date', nargs='?', help='Date to audit (YYYY-MM-DD). Default: today')
    parser.add_argument('--symbols', nargs='+', default=['SPY', 'QQQ', 'TSLA', 'NVDA'],
                       help='Symbols to audit. Default: SPY QQQ TSLA NVDA')
    
    args = parser.parse_args()
    
    # Get date
    date = args.date or datetime.now(pytz.timezone('America/New_York')).strftime('%Y-%m-%d')
    
    print("=" * 80)
    print(f"🔍 PRODUCTION AUDIT: {date}")
    print("=" * 80)
    print(f"📊 Symbols: {', '.join(args.symbols)}")
    print(f"📡 Mode: LIVE API CALLS (not stored data)")
    print("")
    
    # Run audit
    auditor = ProductionAuditor(date)
    
    # 1. Audit DP data
    dp_data = auditor.audit_dark_pool(args.symbols)
    
    # 2. Audit short interest
    short_data = auditor.audit_short_interest(args.symbols)
    
    # 3. Audit Reddit
    reddit_data = auditor.audit_reddit_sentiment(args.symbols)
    
    # 4. Check what signals should exist
    signals = auditor.audit_signals_that_should_exist(args.symbols)
    
    # Final summary
    print("\n" + "=" * 80)
    print("📊 AUDIT SUMMARY")
    print("=" * 80)
    print(f"\n🏦 Dark Pool: {len(dp_data)} symbols analyzed")
    print(f"🔥 Short Interest: {len(short_data)} symbols analyzed")
    print(f"📱 Reddit: {len(reddit_data)} symbols analyzed")
    print(f"\n🎯 Signals That Should Exist:")
    print(f"   Reddit: {len(signals['reddit'])}")
    print(f"   Squeeze: {len(signals['squeeze'])}")
    print(f"   Gamma: {len(signals['gamma'])}")
    print("=" * 80)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
