"""
📊 REGIME DETECTOR

Multi-factor market regime detection (UPTREND, DOWNTREND, CHOPPY, etc.)
"""

import logging
from datetime import datetime, time as dt_time
from typing import Dict

logger = logging.getLogger(__name__)


class RegimeDetector:
    """Detects market regime using multiple factors."""
    
    def detect(self, current_price: float, symbol: str = 'SPY') -> str:
        """
        🧠 SMART REGIME DETECTION
        
        Multi-factor regime detection that adapts to:
        - Intraday price movement (from open)
        - Recent momentum (last 30 min)
        - Volatility (ATR-based thresholds)
        - Time of day (morning chop vs afternoon trend)
        - Higher lows / Lower highs pattern
        
        Returns:
            str: "STRONG_UPTREND", "UPTREND", "STRONG_DOWNTREND", "DOWNTREND", or "CHOPPY"
        """
        try:
            import yfinance as yf
            
            # Get today's intraday data (5-min bars)
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='5m')
            
            if hist.empty or len(hist) < 6:
                return "CHOPPY"
            
            # 1. PRICE CHANGE FROM OPEN
            open_price = hist['Open'].iloc[0]
            change_from_open = ((current_price - open_price) / open_price) * 100
            
            # 2. RECENT MOMENTUM (Last 30 minutes = 6 bars)
            recent_bars = min(6, len(hist))
            recent_prices = hist['Close'].tail(recent_bars)
            recent_start = recent_prices.iloc[0]
            recent_end = recent_prices.iloc[-1]
            recent_momentum = ((recent_end - recent_start) / recent_start) * 100
            
            # 3. VOLATILITY-ADJUSTED THRESHOLDS
            ranges = (hist['High'] - hist['Low']).tail(12)
            avg_range = ranges.mean()
            avg_range_pct = (avg_range / current_price) * 100
            
            base_threshold = 0.15
            volatility_multiplier = max(1.0, avg_range_pct / 0.10)
            trend_threshold = base_threshold * volatility_multiplier
            strong_trend_threshold = trend_threshold * 2.5
            
            # 4. HIGHER HIGHS / LOWER LOWS PATTERN
            segment_size = len(hist) // 3
            if segment_size >= 2:
                seg1_high = hist['High'].iloc[:segment_size].max()
                seg2_high = hist['High'].iloc[segment_size:segment_size*2].max()
                seg3_high = hist['High'].iloc[segment_size*2:].max()
                
                seg1_low = hist['Low'].iloc[:segment_size].min()
                seg2_low = hist['Low'].iloc[segment_size:segment_size*2].min()
                seg3_low = hist['Low'].iloc[segment_size*2:].min()
                
                higher_highs = seg3_high > seg2_high > seg1_high
                higher_lows = seg3_low > seg2_low > seg1_low
                lower_highs = seg3_high < seg2_high < seg1_high
                lower_lows = seg3_low < seg2_low < seg1_low
                
                pattern_bullish = higher_highs or higher_lows
                pattern_bearish = lower_highs or lower_lows
            else:
                pattern_bullish = False
                pattern_bearish = False
            
            # 5. TIME OF DAY ADJUSTMENT
            now = datetime.now()
            current_time = now.time()
            
            is_morning_chop = dt_time(9, 30) <= current_time < dt_time(10, 0)
            is_power_hour = dt_time(15, 0) <= current_time < dt_time(16, 0)
            
            if is_morning_chop:
                trend_threshold *= 1.5
                strong_trend_threshold *= 1.5
            elif is_power_hour:
                trend_threshold *= 0.8
                strong_trend_threshold *= 0.8
            
            # 6. COMPOSITE REGIME DETERMINATION
            bullish_signals = 0
            bearish_signals = 0
            
            if change_from_open > strong_trend_threshold:
                bullish_signals += 2
            elif change_from_open > trend_threshold:
                bullish_signals += 1
            elif change_from_open < -strong_trend_threshold:
                bearish_signals += 2
            elif change_from_open < -trend_threshold:
                bearish_signals += 1
            
            if recent_momentum > trend_threshold * 0.5:
                bullish_signals += 1
            elif recent_momentum < -trend_threshold * 0.5:
                bearish_signals += 1
            
            if pattern_bullish:
                bullish_signals += 1
            if pattern_bearish:
                bearish_signals += 1
            
            session_avg = hist['Close'].mean()
            if current_price > session_avg * 1.002:
                bullish_signals += 1
            elif current_price < session_avg * 0.998:
                bearish_signals += 1
            
            # 7. FINAL REGIME CLASSIFICATION
            if bullish_signals >= 4:
                regime = "STRONG_UPTREND"
            elif bullish_signals >= 2 and bearish_signals < 2:
                regime = "UPTREND"
            elif bearish_signals >= 4:
                regime = "STRONG_DOWNTREND"
            elif bearish_signals >= 2 and bullish_signals < 2:
                regime = "DOWNTREND"
            else:
                regime = "CHOPPY"
            
            logger.debug(f"   📊 REGIME: {regime} (bullish: {bullish_signals}, bearish: {bearish_signals})")
            
            return regime
            
        except Exception as e:
            logger.warning(f"   ⚠️ Regime detection error: {e}")
            return "CHOPPY"
    
    def get_regime_details(self, current_price: float, symbol: str = 'SPY') -> Dict:
        """Get detailed regime information including signal counts."""
        # This would be called after detect() to get cached details
        # For now, return basic info
        regime = self.detect(current_price, symbol)
        return {
            'regime': regime,
            'symbol': symbol,
            'price': current_price
        }

