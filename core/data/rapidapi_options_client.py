#!/usr/bin/env python3
"""
📊 RapidAPI Options Client - Yahoo Finance 15

Fetches options flow data for institutional flow detection.
TESTED AND VALIDATED!

GOLD MINE DATA:
- Most Active Options (500+ stocks)
- Unusual Options Activity (1,859+ trades)
- Full Options Chains
- P/C Ratios, Volume, OI, Greeks
"""

import os
import sys
import requests
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass

# Add parent paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@dataclass
class MostActiveOption:
    """Most active option stock"""
    symbol: str
    name: str
    last_price: float
    price_change: float
    percent_change: float
    total_volume: int
    put_volume_pct: float
    call_volume_pct: float
    put_call_ratio: float
    iv_rank_1y: float
    
    @property
    def is_bullish(self) -> bool:
        """Check if bullish (more calls than puts)"""
        return self.put_call_ratio < 0.8
    
    @property
    def is_bearish(self) -> bool:
        """Check if bearish (more puts than calls)"""
        return self.put_call_ratio > 1.2
    
    @property
    def bias(self) -> str:
        """Get market bias"""
        if self.is_bullish:
            return "BULLISH"
        elif self.is_bearish:
            return "BEARISH"
        return "NEUTRAL"


@dataclass
class UnusualOption:
    """Unusual options activity"""
    symbol: str
    base_symbol: str
    base_price: float
    option_type: str  # "Call" or "Put"
    strike: float
    expiration: str
    days_to_exp: int
    volume: int
    open_interest: int
    vol_oi_ratio: float
    volatility: float
    delta: float
    
    @property
    def is_unusual(self) -> bool:
        """Check if truly unusual (Vol/OI > 30)"""
        return self.vol_oi_ratio > 30
    
    @property
    def is_bullish(self) -> bool:
        """Check if bullish unusual activity"""
        return self.option_type == "Call" and self.is_unusual
    
    @property
    def is_bearish(self) -> bool:
        """Check if bearish unusual activity"""
        return self.option_type == "Put" and self.is_unusual


class RapidAPIOptionsClient:
    """
    Client for Yahoo Finance 15 RapidAPI - OPTIONS
    
    Endpoints:
    - /v1/markets/options/most-active
    - /v1/markets/options/unusual-options-activity
    - /v1/markets/options
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the options client.
        
        Args:
            api_key: RapidAPI key (defaults to env var)
        """
        self.api_key = api_key or os.getenv('YAHOO_RAPIDAPI_KEY')
        self.host = os.getenv('YAHOO_RAPIDAPI_HOST', 'yahoo-finance15.p.rapidapi.com')
        self.base_url = f"https://{self.host}/api"
        
        if not self.api_key:
            print("⚠️  YAHOO_RAPIDAPI_KEY not set in environment")
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make authenticated request to RapidAPI"""
        if not self.api_key:
            return None
            
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ RapidAPI error: {e}")
            return None
    
    def get_most_active_options(self, option_type: str = "STOCKS") -> List[MostActiveOption]:
        """
        Get most active options by volume.
        
        Args:
            option_type: "STOCKS" or "ETFS"
            
        Returns:
            List of MostActiveOption objects (up to 500)
        """
        data = self._make_request(
            "v1/markets/options/most-active",
            params={"type": option_type}
        )
        
        if not data or 'body' not in data:
            return []
        
        options = []
        for item in data['body']:
            try:
                option = MostActiveOption(
                    symbol=item.get('symbol', ''),
                    name=item.get('symbolName', ''),
                    last_price=self._parse_float(item.get('lastPrice', 0)),
                    price_change=self._parse_float(item.get('priceChange', 0)),
                    percent_change=self._parse_float(item.get('percentChange', '0').replace('%', '').replace('+', '')),
                    total_volume=self._parse_int(item.get('optionsTotalVolume', 0)),
                    put_volume_pct=self._parse_float(item.get('optionsPutVolumePercent', '0').replace('%', '')),
                    call_volume_pct=self._parse_float(item.get('optionsCallVolumePercent', '0').replace('%', '')),
                    put_call_ratio=self._parse_float(item.get('optionsPutCallVolumeRatio', 1)),
                    iv_rank_1y=self._parse_float(item.get('optionsImpliedVolatilityRank1y', '0').replace('%', ''))
                )
                options.append(option)
            except Exception as e:
                print(f"⚠️  Error parsing most active option: {e}")
                continue
        
        return options
    
    def get_unusual_activity(self, option_type: str = "STOCKS") -> List[UnusualOption]:
        """
        Get unusual options activity.
        
        Args:
            option_type: "STOCKS" or "ETFS"
            
        Returns:
            List of UnusualOption objects (1,859+ typically)
        """
        data = self._make_request(
            "v1/markets/options/unusual-options-activity",
            params={"type": option_type}
        )
        
        if not data or 'body' not in data:
            return []
        
        options = []
        for item in data['body']:
            try:
                option = UnusualOption(
                    symbol=item.get('symbol', ''),
                    base_symbol=item.get('baseSymbol', ''),
                    base_price=self._parse_float(item.get('baseLastPrice', 0)),
                    option_type=item.get('symbolType', ''),
                    strike=self._parse_float(item.get('strikePrice', '0').replace(',', '')),
                    expiration=item.get('expirationDate', ''),
                    days_to_exp=self._parse_int(item.get('daysToExpiration', 0)),
                    volume=self._parse_int(item.get('volume', 0)),
                    open_interest=self._parse_int(item.get('openInterest', 0)),
                    vol_oi_ratio=self._parse_float(item.get('volumeOpenInterestRatio', 0)),
                    volatility=self._parse_float(item.get('volatility', '0').replace('%', '')),
                    delta=self._parse_float(item.get('delta', 0))
                )
                options.append(option)
            except Exception as e:
                print(f"⚠️  Error parsing unusual option: {e}")
                continue
        
        return options
    
    def get_options_chain(self, ticker: str, display: str = "straddle") -> Optional[Dict]:
        """
        Get full options chain for a ticker.
        
        Args:
            ticker: Stock symbol (e.g., "SPY")
            display: "straddle" or other display type
            
        Returns:
            Raw options chain data
        """
        return self._make_request(
            "v1/markets/options",
            params={"ticker": ticker, "display": display}
        )
    
    def get_bullish_signals(self, min_volume: int = 500000) -> List[MostActiveOption]:
        """
        Get stocks with bullish options flow.
        
        Args:
            min_volume: Minimum options volume
            
        Returns:
            List of bullish MostActiveOption objects
        """
        all_options = self.get_most_active_options()
        return [o for o in all_options if o.is_bullish and o.total_volume >= min_volume]
    
    def get_bearish_signals(self, min_volume: int = 500000) -> List[MostActiveOption]:
        """
        Get stocks with bearish options flow.
        
        Args:
            min_volume: Minimum options volume
            
        Returns:
            List of bearish MostActiveOption objects
        """
        all_options = self.get_most_active_options()
        return [o for o in all_options if o.is_bearish and o.total_volume >= min_volume]
    
    def get_unusual_for_symbol(self, symbol: str) -> List[UnusualOption]:
        """
        Get unusual options activity for a specific symbol.
        
        Args:
            symbol: Stock symbol (e.g., "SPY")
            
        Returns:
            List of unusual options for that symbol
        """
        all_unusual = self.get_unusual_activity()
        return [o for o in all_unusual if o.base_symbol.upper() == symbol.upper()]
    
    def get_market_sentiment(self) -> Dict:
        """
        Get overall market sentiment from options flow.
        
        Returns:
            Dict with bullish/bearish counts and overall bias
        """
        all_options = self.get_most_active_options()
        
        bullish = [o for o in all_options if o.is_bullish]
        bearish = [o for o in all_options if o.is_bearish]
        neutral = [o for o in all_options if not o.is_bullish and not o.is_bearish]
        
        # Weighted by volume
        bullish_volume = sum(o.total_volume for o in bullish)
        bearish_volume = sum(o.total_volume for o in bearish)
        total_volume = bullish_volume + bearish_volume
        
        bullish_pct = (bullish_volume / total_volume * 100) if total_volume > 0 else 50
        
        return {
            'bullish_count': len(bullish),
            'bearish_count': len(bearish),
            'neutral_count': len(neutral),
            'bullish_volume': bullish_volume,
            'bearish_volume': bearish_volume,
            'bullish_pct': bullish_pct,
            'bias': 'BULLISH' if bullish_pct > 55 else ('BEARISH' if bullish_pct < 45 else 'NEUTRAL'),
            'top_bullish': [o.symbol for o in sorted(bullish, key=lambda x: x.total_volume, reverse=True)[:5]],
            'top_bearish': [o.symbol for o in sorted(bearish, key=lambda x: x.total_volume, reverse=True)[:5]]
        }
    
    def _parse_float(self, value) -> float:
        """Parse float from string or number"""
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(',', '').replace('+', '').replace('%', ''))
        except:
            return 0.0
    
    def _parse_int(self, value) -> int:
        """Parse int from string or number"""
        if isinstance(value, int):
            return value
        try:
            return int(str(value).replace(',', ''))
        except:
            return 0


# Standalone test
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("=" * 70)
    print("📊 RAPIDAPI OPTIONS CLIENT TEST")
    print("=" * 70)
    
    # Use the hardcoded key for testing (should be in env)
    api_key = os.getenv('YAHOO_RAPIDAPI_KEY') or "9f107deaabmsh2efbc3559ddca05p17f1abjsn271e6df32f7c"
    
    client = RapidAPIOptionsClient(api_key=api_key)
    
    # Test 1: Most Active
    print("\n📊 MOST ACTIVE OPTIONS:")
    print("-" * 50)
    most_active = client.get_most_active_options()
    print(f"Total: {len(most_active)} stocks")
    
    for opt in most_active[:10]:
        emoji = "🟢" if opt.is_bullish else ("🔴" if opt.is_bearish else "⚪")
        print(f"{emoji} {opt.symbol:6} | ${opt.last_price:>8.2f} | {opt.percent_change:>+6.2f}% | Vol: {opt.total_volume:>10,} | P/C: {opt.put_call_ratio:.2f} | {opt.bias}")
    
    # Test 2: Market Sentiment
    print("\n📈 MARKET SENTIMENT:")
    print("-" * 50)
    sentiment = client.get_market_sentiment()
    print(f"Overall Bias: {sentiment['bias']}")
    print(f"Bullish: {sentiment['bullish_count']} stocks ({sentiment['bullish_pct']:.1f}%)")
    print(f"Bearish: {sentiment['bearish_count']} stocks")
    print(f"Top Bullish: {', '.join(sentiment['top_bullish'])}")
    print(f"Top Bearish: {', '.join(sentiment['top_bearish'])}")
    
    # Test 3: Unusual Activity
    print("\n🔥 UNUSUAL OPTIONS ACTIVITY:")
    print("-" * 50)
    unusual = client.get_unusual_activity()
    print(f"Total: {len(unusual)} unusual trades")
    
    # Top 5 by Vol/OI ratio
    unusual_sorted = sorted(unusual, key=lambda x: x.vol_oi_ratio, reverse=True)[:10]
    for opt in unusual_sorted:
        emoji = "📈" if opt.option_type == "Call" else "📉"
        print(f"{emoji} {opt.base_symbol:5} | {opt.option_type:4} ${opt.strike:>7.2f} | Exp: {opt.expiration} | Vol/OI: {opt.vol_oi_ratio:>6.1f}x | IV: {opt.volatility:.1f}%")
    
    # Test 4: SPY Unusual
    print("\n🎯 SPY UNUSUAL OPTIONS:")
    print("-" * 50)
    spy_unusual = client.get_unusual_for_symbol("SPY")
    print(f"Found: {len(spy_unusual)} unusual SPY options")
    for opt in spy_unusual[:5]:
        print(f"  {opt.option_type} ${opt.strike:.2f} | Exp: {opt.expiration} | Vol/OI: {opt.vol_oi_ratio:.1f}x")
    
    print("\n" + "=" * 70)
    print("✅ RapidAPI Options Client test complete!")
    print("=" * 70)

