import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
import subprocess
import logging
import json
import http.client
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
import google.generativeai as genai
import google.generativeai.types as types
import plotly.graph_objects as go
import plotly.express as px
from decimal import Decimal
from typing import Optional, Dict

from src.data.connectors.yahoo_finance import YahooFinanceConnector
from src.data.models import MarketQuote, OptionChain
from src.llm.memory_enhanced_analysis import MemoryEnhancedAnalysis
from src.data.memory import AnalysisMemory
# Import the new options analyzer functions
from src.analysis.options_analyzer import run_options_analysis # Only import the wrapper
from src.analysis.technical_analyzer import run_technical_analysis
# Import the new enhanced analyzer function
from src.analysis.enhanced_analyzer import run_enhanced_analysis
# Import the new memory analyzer function
from src.analysis.memory_analyzer import run_memory_analysis
# Import the display functions from the new UI module
from src.streamlit_app.ui_components import (
    display_market_overview,
    display_llm_options_analysis,
    display_enhanced_analysis,
    display_memory_enhanced_analysis,
    create_technical_chart,
    display_technical_analysis,
    display_price_targets
)

# Function analyze_technicals_with_llm and its helpers removed as they were moved to src/analysis/technical_analyzer.py

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check if plotly is installed, if not, install it
try:
    import plotly.graph_objects as go
    import plotly.express as px
    logger.info("Plotly is already installed")
except ImportError:
    logger.info("Plotly not found, attempting to install...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "plotly==5.18.0"])
        logger.info("Plotly installed successfully")
        import plotly.graph_objects as go
        import plotly.express as px
    except Exception as e:
        logger.error(f"Failed to install plotly: {str(e)}")
        st.error(f"Failed to install required package 'plotly': {str(e)}")
        st.info("Please contact the administrator to install the required packages.")
        st.stop()

# Initialize session state for storing analysis results and other data
if 'market_data' not in st.session_state:
    st.session_state.market_data = {}
if 'options_data' not in st.session_state:
    st.session_state.options_data = {}
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = {}
if 'enhanced_analysis_result' not in st.session_state:
    st.session_state.enhanced_analysis_result = {}
if 'memory_analysis_result' not in st.session_state:
    st.session_state.memory_analysis_result = {}
if 'historical_analyses' not in st.session_state:
    st.session_state.historical_analyses = []
if 'current_ticker' not in st.session_state:
    st.session_state.current_ticker = ""
if 'analysis_completed' not in st.session_state:
    st.session_state.analysis_completed = False
if 'last_analysis_time' not in st.session_state:
    st.session_state.last_analysis_time = None

# Load environment variables from multiple sources
load_dotenv()  # First try loading from .env file

# Log the path of the .env file found
dotenv_path = find_dotenv()
logger.info(f".env file found at: {dotenv_path}")

# Then try loading from Streamlit secrets if available
if hasattr(st, 'secrets') and 'env' in st.secrets:
    # Update environment with Streamlit secrets
    for key, value in st.secrets['env'].items():
        os.environ[key] = value
        logger.info(f"Loaded environment variable from Streamlit secrets: {key}")
elif hasattr(st, 'secrets'):
    # If secrets exist but not in 'env' section, check for direct keys
    for key in st.secrets:
        if key not in os.environ:
            os.environ[key] = st.secrets[key]
            logger.info(f"Loaded environment variable from Streamlit secrets: {key}")

# Check for required environment variables
required_vars = ['OPENAI_API_KEY', 'GOOGLE_API_KEY', 'RAPIDAPI_KEY'] # Ensure RAPIDAPI_KEY is checked
missing_vars = [var for var in required_vars if not os.environ.get(var)]
if missing_vars:
    logger.warning(f"Missing required environment variables: {', '.join(missing_vars)}")
    st.error(f"Missing required environment variables: {', '.join(missing_vars)}")

# Initialize Google Generative AI with API key
try:
    gemini_api_key = os.environ.get('GOOGLE_API_KEY')
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)
        logger.info("Successfully configured Google Generative AI")
    else:
        logger.warning("GOOGLE_API_KEY not found, Google Gemini features may be unavailable.")
except Exception as e:
    logger.error(f"Failed to configure Google Generative AI: {str(e)}")
    st.error(f"Failed to configure Google Generative AI: {str(e)}")

# Initialize memory analyzer in session state
if 'memory_analyzer' not in st.session_state:
    try:
        st.session_state.memory_analyzer = MemoryEnhancedAnalysis()
        logger.info("Memory analyzer initialized in session state")
    except Exception as e:
        logger.error(f"Failed to initialize memory analyzer: {str(e)}")
        st.error(f"Failed to initialize memory analyzer: {str(e)}")

def generate_price_targets(
    ticker: str, 
    connector: YahooFinanceConnector, 
    market_quote: Optional[MarketQuote] = None, 
    options_data: Optional[OptionChain] = None, 
    technical_analysis: Optional[Dict] = None
) -> Dict:
    """
    Generate price targets using a hybrid approach: LLM analysis combined with
    quantitative methods (technical levels, options implied moves, volatility).
    Refactored to use connector and data objects.
    """
    logger.info(f"Generating price targets for {ticker}")
    
    # First try to generate price targets with specialized LLM using time series data
    try:
        llm_price_targets = analyze_price_targets_with_llm(ticker, market_quote, options_data, technical_analysis)
        
        if llm_price_targets and not llm_price_targets.get("error"):
            logger.info("Successfully generated price targets with specialized LLM using time series data")
            return llm_price_targets
        elif llm_price_targets:
            logger.warning(f"LLM price target analysis failed: {llm_price_targets.get('error')}")
            # Continue with traditional methods as fallback
        else:
            logger.warning("LLM price target analysis returned None.")

    except Exception as e:
        logger.error(f"Error in LLM price target analysis: {str(e)}", exc_info=True)
        # Continue with traditional methods as fallback
    
    # Initialize results structure for traditional methods
    price_targets = {
        "ticker": ticker,
        "current_price": 0,
        "targets": {
            "short_term": {},
            "medium_term": {},
            "long_term": {}
        },
        "methodologies": [],
        "error": None # Add error field
    }
    
    # Get current price
    current_price = 0
    try:
        if market_quote and isinstance(market_quote, MarketQuote) and market_quote.regular_market_price is not None:
            current_price = float(market_quote.regular_market_price)
        elif options_data and isinstance(options_data, OptionChain) and options_data.quote and options_data.quote.regular_market_price is not None:
            current_price = float(options_data.quote.regular_market_price)
        
        if current_price <= 0:
             logger.warning(f"Could not determine a valid current price for {ticker}. Fetching quote again.")
             quote_info = connector.get_quote(ticker)
             current_price = float(quote_info.get("regularMarketPrice", 0))
             if current_price <= 0:
                  logger.error(f"Still could not get a valid current price for {ticker}")
                  price_targets["error"] = "Could not determine current price."
                  return price_targets # Cannot proceed without price
        
             price_targets["current_price"] = current_price
        logger.info(f"Using current price: {current_price} for {ticker}")

    except Exception as e:
        logger.error(f"Error extracting current price: {str(e)}", exc_info=True)
        price_targets["error"] = f"Error getting current price: {e}"
        return price_targets
    
    # If we have technical analysis data, use it for targets
    if technical_analysis and "price_targets" in technical_analysis:
        try:
            tech_targets = technical_analysis.get("price_targets", {})
            
            # Short term targets
            short_term = tech_targets.get("short_term", {})
            if short_term and isinstance(short_term, dict):
                price_targets["targets"]["short_term"]["technical"] = {
                    "bullish": short_term.get("bullish_target", 0),
                    "bearish": short_term.get("bearish_target", 0),
                    "timeframe": short_term.get("timeframe", "1-2 weeks"),
                    "confidence": short_term.get("confidence", 0)
                }
            
            # Medium term targets
            medium_term = tech_targets.get("medium_term", {})
            if medium_term and isinstance(medium_term, dict):
                price_targets["targets"]["medium_term"]["technical"] = {
                    "bullish": medium_term.get("bullish_target", 0),
                    "bearish": medium_term.get("bearish_target", 0),
                    "timeframe": medium_term.get("timeframe", "1-3 months"),
                    "confidence": medium_term.get("confidence", 0)
                }
            
            price_targets["methodologies"].append("technical_analysis")
            logger.info("Added technical analysis-based price targets")
        except Exception as e:
            logger.error(f"Error processing technical analysis price targets: {str(e)}", exc_info=True)
    
    # Try to get additional support/resistance from time series data
    try:
        # Get daily time series - assuming connector is already initialized
        daily_data = connector.get_time_series(ticker, "daily")
        
        # Analyze time series data
        if daily_data:
            ts_analysis = analyze_time_series_data(daily_data, current_price)
            
            # Add support/resistance from time series analysis
            if ts_analysis and (ts_analysis.get("support_levels") or ts_analysis.get("resistance_levels")):
                # Add to short term targets
                if "technical" not in price_targets["targets"]["short_term"]:
                    price_targets["targets"]["short_term"]["time_series"] = {
                        "bullish": max(ts_analysis["resistance_levels"]) if ts_analysis["resistance_levels"] else current_price * 1.05,
                        "bearish": min(ts_analysis["support_levels"]) if ts_analysis["support_levels"] else current_price * 0.95,
                        "timeframe": "1-30 days",
                        "confidence": 65
                    }
                
                # Also use for medium term with wider range
                if "technical" not in price_targets["targets"]["medium_term"]:
                    # For medium term, extend the range by 50%
                    bullish_target = max(ts_analysis["resistance_levels"]) if ts_analysis["resistance_levels"] else current_price * 1.05
                    bearish_target = min(ts_analysis["support_levels"]) if ts_analysis["support_levels"] else current_price * 0.95
                    
                    # Extend range
                    bullish_extension = (bullish_target - current_price) * 0.5
                    bearish_extension = (current_price - bearish_target) * 0.5
                    
                    price_targets["targets"]["medium_term"]["time_series"] = {
                        "bullish": bullish_target + bullish_extension,
                        "bearish": bearish_target - bearish_extension,
                        "timeframe": "1-3 months",
                        "confidence": 55
                    }
                
                price_targets["methodologies"].append("time_series_analysis")
                logger.info("Added time series-based price targets")
            elif ts_analysis:
                 logger.warning(f"Time series analysis for {ticker} did not yield S/R levels.")
        else:
             logger.warning(f"Could not fetch daily time series data for {ticker} using connector.")

    except Exception as e:
        logger.error(f"Error adding time series-based targets: {str(e)}", exc_info=True)
    
    # If we have options data, calculate implied price ranges
    if options_data and isinstance(options_data, OptionChain) and options_data.options:
        try:
            expirations = options_data.options # List of OptionChainOptions
            
            # Group by timeframe
            short_term_exp = []
            medium_term_exp = []
            long_term_exp = []
            now = datetime.now()
            
            for exp_option in expirations:
                days_to_exp = (exp_option.expiration_date - now).days
                if 0 < days_to_exp <= 30:
                    short_term_exp.append(exp_option)
                elif 30 < days_to_exp <= 90:
                    medium_term_exp.append(exp_option)
                elif days_to_exp > 90:
                    long_term_exp.append(exp_option)
            
            # Process short-term expirations
            if short_term_exp:
                nearest_exp = short_term_exp[0]
                straddles_list = nearest_exp.straddles # List of OptionStraddle
                
                if not straddles_list:
                     logger.warning(f"No straddles found for nearest expiration ({nearest_exp.expiration_date}) for {ticker}")
                else:
                    # Find ATM straddle
                    atm_straddle = min(straddles_list, key=lambda s: abs(float(s.strike) - current_price))
                    
                    # Calculate ATM straddle price
                    call_price = float(atm_straddle.call_contract.get_mid_price()) if atm_straddle.call_contract else 0
                    put_price = float(atm_straddle.put_contract.get_mid_price()) if atm_straddle.put_contract else 0
                    straddle_price = call_price + put_price
                    
                    if straddle_price > 0:
                        # Calculate expected move
                        implied_move_pct = (straddle_price / current_price) * 100
                        bullish_target = current_price * (1 + (implied_move_pct/100))
                        bearish_target = current_price * (1 - (implied_move_pct/100))
                        
                        price_targets["targets"]["short_term"]["options_implied"] = {
                            "bullish": round(bullish_target, 2),
                            "bearish": round(bearish_target, 2),
                            "timeframe": f"{(nearest_exp.expiration_date - now).days} days",
                            "implied_move_pct": round(implied_move_pct, 2),
                            "confidence": 70  # Options market implied confidence
                        }
                    else:
                         logger.warning(f"Could not calculate valid straddle price for {ticker} short-term options.")
                
                # Process medium-term if available
                if medium_term_exp:
                    medium_exp = medium_term_exp[0]
                    medium_straddles = medium_exp.straddles
                    
                    if not medium_straddles:
                        logger.warning(f"No straddles found for medium expiration ({medium_exp.expiration_date}) for {ticker}")
                    else:
                        medium_atm = min(medium_straddles, key=lambda s: abs(float(s.strike) - current_price))
                        medium_call_price = float(medium_atm.call_contract.get_mid_price()) if medium_atm.call_contract else 0
                        medium_put_price = float(medium_atm.put_contract.get_mid_price()) if medium_atm.put_contract else 0
                        medium_straddle_price = medium_call_price + medium_put_price
                        
                        if medium_straddle_price > 0:
                            medium_move_pct = (medium_straddle_price / current_price) * 100
                            medium_bullish = current_price * (1 + (medium_move_pct/100))
                            medium_bearish = current_price * (1 - (medium_move_pct/100))
                            
                            price_targets["targets"]["medium_term"]["options_implied"] = {
                                "bullish": round(medium_bullish, 2),
                                "bearish": round(medium_bearish, 2),
                                "timeframe": f"{(medium_exp.expiration_date - now).days} days",
                                "implied_move_pct": round(medium_move_pct, 2),
                                "confidence": 60
                            }
                        else:
                             logger.warning(f"Could not calculate valid straddle price for {ticker} medium-term options.")
            
            if "options_implied" in price_targets["targets"]["short_term"] or \
               "options_implied" in price_targets["targets"]["medium_term"]:
                price_targets["methodologies"].append("options_implied")
                logger.info("Added options-implied price targets")
        except Exception as e:
            logger.error(f"Error calculating options-implied price targets: {str(e)}", exc_info=True)
    
    # Generate volatility-based price targets using historical data (yfinance fallback)
    try:
        import yfinance as yf
        import numpy as np
        
        # Get historical data
        history = connector.get_historical_data(ticker, period="6mo") # Use connector
        
        if history is not None and not history.empty:
            # Calculate historical volatility (30-day)
            returns = np.log(history['Close'] / history['Close'].shift(1))
            vol_30d = returns.rolling(window=30).std() * np.sqrt(252)  # Annualized
            current_vol = vol_30d.iloc[-1] if len(vol_30d) > 30 and not pd.isna(vol_30d.iloc[-1]) else returns.std() * np.sqrt(252)
            
            if pd.isna(current_vol) or current_vol <= 0:
                 logger.warning(f"Could not calculate valid historical volatility for {ticker}")
            else:
                # Calculate volatility-based price ranges
                vol_30d_move = current_price * current_vol / np.sqrt(252/30)  # 30-day expected move
                vol_90d_move = current_price * current_vol / np.sqrt(252/90)  # 90-day expected move
                
                # Add volatility-based targets
                price_targets["targets"]["short_term"]["volatility_based"] = {
                    "bullish": round(current_price + vol_30d_move, 2),
                    "bearish": round(current_price - vol_30d_move, 2),
                    "timeframe": "30 days",
                    "confidence": 65,
                    "volatility": round(current_vol * 100, 2)
                }
                
                price_targets["targets"]["medium_term"]["volatility_based"] = {
                    "bullish": round(current_price + vol_90d_move, 2),
                    "bearish": round(current_price - vol_90d_move, 2),
                    "timeframe": "90 days",
                    "confidence": 55,
                    "volatility": round(current_vol * 100, 2)
                }
                
                price_targets["methodologies"].append("volatility_based")
                logger.info("Added volatility-based price targets")
        else:
             logger.warning(f"Could not fetch historical data via connector for volatility targets ({ticker}).")

    except ImportError:
         logger.error("yfinance or numpy not installed. Cannot calculate volatility targets.")
    except Exception as e:
        logger.error(f"Error calculating volatility-based price targets: {str(e)}", exc_info=True)
    
    # Calculate consensus targets by combining all available methodologies
    try:
        # Short-term consensus
        short_term_targets = []
        for method, data in price_targets["targets"]["short_term"].items():
            if isinstance(data, dict) and data.get("confidence", 0) > 0: # Ensure valid data and confidence
                short_term_targets.append({
                    "bullish": data.get("bullish", 0),
                    "bearish": data.get("bearish", 0),
                    "confidence": data.get("confidence", 0) / 100,  # Weight by confidence
                    "method": method
                })
        
        if short_term_targets:
            bullish_weighted_sum = sum(t["bullish"] * t["confidence"] for t in short_term_targets)
            bearish_weighted_sum = sum(t["bearish"] * t["confidence"] for t in short_term_targets)
            total_confidence = sum(t["confidence"] for t in short_term_targets)
            
            if total_confidence > 0:
                consensus_bullish = bullish_weighted_sum / total_confidence
                consensus_bearish = bearish_weighted_sum / total_confidence
                avg_confidence = (total_confidence / len(short_term_targets)) * 100 # Average confidence
                
                price_targets["targets"]["short_term"]["consensus"] = {
                    "bullish": round(consensus_bullish, 2),
                    "bearish": round(consensus_bearish, 2),
                    "timeframe": "1-30 days",
                    "confidence": round(avg_confidence)
                }
            else:
                 logger.warning(f"Total confidence for short-term consensus is zero for {ticker}.")
        else:
             logger.warning(f"No valid short-term targets found to calculate consensus for {ticker}.")
        
        # Medium-term consensus
        medium_term_targets = []
        for method, data in price_targets["targets"]["medium_term"].items():
             if isinstance(data, dict) and data.get("confidence", 0) > 0:
                medium_term_targets.append({
                    "bullish": data.get("bullish", 0),
                    "bearish": data.get("bearish", 0),
                    "confidence": data.get("confidence", 0) / 100,
                    "method": method
                })
        
        if medium_term_targets:
            bullish_weighted_sum = sum(t["bullish"] * t["confidence"] for t in medium_term_targets)
            bearish_weighted_sum = sum(t["bearish"] * t["confidence"] for t in medium_term_targets)
            total_confidence = sum(t["confidence"] for t in medium_term_targets)
            
            if total_confidence > 0:
                consensus_bullish = bullish_weighted_sum / total_confidence
                consensus_bearish = bearish_weighted_sum / total_confidence
                avg_confidence = (total_confidence / len(medium_term_targets)) * 100
                
                price_targets["targets"]["medium_term"]["consensus"] = {
                    "bullish": round(consensus_bullish, 2),
                    "bearish": round(consensus_bearish, 2),
                    "timeframe": "1-3 months",
                    "confidence": round(avg_confidence)
                }
            else:
                 logger.warning(f"Total confidence for medium-term consensus is zero for {ticker}.")
        else:
             logger.warning(f"No valid medium-term targets found to calculate consensus for {ticker}.")
        
        logger.info("Calculated consensus price targets")
    except Exception as e:
        logger.error(f"Error calculating consensus price targets: {str(e)}", exc_info=True)
    
    # Convert to the format similar to LLM output for consistent display
    # This conversion logic remains as a fallback if the specialized LLM fails
    try:
        short_consensus = price_targets["targets"]["short_term"].get("consensus")
        medium_consensus = price_targets["targets"]["medium_term"].get("consensus")
        
        # Only proceed if we have at least one consensus target
        if short_consensus or medium_consensus:
            # Use available consensus, prioritize short-term if both exist
            primary_consensus = short_consensus if short_consensus else medium_consensus
            primary_timeframe = "short_term" if short_consensus else "medium_term"
            
            # Calculate expected target and direction from the primary consensus
            expected_target = (primary_consensus.get("bullish", 0) + primary_consensus.get("bearish", 0)) / 2
            
            if expected_target > current_price * 1.02:
                direction = "bullish"
            elif expected_target < current_price * 0.98:
                direction = "bearish"
            else:
                direction = "neutral"
            
            potential_return = ((expected_target - current_price) / current_price) * 100
            
            # Create LLM-like format
            llm_format = {
                "ticker": ticker,
                "current_price": current_price,
                "price_targets": { # Include both short and medium if they exist
                    "short_term": price_targets["targets"]["short_term"].get("consensus", {}),
                    "medium_term": price_targets["targets"]["medium_term"].get("consensus", {})
                },
                "primary_forecast": {
                    "target_price": round(expected_target, 2),
                    "direction": direction,
                    "timeframe": primary_consensus.get("timeframe", "N/A"),
                    "confidence": primary_consensus.get("confidence", 50), # Default confidence
                    "potential_return": round(potential_return, 2)
                },
                "analysis_methodology": {
                    "technical_factors": "technical_analysis" in price_targets["methodologies"],
                    "options_implied": "options_implied" in price_targets["methodologies"],
                    "volatility_based": "volatility_based" in price_targets["methodologies"],
                    "fundamental_consideration": False, # Not included in this calculation
                    "time_series_analysis": "time_series_analysis" in price_targets["methodologies"]
                },
                "key_drivers": price_targets["methodologies"], # List the methods used
                "market_context": "Analysis based on consensus of statistical models and technical indicators",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Clean up empty targets in llm_format
            if not llm_format["price_targets"]["short_term"]:
                del llm_format["price_targets"]["short_term"]
            if not llm_format["price_targets"]["medium_term"]:
                del llm_format["price_targets"]["medium_term"]

            return llm_format
        else:
            # If no consensus could be formed, return the raw target dictionary with an error message
            price_targets["error"] = "Could not form a consensus price target."
            return price_targets

    except Exception as e:
        logger.error(f"Error converting traditional targets to LLM format: {str(e)}", exc_info=True)
        price_targets["error"] = f"Failed to format targets: {e}"
        return price_targets # Return the dictionary with collected data and error

def analyze_time_series_data(time_series_data, current_price):
    """Analyze time series data to identify support and resistance levels"""
    logger.info("Analyzing time series data for support/resistance")
    
    # Check if time_series_data is valid
    if not time_series_data or "Time Series (Daily)" not in time_series_data:
        logger.warning("Invalid or missing time series data")
        return {"support_levels": [], "resistance_levels": [], "error": "Missing daily time series data"}
    
    # Extract daily data
    daily_data = time_series_data["Time Series (Daily)"]
    if not daily_data:
        logger.warning("Time series daily data is empty")
        return {"support_levels": [], "resistance_levels": [], "error": "Empty daily time series data"}
        
        # Convert to DataFrame
    try:
        df = pd.DataFrame.from_dict(daily_data, orient="index")
        df.index = pd.to_datetime(df.index)
        df = df.astype(float)
        df = df.sort_index()
        df = df.rename(columns={
            "1. open": "Open",
            "2. high": "High",
            "3. low": "Low",
            "4. close": "Close",
            "5. volume": "Volume"
        })
    except Exception as e:
        logger.error(f"Error converting time series data to DataFrame: {str(e)}")
        return {"support_levels": [], "resistance_levels": [], "error": f"Failed to process time series data: {e}"}
    
    # Calculate Pivot Points (Simple method)
    try:
        last_day = df.iloc[-1]
        pivot = (last_day["High"] + last_day["Low"] + last_day["Close"]) / 3
        r1 = (2 * pivot) - last_day["Low"]
        s1 = (2 * pivot) - last_day["High"]
        r2 = pivot + (last_day["High"] - last_day["Low"])
        s2 = pivot - (last_day["High"] - last_day["Low"])
        r3 = last_day["High"] + 2 * (pivot - last_day["Low"])
        s3 = last_day["Low"] - 2 * (last_day["High"] - pivot)
        
        # Aggregate support and resistance levels
        support = sorted([s1, s2, s3], reverse=True)
        resistance = sorted([r1, r2, r3])
        
        # Filter levels relative to current price
        support_levels = [s for s in support if s < current_price]
        resistance_levels = [r for r in resistance if r > current_price]
        
        # Add 52-week high/low if available in the data (using df max/min)
        if not df.empty:
             year_high = df["High"].max()
             year_low = df["Low"].min()
             if year_high > current_price and year_high not in resistance_levels:
                 resistance_levels.append(year_high)
             if year_low < current_price and year_low not in support_levels:
                 support_levels.append(year_low)
        
        # Ensure sorted and unique levels
        support_levels = sorted(list(set(support_levels)), reverse=True)
        resistance_levels = sorted(list(set(resistance_levels)))
        
        logger.info(f"Identified S/R levels: Support={support_levels}, Resistance={resistance_levels}")
        
        return {
            "support_levels": support_levels[:3], # Limit to 3 levels
            "resistance_levels": resistance_levels[:3],
            "error": None
        }
    except Exception as e:
        logger.error(f"Error calculating pivot points or S/R levels: {str(e)}")
        return {"support_levels": [], "resistance_levels": [], "error": f"Failed to calculate S/R levels: {e}"}

def analyze_price_targets_with_llm(ticker, market_data, options_data=None, technical_analysis=None):
    """
    Use a specialized LLM prompt to generate price targets based on various data points.
    
    Args:
        ticker (str): Stock ticker symbol.
        market_data (dict): Current market quote data.
        options_data (dict, optional): Options chain data.
        technical_analysis (dict, optional): Results from technical analysis.
        
    Returns:
        dict: Price target analysis from the LLM, or dictionary with error.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("Gemini API key not found for price target analysis")
        return {"error": "Gemini API key not found"}
    
    # --- Prepare Data for LLM --- 
        prompt_data = {
            "ticker": ticker,
        "current_market_data": market_data if market_data else "Not Available",
        "options_summary": "Not Available",
        "technical_summary": "Not Available"
    }
    
    # Summarize Options Data (if available)
    if options_data and isinstance(options_data, dict) and "options_expirations" in options_data:
        try:
            exp_count = len(options_data.get("options_expirations", []))
            total_strikes = 0
            total_volume = 0
            total_oi = 0
            
            for exp in options_data.get("options_expirations", []):
                for opt in exp.get("options", []):
                    total_strikes += 1
                    if opt.get("call"):
                        total_volume += opt["call"].get("volume", 0)
                        total_oi += opt["call"].get("open_interest", 0)
                    if opt.get("put"):
                        total_volume += opt["put"].get("volume", 0)
                        total_oi += opt["put"].get("open_interest", 0)
            
            prompt_data["options_summary"] = {
                "expiration_count": exp_count,
                "total_strikes_analyzed": total_strikes,
                "total_volume": total_volume,
                "total_open_interest": total_oi,
                # Add implied move if available from options_implied calculation
                # "short_term_implied_move_pct": options_data.get(...)
            }
        except Exception as e:
            logger.warning(f"Could not summarize options data for LLM prompt: {e}")
            prompt_data["options_summary"] = f"Error summarizing options: {e}"

    # Summarize Technical Analysis (if available)
    if technical_analysis and isinstance(technical_analysis, dict) and "summary" in technical_analysis:
         try:
            prompt_data["technical_summary"] = {
                "overall_signal": technical_analysis.get("summary", {}).get("overall_signal", "N/A"),
                "confidence": technical_analysis.get("summary", {}).get("confidence", "N/A"),
                "key_support": technical_analysis.get("support_resistance", {}).get("support_levels", []), 
                "key_resistance": technical_analysis.get("support_resistance", {}).get("resistance_levels", [])
            }
         except Exception as e:
            logger.warning(f"Could not summarize technical analysis for LLM prompt: {e}")
            prompt_data["technical_summary"] = f"Error summarizing technicals: {e}"
    
    # --- Construct the Prompt --- 
    prompt = f"""
You are an expert financial analyst specializing in price target forecasting. 
Analyze the provided data for {ticker} and generate short-term (1-30 days) and medium-term (1-3 months) price targets. 

Provide your analysis in a structured JSON format.

Input Data:
```json
{json.dumps(prompt_data, indent=2)}
```

Instructions:
1.  **Analyze Key Drivers:** Identify the primary factors (technical, options sentiment, volatility, market context) influencing the potential price movement based ONLY on the provided data.
2.  **Formulate Price Targets:** For both short-term and medium-term horizons, provide:
    *   `bullish_target`: The plausible upper price level.
    *   `bearish_target`: The plausible lower price level.
    *   `expected_target`: Your most likely price outcome within the timeframe.
    *   `confidence`: Your confidence level (0-100) in the expected target.
    *   `key_levels`: A dictionary containing critical `support`, `resistance`, and `invalidation` levels for the forecast.
3.  **Primary Forecast:** Synthesize your analysis into a single primary forecast including `target_price`, `direction` (bullish/bearish/neutral), `timeframe`, `confidence`, and `potential_return` (%).
4.  **Methodology:** Briefly outline the factors considered (`technical_factors`, `options_implied`, `volatility_based`, `fundamental_consideration` [set to false if no fundamental data provided], `time_series_analysis`).
5.  **Market Context:** Add a brief sentence about the broader context if discernible from the data.

Output JSON Structure:
```json
{{
  "ticker": "{ticker}",
  "current_price": {prompt_data.get('current_market_data', {}).get('regularMarketPrice', 0)}, // Use current price from market_data
  "price_targets": {{
    "short_term": {{
              "timeframe": "1-30 days",
      "bullish_target": float,
      "bearish_target": float,
      "expected_target": float,
      "confidence": int, // 0-100
      "key_levels": {{
        "resistance": [float, ...],
        "support": [float, ...],
        "invalidation": float // Price level that invalidates the forecast
      }}
    }},
    "medium_term": {{
              "timeframe": "1-3 months",
      "bullish_target": float,
      "bearish_target": float,
      "expected_target": float,
      "confidence": int, // 0-100
      "key_levels": {{
        "resistance": [float, ...],
        "support": [float, ...],
        "invalidation": float
      }}
    }}
  }},
  "primary_forecast": {{
    "target_price": float,
    "direction": "bullish|bearish|neutral",
    "timeframe": string, // e.g., "1-60 days"
    "confidence": int, // 0-100
    "potential_return": float // Percentage
  }},
  "analysis_methodology": {{
    "technical_factors": [string, ...], // e.g., ["MA Crossover", "RSI Divergence"]
    "options_implied": boolean,
    "volatility_based": boolean,
    "fundamental_consideration": boolean, // Likely false based on input
    "time_series_analysis": boolean
  }},
  "key_drivers": [string, ...], // List the main factors driving the forecast
  "market_context": string, // Brief overall context
  "timestamp": "YYYY-MM-DD HH:MM:SS"
}}
```
"""

    # --- Call Gemini API --- 
    try:
        # Ensure Gemini is configured
        if not genai.config.api_key:
             genai.configure(api_key=api_key)
             logger.info("Configured Gemini API key for price target analysis.")

        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=types.GenerationConfig(
                temperature=0.4, # Allow slightly more variability for forecasting
                top_p=0.95,
                top_k=64,
                max_output_tokens=4096, # Reduced max tokens slightly
                response_mime_type="application/json",
            )
        )
        
        logger.info(f"Sending price target generation prompt to Gemini for {ticker}")
        response = model.generate_content(prompt)
        
        # Add timestamp to the response
        analysis_result = json.loads(response.text)
        analysis_result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        logger.info(f"Received price target analysis from Gemini for {ticker}")
        return analysis_result
            
    except json.JSONDecodeError:
        logger.error(f"Failed to parse Gemini JSON response for {ticker} price targets: {response.text}")
        return {"error": "Failed to parse LLM response", "raw_response": response.text}
    except Exception as e:
        logger.error(f"Error during Gemini API call for {ticker} price targets: {e}", exc_info=True)
        return {"error": f"LLM API call failed: {e}"}

def main():
    # Set page config
    st.set_page_config(page_title="AI Hedge Fund Analysis", layout="wide")
    st.title("📈 AI Hedge Fund Analysis Tool")

    # Initialize connector in session state if not present
    if 'connector' not in st.session_state:
        try:
            # Force connector to use yfinance instead of RapidAPI for reliability
            st.session_state.connector = YahooFinanceConnector(use_rapidapi=False)
            logger.info("YahooFinanceConnector initialized in session state (using yfinance).")
        except Exception as e:
            logger.error(f"Failed to initialize YahooFinanceConnector: {e}")
            st.error(f"Failed to initialize data connector: {e}. Please check API keys and network.")
            st.stop() # Stop execution if connector fails

    connector = st.session_state.connector

    # Sidebar for inputs
    st.sidebar.header("Analysis Inputs")
    
    # Use session state for ticker input persistence
    if 'ticker_input' not in st.session_state:
        st.session_state.ticker_input = "AAPL" # Default ticker
    
    ticker = st.sidebar.text_input("Enter Ticker Symbol", value=st.session_state.ticker_input).upper()
    st.session_state.ticker_input = ticker # Update session state on change

    # Use session state for analysis type selection
    analysis_options = {
        "LLM Options Analysis": "options",
        "LLM Technical Analysis": "technical",
        "Enhanced Comprehensive Analysis": "enhanced",
        "Memory-Enhanced Analysis": "memory",
        "Price Target Generation": "price_target"
    }
    if 'selected_analysis_label' not in st.session_state:
        st.session_state.selected_analysis_label = "LLM Options Analysis"
         
    selected_analysis_label = st.sidebar.selectbox(
         "Select Analysis Type", 
         list(analysis_options.keys()), 
        index=list(analysis_options.keys()).index(st.session_state.selected_analysis_label) # Set default index from session state
    )
    analysis_type = analysis_options[selected_analysis_label]
    st.session_state.selected_analysis_label = selected_analysis_label # Update session state

    # Conditional inputs based on analysis type
    risk_tolerance = "medium" # Default
    if analysis_type == "options":
        if 'risk_tolerance' not in st.session_state:
            st.session_state.risk_tolerance = "Medium"
            risk_tolerance = st.sidebar.select_slider(
            "Select Risk Tolerance (for Options Analysis)", 
            options=["Low", "Medium", "High"],
            value=st.session_state.risk_tolerance
        ).lower()
        st.session_state.risk_tolerance = risk_tolerance.capitalize() # Store capitalized version
        
    timeframe = "1Y" # Default
    if analysis_type == "technical":
        timeframe_options = ["1D", "1W", "1M", "3M", "6M", "1Y", "5Y", "MAX"]
        if 'timeframe' not in st.session_state:
             st.session_state.timeframe = "1Y"
             timeframe = st.sidebar.selectbox(
            "Select Timeframe (for Technical Analysis)", 
            timeframe_options,
            index=timeframe_options.index(st.session_state.timeframe) # Set default index
        )
        st.session_state.timeframe = timeframe # Update session state

    # Analysis button
    if st.sidebar.button("Run Analysis"):
        if not ticker:
            st.sidebar.error("Please enter a ticker symbol")
        else:
            st.session_state.current_ticker = ticker
            st.session_state.analysis_completed = False # Reset flag
            st.session_state.analysis_result = {} # Clear previous results
            st.session_state.market_data = {} # Clear market data
            st.session_state.options_data = {} # Clear options data
            
            # Use spinner for feedback during analysis
            with st.spinner(f"Running {selected_analysis_label} for {ticker}..."):
                try:
                    # Fetch base data required by most analyses
                    logger.info(f"Fetching market quote for {ticker}")
                    market_quote_dict = connector.get_market_quotes(ticker)
                    market_quote = market_quote_dict.get(ticker) if market_quote_dict else None
                    st.session_state.market_data[ticker] = market_quote

                    if market_quote is None or (isinstance(market_quote, dict) and "error" in market_quote):
                        st.error(f"Failed to fetch market quote for {ticker}. Cannot proceed.")
                        st.stop()

                    # Fetch options data if needed (Options, Price Target analyses)
                    option_chain = None
                    if analysis_type in ["options", "price_target"]:
                        logger.info(f"Fetching option chain for {ticker}")
                        option_chain = connector.get_option_chain(ticker)
                        st.session_state.options_data[ticker] = option_chain
                        if option_chain is None or (isinstance(option_chain, dict) and "error" in option_chain):
                            st.warning(f"Failed to fetch option chain for {ticker}. Analysis might be limited.")
                            option_chain = None # Ensure it's None if fetch failed
                            
                    # Fetch historical data IF technical analysis is selected
                    if analysis_type == "technical":
                        logger.info(f"Fetching historical data for {ticker} based on timeframe {timeframe}")
                        # Map timeframe to period/interval for fetching
                        period_map = {
                            "1D": ("5d", "15m"), "1W": ("1mo", "1h"), "1M": ("6mo", "1d"),
                            "3M": ("1y", "1d"), "6M": ("2y", "1d"), "1Y": ("5y", "1d"),
                            "5Y": ("10y", "1wk"), "MAX": ("max", "1mo")
                        }
                        period, interval = period_map.get(timeframe, ("1y", "1d"))
                        try:
                            historical_data_for_tech = connector.get_historical_data(ticker, period=period, interval=interval)
                            if historical_data_for_tech is None or historical_data_for_tech.empty:
                                 st.error(f"Failed to fetch historical data for {ticker}. Technical analysis cannot proceed.")
                                 st.stop()
                            else:
                                 logger.info(f"Successfully fetched historical data for technical analysis: {len(historical_data_for_tech)} rows")
                        except Exception as fetch_err:
                             st.error(f"Error fetching historical data for {ticker}: {fetch_err}")
                             logger.error(f"Error fetching historical data: {fetch_err}", exc_info=True)
                             st.stop()

                    # Execute selected analysis
                    analysis_start_time = datetime.now()
                    if analysis_type == "options":
                        st.session_state.analysis_result = run_options_analysis(ticker, option_chain, risk_tolerance)
                    elif analysis_type == "technical":
                        # Pass connector and optional historical analyses from memory
                        # Pass the fetched historical_data_for_tech
                        st.session_state.analysis_result = run_technical_analysis(
                            ticker,
                            timeframe,
                            connector,
                            historical_data=historical_data_for_tech, # Pass fetched data
                            historical_analyses=st.session_state.historical_analyses
                        )
                    elif analysis_type == "enhanced":
                        # Enhanced analysis needs a list of tickers
                        st.session_state.analysis_result = run_enhanced_analysis([ticker], analysis_type="comprehensive")
                    elif analysis_type == "memory":
                        # Memory analysis uses the instance from session state
                        st.session_state.analysis_result = run_memory_analysis(
                              ticker, 
                            connector,
                            st.session_state.memory_analyzer
                          )
                    elif analysis_type == "price_target":
                        # Price target needs market quote, optionally options and tech analysis
                        # We might run a quick technical analysis here if not available
                        tech_analysis_for_pt = st.session_state.analysis_result if st.session_state.analysis_result.get("timeframe") else None
                        st.session_state.analysis_result = generate_price_targets(
                            ticker, 
                            connector, 
                            market_quote,
                            option_chain,
                            tech_analysis_for_pt
                        )
                    else:
                        st.error(f"Analysis type '{analysis_type}' not implemented yet.")
                        st.stop()

                    analysis_end_time = datetime.now()
                    st.session_state.last_analysis_time = analysis_end_time
                    st.session_state.analysis_completed = True
                    logger.info(f"Analysis completed for {ticker} ({analysis_type}) in {(analysis_end_time - analysis_start_time).total_seconds():.2f}s")
                    st.success(f"{selected_analysis_label} for {ticker} completed!")

                except Exception as e:
                    logger.error(f"Error during analysis for {ticker}: {str(e)}", exc_info=True)
                    st.error(f"An error occurred during analysis: {str(e)}")
                    st.session_state.analysis_completed = False
                    st.stop()

    # --- Display Area --- 
    if st.session_state.current_ticker:
        ticker = st.session_state.current_ticker
        market_quote = st.session_state.market_data.get(ticker)
        analysis_result = st.session_state.analysis_result

        # Display Market Overview (always show if ticker is set)
        current_price = display_market_overview(market_quote, ticker)

        # Display analysis results if completed
        if st.session_state.analysis_completed and analysis_result:
            st.markdown("---") # Separator
            analysis_type = analysis_options[st.session_state.selected_analysis_label]

            if analysis_type == "options":
                display_llm_options_analysis(analysis_result, ticker)
            elif analysis_type == "technical":
                # Display chart first, then detailed analysis
                # Fetch the data again here OR pass it from the analysis step
                # Fetching again is inefficient. Let's pass it.
                # We need the historical_data_for_tech from the analysis step
                # This requires fetching it outside the analysis call or returning it.
                # Fetching outside (as implemented above) seems better.

                # Check if historical_data_for_tech was fetched successfully
                if 'historical_data_for_tech' in locals() and historical_data_for_tech is not None:
                    create_technical_chart(ticker, historical_data_for_tech, analysis_result)
                    display_technical_analysis(analysis_result)
                else:
                     # Attempt to fetch data here if it wasn't available before (less ideal fallback)
                     logger.warning("Historical data not available from main analysis step, attempting fallback fetch for chart.")
                     period_map = {
                         "1D": ("5d", "15m"), "1W": ("1mo", "1h"), "1M": ("6mo", "1d"),
                         "3M": ("1y", "1d"), "6M": ("2y", "1d"), "1Y": ("5y", "1d"),
                         "5Y": ("10y", "1wk"), "MAX": ("max", "1mo")
                     }
                     period, interval = period_map.get(timeframe, ("1y", "1d")) # Use timeframe from session
                     try:
                         fallback_data = connector.get_historical_data(ticker, period=period, interval=interval)
                         if fallback_data is not None and not fallback_data.empty:
                             create_technical_chart(ticker, fallback_data, analysis_result)
                             display_technical_analysis(analysis_result)
                         else:
                              st.error("Could not fetch historical data for chart.")
                              display_technical_analysis(analysis_result) # Display analysis anyway
                     except Exception as fallback_err:
                          st.error(f"Error fetching historical data for chart: {fallback_err}")
                          display_technical_analysis(analysis_result)

            elif analysis_type == "enhanced":
                display_enhanced_analysis(analysis_result)
            elif analysis_type == "memory":
                display_memory_enhanced_analysis(ticker, analysis_result, st.session_state.historical_analyses)
            elif analysis_type == "price_target":
                display_price_targets(analysis_result, ticker)
            else:
                st.warning(f"Display for analysis type '{analysis_type}' not implemented yet.")

            # Add a note about the last analysis time
            if st.session_state.last_analysis_time:
                st.sidebar.info(f"Last analysis: {st.session_state.last_analysis_time.strftime('%Y-%m-%d %H:%M:%S')}")
        elif st.session_state.analysis_completed and not analysis_result:
             st.warning("Analysis ran, but no results were generated. Check logs for details.")

    else:
        st.info("Enter a ticker symbol and select an analysis type to begin.")

if __name__ == "__main__":
    main() 