import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

class MarketDataProvider:
    """
    Centralized provider for historical market data.
    Ensures that backtests only see data that was available ON THAT SPECIFIC DATE.
    Fixes the stale VIX bug from the legacy backtester.
    """
    
    def __init__(self):
        self.cache = {}

    def get_historical_bars(self, symbol: str, date_str: str, interval: str = "1m") -> pd.DataFrame:
        """
        Fetch intraday OHLCV bars for a specific date.
        """
        cache_key = f"{symbol}_{date_str}_{interval}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            today = datetime.now()
            days_ago = (today - date_obj).days
            
            ticker = yf.Ticker(symbol)
            
            # yfinance limits 1m data to the last 7 days
            if interval == "1m":
                if days_ago <= 7:
                    data = ticker.history(period=f"{days_ago + 2}d", interval="1m")
                else:
                    print(f"⚠️ {symbol} 1m data unavailable for {date_str} (yfinance 7-day limit). Falling back to 2m or 5m.")
                    # Fallback to 2m (60 days) or 5m
                    data = ticker.history(start=date_str, end=(date_obj + timedelta(days=1)).strftime('%Y-%m-%d'), interval="5m")
            else:
                data = ticker.history(start=date_str, end=(date_obj + timedelta(days=1)).strftime('%Y-%m-%d'), interval=interval)
            
            if data.empty:
                self.cache[cache_key] = pd.DataFrame()
                return pd.DataFrame()
                
            # Convert index to UTC then to US/Eastern timezone to match NY market hours precisely
            if data.index.tz is None:
               data.index = data.index.tz_localize('UTC').tz_convert('US/Eastern')
            else:
               data.index = data.index.tz_convert('US/Eastern')

            # Filter exactly to the requested date in local time
            filtered_data = data[data.index.strftime('%Y-%m-%d') == date_str]
            self.cache[cache_key] = filtered_data
            return filtered_data
            
        except Exception as e:
            print(f"❌ Error fetching {symbol} bars for {date_str}: {e}")
            self.cache[cache_key] = pd.DataFrame()
            return pd.DataFrame()

    def get_historical_vix(self, date_str: str) -> float:
        """
        Fetch the exact VIX close limit for a specific historical date.
        Fixes the legacy bug where the current live VIX was being injected into past backtests.
        """
        cache_key = f"VIX_{date_str}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            # Fetch D-1 to D+1 to guarantee we get the print for the requested day
            start = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
            end = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
            
            ticker = yf.Ticker("^VIX")
            data = ticker.history(start=start, end=end, interval="1d")
            
            if data.empty:
                return 20.0 # safe fallback
                
            # Try to get exact date match, otherwise closest previous
            date_data = data[data.index.strftime('%Y-%m-%d') <= date_str]
            if not date_data.empty:
                vix_val = float(date_data['Close'].iloc[-1])
                self.cache[cache_key] = vix_val
                return vix_val
                
            return 20.0
            
        except Exception as e:
            print(f"❌ Error fetching VIX for {date_str}: {e}")
            return 20.0
            
    def get_market_context(self, date_str: str) -> Dict[str, Any]:
        """Provides a cohesive snapshot of the market for a given day."""
        vix = self.get_historical_vix(date_str)
        
        # Simple trend proxy using SPY 1d
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            start = (date_obj - timedelta(days=5)).strftime('%Y-%m-%d')
            end = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
            spy = yf.Ticker("SPY").history(start=start, end=end, interval="1d")
            
            direction = "UNKNOWN"
            if not spy.empty and len(spy) >= 2:
                closes = spy['Close'].values
                direction = "UP" if closes[-1] > closes[-2] else "DOWN"
        except:
            direction = "UNKNOWN"
            
        return {
            "vix": vix,
            "direction": direction,
            "date": date_str
        }
