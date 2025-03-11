import numpy as np
from scipy.stats import norm
from datetime import datetime
import math
from typing import Literal, Dict, List, Optional
import json
import os
import logging

from src.data.models import OptionContract, OptionChain

# Set up logging
logger = logging.getLogger(__name__)

def calculate_option_price(S: float, K: float, T: float, r: float, sigma: float, option_type: Literal["CALL", "PUT"]) -> float:
    """Calculate option price using Black-Scholes model
    
    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration in years
        r: Risk-free interest rate
        sigma: Volatility
        option_type: "CALL" or "PUT"
        
    Returns:
        Option price
    """
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == "CALL":
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:  # PUT
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    
    return price

def calculate_greeks(option: OptionContract, underlying_price: float, risk_free_rate: float = 0.05) -> Dict[str, float]:
    """Calculate option Greeks
    
    Args:
        option: Option contract
        underlying_price: Current price of the underlying asset
        risk_free_rate: Risk-free interest rate (default: 0.05 or 5%)
        
    Returns:
        Dictionary with Greeks (delta, gamma, theta, vega, rho)
    """
    if not option.expiration or not option.implied_volatility:
        return {
            "delta": None,
            "gamma": None,
            "theta": None,
            "vega": None,
            "rho": None
        }
    
    # Extract parameters
    S = float(underlying_price)
    K = float(option.strike)
    sigma = float(option.implied_volatility)
    
    # Calculate time to expiration in years
    now = datetime.now()
    T = (option.expiration - now).total_seconds() / (365.25 * 24 * 60 * 60)
    
    if T <= 0:
        return {
            "delta": None,
            "gamma": None,
            "theta": None,
            "vega": None,
            "rho": None
        }
    
    r = risk_free_rate
    
    # Calculate d1 and d2
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    # Calculate Greeks
    if option.option_type == "CALL":
        delta = norm.cdf(d1)
        theta = -(S * sigma * norm.pdf(d1)) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)
    else:  # PUT
        delta = norm.cdf(d1) - 1
        theta = -(S * sigma * norm.pdf(d1)) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)
    
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = S * np.sqrt(T) * norm.pdf(d1) / 100  # Divided by 100 to get the effect of 1% change in volatility
    rho = K * T * np.exp(-r * T) * (norm.cdf(d2) if option.option_type == "CALL" else -norm.cdf(-d2)) / 100
    
    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta / 365,  # Daily theta
        "vega": vega,
        "rho": rho
    }

def evaluate_market_conditions(option_chain: OptionChain) -> Dict[str, any]:
    """Evaluate market conditions based on options data
    
    Args:
        option_chain: Option chain data
        
    Returns:
        Dictionary with market condition indicators
    """
    # Extract all call and put contracts
    all_calls = []
    all_puts = []
    
    for options in option_chain.options:
        for straddle in options.straddles:
            if straddle.call_contract:
                all_calls.append(straddle.call_contract)
            if straddle.put_contract:
                all_puts.append(straddle.put_contract)
    
    # Calculate put-call ratio
    call_volume = sum(c.volume or 0 for c in all_calls)
    put_volume = sum(p.volume or 0 for p in all_puts)
    
    put_call_ratio = put_volume / call_volume if call_volume > 0 else None
    
    # Calculate implied volatility skew
    atm_strike = min(option_chain.strikes, key=lambda x: abs(float(x) - float(option_chain.quote.regular_market_price)))
    
    # Find ATM options
    atm_calls = [c for c in all_calls if c.strike == atm_strike]
    atm_puts = [p for p in all_puts if p.strike == atm_strike]
    
    # Calculate average IV for ATM options
    atm_call_iv = sum(float(c.implied_volatility or 0) for c in atm_calls) / len(atm_calls) if atm_calls else None
    atm_put_iv = sum(float(p.implied_volatility or 0) for p in atm_puts) / len(atm_puts) if atm_puts else None
    
    # Calculate IV skew (difference between put and call IV)
    iv_skew = atm_put_iv - atm_call_iv if (atm_put_iv and atm_call_iv) else None
    
    # Determine market sentiment
    sentiment = "neutral"
    if put_call_ratio:
        if put_call_ratio > 1.2:
            sentiment = "bearish"  # High put volume indicates bearish sentiment
        elif put_call_ratio < 0.8:
            sentiment = "bullish"  # High call volume indicates bullish sentiment
    
    # Check for overbought/oversold conditions
    condition = "normal"
    if iv_skew:
        if iv_skew > 0.05:  # Put IV much higher than call IV
            condition = "oversold"  # Market may be oversold (fear premium in puts)
        elif iv_skew < -0.05:  # Call IV much higher than put IV
            condition = "overbought"  # Market may be overbought (greed premium in calls)
    
    return {
        "put_call_ratio": put_call_ratio,
        "implied_volatility_skew": iv_skew,
        "sentiment": sentiment,
        "market_condition": condition,
        "atm_call_iv": atm_call_iv,
        "atm_put_iv": atm_put_iv
    }

def find_optimal_options_strategy(option_chain: OptionChain, risk_tolerance: Literal["low", "medium", "high"]) -> Dict[str, any]:
    """Find optimal options strategy based on market conditions and risk tolerance
    
    Args:
        option_chain: Option chain data
        risk_tolerance: Risk tolerance level
        
    Returns:
        Dictionary with recommended strategy
    """
    # Evaluate market conditions
    market_conditions = evaluate_market_conditions(option_chain)
    
    # Current price
    current_price = float(option_chain.quote.regular_market_price)
    
    # Get nearest expiration (30-45 days out is ideal for many strategies)
    now = datetime.now()
    target_days = 45 if risk_tolerance == "low" else (30 if risk_tolerance == "medium" else 15)
    
    # Find closest expiration to target days
    expirations = sorted(option_chain.expiration_dates)
    target_exp = min(expirations, key=lambda x: abs((x - now).days - target_days))
    
    # Get options for this expiration
    target_options = next((o for o in option_chain.options if o.expiration_date == target_exp), None)
    
    if not target_options:
        return {"error": "No suitable expiration found"}
    
    # Find ATM strike
    atm_strike = min(option_chain.strikes, key=lambda x: abs(float(x) - current_price))
    
    # Find ATM straddle
    atm_straddle = next((s for s in target_options.straddles if s.strike == atm_strike), None)
    
    if not atm_straddle:
        return {"error": "No suitable strikes found"}
    
    # Determine strategy based on market conditions and risk tolerance
    strategy = {}
    
    if market_conditions["sentiment"] == "bullish":
        if risk_tolerance == "low":
            # Bull call spread
            higher_strike = min((s.strike for s in target_options.straddles if float(s.strike) > float(atm_strike)), key=lambda x: abs(float(x) - (current_price * 1.05)))
            higher_straddle = next((s for s in target_options.straddles if s.strike == higher_strike), None)
            
            strategy = {
                "name": "Bull Call Spread",
                "description": "Buy ATM call, sell OTM call",
                "legs": [
                    {"type": "buy", "option": atm_straddle.call_contract},
                    {"type": "sell", "option": higher_straddle.call_contract if higher_straddle else None}
                ],
                "max_profit": float(higher_strike) - float(atm_strike) - (float(atm_straddle.call_contract.ask) - float(higher_straddle.call_contract.bid)) if higher_straddle else None,
                "max_loss": float(atm_straddle.call_contract.ask) - float(higher_straddle.call_contract.bid) if higher_straddle else None
            }
        elif risk_tolerance == "medium":
            # Long call
            strategy = {
                "name": "Long Call",
                "description": "Buy ATM call",
                "legs": [
                    {"type": "buy", "option": atm_straddle.call_contract}
                ],
                "max_profit": "Unlimited",
                "max_loss": float(atm_straddle.call_contract.ask)
            }
        else:  # high risk
            # Call backspread
            lower_strike = max((s.strike for s in target_options.straddles if float(s.strike) < float(atm_strike)), key=lambda x: float(x))
            lower_straddle = next((s for s in target_options.straddles if s.strike == lower_strike), None)
            
            strategy = {
                "name": "Call Backspread",
                "description": "Sell ITM call, buy multiple OTM calls",
                "legs": [
                    {"type": "sell", "option": lower_straddle.call_contract if lower_straddle else None},
                    {"type": "buy", "option": atm_straddle.call_contract, "quantity": 2}
                ],
                "max_profit": "Unlimited",
                "max_loss": float(atm_strike) - float(lower_strike) - (2 * float(atm_straddle.call_contract.ask) - float(lower_straddle.call_contract.bid)) if lower_straddle else None
            }
    
    elif market_conditions["sentiment"] == "bearish":
        if risk_tolerance == "low":
            # Bear put spread
            lower_strike = max((s.strike for s in target_options.straddles if float(s.strike) < float(atm_strike)), key=lambda x: abs(float(x) - (current_price * 0.95)))
            lower_straddle = next((s for s in target_options.straddles if s.strike == lower_strike), None)
            
            strategy = {
                "name": "Bear Put Spread",
                "description": "Buy ATM put, sell OTM put",
                "legs": [
                    {"type": "buy", "option": atm_straddle.put_contract},
                    {"type": "sell", "option": lower_straddle.put_contract if lower_straddle else None}
                ],
                "max_profit": float(atm_strike) - float(lower_strike) - (float(atm_straddle.put_contract.ask) - float(lower_straddle.put_contract.bid)) if lower_straddle else None,
                "max_loss": float(atm_straddle.put_contract.ask) - float(lower_straddle.put_contract.bid) if lower_straddle else None
            }
        elif risk_tolerance == "medium":
            # Long put
            strategy = {
                "name": "Long Put",
                "description": "Buy ATM put",
                "legs": [
                    {"type": "buy", "option": atm_straddle.put_contract}
                ],
                "max_profit": float(atm_strike),
                "max_loss": float(atm_straddle.put_contract.ask)
            }
        else:  # high risk
            # Put backspread
            higher_strike = min((s.strike for s in target_options.straddles if float(s.strike) > float(atm_strike)), key=lambda x: float(x))
            higher_straddle = next((s for s in target_options.straddles if s.strike == higher_strike), None)
            
            strategy = {
                "name": "Put Backspread",
                "description": "Sell ITM put, buy multiple OTM puts",
                "legs": [
                    {"type": "sell", "option": higher_straddle.put_contract if higher_straddle else None},
                    {"type": "buy", "option": atm_straddle.put_contract, "quantity": 2}
                ],
                "max_profit": float(atm_strike),
                "max_loss": float(higher_strike) - float(atm_strike) - (2 * float(atm_straddle.put_contract.ask) - float(higher_straddle.put_contract.bid)) if higher_straddle else None
            }
    
    else:  # neutral
        if risk_tolerance == "low":
            # Iron condor
            lower_strike1 = max((s.strike for s in target_options.straddles if float(s.strike) < float(atm_strike) * 0.95), key=lambda x: float(x))
            lower_strike2 = max((s.strike for s in target_options.straddles if float(s.strike) < float(atm_strike) * 0.97), key=lambda x: float(x))
            higher_strike1 = min((s.strike for s in target_options.straddles if float(s.strike) > float(atm_strike) * 1.03), key=lambda x: float(x))
            higher_strike2 = min((s.strike for s in target_options.straddles if float(s.strike) > float(atm_strike) * 1.05), key=lambda x: float(x))
            
            lower_straddle1 = next((s for s in target_options.straddles if s.strike == lower_strike1), None)
            lower_straddle2 = next((s for s in target_options.straddles if s.strike == lower_strike2), None)
            higher_straddle1 = next((s for s in target_options.straddles if s.strike == higher_strike1), None)
            higher_straddle2 = next((s for s in target_options.straddles if s.strike == higher_strike2), None)
            
            strategy = {
                "name": "Iron Condor",
                "description": "Sell OTM put spread and OTM call spread",
                "legs": [
                    {"type": "buy", "option": lower_straddle1.put_contract if lower_straddle1 else None},
                    {"type": "sell", "option": lower_straddle2.put_contract if lower_straddle2 else None},
                    {"type": "sell", "option": higher_straddle1.call_contract if higher_straddle1 else None},
                    {"type": "buy", "option": higher_straddle2.call_contract if higher_straddle2 else None}
                ],
                "max_profit": "Credit received",
                "max_loss": "Width of wider spread - credit received"
            }
        elif risk_tolerance == "medium":
            # Short straddle
            strategy = {
                "name": "Short Straddle",
                "description": "Sell ATM call and put",
                "legs": [
                    {"type": "sell", "option": atm_straddle.call_contract},
                    {"type": "sell", "option": atm_straddle.put_contract}
                ],
                "max_profit": float(atm_straddle.call_contract.bid) + float(atm_straddle.put_contract.bid),
                "max_loss": "Unlimited"
            }
        else:  # high risk
            # Long straddle
            strategy = {
                "name": "Long Straddle",
                "description": "Buy ATM call and put",
                "legs": [
                    {"type": "buy", "option": atm_straddle.call_contract},
                    {"type": "buy", "option": atm_straddle.put_contract}
                ],
                "max_profit": "Unlimited",
                "max_loss": float(atm_straddle.call_contract.ask) + float(atm_straddle.put_contract.ask)
            }
    
    return {
        "market_conditions": market_conditions,
        "strategy": strategy,
        "underlying_price": current_price,
        "expiration_date": target_exp.strftime("%Y-%m-%d"),
        "days_to_expiration": (target_exp - now).days
    }

def analyze_options(ticker: str, options_data: dict, risk_tolerance: str = "medium") -> dict:
    """
    Analyze options data and recommend strategies
    
    Args:
        ticker: Stock ticker symbol
        options_data: Options data in dictionary format
        risk_tolerance: Risk tolerance level (low, medium, high)
        
    Returns:
        Dictionary with analysis results
    """
    logger.info(f"Analyzing options for {ticker} with {risk_tolerance} risk tolerance")
    
    try:
        # Use Gemini for options analysis if available
        try:
            from src.llm.models import analyze_options_with_gemini
            return analyze_options_with_gemini(ticker, options_data, risk_tolerance)
        except ImportError:
            logger.warning("Gemini analysis not available, using basic options analysis")
            
            # Fallback to basic analysis
            return {
                "market_conditions": {
                    "put_call_ratio": options_data.get("put_call_ratio", 1.0),
                    "implied_volatility_skew": options_data.get("implied_volatility_skew", 0),
                    "sentiment": options_data.get("sentiment", "neutral"),
                    "market_condition": options_data.get("market_condition", "normal")
                },
                "recommended_strategy": {
                    "name": "Long Stock",
                    "description": "Buy and hold the underlying stock",
                    "legs": [],
                    "max_profit": "Unlimited",
                    "max_loss": "Current stock price"
                },
                "overall_sentiment": "neutral",
                "confidence": 0.5,
                "reasoning": "Basic analysis without LLM capabilities"
            }
    except Exception as e:
        logger.error(f"Error analyzing options: {str(e)}")
        return {
            "error": f"Error analyzing options: {str(e)}",
            "overall_sentiment": "neutral",
            "confidence": 0,
            "reasoning": "Error in analysis"
        }

def prepare_options_data(market_data: dict) -> dict:
    """
    Prepare options data for analysis
    
    Args:
        market_data: Market data from API
        
    Returns:
        Dictionary with prepared options data
    """
    logger.info("Preparing options data for analysis")
    
    try:
        # Extract option chain from market data
        option_chain = market_data.get("raw_data", {}).get("optionChain", {})
        result = option_chain.get("result", [])
        
        if not result:
            logger.error("No result data in API response")
            return {
                "error": "No options data available from API"
            }
        
        # Extract quote data
        quote_data = result[0].get("quote", {})
        current_price = quote_data.get("regularMarketPrice", 0)
        
        # Process options data
        option_chain_data = result[0].get("options", [])
        
        if not option_chain_data:
            logger.error("No options data in API response")
            return {
                "error": "No options data available"
            }
        
        # Calculate put-call ratio
        call_volume = 0
        put_volume = 0
        
        for option_date in option_chain_data:
            straddles = option_date.get("straddles", [])
            
            for straddle in straddles:
                call = straddle.get("call", {})
                put = straddle.get("put", {})
                
                call_volume += call.get("volume", 0) or 0
                put_volume += put.get("volume", 0) or 0
        
        put_call_ratio = put_volume / call_volume if call_volume > 0 else 1.0
        
        # Determine sentiment based on put-call ratio
        sentiment = "neutral"
        if put_call_ratio > 1.2:
            sentiment = "bearish"
        elif put_call_ratio < 0.8:
            sentiment = "bullish"
        
        return {
            "current_price": current_price,
            "put_call_ratio": put_call_ratio,
            "sentiment": sentiment,
            "option_chain": option_chain_data,
            "quote_data": quote_data
        }
        
    except Exception as e:
        logger.error(f"Error preparing options data: {str(e)}")
        return {
            "error": f"Error preparing options data: {str(e)}"
        } 