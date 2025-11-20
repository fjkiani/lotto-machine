import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import os
import logging
import http.client
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def fetch_market_data(ticker):
    """Fetch market data from Yahoo Finance API"""
    try:
        # Use the options API to get basic market data
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
                    "current_price": quote.get("regularMarketPrice", 0)
                }
            
            return {"error": "No market data available in the response"}
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return {"error": "Failed to decode JSON response", "raw_response": data.decode('utf-8')}
    except Exception as e:
        logger.error(f"Error fetching market data: {str(e)}")
        return {"error": str(e)}

def fetch_options_data(ticker):
    """Fetch options data from RapidAPI Yahoo Finance"""
    conn = http.client.HTTPSConnection("yahoo-finance166.p.rapidapi.com")
    
    headers = {
        'x-rapidapi-key': os.getenv("RAPIDAPI_KEY"),
        'x-rapidapi-host': "yahoo-finance166.p.rapidapi.com"
    }
    
    endpoint = f"/api/stock/get-options?region=US&symbol={ticker}"
    logger.info(f"Fetching options data from endpoint: {endpoint}")
    
    conn.request("GET", endpoint, headers=headers)
    
    res = conn.getresponse()
    status = res.status
    data = res.read()
    
    logger.info(f"Options data API response status: {status}")
    
    if status != 200:
        logger.error(f"API error: {status} - {data.decode('utf-8')}")
        return {"error": f"API returned status {status}", "raw_response": data.decode('utf-8')}
    
    try:
        json_data = json.loads(data.decode("utf-8"))
        logger.info(f"Options data keys: {list(json_data.keys())}")
        return json_data
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return {"error": "Failed to decode JSON response", "raw_response": data.decode('utf-8')}

def prepare_options_data(api_data, ticker):
    """Prepare options data for analysis"""
    logger.info(f"Preparing options data for {ticker}")
    
    # Debug: Log the entire API response structure
    logger.info(f"API response keys: {list(api_data.keys())}")
    
    # Extract option chain data
    option_chain = api_data.get("optionChain", {})
    logger.info(f"Option chain keys: {list(option_chain.keys())}")
    
    result = option_chain.get("result", [])
    logger.info(f"Result length: {len(result)}")
    
    if not result or len(result) == 0:
        logger.error("No result data in API response")
        return {"error": "No options data available from API"}
    
    # Log the structure of the first result
    logger.info(f"First result keys: {list(result[0].keys())}")
    
    # Get expiration dates
    expirations = result[0].get("expirationDates", [])
    logger.info(f"Expiration dates: {expirations}")
    
    if not expirations:
        logger.error("No expiration dates in API response")
        return {"error": "No expiration dates available"}
    
    # Get options for each expiration
    options_data = {"options": []}
    
    # Get options chain data
    option_chain_data = result[0].get("options", [])
    logger.info(f"Option chain data length: {len(option_chain_data)}")
    
    if not option_chain_data:
        logger.error("No options data in API response")
        return {"error": "No options chain data available"}
    
    # Log the structure of the first option chain data
    if option_chain_data:
        logger.info(f"First option chain data keys: {list(option_chain_data[0].keys())}")
        
        # Check for straddles
        straddles = option_chain_data[0].get("straddles", [])
        logger.info(f"First expiration straddles count: {len(straddles)}")
        
        # Log sample straddle if available
        if straddles:
            logger.info(f"Sample straddle keys: {list(straddles[0].keys())}")
            
            # Check for call and put in straddle
            sample_straddle = straddles[0]
            if "call" in sample_straddle:
                logger.info(f"Sample call keys: {list(sample_straddle['call'].keys())}")
            if "put" in sample_straddle:
                logger.info(f"Sample put keys: {list(sample_straddle['put'].keys())}")
    
    # Process each expiration date's options
    for option_date in option_chain_data:
        exp_timestamp = option_date.get("expirationDate")
        logger.info(f"Processing expiration date: {exp_timestamp}")
        
        # Get straddles for this expiration
        straddles = option_date.get("straddles", [])
        logger.info(f"Straddles count: {len(straddles)}")
        
        if not straddles:
            logger.warning(f"No straddles for expiration date: {exp_timestamp}")
            continue
        
        # Extract calls and puts from straddles
        calls = []
        puts = []
        
        for straddle in straddles:
            if "call" in straddle and straddle["call"]:
                calls.append(straddle["call"])
            if "put" in straddle and straddle["put"]:
                puts.append(straddle["put"])
        
        logger.info(f"Extracted calls count: {len(calls)}, puts count: {len(puts)}")
        
        # Skip if no calls or puts
        if not calls and not puts:
            logger.warning(f"No calls or puts extracted for expiration date: {exp_timestamp}")
            continue
        
        # Add to options data
        options_data["options"].append({
            "expirationDate": exp_timestamp,
            "calls": calls,
            "puts": puts
        })
    
    if not options_data["options"]:
        logger.error("No valid options data extracted")
        return {"error": "No valid options data could be extracted"}
    
    logger.info(f"Successfully prepared options data with {len(options_data['options'])} expiration dates")
    return options_data

def calculate_implied_volatility_surface(options_data):
    """Calculate implied volatility surface from options data"""
    if "options" not in options_data or not options_data["options"]:
        return None
    
    # Collect all strikes and implied volatilities
    surface_data = []
    
    for option_date in options_data["options"]:
        exp_date = datetime.fromtimestamp(option_date["expirationDate"]).strftime('%Y-%m-%d')
        days_to_expiry = (datetime.strptime(exp_date, '%Y-%m-%d') - datetime.now()).days
        
        # Process calls
        for call in option_date.get("calls", []):
            if "strike" in call and "impliedVolatility" in call:
                surface_data.append({
                    "strike": call["strike"],
                    "days_to_expiry": days_to_expiry,
                    "impliedVolatility": call["impliedVolatility"],
                    "type": "call"
                })
        
        # Process puts
        for put in option_date.get("puts", []):
            if "strike" in put and "impliedVolatility" in put:
                surface_data.append({
                    "strike": put["strike"],
                    "days_to_expiry": days_to_expiry,
                    "impliedVolatility": put["impliedVolatility"],
                    "type": "put"
                })
    
    return pd.DataFrame(surface_data)

def calculate_put_call_ratio(options_data):
    """Calculate put-call ratio from options data"""
    if "options" not in options_data or not options_data["options"]:
        return None
    
    total_call_volume = 0
    total_put_volume = 0
    
    for option_date in options_data["options"]:
        # Sum call volumes
        for call in option_date.get("calls", []):
            if "volume" in call and call["volume"] is not None:
                total_call_volume += call["volume"]
        
        # Sum put volumes
        for put in option_date.get("puts", []):
            if "volume" in put and put["volume"] is not None:
                total_put_volume += put["volume"]
    
    if total_call_volume > 0:
        return total_put_volume / total_call_volume
    return None

def analyze_options_strategies(options_data, market_price):
    """Analyze options data to recommend strategies"""
    if "options" not in options_data or not options_data["options"]:
        logger.warning("No options data available for strategy analysis")
        return []
    
    # Ensure market_price is a number
    current_price = float(market_price) if market_price is not None else 0
    if current_price <= 0:
        logger.warning(f"Invalid market price for strategy analysis: {market_price}")
        return []
    
    strategies = []
    
    try:
        # Get the nearest expiration date
        if options_data["options"]:
            nearest_exp = options_data["options"][0]
            exp_date = datetime.fromtimestamp(nearest_exp["expirationDate"]).strftime('%Y-%m-%d')
            logger.info(f"Analyzing strategies for expiration date: {exp_date}")
            
            # Find ATM calls and puts
            calls = nearest_exp.get("calls", [])
            puts = nearest_exp.get("puts", [])
            
            if not calls or not puts:
                logger.warning("Missing calls or puts data for strategy analysis")
                return []
            
            # Find closest strike to current price
            calls_df = pd.DataFrame(calls)
            puts_df = pd.DataFrame(puts)
            
            if "strike" not in calls_df.columns:
                logger.warning("Strike price data missing in calls")
                return []
            
            # Log available columns for debugging
            logger.info(f"Available columns in calls data: {list(calls_df.columns)}")
            logger.info(f"Available columns in puts data: {list(puts_df.columns)}")
            
            # Find ATM strike (closest to current price)
            atm_strike = calls_df["strike"].iloc[(calls_df["strike"] - current_price).abs().argsort()[0]]
            logger.info(f"ATM strike price: {atm_strike} (current price: {current_price})")
            
            # Basic strategies that don't require implied volatility
            strategies.append({
                "name": "Covered Call",
                "description": f"Buy the stock and sell an ATM or OTM call at strike {atm_strike}",
                "outlook": "Neutral to Slightly Bullish",
                "risk_level": "Low",
                "potential_profit": "Limited to strike price minus current price plus premium",
                "max_loss": "Limited to stock price minus premium received",
                "break_even": f"Stock price minus premium received"
            })
            
            # Bull Call Spread
            higher_strikes = calls_df[calls_df["strike"] > atm_strike]["strike"]
            if not higher_strikes.empty:
                higher_strike = higher_strikes.min()  # Get the next higher strike
                
                strategies.append({
                    "name": "Bull Call Spread",
                    "description": f"Buy {atm_strike} call and sell {higher_strike} call",
                    "outlook": "Bullish",
                    "risk_level": "Medium",
                    "potential_profit": f"Limited to difference between strikes minus net premium paid",
                    "max_loss": "Limited to net premium paid",
                    "break_even": f"Lower strike plus net premium paid"
                })
            
            # Check if we have put strikes below current price
            lower_strikes = puts_df[puts_df["strike"] < atm_strike]["strike"]
            if not lower_strikes.empty:
                lower_strike = lower_strikes.max()  # Get the highest strike below current price
                
                strategies.append({
                    "name": "Bear Put Spread",
                    "description": f"Buy {atm_strike} put and sell {lower_strike} put",
                    "outlook": "Bearish",
                    "risk_level": "Medium",
                    "potential_profit": f"Limited to difference between strikes minus net premium paid",
                    "max_loss": "Limited to net premium paid",
                    "break_even": f"Higher strike minus net premium paid"
                })
            
            # Add Long Straddle strategy
            strategies.append({
                "name": "Long Straddle",
                "description": f"Buy ATM call and put at strike {atm_strike}",
                "outlook": "Volatile (direction neutral)",
                "risk_level": "Medium",
                "potential_profit": "Unlimited to the upside, limited to strike minus premium paid to the downside",
                "max_loss": "Limited to total premium paid",
                "break_even": f"Strike plus/minus premium paid"
            })
            
            # Check if we have implied volatility data
            if "impliedVolatility" in calls_df.columns:
                avg_iv = calls_df["impliedVolatility"].mean()
                logger.info(f"Average implied volatility: {avg_iv:.2%}")
                
                # Iron Condor (if we have enough strikes)
                if not higher_strikes.empty and not lower_strikes.empty:
                    strategies.append({
                        "name": "Iron Condor",
                        "description": "Sell OTM put, buy further OTM put, sell OTM call, buy further OTM call",
                        "outlook": "Neutral",
                        "risk_level": "Medium",
                        "potential_profit": "Limited to net premium received",
                        "max_loss": "Limited to difference between strikes minus net premium received",
                        "break_even": "Lower short strike minus net premium received and upper short strike plus net premium received"
                    })
                
                # Check if IV is high
                if avg_iv > 0.3:  # 30% IV is considered high
                    strategies.append({
                        "name": "Short Straddle",
                        "description": f"Sell ATM call and put at strike {atm_strike}",
                        "outlook": "Neutral with low volatility expectation",
                        "risk_level": "High",
                        "potential_profit": "Limited to premium received",
                        "max_loss": "Unlimited to the upside, limited to strike minus premium received to the downside",
                        "break_even": f"Strike plus/minus premium received"
                    })
    except Exception as e:
        logger.error(f"Error analyzing options strategies: {str(e)}")
        # Return basic strategies that don't require complex calculations
        strategies.append({
            "name": "Long Call",
            "description": "Buy a call option",
            "outlook": "Bullish",
            "risk_level": "Medium",
            "potential_profit": "Unlimited upside potential",
            "max_loss": "Limited to premium paid",
            "break_even": "Strike price plus premium paid"
        })
        
        strategies.append({
            "name": "Long Put",
            "description": "Buy a put option",
            "outlook": "Bearish",
            "risk_level": "Medium",
            "potential_profit": "Limited to strike price minus premium paid",
            "max_loss": "Limited to premium paid",
            "break_even": "Strike price minus premium paid"
        })
    
    return strategies

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

def display_options_analysis(options_data, current_price, ticker):
    """Display options analysis section"""
    st.subheader("Options Analysis")
    
    # Check for API errors
    if "error" in options_data:
        st.error(f"Error fetching options data: {options_data.get('error')}")
        with st.expander("Raw API Response"):
            st.code(options_data.get("raw_response", "No raw response available"))
        return
    
    # Debug: Show raw data
    with st.expander("Raw Options Data"):
        st.json(options_data)
    
    # Prepare options data
    prepared_options = prepare_options_data(options_data, ticker)
    
    if "error" in prepared_options:
        st.error(f"Error preparing options data: {prepared_options.get('error')}")
        return
    
    # Calculate put-call ratio
    put_call_ratio = calculate_put_call_ratio(prepared_options)
    if put_call_ratio:
        sentiment = "Bearish" if put_call_ratio > 1 else "Bullish"
        st.metric("Put-Call Ratio", f"{put_call_ratio:.2f}", f"Sentiment: {sentiment}")
    
    # Extract options chain data
    options = prepared_options.get("options", [])
    
    if options:
        # Get available expiration dates
        exp_dates = []
        for option in options:
            exp_timestamp = option.get("expirationDate", 0)
            if exp_timestamp:
                exp_date = datetime.fromtimestamp(exp_timestamp).strftime('%Y-%m-%d')
                exp_dates.append(exp_date)
        
        if exp_dates:
            # Create tabs for different analyses
            options_tab, iv_tab, strategies_tab = st.tabs(["Options Chain", "Implied Volatility", "Strategy Recommendations"])
            
            with options_tab:
                selected_exp = st.selectbox("Select Expiration Date", exp_dates, key="options_chain_exp")
                
                # Find options for selected expiration
                selected_options = None
                for option in options:
                    exp_date = datetime.fromtimestamp(option.get("expirationDate", 0)).strftime('%Y-%m-%d')
                    if exp_date == selected_exp:
                        selected_options = option
                        break
                
                if selected_options:
                    # Create tabs for calls and puts
                    call_tab, put_tab = st.tabs(["Calls", "Puts"])
                    
                    with call_tab:
                        calls = selected_options.get("calls", [])
                        if calls:
                            calls_df = pd.DataFrame(calls)
                            
                            # Format columns for display
                            display_cols = ["strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility"]
                            display_cols = [col for col in display_cols if col in calls_df.columns]
                            
                            if display_cols:
                                format_dict = {
                                    "strike": "${:.2f}",
                                    "lastPrice": "${:.2f}",
                                    "bid": "${:.2f}",
                                    "ask": "${:.2f}",
                                    "impliedVolatility": "{:.2%}"
                                }
                                
                                # Only include columns that exist in the dataframe
                                format_dict = {k: v for k, v in format_dict.items() if k in display_cols}
                                
                                st.dataframe(calls_df[display_cols].style.format(format_dict))
                        else:
                            st.info("No call options data available for this expiration date.")
                    
                    with put_tab:
                        puts = selected_options.get("puts", [])
                        if puts:
                            puts_df = pd.DataFrame(puts)
                            
                            # Format columns for display
                            display_cols = ["strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility"]
                            display_cols = [col for col in display_cols if col in puts_df.columns]
                            
                            if display_cols:
                                format_dict = {
                                    "strike": "${:.2f}",
                                    "lastPrice": "${:.2f}",
                                    "bid": "${:.2f}",
                                    "ask": "${:.2f}",
                                    "impliedVolatility": "{:.2%}"
                                }
                                
                                # Only include columns that exist in the dataframe
                                format_dict = {k: v for k, v in format_dict.items() if k in display_cols}
                                
                                st.dataframe(puts_df[display_cols].style.format(format_dict))
                        else:
                            st.info("No put options data available for this expiration date.")
            
            with iv_tab:
                # Calculate IV surface
                iv_surface = calculate_implied_volatility_surface(prepared_options)
                
                if iv_surface is not None and not iv_surface.empty:
                    st.subheader("Implied Volatility Analysis")
                    
                    # Create IV smile plot
                    selected_exp_iv = st.selectbox("Select Expiration Date", exp_dates, key="iv_exp")
                    
                    # Filter for selected expiration
                    days_to_expiry = (datetime.strptime(selected_exp_iv, '%Y-%m-%d') - datetime.now()).days
                    exp_iv_data = iv_surface[iv_surface['days_to_expiry'] == days_to_expiry]
                    
                    if not exp_iv_data.empty:
                        # Plot IV smile
                        fig = px.scatter(
                            exp_iv_data, 
                            x="strike", 
                            y="impliedVolatility", 
                            color="type",
                            title=f"Implied Volatility Smile for {selected_exp_iv}",
                            labels={"strike": "Strike Price", "impliedVolatility": "Implied Volatility", "type": "Option Type"}
                        )
                        
                        # Add trendline
                        fig.update_traces(mode='markers+lines')
                        
                        # Add current price line
                        if current_price > 0:
                            fig.add_vline(x=current_price, line_dash="dash", line_color="red", annotation_text="Current Price")
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # IV surface 3D plot
                        st.subheader("Implied Volatility Surface")
                        
                        # Create 3D surface plot
                        if len(exp_dates) > 1:
                            # Only show 3D plot if we have multiple expiration dates
                            fig_3d = px.scatter_3d(
                                iv_surface,
                                x="strike",
                                y="days_to_expiry",
                                z="impliedVolatility",
                                color="type",
                                title="Implied Volatility Surface",
                                labels={"strike": "Strike Price", "days_to_expiry": "Days to Expiry", "impliedVolatility": "Implied Volatility", "type": "Option Type"}
                            )
                            
                            st.plotly_chart(fig_3d, use_container_width=True)
                    else:
                        st.info("No implied volatility data available for this expiration date.")
                else:
                    st.info("Insufficient data to calculate implied volatility surface.")
            
            with strategies_tab:
                st.subheader("Options Strategy Recommendations")
                
                # Analyze options strategies
                strategies = analyze_options_strategies(prepared_options, current_price)
                
                if strategies:
                    for i, strategy in enumerate(strategies):
                        with st.expander(f"{i+1}. {strategy['name']} - {strategy['outlook']}"):
                            st.write(f"**Description:** {strategy['description']}")
                            st.write(f"**Risk Level:** {strategy['risk_level']}")
                            st.write(f"**Potential Profit:** {strategy['potential_profit']}")
                            st.write(f"**Maximum Loss:** {strategy['max_loss']}")
                            st.write(f"**Break-even Point:** {strategy['break_even']}")
                else:
                    st.info("No strategy recommendations available based on current options data.")
        else:
            st.info("No options expiration dates available for this ticker.")
    else:
        st.info("No options data available for this ticker.")

def main():
    st.set_page_config(
        page_title="Options Analysis Dashboard",
        page_icon="📈",
        layout="wide"
    )
    
    st.title("Options Analysis Dashboard")
    
    # Display API key status
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        st.error("RAPIDAPI_KEY not found in environment variables. Please add it to your .env file.")
    else:
        st.sidebar.success(f"API Key found: {api_key[:5]}...{api_key[-5:]}")
    
    # Sidebar
    st.sidebar.header("Settings")
    ticker = st.sidebar.text_input("Enter Ticker Symbol", value="AAPL").upper()
    
    if ticker:
        try:
            with st.spinner(f"Fetching data for {ticker}..."):
                # Fetch market data
                market_data = fetch_market_data(ticker)
                current_price = display_market_overview(market_data, ticker)
                
                # Fetch and display options data
                options_data = fetch_options_data(ticker)
                display_options_analysis(options_data, current_price, ticker)
                
        except Exception as e:
            st.error(f"Error fetching data: {str(e)}")
            logger.error(f"Error in main: {str(e)}", exc_info=True)
            
            # Show detailed error information
            with st.expander("Error Details"):
                import traceback
                st.code(traceback.format_exc())

if __name__ == "__main__":
    main() 