#!/usr/bin/env python3
"""
GAMMA EXPOSURE TRACKER
======================
Tracks dealer gamma positioning to identify stabilizing vs amplifying regimes.

Positive gamma = dealers long options (stabilizing - buy dips, sell rallies)
Negative gamma = dealers short options (amplifying - sell dips, buy rallies)

This is THE edge for timing entries.

Author: Alpha's AI Hedge Fund
Date: 2025-01-XX
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from datetime import datetime
import logging
import yfinance as yf
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GammaExposureData:
    """Gamma exposure analysis result"""
    symbol: str
    date: str
    gamma_by_strike: Dict[float, float]  # strike -> net gamma
    gamma_flip_level: Optional[float]  # Where GEX crosses zero
    current_regime: str  # POSITIVE or NEGATIVE
    total_gex: float
    price: float


class GammaExposureTracker:
    """Tracks dealer gamma exposure to identify trading regimes"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize gamma tracker
        
        Args:
            api_key: ChartExchange API key (optional, uses yfinance as fallback)
        """
        self.api_key = api_key
        logger.info("📊 Gamma Exposure Tracker initialized")
    
    def calculate_gamma_exposure(self, symbol: str, price: float, 
                                date: Optional[str] = None) -> Optional[GammaExposureData]:
        """
        Calculate net gamma exposure at each strike
        
        Positive GEX = dealers long options (stabilizing)
        Negative GEX = dealers short options (amplifying)
        
        Args:
            symbol: Ticker symbol
            price: Current price
            date: Date for analysis (default: today)
        
        Returns:
            GammaExposureData with gamma analysis
        """
        try:
            # Get options chain from yfinance (ChartExchange only has summary)
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            
            if not expirations:
                logger.warning(f"No options expirations found for {symbol}")
                return None
            
            # Use nearest expiration for gamma calculation
            nearest_exp = expirations[0]
            opt_chain = ticker.option_chain(nearest_exp)
            
            gamma_by_strike = {}
            
            # Process calls
            for _, call in opt_chain.calls.iterrows():
                strike = float(call['strike'])
                oi = int(call['openInterest']) if 'openInterest' in call and not np.isnan(call['openInterest']) else 0
                # Gamma may not always be available in yfinance, use delta as proxy if needed
                if 'gamma' in call and not np.isnan(call['gamma']):
                    gamma = float(call['gamma'])
                elif 'delta' in call and not np.isnan(call['delta']):
                    # Use delta as rough proxy (gamma is derivative of delta)
                    gamma = abs(float(call['delta'])) * 0.1  # Rough approximation
                else:
                    gamma = 0.0
                
                # Dealers are opposite side (market makers short calls when retail buys)
                # Net gamma = -call_oi * gamma (dealers short = negative gamma)
                if strike not in gamma_by_strike:
                    gamma_by_strike[strike] = 0.0
                gamma_by_strike[strike] -= oi * gamma * 100  # Convert to shares (100 per contract)
            
            # Process puts
            for _, put in opt_chain.puts.iterrows():
                strike = float(put['strike'])
                oi = int(put['openInterest']) if 'openInterest' in put and not np.isnan(put['openInterest']) else 0
                # Gamma may not always be available in yfinance, use delta as proxy if needed
                if 'gamma' in put and not np.isnan(put['gamma']):
                    gamma = float(put['gamma'])
                elif 'delta' in put and not np.isnan(put['delta']):
                    # Use delta as rough proxy (gamma is derivative of delta)
                    gamma = abs(float(put['delta'])) * 0.1  # Rough approximation
                else:
                    gamma = 0.0
                
                # Dealers are opposite side (market makers short puts when retail buys)
                # Net gamma = +put_oi * gamma (dealers short puts = positive gamma)
                if strike not in gamma_by_strike:
                    gamma_by_strike[strike] = 0.0
                gamma_by_strike[strike] += oi * gamma * 100  # Convert to shares
            
            # Find gamma flip point (where GEX crosses zero)
            gamma_flip = self._find_gamma_flip(gamma_by_strike, price)
            
            # Determine current regime
            current_regime = 'POSITIVE' if price > gamma_flip else 'NEGATIVE' if gamma_flip else 'UNKNOWN'
            
            # Calculate total GEX
            total_gex = sum(gamma_by_strike.values())
            
            return GammaExposureData(
                symbol=symbol,
                date=date or datetime.now().strftime('%Y-%m-%d'),
                gamma_by_strike=gamma_by_strike,
                gamma_flip_level=gamma_flip,
                current_regime=current_regime,
                total_gex=total_gex,
                price=price
            )
            
        except Exception as e:
            logger.error(f"Error calculating gamma exposure for {symbol}: {e}")
            return None
    
    def _find_gamma_flip(self, gamma_by_strike: Dict[float, float], 
                        current_price: float) -> Optional[float]:
        """
        Find the price level where gamma exposure flips from positive to negative
        
        Returns the strike closest to current price where GEX crosses zero
        """
        if not gamma_by_strike:
            return None
        
        # Sort strikes by distance from current price
        strikes = sorted(gamma_by_strike.keys(), key=lambda s: abs(s - current_price))
        
        # Find where cumulative GEX crosses zero
        cumulative_gex = 0.0
        for strike in strikes:
            cumulative_gex += gamma_by_strike[strike]
            
            # If we've crossed zero, return this strike
            if cumulative_gex <= 0:
                return strike
        
        # If never crossed zero, return strike with minimum GEX
        min_gex_strike = min(gamma_by_strike.items(), key=lambda x: abs(x[1]))
        return min_gex_strike[0]
    
    def should_trade_based_on_gamma(self, price: float, gamma_data: GammaExposureData, 
                                   signal_action: str) -> Tuple[bool, str]:
        """
        Gamma-aware trade approval
        
        Args:
            price: Current price
            gamma_data: Gamma exposure analysis
            signal_action: 'BUY' or 'SELL'
        
        Returns:
            (should_trade: bool, reason: str)
        """
        regime = gamma_data.current_regime
        flip = gamma_data.gamma_flip_level
        
        if not flip:
            return True, "No gamma flip level detected - proceeding"
        
        # LONG signals: Better below gamma flip (negative gamma = buy dips amplified)
        if signal_action == 'BUY':
            if regime == 'NEGATIVE':
                return True, "Negative gamma regime - long signals favored (amplified moves)"
            elif regime == 'POSITIVE':
                return False, "Positive gamma regime - long signals dampened (dealers stabilize)"
            else:
                return True, "Unknown gamma regime - proceeding"
        
        # SHORT signals: Better above gamma flip (negative gamma = sell rallies amplified)
        elif signal_action == 'SELL':
            if regime == 'NEGATIVE':
                return True, "Negative gamma regime - short signals favored (amplified moves)"
            elif regime == 'POSITIVE':
                return False, "Positive gamma regime - short signals dampened (dealers stabilize)"
            else:
                return True, "Unknown gamma regime - proceeding"
        
        return True, "Gamma check passed"
    
    def get_gamma_regime_summary(self, gamma_data: GammaExposureData) -> str:
        """Get human-readable summary of gamma regime"""
        if not gamma_data:
            return "No gamma data available"
        
        summary = f"Gamma Regime: {gamma_data.current_regime}\n"
        summary += f"Gamma Flip Level: ${gamma_data.gamma_flip_level:.2f}\n" if gamma_data.gamma_flip_level else "No flip level\n"
        summary += f"Total GEX: {gamma_data.total_gex:,.0f} shares\n"
        summary += f"Current Price: ${gamma_data.price:.2f}\n"
        
        if gamma_data.gamma_flip_level:
            distance = abs(gamma_data.price - gamma_data.gamma_flip_level) / gamma_data.price * 100
            summary += f"Distance to Flip: {distance:.2f}%\n"
        
        return summary


if __name__ == "__main__":
    # Test the gamma tracker
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    tracker = GammaExposureTracker()
    
    # Test with SPY
    symbol = "SPY"
    ticker = yf.Ticker(symbol)
    price = float(ticker.history(period='1d')['Close'].iloc[-1])
    
    print(f"\n📊 Testing Gamma Exposure Tracker for {symbol}")
    print(f"Current Price: ${price:.2f}\n")
    
    gamma_data = tracker.calculate_gamma_exposure(symbol, price)
    
    if gamma_data:
        print(tracker.get_gamma_regime_summary(gamma_data))
        
        # Test trade approval
        should_trade, reason = tracker.should_trade_based_on_gamma(price, gamma_data, 'BUY')
        print(f"\nBUY Signal: {'✅' if should_trade else '❌'} - {reason}")
        
        should_trade, reason = tracker.should_trade_based_on_gamma(price, gamma_data, 'SELL')
        print(f"SELL Signal: {'✅' if should_trade else '❌'} - {reason}")
    else:
        print("❌ Failed to calculate gamma exposure")

