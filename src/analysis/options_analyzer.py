import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict

import google.generativeai as genai
import google.generativeai.types as types
from dotenv import load_dotenv

from src.data.models import OptionChain # Assuming OptionChain and related types are in models
# Import the database utility function
from src.data.database_utils import save_analysis

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
    # Relaxed check: Verify expected attributes instead of strict isinstance
    if not hasattr(option_chain, 'underlying_symbol') or not hasattr(option_chain, 'options'):
         logger.error(f"Invalid object passed to prepare_gemini_input (missing attributes). Type: {type(option_chain)}")
         return {"error": f"Invalid data object for option chain (missing attributes): {type(option_chain)}"}


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
    You are a sharp, quantitative options analyst providing insights specifically for **short-term/day traders**. Analyze the options data for {ticker} to uncover actionable sentiment, volatility dynamics, and a potential trade setup, considering a {risk_tolerance} risk tolerance.

    Here is the options data for the nearest expirations:
    {json.dumps(option_chain_data, indent=2)}

    Perform a detailed, quantitative options chain analysis focused on the **near term**:

    1. SHORT-TERM SENTIMENT & FLOW ANALYSIS:
       - **Quantify:** Calculate the Put/Call Volume Ratio and Put/Call Open Interest Ratio using the data for the **nearest expiration date** provided. Ensure these calculated values are included in the output JSON.
       - **Identify:** List specific strikes (and whether calls or puts) in the nearest expiration showing **significant volume spikes** (e.g., > 3x average volume if available, or top 3 by volume increase) or **large open interest changes**.
       - **Interpret:** Based ONLY on the provided data, is the near-term options flow suggesting bullishness (e.g., call buying, put selling) or bearishness (e.g., put buying, call selling)? Highlight specific contracts supporting this.
       - **Institutional Positioning:** Are there any visible large blocks or spread trades (e.g., vertical spreads, straddles/strangles with high OI/volume) suggesting institutional plays for the short term? Describe them.

    2. NEAR-TERM VOLATILITY DYNAMICS:
       - **Quantify:** Calculate the **implied volatility (IV) percentage** for ATM calls and puts for the nearest expiration. Calculate the IV skew (Put IV % - Call IV %) and include this numerical value in the JSON output.
       - **Interpret Skew:** Does the calculated near-term IV skew value suggest fear (positive skew, higher put IV), greed (negative skew, higher call IV), or neutrality?
       - **Term Structure:** Briefly compare the ATM IV of the nearest expiration to the next one provided. Is volatility expected to increase (contango) or decrease (backwardation) in the very near term?
       - **Implied Move:** Based on the nearest expiration's ATM straddle price (calculated as ATM Call Mid Price + ATM Put Mid Price, if available), what is the approximate **implied percentage move** for this expiration period? Ensure this calculated percentage is in the JSON.

    3. KEY LEVELS & STRATEGIES:
       - **Key Strikes:** Identify 2-3 key strike prices for the nearest expiration that appear significant based on high Open Interest or Volume (potential support/resistance/pinning areas).
       - **Observed Strategies:** Explicitly identify and describe any **common options strategies** potentially being deployed based on volume and OI patterns (e.g., "High call OI at $STRIKE suggests potential covered call writing", "High put volume at $STRIKE may indicate protective put buying"). If none are apparent, state 'None Observed'.

    4. ACTIONABLE DAY TRADE IDEA (Single Recommendation):
       Based *strictly* on the near-term options data analysis above, provide ONE potential day trade or very short-term (1-3 day) options trade idea. **If no clear edge is present based solely on this options data, state that explicitly.**
       If recommending a trade:
       - **Contract:** Specific contract (Symbol, Strike, Type, Expiration).
       - **Rationale:** Clear, concise reason based *only* on the options signals identified above (e.g., "High call volume at $STRIKE suggests near-term bullish breakout attempt").
       - **Entry/Target/Stop:** Suggest approximate levels based on the option's price and potential short-term move.
       - **Confidence:** Low/Medium/High based on clarity of signals.

    Format your response as a JSON object. Ensure all calculations requested (P/C Ratios, IV Skew, Implied Move %) are included:
    ```json
    {{
        "analysis_timestamp": "{datetime.now().isoformat()}",
        "ticker": "{ticker}",
        "current_price": {option_chain_data.get("current_price", 0)},
        "short_term_sentiment_flow": {{
            "nearest_expiration_date": "YYYY-MM-DD", // Specify the date used
            "put_call_volume_ratio": float, // Calculated P/C Volume Ratio for nearest expiry
            "put_call_oi_ratio": float, // Calculated P/C OI Ratio for nearest expiry
            "significant_volume_strikes": [ // List of strikes/contracts with high volume
                {{"strike": float, "type": "call|put", "volume": int, "oi": int}}
            ],
            "significant_oi_strikes": [ // List of strikes/contracts with high OI
                {{"strike": float, "type": "call|put", "volume": int, "oi": int}}
            ],
            "interpreted_flow_bias": "bullish|bearish|mixed|unclear",
            "flow_signals": [string], // e.g., "High call volume at strike X"
            "potential_institutional_plays": [string] // Description of observed spreads/blocks
        }},
        "near_term_volatility": {{
            "nearest_expiration_date": "YYYY-MM-DD", // Specify the date used
            "atm_call_iv_pct": float,
            "atm_put_iv_pct": float,
            "atm_iv_skew": float, // Calculated (Put IV % - Call IV %)
            "iv_skew_interpretation": "fear|greed|neutral", // Based on Put IV vs Call IV
            "term_structure_near_term": "contango|backwardation|flat", // Compare nearest vs next expiry IV
            "implied_percentage_move": float // Calculated % move for nearest expiry
        }},
        "key_levels_strategies": {{
            "key_options_strikes": [float], // Strikes with high vol/OI
            "potential_support": float, // Nearest key strike below price
            "potential_resistance": float, // Nearest key strike above price
            "observed_strategies": [string] // Description of potential strategies seen or "None Observed"
        }},
        "actionable_trade_idea": {{
            "recommendation_status": "Trade Recommended|No Clear Edge",
            "contract_symbol": string, // Only if trade recommended
            "contract_type": "call|put", // Only if trade recommended
            "strike": float, // Only if trade recommended
            "expiration": string, // Only if trade recommended
            "rationale": string, // Justification based on options data or why no edge
            "suggested_entry": float, // Only if trade recommended
            "suggested_target": float, // Only if trade recommended
            "suggested_stop": float, // Only if trade recommended
            "confidence": "Low|Medium|High" // Confidence in the idea
        }}
        // Removed Greeks, Risk Assessment, Market Context sections for brevity and focus
    }}
    ```
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

        # --> ADD LOGGING HERE <--
        logger.debug(f"Raw response from analyze_with_gemini for {ticker}:\\n{response.text}")
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

# --- Deep Reasoning Function ---
def deep_reasoning_options_analysis(options_data_dict: Dict, initial_analysis_json: Dict) -> str:
    """
    Performs a deep reasoning analysis on the initial options analysis using a second LLM call.

    Args:
        options_data_dict: The dictionary created by prepare_gemini_input.
        initial_analysis_json: The JSON dictionary returned by analyze_with_gemini.

    Returns:
        A string containing the narrative deep reasoning analysis, or an error message.
    """
    api_key = os.getenv("GEMINI_API_KEY") # Or choose another provider/key if desired
    if not api_key:
        logger.error("API key not found for deep reasoning options analysis")
        return "Error: API key missing for deep reasoning."

    ticker = initial_analysis_json.get("ticker", "Unknown Ticker")
    logger.info(f"Performing deep reasoning options analysis for {ticker}")

    # Configure Gemini (or other model)
    try:
        if not genai._config.api_key: # Configure if not already done
             genai.configure(api_key=api_key)
    except AttributeError:
        genai.configure(api_key=api_key)
    except Exception as config_err:
        logger.error(f"Error configuring API for deep reasoning: {config_err}")
        return f"Error: Failed to configure API: {config_err}"

    # Select model (Could use a more powerful model like Pro if needed)
    # model_name = "gemini-1.5-pro-latest" 
    model_name = "gemini-1.5-flash" # Sticking with flash for now

    # Create the prompt for the deep reasoning LLM
    prompt = f"""
    You are a senior options strategist reviewing an analysis generated by a quantitative analyst. Your goal is to provide deeper, narrative insights and identify potential issues.

    **Input Data Provided to Analyst:**
    ```json
    {json.dumps(options_data_dict, indent=2, default=str)}
    ```

    **Analyst's Structured Output:**
    ```json
    {json.dumps(initial_analysis_json, indent=2, default=str)}
    ```

    **Your Task:**
    Provide a concise narrative analysis (plain text, max 3-4 paragraphs) that covers the following:

    1.  **Critique & Consistency Check:** Briefly critique the analyst's structured output based on the input data. Are there any obvious contradictions (e.g., sentiment stated vs. flow described)? Are key quantitative findings (like P/C ratios, IV skew) logically interpreted? Were any significant signals in the raw data potentially missed?
    2.  **Deeper Insights & Market Psychology:** Go beyond the structured points. What might the observed options activity imply about market psychology (e.g., fear, greed, uncertainty)? Are there potential catalysts or events hinted at by the pricing or positioning? Are there more complex strategies possibly at play?
    3.  **Conflicting Signals:** Explicitly point out any conflicting signals within the options data itself (e.g., near-term sentiment differs from mid-term, volume contradicts OI trends at a key level).
    4.  **Overall Confidence Adjustment:** Based on your review, would you increase or decrease confidence in the analyst's overall assessment or trade idea? Briefly state why.

    Focus on providing actionable context and highlighting potential pitfalls or nuances not captured in the initial structured analysis. Keep the language professional and direct.
    """

    try:
        model = genai.GenerativeModel(
            model_name=model_name, 
            generation_config=types.GenerationConfig(
                temperature=0.5, # Slightly higher temp for more nuanced narrative
                top_p=0.95,
                top_k=64,
                max_output_tokens=1024 # Narrative output can be shorter
            )
        )
        
        logger.info(f"Sending deep reasoning options prompt to {model_name} for {ticker}")
        response = model.generate_content(prompt)
        
        deep_reasoning_text = response.text
        # --> ADD LOGGING HERE <--
        logger.debug(f"Raw response from deep_reasoning_options_analysis for {ticker}:\n{deep_reasoning_text}")
        logger.info(f"Received deep reasoning options analysis for {ticker}")
        return deep_reasoning_text

    except Exception as e:
        logger.error(f"Error during deep reasoning API call for {ticker}: {e}", exc_info=True)
        return f"Error: Deep reasoning LLM call failed: {e}"

# --- Synthesis Function ---
def synthesize_options_analysis(
    options_data_dict: Dict, 
    initial_analysis_json: Dict, 
    deep_reasoning_narrative: str
) -> Dict:
    """
    Synthesizes the initial analysis and deep reasoning critique into a final 
    assessment and actionable recommendation using a third LLM call.

    Args:
        options_data_dict: The dictionary created by prepare_gemini_input.
        initial_analysis_json: The JSON dictionary returned by analyze_with_gemini.
        deep_reasoning_narrative: The narrative critique from deep_reasoning_options_analysis.

    Returns:
        A dictionary containing the structured final summary or an error message.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("API key not found for synthesis options analysis")
        return {"error": "API key missing for synthesis step."}

    ticker = initial_analysis_json.get("ticker", "Unknown Ticker")
    logger.info(f"Performing synthesis analysis for {ticker}")

    # Configure Gemini
    try:
        if not genai._config.api_key: 
             genai.configure(api_key=api_key)
    except AttributeError:
        genai.configure(api_key=api_key)
    except Exception as config_err:
        logger.error(f"Error configuring API for synthesis: {config_err}")
        return {"error": f"Failed to configure API for synthesis: {config_err}"}

    # Select model (Flash should be sufficient for synthesis)
    model_name = "gemini-1.5-flash" 

    # Create the prompt for the Synthesis LLM (Portfolio Manager)
    prompt = f"""
    You are the Portfolio Manager reviewing an options analysis workflow for {ticker}.
    You have:
    1. The raw options data provided.
    2. An initial structured analysis from a quantitative analyst.
    3. A narrative critique from a senior options strategist.

    **Input Data:**
    ```json
    {json.dumps(options_data_dict, indent=2, default=str)}
    ```

    **Initial Analyst Report:**
    ```json
    {json.dumps(initial_analysis_json, indent=2, default=str)}
    ```

    **Senior Strategist's Critique:**
    ```text
    {deep_reasoning_narrative}
    ```

    **Your Task:**
    Synthesize all available information into a final, actionable decision summary. Your summary must:

    1.  **Acknowledge Critique:** Briefly mention the key points raised in the strategist's critique (e.g., data anomalies, conflicting signals, missed strategies).
    2.  **Reconcile & Conclude:** Attempt to reconcile conflicting information where possible. State the *final overall assessment* of the near-term outlook (bullish/bearish/neutral/uncertain) based on the combined evidence, considering the critique's impact.
    3.  **Final Trade Decision:** Based on the synthesized view and the critique, make a *final decision* on the trade idea:
        *   **Proceed:** If the initial idea still holds merit despite the critique (potentially with adjustments).
        *   **Revise:** If the critique suggests modifying the original idea (e.g., different strike, different strategy, smaller size).
        *   **Reject/No Trade:** If the critique invalidates the initial idea due to risks, uncertainty, or data issues.
    4.  **Final Recommendation Details (if Proceed/Revise):** If proceeding or revising, provide the *final* contract details, rationale (incorporating critique), entry/target/stop levels, and confidence.
    5.  **Rationale for Rejection (if Reject/No Trade):** Clearly state the primary reasons for rejecting the trade based on the critique.
    6.  **Confidence Level:** State your overall confidence (Low/Medium/High) in the *final* assessment and trade decision (or lack thereof).
    7.  **Next Steps:** Suggest 1-2 concrete next steps (e.g., "Monitor price action around $XXX support", "Wait for volatility confirmation", "Investigate IV data anomaly before trading", "Re-evaluate after upcoming event").

    Output your synthesis as a structured JSON object:
    ```json
    {{
      "synthesis_timestamp": "{datetime.now().isoformat()}",
      "ticker": "{ticker}",
      "critique_summary": [string], // Key points acknowledged from critique
      "final_assessment": {{
        "overall_outlook": "Bullish|Bearish|Neutral|Uncertain",
        "key_signals_considered": [string], // e.g., "Strong put volume, but concerning IV anomaly"
        "confidence": "Low|Medium|High" // Confidence in the outlook itself
      }},
      "final_trade_decision": {{
        "decision": "Proceed|Revise|Reject/No Trade",
        "final_rationale": string, // Justification for the final decision, incorporating critique
        // Include the following only if decision is Proceed or Revise
        "revised_contract_symbol": string, 
        "revised_contract_type": "call|put",
        "revised_strike": float,
        "revised_expiration": string,
        "revised_entry": float,
        "revised_target": float,
        "revised_stop": float,
        "revised_confidence": "Low|Medium|High" 
      }},
      "next_steps": [string] // 1-2 suggested next actions
    }}
    ```
    """

    try:
        model = genai.GenerativeModel(
            model_name=model_name, 
            generation_config=types.GenerationConfig(
                temperature=0.4, # Balanced temperature for synthesis
                top_p=0.95,
                top_k=64,
                max_output_tokens=2048, # Allow sufficient tokens for the summary
                response_mime_type="application/json",
            )
        )
        
        logger.info(f"Sending synthesis options prompt to {model_name} for {ticker}")
        response = model.generate_content(prompt)
        
        synthesis_result = json.loads(response.text)
        logger.debug(f"Raw response from synthesize_options_analysis for {ticker}:\n{response.text}")
        logger.info(f"Received synthesis options analysis for {ticker}")
        return synthesis_result

    except json.JSONDecodeError:
        logger.error(f"Failed to parse synthesis JSON response for {ticker}: {response.text}")
        return {"error": "Failed to parse synthesis LLM response", "raw_response": response.text}
    except Exception as e:
        logger.error(f"Error during synthesis API call for {ticker}: {e}", exc_info=True)
        return {"error": f"Synthesis LLM call failed: {e}"} 

# Example of a wrapper function that might be called by the main app
# This helps abstract the underlying implementation
def run_options_analysis(ticker: str, option_chain: OptionChain, risk_tolerance: str) -> Dict:
    """Runs the complete options analysis workflow."""
    analysis_type = "options" # Define analysis type for saving
    logger.info(f"Running LLM Options Analysis for {ticker} with risk={risk_tolerance}")
    try:
        gemini_input = prepare_gemini_input(option_chain, ticker)
        if "error" in gemini_input:
            return gemini_input
            
        # --> ADD LOGGING HERE <--
        # Use json.dumps for pretty printing the dict in logs
        logger.debug(f"Gemini input prepared for {ticker}:\n{json.dumps(gemini_input, indent=2, default=str)}")
        
        # Step 1: Initial Structured Analysis
        analysis_result = analyze_with_gemini(ticker, gemini_input, risk_tolerance)
        
        # Check if initial analysis failed before proceeding
        if isinstance(analysis_result, dict) and "error" in analysis_result:
            logger.error(f"Initial options analysis failed for {ticker}: {analysis_result['error']}")
            # Return the error from the initial analysis
            return analysis_result
            
        # Step 2: Deep Reasoning Analysis
        logger.info(f"Proceeding to deep reasoning analysis for {ticker}")
        deep_reasoning_narrative = deep_reasoning_options_analysis(gemini_input, analysis_result)
        
        # Step 3: Add narrative to the result
        # Ensure analysis_result is a dictionary before adding the key
        if isinstance(analysis_result, dict):
            analysis_result["deep_reasoning_narrative"] = deep_reasoning_narrative
        else:
            # This case should ideally not happen if the error check above works,
            # but as a fallback, create a new dict.
            logger.warning("Initial analysis result was not a dict. Creating new dict for deep reasoning.")
            analysis_result = {
                "error": "Initial analysis result format unexpected.",
                "initial_analysis_raw": analysis_result, # Store the original non-dict result
                "deep_reasoning_narrative": deep_reasoning_narrative
            }
        
        # Step 4: Synthesis Analysis
        logger.info(f"Proceeding to synthesis analysis for {ticker}")
        synthesis_result = synthesize_options_analysis(gemini_input, analysis_result, deep_reasoning_narrative)
        
        # Check for errors in synthesis
        if isinstance(synthesis_result, dict) and "error" in synthesis_result:
             logger.error(f"Synthesis analysis failed for {ticker}: {synthesis_result['error']}")
             # Optionally add synthesis error to the main result before returning
             if isinstance(analysis_result, dict):
                 analysis_result["synthesis_error"] = synthesis_result['error']
             # Return the analysis_result which already contains initial + deep reasoning
             # Do not save if synthesis failed
             return analysis_result
        
        # Add the synthesis result to the main analysis dictionary
        if isinstance(analysis_result, dict):
             analysis_result["final_summary"] = synthesis_result
        else:
             # If initial analysis wasn't a dict, we still want to return the synthesis
             logger.warning("Initial analysis result was not a dict, returning synthesis directly.")
             # We might want to combine the raw initial analysis and deep reasoning here too if possible
             # For now, just return the synthesis if the initial was bad format
             if isinstance(synthesis_result, dict): # Ensure synthesis itself is a dict
                 synthesis_result["warning"] = "Initial analysis format was unexpected."
                 # Don't save this partial result either
                 return synthesis_result
             else:
                 # Both initial and synthesis failed to produce dicts
                 # Don't save
                 return {"error": "Both initial analysis and synthesis failed to produce valid results."}

        # --- Save successful analysis result to database --- 
        if isinstance(analysis_result, dict) and "error" not in analysis_result:
            try:
                save_analysis(ticker, analysis_type, analysis_result)
            except Exception as db_save_err:
                # Log error but don't block returning the analysis result
                logger.error(f"Failed to save analysis result to database for {ticker}: {db_save_err}", exc_info=True)
        # --- End of Save Step --- 

        # Return the complete result including initial analysis, deep reasoning, and synthesis
        return analysis_result
        
    except Exception as e:
        logger.error(f"Error running options analysis workflow for {ticker}: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred during options analysis: {e}"}
