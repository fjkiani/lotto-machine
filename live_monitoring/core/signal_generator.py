#!/usr/bin/env python3
"""
SIGNAL GENERATOR - Pure signal generation logic
- Takes institutional context + current price
- Generates signals based on rules
- Returns structured signal objects
"""

from dataclasses import dataclass
from typing import Optional, List, Union
from datetime import datetime
import logging
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add paths
sys.path.append(str(Path(__file__).parent.parent.parent / 'core'))
sys.path.append(str(Path(__file__).parent))

from ultra_institutional_engine import UltraInstitutionalEngine, UltraSignal, InstitutionalContext
from reddit_sentiment import RedditSentimentAnalyzer
from gamma_exposure import GammaExposureTracker
from lottery_signals import SignalType, SignalAction, LiveSignal, LotterySignal
from zero_dte_strategy import ZeroDTEStrategy
from volatility_expansion import VolatilityExpansionDetector

logger = logging.getLogger(__name__)

@dataclass
class LiveSignal:
    """Simplified signal for live trading"""
    timestamp: datetime
    symbol: str
    action: str  # BUY or SELL
    signal_type: str  # SQUEEZE, GAMMA, BREAKOUT, BOUNCE
    
    # Prices
    current_price: float
    entry_price: float
    stop_loss: float
    take_profit: float
    
    # Metrics
    confidence: float
    risk_reward_ratio: float
    position_size_pct: float  # % of account
    
    # Context
    dp_level: float
    dp_volume: int
    institutional_score: float
    
    # Reasoning
    primary_reason: str
    supporting_factors: List[str]
    warnings: List[str]
    
    # State
    is_master_signal: bool
    is_actionable: bool

class SignalGenerator:
    """Generate signals from institutional intelligence"""
    
    def __init__(self, min_master_confidence: float = 0.75,
                 min_high_confidence: float = 0.60,
                 api_key: str = None,
                 use_sentiment: bool = True,
                 use_gamma: bool = True,
                 use_lottery_mode: bool = True,
                 lottery_confidence_threshold: float = 0.80):
        self.min_master_confidence = min_master_confidence
        self.min_high_confidence = min_high_confidence
        self.use_sentiment = use_sentiment
        self.use_gamma = use_gamma
        self.use_lottery_mode = use_lottery_mode
        self.lottery_threshold = lottery_confidence_threshold
        
        # Initialize sentiment analyzer if enabled
        if self.use_sentiment and api_key:
            try:
                self.sentiment_analyzer = RedditSentimentAnalyzer(api_key=api_key)
                logger.info("📱 Reddit sentiment analyzer enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize sentiment analyzer: {e}")
                self.sentiment_analyzer = None
                self.use_sentiment = False
        else:
            self.sentiment_analyzer = None
        
        # Initialize gamma tracker if enabled
        if self.use_gamma:
            try:
                self.gamma_tracker = GammaExposureTracker(api_key=api_key)
                logger.info("📊 Gamma exposure tracker enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize gamma tracker: {e}")
                self.gamma_tracker = None
                self.use_gamma = False
        else:
            self.gamma_tracker = None
        
        # Initialize lottery components if enabled
        if self.use_lottery_mode:
            try:
                self.zero_dte_strategy = ZeroDTEStrategy()
                self.vol_detector = VolatilityExpansionDetector()
                logger.info("🎰 Lottery mode enabled")
                logger.info(f"   Lottery threshold: {lottery_confidence_threshold:.0%}")
            except Exception as e:
                logger.warning(f"Failed to initialize lottery components: {e}")
                self.zero_dte_strategy = None
                self.vol_detector = None
                self.use_lottery_mode = False
        else:
            self.zero_dte_strategy = None
            self.vol_detector = None
        
        logger.info("🎯 Signal Generator initialized")
        logger.info(f"   Master threshold: {min_master_confidence:.0%}")
        logger.info(f"   High confidence threshold: {min_high_confidence:.0%}")
        logger.info(f"   Sentiment filtering: {'enabled' if self.use_sentiment else 'disabled'}")
        logger.info(f"   Gamma filtering: {'enabled' if self.use_gamma else 'disabled'}")
        logger.info(f"   Lottery mode: {'enabled' if self.use_lottery_mode else 'disabled'}")
    
    def generate_signals(self, symbol: str, current_price: float,
                        inst_context: InstitutionalContext,
                        minute_bars=None,
                        account_value: float = 100000.0) -> List[Union[LiveSignal, LotterySignal]]:
        """
        Generate signals from institutional context + real-time momentum + lottery opportunities
        
        Args:
            symbol: Ticker symbol
            current_price: Current price
            inst_context: Institutional context (yesterday's data)
            minute_bars: Optional DataFrame with recent minute bars for momentum detection
            account_value: Account value for position sizing
        
        Returns:
            List of LiveSignal or LotterySignal objects (regular + lottery)
        """
        all_signals = []
        
        try:
            # STEP 1: Generate regular signals (always)
            regular_signals = self._generate_regular_signals(
                symbol, current_price, inst_context, minute_bars
            )
            all_signals.extend(regular_signals)
            
            # STEP 2: If lottery mode enabled, check for lottery opportunities
            if self.use_lottery_mode and self.zero_dte_strategy and self.vol_detector:
                lottery_signals = self._generate_lottery_signals(
                    symbol, current_price, regular_signals, account_value
                )
                all_signals.extend(lottery_signals)
            
            # STEP 3: Apply master filters
            filtered_signals = self._apply_master_filters(all_signals)
            
            return filtered_signals
            
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            return []
    
    def _generate_regular_signals(
        self, symbol: str, current_price: float,
        inst_context: InstitutionalContext,
        minute_bars=None
    ) -> List[LiveSignal]:
        """
        Generate regular stock trading signals
        
        Returns:
            List of LiveSignal objects
        """
        signals = []
        
        try:
            # FIRST: Check for real-time selloff (momentum-based, doesn't need institutional data)
            if minute_bars is not None and len(minute_bars) >= 10:
                selloff_signal = self._detect_realtime_selloff(symbol, current_price, minute_bars)
                if selloff_signal:
                    signals.append(selloff_signal)
            # Check squeeze potential
            if inst_context.squeeze_potential >= 0.7:
                signal = self._create_squeeze_signal(symbol, current_price, inst_context)
                if signal:
                    signals.append(signal)
            
            # Check gamma pressure
            if inst_context.gamma_pressure >= 0.7:
                signal = self._create_gamma_signal(symbol, current_price, inst_context)
                if signal:
                    signals.append(signal)
            
            # Check institutional buying (breakout/bounce)
            if inst_context.institutional_buying_pressure >= 0.7:
                signal = self._create_dp_signal(symbol, current_price, inst_context)
                if signal:
                    signals.append(signal)
            
            # Check for BEARISH signals (breakdown, rejection, bearish flow)
            # Breakdown: Price breaks below DP support with volume
            breakdown_signal = self._create_breakdown_signal(symbol, current_price, inst_context)
            if breakdown_signal:
                signals.append(breakdown_signal)
            
            # Bearish institutional flow: DP sell ratio high
            if inst_context.dp_buy_sell_ratio < 0.7 and inst_context.dp_total_volume > 1_000_000:
                bearish_signal = self._create_bearish_flow_signal(symbol, current_price, inst_context)
                if bearish_signal:
                    signals.append(bearish_signal)
            
            # Filter by confidence
            signals = [s for s in signals if s.confidence >= self.min_high_confidence]
            
            # Apply sentiment filter if enabled
            if self.use_sentiment and self.sentiment_analyzer:
                filtered_signals = []
                for signal in signals:
                    try:
                        analysis = self.sentiment_analyzer.fetch_reddit_sentiment(signal.symbol, days=7)
                        if analysis:
                            should_trade, reason = self.sentiment_analyzer.should_trade_based_on_sentiment(
                                analysis, signal.action
                            )
                            if not should_trade:
                                logger.info(f"   ❌ Sentiment veto for {signal.symbol}: {reason}")
                                continue  # Skip this signal
                            else:
                                logger.debug(f"   ✅ Sentiment approved: {reason}")
                    except Exception as e:
                        logger.warning(f"Error checking sentiment for {signal.symbol}: {e}")
                        # Continue with signal if sentiment check fails
                    
                    filtered_signals.append(signal)
                
                signals = filtered_signals
            
            # Apply gamma filter if enabled
            if self.use_gamma and self.gamma_tracker:
                filtered_signals = []
                for signal in signals:
                    try:
                        gamma_data = self.gamma_tracker.calculate_gamma_exposure(
                            signal.symbol, current_price
                        )
                        if gamma_data:
                            should_trade, reason = self.gamma_tracker.should_trade_based_on_gamma(
                                current_price, gamma_data, signal.action
                            )
                            if not should_trade:
                                logger.info(f"   ❌ Gamma veto for {signal.symbol}: {reason}")
                                continue  # Skip this signal
                            else:
                                logger.debug(f"   ✅ Gamma approved: {reason}")
                                # Boost confidence if gamma regime favors the trade
                                if "favored" in reason.lower():
                                    signal.confidence = min(signal.confidence * 1.1, 1.0)
                    except Exception as e:
                        logger.warning(f"Error checking gamma for {signal.symbol}: {e}")
                        # Continue with signal if gamma check fails
                    
                    filtered_signals.append(signal)
                
                signals = filtered_signals
            
            logger.info(f"Generated {len(signals)} regular signals for {symbol}")
            
        except Exception as e:
            logger.error(f"Error generating regular signals: {e}")
        
        return signals
    
    def _generate_lottery_signals(
        self, symbol: str, current_price: float,
        regular_signals: List[LiveSignal],
        account_value: float
    ) -> List[LotterySignal]:
        """
        Generate lottery signals from high-confidence regular signals + volatility expansion
        
        Returns:
            List of LotterySignal objects
        """
        lottery_signals = []
        
        try:
            # Check volatility expansion
            vol_status = self.vol_detector.detect_expansion(symbol, lookback_minutes=30)
            
            if not vol_status:
                return lottery_signals  # No volatility data available
            
            # Check if we have volatility expansion with lottery potential
            if vol_status.lottery_potential in ['HIGH', 'MEDIUM']:
                logger.info(f"   🎰 Volatility expansion detected: {vol_status.status} ({vol_status.lottery_potential} potential)")
                
                # Convert high-confidence regular signals to lottery signals
                for signal in regular_signals:
                    if signal.confidence >= self.lottery_threshold:
                        lottery_signal = self._convert_to_lottery_signal(
                            signal, current_price, vol_status, account_value
                        )
                        if lottery_signal and lottery_signal.is_valid:
                            lottery_signals.append(lottery_signal)
                            logger.info(f"   🎰 Converted {signal.signal_type} to lottery signal")
            
            # TODO: Check for event-driven lottery setups (Phase 2)
            # event_lotteries = self._check_event_lottery_setups(symbol, current_price)
            # lottery_signals.extend(event_lotteries)
            
            logger.info(f"Generated {len(lottery_signals)} lottery signals for {symbol}")
            
        except Exception as e:
            logger.error(f"Error generating lottery signals: {e}")
        
        return lottery_signals
    
    def _convert_to_lottery_signal(
        self, regular_signal: LiveSignal, current_price: float,
        vol_status, account_value: float
    ) -> Optional[LotterySignal]:
        """
        Convert high-confidence regular signal to 0DTE lottery play
        
        Args:
            regular_signal: High-confidence regular signal
            current_price: Current stock price
            vol_status: VolatilityExpansionStatus
            account_value: Account value for position sizing
        
        Returns:
            LotterySignal or None
        """
        try:
            # Convert signal to 0DTE trade
            zero_dte_trade = self.zero_dte_strategy.convert_signal_to_0dte(
                signal_symbol=regular_signal.symbol,
                signal_action=regular_signal.action.value if isinstance(regular_signal.action, SignalAction) else regular_signal.action,
                signal_confidence=regular_signal.confidence,
                current_price=current_price,
                account_value=account_value
            )
            
            if not zero_dte_trade.is_valid or not zero_dte_trade.strike_recommendation:
                return None
            
            strike_rec = zero_dte_trade.strike_recommendation
            
            # Determine signal type
            if regular_signal.action == SignalAction.BUY or (isinstance(regular_signal.action, str) and regular_signal.action == 'BUY'):
                signal_type = SignalType.LOTTERY_0DTE_CALL
            else:
                signal_type = SignalType.LOTTERY_0DTE_PUT
            
            # Build LotterySignal
            lottery_signal = LotterySignal(
                symbol=regular_signal.symbol,
                action=regular_signal.action if isinstance(regular_signal.action, SignalAction) else SignalAction.BUY,
                timestamp=regular_signal.timestamp,
                entry_price=strike_rec.mid_price,
                target_price=zero_dte_trade.take_profit_levels[0][0] * strike_rec.mid_price if zero_dte_trade.take_profit_levels else strike_rec.mid_price * 2.0,
                stop_price=zero_dte_trade.stop_loss if zero_dte_trade.stop_loss else strike_rec.mid_price * 0.5,
                confidence=regular_signal.confidence,
                signal_type=signal_type,
                rationale=f"LOTTERY: {regular_signal.rationale} + {vol_status.lottery_potential} IV expansion",
                position_size_pct=zero_dte_trade.position_size_pct,
                position_size_dollars=zero_dte_trade.max_risk_dollars,
                risk_reward_ratio=zero_dte_trade.risk_reward_ratio,
                is_master_signal=regular_signal.confidence >= self.min_master_confidence,
                is_actionable=True,
                # Lottery-specific fields
                strike=strike_rec.strike,
                expiry=strike_rec.expiry.strftime('%Y-%m-%d') if hasattr(strike_rec.expiry, 'strftime') else str(strike_rec.expiry),
                option_type=strike_rec.option_type,
                delta=strike_rec.delta,
                gamma=strike_rec.gamma,
                iv=strike_rec.iv,
                iv_rank=vol_status.iv_spike_pct / 100.0,  # Convert % to decimal
                lottery_potential=vol_status.lottery_potential,
                open_interest=strike_rec.open_interest,
                volume=strike_rec.volume,
                bid=strike_rec.bid,
                ask=strike_rec.ask,
                spread_pct=strike_rec.spread_pct,
                liquidity_score=strike_rec.liquidity_score,
                take_profit_levels=zero_dte_trade.take_profit_levels,
                supporting_factors=[
                    f"IV expansion: {vol_status.iv_spike_pct:.1f}%",
                    f"Volatility status: {vol_status.status}",
                    f"Strike: ${strike_rec.strike:.2f} ({strike_rec.option_type})",
                    f"Delta: {strike_rec.delta:.3f}",
                    f"Premium: ${strike_rec.mid_price:.2f}",
                ]
            )
            
            return lottery_signal
            
        except Exception as e:
            logger.error(f"Error converting to lottery signal: {e}")
            return None
    
    def _apply_master_filters(self, signals: List[Union[LiveSignal, LotterySignal]]) -> List[Union[LiveSignal, LotterySignal]]:
        """
        Apply master filters to all signals (regular + lottery)
        
        Returns:
            Filtered list of signals
        """
        filtered = []
        
        for signal in signals:
            # Confidence filter
            if signal.confidence < self.min_high_confidence:
                continue
            
            # Apply sentiment filter if enabled
            if self.use_sentiment and self.sentiment_analyzer:
                try:
                    analysis = self.sentiment_analyzer.fetch_reddit_sentiment(signal.symbol, days=7)
                    if analysis:
                        should_trade, reason = self.sentiment_analyzer.should_trade_based_on_sentiment(
                            analysis, signal.action.value if isinstance(signal.action, SignalAction) else signal.action
                        )
                        if not should_trade:
                            logger.info(f"   ❌ Sentiment veto for {signal.symbol}: {reason}")
                            continue
                except Exception as e:
                    logger.warning(f"Error checking sentiment: {e}")
            
            # Apply gamma filter if enabled
            if self.use_gamma and self.gamma_tracker:
                try:
                    # For lottery signals, skip gamma filter (options have their own dynamics)
                    if isinstance(signal, LotterySignal):
                        pass  # Skip gamma filter for lottery
                    else:
                        # Regular signal gamma check
                        gamma_data = self.gamma_tracker.calculate_gamma_exposure(signal.symbol, current_price=signal.entry_price)
                        if gamma_data:
                            should_trade, reason = self.gamma_tracker.should_trade_based_on_gamma(
                                signal.entry_price, gamma_data, 
                                signal.action.value if isinstance(signal.action, SignalAction) else signal.action
                            )
                            if not should_trade:
                                logger.info(f"   ❌ Gamma veto for {signal.symbol}: {reason}")
                                continue
                except Exception as e:
                    logger.warning(f"Error checking gamma: {e}")
            
            filtered.append(signal)
        
        return filtered
    
    def _calculate_confidence_score(self, context: InstitutionalContext, 
                                    signal_type: str, price: float) -> float:
        """
        EXACT CONFIDENCE CALCULATION FORMULA
        
        Confidence = weighted sum of signal components (0-1 scale)
        
        Components:
        - Dark Pool Signal Strength: 40% weight
        - Options Flow Signal: 30% weight  
        - Sentiment Score: 15% weight
        - Gamma Exposure Signal: 15% weight
        
        Each component normalized to 0-1 scale
        """
        # 1. Dark Pool Signal Strength (40% weight)
        # Based on: DP buy/sell ratio, DP volume, battleground proximity
        dp_score = 0.0
        
        # DP buy/sell ratio (0-1)
        if context.dp_buy_sell_ratio > 1.5:
            dp_score += 0.4
        elif context.dp_buy_sell_ratio > 1.2:
            dp_score += 0.3
        elif context.dp_buy_sell_ratio > 1.0:
            dp_score += 0.2
        elif context.dp_buy_sell_ratio < 0.7:
            dp_score -= 0.2  # Bearish DP flow
        
        # DP volume strength (0-1)
        if context.dp_total_volume > 10_000_000:
            dp_score += 0.3
        elif context.dp_total_volume > 5_000_000:
            dp_score += 0.2
        elif context.dp_total_volume > 1_000_000:
            dp_score += 0.1
        
        # Battleground proximity (0-1)
        if context.dp_battlegrounds:
            nearest_bg = min([abs(bg - price) / price for bg in context.dp_battlegrounds])
            if nearest_bg < 0.001:  # Within 0.1%
                dp_score += 0.3
            elif nearest_bg < 0.003:  # Within 0.3%
                dp_score += 0.2
        
        dp_component = min(max(dp_score, 0.0), 1.0) * 0.40  # 40% weight
        
        # 2. Options Flow Signal (30% weight)
        # Based on: Put/call ratio, max pain, total OI
        options_score = 0.0
        
        # Put/call ratio (low = bullish)
        if context.put_call_ratio < 0.7:
            options_score += 0.4
        elif context.put_call_ratio < 0.9:
            options_score += 0.3
        elif context.put_call_ratio < 1.0:
            options_score += 0.2
        
        # Max pain alignment (if available)
        if context.max_pain and abs(context.max_pain - price) / price < 0.02:
            options_score += 0.3
        
        # High OI (institutional interest)
        if context.total_option_oi > 10_000_000:
            options_score += 0.3
        elif context.total_option_oi > 5_000_000:
            options_score += 0.2
        
        options_component = min(max(options_score, 0.0), 1.0) * 0.30  # 30% weight
        
        # 3. Sentiment Score (15% weight)
        # Note: Reddit sentiment handled separately, this is institutional sentiment
        # Use short volume as proxy (low shorting = bullish sentiment)
        sentiment_score = 0.0
        if context.short_volume_pct < 25:
            sentiment_score = 1.0
        elif context.short_volume_pct < 30:
            sentiment_score = 0.7
        elif context.short_volume_pct < 35:
            sentiment_score = 0.4
        
        sentiment_component = sentiment_score * 0.15  # 15% weight
        
        # 4. Gamma Exposure Signal (15% weight)
        # Based on: Gamma pressure from context
        gamma_component = context.gamma_pressure * 0.15  # 15% weight
        
        # Final confidence = sum of components
        confidence = dp_component + options_component + sentiment_component + gamma_component
        
        # Clamp to 0-1
        return min(max(confidence, 0.0), 1.0)
    
    def _create_squeeze_signal(self, symbol: str, price: float,
                               context: InstitutionalContext) -> Optional[LiveSignal]:
        """Create squeeze signal if criteria met"""
        
        # Find nearest support battleground
        supports = [bg for bg in context.dp_battlegrounds if bg <= price * 1.01]
        if not supports:
            return None
        
        nearest_support = max(supports)
        
        # Calculate stops and targets
        stop = nearest_support * 0.97  # 3% below support
        risk = price - stop
        target = price + (risk * 3.0)  # 3:1 R/R for squeeze
        
        # Calculate EXACT confidence score
        base_confidence = self._calculate_confidence_score(context, "SQUEEZE", price)
        
        # Boost for squeeze-specific factors
        squeeze_boost = 0.0
        if context.short_volume_pct > 40:
            squeeze_boost += 0.15
        if context.borrow_fee_rate > 5.0:
            squeeze_boost += 0.10
        if context.days_to_cover and context.days_to_cover > 5:
            squeeze_boost += 0.05
        
        confidence = min(base_confidence + squeeze_boost, 1.0)
        
        # Position sizing based on confidence
        if confidence >= 0.85:
            position_pct = 0.02  # Full 2%
        else:
            position_pct = 0.01  # Half size
        
        return LiveSignal(
            timestamp=datetime.now(),
            symbol=symbol,
            action="BUY",
            signal_type="SQUEEZE",
            current_price=price,
            entry_price=price,
            stop_loss=stop,
            take_profit=target,
            confidence=confidence,
            risk_reward_ratio=(target - price) / (price - stop),
            position_size_pct=position_pct,
            dp_level=nearest_support,
            dp_volume=0,  # Would need to look up
            institutional_score=context.institutional_buying_pressure,
            primary_reason=f"SQUEEZE SETUP: {context.short_volume_pct:.0f}% short, {context.borrow_fee_rate:.1f}% borrow fee",
            supporting_factors=[
                f"Days to cover: {context.days_to_cover}" if context.days_to_cover else "",
                f"Institutional buying: {context.institutional_buying_pressure:.0%}",
                f"DP support @ ${nearest_support:.2f}"
            ],
            warnings=[],
            is_master_signal=context.squeeze_potential >= self.min_master_confidence,
            is_actionable=True
        )
    
    def _create_gamma_signal(self, symbol: str, price: float,
                            context: InstitutionalContext) -> Optional[LiveSignal]:
        """Create gamma ramp signal"""
        
        if not context.max_pain or context.max_pain <= price:
            return None
        
        # Find support
        supports = [bg for bg in context.dp_battlegrounds if bg <= price * 1.01]
        if not supports:
            return None
        
        nearest_support = max(supports)
        
        stop = nearest_support * 0.97
        target = context.max_pain
        risk = price - stop
        
        # Calculate EXACT confidence score
        base_confidence = self._calculate_confidence_score(context, "GAMMA_RAMP", price)
        
        # Boost for gamma-specific factors
        gamma_boost = 0.0
        if context.put_call_ratio < 0.7:
            gamma_boost += 0.15
        if context.max_pain and abs(context.max_pain - price) / price < 0.01:
            gamma_boost += 0.10
        
        confidence = min(base_confidence + gamma_boost, 1.0)
        
        position_pct = 0.02 if confidence >= 0.85 else 0.01
        
        return LiveSignal(
            timestamp=datetime.now(),
            symbol=symbol,
            action="BUY",
            signal_type="GAMMA_RAMP",
            current_price=price,
            entry_price=price,
            stop_loss=stop,
            take_profit=target,
            confidence=confidence,
            risk_reward_ratio=(target - price) / risk if risk > 0 else 0,
            position_size_pct=position_pct,
            dp_level=nearest_support,
            dp_volume=0,
            institutional_score=context.institutional_buying_pressure,
            primary_reason=f"GAMMA RAMP: P/C {context.put_call_ratio:.2f}, Max Pain ${context.max_pain:.2f}",
            supporting_factors=[
                f"Call OI: {context.total_option_oi:,}",
                f"Max pain ${(context.max_pain - price) / price * 100:+.1f}% above",
                f"DP support @ ${nearest_support:.2f}"
            ],
            warnings=[],
            is_master_signal=context.gamma_pressure >= self.min_master_confidence,
            is_actionable=True
        )
    
    def _create_dp_signal(self, symbol: str, price: float,
                         context: InstitutionalContext) -> Optional[LiveSignal]:
        """Create DP breakout/bounce signal"""
        
        if not context.dp_battlegrounds:
            return None
        
        # Check if at support (bounce) or near resistance (breakout)
        supports = [bg for bg in context.dp_battlegrounds if bg <= price * 1.01]
        resistances = [bg for bg in context.dp_battlegrounds if bg >= price * 0.99]
        
        if supports:
            # At support - bounce play
            nearest_support = max(supports)
            signal_type = "BOUNCE"
            stop = nearest_support * 0.995  # 0.5% below
            
            # Target next resistance or 2:1 R/R
            risk = price - stop
            if resistances and min(resistances) > price:
                target = min(resistances)
            else:
                target = price + (risk * 2.0)
        
        elif resistances:
            # Near resistance - potential breakout
            nearest_resistance = min(resistances)
            
            # Only signal if VERY close (< 0.2%)
            if (nearest_resistance - price) / price > 0.002:
                return None
            
            signal_type = "BREAKOUT"
            stop = nearest_resistance * 0.997  # Below broken resistance
            risk = price - stop
            target = price + (risk * 2.0)
        
        else:
            return None
        
        # Calculate EXACT confidence score
        base_confidence = self._calculate_confidence_score(context, signal_type, price)
        
        # Boost for DP-specific factors
        dp_boost = 0.0
        if context.dp_buy_sell_ratio > 1.5:
            dp_boost += 0.15
        if context.dark_pool_pct > 50:
            dp_boost += 0.10
        
        confidence = min(base_confidence + dp_boost, 1.0)
        
        position_pct = 0.02 if confidence >= 0.85 else 0.01
        
        level = nearest_support if signal_type == "BOUNCE" else nearest_resistance
        
        return LiveSignal(
            timestamp=datetime.now(),
            symbol=symbol,
            action="BUY",
            signal_type=signal_type,
            current_price=price,
            entry_price=price,
            stop_loss=stop,
            take_profit=target,
            confidence=confidence,
            risk_reward_ratio=(target - price) / (price - stop),
            position_size_pct=position_pct,
            dp_level=level,
            dp_volume=context.dp_total_volume,
            institutional_score=context.institutional_buying_pressure,
            primary_reason=f"INSTITUTIONAL {signal_type}: {context.dp_total_volume:,} DP volume, {context.dp_buy_sell_ratio:.2f} B/S",
            supporting_factors=[
                f"Buying pressure: {context.institutional_buying_pressure:.0%}",
                f"Dark pool: {context.dark_pool_pct:.0f}%",
                f"DP level @ ${level:.2f}"
            ],
            warnings=[],
            is_master_signal=context.institutional_buying_pressure >= self.min_master_confidence,
            is_actionable=True
        )

    def _create_breakdown_signal(self, symbol: str, price: float,
                                context: InstitutionalContext) -> Optional[LiveSignal]:
        """
        Create SELL signal when price breaks below DP support
        
        This catches selloffs like the one we just missed!
        """
        if not context.dp_battlegrounds:
            return None
        
        # Find supports that price has broken below
        supports = [bg for bg in context.dp_battlegrounds if bg > price * 0.99 and bg < price * 1.02]
        
        if not supports:
            return None
        
        # Check if we just broke below a support (within 0.3%)
        nearest_support = min(supports, key=lambda x: abs(x - price))
        distance_below = (price - nearest_support) / nearest_support
        
        # Only signal if we're below support (breakdown)
        if distance_below < -0.003:  # More than 0.3% below
            return None  # Too far below, already broken
        
        if distance_below > 0.003:  # More than 0.3% above
            return None  # Not broken yet
        
        # We're at or just broke support - check for bearish confirmation
        # Need: Bearish DP flow OR high put/call ratio OR negative momentum
        
        bearish_confirmation = False
        reasons = []
        
        # Check DP flow
        if context.dp_buy_sell_ratio < 0.8:  # More selling than buying
            bearish_confirmation = True
            reasons.append(f"Bearish DP flow (B/S: {context.dp_buy_sell_ratio:.2f})")
        
        # Check put/call ratio
        if context.put_call_ratio > 1.2:  # High put activity
            bearish_confirmation = True
            reasons.append(f"High P/C ratio ({context.put_call_ratio:.2f})")
        
        # Check short volume
        if context.short_volume_pct > 35:  # High shorting
            bearish_confirmation = True
            reasons.append(f"High short volume ({context.short_volume_pct:.0f}%)")
        
        if not bearish_confirmation:
            return None  # No bearish confirmation
        
        # Calculate stops and targets
        stop = nearest_support * 1.005  # 0.5% above broken support (now resistance)
        risk = stop - price
        target = price - (risk * 2.0)  # 2:1 R/R for breakdown
        
        # Calculate confidence
        base_confidence = self._calculate_confidence_score(context, "BREAKDOWN", price)
        
        # Boost for breakdown-specific factors
        breakdown_boost = 0.0
        if context.dp_buy_sell_ratio < 0.7:
            breakdown_boost += 0.15
        if context.put_call_ratio > 1.3:
            breakdown_boost += 0.10
        if context.short_volume_pct > 40:
            breakdown_boost += 0.05
        
        confidence = min(base_confidence + breakdown_boost, 1.0)
        
        position_pct = 0.02 if confidence >= 0.85 else 0.01
        
        return LiveSignal(
            timestamp=datetime.now(),
            symbol=symbol,
            action="SELL",
            signal_type="BREAKDOWN",
            current_price=price,
            entry_price=price,
            stop_loss=stop,
            take_profit=target,
            confidence=confidence,
            risk_reward_ratio=(price - target) / (stop - price) if (stop - price) > 0 else 0,
            position_size_pct=position_pct,
            dp_level=nearest_support,
            dp_volume=context.dp_total_volume,
            institutional_score=1.0 - context.institutional_buying_pressure,  # Inverted for bearish
            primary_reason=f"BREAKDOWN below DP support ${nearest_support:.2f}",
            supporting_factors=reasons,
            warnings=[],
            is_master_signal=confidence >= self.min_master_confidence,
            is_actionable=True
        )
    
    def _create_bearish_flow_signal(self, symbol: str, price: float,
                                   context: InstitutionalContext) -> Optional[LiveSignal]:
        """
        Create SELL signal from bearish institutional flow
        
        Detects when institutions are selling heavily (DP sell ratio high)
        """
        # Need strong bearish flow
        if context.dp_buy_sell_ratio >= 0.7:
            return None  # Not bearish enough
        
        if context.dp_total_volume < 1_000_000:
            return None  # Not enough volume
        
        # Find nearest resistance for target
        resistances = [bg for bg in context.dp_battlegrounds if bg >= price * 0.99]
        if not resistances:
            return None
        
        nearest_resistance = min(resistances)
        
        # Calculate stops and targets
        stop = price * 1.01  # 1% above entry
        risk = stop - price
        target = price - (risk * 2.0)  # 2:1 R/R
        
        # Calculate confidence
        base_confidence = self._calculate_confidence_score(context, "BEARISH_FLOW", price)
        
        # Boost for bearish flow
        bearish_boost = 0.0
        if context.dp_buy_sell_ratio < 0.6:
            bearish_boost += 0.20
        elif context.dp_buy_sell_ratio < 0.7:
            bearish_boost += 0.10
        
        confidence = min(base_confidence + bearish_boost, 1.0)
        
        position_pct = 0.02 if confidence >= 0.85 else 0.01
        
        return LiveSignal(
            timestamp=datetime.now(),
            symbol=symbol,
            action="SELL",
            signal_type="BEARISH_FLOW",
            current_price=price,
            entry_price=price,
            stop_loss=stop,
            take_profit=target,
            confidence=confidence,
            risk_reward_ratio=(price - target) / (stop - price) if (stop - price) > 0 else 0,
            position_size_pct=position_pct,
            dp_level=nearest_resistance,
            dp_volume=context.dp_total_volume,
            institutional_score=1.0 - context.institutional_buying_pressure,
            primary_reason=f"BEARISH INSTITUTIONAL FLOW: DP B/S {context.dp_buy_sell_ratio:.2f}, {context.dp_total_volume:,} shares",
            supporting_factors=[
                f"Put/call ratio: {context.put_call_ratio:.2f}",
                f"Short volume: {context.short_volume_pct:.0f}%"
            ],
            warnings=[],
            is_master_signal=confidence >= self.min_master_confidence,
            is_actionable=True
        )



