#!/usr/bin/env python3
"""
ZERO DTE STRATEGY - Modular 0DTE Options Strategy Component

This module handles:
- Strike selection for 0DTE options (deep OTM lottery tickets)
- Position sizing (0.5-1% risk vs 2% for normal signals)
- Premium filtering (< $1.00 for cheap lottery)
- Open interest checks (> 1000 for liquidity)
- IV filtering (> 30% for movement expected)

COMPONENT-BASED ARCHITECTURE:
- Pure logic, no side effects
- Takes signal + options data → returns 0DTE recommendation
- Can be easily tested, improved, or replaced
"""

from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from datetime import datetime, date
import logging
import yfinance as yf
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ZeroDTEStrike:
    """0DTE strike recommendation"""
    symbol: str
    strike: float
    option_type: str  # 'CALL' or 'PUT'
    expiry: date
    premium: float
    delta: float
    gamma: float
    iv: float
    open_interest: int
    volume: int
    bid: float
    ask: float
    mid_price: float
    spread_pct: float
    liquidity_score: str  # 'HIGH', 'MEDIUM', 'LOW'
    lottery_potential: str  # 'HIGH', 'MEDIUM', 'LOW'
    reason: str


@dataclass
class ZeroDTETrade:
    """Complete 0DTE trade recommendation"""
    signal_symbol: str
    signal_action: str  # 'BUY' or 'SELL'
    signal_confidence: float
    strike_recommendation: Optional[ZeroDTEStrike]
    position_size_pct: float  # % of account (0.5-1% for 0DTE)
    max_risk_dollars: float
    expected_premium: float
    entry_price: float
    stop_loss: Optional[float]  # Usually 50% of premium
    take_profit_levels: List[Tuple[float, float]]  # [(multiple, sell_pct), ...]
    is_valid: bool
    rejection_reason: Optional[str]


class ZeroDTEStrategy:
    """
    Modular 0DTE options strategy component
    
    This is a PURE component - no state, no side effects.
    Takes inputs → returns outputs.
    Easy to test, improve, or replace.
    """
    
    def __init__(
        self,
        min_delta: float = 0.05,
        max_delta: float = 0.10,
        max_premium: float = 1.00,
        min_open_interest: int = 1000,
        min_volume: int = 100,
        min_iv: float = 0.30,
        max_spread_pct: float = 0.20
    ):
        """
        Initialize 0DTE strategy with configurable parameters
        
        Args:
            min_delta: Minimum delta (0.05 = deep OTM)
            max_delta: Maximum delta (0.10 = not too close to ATM)
            max_premium: Maximum premium to pay (< $1.00 for cheap lottery)
            min_open_interest: Minimum OI for liquidity (1000+)
            min_volume: Minimum daily volume (100+)
            min_iv: Minimum IV (30%+ for movement expected)
            max_spread_pct: Maximum bid-ask spread (20% of mid)
        """
        self.min_delta = min_delta
        self.max_delta = max_delta
        self.max_premium = max_premium
        self.min_open_interest = min_open_interest
        self.min_volume = min_volume
        self.min_iv = min_iv
        self.max_spread_pct = max_spread_pct
        
        logger.info("🎰 ZeroDTE Strategy initialized")
        logger.info(f"   Delta range: {min_delta}-{max_delta}")
        logger.info(f"   Max premium: ${max_premium:.2f}")
        logger.info(f"   Min OI: {min_open_interest:,}")
        logger.info(f"   Min IV: {min_iv:.0%}")
    
    def convert_signal_to_0dte(
        self,
        signal_symbol: str,
        signal_action: str,
        signal_confidence: float,
        current_price: float,
        account_value: float = 100000.0
    ) -> ZeroDTETrade:
        """
        Convert a regular signal to a 0DTE options trade
        
        This is the MAIN entry point for the component.
        
        Args:
            signal_symbol: Ticker symbol (e.g., 'SPY')
            signal_action: 'BUY' or 'SELL'
            signal_confidence: Signal confidence (0-1)
            current_price: Current stock price
            account_value: Account value for position sizing
        
        Returns:
            ZeroDTETrade object with strike recommendation and position sizing
        """
        try:
            # Fetch 0DTE options chain
            options_chain = self._fetch_0dte_chain(signal_symbol)
            if not options_chain:
                return ZeroDTETrade(
                    signal_symbol=signal_symbol,
                    signal_action=signal_action,
                    signal_confidence=signal_confidence,
                    strike_recommendation=None,
                    position_size_pct=0.0,
                    max_risk_dollars=0.0,
                    expected_premium=0.0,
                    entry_price=current_price,
                    stop_loss=None,
                    take_profit_levels=[],
                    is_valid=False,
                    rejection_reason="No 0DTE options chain available"
                )
            
            # Select best strike
            strike_rec = self.select_strike(
                signal_action=signal_action,
                current_price=current_price,
                options_chain=options_chain
            )
            
            if not strike_rec:
                return ZeroDTETrade(
                    signal_symbol=signal_symbol,
                    signal_action=signal_action,
                    signal_confidence=signal_confidence,
                    strike_recommendation=None,
                    position_size_pct=0.0,
                    max_risk_dollars=0.0,
                    expected_premium=0.0,
                    entry_price=current_price,
                    stop_loss=None,
                    take_profit_levels=[],
                    is_valid=False,
                    rejection_reason="No suitable 0DTE strike found"
                )
            
            # Calculate position size
            position_pct, max_risk = self.calculate_position_size_0dte(
                account_value=account_value,
                signal_confidence=signal_confidence,
                premium=strike_rec.mid_price
            )
            
            # Calculate stop loss (usually 50% of premium)
            stop_loss = strike_rec.mid_price * 0.5 if strike_rec.mid_price > 0 else None
            
            # Define profit-taking levels
            take_profit_levels = [
                (2.0, 0.30),   # 2x = sell 30%
                (5.0, 0.30),   # 5x = sell 30% more
                (10.0, 0.30),  # 10x = sell 30% more
                (20.0, 0.10),  # 20x = sell final 10%, let rest run
            ]
            
            return ZeroDTETrade(
                signal_symbol=signal_symbol,
                signal_action=signal_action,
                signal_confidence=signal_confidence,
                strike_recommendation=strike_rec,
                position_size_pct=position_pct,
                max_risk_dollars=max_risk,
                expected_premium=strike_rec.mid_price,
                entry_price=strike_rec.mid_price,
                stop_loss=stop_loss,
                take_profit_levels=take_profit_levels,
                is_valid=True,
                rejection_reason=None
            )
            
        except Exception as e:
            logger.error(f"Error converting signal to 0DTE: {e}")
            return ZeroDTETrade(
                signal_symbol=signal_symbol,
                signal_action=signal_action,
                signal_confidence=signal_confidence,
                strike_recommendation=None,
                position_size_pct=0.0,
                max_risk_dollars=0.0,
                expected_premium=0.0,
                entry_price=current_price,
                stop_loss=None,
                take_profit_levels=[],
                is_valid=False,
                rejection_reason=f"Error: {str(e)}"
            )
    
    def select_strike(
        self,
        signal_action: str,
        current_price: float,
        options_chain: pd.DataFrame
    ) -> Optional[ZeroDTEStrike]:
        """
        Select best 0DTE strike based on signal direction
        
        For BUY signals: Select CALL strike (above current price)
        For SELL signals: Select PUT strike (below current price)
        
        Args:
            signal_action: 'BUY' or 'SELL'
            current_price: Current stock price
            options_chain: DataFrame with 0DTE options data
        
        Returns:
            ZeroDTEStrike recommendation or None
        """
        try:
            if signal_action == 'BUY':
                # Calls: Strike above current price
                target_strikes = [
                    current_price * 1.02,  # 2% OTM
                    current_price * 1.03,  # 3% OTM
                    current_price * 1.05,  # 5% OTM
                ]
                option_type = 'CALL'
            elif signal_action == 'SELL':
                # Puts: Strike below current price
                target_strikes = [
                    current_price * 0.98,  # 2% OTM
                    current_price * 0.97,  # 3% OTM
                    current_price * 0.95,  # 5% OTM
                ]
                option_type = 'PUT'
            else:
                logger.warning(f"Unknown signal action: {signal_action}")
                return None
            
            # Filter options by type
            options = options_chain[options_chain['optionType'] == option_type].copy()
            
            if options.empty:
                logger.warning(f"No {option_type} options found")
                return None
            
            # Find best strike for each target
            best_strikes = []
            for target_strike in target_strikes:
                # Find closest strike
                options['strike_diff'] = abs(options['strike'] - target_strike)
                closest = options.nsmallest(1, 'strike_diff')
                
                if not closest.empty:
                    best_strikes.append(closest.iloc[0])
            
            if not best_strikes:
                return None
            
            # Score each strike and pick best
            scored_strikes = []
            for strike_data in best_strikes:
                score = self._score_strike(strike_data, current_price)
                if score > 0:  # Only include valid strikes
                    scored_strikes.append((score, strike_data))
            
            if not scored_strikes:
                return None
            
            # Pick highest scoring strike
            best_score, best_strike = max(scored_strikes, key=lambda x: x[0])
            
            # Build recommendation
            return self._build_strike_recommendation(
                best_strike, current_price, option_type
            )
            
        except Exception as e:
            logger.error(f"Error selecting strike: {e}")
            return None
    
    def _score_strike(self, strike_data: pd.Series, current_price: float) -> float:
        """
        Score a strike based on our criteria
        
        Returns:
            Score (0-100), 0 = invalid
        """
        score = 0.0
        
        try:
            # Check delta (must be in range)
            delta = abs(float(strike_data.get('delta', 0)))
            if not (self.min_delta <= delta <= self.max_delta):
                return 0.0  # Invalid
            
            # Delta score (closer to middle of range = better)
            delta_mid = (self.min_delta + self.max_delta) / 2
            delta_score = 1.0 - abs(delta - delta_mid) / (self.max_delta - self.min_delta)
            score += delta_score * 30  # 30 points max
            
            # Premium score (cheaper = better, but must be > 0)
            premium = float(strike_data.get('lastPrice', strike_data.get('bid', 0)))
            if premium <= 0 or premium > self.max_premium:
                return 0.0  # Invalid
            
            premium_score = 1.0 - (premium / self.max_premium)
            score += premium_score * 20  # 20 points max
            
            # Open interest score
            oi = int(strike_data.get('openInterest', 0))
            if oi < self.min_open_interest:
                return 0.0  # Invalid
            
            oi_score = min(oi / (self.min_open_interest * 5), 1.0)  # Cap at 5x min
            score += oi_score * 20  # 20 points max
            
            # Volume score
            volume = int(strike_data.get('volume', 0))
            if volume < self.min_volume:
                return 0.0  # Invalid
            
            volume_score = min(volume / (self.min_volume * 5), 1.0)  # Cap at 5x min
            score += volume_score * 10  # 10 points max
            
            # IV score (higher = better, but must be > min)
            iv = float(strike_data.get('impliedVolatility', 0))
            if iv < self.min_iv:
                return 0.0  # Invalid
            
            iv_score = min((iv - self.min_iv) / 0.5, 1.0)  # Cap at 50% IV
            score += iv_score * 10  # 10 points max
            
            # Spread score (tighter = better)
            bid = float(strike_data.get('bid', 0))
            ask = float(strike_data.get('ask', 0))
            mid = (bid + ask) / 2 if (bid > 0 and ask > 0) else premium
            spread = ask - bid
            spread_pct = spread / mid if mid > 0 else 1.0
            
            if spread_pct > self.max_spread_pct:
                return 0.0  # Invalid
            
            spread_score = 1.0 - (spread_pct / self.max_spread_pct)
            score += spread_score * 10  # 10 points max
            
            return score
            
        except Exception as e:
            logger.debug(f"Error scoring strike: {e}")
            return 0.0
    
    def _build_strike_recommendation(
        self,
        strike_data: pd.Series,
        current_price: float,
        option_type: str
    ) -> ZeroDTEStrike:
        """Build ZeroDTEStrike object from strike data"""
        try:
            strike = float(strike_data.get('strike', 0))
            bid = float(strike_data.get('bid', 0))
            ask = float(strike_data.get('ask', 0))
            mid = (bid + ask) / 2 if (bid > 0 and ask > 0) else float(strike_data.get('lastPrice', 0))
            spread = ask - bid
            spread_pct = (spread / mid * 100) if mid > 0 else 0.0
            
            # Determine liquidity score
            oi = int(strike_data.get('openInterest', 0))
            volume = int(strike_data.get('volume', 0))
            
            if oi >= 5000 and volume >= 500 and spread_pct < 10:
                liquidity = 'HIGH'
            elif oi >= 2000 and volume >= 200 and spread_pct < 15:
                liquidity = 'MEDIUM'
            else:
                liquidity = 'LOW'
            
            # Determine lottery potential
            delta = abs(float(strike_data.get('delta', 0)))
            iv = float(strike_data.get('impliedVolatility', 0))
            premium = mid
            
            if delta <= 0.07 and iv >= 0.40 and premium <= 0.50:
                lottery = 'HIGH'
            elif delta <= 0.09 and iv >= 0.35 and premium <= 0.75:
                lottery = 'MEDIUM'
            else:
                lottery = 'LOW'
            
            # Get expiry date (today for 0DTE)
            expiry = date.today()
            
            reason = f"{option_type} {strike:.2f} (Delta: {delta:.3f}, IV: {iv:.0%}, Premium: ${premium:.2f})"
            
            return ZeroDTEStrike(
                symbol=strike_data.get('symbol', ''),
                strike=strike,
                option_type=option_type,
                expiry=expiry,
                premium=mid,
                delta=delta,
                gamma=float(strike_data.get('gamma', 0)),
                iv=iv,
                open_interest=oi,
                volume=volume,
                bid=bid,
                ask=ask,
                mid_price=mid,
                spread_pct=spread_pct,
                liquidity_score=liquidity,
                lottery_potential=lottery,
                reason=reason
            )
            
        except Exception as e:
            logger.error(f"Error building strike recommendation: {e}")
            raise
    
    def calculate_position_size_0dte(
        self,
        account_value: float,
        signal_confidence: float,
        premium: float
    ) -> Tuple[float, float]:
        """
        Calculate position size for 0DTE (0.5-1% risk vs 2% for normal)
        
        Args:
            account_value: Total account value
            signal_confidence: Signal confidence (0-1)
            premium: Option premium per contract
        
        Returns:
            (position_size_pct, max_risk_dollars)
        """
        # 0DTE = higher risk, smaller position
        # Normal signals: 2% risk
        # 0DTE signals: 0.5-1% risk (can lose 100%)
        
        if signal_confidence > 0.85:
            risk_pct = 0.01  # 1% risk
        elif signal_confidence > 0.75:
            risk_pct = 0.005  # 0.5% risk
        else:
            risk_pct = 0.0  # Don't take <75% confidence on 0DTE
        
        max_risk_dollars = account_value * risk_pct
        
        # Calculate how many contracts we can buy
        if premium > 0:
            max_contracts = int(max_risk_dollars / premium)
            position_value = max_contracts * premium
            position_pct = (position_value / account_value) if account_value > 0 else 0.0
        else:
            position_pct = 0.0
            max_risk_dollars = 0.0
        
        return position_pct, max_risk_dollars
    
    def _fetch_0dte_chain(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetch 0DTE options chain using yfinance
        
        Returns:
            DataFrame with 0DTE options or None
        """
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            
            if not expirations:
                logger.warning(f"No options expirations found for {symbol}")
                return None
            
            # Find today's expiration (0DTE)
            today = date.today()
            today_str = today.strftime('%Y-%m-%d')
            
            # Check if today is an expiration
            if today_str not in expirations:
                # Find nearest expiration (might be tomorrow)
                nearest = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d').date() - today).days))
                nearest_date = datetime.strptime(nearest, '%Y-%m-%d').date()
                
                if (nearest_date - today).days > 1:
                    logger.warning(f"No 0DTE expiration for {symbol} (nearest: {nearest})")
                    return None
                
                # Use nearest (might be 1DTE)
                expiry_to_use = nearest
            else:
                expiry_to_use = today_str
            
            # Get options chain for this expiration
            opt_chain = ticker.option_chain(expiry_to_use)
            
            # Combine calls and puts
            calls = opt_chain.calls.copy()
            calls['optionType'] = 'CALL'
            puts = opt_chain.puts.copy()
            puts['optionType'] = 'PUT'
            
            # Combine
            all_options = pd.concat([calls, puts], ignore_index=True)
            all_options['symbol'] = symbol
            all_options['expiry'] = expiry_to_use
            
            logger.debug(f"Fetched {len(all_options)} 0DTE options for {symbol}")
            
            return all_options
            
        except Exception as e:
            logger.error(f"Error fetching 0DTE chain for {symbol}: {e}")
            return None

