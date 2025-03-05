import os
import json
import http.client
from datetime import datetime
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def fetch_options_from_rapidapi(ticker):
    """Fetch options data from RapidAPI Yahoo Finance endpoint"""
    logger.info(f"Fetching options data for {ticker} from RapidAPI")
    
    conn = http.client.HTTPSConnection("yahoo-finance166.p.rapidapi.com")
    
    headers = {
        'x-rapidapi-key': os.getenv("RAPIDAPI_KEY", "a5c0896b36mshaa509a779a23bb6p181f51jsna75ba55edc97"),
        'x-rapidapi-host': "yahoo-finance166.p.rapidapi.com"
    }
    
    conn.request("GET", f"/api/stock/get-options?region=US&symbol={ticker}", headers=headers)
    
    res = conn.getresponse()
    data = res.read()
    
    return json.loads(data.decode("utf-8"))

def prepare_gemini_input(api_data, ticker):
    """Prepare option chain data for Gemini analysis"""
    logger.info(f"Preparing Gemini input for {ticker}")
    
    # Debug: Print API response structure
    logger.info(f"API Response Keys: {api_data.keys()}")
    
    # Extract quote data
    option_chain = api_data.get("optionChain", {})
    logger.info(f"Option Chain Keys: {option_chain.keys()}")
    
    result = option_chain.get("result", [])
    if not result:
        logger.error("No result data in API response")
        # Create a minimal structure for testing
        return {
            "underlying_symbol": ticker,
            "current_price": 0,
            "error": "No options data available from API"
        }
    
    quote_data = result[0].get("quote", {})
    current_price = quote_data.get("regularMarketPrice", 0)
    
    # Convert option chain to dictionary for Gemini
    option_chain_dict = {
        "underlying_symbol": ticker,
        "current_price": current_price,
        "expiration_dates": [],
        "strikes": [],
        "options_sample": []
    }
    
    # Process options data
    option_chain_data = result[0].get("options", [])
    logger.info(f"Option Chain Data: {option_chain_data}") #added log
    if not option_chain_data:
        logger.error("No options data in API response")
        return option_chain_dict
    
    # Extract expiration dates
    for option_date in option_chain_data:
        timestamp = option_date.get("expirationDate")
        if timestamp:
            exp_date = datetime.fromtimestamp(timestamp)
            option_chain_dict["expiration_dates"].append(exp_date.strftime("%Y-%m-%d"))
    
    # Get all strikes from first expiration
    if option_chain_data:
        first_exp = option_chain_data[0]
        straddles = first_exp.get("straddles", [])

        if not straddles:
            logger.error("No straddles data in API response")
            return option_chain_dict
            
        strikes = []
        for straddle in straddles:
            if straddle.get("strike") not in strikes:
                strikes.append(straddle.get("strike"))

        option_chain_dict["strikes"] = strikes[:20]  # Limit to first 20 strikes
        
        if not strikes:
            logger.error("No strike prices in API response")
            return option_chain_dict
            
        # Find ATM strike
        atm_strike = min(strikes, key=lambda x: abs(x - current_price))
        atm_index = strikes.index(atm_strike)
        
        # Get a range of strikes around ATM
        start_idx = max(0, atm_index - 2)
        end_idx = min(len(strikes), atm_index + 3)
        sample_strikes = strikes[start_idx:end_idx]
        
        # Create a mapping of strikes to puts for easier lookup
        
        straddles_by_strike = {}
        for straddle in straddles:
            straddles_by_strike[straddle.get('strike')] = straddle

        # Add sample options
        for strike in sample_strikes:
            call_data = None
            put_data = None
            
            # Find call at this strike and put at this strike.
            straddle = straddles_by_strike.get(strike)
            if straddle:
                call = straddle.get('call')
                put = straddle.get('put')
                if call:
                    call_data = {
                        "contract_symbol": call.get("contractSymbol"),
                        "strike": call.get("strike"),
                        "bid": call.get("bid"),
                        "ask": call.get("ask"),
                        "implied_volatility": call.get("impliedVolatility"),
                        "volume": call.get("volume"),
                        "open_interest": call.get("openInterest"),
                        "in_the_money": call.get("inTheMoney")
                    }
                if put:
                    put_data = {
                        "contract_symbol": put.get("contractSymbol"),
                        "strike": put.get("strike"),
                        "bid": put.get("bid"),
                        "ask": put.get("ask"),
                        "implied_volatility": put.get("impliedVolatility"),
                        "volume": put.get("volume"),
                        "open_interest": put.get("openInterest"),
                        "in_the_money": call.get("inTheMoney")
                    }
            
            option_chain_dict["options_sample"].append({
                "strike": strike,
                "call": call_data,
                "put": put_data
            })
    
    return option_chain_dict

def analyze_with_gemini(ticker, option_chain_data, risk_tolerance="medium"):
    """Use Gemini to analyze options data"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.")

    # Check if we have valid options data
    if option_chain_data.get("error"):
        return {
            "error": option_chain_data.get("error"),
            "overall_sentiment": "neutral",
            "confidence": 0,
            "reasoning": "Insufficient data for analysis"
        }

    import google.generativeai as genai
    import google.generativeai.types as types

    # Initialize Gemini client
    genai.configure(api_key=api_key)

    prompt = """
Analyze the following options data for {ticker} and recommend an optimal options trading strategy based on a {risk_tolerance} risk tolerance level.

Option Chain Data:
{option_chain_data}

Specifically, please:

1. Analyze the current market conditions, paying close attention to the differences in implied volatility between call and put options, and the volume and open interest data. Provide a detailed analysis of how these factors influence your strategy recommendation.

2. Calculate the Put/Call Ratio as follows:
   - Sum the 'volume' values for all put options in the 'options_sample' data.
   - Sum the 'volume' values for all call options in the 'options_sample' data.
   - Divide the total put volume by the total call volume.
   - Report the result as the 'put_call_ratio'.

3. Calculate the Implied Volatility (IV) Skew as follows:
   - Use the put option with the highest 'strike' in the 'options_sample' data as the out-of-the-money (OTM) put.
   - Use the call option with the lowest 'strike' in the 'options_sample' data as the OTM call.
   - Subtract the 'implied_volatility' of the OTM call from the 'implied_volatility' of the OTM put.
   - Report the result as the 'implied_volatility_skew'.

4. Calculate the Maximum Profit for the recommended strategy as follows:
   - For each option in the strategy, calculate the mid-price by averaging the 'bid' and 'ask' values.
   - Sum the mid-prices of all options that are being sold in the strategy.
   - Report the result as the 'max_profit'.

5. Evaluate whether the market is overbought or oversold based on the provided data.

6. Recommend an options strategy with specific strikes and expiration, justifying your choice based on the analysis of the provided data, including implied volatility, volume, and open interest.

7. Estimate the maximum profit and loss potential for the recommended strategy, considering the mid price (average of bid and ask) for premium calculations.

8. Determine the overall market sentiment (bullish, bearish, or neutral) and provide a confidence level (percentage).

9. Explain your reasoning in detail, referencing specific data points from the provided option chain, especially the differences in implied volatility between calls and puts, and the volume and open interest.

10. Provide estimates or calculations of the key Greeks (delta, gamma, theta, vega) for at-the-money options. If exact calculations are not possible, provide well-reasoned estimations. Fill in the following table:

Greeks:
| Option Type | Strike | Delta | Gamma | Theta | Vega |
|-------------|--------|-------|-------|-------|------|
| Call        | {atm_strike} |       |       |       |      |
| Put         | {atm_strike} |       |       |       |      |

11. Explain in detail why you have the level of confidence that you have in this analysis.

Format your response as a JSON object with the following structure:
{{
    "market_conditions": {{
        "put_call_ratio": float,
        "implied_volatility_skew": float,
        "sentiment": "bullish|bearish|neutral",
        "market_condition": "overbought|oversold|normal"
    }},
    "greeks": {{
        "call_delta": float,
        "call_gamma": float,
        "call_theta": float,
        "call_vega": float,
        "put_delta": float,
        "put_gamma": float,
        "put_theta": float,
        "put_vega": float
    }},
    "recommended_strategy": {{
        "name": string,
        "description": string,
        "legs": [
            {{"type": "buy|sell", "option_type": "call|put", "strike": float, "expiration": string}}
        ],
        "max_profit": string,
        "max_loss": string
    }},
    "overall_sentiment": "bullish|bearish|neutral",
    "confidence": float,
    "reasoning": string
}}
""".format(
    ticker=ticker,
    risk_tolerance=risk_tolerance,
    option_chain_data=json.dumps(option_chain_data, indent=2),
    atm_strike=option_chain_data["options_sample"][2]["strike"]
)
    # Configure Gemini model
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
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
        return {
            "error": "Failed to parse Gemini response",
            "raw_response": response.text,
            "overall_sentiment": "neutral",
            "confidence": 0,
            "reasoning": "Error in analysis"
        }

def main():
    # Test ticker
    ticker = "TSLA"
    risk_tolerance = "medium"

    try:
        # Fetch options data from RapidAPI
        api_data = fetch_options_from_rapidapi(ticker)

        # Debug: Save raw API response to file
        with open("api_response.json", "w") as f:
            json.dump(api_data, f, indent=2)
        logger.info("Saved raw API response to api_response.json")

        # Prepare data for Gemini
        gemini_input = prepare_gemini_input(api_data, ticker)

        # Debug: Save prepared input to file
        with open("gemini_input.json", "w") as f:
            json.dump(gemini_input, f, indent=2)
        logger.info("Saved Gemini input to gemini_input.json")

        # Check if we have valid data
        if gemini_input.get("error"):
            print(f"\nError: {gemini_input.get('error')}")
            return

        # Run analysis with Gemini
        logger.info(f"Running Gemini analysis for {ticker}")
        analysis_result = analyze_with_gemini(ticker, gemini_input, risk_tolerance)

        # Display results
        print("\n===== Options Analysis Results =====\n")
        print(f"Ticker: {ticker}")
        print(f"Current Price: ${gemini_input['current_price']:.2f}")
        print(f"Risk Tolerance: {risk_tolerance}")

        if analysis_result.get("error"):
            print(f"\nError: {analysis_result.get('error')}")
            return

        print("\nMarket Conditions:")
        market_conditions = analysis_result.get("market_conditions", {})
        print(f"  Sentiment: {market_conditions.get('sentiment', 'N/A')}")
        print(f"  Market Condition: {market_conditions.get('market_condition', 'N/A')}")
        print(f"  Put-Call Ratio: {market_conditions.get('put_call_ratio', 'N/A')}")
        print(f"  IV Skew: {market_conditions.get('implied_volatility_skew', 'N/A')}")

        print("\nGreeks:")
        greeks = analysis_result.get("greeks", {})
        if greeks:
            print(f"  Call Delta: {greeks.get('call_delta', 'N/A')}")
            print(f"  Call Gamma: {greeks.get('call_gamma', 'N/A')}")
            print(f"  Call Theta: {greeks.get('call_theta', 'N/A')}")
            print(f"  Call Vega: {greeks.get('call_vega', 'N/A')}")
            print(f"  Put Delta: {greeks.get('put_delta', 'N/A')}")
            print(f"  Put Gamma: {greeks.get('put_gamma', 'N/A')}")
            print(f"  Put Theta: {greeks.get('put_theta', 'N/A')}")
            print(f"  Put Vega: {greeks.get('put_vega', 'N/A')}")
        else:
            print("  Greeks: N/A")

        print("\nRecommended Strategy:")
        strategy = analysis_result.get("recommended_strategy", {})
        print(f"  Name: {strategy.get('name', 'N/A')}")
        print(f"  Description: {strategy.get('description', 'N/A')}")
        print("  Legs:")
        for leg in strategy.get("legs", []):
            print(f"    - {leg.get('type', 'N/A')} {leg.get('option_type', 'N/A')} @ strike ${leg.get('strike', 'N/A')}")
        print(f"  Max Profit: {strategy.get('max_profit', 'N/A')}")
        print(f"  Max Loss: {strategy.get('max_loss', 'N/A')}")

        print(f"\nOverall Sentiment: {analysis_result.get('overall_sentiment', 'N/A')}")
        print(f"Confidence: {analysis_result.get('confidence', 'N/A')}%")
        print(f"\nReasoning: {analysis_result.get('reasoning', 'N/A')}")

    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()