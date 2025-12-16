"""
🔍 DIRECT API TEST
Bypasses deployment and tests APIs directly to see what signals would fire
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import os
import sys

# Add parent for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

@dataclass
class DirectSignal:
    """Signal generated from direct API test"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    volume: int
    direction: str
    confidence: float
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reasoning: str = ""

class DirectAPITester:
    """Tests APIs directly and generates signals"""
    
    def __init__(self):
        self.api_client = None
        self._init_api_client()
    
    def _init_api_client(self):
        """Initialize API client"""
        try:
            from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
            
            api_key = os.getenv('CHARTEXCHANGE_API_KEY')
            if not api_key:
                print("⚠️  CHARTEXCHANGE_API_KEY not set - using test mode")
                return None
            
            self.api_client = UltimateChartExchangeClient(api_key)
            print("✅ API client initialized")
        except Exception as e:
            print(f"⚠️  Failed to initialize API client: {e}")
            self.api_client = None
    
    def test_today(self, symbols: List[str] = ['SPY', 'QQQ']) -> List[DirectSignal]:
        """
        Test APIs for today and generate signals
        
        Returns:
            List of signals that would have been generated
        """
        if not self.api_client:
            print("❌ API client not available")
            return []
        
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        print(f"\n🔍 Testing APIs for {today}...")
        print("=" * 80)
        
        all_signals = []
        
        for symbol in symbols:
            print(f"\n{symbol}:")
            print("-" * 80)
            
            # Try today first, fallback to yesterday (T+1 delay)
            levels = None
            for date in [today, yesterday]:
                try:
                    levels = self.api_client.get_dark_pool_levels(symbol, date)
                    if levels:
                        print(f"  ✅ Found {len(levels)} DP levels for {date}")
                        break
                except Exception as e:
                    print(f"  ⚠️  Error fetching {date}: {e}")
                    continue
            
            if not levels:
                print(f"  ❌ No DP levels found")
                continue
            
            # Get current price
            try:
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1d', interval='1m')
                if hist.empty:
                    print(f"  ⚠️  No price data")
                    continue
                current_price = float(hist['Close'].iloc[-1])
                print(f"  📊 Current price: ${current_price:.2f}")
            except Exception as e:
                print(f"  ⚠️  Error fetching price: {e}")
                continue
            
            # Show top levels and distances
            sorted_levels = sorted(levels, key=lambda x: int(x.get('volume', 0)), reverse=True)
            print(f"  📊 Top 5 DP Levels:")
            for i, level in enumerate(sorted_levels[:5], 1):
                level_price = float(level.get('level', level.get('price', 0)))
                level_volume = int(level.get('volume', 0))
                distance_pct = abs(current_price - level_price) / current_price * 100
                print(f"    {i}. ${level_price:.2f} ({level_volume:,} shares) - {distance_pct:.2f}% away")
            
            # Generate signals from DP levels
            signals = self._generate_signals_from_levels(symbol, levels, current_price)
            all_signals.extend(signals)
            
            if signals:
                print(f"  🎯 Generated {len(signals)} signals:")
                for sig in signals[:5]:  # Show top 5
                    print(f"    • {sig.signal_type} @ ${sig.price:.2f} ({sig.volume:,} shares) - {sig.direction} ({sig.confidence:.0f}%)")
            else:
                print(f"  ⚠️  No signals generated")
                print(f"     → Price ${current_price:.2f} too far from DP levels")
                print(f"     → Try adjusting MAX_DISTANCE_PCT or check if using correct date")
        
        return all_signals
    
    def _generate_signals_from_levels(self, symbol: str, levels: List[Dict], 
                                      current_price: float) -> List[DirectSignal]:
        """Generate signals from DP levels"""
        signals = []
        
        # Sort by volume (convert to int for proper sorting)
        sorted_levels = sorted(levels, key=lambda x: int(x.get('volume', 0)), reverse=True)
        
        # Thresholds (from production system)
        MIN_BATTLEGROUND_VOLUME = 1_000_000  # 1M+ shares
        MIN_MAJOR_VOLUME = 500_000  # 500K+ shares
        MAX_DISTANCE_PCT = 1.0  # 1.0% away from level (relaxed for testing)
        
        for level in sorted_levels[:20]:  # Top 20 levels
            # API returns 'level' not 'price', and it's a string
            level_price = float(level.get('level', level.get('price', 0)))
            level_volume = int(level.get('volume', 0))
            level_type = level.get('level_type', 'RESISTANCE')  # Default if not specified
            
            if level_volume < MIN_MAJOR_VOLUME:
                continue
            
            # Calculate distance
            distance_pct = abs(current_price - level_price) / current_price * 100
            
            if distance_pct > MAX_DISTANCE_PCT:
                continue  # Too far away
            
            # Determine direction based on price vs level
            if current_price < level_price:
                direction = "LONG"  # Price below resistance = long opportunity
                signal_type = "BOUNCE" if level_type == 'RESISTANCE' else "BREAKOUT"
            else:
                direction = "SHORT"  # Price above support = short opportunity
                signal_type = "FADE" if level_type == 'SUPPORT' else "REVERSAL"
            
            # Calculate confidence
            confidence = self._calculate_confidence(level_volume, distance_pct, level_type)
            
            # Debug output for top levels
            if len([s for s in signals if s.symbol == symbol]) < 3:  # Show first 3 attempts per symbol
                print(f"      DEBUG: ${level_price:.2f} | Vol: {level_volume:,} | Dist: {distance_pct:.2f}% | Conf: {confidence:.0f}%")
            
            if confidence < 60:  # Minimum threshold
                continue
            
            # Calculate entry/stop/target
            entry, stop_loss, take_profit = self._calculate_trade_setup(
                current_price, level_price, direction
            )
            
            signal = DirectSignal(
                timestamp=datetime.now(),
                symbol=symbol,
                signal_type=signal_type,
                price=level_price,
                volume=level_volume,
                direction=direction,
                confidence=confidence,
                entry=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reasoning=f"{signal_type} at {level_type} ${level_price:.2f} ({level_volume:,} shares, {distance_pct:.2f}% away)"
            )
            
            signals.append(signal)
        
        return signals
    
    def _calculate_confidence(self, volume: int, distance_pct: float, level_type: str) -> float:
        """Calculate signal confidence"""
        confidence = 50  # Base
        
        # Volume component (0-30 points)
        if volume >= 5_000_000:
            confidence += 30
        elif volume >= 2_000_000:
            confidence += 25
        elif volume >= 1_000_000:
            confidence += 20
        elif volume >= 500_000:
            confidence += 10
        
        # Distance component (0-20 points)
        if distance_pct < 0.1:
            confidence += 20  # Very close
        elif distance_pct < 0.2:
            confidence += 15
        elif distance_pct < 0.3:
            confidence += 10
        elif distance_pct < 0.5:
            confidence += 5
        
        return min(confidence, 100.0)
    
    def _calculate_trade_setup(self, current_price: float, level_price: float, 
                               direction: str) -> tuple[float, float, float]:
        """Calculate entry, stop loss, take profit"""
        if direction == "LONG":
            entry = level_price  # Enter at level
            stop_loss = entry * 0.997  # 0.3% stop
            take_profit = entry * 1.006  # 0.6% target (2:1 R/R)
        else:  # SHORT
            entry = level_price
            stop_loss = entry * 1.003  # 0.3% stop
            take_profit = entry * 0.994  # 0.6% target (2:1 R/R)
        
        return entry, stop_loss, take_profit

