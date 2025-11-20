#!/usr/bin/env python3
"""
TECHNICAL STRATEGY - Pure price action & indicators
====================================================
Generate signals based on:
- RSI (overbought/oversold)
- MACD (momentum)
- Bollinger Bands (volatility)
- Support/Resistance (pivot points)
- Volume confirmation

Author: Alpha's AI Hedge Fund
Date: 2024-10-18
"""

import yfinance as yf
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class TechnicalContext:
    """Technical analysis context for a symbol"""
    symbol: str
    timestamp: datetime
    
    # Current price
    current_price: float
    
    # Indicators
    rsi: float
    macd_line: float
    signal_line: float
    macd_histogram: float
    
    # Bollinger Bands
    bb_upper: float
    bb_middle: float
    bb_lower: float
    bb_width: float  # Volatility measure
    
    # Moving Averages
    sma_20: float
    sma_50: float
    sma_200: Optional[float]
    
    # Support/Resistance
    resistance_1: float
    resistance_2: float
    pivot: float
    support_1: float
    support_2: float
    
    # Volume
    current_volume: float
    avg_volume: float
    volume_ratio: float
    
    # Trend
    trend: str  # BULLISH, BEARISH, NEUTRAL
    
    def __repr__(self):
        return (f"TechnicalContext(symbol={self.symbol}, price=${self.current_price:.2f}, "
                f"RSI={self.rsi:.1f}, MACD={self.macd_histogram:.2f}, "
                f"Trend={self.trend}, VolumeRatio={self.volume_ratio:.2f}x)")


@dataclass
class TechnicalSignal:
    """Technical trading signal"""
    timestamp: datetime
    symbol: str
    action: str  # BUY or SELL
    signal_type: str  # RSI_OVERSOLD, MACD_BULLISH, BB_SQUEEZE, BREAKOUT, BOUNCE
    
    # Prices
    current_price: float
    entry_price: float
    stop_loss: float
    take_profit: float
    
    # Metrics
    confidence: float  # 0-100
    risk_reward_ratio: float
    
    # Technical context
    rsi: float
    macd_histogram: float
    trend: str
    volume_ratio: float
    
    # Reasoning
    primary_reason: str
    supporting_factors: List[str]
    
    def __repr__(self):
        return (f"TechnicalSignal({self.signal_type}, {self.action} @ ${self.entry_price:.2f}, "
                f"Confidence={self.confidence:.0f}%, R/R={self.risk_reward_ratio:.1f})")


class TechnicalStrategyEngine:
    """
    Generate trading signals from technical analysis
    """
    
    def __init__(self, min_confidence: float = 0.60):
        self.min_confidence = min_confidence
        logger.info("📈 Technical Strategy Engine initialized")
        logger.info(f"   Min confidence: {min_confidence:.0%}")
    
    def fetch_technical_context(self, symbol: str) -> Optional[TechnicalContext]:
        """
        Fetch all technical data and calculate indicators
        
        Returns:
            TechnicalContext object or None if error
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Get historical data (3 months for indicators)
            df = ticker.history(period='3mo', interval='1d')
            
            if df.empty or len(df) < 50:
                logger.warning(f"Insufficient data for {symbol}")
                return None
            
            close = df['Close']
            high = df['High']
            low = df['Low']
            volume = df['Volume']
            
            # Calculate RSI
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            
            # Calculate MACD
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_histogram = macd_line - signal_line
            
            # Calculate Bollinger Bands
            sma20 = close.rolling(window=20).mean()
            std20 = close.rolling(window=20).std()
            bb_upper = sma20 + (std20 * 2)
            bb_lower = sma20 - (std20 * 2)
            bb_width = (bb_upper - bb_lower) / sma20  # Normalized width
            
            # Calculate other MAs
            sma50 = close.rolling(window=50).mean()
            sma200 = close.rolling(window=200).mean() if len(close) >= 200 else None
            
            # Calculate Pivot Points (from 30-day high/low)
            df_30d = df.tail(30)
            high_30d = df_30d['High'].max()
            low_30d = df_30d['Low'].min()
            current_price = close.iloc[-1]
            
            pivot = (high_30d + low_30d + current_price) / 3
            r1 = 2 * pivot - low_30d
            r2 = pivot + (high_30d - low_30d)
            s1 = 2 * pivot - high_30d
            s2 = pivot - (high_30d - low_30d)
            
            # Volume analysis
            avg_volume = volume.mean()
            current_volume = volume.iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Determine trend
            if current_price > sma50.iloc[-1] and (sma200 is None or current_price > sma200.iloc[-1]):
                trend = "BULLISH"
            elif current_price < sma50.iloc[-1] and (sma200 is None or current_price < sma200.iloc[-1]):
                trend = "BEARISH"
            else:
                trend = "NEUTRAL"
            
            context = TechnicalContext(
                symbol=symbol,
                timestamp=datetime.now(),
                current_price=current_price,
                rsi=current_rsi,
                macd_line=macd_line.iloc[-1],
                signal_line=signal_line.iloc[-1],
                macd_histogram=macd_histogram.iloc[-1],
                bb_upper=bb_upper.iloc[-1],
                bb_middle=sma20.iloc[-1],
                bb_lower=bb_lower.iloc[-1],
                bb_width=bb_width.iloc[-1],
                sma_20=sma20.iloc[-1],
                sma_50=sma50.iloc[-1],
                sma_200=sma200.iloc[-1] if sma200 is not None else None,
                resistance_1=r1,
                resistance_2=r2,
                pivot=pivot,
                support_1=s1,
                support_2=s2,
                current_volume=current_volume,
                avg_volume=avg_volume,
                volume_ratio=volume_ratio,
                trend=trend
            )
            
            logger.debug(f"Fetched technical context: {context}")
            return context
            
        except Exception as e:
            logger.error(f"Error fetching technical context for {symbol}: {e}")
            return None
    
    def generate_signals(self, symbol: str) -> List[TechnicalSignal]:
        """
        Generate technical trading signals
        
        Returns:
            List of TechnicalSignal objects
        """
        signals = []
        
        # Fetch technical context
        ctx = self.fetch_technical_context(symbol)
        if not ctx:
            return signals
        
        # Check for various signal types
        
        # 1. RSI Oversold/Overbought
        if ctx.rsi < 30 and ctx.trend != "BEARISH":
            signal = self._create_rsi_oversold_signal(ctx)
            if signal:
                signals.append(signal)
        elif ctx.rsi > 70 and ctx.trend != "BULLISH":
            signal = self._create_rsi_overbought_signal(ctx)
            if signal:
                signals.append(signal)
        
        # 2. MACD Crossover
        if ctx.macd_histogram > 0 and abs(ctx.macd_histogram) > 0.5 and ctx.trend == "BULLISH":
            signal = self._create_macd_bullish_signal(ctx)
            if signal:
                signals.append(signal)
        elif ctx.macd_histogram < 0 and abs(ctx.macd_histogram) > 0.5 and ctx.trend == "BEARISH":
            signal = self._create_macd_bearish_signal(ctx)
            if signal:
                signals.append(signal)
        
        # 3. Bollinger Band Squeeze/Breakout
        if ctx.bb_width < 0.03 and ctx.volume_ratio > 1.3:  # Low volatility + volume spike
            signal = self._create_bb_squeeze_signal(ctx)
            if signal:
                signals.append(signal)
        
        # 4. Support Bounce
        distance_to_s1 = abs(ctx.current_price - ctx.support_1) / ctx.current_price
        if distance_to_s1 < 0.005 and ctx.volume_ratio > 1.5 and ctx.rsi < 45:
            signal = self._create_support_bounce_signal(ctx)
            if signal:
                signals.append(signal)
        
        # 5. Resistance Breakout
        distance_to_r1 = (ctx.current_price - ctx.resistance_1) / ctx.resistance_1
        if 0 < distance_to_r1 < 0.01 and ctx.volume_ratio > 1.8 and ctx.rsi > 55:
            signal = self._create_breakout_signal(ctx)
            if signal:
                signals.append(signal)
        
        # Filter by minimum confidence
        signals = [s for s in signals if s.confidence >= self.min_confidence * 100]
        
        logger.info(f"Generated {len(signals)} technical signals for {symbol}")
        for sig in signals:
            logger.debug(f"  {sig}")
        
        return signals
    
    def _create_rsi_oversold_signal(self, ctx: TechnicalContext) -> Optional[TechnicalSignal]:
        """RSI < 30 with potential reversal"""
        entry = ctx.current_price
        stop = entry * 0.98  # 2% stop
        target = entry * 1.04  # 4% target (2:1 R/R)
        rr = (target - entry) / (entry - stop)
        
        # Confidence based on RSI depth and volume
        confidence = 60
        if ctx.rsi < 25:
            confidence += 10
        if ctx.volume_ratio > 1.5:
            confidence += 10
        if ctx.trend == "BULLISH":
            confidence += 5
        
        supporting = []
        if ctx.volume_ratio > 1.5:
            supporting.append(f"Volume spike ({ctx.volume_ratio:.1f}x)")
        if ctx.current_price < ctx.bb_lower:
            supporting.append("Below lower BB")
        if ctx.trend == "BULLISH":
            supporting.append("Bullish trend")
        
        return TechnicalSignal(
            timestamp=ctx.timestamp,
            symbol=ctx.symbol,
            action="BUY",
            signal_type="RSI_OVERSOLD",
            current_price=ctx.current_price,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=min(confidence, 95),
            risk_reward_ratio=rr,
            rsi=ctx.rsi,
            macd_histogram=ctx.macd_histogram,
            trend=ctx.trend,
            volume_ratio=ctx.volume_ratio,
            primary_reason=f"RSI oversold at {ctx.rsi:.1f}",
            supporting_factors=supporting
        )
    
    def _create_rsi_overbought_signal(self, ctx: TechnicalContext) -> Optional[TechnicalSignal]:
        """RSI > 70 with potential reversal"""
        entry = ctx.current_price
        stop = entry * 1.02  # 2% stop
        target = entry * 0.96  # 4% target (2:1 R/R)
        rr = (entry - target) / (stop - entry)
        
        confidence = 60
        if ctx.rsi > 75:
            confidence += 10
        if ctx.volume_ratio > 1.5:
            confidence += 10
        if ctx.trend == "BEARISH":
            confidence += 5
        
        supporting = []
        if ctx.volume_ratio > 1.5:
            supporting.append(f"Volume spike ({ctx.volume_ratio:.1f}x)")
        if ctx.current_price > ctx.bb_upper:
            supporting.append("Above upper BB")
        if ctx.trend == "BEARISH":
            supporting.append("Bearish trend")
        
        return TechnicalSignal(
            timestamp=ctx.timestamp,
            symbol=ctx.symbol,
            action="SELL",
            signal_type="RSI_OVERBOUGHT",
            current_price=ctx.current_price,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=min(confidence, 95),
            risk_reward_ratio=rr,
            rsi=ctx.rsi,
            macd_histogram=ctx.macd_histogram,
            trend=ctx.trend,
            volume_ratio=ctx.volume_ratio,
            primary_reason=f"RSI overbought at {ctx.rsi:.1f}",
            supporting_factors=supporting
        )
    
    def _create_macd_bullish_signal(self, ctx: TechnicalContext) -> Optional[TechnicalSignal]:
        """MACD bullish crossover with trend confirmation"""
        entry = ctx.current_price
        stop = entry * 0.98
        target = entry * 1.06  # 3:1 R/R
        rr = (target - entry) / (entry - stop)
        
        confidence = 65
        if abs(ctx.macd_histogram) > 1.0:
            confidence += 10
        if ctx.volume_ratio > 1.3:
            confidence += 10
        if ctx.current_price > ctx.sma_20:
            confidence += 5
        
        supporting = []
        if abs(ctx.macd_histogram) > 1.0:
            supporting.append(f"Strong MACD ({ctx.macd_histogram:.2f})")
        if ctx.volume_ratio > 1.3:
            supporting.append(f"Volume confirmation ({ctx.volume_ratio:.1f}x)")
        if ctx.rsi > 50:
            supporting.append(f"RSI bullish ({ctx.rsi:.1f})")
        
        return TechnicalSignal(
            timestamp=ctx.timestamp,
            symbol=ctx.symbol,
            action="BUY",
            signal_type="MACD_BULLISH",
            current_price=ctx.current_price,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=min(confidence, 95),
            risk_reward_ratio=rr,
            rsi=ctx.rsi,
            macd_histogram=ctx.macd_histogram,
            trend=ctx.trend,
            volume_ratio=ctx.volume_ratio,
            primary_reason="MACD bullish crossover",
            supporting_factors=supporting
        )
    
    def _create_macd_bearish_signal(self, ctx: TechnicalContext) -> Optional[TechnicalSignal]:
        """MACD bearish crossover"""
        entry = ctx.current_price
        stop = entry * 1.02
        target = entry * 0.94  # 3:1 R/R
        rr = (entry - target) / (stop - entry)
        
        confidence = 65
        if abs(ctx.macd_histogram) > 1.0:
            confidence += 10
        if ctx.volume_ratio > 1.3:
            confidence += 10
        if ctx.current_price < ctx.sma_20:
            confidence += 5
        
        supporting = []
        if abs(ctx.macd_histogram) > 1.0:
            supporting.append(f"Strong MACD ({ctx.macd_histogram:.2f})")
        if ctx.volume_ratio > 1.3:
            supporting.append(f"Volume confirmation ({ctx.volume_ratio:.1f}x)")
        if ctx.rsi < 50:
            supporting.append(f"RSI bearish ({ctx.rsi:.1f})")
        
        return TechnicalSignal(
            timestamp=ctx.timestamp,
            symbol=ctx.symbol,
            action="SELL",
            signal_type="MACD_BEARISH",
            current_price=ctx.current_price,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=min(confidence, 95),
            risk_reward_ratio=rr,
            rsi=ctx.rsi,
            macd_histogram=ctx.macd_histogram,
            trend=ctx.trend,
            volume_ratio=ctx.volume_ratio,
            primary_reason="MACD bearish crossover",
            supporting_factors=supporting
        )
    
    def _create_bb_squeeze_signal(self, ctx: TechnicalContext) -> Optional[TechnicalSignal]:
        """Bollinger Band squeeze with breakout potential"""
        # Direction determined by position relative to BB middle and trend
        direction = "BUY" if ctx.current_price > ctx.bb_middle and ctx.trend != "BEARISH" else "SELL"
        
        entry = ctx.current_price
        if direction == "BUY":
            stop = ctx.bb_lower
            target = ctx.bb_upper
        else:
            stop = ctx.bb_upper
            target = ctx.bb_lower
        
        rr = abs(target - entry) / abs(entry - stop) if abs(entry - stop) > 0 else 1.0
        
        confidence = 70
        if ctx.volume_ratio > 1.5:
            confidence += 10
        if abs(ctx.macd_histogram) > 0.5:
            confidence += 5
        
        supporting = []
        supporting.append(f"BB width {ctx.bb_width:.4f} (squeeze)")
        supporting.append(f"Volume spike ({ctx.volume_ratio:.1f}x)")
        if ctx.trend != "NEUTRAL":
            supporting.append(f"{ctx.trend.capitalize()} trend")
        
        return TechnicalSignal(
            timestamp=ctx.timestamp,
            symbol=ctx.symbol,
            action=direction,
            signal_type="BB_SQUEEZE",
            current_price=ctx.current_price,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=min(confidence, 95),
            risk_reward_ratio=rr,
            rsi=ctx.rsi,
            macd_histogram=ctx.macd_histogram,
            trend=ctx.trend,
            volume_ratio=ctx.volume_ratio,
            primary_reason="Bollinger Band squeeze breakout",
            supporting_factors=supporting
        )
    
    def _create_support_bounce_signal(self, ctx: TechnicalContext) -> Optional[TechnicalSignal]:
        """Bounce off support level"""
        entry = ctx.support_1
        stop = ctx.support_2
        target = ctx.resistance_1
        rr = (target - entry) / (entry - stop) if (entry - stop) > 0 else 1.0
        
        confidence = 70
        if ctx.volume_ratio > 2.0:
            confidence += 10
        if ctx.rsi < 35:
            confidence += 5
        if ctx.trend == "BULLISH":
            confidence += 5
        
        supporting = []
        supporting.append(f"At support ${ctx.support_1:.2f}")
        supporting.append(f"Volume spike ({ctx.volume_ratio:.1f}x)")
        if ctx.rsi < 35:
            supporting.append(f"RSI oversold ({ctx.rsi:.1f})")
        
        return TechnicalSignal(
            timestamp=ctx.timestamp,
            symbol=ctx.symbol,
            action="BUY",
            signal_type="SUPPORT_BOUNCE",
            current_price=ctx.current_price,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=min(confidence, 95),
            risk_reward_ratio=rr,
            rsi=ctx.rsi,
            macd_histogram=ctx.macd_histogram,
            trend=ctx.trend,
            volume_ratio=ctx.volume_ratio,
            primary_reason=f"Bounce off support ${ctx.support_1:.2f}",
            supporting_factors=supporting
        )
    
    def _create_breakout_signal(self, ctx: TechnicalContext) -> Optional[TechnicalSignal]:
        """Breakout above resistance"""
        entry = ctx.resistance_1
        stop = ctx.pivot
        target = ctx.resistance_2
        rr = (target - entry) / (entry - stop) if (entry - stop) > 0 else 1.0
        
        confidence = 75
        if ctx.volume_ratio > 2.0:
            confidence += 10
        if ctx.rsi > 60:
            confidence += 5
        if ctx.macd_histogram > 0:
            confidence += 5
        
        supporting = []
        supporting.append(f"Breaking resistance ${ctx.resistance_1:.2f}")
        supporting.append(f"Volume surge ({ctx.volume_ratio:.1f}x)")
        if ctx.rsi > 60:
            supporting.append(f"RSI momentum ({ctx.rsi:.1f})")
        if ctx.macd_histogram > 0:
            supporting.append("MACD bullish")
        
        return TechnicalSignal(
            timestamp=ctx.timestamp,
            symbol=ctx.symbol,
            action="BUY",
            signal_type="BREAKOUT",
            current_price=ctx.current_price,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=min(confidence, 95),
            risk_reward_ratio=rr,
            rsi=ctx.rsi,
            macd_histogram=ctx.macd_histogram,
            trend=ctx.trend,
            volume_ratio=ctx.volume_ratio,
            primary_reason=f"Breakout above ${ctx.resistance_1:.2f}",
            supporting_factors=supporting
        )


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    
    engine = TechnicalStrategyEngine(min_confidence=0.60)
    
    for symbol in ['SPY', 'QQQ']:
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Testing {symbol}")
        logger.info('=' * 80)
        
        signals = engine.generate_signals(symbol)
        
        if signals:
            logger.info(f"\n🎯 Generated {len(signals)} signals:")
            for sig in signals:
                logger.info(f"\n  {sig.signal_type}:")
                logger.info(f"    Action: {sig.action} @ ${sig.entry_price:.2f}")
                logger.info(f"    Stop: ${sig.stop_loss:.2f} | Target: ${sig.take_profit:.2f}")
                logger.info(f"    Confidence: {sig.confidence:.0f}% | R/R: {sig.risk_reward_ratio:.2f}")
                logger.info(f"    Reason: {sig.primary_reason}")
                for factor in sig.supporting_factors:
                    logger.info(f"      + {factor}")
        else:
            logger.info(f"\n  No signals generated")



