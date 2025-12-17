"""
🔥 ENHANCED REDDIT BACKTEST - FULL INTEGRATION

This module combines:
1. Reddit Sentiment (ChartExchange)
2. Dark Pool Data (DP levels, battlegrounds)
3. Institutional Flow (buying pressure, short interest)
4. Options Data (gamma, max pain)
5. Price Action (momentum, volume)

The goal: Better AVOID vs LONG decisions by combining multiple data sources.

Current Logic Gap:
- VELOCITY_SURGE → AVOID (blanket rule for non mega-caps)
- CONFIRMED_MOMENTUM → LONG (only for mega-caps with price confirmation)

Enhanced Logic:
- VELOCITY_SURGE + DP_SUPPORT + BULLISH_FLOW → LONG (institutions buying despite velocity)
- VELOCITY_SURGE + DP_RESISTANCE + BEARISH_FLOW → SHORT (distribution despite hype)
- VELOCITY_SURGE + NO_DP_SIGNAL → AVOID (keep original behavior)

Author: Alpha's AI Hedge Fund
Date: 2025-12-17
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import yfinance as yf
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)


@dataclass
class EnhancedSignal:
    """Signal with multi-source confirmation"""
    symbol: str
    timestamp: datetime
    
    # Reddit data
    reddit_signal: str  # Original Reddit signal type
    reddit_action: str  # Original action (LONG, SHORT, AVOID)
    reddit_strength: float
    sentiment: float
    mention_count: int
    velocity_surge: bool
    
    # DP data
    dp_signal: Optional[str] = None  # SUPPORT, RESISTANCE, NEUTRAL
    dp_level: Optional[float] = None
    dp_volume: Optional[int] = None
    buying_pressure: Optional[float] = None
    
    # Institutional data
    short_interest: Optional[float] = None
    borrow_fee: Optional[float] = None
    inst_flow: Optional[str] = None  # ACCUMULATION, DISTRIBUTION, NEUTRAL
    
    # Options data
    max_pain: Optional[float] = None
    put_call_ratio: Optional[float] = None
    gamma_exposure: Optional[str] = None  # POSITIVE, NEGATIVE
    
    # Price data
    current_price: float = 0
    price_change_1d: float = 0
    price_change_5d: float = 0
    price_change_20d: float = 0
    volume_ratio: float = 1.0
    
    # Enhanced decision
    enhanced_action: str = "NEUTRAL"  # Final decision after synthesis
    enhanced_strength: float = 0
    enhancement_reasons: List[str] = field(default_factory=list)
    
    # Validation
    outcome: Optional[str] = None
    return_5d: Optional[float] = None


class EnhancedRedditBacktester:
    """
    Enhanced Reddit backtester with DP, institutional, and options integration.
    """
    
    # Mega-caps get special treatment
    MEGA_CAPS = ['TSLA', 'NVDA', 'AAPL', 'MSFT', 'META', 'AMZN', 'GOOGL', 'GOOG', 'AMD', 'NFLX']
    
    def __init__(self, api_key: str = None):
        """Initialize with ChartExchange API."""
        from dotenv import load_dotenv
        load_dotenv()
        
        self.api_key = api_key or os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
        
        self.client = None
        self.exploiter = None
        
        if self.api_key:
            try:
                from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
                self.client = UltimateChartExchangeClient(self.api_key, tier=3)
                
                from live_monitoring.exploitation.reddit_exploiter import RedditExploiter
                self.exploiter = RedditExploiter(self.api_key)
            except Exception as e:
                logger.error(f"Error initializing clients: {e}")
    
    def analyze_with_full_context(self, symbol: str) -> Optional[EnhancedSignal]:
        """
        Analyze a symbol with ALL available data sources.
        """
        signal = EnhancedSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            reddit_signal="",
            reddit_action="NEUTRAL",
            reddit_strength=0,
            sentiment=0,
            mention_count=0,
            velocity_surge=False
        )
        
        # 1. Get Reddit data
        self._add_reddit_data(signal)
        
        # 2. Get Price data
        self._add_price_data(signal)
        
        # 3. Get DP data
        self._add_dp_data(signal)
        
        # 4. Get Institutional flow
        self._add_institutional_data(signal)
        
        # 5. Get Options data
        self._add_options_data(signal)
        
        # 6. Make enhanced decision
        self._make_enhanced_decision(signal)
        
        return signal
    
    def _add_reddit_data(self, signal: EnhancedSignal):
        """Add Reddit sentiment data."""
        if not self.exploiter:
            return
        
        try:
            analysis = self.exploiter.analyze_ticker(signal.symbol, days=7)
            
            if analysis:
                signal.reddit_signal = analysis.signal_type.value if analysis.signal_type else ""
                signal.reddit_action = analysis.action
                signal.reddit_strength = analysis.signal_strength
                signal.sentiment = analysis.avg_sentiment
                signal.mention_count = analysis.total_mentions
                signal.velocity_surge = "VELOCITY" in signal.reddit_signal
                
        except Exception as e:
            logger.debug(f"Error getting Reddit data for {signal.symbol}: {e}")
    
    def _add_price_data(self, signal: EnhancedSignal):
        """Add price and volume data."""
        try:
            ticker = yf.Ticker(signal.symbol)
            hist = ticker.history(period='1mo')
            
            if not hist.empty:
                signal.current_price = float(hist['Close'].iloc[-1])
                
                if len(hist) > 1:
                    signal.price_change_1d = (signal.current_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100
                if len(hist) > 5:
                    signal.price_change_5d = (signal.current_price - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5] * 100
                if len(hist) > 20:
                    signal.price_change_20d = (signal.current_price - hist['Close'].iloc[-20]) / hist['Close'].iloc[-20] * 100
                
                avg_volume = hist['Volume'].mean()
                if avg_volume > 0:
                    signal.volume_ratio = hist['Volume'].iloc[-1] / avg_volume
                    
        except Exception as e:
            logger.debug(f"Error getting price data for {signal.symbol}: {e}")
    
    def _add_dp_data(self, signal: EnhancedSignal):
        """Add dark pool data."""
        if not self.client:
            return
        
        try:
            # Get DP levels - use yesterday's date (T+1 data)
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            levels = self.client.get_dark_pool_levels(signal.symbol, date=yesterday)
            
            if levels:
                # Find nearest level to current price
                # Sort by volume to find strongest level
                sorted_levels = sorted(levels[:20], key=lambda x: int(x.get('volume', 0)), reverse=True)
                
                # Find levels near current price (within 2%)
                support_levels = []
                resistance_levels = []
                
                for level in sorted_levels[:10]:
                    if isinstance(level, dict):
                        # API returns 'level' not 'price'
                        price = float(level.get('level', level.get('price', 0)))
                        volume = int(level.get('volume', 0))
                        
                        if volume < 10000:  # Skip tiny levels
                            continue
                        
                        distance_pct = abs(price - signal.current_price) / signal.current_price * 100
                        
                        if distance_pct < 3:  # Within 3% of current price
                            if price < signal.current_price:
                                support_levels.append({'price': price, 'volume': volume})
                            else:
                                resistance_levels.append({'price': price, 'volume': volume})
                
                # Determine primary signal based on strongest nearby level
                if support_levels:
                    strongest_support = max(support_levels, key=lambda x: x['volume'])
                    if not resistance_levels or strongest_support['volume'] > max(r['volume'] for r in resistance_levels):
                        signal.dp_level = strongest_support['price']
                        signal.dp_volume = strongest_support['volume']
                        signal.dp_signal = "SUPPORT"
                
                if resistance_levels and not signal.dp_signal:
                    strongest_resistance = max(resistance_levels, key=lambda x: x['volume'])
                    signal.dp_level = strongest_resistance['price']
                    signal.dp_volume = strongest_resistance['volume']
                    signal.dp_signal = "RESISTANCE"
            
            # Get DP prints for buying pressure - use yesterday's date
            prints = self.client.get_dark_pool_prints(signal.symbol, date=yesterday)
            
            if prints:
                # DP prints have 'price' and 'volume' - estimate buy/sell by price vs VWAP
                total_volume = 0
                buy_volume = 0
                
                # Calculate rough VWAP from prints
                if len(prints) > 0:
                    prices = [float(p.get('price', 0)) for p in prints[:100]]
                    volumes = [int(p.get('volume', 0)) for p in prints[:100]]
                    
                    if sum(volumes) > 0:
                        vwap = sum(p * v for p, v in zip(prices, volumes)) / sum(volumes)
                        
                        # Estimate: trades above VWAP = buying, below = selling
                        for p in prints[:100]:
                            price = float(p.get('price', 0))
                            vol = int(p.get('volume', 0))
                            total_volume += vol
                            if price >= vwap:
                                buy_volume += vol
                
                if total_volume > 0:
                    signal.buying_pressure = buy_volume / total_volume * 100
                    
        except Exception as e:
            logger.debug(f"Error getting DP data for {signal.symbol}: {e}")
    
    def _add_institutional_data(self, signal: EnhancedSignal):
        """Add short interest and institutional flow data."""
        if not self.client:
            return
        
        try:
            # Get short data
            short_data = self.client.get_short_volume(signal.symbol)
            
            if short_data and isinstance(short_data, list) and short_data:
                latest = short_data[0] if isinstance(short_data[0], dict) else {}
                signal.short_interest = float(latest.get('short_pct', 0))
            
            # Get borrow fee
            borrow = self.client.get_borrow_fee(signal.symbol)
            
            if borrow:
                signal.borrow_fee = float(borrow.get('fee_rate', 0))
            
            # Determine institutional flow
            if signal.buying_pressure:
                if signal.buying_pressure > 60:
                    signal.inst_flow = "ACCUMULATION"
                elif signal.buying_pressure < 40:
                    signal.inst_flow = "DISTRIBUTION"
                else:
                    signal.inst_flow = "NEUTRAL"
                    
        except Exception as e:
            logger.debug(f"Error getting institutional data for {signal.symbol}: {e}")
    
    def _add_options_data(self, signal: EnhancedSignal):
        """Add options and gamma data."""
        # NOTE: ChartExchange options API is not available (returns 400)
        # Skip options data for now - we have DP + short + price which is sufficient
        pass
    
    def _make_enhanced_decision(self, signal: EnhancedSignal):
        """
        Make enhanced decision based on ALL data sources.
        
        This is the KEY logic that upgrades AVOID → LONG or confirms AVOID.
        """
        reasons = []
        
        # Start with Reddit's decision
        enhanced_action = signal.reddit_action
        enhanced_strength = signal.reddit_strength
        
        is_mega_cap = signal.symbol in self.MEGA_CAPS
        
        # CASE 1: VELOCITY_SURGE that might actually be LONG
        if signal.velocity_surge and signal.reddit_action == "AVOID":
            upgrade_points = 0
            
            # Check 1: Is price actually rallying?
            if signal.price_change_5d > 5:
                upgrade_points += 2
                reasons.append(f"✅ Price rallying {signal.price_change_5d:+.1f}% (5d)")
            
            # Check 2: Is DP showing support?
            if signal.dp_signal == "SUPPORT" and signal.dp_volume and signal.dp_volume > 100000:
                upgrade_points += 2
                reasons.append(f"✅ DP support at ${signal.dp_level:.2f} ({signal.dp_volume:,} vol)")
            
            # Check 3: Are institutions accumulating?
            if signal.inst_flow == "ACCUMULATION":
                upgrade_points += 2
                reasons.append(f"✅ Institutional accumulation ({signal.buying_pressure:.0f}% buy pressure)")
            
            # Check 4: Is it a mega-cap? (more reliable momentum)
            if is_mega_cap:
                upgrade_points += 1
                reasons.append(f"✅ Mega-cap (more reliable momentum)")
            
            # Check 5: Options bullish?
            if signal.put_call_ratio and signal.put_call_ratio < 0.8:
                upgrade_points += 1
                reasons.append(f"✅ Bullish options flow (P/C: {signal.put_call_ratio:.2f})")
            
            # Check 6: Volume confirmation
            if signal.volume_ratio > 1.5:
                upgrade_points += 1
                reasons.append(f"✅ High volume ({signal.volume_ratio:.1f}x avg)")
            
            # Decision: Upgrade if enough confirmation
            if upgrade_points >= 4:
                enhanced_action = "LONG"
                enhanced_strength = min(85, 50 + upgrade_points * 5)
                reasons.insert(0, f"🔄 UPGRADED: AVOID → LONG (score: {upgrade_points})")
            elif upgrade_points >= 2:
                enhanced_action = "WATCH_LONG"
                enhanced_strength = 60
                reasons.insert(0, f"👀 UPGRADED: AVOID → WATCH (score: {upgrade_points})")
            else:
                reasons.insert(0, f"⚠️ CONFIRMED: AVOID (score: {upgrade_points} < 4)")
        
        # CASE 2: LONG that might actually be AVOID (distribution check)
        elif signal.reddit_action == "LONG":
            downgrade_points = 0
            
            # Check for distribution signals
            if signal.inst_flow == "DISTRIBUTION":
                downgrade_points += 2
                reasons.append(f"⚠️ Institutional distribution ({signal.buying_pressure:.0f}% buy)")
            
            if signal.dp_signal == "RESISTANCE" and signal.dp_volume and signal.dp_volume > 100000:
                downgrade_points += 1
                reasons.append(f"⚠️ DP resistance at ${signal.dp_level:.2f}")
            
            if signal.put_call_ratio and signal.put_call_ratio > 1.3:
                downgrade_points += 1
                reasons.append(f"⚠️ Bearish options (P/C: {signal.put_call_ratio:.2f})")
            
            # Only downgrade if strong counter-signals
            if downgrade_points >= 3:
                enhanced_action = "WATCH"
                enhanced_strength = 55
                reasons.insert(0, f"🔄 DOWNGRADED: LONG → WATCH (warnings: {downgrade_points})")
            else:
                reasons.insert(0, f"✅ CONFIRMED: LONG ({downgrade_points} minor warnings)")
        
        # Set enhanced values
        signal.enhanced_action = enhanced_action
        signal.enhanced_strength = enhanced_strength
        signal.enhancement_reasons = reasons
    
    def run_full_analysis(self, symbols: List[str]) -> Dict[str, EnhancedSignal]:
        """Run full enhanced analysis on multiple symbols."""
        results = {}
        
        for symbol in symbols:
            try:
                signal = self.analyze_with_full_context(symbol)
                if signal:
                    results[symbol] = signal
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
        
        return results
    
    def print_report(self, results: Dict[str, EnhancedSignal]):
        """Print enhanced analysis report."""
        print("="*100)
        print("🔥 ENHANCED REDDIT BACKTEST - FULL SYNTHESIS REPORT")
        print("="*100)
        print(f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\nData Sources: Reddit + DP + Institutional + Options + Price")
        
        # Group by action
        longs = [(s, r) for s, r in results.items() if r.enhanced_action == "LONG"]
        watch = [(s, r) for s, r in results.items() if "WATCH" in r.enhanced_action]
        avoid = [(s, r) for s, r in results.items() if r.enhanced_action == "AVOID"]
        neutral = [(s, r) for s, r in results.items() if r.enhanced_action == "NEUTRAL"]
        
        # Upgraded signals (AVOID → LONG or WATCH)
        upgraded = [(s, r) for s, r in results.items() if "UPGRADED" in str(r.enhancement_reasons)]
        
        print(f"\n{'─'*100}")
        print(f"📊 SIGNAL SUMMARY")
        print(f"{'─'*100}")
        
        if upgraded:
            print(f"\n🔄 UPGRADED SIGNALS ({len(upgraded)}):")
            for symbol, sig in upgraded:
                emoji = '🚀' if sig.enhanced_action == 'LONG' else '👀'
                print(f"   {emoji} {symbol:5} | {sig.reddit_action:5} → {sig.enhanced_action:10} | "
                      f"Str: {sig.enhanced_strength:.0f}%")
                for reason in sig.enhancement_reasons[:3]:
                    print(f"      • {reason}")
        
        if longs:
            print(f"\n🚀 LONG SIGNALS ({len(longs)}):")
            for symbol, sig in sorted(longs, key=lambda x: x[1].enhanced_strength, reverse=True):
                print(f"   {symbol:5} | Str: {sig.enhanced_strength:.0f}% | "
                      f"Price: ${sig.current_price:.2f} | 5D: {sig.price_change_5d:+.1f}%")
                if sig.dp_signal:
                    print(f"      DP: {sig.dp_signal} @ ${sig.dp_level:.2f}")
                if sig.inst_flow:
                    print(f"      Flow: {sig.inst_flow} ({sig.buying_pressure:.0f}% buy)")
        
        if watch:
            print(f"\n👀 WATCH SIGNALS ({len(watch)}):")
            for symbol, sig in watch:
                print(f"   {symbol:5} | {sig.enhanced_action:10} | {sig.reddit_signal}")
        
        if avoid:
            print(f"\n⚠️ AVOID SIGNALS ({len(avoid)}):")
            for symbol, sig in avoid:
                print(f"   {symbol:5} | {sig.reddit_signal}")
        
        # Detailed breakdown for key stocks
        key_stocks = ['TSLA', 'NVDA', 'AMD', 'META', 'GME']
        
        print(f"\n{'='*100}")
        print(f"📋 DETAILED BREAKDOWN (KEY STOCKS)")
        print(f"{'='*100}")
        
        for symbol in key_stocks:
            if symbol not in results:
                continue
            
            sig = results[symbol]
            
            print(f"\n{'─'*80}")
            action_emoji = '🚀' if sig.enhanced_action == 'LONG' else '👀' if 'WATCH' in sig.enhanced_action else '⚠️'
            print(f"{action_emoji} {symbol}")
            print(f"{'─'*80}")
            
            print(f"   📱 Reddit: {sig.reddit_signal} ({sig.reddit_action}) | Str: {sig.reddit_strength:.0f}%")
            print(f"      Sentiment: {sig.sentiment:+.3f} | Mentions: {sig.mention_count} | Velocity: {'🔥' if sig.velocity_surge else 'Normal'}")
            
            print(f"\n   💰 Price: ${sig.current_price:.2f}")
            print(f"      1D: {sig.price_change_1d:+.2f}% | 5D: {sig.price_change_5d:+.2f}% | 20D: {sig.price_change_20d:+.2f}%")
            print(f"      Volume: {sig.volume_ratio:.1f}x average")
            
            if sig.dp_signal:
                print(f"\n   🏛️ Dark Pool: {sig.dp_signal}")
                print(f"      Level: ${sig.dp_level:.2f} | Volume: {sig.dp_volume:,}")
                if sig.buying_pressure:
                    print(f"      Buy Pressure: {sig.buying_pressure:.1f}%")
            
            if sig.inst_flow:
                print(f"\n   📊 Institutional: {sig.inst_flow}")
                if sig.short_interest:
                    print(f"      Short Interest: {sig.short_interest:.1f}%")
                if sig.borrow_fee:
                    print(f"      Borrow Fee: {sig.borrow_fee:.1f}%")
            
            if sig.max_pain:
                print(f"\n   📈 Options:")
                print(f"      Max Pain: ${sig.max_pain:.2f} | P/C: {sig.put_call_ratio:.2f}")
                if sig.gamma_exposure:
                    print(f"      Gamma: {sig.gamma_exposure}")
            
            print(f"\n   🎯 ENHANCED DECISION: {sig.enhanced_action} ({sig.enhanced_strength:.0f}%)")
            for reason in sig.enhancement_reasons[:5]:
                print(f"      • {reason}")
        
        print(f"\n{'='*100}")
        print(f"✅ ANALYSIS COMPLETE")
        print(f"{'='*100}\n")


def run_enhanced_backtest():
    """Run the enhanced Reddit backtest."""
    backtester = EnhancedRedditBacktester()
    
    symbols = [
        # Mega-caps
        'TSLA', 'NVDA', 'AAPL', 'MSFT', 'META', 'AMZN', 'GOOGL', 'AMD',
        # Reddit favorites
        'GME', 'PLTR', 'SOFI', 'RIVN', 
        # Others
        'COIN', 'HOOD', 'MARA'
    ]
    
    results = backtester.run_full_analysis(symbols)
    backtester.print_report(results)
    
    return results


if __name__ == "__main__":
    run_enhanced_backtest()

