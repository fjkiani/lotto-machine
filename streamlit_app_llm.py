import streamlit as st
import pandas as pd
import os
import sys
import subprocess
import logging

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

import json
import os
import logging
import http.client
import google.generativeai as genai
import google.generativeai.types as types
from datetime import datetime, timedelta
from dotenv import load_dotenv
from src.analysis.enhanced_analysis_pipeline import EnhancedAnalysisPipeline
from src.data.connectors.yahoo_finance import YahooFinanceConnector
from src.llm.memory_enhanced_analysis import MemoryEnhancedAnalysis
from src.data.memory import AnalysisMemory

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
required_vars = ['OPENAI_API_KEY', 'GOOGLE_API_KEY']
missing_vars = [var for var in required_vars if not os.environ.get(var)]
if missing_vars:
    logger.warning(f"Missing required environment variables: {', '.join(missing_vars)}")
    st.error(f"Missing required environment variables: {', '.join(missing_vars)}")

# Initialize Google Generative AI with API key
try:
    genai.configure(api_key=os.environ.get('GOOGLE_API_KEY'))
    logger.info("Successfully configured Google Generative AI")
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

def fetch_market_data(ticker):
    """Fetch market data from RapidAPI Yahoo Finance"""
    conn = http.client.HTTPSConnection("yahoo-finance166.p.rapidapi.com")
    
    headers = {
        'X-RapidAPI-Key': os.getenv("RAPIDAPI_KEY"),
        'X-RapidAPI-Host': "yahoo-finance166.p.rapidapi.com"
    }
    
    endpoint = f"/api/stock/get-options?region=US&symbol={ticker}"
    logger.info(f"Fetching market data from endpoint: {endpoint}")
    
    conn.request("GET", endpoint, headers=headers)
    
    res = conn.getresponse()
    status = res.status
    data = res.read()
    
    logger.info(f"Market data API response status: {status}")
    
    if status != 200:
        logger.error(f"API error: {status} - {data.decode('utf-8')}")
        return {"error": f"API returned status {status}", "raw_response": data.decode('utf-8')}
    
    try:
        json_data = json.loads(data.decode("utf-8"))
        logger.info(f"Market data keys: {list(json_data.keys())}")
        
        # Extract basic market data from options response
        option_chain = json_data.get("optionChain", {})
        result = option_chain.get("result", [])
        
        if result and len(result) > 0:
            quote = result[0].get("quote", {})
            return {
                "quoteSummary": {
                    "result": [{
                        "price": {
                            "regularMarketPrice": {"raw": quote.get("regularMarketPrice", 0)},
                            "regularMarketChangePercent": {"raw": quote.get("regularMarketChangePercent", 0)},
                            "regularMarketVolume": {"raw": quote.get("regularMarketVolume", 0)},
                            "averageDailyVolume10Day": {"raw": quote.get("averageDailyVolume10Day", 0)},
                            "marketCap": {"raw": quote.get("marketCap", 0)}
                        },
                        "summaryDetail": {
                            "fiftyTwoWeekLow": {"raw": quote.get("fiftyTwoWeekLow", 0)},
                            "fiftyTwoWeekHigh": {"raw": quote.get("fiftyTwoWeekHigh", 0)},
                            "trailingPE": {"raw": quote.get("trailingPE", 0)},
                            "dividendYield": {"raw": quote.get("dividendYield", 0)},
                            "beta": {"raw": quote.get("beta", 0)}
                        }
                    }]
                },
                "current_price": quote.get("regularMarketPrice", 0),
                "raw_data": json_data
            }
        
        return {"error": "No market data available in the response"}
        
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON response: {e}")
        return {"error": f"Error parsing response: {e}"}
    except Exception as e:
        logger.error(f"Error fetching market data: {e}")
        return {"error": f"Error fetching market data: {e}"}

def prepare_gemini_input(api_data, ticker):
    """Prepare option chain data for Gemini analysis"""
    logger.info(f"Preparing Gemini input for {ticker}")
    
    # Debug: Print API response structure
    logger.info(f"API Response Keys: {api_data.keys()}")
    
    # Extract quote data
    option_chain = api_data.get("raw_data", {}).get("optionChain", {})
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
    logger.info(f"Option Chain Data Length: {len(option_chain_data)}")
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
            
            # Find call at this strike and put at this strike
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
                        "in_the_money": put.get("inTheMoney")
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
        return {"error": "Gemini API key not found in environment variables"}
    
    if not option_chain_data or "options_sample" not in option_chain_data or not option_chain_data["options_sample"]:
        return {"error": "Insufficient options data for analysis"}
    
    # Configure Gemini
    genai.configure(api_key=api_key)
    
    # Create prompt for options analysis
    prompt = f"""
    You are a professional options trader and financial analyst. I need you to analyze the options data for {ticker} and provide recommendations based on a {risk_tolerance} risk tolerance.
    
    Here is the options data:
    {json.dumps(option_chain_data, indent=2)}
    
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
    | Call        | {option_chain_data["options_sample"][len(option_chain_data["options_sample"])//2]["strike"] if option_chain_data["options_sample"] else 0} |       |       |       |      |
    | Put         | {option_chain_data["options_sample"][len(option_chain_data["options_sample"])//2]["strike"] if option_chain_data["options_sample"] else 0} |       |       |       |      |
    
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
    """
    try:
        # Configure Gemini model - CHANGED FROM PRO TO FLASH
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
            return {
                "error": "Failed to parse Gemini response",
                "raw_response": response.text,
                "overall_sentiment": "neutral",
                "confidence": 0,
                "reasoning": "Error in analysis"
            }
    except Exception as e:
        logger.error(f"Error calling Gemini API: {str(e)}")
        return {
            "error": f"Error calling Gemini API: {str(e)}",
            "overall_sentiment": "neutral",
            "confidence": 0,
            "reasoning": "Error in analysis"
        }

def display_market_overview(market_data, ticker):
    """Display market overview data"""
    st.header(f"Market Overview: {ticker}")
    
    # Check if market_data is None or has an error
    if market_data is None:
        st.error(f"No market data available for {ticker}")
        return 0  # Return default price of 0
        
    if "error" in market_data:
        st.error(f"Error fetching market data: {market_data.get('error')}")
        with st.expander("Raw API Response"):
            st.code(market_data.get("raw_response", "No raw response available"))
        return 0  # Return default price of 0 if there's an error
    
    # Extract price data
    price_data = None
    summary_detail = None
    
    try:
        if "quoteSummary" in market_data and "result" in market_data["quoteSummary"]:
            result = market_data["quoteSummary"]["result"]
            if result and len(result) > 0:
                price_data = result[0].get("price", {})
                summary_detail = result[0].get("summaryDetail", {})
    except Exception as e:
        st.error(f"Error extracting market data: {str(e)}")
        return 0
    
    if not price_data:
        st.warning("Price data not available")
        return 0
    
    # Display key metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        current_price = price_data.get("regularMarketPrice", {}).get("raw", 0)
        st.metric("Price", price_data.get("regularMarketPrice", {}).get("fmt", f"${current_price:.2f}"))
    
    with col2:
        volume = price_data.get("regularMarketVolume", {}).get("raw", 0)
        st.metric("Volume", price_data.get("regularMarketVolume", {}).get("fmt", f"{volume:,}"))
    
    with col3:
        market_cap = summary_detail.get("marketCap", {}).get("raw", 0) if summary_detail else 0
        market_cap_fmt = summary_detail.get("marketCap", {}).get("fmt", f"${market_cap/1000000000:.2f}B") if summary_detail else f"${market_cap/1000000000:.2f}B"
        st.metric("Market Cap", market_cap_fmt)
    
    # Display additional market information if available
    if price_data and summary_detail:
        with st.expander("Additional Market Information"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Day High", price_data.get("regularMarketDayHigh", {}).get("fmt", "N/A"))
                st.metric("Day Low", price_data.get("regularMarketDayLow", {}).get("fmt", "N/A"))
                st.metric("Open", price_data.get("regularMarketOpen", {}).get("fmt", "N/A"))
                st.metric("Previous Close", price_data.get("regularMarketPreviousClose", {}).get("fmt", "N/A"))
            
            with col2:
                st.metric("52 Week High", summary_detail.get("fiftyTwoWeekHigh", {}).get("fmt", "N/A"))
                st.metric("52 Week Low", summary_detail.get("fiftyTwoWeekLow", {}).get("fmt", "N/A"))
    
    return current_price

def display_llm_options_analysis(analysis_result, ticker):
    """Display LLM-powered options analysis"""
    st.header("LLM-Powered Options Analysis")
    
    # Check for errors
    if "error" in analysis_result:
        st.error(f"Error in options analysis: {analysis_result.get('error')}")
        if "raw_response" in analysis_result:
            with st.expander("Raw LLM Response"):
                st.code(analysis_result.get("raw_response"))
        return
    
    # Market Conditions
    st.subheader("Market Conditions")
    market_conditions = analysis_result.get("market_conditions", {})
    
    col1, col2 = st.columns(2)
    with col1:
        put_call_ratio = market_conditions.get('put_call_ratio')
        if put_call_ratio is not None:
            st.metric("Put-Call Ratio", f"{put_call_ratio:.2f}")
        else:
            st.metric("Put-Call Ratio", "N/A")
            
        iv_skew = market_conditions.get('implied_volatility_skew')
        if iv_skew is not None:
            st.metric("IV Skew", f"{iv_skew:.2f}")
        else:
            st.metric("IV Skew", "N/A")
    
    with col2:
        sentiment = market_conditions.get('sentiment', 'neutral')
        sentiment_color = {
            'bullish': 'green',
            'bearish': 'red',
            'neutral': 'blue'
        }.get(sentiment.lower(), 'blue')
        
        st.markdown(f"**Sentiment**: <span style='color:{sentiment_color}'>{sentiment}</span>", unsafe_allow_html=True)
        
        market_condition = market_conditions.get('market_condition', 'normal')
        condition_color = {
            'overbought': 'red',
            'oversold': 'green',
            'normal': 'blue'
        }.get(market_condition.lower(), 'blue')
        
        st.markdown(f"**Market Condition**: <span style='color:{condition_color}'>{market_condition}</span>", unsafe_allow_html=True)
    
    # Greeks
    st.subheader("Options Greeks")
    greeks = analysis_result.get("greeks", {})
    
    # Create a DataFrame for the Greeks
    greeks_data = {
        "Greek": ["Delta", "Gamma", "Theta", "Vega"],
        "Call": [
            greeks.get("call_delta", "N/A"),
            greeks.get("call_gamma", "N/A"),
            greeks.get("call_theta", "N/A"),
            greeks.get("call_vega", "N/A")
        ],
        "Put": [
            greeks.get("put_delta", "N/A"),
            greeks.get("put_gamma", "N/A"),
            greeks.get("put_theta", "N/A"),
            greeks.get("put_vega", "N/A")
        ]
    }
    
    greeks_df = pd.DataFrame(greeks_data)
    st.table(greeks_df)
    
    # Recommended Strategy
    st.subheader("Recommended Options Strategy")
    strategy = analysis_result.get("recommended_strategy", {})
    
    st.markdown(f"### {strategy.get('name', 'N/A')}")
    st.write(strategy.get('description', 'N/A'))
    
    # Strategy legs
    st.write("**Strategy Legs:**")
    legs = strategy.get("legs", [])
    
    if legs:
        legs_data = []
        for leg in legs:
            legs_data.append({
                "Action": leg.get("type", "N/A"),
                "Option Type": leg.get("option_type", "N/A"),
                "Strike": f"${leg.get('strike', 0):.2f}" if leg.get('strike') is not None else "N/A",
                "Expiration": leg.get("expiration", "N/A")
            })
        
        legs_df = pd.DataFrame(legs_data)
        st.table(legs_df)
    
    # Profit/Loss
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Maximum Profit**: {strategy.get('max_profit', 'N/A')}")
    with col2:
        st.markdown(f"**Maximum Loss**: {strategy.get('max_loss', 'N/A')}")
    
    # Overall Analysis
    st.subheader("Analysis Summary")
    
    # Overall sentiment and confidence
    sentiment = analysis_result.get("overall_sentiment", "neutral")
    confidence = analysis_result.get("confidence", 0)
    
    sentiment_color = {
        'bullish': 'green',
        'bearish': 'red',
        'neutral': 'blue'
    }.get(sentiment.lower(), 'blue')
    
    st.markdown(f"**Overall Sentiment**: <span style='color:{sentiment_color}'>{sentiment}</span> (Confidence: {confidence:.1f}%)", unsafe_allow_html=True)
    
    # Reasoning
    st.subheader("Detailed Reasoning")
    st.write(analysis_result.get("reasoning", "No reasoning provided"))

def display_enhanced_analysis(analysis_result):
    """Display enhanced analysis with feedback loop"""
    st.header("Enhanced Analysis with Feedback Loop")
    
    # Market Overview
    st.subheader("Market Overview")
    market_overview = analysis_result.get("market_overview", {})
    
    col1, col2 = st.columns(2)
    with col1:
        sentiment = market_overview.get('sentiment', 'neutral')
        sentiment_color = {
            'bullish': 'green',
            'bearish': 'red',
            'neutral': 'blue'
        }.get(sentiment.lower(), 'blue')
        st.markdown(f"**Market Sentiment**: <span style='color:{sentiment_color}'>{sentiment}</span>", unsafe_allow_html=True)
    
    with col2:
        market_condition = market_overview.get('market_condition', 'normal')
        condition_color = {
            'overbought': 'red',
            'oversold': 'green',
            'normal': 'blue'
        }.get(market_condition.lower(), 'blue')
        st.markdown(f"**Market Condition**: <span style='color:{condition_color}'>{market_condition}</span>", unsafe_allow_html=True)
    
    # Key Observations
    st.subheader("Key Observations")
    for observation in market_overview.get("key_observations", []):
        st.markdown(f"- {observation}")
    
    # Ticker Analysis
    st.subheader("Ticker Analysis")
    ticker_analysis = analysis_result.get("ticker_analysis", {})
    
    for ticker, ticker_data in ticker_analysis.items():
        with st.expander(f"{ticker} Analysis"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                sentiment = ticker_data.get('sentiment', 'neutral')
                sentiment_color = {
                    'bullish': 'green',
                    'bearish': 'red',
                    'neutral': 'blue'
                }.get(sentiment.lower(), 'blue')
                st.markdown(f"**Sentiment**: <span style='color:{sentiment_color}'>{sentiment}</span>", unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"**Recommendation**: {ticker_data.get('recommendation', 'N/A')}")
            
            with col3:
                st.markdown(f"**Risk Level**: {ticker_data.get('risk_level', 'N/A')}")
            
            # Technical Signals
            if "technical_signals" in ticker_data:
                st.markdown("**Technical Signals:**")
                for signal in ticker_data["technical_signals"]:
                    st.markdown(f"- {signal}")
            
            # Price Targets
            price_target = ticker_data.get("price_target", {})
            if price_target:
                st.markdown("**Price Targets:**")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Short-term", f"${price_target.get('short_term', 'N/A')}")
                with col2:
                    st.metric("Long-term", f"${price_target.get('long_term', 'N/A')}")
                
                if "note" in price_target:
                    st.info(f"Note: {price_target['note']}")
            
            # Key Insights
            if "key_insights" in ticker_data:
                st.markdown("**Key Insights:**")
                for insight in ticker_data["key_insights"]:
                    st.markdown(f"- {insight}")
    
    # Trading Opportunities
    st.subheader("Trading Opportunities")
    opportunities = analysis_result.get("trading_opportunities", [])
    
    for opportunity in opportunities:
        with st.expander(f"{opportunity.get('ticker', 'N/A')} - {opportunity.get('strategy', 'N/A')}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**Time Horizon**: {opportunity.get('time_horizon', 'N/A')}")
                st.markdown(f"**Risk/Reward**: {opportunity.get('risk_reward_ratio', 'N/A')}")
            
            with col2:
                st.markdown("**Rationale:**")
                st.write(opportunity.get('rationale', 'N/A'))
    
    # Overall Recommendation
    st.subheader("Overall Recommendation")
    st.write(analysis_result.get('overall_recommendation', 'N/A'))
    
    # Feedback Information
    if "feedback" in analysis_result:
        st.header("Feedback Loop Information")
        feedback = analysis_result["feedback"]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Contradictions Detected", feedback.get('contradictions_detected', 0))
        
        st.subheader("Changes Made")
        for change in feedback.get("changes_made", []):
            st.markdown(f"- {change}")
        
        st.subheader("Overall Assessment")
        st.write(feedback.get('overall_assessment', 'N/A'))
        
        # Learning Points
        if "learning_points" in feedback:
            st.subheader("Learning Points")
            for point in feedback["learning_points"]:
                st.markdown(f"- {point}")

def display_memory_enhanced_analysis(ticker, analysis_result, historical_analyses):
    """Display memory-enhanced analysis results with historical context"""
    
    # Display current analysis
    st.subheader(f"Memory-Enhanced Analysis for {ticker}")
    
    # Check if we have a valid analysis result
    if not analysis_result or isinstance(analysis_result, str):
        st.error(f"Invalid analysis result: {analysis_result if isinstance(analysis_result, str) else 'No data'}")
        return
    
    # Market Overview
    st.write("### Market Overview")
    current_price = analysis_result.get("current_price", "N/A")
    price_change = analysis_result.get("price_change_percent", "N/A")
    
    # Format current price as float if possible
    try:
        if current_price != "N/A":
            current_price = float(current_price)
            price_display = f"${current_price:.2f}"
        else:
            price_display = "N/A"
    except (ValueError, TypeError):
        price_display = f"${current_price}" if current_price != "N/A" else "N/A"
    
    # Display price with change if available
    if price_change != "N/A":
        try:
            price_change = float(price_change)
            st.metric("Current Price", price_display, f"{price_change:.2f}%")
        except (ValueError, TypeError):
            st.metric("Current Price", price_display)
    else:
        st.metric("Current Price", price_display)
    
    # Additional market metrics if available
    col1, col2 = st.columns(2)
    with col1:
        volume = analysis_result.get("volume", "N/A")
        if volume != "N/A":
            try:
                volume = int(volume)
                st.metric("Volume", f"{volume:,}")
            except (ValueError, TypeError):
                st.metric("Volume", volume)
    
    with col2:
        market_cap = analysis_result.get("market_cap", "N/A")
        if market_cap != "N/A":
            try:
                market_cap = float(market_cap)
                st.metric("Market Cap", f"${market_cap/1e9:.2f}B" if market_cap >= 1e9 else f"${market_cap/1e6:.2f}M")
            except (ValueError, TypeError):
                st.metric("Market Cap", market_cap)
    
    # Analysis Summary
    st.write("### Analysis Summary")
    summary = analysis_result.get("summary", "No summary available")
    st.write(summary)
    
    # Recommendation
    recommendation = analysis_result.get("recommendation", {})
    if recommendation:
        st.write("### Recommendation")
        rec_type = recommendation.get("type", "N/A")
        confidence = recommendation.get("confidence", 0)
        
        # Color-code the recommendation
        rec_color = {
            "BUY": "green",
            "SELL": "red",
            "HOLD": "blue"
        }.get(rec_type.upper(), "black")
        
        st.markdown(f"**Recommendation:** <span style='color:{rec_color}'>{rec_type.upper()}</span> with {confidence:.1f}% confidence", unsafe_allow_html=True)
        st.write(recommendation.get("reasoning", "No reasoning provided"))
    
    # Historical Context
    st.write("### Historical Context")
    if historical_analyses:
        # Convert to DataFrame for easier manipulation
        hist_data = []
        for analysis in historical_analyses:
            # Extract data from dictionary
            try:
                # Get recommendation data
                rec_data = analysis.get("recommendation", {})
                if isinstance(rec_data, dict):
                    rec_type = rec_data.get("type", "N/A")
                    confidence = rec_data.get("confidence", 0)
                else:
                    rec_type = str(rec_data).upper() if rec_data else "N/A"
                    confidence = 0
                
                # Get price data
                price = analysis.get("price", 0)
                if isinstance(price, str) and price.strip():
                    try:
                        price = float(price)
                    except (ValueError, TypeError):
                        price = 0
                
                hist_data.append({
                    "timestamp": analysis.get("timestamp", "Unknown"),
                    "price": price,
                    "recommendation": rec_type,
                    "confidence": confidence,
                    "accuracy": analysis.get("accuracy_score", 0)
                })
            except Exception as e:
                st.warning(f"Error processing historical analysis: {str(e)}")
                continue
        
        if hist_data:
            hist_df = pd.DataFrame(hist_data)
            if not hist_df.empty:
                # Convert timestamp to datetime if it's not already
                if not pd.api.types.is_datetime64_any_dtype(hist_df['timestamp']):
                    try:
                        hist_df['timestamp'] = pd.to_datetime(hist_df['timestamp'])
                    except:
                        st.warning("Could not convert timestamps to datetime format")
                
                hist_df = hist_df.sort_values('timestamp', ascending=False)
                
                # Display historical recommendations
                st.write("Previous Recommendations:")
                for _, analysis in hist_df.iterrows():
                    timestamp_str = analysis['timestamp']
                    if isinstance(analysis['timestamp'], pd.Timestamp):
                        timestamp_str = analysis['timestamp'].strftime('%Y-%m-%d %H:%M')
                        
                    with st.expander(f"Analysis from {timestamp_str}"):
                        st.write(f"Price at Analysis: ${analysis['price']:.2f}")
                        st.write(f"Recommendation: {analysis['recommendation']}")
                        st.write(f"Confidence: {analysis['confidence']:.1f}%")
                        st.write(f"Accuracy Score: {analysis['accuracy']:.2f}")
                        
                # Plot price and recommendations over time if we have more than one data point
                if len(hist_df) > 1:
                    fig = go.Figure()
                    
                    # Add price line
                    fig.add_trace(go.Scatter(
                        x=hist_df['timestamp'], 
                        y=hist_df['price'],
                        mode='lines+markers',
                        name='Price'
                    ))
                    
                    # Add recommendation markers
                    buy_df = hist_df[hist_df['recommendation'] == 'BUY']
                    sell_df = hist_df[hist_df['recommendation'] == 'SELL']
                    hold_df = hist_df[hist_df['recommendation'] == 'HOLD']
                    
                    if not buy_df.empty:
                        fig.add_trace(go.Scatter(
                            x=buy_df['timestamp'], 
                            y=buy_df['price'],
                            mode='markers',
                            marker=dict(color='green', size=12, symbol='triangle-up'),
                            name='Buy'
                        ))
                    
                    if not sell_df.empty:
                        fig.add_trace(go.Scatter(
                            x=sell_df['timestamp'], 
                            y=sell_df['price'],
                            mode='markers',
                            marker=dict(color='red', size=12, symbol='triangle-down'),
                            name='Sell'
                        ))
                    
                    if not hold_df.empty:
                        fig.add_trace(go.Scatter(
                            x=hold_df['timestamp'], 
                            y=hold_df['price'],
                            mode='markers',
                            marker=dict(color='blue', size=12, symbol='circle'),
                            name='Hold'
                        ))
                    
                    fig.update_layout(
                        title=f'Historical Price and Recommendations for {ticker}',
                        xaxis_title='Date',
                        yaxis_title='Price ($)',
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    
                    st.plotly_chart(fig)
        else:
            st.info("No valid historical analyses available.")
    else:
        st.info("No historical analyses available yet.")
    
    # Learning Points
    learning_points = analysis_result.get("learning_points", [])
    if learning_points:
        st.write("### Learning Points")
        for point in learning_points:
            st.write(f"- {point}")
    
    # Feedback Collection
    st.write("### Provide Feedback")
    feedback_type = st.selectbox(
        "Feedback Type", 
        ["General", "Accuracy", "Insight", "Recommendation", "Other"]
    )
    feedback_text = st.text_area("Your Feedback")
    
    if st.button("Submit Feedback"):
        try:
            # Get the analysis ID from the result
            analysis_id = analysis_result.get("analysis_id", None)
            if analysis_id:
                st.session_state.memory_analyzer.add_user_feedback(
                    analysis_id=analysis_id,
                    feedback_type=feedback_type.lower(),
                    feedback_text=feedback_text
                )
                st.success("Thank you for your feedback!")
            else:
                st.error("Could not submit feedback: Analysis ID not found")
        except Exception as e:
            st.error(f"Error submitting feedback: {str(e)}")
            logger.error(f"Feedback submission error: {str(e)}", exc_info=True)

def create_technical_chart(ticker, market_data, analysis_result):
    """Create a technical chart with AI-identified labels and indicators"""
    st.subheader(f"Technical Analysis Chart for {ticker}")
    
    # Check if we have valid market data
    if market_data is None:
        st.error("No market data available for chart visualization")
        return
        
    if "error" in market_data:
        st.error(f"Error in market data: {market_data['error']}")
        return
        
    # Check if we have valid analysis result
    if analysis_result is None:
        st.warning("No analysis result available. Chart will be created with limited indicators.")
    elif "error" in analysis_result:
        st.warning(f"Error in analysis result: {analysis_result['error']}. Chart will be created with limited indicators.")
    
    # Add timeframe selection
    timeframe_options = {
        "1 Month": "1mo",
        "3 Months": "3mo",
        "6 Months": "6mo",
        "1 Year": "1y",
        "2 Years": "2y",
        "5 Years": "5y",
        "Max": "max"
    }
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        selected_timeframe = st.selectbox("Select Timeframe", list(timeframe_options.keys()), index=1)
    
    with col2:
        chart_type = st.selectbox("Chart Type", ["Candlestick", "Line", "OHLC"], index=0)
    
    with col3:
        show_volume = st.checkbox("Show Volume", value=True)
    
    # Technical indicator selection
    indicator_options = st.multiselect(
        "Select Technical Indicators",
        ["Moving Averages", "Bollinger Bands", "RSI", "MACD", "Support/Resistance"],
        default=["Moving Averages", "Bollinger Bands", "Support/Resistance"]
    )
    
    try:
        # Try to import yfinance
        try:
            import yfinance as yf
        except ImportError:
            st.warning("Installing yfinance package...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance"])
            import yfinance as yf
            st.success("yfinance installed successfully")
        
        # Get historical data using yfinance
        yf_timeframe = timeframe_options[selected_timeframe]
        
        # Fetch data with error handling
        try:
            ticker_data = yf.Ticker(ticker)
            df = ticker_data.history(period=yf_timeframe)
            
            if df.empty:
                st.error(f"No historical data available for {ticker}")
                return
                
            # Reset index to make date a column
            df = df.reset_index()
            
            # Calculate technical indicators
            if "Moving Averages" in indicator_options:
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['MA50'] = df['Close'].rolling(window=50).mean()
                df['MA200'] = df['Close'].rolling(window=200).mean()
            
            if "Bollinger Bands" in indicator_options:
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['20dSTD'] = df['Close'].rolling(window=20).std()
                df['Upper'] = df['MA20'] + (df['20dSTD'] * 2)
                df['Lower'] = df['MA20'] - (df['20dSTD'] * 2)
            
            if "RSI" in indicator_options:
                delta = df['Close'].diff()
                gain = delta.where(delta > 0, 0)
                loss = -delta.where(delta < 0, 0)
                avg_gain = gain.rolling(window=14).mean()
                avg_loss = loss.rolling(window=14).mean()
                rs = avg_gain / avg_loss
                df['RSI'] = 100 - (100 / (1 + rs))
            
            if "MACD" in indicator_options:
                exp1 = df['Close'].ewm(span=12, adjust=False).mean()
                exp2 = df['Close'].ewm(span=26, adjust=False).mean()
                df['MACD'] = exp1 - exp2
                df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                df['Histogram'] = df['MACD'] - df['Signal']
            
        except Exception as e:
            st.error(f"Error fetching historical data: {str(e)}")
            logger.error(f"Historical data fetch error: {str(e)}", exc_info=True)
            return
            
        # Create the chart based on selected type
        fig = go.Figure()
        
        try:
            if chart_type == "Candlestick":
                fig.add_trace(go.Candlestick(
                    x=df['Date'],
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    name='Price'
                ))
            elif chart_type == "OHLC":
                fig.add_trace(go.Ohlc(
                    x=df['Date'],
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    name='Price'
                ))
            else:  # Line chart
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['Close'],
                    mode='lines',
                    name='Close Price',
                    line=dict(color='blue', width=2)
                ))
            
            # Add technical indicators
            if "Moving Averages" in indicator_options:
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['MA20'],
                    mode='lines',
                    name='20-day MA',
                    line=dict(color='orange', width=1)
                ))
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['MA50'],
                    mode='lines',
                    name='50-day MA',
                    line=dict(color='green', width=1)
                ))
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['MA200'],
                    mode='lines',
                    name='200-day MA',
                    line=dict(color='red', width=1)
                ))
            
            if "Bollinger Bands" in indicator_options:
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['Upper'],
                    mode='lines',
                    name='Upper Band',
                    line=dict(color='gray', width=1, dash='dash')
                ))
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['Lower'],
                    mode='lines',
                    name='Lower Band',
                    line=dict(color='gray', width=1, dash='dash'),
                    fill='tonexty'
                ))
            
            # Add volume if selected
            if show_volume:
                fig.add_trace(go.Bar(
                    x=df['Date'],
                    y=df['Volume'],
                    name='Volume',
                    marker_color='rgba(0, 0, 255, 0.3)',
                    opacity=0.3,
                    yaxis='y2'
                ))
            
            # Add support and resistance levels if selected
            if "Support/Resistance" in indicator_options:
                # Get levels from technical analysis
                sr_levels = analysis_result.get("support_resistance", {})
                
                # Add strong support levels
                for level in sr_levels.get("strong_support_levels", []):
                    fig.add_hline(
                        y=level,
                        line_dash="solid",
                        line_color="green",
                        line_width=2,
                        annotation=dict(
                            text=f"Strong Support: ${level:.2f}",
                            align="left",
                            xanchor="left",
                            yanchor="bottom"
                        )
                    )
                
                # Add weak support levels
                for level in sr_levels.get("weak_support_levels", []):
                    fig.add_hline(
                        y=level,
                        line_dash="dot",
                        line_color="lightgreen",
                        line_width=1,
                        annotation=dict(
                            text=f"Weak Support: ${level:.2f}",
                            align="left",
                            xanchor="left",
                            yanchor="bottom"
                        )
                    )
                
                # Add strong resistance levels
                for level in sr_levels.get("strong_resistance_levels", []):
                    fig.add_hline(
                        y=level,
                        line_dash="solid",
                        line_color="red",
                        line_width=2,
                        annotation=dict(
                            text=f"Strong Resistance: ${level:.2f}",
                            align="left",
                            xanchor="left",
                            yanchor="top"
                        )
                    )
                
                # Add weak resistance levels
                for level in sr_levels.get("weak_resistance_levels", []):
                    fig.add_hline(
                        y=level,
                        line_dash="dot",
                        line_color="pink",
                        line_width=1,
                        annotation=dict(
                            text=f"Weak Resistance: ${level:.2f}",
                            align="left",
                            xanchor="left",
                            yanchor="top"
                        )
                    )
            
            # Update layout
            layout_height = 600
            if "RSI" in indicator_options:
                layout_height += 200
            if "MACD" in indicator_options:
                layout_height += 200
            
            fig.update_layout(
                title=f"{ticker} Technical Analysis Chart ({selected_timeframe})",
                xaxis_title="Date",
                yaxis_title="Price ($)",
                height=layout_height,
                xaxis_rangeslider_visible=False,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            if show_volume:
                fig.update_layout(
                    yaxis2=dict(
                        title="Volume",
                        overlaying="y",
                        side="right",
                        showgrid=False
                    )
                )
            
            # Add RSI subplot if selected
            if "RSI" in indicator_options:
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['RSI'],
                    mode='lines',
                    name='RSI',
                    yaxis='y3'
                ))
                
                fig.update_layout(
                    yaxis3=dict(
                        title="RSI",
                        range=[0, 100],
                        domain=[0, 0.2]
                    )
                )
                
                # Add RSI reference lines
                fig.add_shape(
                    dict(
                        type="line",
                        y0=70, y1=70,
                        x0=df['Date'].iloc[0], x1=df['Date'].iloc[-1],
                        line=dict(color="red", width=1, dash="dash"),
                        yref='y3'
                    )
                )
                fig.add_shape(
                    dict(
                        type="line",
                        y0=30, y1=30,
                        x0=df['Date'].iloc[0], x1=df['Date'].iloc[-1],
                        line=dict(color="green", width=1, dash="dash"),
                        yref='y3'
                    )
                )
            
            # Add MACD subplot if selected
            if "MACD" in indicator_options:
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['MACD'],
                    mode='lines',
                    name='MACD',
                    yaxis='y4'
                ))
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['Signal'],
                    mode='lines',
                    name='Signal',
                    yaxis='y4'
                ))
                fig.add_trace(go.Bar(
                    x=df['Date'],
                    y=df['Histogram'],
                    name='MACD Histogram',
                    yaxis='y4'
                ))
                
                fig.update_layout(
                    yaxis4=dict(
                        title="MACD",
                        domain=[0.25, 0.45] if "RSI" in indicator_options else [0, 0.2]
                    )
                )
            
            # Display the chart
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error creating chart visualization: {str(e)}")
            logger.error(f"Chart creation error: {str(e)}", exc_info=True)
            return
            
    except Exception as e:
        st.error(f"Error in technical chart creation: {str(e)}")
        logger.error(f"Technical chart error: {str(e)}", exc_info=True)
        return

def analyze_technicals_with_llm(ticker: str, timeframe: str = "daily"):
    """
    Use LLM to analyze technical indicators and provide specific targets
    """
    try:
        # Import required packages
        import yfinance as yf
        import pandas as pd
        import numpy as np
        from datetime import datetime, timedelta
        
        # Map timeframe to yfinance interval and period
        timeframe_map = {
            "monthly": ("1mo", "2y"),
            "weekly": ("1wk", "1y"),
            "daily": ("1d", "6mo"),
            "hourly": ("1h", "1mo")
        }
        
        interval, period = timeframe_map.get(timeframe, ("1d", "6mo"))
        
        # Fetch historical data
        ticker_data = yf.Ticker(ticker)
        df = ticker_data.history(period=period, interval=interval)
        
        if df.empty:
            return {"error": f"No historical data available for {ticker}"}
            
        # Calculate technical indicators
        # RSI
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['Signal']
        
        # Bollinger Bands
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['20dSTD'] = df['Close'].rolling(window=20).std()
        df['Upper_Band'] = df['MA20'] + (df['20dSTD'] * 2)
        df['Lower_Band'] = df['MA20'] - (df['20dSTD'] * 2)
        
        # Moving Averages
        df['MA50'] = df['Close'].rolling(window=50).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()
        
        # Calculate potential support and resistance levels using price action
        pivot_high = df['High'].rolling(window=20, center=True).max()
        pivot_low = df['Low'].rolling(window=20, center=True).min()
        
        # Prepare data for LLM analysis
        current_price = float(df['Close'].iloc[-1])
        
        # Get support and resistance levels
        support_levels = sorted(set([round(float(level), 2) for level in pivot_low.dropna().unique() if level < current_price]))[-3:]
        resistance_levels = sorted(set([round(float(level), 2) for level in pivot_high.dropna().unique() if level > current_price]))[:3]
        
        technical_data = {
            "ticker": ticker,
            "timeframe": timeframe,
            "current_price": current_price,
            "last_close": float(df['Close'].iloc[-1]),
            "last_open": float(df['Open'].iloc[-1]),
            "last_high": float(df['High'].iloc[-1]),
            "last_low": float(df['Low'].iloc[-1]),
            "volume": int(df['Volume'].iloc[-1]),
            "price_change": float((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100),
            "technical_indicators": {
                "rsi": float(df['RSI'].iloc[-1]),
                "macd": {
                    "macd_line": float(df['MACD'].iloc[-1]),
                    "signal_line": float(df['Signal'].iloc[-1]),
                    "histogram": float(df['MACD_Hist'].iloc[-1])
                },
                "bollinger_bands": {
                    "upper": float(df['Upper_Band'].iloc[-1]),
                    "middle": float(df['MA20'].iloc[-1]),
                    "lower": float(df['Lower_Band'].iloc[-1])
                },
                "moving_averages": {
                    "ma20": float(df['MA20'].iloc[-1]),
                    "ma50": float(df['MA50'].iloc[-1]),
                    "ma200": float(df['MA200'].iloc[-1])
                }
            },
            "historical_data": {
                "price_range": {
                    "period_high": float(df['High'].max()),
                    "period_low": float(df['Low'].min())
                },
                "volatility": float(df['Close'].pct_change().std() * 100),
                "volume_trend": "increasing" if df['Volume'].iloc[-1] > df['Volume'].mean() else "decreasing",
                "potential_support_levels": support_levels,
                "potential_resistance_levels": resistance_levels
            }
        }
        
        # Create prompt for LLM analysis
        prompt = f"""
        You are an expert technical analyst. Analyze the following technical data for {ticker} on a {timeframe} timeframe and provide specific insights and predictions.
        
        Technical Data:
        {json.dumps(technical_data, indent=2)}
        
        Please provide a detailed technical analysis including:
        1. Current market position and trend analysis
        2. Specific support and resistance levels with confidence levels
        3. RSI analysis and potential reversal points
        4. MACD signal interpretation and potential crossovers
        5. Bollinger Bands analysis and volatility assessment
        6. Moving average analysis and potential crossovers
        7. Volume analysis and its implications
        8. Specific price targets for both upside and downside scenarios
        9. Risk assessment and optimal stop-loss levels
        10. Time projection for target achievement
        
        Format your response as a JSON object with the following structure:
        {{
            "trend_analysis": {{
                "primary_trend": "bullish|bearish|neutral",
                "trend_strength": 0-100,
                "trend_duration": "string"
            }},
            "support_resistance": {{
                "strong_support_levels": [float],
                "weak_support_levels": [float],
                "strong_resistance_levels": [float],
                "weak_resistance_levels": [float],
                "confidence_scores": {{
                    "support": 0-100,
                    "resistance": 0-100
                }}
            }},
            "indicator_analysis": {{
                "rsi": {{
                    "condition": "overbought|oversold|neutral",
                    "value": float,
                    "interpretation": "string"
                }},
                "macd": {{
                    "signal": "bullish|bearish|neutral",
                    "strength": 0-100,
                    "next_crossover": "string"
                }},
                "bollinger_bands": {{
                    "position": "upper|middle|lower",
                    "bandwidth": float,
                    "squeeze_potential": bool
                }}
            }},
            "price_targets": {{
                "short_term": {{
                    "timeframe": "string",
                    "bullish_target": float,
                    "bearish_target": float,
                    "confidence": 0-100
                }},
                "medium_term": {{
                    "timeframe": "string",
                    "bullish_target": float,
                    "bearish_target": float,
                    "confidence": 0-100
                }}
            }},
            "risk_assessment": {{
                "optimal_stop_loss": float,
                "risk_reward_ratio": float,
                "volatility_risk": "low|medium|high",
                "key_risk_factors": [string]
            }},
            "summary": "string",
            "confidence_score": 0-100
        }}
        """
        
        try:
            # Use Gemini for analysis
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
            
            response = model.generate_content(prompt)
            
            try:
                analysis_result = json.loads(response.text)
                analysis_result["technical_data"] = technical_data
                return analysis_result
            except json.JSONDecodeError:
                return {
                    "error": "Failed to parse LLM response",
                    "raw_response": response.text
                }
        except Exception as e:
            logger.error(f"Error calling Gemini API: {str(e)}")
            return {"error": f"Error calling Gemini API: {str(e)}"}
            
    except Exception as e:
        logger.error(f"Error in technical analysis: {str(e)}", exc_info=True)
        return {"error": f"Technical analysis error: {str(e)}"}

def display_technical_analysis(analysis_result: dict):
    """Display the technical analysis results in a structured format"""
    if "error" in analysis_result:
        st.error(f"Error in technical analysis: {analysis_result['error']}")
        if "raw_response" in analysis_result:
            with st.expander("Raw LLM Response"):
                st.code(analysis_result["raw_response"])
        return
    
    # Trend Analysis
    st.subheader("Trend Analysis")
    trend = analysis_result.get("trend_analysis", {})
    col1, col2, col3 = st.columns(3)
    
    with col1:
        primary_trend = trend.get("primary_trend", "neutral")
        trend_color = {
            "bullish": "green",
            "bearish": "red",
            "neutral": "blue"
        }.get(primary_trend.lower(), "blue")
        st.markdown(f"**Primary Trend**: <span style='color:{trend_color}'>{primary_trend.upper()}</span>", unsafe_allow_html=True)
    
    with col2:
        st.metric("Trend Strength", f"{trend.get('trend_strength', 0)}%")
    
    with col3:
        st.write("**Duration:**", trend.get("trend_duration", "N/A"))
    
    # Support and Resistance
    st.subheader("Support and Resistance Levels")
    sr_levels = analysis_result.get("support_resistance", {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Strong Support Levels:**")
        for level in sr_levels.get("strong_support_levels", []):
            st.markdown(f"- ${level:.2f}")
        
        st.write("**Weak Support Levels:**")
        for level in sr_levels.get("weak_support_levels", []):
            st.markdown(f"- ${level:.2f}")
    
    with col2:
        st.write("**Strong Resistance Levels:**")
        for level in sr_levels.get("strong_resistance_levels", []):
            st.markdown(f"- ${level:.2f}")
        
        st.write("**Weak Resistance Levels:**")
        for level in sr_levels.get("weak_resistance_levels", []):
            st.markdown(f"- ${level:.2f}")
    
    # Confidence Scores
    confidence = sr_levels.get("confidence_scores", {})
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Support Confidence", f"{confidence.get('support', 0)}%")
    with col2:
        st.metric("Resistance Confidence", f"{confidence.get('resistance', 0)}%")
    
    # Technical Indicators
    st.subheader("Technical Indicators")
    
    # RSI
    rsi_data = analysis_result.get("indicator_analysis", {}).get("rsi", {})
    st.write("**RSI Analysis**")
    col1, col2 = st.columns(2)
    with col1:
        condition = rsi_data.get("condition", "neutral")
        condition_color = {
            "overbought": "red",
            "oversold": "green",
            "neutral": "blue"
        }.get(condition.lower(), "blue")
        st.markdown(f"Condition: <span style='color:{condition_color}'>{condition.upper()}</span>", unsafe_allow_html=True)
        st.metric("RSI Value", f"{rsi_data.get('value', 0):.2f}")
    with col2:
        st.write("Interpretation:", rsi_data.get("interpretation", "N/A"))
    
    # MACD
    macd_data = analysis_result.get("indicator_analysis", {}).get("macd", {})
    st.write("**MACD Analysis**")
    col1, col2, col3 = st.columns(3)
    with col1:
        signal = macd_data.get("signal", "neutral")
        signal_color = {
            "bullish": "green",
            "bearish": "red",
            "neutral": "blue"
        }.get(signal.lower(), "blue")
        st.markdown(f"Signal: <span style='color:{signal_color}'>{signal.upper()}</span>", unsafe_allow_html=True)
    with col2:
        st.metric("Signal Strength", f"{macd_data.get('strength', 0)}%")
    with col3:
        st.write("Next Crossover:", macd_data.get("next_crossover", "N/A"))
    
    # Bollinger Bands
    bb_data = analysis_result.get("indicator_analysis", {}).get("bollinger_bands", {})
    st.write("**Bollinger Bands Analysis**")
    col1, col2 = st.columns(2)
    with col1:
        st.write("Position:", bb_data.get("position", "N/A"))
        st.metric("Bandwidth", f"{bb_data.get('bandwidth', 0):.2f}")
    with col2:
        squeeze = bb_data.get("squeeze_potential", False)
        st.write("Squeeze Potential:", "Yes" if squeeze else "No")
    
    # Price Targets
    st.subheader("Price Targets")
    
    # Short Term
    st.write("**Short Term Targets**")
    short_term = analysis_result.get("price_targets", {}).get("short_term", {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Bullish Target", f"${short_term.get('bullish_target', 0):.2f}")
    with col2:
        st.metric("Bearish Target", f"${short_term.get('bearish_target', 0):.2f}")
    with col3:
        st.metric("Confidence", f"{short_term.get('confidence', 0)}%")
    st.write("Timeframe:", short_term.get("timeframe", "N/A"))
    
    # Medium Term
    st.write("**Medium Term Targets**")
    medium_term = analysis_result.get("price_targets", {}).get("medium_term", {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Bullish Target", f"${medium_term.get('bullish_target', 0):.2f}")
    with col2:
        st.metric("Bearish Target", f"${medium_term.get('bearish_target', 0):.2f}")
    with col3:
        st.metric("Confidence", f"{medium_term.get('confidence', 0)}%")
    st.write("Timeframe:", medium_term.get("timeframe", "N/A"))
    
    # Risk Assessment
    st.subheader("Risk Assessment")
    risk_data = analysis_result.get("risk_assessment", {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Optimal Stop Loss", f"${risk_data.get('optimal_stop_loss', 0):.2f}")
    with col2:
        st.metric("Risk/Reward Ratio", f"{risk_data.get('risk_reward_ratio', 0):.2f}")
    with col3:
        volatility = risk_data.get("volatility_risk", "medium")
        volatility_color = {
            "low": "green",
            "medium": "blue",
            "high": "red"
        }.get(volatility.lower(), "blue")
        st.markdown(f"Volatility Risk: <span style='color:{volatility_color}'>{volatility.upper()}</span>", unsafe_allow_html=True)
    
    st.write("**Key Risk Factors:**")
    for factor in risk_data.get("key_risk_factors", []):
        st.markdown(f"- {factor}")
    
    # Summary
    st.subheader("Analysis Summary")
    st.write(analysis_result.get("summary", "No summary available"))
    st.metric("Overall Confidence Score", f"{analysis_result.get('confidence_score', 0)}%")

def main():
    # Set page config
    st.set_page_config(
        page_title="AI-Powered Market Analysis Dashboard",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Add custom CSS
    st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.2rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("AI-Powered Market Analysis")
    
    # Ticker input
    ticker = st.sidebar.text_input("Enter Stock Ticker", "AAPL").upper()
    
    # Risk tolerance selection
    risk_tolerance = st.sidebar.selectbox(
        "Select Risk Tolerance",
        ["low", "medium", "high"],
        index=1  # Default to medium
    )
    
    # Analysis type selection
    analysis_type = st.sidebar.selectbox(
        "Select Analysis Type",
        ["basic", "comprehensive"],
        index=1  # Default to comprehensive
    )
    
    # Use feedback loop checkbox
    use_feedback_loop = st.sidebar.checkbox("Use Feedback Loop", value=True)
    
    # Clear cache button
    if st.sidebar.button("Clear Analysis Cache"):
        # Reset all session state variables related to analysis
        st.session_state.market_data = {}
        st.session_state.options_data = {}
        st.session_state.analysis_result = {}
        st.session_state.enhanced_analysis_result = {}
        st.session_state.memory_analysis_result = {}
        st.session_state.historical_analyses = []
        st.session_state.analysis_completed = False
        st.session_state.last_analysis_time = None
        st.sidebar.success("Analysis cache cleared!")
    
    # Run analysis button
    run_analysis = st.sidebar.button("Run Analysis")
    
    # Check if we need to run a new analysis
    need_new_analysis = run_analysis or (ticker != st.session_state.current_ticker)
    
    # Main content
    st.title("AI-Powered Market Analysis Dashboard")
    
    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Options Analysis", 
        "Enhanced Analysis", 
        "Memory-Enhanced Analysis", 
        "Technical Chart",
        "LLM Technical Analysis"
    ])
    
    # Run analysis if needed
    if need_new_analysis:
        with st.spinner(f"Fetching market data for {ticker}..."):
            # Fetch market data
            market_data = fetch_market_data(ticker)
            st.session_state.market_data = market_data
            st.session_state.current_ticker = ticker
        
        # Check if market_data is not None and doesn't have an error
        if market_data is not None and "error" not in market_data:
            with st.spinner(f"Fetching options data for {ticker}..."):
                # Prepare options data for Gemini
                options_data = prepare_gemini_input(market_data, ticker)
                st.session_state.options_data = options_data
            
            with st.spinner(f"Analyzing {ticker} with Gemini..."):
                # Analyze with Gemini
                analysis_result = analyze_with_gemini(ticker, options_data, risk_tolerance)
                st.session_state.analysis_result = analysis_result
            
            with st.spinner(f"Running enhanced analysis for {ticker}..."):
                # Run enhanced analysis
                pipeline = EnhancedAnalysisPipeline(use_feedback_loop=use_feedback_loop)
                enhanced_result = pipeline.analyze_tickers([ticker], analysis_type)
                st.session_state.enhanced_analysis_result = enhanced_result
            
            with st.spinner(f"Running memory-enhanced analysis for {ticker}..."):
                # Initialize memory analyzer
                try:
                    memory_analyzer = MemoryEnhancedAnalysis()
                    memory_result = memory_analyzer.analyze_ticker_with_memory(
                        ticker, 
                        analysis_type=analysis_type,
                        risk_tolerance=risk_tolerance
                    )
                    historical_analyses = memory_analyzer.get_analysis_history(ticker)
                    
                    st.session_state.memory_analysis_result = memory_result
                    st.session_state.historical_analyses = historical_analyses
                except Exception as e:
                    st.error(f"Failed to initialize memory analyzer: {str(e)}")
                    st.session_state.memory_analysis_result = {"error": str(e)}
                    st.session_state.historical_analyses = []
            
            # Mark analysis as completed and store timestamp
            st.session_state.analysis_completed = True
            st.session_state.last_analysis_time = datetime.now()
        else:
            # Handle the case where market_data is None or has an error
            error_message = "No data available" if market_data is None else market_data.get("error", "Unknown error")
            st.error(f"Error fetching market data for {ticker}: {error_message}")
            st.session_state.analysis_completed = False
    
    # Display analysis results in tabs
    with tab1:
        if st.session_state.analysis_completed:
            display_llm_options_analysis(st.session_state.analysis_result, ticker)
        else:
            st.info("Run an analysis to see options data.")
    
    with tab2:
        if st.session_state.analysis_completed:
            display_enhanced_analysis(st.session_state.enhanced_analysis_result)
        else:
            st.info("Run an analysis to see enhanced analysis results.")
    
    with tab3:
        if st.session_state.analysis_completed:
            display_memory_enhanced_analysis(ticker, st.session_state.memory_analysis_result, st.session_state.historical_analyses)
        else:
            st.info("Run an analysis to see memory-enhanced analysis results.")
    
    with tab4:
        if st.session_state.analysis_completed:
            create_technical_chart(ticker, st.session_state.market_data, st.session_state.enhanced_analysis_result)
        else:
            st.info("Run an analysis to see technical chart.")
    
    # Add the new tab content
    with tab5:
        if st.session_state.analysis_completed:
            # Add timeframe selection
            timeframe = st.selectbox(
                "Select Analysis Timeframe",
                ["monthly", "weekly", "daily", "hourly"],
                index=2  # Default to daily
            )
            
            # Run technical analysis
            with st.spinner(f"Performing {timeframe} technical analysis for {ticker}..."):
                technical_analysis = analyze_technicals_with_llm(ticker, timeframe)
                display_technical_analysis(technical_analysis)
        else:
            st.info("Run an analysis to see LLM-powered technical analysis.")
    
    # Display last analysis time if available
    if st.session_state.last_analysis_time:
        st.sidebar.markdown(f"**Last analysis:** {st.session_state.last_analysis_time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main() 