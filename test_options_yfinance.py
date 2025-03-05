import os
import json
import logging
from datetime import datetime
import yfinance as yf
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def fetch_options_from_yfinance(ticker):
    """Fetch options data directly from Yahoo Finance using yfinance"""
    logger.info(f"Fetching options data for {ticker} using yfinance")
    
    # Get stock info
    stock = yf.Ticker(ticker)
    
    # Get options expiration dates
    expirations = stock.options
    
    if not expirations:
        logger.error(f"No options data available for {ticker}")
        return None
    
    # Get current stock price
    current_price = stock.info.get('regularMarketPrice', 0)
    
    # Get options for the first expiration date
    exp_date = expirations[0]
    options = stock.option_chain(exp_date)
    
    return {
        "ticker": ticker,
        "current_price": current_price,
        "expiration": exp_date,
        "calls": options.calls.to_dict('records'),
        "puts": options.puts.to_dict('records')
    }

def prepare_gemini_input(options_data):
    """Prepare option chain data for Gemini analysis"""
    if not options_data:
        return {
            "underlying_symbol": "Unknown",
            "current_price": 0,
            "error": "No options data available"
        }
    
    ticker = options_data["ticker"]
    current_price = options_data["current_price"]
    
    # Convert option chain to dictionary for Gemini
    option_chain_dict = {
        "underlying_symbol": ticker,
        "current_price": current_price,
        "expiration_dates": [options_data["expiration"]],
        "options_sample": []
    }
    
    # Get all strikes from calls
    calls = options_data["calls"]
    puts = options_data["puts"]
    
    # Create a mapping of strikes to puts for easier lookup
    puts_by_strike = {p["strike"]: p for p in puts}
    
    # Find ATM strike
    strikes = [call["strike"] for call in calls]
    if not strikes:
        return {
            "underlying_symbol": ticker,
            "current_price": current_price,
            "error": "No strike prices available"
        }
    
    atm_strike = min(strikes, key=lambda x: abs(x - current_price))
    
    # Get a range of strikes around ATM
    strikes_around_atm = sorted([s for s in strikes if 0.9 * atm_strike <= s <= 1.1 * atm_strike])
    sample_strikes = strikes_around_atm[:5]  # Take up to 5 strikes around ATM
    
    # Add sample options
    for strike in sample_strikes:
        call_data = None
        put_data = None
        
        # Find call at this strike
        for call in calls:
            if call["strike"] == strike:
                call_data = {
                    "contract_symbol": call.get("contractSymbol", ""),
                    "strike": call["strike"],
                    "bid": call.get("bid", 0),
                    "ask": call.get("ask", 0),
                    "implied_volatility": call.get("impliedVolatility", 0),
                    "volume": call.get("volume", 0),
                    "open_interest": call.get("openInterest", 0),
                    "in_the_money": call.get("inTheMoney", False)
                }
                break
        
        # Find put at this strike
        put = puts_by_strike.get(strike)
        if put:
            put_data = {
                "contract_symbol": put.get("contractSymbol", ""),
                "strike": put["strike"],
                "bid": put.get("bid", 0),
                "ask": put.get("ask", 0),
                "implied_volatility": put.get("impliedVolatility", 0),
                "volume": put.get("volume", 0),
                "open_interest": put.get("openInterest", 0),
                "in_the_money": put.get("inTheMoney", False)
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
    
    # Try different import approaches to handle various package versions
    try:
        # First try the standard import
        import google.generativeai as genai
        from google.generativeai import GenerationConfig
        
        # Initialize Gemini client
        genai.configure(api_key=api_key)
        
        # Configure Gemini model
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            generation_config=GenerationConfig(
                temperature=0.2,
                top_p=0.95,
                top_k=64,
                max_output_tokens=8192,
            )
        )
    except (ImportError, AttributeError):
        # Fall back to langchain integration
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            
            model = ChatGoogleGenerativeAI(
                model="gemini-1.5-pro",
                google_api_key=api_key,
                temperature=0.2,
                top_p=0.95,
                top_k=64,
                max_output_tokens=8192,
            )
            
            # Define a wrapper function to match the direct API
            def generate_content(prompt):
                response = model.invoke(prompt)
                return type('obj', (object,), {'text': response.content})
            
            model.generate_content = generate_content
        except ImportError:
            raise ImportError("Could not import Google Generative AI. Please install with: pip install google-generativeai langchain-google-genai")
    
    # Prepare prompt with options data
    prompt = """
    Analyze the following options data for {ticker} and recommend an optimal options trading strategy 
    based on a {risk_tolerance} risk tolerance level.
    
    Option Chain Data:
    {option_chain_data}
    
    Please provide:
    1. An analysis of current market conditions based on the options data
    2. Evaluation of whether the market is overbought or oversold
    3. Calculation of key Greeks for at-the-money options
    4. Recommended options strategy with specific strikes and expiration
    5. Maximum profit and loss potential for the recommended strategy
    6. Overall market sentiment (bullish, bearish, or neutral)
    
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
        option_chain_data=json.dumps(option_chain_data, indent=2)
    )
    
    # Generate response
    response = model.generate_content(prompt)
    
    # Parse and return the JSON response
    try:
        return json.loads(response.text)
    except (json.JSONDecodeError, AttributeError):
        # If response is not valid JSON or has a different structure, return a simplified response
        try:
            # Try to extract JSON from the text if it's not properly formatted
            import re
            json_match = re.search(r'({.*})', response.text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            else:
                return {
                    "error": "Failed to parse Gemini response",
                    "raw_response": response.text,
                    "overall_sentiment": "neutral",
                    "confidence": 0,
                    "reasoning": "Error in analysis"
                }
        except Exception:
            return {
                "error": "Failed to parse Gemini response",
                "raw_response": str(response),
                "overall_sentiment": "neutral",
                "confidence": 0,
                "reasoning": "Error in analysis"
            }

def main():
    # Test ticker
    ticker = "AAPL"
    risk_tolerance = "medium"
    
    try:
        # Install yfinance if not already installed
        try:
            import yfinance
        except ImportError:
            import subprocess
            print("Installing yfinance...")
            subprocess.check_call(["pip", "install", "yfinance"])
            import yfinance
        
        # Fetch options data from yfinance
        options_data = fetch_options_from_yfinance(ticker)
        
        # Debug: Save raw options data to file
        with open("options_data.json", "w") as f:
            json.dump(options_data, f, indent=2, default=str)
        logger.info("Saved raw options data to options_data.json")
        
        # Prepare data for Gemini
        gemini_input = prepare_gemini_input(options_data)
        
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
            print(f"\nRaw Response: {analysis_result.get('raw_response')}")
            return
            
        print("\nMarket Conditions:")
        market_conditions = analysis_result.get("market_conditions", {})
        print(f"  Sentiment: {market_conditions.get('sentiment', 'N/A')}")
        print(f"  Market Condition: {market_conditions.get('market_condition', 'N/A')}")
        print(f"  Put-Call Ratio: {market_conditions.get('put_call_ratio', 'N/A')}")
        print(f"  IV Skew: {market_conditions.get('implied_volatility_skew', 'N/A')}")
        
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