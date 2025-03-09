import streamlit as st

# Set page config - must be the first Streamlit command
st.set_page_config(
    page_title="Options Analysis Dashboard",
    page_icon="📈",
    layout="wide"
)

import pandas as pd
import os
import sys
import subprocess
import logging
import http.client
import json
from datetime import datetime, timedelta

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath('.'))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flag to track if plotly is available
plotly_available = False

# Check if plotly is installed
try:
    import plotly.graph_objects as go
    import plotly.express as px
    plotly_available = True
    logger.info("Plotly is already installed")
except ImportError:
    logger.warning("Plotly is not available, will use alternative visualizations")
    st.warning("Plotly is not available. Some visualizations will be limited.")
    
# Check if Google Generative AI is installed
gemini_available = False
try:
    import google.generativeai as genai
    # Create a types module if it doesn't exist
    try:
        import google.generativeai.types as types
    except ImportError:
        # Create a simple types module as a fallback
        class SimpleTypes:
            class GenerationConfig:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)
        
        # Add the SimpleTypes to the genai module
        genai.types = SimpleTypes()
        
    gemini_available = True
    logger.info("Google Generative AI is already installed")
except ImportError:
    logger.error("Google Generative AI package not found")
    st.error("Required package 'google.generativeai' is not available. Some features will be limited.")
    
from dotenv import load_dotenv

# Try to import the enhanced analysis pipeline
try:
    from src.analysis.enhanced_analysis_pipeline import EnhancedAnalysisPipeline
    pipeline_available = True
    logger.info("Enhanced analysis pipeline is available")
except ImportError as e:
    pipeline_available = False
    logger.error(f"Enhanced analysis pipeline module not found: {e}")
    # Print the Python path for debugging
    logger.error(f"Python path: {sys.path}")
    # Check if the file exists
    file_path = os.path.join('src', 'analysis', 'enhanced_analysis_pipeline.py')
    if os.path.exists(file_path):
        logger.info(f"File exists: {file_path}")
    else:
        logger.error(f"File does not exist: {file_path}")
    # List the contents of the src/analysis directory
    analysis_dir = os.path.join('src', 'analysis')
    if os.path.exists(analysis_dir):
        logger.info(f"Contents of {analysis_dir}: {os.listdir(analysis_dir)}")
    else:
        logger.error(f"Directory does not exist: {analysis_dir}")
    st.error("Required module 'src.analysis.enhanced_analysis_pipeline' is not available. Some features will be limited.")

# Load environment variables from multiple sources
load_dotenv()  # First try loading from .env file

# Then try loading from Streamlit secrets if available
try:
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
except FileNotFoundError as e:
    logger.warning(f"No secrets file found: {str(e)}")
    st.warning("No secrets file found. Using environment variables from .env file or system environment.")
except Exception as e:
    logger.error(f"Error loading secrets: {str(e)}")
    st.error(f"Error loading secrets: {str(e)}")

# Check for required environment variables
required_vars = ['OPENAI_API_KEY', 'GOOGLE_API_KEY']
missing_vars = [var for var in required_vars if not os.environ.get(var)]
if missing_vars:
    logger.warning(f"Missing required environment variables: {', '.join(missing_vars)}")
    st.error(f"Missing required environment variables: {', '.join(missing_vars)}")

# Initialize Google Generative AI with API key if available
if gemini_available:
    try:
        genai.configure(api_key=os.environ.get('GOOGLE_API_KEY'))
        logger.info("Successfully configured Google Generative AI")
    except Exception as e:
        logger.error(f"Failed to configure Google Generative AI: {str(e)}")
        st.error(f"Failed to configure Google Generative AI: {str(e)}")

def fetch_market_data(ticker):
    """Fetch market data from RapidAPI Yahoo Finance"""
    conn = http.client.HTTPSConnection("yahoo-finance166.p.rapidapi.com")
    
    headers = {
        'x-rapidapi-key': os.getenv("RAPIDAPI_KEY"),
        'x-rapidapi-host': "yahoo-finance166.p.rapidapi.com"
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
        logger.error(f"JSON decode error: {str(e)}")
        return {"error": "Failed to decode JSON response", "raw_response": data.decode('utf-8')}
    except Exception as e:
        logger.error(f"Error fetching market data: {str(e)}")
        return {"error": str(e)}

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
    # Check if Gemini is available
    if not gemini_available:
        return {
            "error": "Google Generative AI package is not available. Please install it to use this feature.",
            "overall_sentiment": "neutral",
            "confidence": 0,
            "reasoning": "Dependency missing"
        }
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "error": "Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.",
            "overall_sentiment": "neutral",
            "confidence": 0,
            "reasoning": "API key missing"
        }

    # Check if we have valid options data
    if option_chain_data.get("error"):
        return {
            "error": option_chain_data.get("error"),
            "overall_sentiment": "neutral",
            "confidence": 0,
            "reasoning": "Insufficient data for analysis"
        }

    # Initialize Gemini client
    genai.configure(api_key=api_key)

    prompt = f"""
Analyze the following options data for {ticker} and recommend an optimal options trading strategy based on a {risk_tolerance} risk tolerance level.

Option Chain Data:
{json.dumps(option_chain_data, indent=2)}

Specifically, please:

1. Analyze the current market conditions, paying close attention to the differences in implied volatility between call and put options, and the volume and open interest data. Provide a detailed analysis of how these factors influence your strategy recommendation.

2. Calculate the Put/Call Ratio as follows:
   - Sum the 'volume' values for all put options in the 'options_sample' data.
   - Sum the 'volume' values for all call options in the 'options_sample' data.
   - Divide the put volume by the call volume.
   - Interpret this ratio: values above 1 indicate bearish sentiment, values below 1 indicate bullish sentiment.

3. Recommend specific options strategies appropriate for the current market conditions and the {risk_tolerance} risk tolerance level.

4. For each recommended strategy, explain:
   - The specific options to buy/sell (strike prices and expiration dates)
   - The maximum potential profit and loss
   - The break-even point(s)
   - The ideal market conditions for this strategy
   - The exit strategy (when to exit the position)

5. Provide a confidence level (0-100%) for your recommendation and explain your reasoning.

Format your response as a JSON object with the following structure:
{{
  "ticker": "{ticker}",
  "analysis_date": "current date",
  "market_conditions": {{
    "implied_volatility_analysis": "detailed analysis of IV",
    "put_call_ratio": "calculated ratio and interpretation",
    "overall_sentiment": "bullish/bearish/neutral",
    "key_observations": ["list of important observations"]
  }},
  "recommended_strategies": [
    {{
      "strategy_name": "name of strategy",
      "description": "brief description",
      "implementation": "specific options to trade",
      "max_profit": "maximum potential profit",
      "max_loss": "maximum potential loss",
      "break_even": "break-even point(s)",
      "ideal_conditions": "when this strategy works best",
      "exit_strategy": "when to exit the position",
      "risk_level": "low/medium/high"
    }}
  ],
  "confidence": "confidence level (0-100%)",
  "reasoning": "detailed explanation of your recommendation"
}}
"""

    try:
        # Create a generation config
        generation_config = genai.types.GenerationConfig(
            temperature=0.2,
            top_p=0.8,
            top_k=40,
            max_output_tokens=2048,
        )
        
        # Generate content
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(prompt, generation_config=generation_config)
        
        # Extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            return result
        else:
            return {
                "error": "Could not extract JSON from Gemini response",
                "overall_sentiment": "neutral",
                "confidence": 0,
                "reasoning": "Error in response format"
            }
    except Exception as e:
        logger.error(f"Error in Gemini analysis: {str(e)}")
        return {
            "error": f"Error in Gemini analysis: {str(e)}",
            "overall_sentiment": "neutral",
            "confidence": 0,
            "reasoning": "Error during analysis"
        }

def display_market_overview(market_data, ticker):
    """Display market overview section"""
    st.subheader("Market Overview")
    
    # Check for API errors
    if "error" in market_data:
        st.error(f"Error fetching market data: {market_data.get('error')}")
        with st.expander("Raw API Response"):
            st.code(market_data.get("raw_response", "No raw response available"))
        return 0  # Return default price of 0 if there's an error
    
    # Debug: Show raw data
    with st.expander("Raw Market Data"):
        st.json(market_data)
    
    # Get current price directly if available
    current_price = market_data.get("current_price", 0)
    
    # Extract quote data
    quote_summary = market_data.get("quoteSummary", {})
    result = quote_summary.get("result", [{}])[0] if quote_summary.get("result") else {}
    price = result.get("price", {})
    
    # If current_price is not set directly, try to get it from price data
    if not current_price and price:
        current_price = price.get("regularMarketPrice", {}).get("raw", 0)
    
    # Create columns for key metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Price",
            f"${current_price:.2f}",
            f"{price.get('regularMarketChangePercent', {}).get('raw', 0):.2f}%"
        )
    
    with col2:
        st.metric(
            "Volume",
            f"{price.get('regularMarketVolume', {}).get('raw', 0):,}",
            f"Avg: {price.get('averageDailyVolume10Day', {}).get('raw', 0):,}"
        )
    
    with col3:
        market_cap = price.get('marketCap', {}).get('raw', 0)
        st.metric(
            "Market Cap",
            f"${market_cap/1e9:.2f}B" if market_cap else "N/A",
            ""
        )
    
    # Additional market information if available
    summary_detail = result.get("summaryDetail", {})
    if summary_detail:
        st.subheader("Key Statistics")
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("52 Week Range", 
                    f"${summary_detail.get('fiftyTwoWeekLow', {}).get('raw', 0):.2f} - ${summary_detail.get('fiftyTwoWeekHigh', {}).get('raw', 0):.2f}")
            
            trailing_pe = summary_detail.get('trailingPE', {}).get('raw', 0)
            st.metric("PE Ratio (TTM)", 
                    f"{trailing_pe:.2f}" if trailing_pe else "N/A")
        
        with col2:
            dividend_yield = summary_detail.get('dividendYield', {}).get('raw', 0)
            st.metric("Dividend Yield", 
                    f"{dividend_yield*100:.2f}%" if dividend_yield else "N/A")
            
            beta = summary_detail.get('beta', {}).get('raw', 0)
            st.metric("Beta", 
                    f"{beta:.2f}" if beta else "N/A")
    
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
        st.metric("Put-Call Ratio", f"{market_conditions.get('put_call_ratio', 0):.2f}")
        st.metric("IV Skew", f"{market_conditions.get('implied_volatility_skew', 0):.2f}")
    
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
                "Strike": f"${leg.get('strike', 0):.2f}",
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

def main():
    st.title("AI-Powered Market Analysis Dashboard")
    
    # Check for required dependencies
    missing_dependencies = []
    if not gemini_available:
        missing_dependencies.append("Google Generative AI")
    if not pipeline_available:
        missing_dependencies.append("Enhanced Analysis Pipeline")
    
    if missing_dependencies:
        st.error(f"Missing required dependencies: {', '.join(missing_dependencies)}")
        st.info("The app will run with limited functionality. Please contact the administrator to install the required packages.")
    
    # Sidebar
    st.sidebar.header("Settings")
    ticker = st.sidebar.text_input("Enter Ticker Symbol", value="AAPL").upper()
    
    risk_tolerance = st.sidebar.selectbox(
        "Risk Tolerance",
        ["low", "medium", "high"],
        index=1
    )
    
    analysis_type = st.sidebar.selectbox(
        "Analysis Type",
        ["basic", "technical", "fundamental", "comprehensive"],
        index=3
    )
    
    use_feedback_loop = st.sidebar.checkbox("Use Feedback Loop", value=True)
    
    analyze_button = st.sidebar.button("Analyze")
    
    # Check for API keys
    api_key = os.getenv("RAPIDAPI_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        st.sidebar.error("Quant_KEY not found in environment variables")
    else:
        st.sidebar.success(f"Quant-API Key: {api_key[:5]}...{api_key[-5:]}")
    
    if not gemini_key:
        st.sidebar.error("LLM_API_KEY not found in environment variables")
    else:
        st.sidebar.success(f"LLM API Key: {gemini_key[:5]}...{gemini_key[-5:]}")
    
    # Create tabs
    tab1, tab2 = st.tabs(["Options Analysis", "Enhanced Analysis"])
    
    if analyze_button:
        try:
            with st.spinner(f"Fetching data for {ticker}..."):
                # Fetch market data
                market_data = fetch_market_data(ticker)
                
                with tab1:
                    current_price = display_market_overview(market_data, ticker)
                    
                    if "error" in market_data:
                        st.error(f"Error fetching market data: {market_data.get('error')}")
                    else:
                        # Prepare data for Gemini
                        with st.spinner("Preparing options data for analysis..."):
                            gemini_input = prepare_gemini_input(market_data, ticker)
                            
                            if "error" in gemini_input:
                                st.error(f"Error preparing options data: {gemini_input.get('error')}")
                            else:
                                # Show prepared data
                                with st.expander("Prepared Options Data"):
                                    st.json(gemini_input)
                                
                                # Run LLM analysis if available
                                if gemini_available:
                                    with st.spinner("Analyzing options with LLM..."):
                                        analysis_result = analyze_with_gemini(ticker, gemini_input, risk_tolerance)
                                        
                                        # Display LLM analysis
                                        display_llm_options_analysis(analysis_result, ticker)
                                else:
                                    st.warning("Google Generative AI is not available. Options analysis cannot be performed.")
                
                with tab2:
                    if pipeline_available:
                        with st.spinner("Running enhanced analysis..."):
                            # Create enhanced analysis pipeline
                            pipeline = EnhancedAnalysisPipeline(use_feedback_loop=use_feedback_loop)
                            
                            # Run enhanced analysis
                            enhanced_analysis = pipeline.analyze_tickers([ticker], analysis_type)
                            
                            # Display enhanced analysis
                            display_enhanced_analysis(enhanced_analysis)
                            
                            # Display learning summary if feedback loop is enabled
                            if use_feedback_loop:
                                learning_db = pipeline.get_learning_database()
                                if not learning_db.empty:
                                    st.subheader("Learning Summary")
                                    
                                    # Get and display learning summary
                                    learning_summary = pipeline.get_learning_summary()
                                    
                                    # Create bar chart
                                    categories = list(learning_summary.keys())
                                    counts = list(learning_summary.values())
                                    
                                    if plotly_available:
                                        # Use plotly if available
                                        fig = go.Figure(data=[
                                            go.Bar(
                                                x=categories,
                                                y=counts,
                                                text=counts,
                                                textposition='auto',
                                            )
                                        ])
                                        
                                        fig.update_layout(
                                            title="Learning Points by Category",
                                            xaxis_title="Category",
                                            yaxis_title="Count",
                                            showlegend=False
                                        )
                                        
                                        st.plotly_chart(fig)
                                    else:
                                        # Fallback to Streamlit's built-in chart
                                        st.subheader("Learning Points by Category")
                                        chart_data = pd.DataFrame({
                                            'Category': categories,
                                            'Count': counts
                                        })
                                        st.bar_chart(chart_data, x='Category', y='Count')
                    else:
                        st.warning("Enhanced Analysis Pipeline is not available. Enhanced analysis cannot be performed.")
                
        except Exception as e:
            st.error(f"Error in analysis: {str(e)}")
            logger.error(f"Error in main: {str(e)}", exc_info=True)
            
            # Show detailed error information
            with st.expander("Error Details"):
                import traceback
                st.code(traceback.format_exc())

if __name__ == "__main__":
    main() 