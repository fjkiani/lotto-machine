import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict

import google.generativeai as genai
import google.generativeai.types as types
from dotenv import load_dotenv

from src.data.models import OptionChain # Assuming OptionChain and related types are in models

# Set up logging
logger = logging.getLogger(__name__)
load_dotenv() # Load environment variables if needed for API keys


def prepare_gemini_input(option_chain: Optional[OptionChain], ticker: str) -> Dict:
    """Prepare option chain data for Gemini analysis using OptionChain object"""
    logger.info(f"Preparing Gemini input for {ticker} using OptionChain object")

    # Check if option_chain is valid
    if option_chain is None:
        logger.error("No OptionChain object provided")
        return {"error": "OptionChain object is None"}
    if isinstance(option_chain, dict) and "error" in option_chain:
         logger.error(f"Error in OptionChain object: {option_chain['error']}")
         return {"error": f"Error fetching option chain: {option_chain['error']}"}
    if not isinstance(option_chain, OptionChain):
         logger.error(f"Invalid data type passed to prepare_gemini_input: {type(option_chain)}")
         return {"error": f"Invalid data type for option chain: {type(option_chain)}"}


    # Extract quote data from OptionChain
    quote_data = option_chain.quote
    if quote_data is None:
        logger.error("No quote data in OptionChain object")
        # Fallback or error handling
        current_price = 0.0
    else:
         # Ensure current_price is float
        current_price = float(quote_data.regular_market_price) if quote_data.regular_market_price is not None else 0.0
        logger.info(f"Current price from OptionChain.quote: {current_price}")


    # Convert option chain to dictionary for Gemini
    option_chain_dict = {
        "underlying_symbol": ticker,
        "current_price": current_price,
        "expiration_dates": [],
        "options_expirations": []  # Will contain all expirations with their own options
    }

    # Process options data from OptionChain object
    option_chain_data = option_chain.options
    logger.info(f"Number of expirations in OptionChain: {len(option_chain_data)}")
    if not option_chain_data:
        logger.warning("No options data in OptionChain object")
        return option_chain_dict # Return dict with current price but no options

    # Loop through each expiration date (limited to first 3 for performance)
    for exp_idx, option_date in enumerate(option_chain_data[:3]):
        exp_date = option_date.expiration_date # Already a datetime object

        if not exp_date:
            continue

        exp_date_str = exp_date.strftime("%Y-%m-%d")
        option_chain_dict["expiration_dates"].append(exp_date_str)

        straddles = option_date.straddles # List of OptionStraddle objects
        if not straddles:
            logger.warning(f"No straddles data for expiration {exp_date_str}")
            continue

        # Get all strikes for this expiration
        strikes = sorted(list(set(s.strike for s in straddles if s.strike is not None)))

        if not strikes:
            logger.warning(f"No strike prices for expiration {exp_date_str}")
            continue
        
        # Convert strikes to float for comparison
        strikes_float = [float(s) for s in strikes]

        # Find ATM strike (closest float strike to float current_price)
        # Handle case where current_price is 0
        if current_price == 0.0:
             atm_strike = strikes_float[len(strikes_float)//2] # Pick middle strike if price is 0
        else:
             atm_strike = min(strikes_float, key=lambda x: abs(x - current_price))

        # Process options for this expiration
        expiration_data = {
            "expiration_date": exp_date_str,
            "days_to_expiration": (exp_date - datetime.now()).days,
            "options": []
        }

        # Include more strikes if this is the nearest expiration
        max_strikes = 20 if exp_idx > 0 else 40

        # Create a mapping of strikes (as float) to straddles for easier lookup
        straddles_by_strike = {float(s.strike): s for s in straddles if s.strike is not None}

        # Sort float strikes and select a range around ATM (weighted toward ATM)
        sorted_strikes_float = sorted(strikes_float)
        try:
            atm_index = sorted_strikes_float.index(atm_strike)
        except ValueError:
            atm_index = len(sorted_strikes_float) // 2 # Fallback if ATM not found

        # Calculate start and end indices to include more options around ATM
        half_range = min(max_strikes // 2, len(sorted_strikes_float) // 2)
        start_idx = max(0, atm_index - half_range)
        end_idx = min(len(sorted_strikes_float), atm_index + half_range + 1) # +1 for inclusive slice end

        # Get selected strikes (as float)
        selected_strikes_float = sorted_strikes_float[start_idx:end_idx]

        # Add options data
        for strike_float in selected_strikes_float:
            call_data = None
            put_data = None

            # Find call and put at this strike
            straddle = straddles_by_strike.get(strike_float)
            if straddle:
                call_contract = straddle.call_contract # OptionContract object or None
                put_contract = straddle.put_contract   # OptionContract object or None

                if call_contract:
                    # Ensure values are JSON serializable (float or int)
                    bid = float(call_contract.bid) if call_contract.bid is not None else 0.0
                    ask = float(call_contract.ask) if call_contract.ask is not None else 0.0
                    mid_price = (bid + ask) / 2 if bid is not None and ask is not None else 0.0
                    implied_vol = float(call_contract.implied_volatility) if call_contract.implied_volatility is not None else None # Keep None if not available
                    volume = int(call_contract.volume) if call_contract.volume is not None else 0
                    open_interest = int(call_contract.open_interest) if call_contract.open_interest is not None else 0

                    call_data = {
                        "contract_symbol": call_contract.contract_symbol,
                        "strike": strike_float,
                        "bid": bid,
                        "ask": ask,
                        "mid_price": mid_price,
                        "implied_volatility": implied_vol,
                        "volume": volume,
                        "open_interest": open_interest,
                        "in_the_money": call_contract.in_the_money,
                        "expiration": exp_date_str
                    }

                if put_contract:
                     # Ensure values are JSON serializable (float or int)
                    bid = float(put_contract.bid) if put_contract.bid is not None else 0.0
                    ask = float(put_contract.ask) if put_contract.ask is not None else 0.0
                    mid_price = (bid + ask) / 2 if bid is not None and ask is not None else 0.0
                    implied_vol = float(put_contract.implied_volatility) if put_contract.implied_volatility is not None else None # Keep None if not available
                    volume = int(put_contract.volume) if put_contract.volume is not None else 0
                    open_interest = int(put_contract.open_interest) if put_contract.open_interest is not None else 0

                    put_data = {
                        "contract_symbol": put_contract.contract_symbol,
                        "strike": strike_float,
                        "bid": bid,
                        "ask": ask,
                        "mid_price": mid_price,
                        "implied_volatility": implied_vol,
                        "volume": volume,
                        "open_interest": open_interest,
                        "in_the_money": put_contract.in_the_money,
                        "expiration": exp_date_str
                    }

            expiration_data["options"].append({
                "strike": strike_float,
                "distance_from_atm": abs(strike_float - current_price) / current_price * 100 if current_price else 0,  # % distance
                "call": call_data,
                "put": put_data
            })

        option_chain_dict["options_expirations"].append(expiration_data)

    return option_chain_dict


def analyze_with_gemini(ticker, option_chain_data, risk_tolerance="medium"):
    """Use Gemini to analyze options data"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("Gemini API key not found in environment variables")
        return {"error": "Gemini API key not found in environment variables"}
    
    if not option_chain_data or "options_expirations" not in option_chain_data or not option_chain_data["options_expirations"]:
        logger.warning(f"Insufficient options data provided to analyze_with_gemini for {ticker}")
        return {"error": "Insufficient options data for analysis"}
    
    # Configure Gemini
    try:
        # Attempt to configure only if necessary (more robust)
        if not genai._config.api_key:
             genai.configure(api_key=api_key)
             logger.info("Configured Gemini API key.")
    except AttributeError:
         # If genai._config doesn't exist or api_key isn't an attribute
         genai.configure(api_key=api_key)
         logger.info("Configured Gemini API key (initial config).")
    except Exception as config_err:
         logger.error(f"Error configuring Gemini: {config_err}")
         return {"error": f"Failed to configure Gemini API: {config_err}"}
    
    # Create prompt for options analysis
    prompt = f"""
    You are a professional options trader and financial analyst. I need you to analyze the options data for {ticker} to uncover market sentiment and provide a single clear recommendation based on a {risk_tolerance} risk tolerance.
    
    Here is the options data:
    {json.dumps(option_chain_data, indent=2)}
    
    Please perform a comprehensive options chain analysis:
    
    1. MARKET SENTIMENT ANALYSIS:
       Analyze the options chain to determine if the market is bullish or bearish on this stock. Consider:
       - Put/Call volume ratio and open interest patterns
       - Unusual activity in specific strikes or expirations
       - Implied volatility differences between calls and puts
       - Unusual option flow or activity that suggests institutional positioning
       - Options chain pricing skew and what it reveals about market expectations
       
       Be specific about what signals in the options data indicate bullish or bearish sentiment.
    
    2. VOLATILITY ANALYSIS:
       - Determine if the current options are pricing in any significant events or movements
       - Analyze the volatility term structure across different expirations
       - Identify whether the market is anticipating a move up or down based on volatility pricing
       - Analyze if volatility levels suggest an impending move in a particular direction
    
    3. OPTIONS CHAIN INSIGHTS:
       Uncover specific insights from the options chain data, such as:
       - Where smart money appears to be positioning based on unusual activity
       - Whether there are any large open interest positions at specific strikes suggesting support/resistance
       - Key price levels that appear significant in the options chain
       - Whether market makers appear to be leaning bullish or bearish based on pricing
       - Any unusual spreads or strategies being employed in the market
    
    4. SINGLE CLEAR RECOMMENDATION:
       Based on all insights from the options chain, provide a SINGLE best option trade for the given risk tolerance.
       Instead of multiple options, recommend the ONE option contract that best aligns with the market direction 
       you've uncovered. Include:
       - Contract details (exact strike, expiration, call/put)
       - Entry price range
       - Profit target
       - Stop loss level
       - Expected probability of success
       - Clear rationale for why this specific contract is optimal given the current options chain

    Format your response as a JSON object with the following structure:
    {{
        "market_direction": {{
            "overall_bias": "bullish|bearish|neutral",
            "confidence": float,  // 0-100
            "key_signals": [
                string,  // List specific signals from the options chain supporting this direction
                string,
                string
            ],
            "detailed_analysis": string,  // Deep analysis of market direction signals
            "current_price": {option_chain_data.get("current_price", 0)}  // Current stock price
        }},
        "volatility_insights": {{
            "implied_move": string,  // e.g., "±5% over next week"
            "volatility_skew": "call_skew|put_skew|neutral",
            "event_expectations": [string],  // Any events the options chain suggests the market is pricing in
            "volatility_analysis": string  // Detailed analysis of volatility patterns
        }},
        "options_chain_insights": {{
            "unusual_activity": [string],  // Specific unusual options activity
            "key_strike_levels": [float],  // Important price levels from options chain
            "institutional_positioning": string,  // How institutions appear to be positioned
            "options_flow_analysis": string  // Analysis of recent options flow
        }},
        "recommended_trade": {{
            "contract_type": "call|put",
            "strike": float,
            "expiration": string,
            "contract_symbol": string,
            "entry_price": float,
            "profit_target": float,
            "stop_loss": float,
            "probability_of_success": float,  // 0-100
            "risk_reward_ratio": float,
            "trade_thesis": string,  // Detailed explanation of the trade thesis
            "exit_strategy": string  // When and how to exit the trade
        }},
        "greeks": {{
            "delta": float,
            "gamma": float,
            "theta": float,
            "vega": float,
            "greeks_impact": string  // How the Greeks affect this trade
        }},
        "risk_assessment": {{
            "max_loss": string,
            "max_gain": string,
            "key_risks": [string],
            "position_sizing_recommendation": string  // How much to allocate to this trade
        }},
        "market_context": string  // Broader market context for this stock and sector
    }}
    """
    try:
        # Configure Gemini model
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=types.GenerationConfig(
                temperature=0.2,
                top_p=0.95,
                top_k=64,
                max_output_tokens=8192,
                response_mime_type="application/json",
            )
        )

        # Generate response
        response = model.generate_content(prompt)

        # Parse and return the JSON response
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            # If response is not valid JSON, return a simplified response
            logger.error(f"Failed to parse Gemini response for {ticker}: {response.text}")
            return {
                "error": "Failed to parse Gemini response",
                "raw_response": response.text,
                # Add fallback fields to match expected structure minimally
                "market_direction": {"overall_bias": "neutral", "confidence": 0, "key_signals": [], "detailed_analysis": "Error parsing response."},
                "volatility_insights": {},
                "options_chain_insights": {},
                "recommended_trade": {},
                "greeks": {},
                "risk_assessment": {},
                "market_context": "Analysis failed due to parsing error."
            }
    except Exception as e:
        logger.error(f"Error calling Gemini API: {str(e)}", exc_info=True) # Add exc_info for traceback
        return {
            "error": f"Error calling Gemini API: {str(e)}",
             # Add fallback fields
            "market_direction": {"overall_bias": "neutral", "confidence": 0, "key_signals": [], "detailed_analysis": "Error calling API."},
            "volatility_insights": {},
            "options_chain_insights": {},
            "recommended_trade": {},
            "greeks": {},
            "risk_assessment": {},
            "market_context": "Analysis failed due to API error."
        }

# Example of a wrapper function that might be called by the main app
# This helps abstract the underlying implementation
def run_options_analysis(ticker: str, option_chain: OptionChain, risk_tolerance: str) -> Dict:
    """Runs the complete options analysis workflow."""
    logger.info(f"Running LLM Options Analysis for {ticker} with risk={risk_tolerance}")
    try:
        gemini_input = prepare_gemini_input(option_chain, ticker)
        if "error" in gemini_input:
            return gemini_input
            
        analysis_result = analyze_with_gemini(ticker, gemini_input, risk_tolerance)
        return analysis_result
        
    except Exception as e:
        logger.error(f"Error running options analysis workflow for {ticker}: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred during options analysis: {e}"}
