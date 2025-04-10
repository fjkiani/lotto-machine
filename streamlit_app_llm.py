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

from src.analysis.enhanced_analysis_pipeline import EnhancedAnalysisPipeline
from src.data.connectors.yahoo_finance import YahooFinanceConnector
from src.data.models import MarketQuote, OptionChain
from src.llm.memory_enhanced_analysis import MemoryEnhancedAnalysis
from src.data.memory import AnalysisMemory
# Import the new options analyzer functions
from src.analysis.options_analyzer import prepare_gemini_input, analyze_with_gemini, run_options_analysis
from src.analysis.technical_analyzer import run_technical_analysis
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

def display_market_overview(market_quote: Optional[MarketQuote], ticker: str) -> float:
    """Display market overview data from a MarketQuote object"""
    st.header(f"Market Overview: {ticker}")

    # Check if market_quote is None or has an error
    if market_quote is None:
        st.error(f"No market data available for {ticker}")
        return 0.0 # Return default price of 0.0 (float)

    # Check if it's an error dictionary passed instead of an object
    if isinstance(market_quote, dict) and "error" in market_quote:
        st.error(f"Error fetching market data: {market_quote.get('error')}")
        if "raw_response" in market_quote:
             with st.expander("Raw API Response"):
                 st.code(market_quote.get("raw_response", "No raw response available"))
        return 0.0 # Return default price of 0.0

    if not isinstance(market_quote, MarketQuote):
        st.error(f"Invalid market data type received: {type(market_quote)}")
        return 0.0

    # Extract data from MarketQuote object
    current_price = float(market_quote.regular_market_price) if market_quote.regular_market_price is not None else 0.0
    volume = int(market_quote.regular_market_volume) if market_quote.regular_market_volume is not None else 0
    market_cap = float(market_quote.market_cap) if market_quote.market_cap is not None else 0

    # Display key metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Price", f"${current_price:.2f}")

    with col2:
        st.metric("Volume", f"{volume:,}")

    with col3:
        # Format market cap nicely (e.g., $1.23T, $45.6B, $789M)
        if market_cap >= 1e12:
            market_cap_fmt = f"${market_cap / 1e12:.2f}T"
        elif market_cap >= 1e9:
            market_cap_fmt = f"${market_cap / 1e9:.2f}B"
        elif market_cap >= 1e6:
            market_cap_fmt = f"${market_cap / 1e6:.2f}M"
        else:
            market_cap_fmt = f"${market_cap:,.0f}"
        st.metric("Market Cap", market_cap_fmt)

    # Display additional market information if available
    with st.expander("Additional Market Information"):
        col1_add, col2_add = st.columns(2)

        def format_value(value):
             return f"${float(value):.2f}" if value is not None else "N/A"

        with col1_add:
            st.metric("Day High", format_value(market_quote.regular_market_day_high))
            st.metric("Day Low", format_value(market_quote.regular_market_day_low))
            st.metric("Open", format_value(market_quote.regular_market_open))
            st.metric("Previous Close", format_value(market_quote.regular_market_previous_close))

        with col2_add:
            st.metric("52 Week High", format_value(market_quote.fifty_two_week_high))
            st.metric("52 Week Low", format_value(market_quote.fifty_two_week_low))
            # Add other relevant fields if needed, e.g., PE Ratio, Dividend Yield
            pe_ratio = float(market_quote.trailing_pe) if market_quote.trailing_pe is not None else None
            st.metric("Trailing P/E", f"{pe_ratio:.2f}" if pe_ratio is not None else "N/A")
            div_yield = market_quote.get_dividend_yield() # Use the method from MarketQuote
            st.metric("Dividend Yield", f"{div_yield:.2%}" if div_yield is not None else "N/A")


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

    # Market Direction Analysis
    st.subheader("Market Direction Analysis")
    market_direction = analysis_result.get("market_direction", {})

    # Overall market bias with color
    overall_bias = market_direction.get('overall_bias', 'neutral')
    bias_color = {
        'bullish': 'green',
        'bearish': 'red',
        'neutral': 'blue'
    }.get(overall_bias.lower(), 'blue')

    # Confidence score
    confidence = market_direction.get('confidence', 0)

    # Create two columns for the main metrics
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"### Market Bias: <span style='color:{bias_color};font-size:24px'>{overall_bias.upper()}</span>", unsafe_allow_html=True)

    with col2:
        # Create a gauge chart for confidence
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = confidence,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Confidence"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': bias_color},
                'steps': [
                    {'range': [0, 33], 'color': 'lightgray'},
                    {'range': [33, 66], 'color': 'gray'},
                    {'range': [66, 100], 'color': 'darkgray'}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # Key signals from the options chain
    st.markdown("### Key Signals from Options Chain")
    key_signals = market_direction.get('key_signals', [])
    if key_signals:
        for i, signal in enumerate(key_signals):
            st.markdown(f"**{i+1}.** {signal}")
    else:
        st.write("No key signals identified")

    # Detailed market analysis
    if "detailed_analysis" in market_direction:
        with st.expander("Detailed Market Direction Analysis"):
            st.write(market_direction.get('detailed_analysis', ''))

    # Volatility Insights
    st.subheader("Volatility Insights")
    volatility_insights = analysis_result.get("volatility_insights", {})

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**Expected Move**: {volatility_insights.get('implied_move', 'N/A')}")

        # Volatility skew with color coding
        skew = volatility_insights.get('volatility_skew', 'neutral')
        skew_color = {
            'call_skew': 'green',
            'put_skew': 'red',
            'neutral': 'blue'
        }.get(skew.lower(), 'blue')

        skew_display = {
            'call_skew': 'CALL SKEW (Bullish)',
            'put_skew': 'PUT SKEW (Bearish)',
            'neutral': 'NEUTRAL'
        }.get(skew.lower(), skew.upper())

        st.markdown(f"**Volatility Skew**: <span style='color:{skew_color}'>{skew_display}</span>", unsafe_allow_html=True)

    with col2:
        st.markdown("**Event Expectations:**")
        events = volatility_insights.get('event_expectations', [])
        if events:
            for event in events:
                st.markdown(f"- {event}")
        else:
            st.write("No specific events anticipated")

    # Detailed volatility analysis
    if "volatility_analysis" in volatility_insights:
        with st.expander("Detailed Volatility Analysis"):
            st.write(volatility_insights.get('volatility_analysis', ''))

    # Options Chain Insights
    st.subheader("Options Chain Insights")

    options_insights = analysis_result.get("options_chain_insights", {})

    # Key strike levels as a bullet chart or table
    key_strikes = options_insights.get('key_strike_levels', [])
    if key_strikes:
        st.markdown("### Key Price Levels")

        # Convert to DataFrame for table display
        current_price = analysis_result.get("market_direction", {}).get("current_price", 0)
        if current_price == 0:
            # Fallback to underlying price from session state if available
            if 'options_data' in st.session_state:
                current_price = st.session_state.options_data.get("current_price", 0)

        strikes_df = pd.DataFrame({
            'Strike Level': [f"${strike:.2f}" for strike in key_strikes],
            'Distance': [f"{((strike - current_price) / current_price * 100):.2f}%" for strike in key_strikes],
            'Type': ['Resistance' if strike > current_price else 'Support' for strike in key_strikes]
        })

        st.table(strikes_df)

    # Unusual activity
    st.markdown("### Unusual Options Activity")
    unusual_activity = options_insights.get('unusual_activity', [])
    if unusual_activity:
        for activity in unusual_activity:
            st.markdown(f"- {activity}")
    else:
        st.write("No unusual options activity detected")

    # Institutional positioning
    st.markdown("### Institutional Positioning")
    st.write(options_insights.get('institutional_positioning', 'No clear institutional positioning detected'))

    # Options flow analysis
    with st.expander("Options Flow Analysis"):
        st.write(options_insights.get('options_flow_analysis', 'No options flow analysis available'))

    # SINGLE RECOMMENDED TRADE (Main Feature)
    st.markdown("---")
    st.subheader("🔥 Recommended Options Trade 🔥")

    recommended_trade = analysis_result.get("recommended_trade", {})

    if not recommended_trade:
        st.warning("No trade recommendation available")
    else:
        # Trade type with color
        trade_type = recommended_trade.get('contract_type', '').upper()
        trade_color = 'green' if trade_type == 'CALL' else 'red' if trade_type == 'PUT' else 'blue'

        # Display trade details in an eye-catching format
        st.markdown(f"""
        <div style="background-color: rgba(0, 0, 0, 0.05); padding: 20px; border-radius: 10px; border-left: 5px solid {trade_color};">
            <h2 style="color: {trade_color};">{trade_type} {ticker} @ ${recommended_trade.get('strike', 0):.2f}</h2>
            <p style="font-size: 1.2em;"><strong>Expiration:</strong> {recommended_trade.get('expiration', 'N/A')}</p>
            <p style="font-size: 1.2em;"><strong>Symbol:</strong> {recommended_trade.get('contract_symbol', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)

        # Trade metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Entry Price", f"${recommended_trade.get('entry_price', 0):.2f}")

        with col2:
            st.metric("Profit Target", f"${recommended_trade.get('profit_target', 0):.2f}")

        with col3:
            st.metric("Stop Loss", f"${recommended_trade.get('stop_loss', 0):.2f}")

        # Success probability and risk/reward
        col1, col2 = st.columns(2)

        with col1:
            prob = recommended_trade.get('probability_of_success', 0)

            # Create simple probability gauge
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = prob,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Probability of Success"},
                gauge = {
                    'axis': {'range': [None, 100]},
                    'bar': {'color': trade_color},
                    'steps': [
                        {'range': [0, 30], 'color': 'lightgray'},
                        {'range': [30, 70], 'color': 'gray'},
                        {'range': [70, 100], 'color': 'darkgray'}
                    ]
                }
            ))
            fig.update_layout(height=200, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            risk_reward = recommended_trade.get('risk_reward_ratio', 0)

            # Display risk/reward as horizontal stacked bar
            if risk_reward > 0:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    y=['Risk-Reward'],
                    x=[1],
                    name='Risk',
                    orientation='h',
                    marker=dict(color='red')
                ))
                fig.add_trace(go.Bar(
                    y=['Risk-Reward'],
                    x=[risk_reward],
                    name='Reward',
                    orientation='h',
                    marker=dict(color='green')
                ))
                fig.update_layout(
                    barmode='stack',
                    title='Risk-Reward Ratio',
                    height=200,
                    margin=dict(l=20, r=20, t=50, b=20),
                    legend=dict(orientation="h")
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.metric("Risk-Reward Ratio", f"{risk_reward:.2f}")

        # Trade thesis
        st.markdown("### Trade Thesis")
        st.write(recommended_trade.get('trade_thesis', 'No trade thesis provided'))

        # Exit strategy
        with st.expander("Exit Strategy"):
            st.write(recommended_trade.get('exit_strategy', 'No exit strategy provided'))

    # Greeks
    st.subheader("Options Greeks")
    greeks = analysis_result.get("greeks", {})

    # Create a DataFrame for the Greeks
    greeks_data = {
        "Greek": ["Delta", "Gamma", "Theta", "Vega"],
        "Value": [
            greeks.get("delta", "N/A"),
            greeks.get("gamma", "N/A"),
            greeks.get("theta", "N/A"),
            greeks.get("vega", "N/A")
        ]
    }

    greeks_df = pd.DataFrame(greeks_data)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.table(greeks_df)

    with col2:
        st.markdown("### Greeks Impact")
        st.write(greeks.get("greeks_impact", "No Greeks impact analysis provided"))

    # Risk Assessment
    st.subheader("Risk Assessment")
    risk_assessment = analysis_result.get("risk_assessment", {})

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Maximum Loss", risk_assessment.get("max_loss", "N/A"))

    with col2:
        st.metric("Maximum Gain", risk_assessment.get("max_gain", "N/A"))

    # Key risks
    st.markdown("### Key Risks")
    key_risks = risk_assessment.get('key_risks', [])
    if key_risks:
        for risk in key_risks:
            st.markdown(f"- {risk}")
    else:
        st.write("No specific risks identified")

    # Position sizing
    st.markdown("### Position Sizing Recommendation")
    st.write(risk_assessment.get('position_sizing_recommendation', 'No position sizing recommendation provided'))

    # Market Context
    st.subheader("Market Context")
    st.write(analysis_result.get("market_context", "No market context provided"))

def display_enhanced_analysis(analysis_result):
    """Display enhanced analysis with feedback loop"""
    st.header("Enhanced Analysis with Feedback Loop")

    # Check for errors
    if "error" in analysis_result:
        st.error(f"Error in enhanced analysis: {analysis_result.get('error')}")
        return

    # Market Overview - Enhanced with visual elements
    st.subheader("Market Overview")
    market_overview = analysis_result.get("market_overview", {})

    # Sentiment and Market Condition with visuals
    col1, col2 = st.columns(2)

    with col1:
        sentiment = market_overview.get('sentiment', 'neutral')
        sentiment_color = {
            'bullish': 'green',
            'bearish': 'red',
            'neutral': 'blue'
        }.get(sentiment.lower(), 'blue')

        # Create a gauge for sentiment
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = {
                'bullish': 75,
                'somewhat bullish': 60,
                'neutral': 50,
                'somewhat bearish': 40,
                'bearish': 25
            }.get(sentiment.lower(), 50),
            title = {'text': "Market Sentiment"},
            gauge = {
                'axis': {'range': [0, 100]},
                'bar': {'color': sentiment_color},
                'steps': [
                    {'range': [0, 30], 'color': 'rgba(255, 0, 0, 0.2)'},
                    {'range': [30, 45], 'color': 'rgba(255, 165, 0, 0.2)'},
                    {'range': [45, 55], 'color': 'rgba(0, 0, 255, 0.2)'},
                    {'range': [55, 70], 'color': 'rgba(144, 238, 144, 0.2)'},
                    {'range': [70, 100], 'color': 'rgba(0, 128, 0, 0.2)'}
                ]
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        market_condition = market_overview.get('market_condition', 'normal')
        condition_color = {
            'overbought': 'red',
            'oversold': 'green',
            'normal': 'blue'
        }.get(market_condition.lower(), 'blue')

        # Visual representation of market condition
        market_condition_value = {
            'strongly overbought': 90,
            'overbought': 75,
            'slightly overbought': 65,
            'normal': 50,
            'slightly oversold': 35,
            'oversold': 25,
            'strongly oversold': 10
        }.get(market_condition.lower(), 50)

        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = market_condition_value,
            title = {'text': "Market Condition"},
            gauge = {
                'axis': {'range': [0, 100]},
                'bar': {'color': condition_color},
                'steps': [
                    {'range': [0, 30], 'color': 'rgba(0, 128, 0, 0.2)'},  # Oversold - green
                    {'range': [30, 45], 'color': 'rgba(144, 238, 144, 0.2)'},
                    {'range': [45, 55], 'color': 'rgba(220, 220, 220, 0.2)'},  # Normal - gray
                    {'range': [55, 70], 'color': 'rgba(255, 165, 0, 0.2)'},
                    {'range': [70, 100], 'color': 'rgba(255, 0, 0, 0.2)'}  # Overbought - red
                ]
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # Key Market Observations with icons
    st.subheader("Key Market Observations")
    observations = market_overview.get("key_observations", [])

    if observations:
        for i, observation in enumerate(observations):
            icon = "🔍" if i % 4 == 0 else "📊" if i % 4 == 1 else "💡" if i % 4 == 2 else "⚡"
            st.markdown(f"{icon} {observation}")
    else:
        st.info("No key market observations available")

    # Market Signals Dashboard
    if "market_signals" in market_overview:
        st.subheader("Market Signals Dashboard")

        signals = market_overview.get("market_signals", {})
        signal_types = ['bullish', 'bearish', 'neutral']

        # Create three columns for signal types
        cols = st.columns(3)

        for i, signal_type in enumerate(signal_types):
            with cols[i]:
                st.markdown(f"### {signal_type.title()} Signals")
                signal_list = signals.get(f"{signal_type}_signals", [])

                if signal_list:
                    for signal in signal_list:
                        st.markdown(f"- {signal}")
                else:
                    st.write(f"No {signal_type} signals detected")

    # Ticker Analysis - Enhanced with visual elements and more details
    st.markdown("---")
    st.subheader("Ticker Analysis")
    ticker_analysis = analysis_result.get("ticker_analysis", {})

    # For each ticker, create an enhanced display
    for ticker, ticker_data in ticker_analysis.items():
        # Create a card-like container for each ticker
        st.markdown(f"""
        <div style="border-radius: 10px; border: 1px solid #ccc; padding: 15px; margin-bottom: 20px;">
            <h3 style="text-align: center;">{ticker} Analysis</h3>
        </div>
        """, unsafe_allow_html=True)

        # Sentiment and recommendation in a visual way
        sentiment = ticker_data.get('sentiment', 'neutral')
        recommendation = ticker_data.get('recommendation', 'N/A')
        risk_level = ticker_data.get('risk_level', 'N/A')

        sentiment_color = {
            'bullish': 'green',
            'bearish': 'red',
            'neutral': 'blue',
            'somewhat bullish': 'lightgreen',
            'somewhat bearish': 'salmon'
        }.get(sentiment.lower(), 'blue')

        risk_color = {
            'high': 'red',
            'medium': 'orange',
            'low': 'green'
        }.get(risk_level.lower(), 'gray')

        # Create 3 columns for main metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"**Sentiment**: <span style='color:{sentiment_color};font-size:18px'>{sentiment.upper()}</span>", unsafe_allow_html=True)

        with col2:
            st.markdown(f"**Recommendation**: <span style='font-weight:bold;font-size:18px'>{recommendation}</span>", unsafe_allow_html=True)

        with col3:
            st.markdown(f"**Risk Level**: <span style='color:{risk_color};font-size:18px'>{risk_level.upper()}</span>", unsafe_allow_html=True)

        # Technical Indicators Dashboard
        if "technical_indicators" in ticker_data:
            st.markdown("### Technical Indicators")

            indicators = ticker_data.get("technical_indicators", {})

            # Create a DataFrame for technical indicators
            indicator_list = []

            for name, properties in indicators.items():
                indicator_list.append({
                    "Indicator": name.upper(),
                    "Value": properties.get("value", "N/A"),
                    "Signal": properties.get("signal", "N/A"),
                    "Interpretation": properties.get("interpretation", "N/A")
                })

            if indicator_list:
                indicator_df = pd.DataFrame(indicator_list)
                st.table(indicator_df)
            else:
                st.info("No technical indicators available")

        # Technical Signals with enhanced display
        if "technical_signals" in ticker_data:
            st.markdown("### Technical Signals")

            signals = ticker_data.get("technical_signals", [])

            # Group signals by type: bullish, bearish, or neutral
            bullish_signals = [signal for signal in signals if "bullish" in signal.lower()]
            bearish_signals = [signal for signal in signals if "bearish" in signal.lower()]
            neutral_signals = [signal for signal in signals if "bullish" not in signal.lower() and "bearish" not in signal.lower()]

            # Create columns for signal types
            if bullish_signals or bearish_signals or neutral_signals:
                cols = st.columns(3)

                with cols[0]:
                    st.markdown("#### Bullish Signals")
                    if bullish_signals:
                        for signal in bullish_signals:
                            st.markdown(f"- 🟢 {signal}")
                    else:
                        st.write("No bullish signals")

                with cols[1]:
                    st.markdown("#### Bearish Signals")
                    if bearish_signals:
                        for signal in bearish_signals:
                            st.markdown(f"- 🔴 {signal}")
                    else:
                        st.write("No bearish signals")

                with cols[2]:
                    st.markdown("#### Neutral Signals")
                    if neutral_signals:
                        for signal in neutral_signals:
                            st.markdown(f"- 🔵 {signal}")
                    else:
                        st.write("No neutral signals")
            else:
                st.info("No technical signals detected")

        # Support and Resistance Levels
        if "support_resistance" in ticker_data:
            st.markdown("### Support & Resistance")

            sr_data = ticker_data.get("support_resistance", {})

            # Current price for reference
            current_price = ticker_data.get("current_price", 0)

            # Support levels
            support_levels = sr_data.get("support_levels", [])
            resistance_levels = sr_data.get("resistance_levels", [])

            if support_levels or resistance_levels:
                # Create a price chart with support and resistance lines
                all_levels = support_levels + resistance_levels + [current_price]
                min_price = min(all_levels) * 0.95 if all_levels else 0
                max_price = max(all_levels) * 1.05 if all_levels else 100

                fig = go.Figure()

                # Add current price line
                fig.add_shape(
                    type="line",
                    x0=0, x1=1,
                    y0=current_price, y1=current_price,
                    line=dict(color="blue", width=2, dash="solid"),
                )

                # Add annotation for current price
                fig.add_annotation(
                    x=0.5, y=current_price,
                    text=f"Current: ${current_price:.2f}",
                    showarrow=False,
                    yshift=10,
                    bgcolor="rgba(255, 255, 255, 0.8)"
                )

                # Add support levels
                for level in support_levels:
                    fig.add_shape(
                        type="line",
                        x0=0, x1=1,
                        y0=level, y1=level,
                        line=dict(color="green", width=1.5, dash="dash"),
                    )
                    fig.add_annotation(
                        x=0.2, y=level,
                        text=f"Support: ${level:.2f}",
                        showarrow=False,
                        yshift=-15,
                        bgcolor="rgba(144, 238, 144, 0.8)"
                    )

                # Add resistance levels
                for level in resistance_levels:
                    fig.add_shape(
                        type="line",
                        x0=0, x1=1,
                        y0=level, y1=level,
                        line=dict(color="red", width=1.5, dash="dash"),
                    )
                    fig.add_annotation(
                        x=0.8, y=level,
                        text=f"Resistance: ${level:.2f}",
                        showarrow=False,
                        yshift=15,
                        bgcolor="rgba(255, 200, 200, 0.8)"
                    )
                
                # Configure chart layout
                fig.update_layout(
                    title=f"{ticker} Support & Resistance Levels",
                    xaxis=dict(
                        showgrid=False,
                        zeroline=False,
                        showticklabels=False
                    ),
                    yaxis=dict(
                        range=[min_price, max_price],
                        title="Price ($)"
                    ),
                    height=400,
                    margin=dict(l=20, r=20, t=50, b=20),
                    showlegend=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No support and resistance levels detected")
        
        # Price Targets with visual elements
        if "price_target" in ticker_data:
            st.markdown("### Price Targets")
            
            price_target = ticker_data.get("price_target", {})
            current_price = ticker_data.get("current_price", 0)
            
            if current_price and (price_target.get('short_term') or price_target.get('long_term')):
                col1, col2 = st.columns(2)
                
                with col1:
                    short_term = price_target.get('short_term')
                    if short_term:
                        # Calculate percentage change
                        try:
                            short_term_value = float(short_term) if isinstance(short_term, (int, float, str)) else 0
                            pct_change = ((short_term_value - current_price) / current_price) * 100
                            delta_color = "normal" if abs(pct_change) < 1 else "off" if pct_change < 0 else "inverse"
                            st.metric("Short-term Target", f"${short_term_value:.2f}", f"{pct_change:.2f}%", delta_color=delta_color)
                        except (ValueError, TypeError):
                            st.metric("Short-term Target", f"${short_term}")
                    else:
                        st.metric("Short-term Target", "N/A")
                
                with col2:
                    long_term = price_target.get('long_term')
                    if long_term:
                        # Calculate percentage change
                        try:
                            long_term_value = float(long_term) if isinstance(long_term, (int, float, str)) else 0
                            pct_change = ((long_term_value - current_price) / current_price) * 100
                            delta_color = "normal" if abs(pct_change) < 1 else "off" if pct_change < 0 else "inverse"
                            st.metric("Long-term Target", f"${long_term_value:.2f}", f"{pct_change:.2f}%", delta_color=delta_color)
                        except (ValueError, TypeError):
                            st.metric("Long-term Target", f"${long_term}")
                    else:
                        st.metric("Long-term Target", "N/A")
                
                # Add notes if available
                if "note" in price_target:
                    st.info(f"**Note**: {price_target['note']}")
            else:
                st.info("No price targets available")
        
        # Key Insights with enhanced styling
        if "key_insights" in ticker_data:
            st.markdown("### Key Insights")
            
            insights = ticker_data.get("key_insights", [])
            
            if insights:
                # Create a card-like container for insights
                insights_html = "<div style='background-color: #f8f9fa; padding: 15px; border-radius: 5px;'>"
                
                for i, insight in enumerate(insights):
                    icon = "🎯" if i % 5 == 0 else "💰" if i % 5 == 1 else "📈" if i % 5 == 2 else "⚠️" if i % 5 == 3 else "💡"
                    insights_html += f"<p style='margin-bottom: 10px;'>{icon} {insight}</p>"
                
                insights_html += "</div>"
                st.markdown(insights_html, unsafe_allow_html=True)
            else:
                st.info("No key insights available")
    
    # Trading Opportunities - Enhanced with visual elements
    st.markdown("---")
    st.subheader("Trading Opportunities")
    opportunities = analysis_result.get("trading_opportunities", [])
    
    if opportunities:
        for opportunity in opportunities:
            # Create a colorful card based on the strategy type
            strategy = opportunity.get('strategy', 'N/A')
            ticker = opportunity.get('ticker', 'N/A')
            
            # Determine card color based on strategy type
            card_color = "#d1e7dd"  # Default light green
            if "short" in strategy.lower():
                card_color = "#f8d7da"  # Light red for short strategies
            elif "neutral" in strategy.lower() or "income" in strategy.lower():
                card_color = "#cff4fc"  # Light blue for neutral/income strategies
            
            # Create the card header
            st.markdown(f"""
            <div style="background-color: {card_color}; padding: 15px; border-radius: 10px 10px 0 0; margin-bottom: 0px;">
                <h3 style="margin: 0;">{ticker} - {strategy}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # Create the card body
            st.markdown(f"""
            <div style="border: 1px solid {card_color}; padding: 15px; border-radius: 0 0 10px 10px; margin-bottom: 20px;">
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                time_horizon = opportunity.get('time_horizon', 'N/A')
                risk_reward = opportunity.get('risk_reward_ratio', 'N/A')
                
                st.markdown(f"**Time Horizon**: {time_horizon}")
                st.markdown(f"**Risk/Reward Ratio**: {risk_reward}")
                
                # Add entry/exit points if available
                if "entry_point" in opportunity:
                    st.markdown(f"**Entry Point**: ${opportunity['entry_point']}")
                
                if "exit_point" in opportunity:
                    st.markdown(f"**Exit Point**: ${opportunity['exit_point']}")
                
                if "stop_loss" in opportunity:
                    st.markdown(f"**Stop Loss**: ${opportunity['stop_loss']}")
            
            with col2:
                st.markdown("**Rationale:**")
                rationale = opportunity.get('rationale', 'No rationale provided')
                st.markdown(f"<div style='background-color: #f8f9fa; padding: 10px; border-radius: 5px;'>{rationale}</div>", unsafe_allow_html=True)
            
            # Close the card div
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No trading opportunities identified")
    
    # Overall Recommendation with emphasis
    st.markdown("---")
    st.subheader("Overall Recommendation")
    
    recommendation = analysis_result.get('overall_recommendation', 'N/A')
    
    st.markdown(f"""
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #0d6efd;">
        <p style="font-size: 18px; font-weight: bold;">{recommendation}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Feedback Information with visual enhancements
    if "feedback" in analysis_result:
        st.markdown("---")
        st.header("Feedback Loop Information")
        feedback = analysis_result["feedback"]
        
        col1, col2 = st.columns(2)
        
        with col1:
            contradictions = feedback.get('contradictions_detected', 0)
            st.metric("Contradictions Detected", contradictions, delta=None, delta_color="inverse")
        
        with col2:
            confidence = feedback.get('confidence', 0)
            st.metric("Analysis Confidence", f"{confidence}%", delta=None)
        
        # Changes Made with colorful styling
        st.subheader("Changes Made")
        changes = feedback.get("changes_made", [])
        
        if changes:
            for change in changes:
                st.markdown(f"🔄 {change}")
        else:
            st.info("No changes were made during the feedback loop")
        
        # Overall Assessment
        st.subheader("Overall Assessment")
        assessment = feedback.get('overall_assessment', 'N/A')
        
        st.markdown(f"""
        <div style="background-color: #e2e3e5; padding: 15px; border-radius: 5px;">
            {assessment}
        </div>
        """, unsafe_allow_html=True)
        
        # Learning Points with visual styling
        if "learning_points" in feedback:
            st.subheader("Learning Points")
            
            points = feedback["learning_points"]
            if points:
                for i, point in enumerate(points):
                    icon = "💡" if i % 3 == 0 else "📚" if i % 3 == 1 else "🧠"
                    st.markdown(f"{icon} {point}")
            else:
                st.info("No learning points identified")

def display_memory_enhanced_analysis(ticker, analysis_result, historical_analyses):
    """Display memory-enhanced analysis results with historical context"""
    
    if analysis_result is None or "error" in analysis_result:
        st.error(f"Error in analysis result: {analysis_result.get('error', 'Unknown error')}")
        return

    # Market Overview Section
    st.header("Market Overview")
    if "market_overview" in analysis_result:
        market_overview = analysis_result["market_overview"]
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Market Sentiment", market_overview.get("sentiment", "N/A"))
        with col2:
            st.write("Key Market Factors:")
            for factor in market_overview.get("key_factors", []):
                st.markdown(f"- {factor}")
        with col3:
            st.write("Summary:")
            st.write(market_overview.get("summary", "N/A"))

    # Ticker Analysis Section
    st.header(f"Analysis for {ticker}")
    if "ticker_analysis" in analysis_result and ticker in analysis_result["ticker_analysis"]:
        ticker_data = analysis_result["ticker_analysis"][ticker]
        
        # Current Price and Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            current_price = ticker_data.get("current_price", 0)
            st.metric("Current Price", f"${current_price:,.2f}")
        with col2:
            st.metric("Recommendation", ticker_data.get("recommendation", "N/A"))
        with col3:
            confidence = ticker_data.get("confidence", "0")
            # Handle string percentage values
            if isinstance(confidence, str):
                try:
                    # Remove % sign if present and convert to float
                    confidence = float(confidence.strip('%')) / 100
                except ValueError:
                    confidence = 0
            st.metric("Confidence", f"{confidence*100:.1f}%")

        # Risk Assessment
        if "risk_assessment" in ticker_data:
            risk = ticker_data["risk_assessment"]
            st.subheader("Risk Assessment")
            col1, col2 = st.columns(2)
            with col1:
                risk_level = risk.get("overall_risk", "N/A")
                st.metric("Risk Level", risk_level)
            with col2:
                st.write("Risk Factors:")
                for factor in risk.get("factors", []):
                    st.markdown(f"- {factor}")

        # Price Targets
        if "price_targets" in ticker_data:
            st.subheader("Price Targets")
            targets = ticker_data["price_targets"]
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("Short Term:")
                short_term = targets.get("short_term", {})
                st.metric("Target", f"${short_term.get('target', 0):,.2f}")
                st.write(f"Timeframe: {short_term.get('timeframe', 'N/A')}")
                st.write(f"Confidence: {short_term.get('confidence', 'N/A')}")
            
            with col2:
                st.write("Long Term:")
                long_term = targets.get("long_term", {})
                st.metric("Target", f"${long_term.get('target', 0):,.2f}")
                st.write(f"Timeframe: {long_term.get('timeframe', 'N/A')}")
                st.write(f"Confidence: {long_term.get('confidence', 'N/A')}")

    # Trading Opportunities
    if "trading_opportunities" in analysis_result:
        st.header("Trading Opportunities")
        for opportunity in analysis_result["trading_opportunities"]:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Type**: {opportunity.get('type', 'N/A')}")
                st.markdown(f"**Entry Point**: ${opportunity.get('entry_point', 'N/A')}")
                st.markdown(f"**Target**: ${opportunity.get('target', 'N/A')}")
                st.markdown(f"**Stop Loss**: ${opportunity.get('stop_loss', 'N/A')}")
                st.markdown(f"**Time Horizon**: {opportunity.get('time_horizon', 'N/A')}")
                st.markdown(f"**Risk/Reward**: {opportunity.get('risk_reward_ratio', 'N/A')}")
            with col2:
                st.markdown("**Rationale:**")
                st.write(opportunity.get('rationale', 'N/A'))

    # Historical Analysis Section
    if historical_analyses:
        st.header("Historical Analysis")
        
        # Convert to DataFrame for easier manipulation
        analysis_records = []
        for analysis in historical_analyses:
            try:
                analysis_data = analysis.get('analysis_data', {})
                if isinstance(analysis_data, str):
                    analysis_data = json.loads(analysis_data)
                
                record = {
                    'timestamp': pd.to_datetime(analysis['timestamp']),
                    'current_price': analysis_data.get('current_price', 0.0),
                    'recommendation': analysis_data.get('recommendation', 'N/A'),
                    'confidence': analysis_data.get('confidence', 0.0),
                    'risk_level': analysis_data.get('risk_level', 'N/A'),
                    'market_sentiment': analysis_data.get('market_sentiment', 'N/A'),
                    'accuracy_score': analysis_data.get('accuracy_score', 0.0)
                }
                analysis_records.append(record)
            except Exception as e:
                st.warning(f"Error processing historical analysis: {str(e)}")
                continue

        if analysis_records:
            df = pd.DataFrame(analysis_records)
            df = df.sort_values('timestamp')

            # Display historical analysis table
            st.dataframe(df)

            # Plot if we have multiple data points
            if len(df) > 1:
                st.line_chart(df.set_index('timestamp')['current_price'])

    # Memory Information
    if "memory_context" in analysis_result:
        st.header("Memory Information")
        st.write(analysis_result["memory_context"])

    # Learning Points
    if "learning_points" in analysis_result:
        st.header("Learning Points")
        for point in analysis_result["learning_points"]:
            st.markdown(f"- {point}")

    # Feedback Form
    st.header("Feedback")
    feedback_type = st.selectbox("Feedback Type", ["Accuracy", "Usefulness", "Clarity"])
    feedback_text = st.text_area("Your Feedback")
    if st.button("Submit Feedback"):
        if "analysis_id" in analysis_result:
            try:
                memory_analyzer = MemoryEnhancedAnalysis()
                memory_analyzer.add_user_feedback(
                    analysis_result["analysis_id"],
                    feedback_type.lower(),
                    feedback_text
                )
                st.success("Feedback submitted successfully!")
            except Exception as e:
                st.error(f"Error submitting feedback: {str(e)}")
        else:
            st.error("No analysis ID found. Feedback cannot be submitted.")

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
            if "Support/Resistance" in indicator_options and analysis_result:
                ticker_analysis = analysis_result.get("ticker_analysis", {}).get(ticker, {})
                if "support_resistance" in ticker_analysis:
                    sr_levels = ticker_analysis["support_resistance"]
                    
                    # Add support levels
                    for level in sr_levels.get("support_levels", []):
                        fig.add_hline(
                            y=level,
                            line_dash="dash",
                            line_color="green",
                            annotation_text=f"Support: ${level:.2f}"
                        )
                    
                    # Add resistance levels
                    for level in sr_levels.get("resistance_levels", []):
                        fig.add_hline(
                            y=level,
                            line_dash="dash",
                            line_color="red",
                            annotation_text=f"Resistance: ${level:.2f}"
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
        volatility_risk = risk_data.get("volatility_risk", "medium")
        risk_color = {
            "high": "red",
            "medium": "orange",
            "low": "green"
        }.get(volatility_risk.lower(), "orange")
        st.markdown(f"Volatility Risk: <span style='color:{risk_color}'>{volatility_risk.upper()}</span>", unsafe_allow_html=True)
    
    st.write("**Key Risk Factors:**")
    for factor in risk_data.get("key_risk_factors", []):
        st.markdown(f"- {factor}")
    
    # Summary
    st.subheader("Analysis Summary")
    st.write(analysis_result.get("summary", "No summary provided."))
    
    # Confidence Score
    overall_confidence = analysis_result.get("confidence_score", 0)
    
    # Create confidence gauge
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = overall_confidence,
        title = {'text': "Overall Confidence"},
        gauge = {
            'axis': {'range': [0, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 30], 'color': "lightgray"},
                {'range': [30, 70], 'color': "gray"},
                {'range': [70, 100], 'color': "darkgray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 50
            }
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)
    
    # LLM Self-Improvement Section - Only show if available
    if "self_improvement" in analysis_result or "learning_points" in analysis_result:
        st.markdown("---")
        st.header("AI Self-Improvement Insights")
        
        # Create a nice card for the self-improvement section
        st.markdown("""
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #6c757d;">
            <h4 style="color: #6c757d;">How the AI is Learning & Improving</h4>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Self-improvement details
            if "self_improvement" in analysis_result:
                self_improvement = analysis_result.get("self_improvement", {})
                
                # Confidence adjustment
                confidence_adjustment = self_improvement.get("confidence_adjustment", 0)
                adjustment_direction = "increased" if confidence_adjustment > 0 else "decreased" if confidence_adjustment < 0 else "unchanged"
                adjustment_color = "green" if confidence_adjustment > 0 else "red" if confidence_adjustment < 0 else "gray"
                
                st.markdown(f"""
                <p><strong>Confidence Adjustment:</strong> <span style="color: {adjustment_color};">{adjustment_direction} by {abs(confidence_adjustment):.1f}%</span></p>
                """, unsafe_allow_html=True)
                
                # Improved methodology
                improved_methodology = self_improvement.get("improved_methodology", "No methodology improvements mentioned.")
                st.markdown(f"<p><strong>Improved Methodology:</strong> {improved_methodology}</p>", unsafe_allow_html=True)
        
        with col2:
            # Metadata about the analysis
            if "analysis_metadata" in analysis_result:
                metadata = analysis_result.get("analysis_metadata", {})
                st.markdown("<p><strong>Analysis Information:</strong></p>", unsafe_allow_html=True)
                st.markdown(f"<p>✓ Historical data utilized: {'Yes' if metadata.get('historical_data_used', False) else 'No'}</p>", unsafe_allow_html=True)
                st.markdown(f"<p>✓ Feedback loop version: {metadata.get('feedback_loop_version', 'N/A')}</p>", unsafe_allow_html=True)
                st.markdown(f"<p>✓ Analysis timestamp: {metadata.get('timestamp', 'N/A')}</p>", unsafe_allow_html=True)
        
        # Key learnings
        if "self_improvement" in analysis_result and "key_learnings" in analysis_result["self_improvement"]:
            st.subheader("Key Learnings")
            learnings = analysis_result["self_improvement"].get("key_learnings", [])
            
            if learnings:
                for i, learning in enumerate(learnings):
                    icon = "🧠" if i % 3 == 0 else "📈" if i % 3 == 1 else "🔍"
                    st.markdown(f"{icon} {learning}")
            else:
                st.info("No key learnings recorded")
        
        # Learning points
        if "learning_points" in analysis_result:
            st.subheader("Learning Points from Historical Analysis")
            learning_points = analysis_result.get("learning_points", [])
            
            if learning_points:
                for i, point in enumerate(learning_points):
                    icon = "💡" if i % 4 == 0 else "📊" if i % 4 == 1 else "⚖️" if i % 4 == 2 else "🔮"
                    st.markdown(f"{icon} {point}")
            else:
                st.info("No learning points recorded")
        
        # Performance visualizations
        if "performance_metrics" in analysis_result:
            st.subheader("Performance Metrics")
            metrics = analysis_result.get("performance_metrics", {})
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Accuracy over time
                if "accuracy_over_time" in metrics:
                    accuracy_data = metrics["accuracy_over_time"]
                    try:
                        df = pd.DataFrame(accuracy_data)
                        st.line_chart(df.set_index("date")["accuracy"])
                    except:
                        st.error("Could not visualize accuracy data")
            
            with col2:
                # Success rates by indicator
                if "success_by_indicator" in metrics:
                    indicator_data = metrics["success_by_indicator"]
                    try:
                        df = pd.DataFrame(indicator_data)
                        st.bar_chart(df.set_index("indicator")["success_rate"])
                    except:
                        st.error("Could not visualize indicator success data")
    
    # Raw technical data
    if "technical_data" in analysis_result:
        with st.expander("Raw Technical Data"):
            st.json(analysis_result["technical_data"])

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
        
        if not llm_price_targets.get("error"):
            logger.info("Successfully generated price targets with specialized LLM using time series data")
            return llm_price_targets
        else:
            logger.warning(f"LLM price target analysis failed: {llm_price_targets.get('error')}")
            # Continue with traditional methods as fallback
    except Exception as e:
        logger.error(f"Error in LLM price target analysis: {str(e)}")
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
        "methodologies": []
    }
    
    # Get current price
    try:
        if market_quote and "raw_data" in market_quote:
            quote = market_quote.get("raw_data", {}).get("optionChain", {}).get("result", [{}])[0].get("quote", {})
            current_price = quote.get("regularMarketPrice", 0)
            price_targets["current_price"] = current_price
        elif options_data:
            current_price = options_data.get("current_price", 0)
            price_targets["current_price"] = current_price
        else:
            logger.warning("No current price found in market_quote or options_data")
            return price_targets
    except Exception as e:
        logger.error(f"Error extracting current price: {str(e)}")
        return price_targets
    
    # If we have technical analysis data, use it for targets
    if technical_analysis and "price_targets" in technical_analysis:
        try:
            tech_targets = technical_analysis.get("price_targets", {})
            
            # Short term targets
            short_term = tech_targets.get("short_term", {})
            if short_term:
                price_targets["targets"]["short_term"]["technical"] = {
                    "bullish": short_term.get("bullish_target", 0),
                    "bearish": short_term.get("bearish_target", 0),
                    "timeframe": short_term.get("timeframe", "1-2 weeks"),
                    "confidence": short_term.get("confidence", 0)
                }
            
            # Medium term targets
            medium_term = tech_targets.get("medium_term", {})
            if medium_term:
                price_targets["targets"]["medium_term"]["technical"] = {
                    "bullish": medium_term.get("bullish_target", 0),
                    "bearish": medium_term.get("bearish_target", 0),
                    "timeframe": medium_term.get("timeframe", "1-3 months"),
                    "confidence": medium_term.get("confidence", 0)
                }
            
            price_targets["methodologies"].append("technical_analysis")
            logger.info("Added technical analysis-based price targets")
        except Exception as e:
            logger.error(f"Error processing technical analysis price targets: {str(e)}")
    
    # Try to get additional support/resistance from time series data
    try:
        from src.data.connectors.yahoo_finance import YahooFinanceConnector
        connector = YahooFinanceConnector()
        
        # Get daily time series
        daily_data = connector.get_time_series(ticker, "daily")
        
        # Analyze time series data
        if daily_data:
            ts_analysis = analyze_time_series_data(daily_data, current_price)
            
            # Add support/resistance from time series analysis
            if ts_analysis["support_levels"] or ts_analysis["resistance_levels"]:
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
    except Exception as e:
        logger.error(f"Error adding time series-based targets: {str(e)}")
    
    # If we have options data, calculate implied price ranges
    if options_data and "options_expirations" in options_data:
        try:
            expirations = options_data.get("options_expirations", [])
            
            # Group by timeframe
            short_term_exp = []
            medium_term_exp = []
            long_term_exp = []
            
            for exp in expirations:
                days_to_exp = exp.get("days_to_expiration", 0)
                if days_to_exp <= 30:
                    short_term_exp.append(exp)
                elif days_to_exp <= 90:
                    medium_term_exp.append(exp)
                else:
                    long_term_exp.append(exp)
            
            # Process short-term expirations
            if short_term_exp:
                nearest_exp = short_term_exp[0]
                options_list = nearest_exp.get("options", [])
                
                # Calculate price targets based on ATM straddle
                atm_option = min(options_list, key=lambda x: abs(x.get("strike", 0) - current_price))
                
                # Find the ATM straddle price (sum of ATM call and put)
                call_price = 0
                put_price = 0
                
                if atm_option.get("call") and atm_option.get("put"):
                    call_price = atm_option["call"].get("mid_price", 0)
                    put_price = atm_option["put"].get("mid_price", 0)
                
                straddle_price = call_price + put_price
                
                # Calculate expected move (implied by options market)
                implied_move_pct = (straddle_price / current_price) * 100
                
                # Calculate bullish and bearish targets
                bullish_target = current_price * (1 + (implied_move_pct/100))
                bearish_target = current_price * (1 - (implied_move_pct/100))
                
                price_targets["targets"]["short_term"]["options_implied"] = {
                    "bullish": round(bullish_target, 2),
                    "bearish": round(bearish_target, 2),
                    "timeframe": f"{nearest_exp.get('days_to_expiration', 0)} days",
                    "implied_move_pct": round(implied_move_pct, 2),
                    "confidence": 70  # Options market implied confidence
                }
                
                # Also add medium-term projection using longer-dated options if available
                if medium_term_exp:
                    medium_exp = medium_term_exp[0]
                    medium_options = medium_exp.get("options", [])
                    
                    # Find ATM option
                    medium_atm = min(medium_options, key=lambda x: abs(x.get("strike", 0) - current_price))
                    
                    medium_call_price = 0
                    medium_put_price = 0
                    
                    if medium_atm.get("call") and medium_atm.get("put"):
                        medium_call_price = medium_atm["call"].get("mid_price", 0)
                        medium_put_price = medium_atm["put"].get("mid_price", 0)
                    
                    medium_straddle = medium_call_price + medium_put_price
                    medium_move_pct = (medium_straddle / current_price) * 100
                    
                    medium_bullish = current_price * (1 + (medium_move_pct/100))
                    medium_bearish = current_price * (1 - (medium_move_pct/100))
                    
                    price_targets["targets"]["medium_term"]["options_implied"] = {
                        "bullish": round(medium_bullish, 2),
                        "bearish": round(medium_bearish, 2),
                        "timeframe": f"{medium_exp.get('days_to_expiration', 0)} days",
                        "implied_move_pct": round(medium_move_pct, 2),
                        "confidence": 60  # Medium-term options are less certain
                    }
            
            price_targets["methodologies"].append("options_implied")
            logger.info("Added options-implied price targets")
        except Exception as e:
            logger.error(f"Error calculating options-implied price targets: {str(e)}")
    
    # Generate volatility-based price targets using historical data
    try:
        import yfinance as yf
        import numpy as np
        
        # Get historical data
        ticker_data = yf.Ticker(ticker)
        history = ticker_data.history(period="6mo")
        
        if not history.empty:
            # Calculate historical volatility (30-day)
            returns = np.log(history['Close'] / history['Close'].shift(1))
            vol_30d = returns.rolling(window=30).std() * np.sqrt(252)  # Annualized
            current_vol = vol_30d.iloc[-1] if len(vol_30d) > 30 else returns.std() * np.sqrt(252)
            
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
    except Exception as e:
        logger.error(f"Error calculating volatility-based price targets: {str(e)}")
    
    # Calculate consensus targets by combining all available methodologies
    try:
        # Short-term consensus
        short_term_targets = []
        for method, data in price_targets["targets"]["short_term"].items():
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
                
                price_targets["targets"]["short_term"]["consensus"] = {
                    "bullish": round(consensus_bullish, 2),
                    "bearish": round(consensus_bearish, 2),
                    "timeframe": "1-30 days",
                    "confidence": 75
                }
        
        # Medium-term consensus
        medium_term_targets = []
        for method, data in price_targets["targets"]["medium_term"].items():
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
                
                price_targets["targets"]["medium_term"]["consensus"] = {
                    "bullish": round(consensus_bullish, 2),
                    "bearish": round(consensus_bearish, 2),
                    "timeframe": "1-3 months",
                    "confidence": 65
                }
        
        logger.info("Calculated consensus price targets")
    except Exception as e:
        logger.error(f"Error calculating consensus price targets: {str(e)}")
    
    # Convert to the format similar to LLM output for consistent display
    try:
        # If we have consensus targets, convert to the LLM format
        short_consensus = price_targets["targets"]["short_term"].get("consensus", {})
        medium_consensus = price_targets["targets"]["medium_term"].get("consensus", {})
        
        if short_consensus and medium_consensus:
            # Take the average of short and medium term as primary forecast
            short_expected = (short_consensus.get("bullish", 0) + short_consensus.get("bearish", 0)) / 2
            medium_expected = (medium_consensus.get("bullish", 0) + medium_consensus.get("bearish", 0)) / 2
            
            primary_target = (short_expected + medium_expected) / 2
            
            # Determine direction
            if primary_target > current_price * 1.02:
                direction = "bullish"
            elif primary_target < current_price * 0.98:
                direction = "bearish"
            else:
                direction = "neutral"
            
            # Calculate potential return
            potential_return = ((primary_target - current_price) / current_price) * 100
            
            # Create LLM-like format
            llm_format = {
                "ticker": ticker,
                "current_price": current_price,
                "price_targets": {
                    "short_term": {
                        "timeframe": "1-30 days",
                        "bullish_target": short_consensus.get("bullish", 0),
                        "bearish_target": short_consensus.get("bearish", 0),
                        "expected_target": short_expected,
                        "confidence": short_consensus.get("confidence", 0),
                        "key_levels": {
                            "resistance": [],
                            "support": [],
                            "invalidation": 0
                        }
                    },
                    "medium_term": {
                        "timeframe": "1-3 months",
                        "bullish_target": medium_consensus.get("bullish", 0),
                        "bearish_target": medium_consensus.get("bearish", 0),
                        "expected_target": medium_expected,
                        "confidence": medium_consensus.get("confidence", 0),
                        "key_levels": {
                            "resistance": [],
                            "support": [],
                            "invalidation": 0
                        }
                    }
                },
                "primary_forecast": {
                    "target_price": round(primary_target, 2),
                    "direction": direction,
                    "timeframe": "1-60 days",
                    "confidence": 65,
                    "potential_return": round(potential_return, 2)
                },
                "analysis_methodology": {
                    "technical_factors": ["Moving Averages", "Support/Resistance"],
                    "options_implied": "options_implied" in price_targets["methodologies"],
                    "volatility_based": "volatility_based" in price_targets["methodologies"],
                    "fundamental_consideration": False,
                    "time_series_analysis": "time_series_analysis" in price_targets["methodologies"]
                },
                "key_drivers": [
                    "Historical volatility",
                    "Options market pricing",
                    "Technical support/resistance levels"
                ],
                "market_context": "Analysis based on statistical models and technical indicators",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return llm_format
    except Exception as e:
        logger.error(f"Error converting to LLM format: {str(e)}")
    
    # Return the traditional format if conversion failed
    return price_targets

def display_price_targets(price_targets, ticker):
    """
    Display price targets in a visually appealing way
    Supports both traditional price targets format and the new LLM-specialized format
    
    Args:
        price_targets: Dictionary with price targets data
        ticker: Stock ticker symbol
    """
    st.subheader(f"📊 Price Targets for {ticker}")
    
    # Check if we have the LLM specialized format (primary_forecast field indicates this)
    is_llm_specialized = "primary_forecast" in price_targets
    
    # Get current price
    current_price = price_targets.get("current_price", 0)
    if current_price == 0 and "price_targets" in price_targets:
        # Try to extract from specialized LLM format
        current_price = price_targets.get("current_price", 0)
    
    if not current_price:
        st.warning("Current price information not available")
        return
        
    # Display header metrics - formatted based on which data structure we have
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Primary forecast or consensus target
        if is_llm_specialized:
            primary = price_targets.get("primary_forecast", {})
            target_price = primary.get("target_price", 0)
            if target_price:
                target_pct = ((target_price - current_price) / current_price) * 100
                direction = primary.get("direction", "neutral")
                confidence = primary.get("confidence", 0)
                
                # Format the delta based on direction
                delta_text = f"{target_pct:.2f}% ({direction})"
                st.metric(
                    "Primary Target", 
                    f"${target_price:.2f}", 
                    delta_text,
                    delta_color="normal" if direction == "neutral" else ("inverse" if direction == "bearish" else "normal")
                )
            else:
                st.metric("Primary Target", "Not available")
        else:
            # Use short-term consensus if available
            short_term = price_targets.get("targets", {}).get("short_term", {})
            consensus = short_term.get("consensus", {})
            
            if consensus:
                bullish = consensus.get("bullish", 0)
                bullish_pct = ((bullish - current_price) / current_price) * 100 if current_price else 0
                st.metric("Short-Term Target", f"${bullish:.2f}", f"{bullish_pct:.2f}%")
            else:
                st.metric("Short-Term Target", "Not available")
    
    with col2:
        if is_llm_specialized:
            # Display conviction level from LLM
            confidence = price_targets.get("primary_forecast", {}).get("confidence", 0)
            st.metric("Analyst Conviction", f"{confidence}%")
        else:
            # Use medium-term consensus if available
            medium_term = price_targets.get("targets", {}).get("medium_term", {})
            consensus = medium_term.get("consensus", {})
            
            if consensus:
                bullish = consensus.get("bullish", 0)
                bullish_pct = ((bullish - current_price) / current_price) * 100 if current_price else 0
                st.metric("Medium-Term Target", f"${bullish:.2f}", f"{bullish_pct:.2f}%")
            else:
                st.metric("Medium-Term Target", "Not available")
    
    with col3:
        if is_llm_specialized:
            # Display timeframe
            timeframe = price_targets.get("primary_forecast", {}).get("timeframe", "Unknown")
            potential_return = price_targets.get("primary_forecast", {}).get("potential_return", 0)
            st.metric("Timeframe", timeframe, f"{potential_return:.2f}%" if potential_return else None)
        else:
            # Current price reference
            st.metric("Current Price", f"${current_price:.2f}")
            
    # Visual representation of price targets
    st.markdown("### Price Target Ranges")
    
    # Handle different data formats
    if is_llm_specialized:
        # Create tabs for different timeframes
        short_tab, medium_tab = st.tabs(["Short-Term (1-30 days)", "Medium-Term (1-3 months)"])
        
        with short_tab:
            # Extract data from specialized LLM format
            short_term_data = price_targets.get("price_targets", {}).get("short_term", {})
            
            if short_term_data:
                # Display key metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    bullish = short_term_data.get("bullish_target", 0)
                    bullish_pct = ((bullish - current_price) / current_price) * 100 if current_price and bullish else 0
                    st.metric("Bullish Target", f"${bullish:.2f}", f"{bullish_pct:.2f}%")
                
                with col2:
                    expected = short_term_data.get("expected_target", 0)
                    expected_pct = ((expected - current_price) / current_price) * 100 if current_price and expected else 0
                    st.metric("Expected Target", f"${expected:.2f}", f"{expected_pct:.2f}%")
                    
                with col3:
                    bearish = short_term_data.get("bearish_target", 0)
                    bearish_pct = ((bearish - current_price) / current_price) * 100 if current_price and bearish else 0
                    st.metric("Bearish Target", f"${bearish:.2f}", f"{bearish_pct:.2f}%")
                
                # Create visual chart
                fig = go.Figure()
                
                # Add current price line
                fig.add_shape(
                    type="line",
                    x0=0, x1=1,
                    y0=current_price, y1=current_price,
                    line=dict(color="blue", width=2, dash="solid"),
                )
                
                # Add bullish, expected, and bearish targets
                if bullish:
                    fig.add_shape(
                        type="line",
                        x0=0.2, x1=0.8,
                        y0=bullish, y1=bullish,
                        line=dict(color="green", width=2, dash="dash"),
                    )
                    fig.add_annotation(
                        x=0.9, y=bullish,
                        text=f"Bullish: ${bullish:.2f} ({bullish_pct:.1f}%)",
                        showarrow=False,
                        align="left"
                    )
                
                if expected:
                    fig.add_shape(
                        type="line",
                        x0=0.2, x1=0.8,
                        y0=expected, y1=expected,
                        line=dict(color="orange", width=2, dash="dash"),
                    )
                    fig.add_annotation(
                        x=0.9, y=expected,
                        text=f"Expected: ${expected:.2f} ({expected_pct:.1f}%)",
                        showarrow=False,
                        align="left"
                    )
                
                if bearish:
                    fig.add_shape(
                        type="line",
                        x0=0.2, x1=0.8,
                        y0=bearish, y1=bearish,
                        line=dict(color="red", width=2, dash="dash"),
                    )
                    fig.add_annotation(
                        x=0.9, y=bearish,
                        text=f"Bearish: ${bearish:.2f} ({bearish_pct:.1f}%)",
                        showarrow=False,
                        align="left"
                    )
                
                # Add current price annotation
                fig.add_annotation(
                    x=0.1, y=current_price,
                    text=f"Current: ${current_price:.2f}",
                    showarrow=False,
                    align="right"
                )
                
                # Add key levels if available
                key_levels = short_term_data.get("key_levels", {})
                
                # Add support levels
                support_levels = key_levels.get("support", [])
                for i, level in enumerate(support_levels):
                    if level < current_price:  # Only show support below current price
                        fig.add_shape(
                            type="line",
                            x0=0.2, x1=0.8,
                            y0=level, y1=level,
                            line=dict(color="lightgreen", width=1.5, dash="dot"),
                        )
                        fig.add_annotation(
                            x=0.15, y=level,
                            text=f"S{i+1}: ${level:.2f}",
                            showarrow=False,
                            align="right",
                            font=dict(size=10)
                        )
                
                # Add resistance levels
                resistance_levels = key_levels.get("resistance", [])
                for i, level in enumerate(resistance_levels):
                    if level > current_price:  # Only show resistance above current price
                        fig.add_shape(
                            type="line",
                            x0=0.2, x1=0.8,
                            y0=level, y1=level,
                            line=dict(color="lightcoral", width=1.5, dash="dot"),
                        )
                        fig.add_annotation(
                            x=0.15, y=level,
                            text=f"R{i+1}: ${level:.2f}",
                            showarrow=False,
                            align="right",
                            font=dict(size=10)
                        )
                
                # Add invalidation level if available
                invalidation = key_levels.get("invalidation")
                if invalidation:
                    fig.add_shape(
                        type="line",
                        x0=0.2, x1=0.8,
                        y0=invalidation, y1=invalidation,
                        line=dict(color="black", width=1.5, dash="longdash"),
                    )
                    fig.add_annotation(
                        x=0.15, y=invalidation,
                        text=f"Invalidation: ${invalidation:.2f}",
                        showarrow=False,
                        align="right",
                        font=dict(size=10)
                    )
                
                # Set y-axis range with some padding
                all_values = [current_price]
                if bullish: all_values.append(bullish)
                if expected: all_values.append(expected)
                if bearish: all_values.append(bearish)
                all_values.extend(support_levels)
                all_values.extend(resistance_levels)
                if invalidation: all_values.append(invalidation)
                
                y_min = min(all_values)
                y_max = max(all_values)
                padding = (y_max - y_min) * 0.1
                
                # Configure chart layout
                fig.update_layout(
                    title=f"Short-Term Price Targets ({short_term_data.get('timeframe', '1-30 days')})",
                    xaxis=dict(
                        showgrid=False,
                        zeroline=False,
                        showticklabels=False,
                        range=[0, 1]
                    ),
                    yaxis=dict(
                        range=[y_min - padding, y_max + padding],
                        title="Price ($)"
                    ),
                    height=400,
                    margin=dict(l=20, r=20, t=50, b=20),
                    showlegend=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Display confidence
                confidence = short_term_data.get("confidence", 0)
                if confidence:
                    st.caption(f"Confidence: {confidence}%")
            else:
                st.info("No short-term price targets available")
        
        with medium_tab:
            # Extract data from specialized LLM format
            medium_term_data = price_targets.get("price_targets", {}).get("medium_term", {})
            
            if medium_term_data:
                # Similar implementation as short-term tab
                # (Abbreviated for clarity - you would implement a similar visualization)
                col1, col2, col3 = st.columns(3)
                with col1:
                    bullish = medium_term_data.get("bullish_target", 0)
                    bullish_pct = ((bullish - current_price) / current_price) * 100 if current_price and bullish else 0
                    st.metric("Bullish Target", f"${bullish:.2f}", f"{bullish_pct:.2f}%")
                
                with col2:
                    expected = medium_term_data.get("expected_target", 0)
                    expected_pct = ((expected - current_price) / current_price) * 100 if current_price and expected else 0
                    st.metric("Expected Target", f"${expected:.2f}", f"{expected_pct:.2f}%")
                    
                with col3:
                    bearish = medium_term_data.get("bearish_target", 0)
                    bearish_pct = ((bearish - current_price) / current_price) * 100 if current_price and bearish else 0
                    st.metric("Bearish Target", f"${bearish:.2f}", f"{bearish_pct:.2f}%")
                
                # Similar chart creation logic as short-term tab
                # (Code would be nearly identical to the short-term chart)
                st.info("Medium-term chart implementation follows the same pattern as short-term")
            else:
                st.info("No medium-term price targets available")
        
        # Display key drivers and market context
        st.subheader("Analysis Insights")
        
        # Key drivers
        key_drivers = price_targets.get("key_drivers", [])
        if key_drivers:
            st.markdown("#### Key Price Drivers")
            for driver in key_drivers:
                st.markdown(f"- {driver}")
        
        # Market context
        market_context = price_targets.get("market_context")
        if market_context:
            st.markdown("#### Market Context")
            st.markdown(market_context)
        
        # Methodology
        methodology = price_targets.get("analysis_methodology", {})
        if methodology:
            st.markdown("#### Analysis Methodology")
            factors = methodology.get("technical_factors", [])
            if factors:
                st.markdown("**Technical Factors:**")
                for factor in factors:
                    st.markdown(f"- {factor}")
            
            # Additional methodology details
            methods_used = []
            if methodology.get("technical_factors"): methods_used.append("Technical Analysis")
            if methodology.get("options_implied"): methods_used.append("Options Market Pricing")
            if methodology.get("volatility_based"): methods_used.append("Historical Volatility")
            if methodology.get("fundamental_consideration"): methods_used.append("Fundamental Analysis")
            
            if methods_used:
                st.markdown("**Methodologies Used:**")
                st.markdown(", ".join(methods_used))
                
    else:
        # Handle traditional format (showing previous implementation)
        # Create tabs for different timeframes
        short_tab, medium_tab = st.tabs(["Short-Term (1-30 days)", "Medium-Term (1-3 months)"])
        
        # Short-term price targets
        with short_tab:
            short_term = price_targets.get("targets", {}).get("short_term", {})
            
            if not short_term:
                st.info("No short-term price targets available")
                return
            
            # Create a visual price range chart
            fig = go.Figure()
            
            # Add current price line
            fig.add_shape(
                type="line",
                x0=0, x1=1,
                y0=current_price, y1=current_price,
                line=dict(color="blue", width=2, dash="solid"),
            )
            
            # Add target ranges for each methodology
            y_max = current_price
            y_min = current_price
            
            for method, data in short_term.items():
                if method != "consensus":
                    bullish = data.get("bullish", 0)
                    bearish = data.get("bearish", 0)
                    
                    # Update min/max for scaling
                    y_max = max(y_max, bullish)
                    y_min = min(y_min, bearish)
                    
                    # Add bullish target line
                    fig.add_shape(
                        type="line",
                        x0=0.2, x1=0.8,
                        y0=bullish, y1=bullish,
                        line=dict(color="green", width=1.5, dash="dash"),
                    )
                    
                    # Add bearish target line
                    fig.add_shape(
                        type="line",
                        x0=0.2, x1=0.8,
                        y0=bearish, y1=bearish,
                        line=dict(color="red", width=1.5, dash="dash"),
                    )
                    
                    # Add annotations
                    fig.add_annotation(
                        x=0.1, y=bullish,
                        text=f"{method}: ${bullish:.2f}",
                        showarrow=False,
                        xshift=-5,
                        align="right"
                    )
                    
                    fig.add_annotation(
                        x=0.1, y=bearish,
                        text=f"{method}: ${bearish:.2f}",
                        showarrow=False,
                        xshift=-5,
                        align="right"
                    )
            
            # Add current price annotation
            fig.add_annotation(
                x=0.5, y=current_price,
                text=f"Current: ${current_price:.2f}",
                showarrow=False,
                yshift=10,
                bgcolor="rgba(255, 255, 255, 0.8)"
            )
            
            # Configure chart layout
            buffer = (y_max - y_min) * 0.1  # 10% buffer
            fig.update_layout(
                title="Short-Term Price Target Ranges",
                xaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    range=[0, 1]
                ),
                yaxis=dict(
                    range=[y_min - buffer, y_max + buffer],
                    title="Price ($)"
                ),
                height=400,
                margin=dict(l=20, r=20, t=50, b=20),
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Show details about each methodology
            with st.expander("Price Target Methodologies"):
                for method, data in short_term.items():
                    if method == "consensus":
                        continue
                        
                    st.markdown(f"### {method.replace('_', ' ').title()}")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        bullish = data.get("bullish", 0)
                        bullish_pct = ((bullish - current_price) / current_price) * 100 if current_price else 0
                        st.metric("Bullish Target", f"${bullish:.2f}", f"{bullish_pct:.2f}%")
                    
                    with col2:
                        bearish = data.get("bearish", 0)
                        bearish_pct = ((bearish - current_price) / current_price) * 100 if current_price else 0
                        st.metric("Bearish Target", f"${bearish:.2f}", f"{bearish_pct:.2f}%")
                    
                    with col3:
                        st.metric("Timeframe", data.get("timeframe", "N/A"))
                    
                    # Additional information for options implied moves
                    if method == "options_implied" and "implied_move_pct" in data:
                        st.metric("Implied Move", f"{data['implied_move_pct']}%")
                    
                    # Additional information for volatility-based targets
                    if method == "volatility_based" and "volatility" in data:
                        st.metric("Historical Volatility", f"{data['volatility']}%")
                    
                    st.markdown("---")
        
        # Medium-term price targets
        with medium_tab:
            medium_term = price_targets.get("targets", {}).get("medium_term", {})
            
            if not medium_term:
                st.info("No medium-term price targets available")
                return
            
            # Rest of the existing medium-term tab implementation...
            # (Abbreviated for brevity - similar structure to short-term tab)
            st.info("Medium-term implementation follows same pattern as short-term")
    
    # Summary of methodologies used (for traditional format)
    if not is_llm_specialized:
        st.subheader("Methodology Summary")
        methodologies = price_targets.get("methodologies", [])
        
        if methodologies:
            method_descriptions = {
                "technical_analysis": "Price targets derived from technical analysis indicators like support/resistance levels, trend strength, and chart patterns.",
                "options_implied": "Targets derived from options market pricing, which reflects the market's expected price range.",
                "volatility_based": "Targets calculated using historical price volatility to estimate potential price movements.",
                "analyst_consensus": "Average of professional analyst price targets from various financial institutions."
            }
            
            for method in methodologies:
                if method in method_descriptions:
                    st.markdown(f"- **{method.replace('_', ' ').title()}**: {method_descriptions[method]}")
                else:
                    st.markdown(f"- **{method.replace('_', ' ').title()}**")
        else:
            st.info("No methodology information available")

def analyze_time_series_data(time_series_data, current_price):
    """
    Analyze time series data to identify key technical patterns and levels.
    
    Args:
        time_series_data: Dictionary containing time series data
        current_price: Current price of the asset
        
    Returns:
        Dictionary with technical analysis of time series data
    """
    import pandas as pd
    import numpy as np
    
    logger.info("Analyzing time series data for technical patterns")
    
    # Initialize results
    results = {
        "trend": {
            "short_term": "neutral",
            "medium_term": "neutral",
            "long_term": "neutral"
        },
        "support_levels": [],
        "resistance_levels": [],
        "price_patterns": [],
        "volatility": {
            "historical_volatility": 0,
            "recent_volatility": 0,
            "volatility_trend": "stable"
        },
        "volume_analysis": {
            "volume_trend": "neutral",
            "notable_volume_events": []
        },
        "key_levels": []
    }
    
    try:
        # Extract data from the time series format
        time_series = time_series_data.get(f"Time Series (Daily)", {})
        
        if not time_series:
            logger.warning("No time series data available for analysis")
            return results
        
        # Convert to DataFrame
        data = []
        for date, values in time_series.items():
            data.append({
                'date': date,
                'open': float(values.get("1. open", 0)),
                'high': float(values.get("2. high", 0)),
                'low': float(values.get("3. low", 0)),
                'close': float(values.get("4. close", 0)),
                'volume': int(values.get("5. volume", 0))
            })
        
        # Sort by date and create DataFrame
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        if len(df) < 10:
            logger.warning("Insufficient time series data points for analysis")
            return results
        
        # Calculate basic indicators
        # Moving averages
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma50'] = df['close'].rolling(window=50).mean()
        df['ma200'] = df['close'].rolling(window=200).mean()
        
        # Volatility (standard deviation of returns)
        df['returns'] = df['close'].pct_change()
        df['volatility_20d'] = df['returns'].rolling(window=20).std() * np.sqrt(252)  # Annualized
        
        # Volume moving average
        df['volume_ma20'] = df['volume'].rolling(window=20).mean()
        
        # Identify recent data (last 90 days)
        recent_df = df.tail(min(90, len(df)))
        
        # Trend determination
        # Short-term trend (5-day vs 20-day MA)
        last_row = df.iloc[-1]
        if last_row['ma5'] > last_row['ma20']:
            results['trend']['short_term'] = "bullish"
        elif last_row['ma5'] < last_row['ma20']:
            results['trend']['short_term'] = "bearish"
        
        # Medium-term trend (20-day vs 50-day MA)
        if last_row['ma20'] > last_row['ma50']:
            results['trend']['medium_term'] = "bullish"
        elif last_row['ma20'] < last_row['ma50']:
            results['trend']['medium_term'] = "bearish"
        
        # Long-term trend (50-day vs 200-day MA)
        if len(df) > 200 and not pd.isna(last_row['ma200']):
            if last_row['ma50'] > last_row['ma200']:
                results['trend']['long_term'] = "bullish"
            elif last_row['ma50'] < last_row['ma200']:
                results['trend']['long_term'] = "bearish"
        
        # Identify support and resistance levels
        # Use recent lows for support
        recent_lows = recent_df[(recent_df['low'] == recent_df['low'].rolling(10, center=True).min()) & 
                               (recent_df['low'] < current_price)]
        if not recent_lows.empty:
            support_levels = sorted(recent_lows['low'].unique().tolist())
            results['support_levels'] = support_levels[-3:] if len(support_levels) > 3 else support_levels
        
        # Use recent highs for resistance
        recent_highs = recent_df[(recent_df['high'] == recent_df['high'].rolling(10, center=True).max()) &
                                (recent_df['high'] > current_price)]
        if not recent_highs.empty:
            resistance_levels = sorted(recent_highs['high'].unique().tolist())
            results['resistance_levels'] = resistance_levels[:3] if len(resistance_levels) > 3 else resistance_levels
        
        # Volatility analysis
        if len(df) >= 20:
            current_vol = df['volatility_20d'].iloc[-1]
            avg_vol = df['volatility_20d'].mean()
            
            results['volatility']['historical_volatility'] = round(avg_vol * 100, 2)  # Convert to percentage
            results['volatility']['recent_volatility'] = round(current_vol * 100, 2)  # Convert to percentage
            
            if current_vol > avg_vol * 1.2:
                results['volatility']['volatility_trend'] = "increasing"
            elif current_vol < avg_vol * 0.8:
                results['volatility']['volatility_trend'] = "decreasing"
        
        # Volume analysis
        if len(df) >= 20:
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume_ma20'].iloc[-1]
            
            if current_volume > avg_volume * 1.5:
                results['volume_analysis']['volume_trend'] = "high"
                results['volume_analysis']['notable_volume_events'].append("Recent volume spike")
            elif current_volume < avg_volume * 0.5:
                results['volume_analysis']['volume_trend'] = "low"
                results['volume_analysis']['notable_volume_events'].append("Recent volume decline")
        
        # Identify recent price patterns
        # Double Bottom
        if len(recent_df) > 20:
            lows = recent_df[(recent_df['low'] == recent_df['low'].rolling(10, center=True).min())]
            if len(lows) >= 2:
                # Check if two recent lows are within 3% of each other
                recent_lows = lows.tail(2)
                if len(recent_lows) == 2:
                    low1 = recent_lows.iloc[0]['low']
                    low2 = recent_lows.iloc[1]['low']
                    if abs(low1 - low2) / low1 < 0.03:
                        results['price_patterns'].append("Double Bottom")
        
        # Double Top
        if len(recent_df) > 20:
            highs = recent_df[(recent_df['high'] == recent_df['high'].rolling(10, center=True).max())]
            if len(highs) >= 2:
                # Check if two recent highs are within 3% of each other
                recent_highs = highs.tail(2)
                if len(recent_highs) == 2:
                    high1 = recent_highs.iloc[0]['high']
                    high2 = recent_highs.iloc[1]['high']
                    if abs(high1 - high2) / high1 < 0.03:
                        results['price_patterns'].append("Double Top")
        
        # Identify key price levels (round numbers, historical significant levels)
        # Round to nearest 5% of current price
        round_factor = current_price * 0.05
        key_price_points = [round(current_price / round_factor) * round_factor * i for i in [0.8, 0.9, 1.0, 1.1, 1.2]]
        
        # Add to results
        results['key_levels'] = [round(level, 2) for level in key_price_points]
        
        return results
    
    except Exception as e:
        logger.error(f"Error analyzing time series data: {str(e)}")
        return results

def analyze_price_targets_with_llm(ticker, market_data, options_data=None, technical_analysis=None):
    """
    Use a specialized LLM to analyze and generate price targets with higher precision.
    This function is specifically optimized for price target prediction rather than
    general market or options analysis.
    
    Args:
        ticker: The stock ticker symbol
        market_data: Market data dictionary from Yahoo Finance
        options_data: Options chain data dictionary (optional)
        technical_analysis: Technical analysis data dictionary (optional)
        
    Returns:
        Dictionary with detailed price targets and reasoning
    """
    logger.info(f"Analyzing price targets with specialized LLM for {ticker}")
    
    # Get API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("Gemini API key not found in environment variables")
        return {"error": "Gemini API key not found in environment variables"}
    
    try:
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Extract current price and other relevant metrics
        current_price = 0
        historical_vol = 0
        market_cap = 0
        pe_ratio = 0
        
        if market_data and "raw_data" in market_data:
            quote = market_data.get("raw_data", {}).get("optionChain", {}).get("result", [{}])[0].get("quote", {})
            current_price = quote.get("regularMarketPrice", 0)
            market_cap = quote.get("marketCap", 0)
            pe_ratio = quote.get("forwardPE", quote.get("trailingPE", 0))
        elif options_data:
            current_price = options_data.get("current_price", 0)
            
        # Fetch time series data for enhanced analysis
        try:
            from src.data.connectors.yahoo_finance import YahooFinanceConnector
            connector = YahooFinanceConnector()
            
            # Get daily, weekly, and monthly time series
            daily_data = connector.get_time_series(ticker, "daily")
            weekly_data = connector.get_time_series(ticker, "weekly")
            
            # Analyze time series data
            time_series_analysis = analyze_time_series_data(daily_data, current_price)
            logger.info(f"Time series analysis completed for {ticker}")
        except Exception as e:
            logger.error(f"Error fetching or analyzing time series data: {str(e)}")
            time_series_analysis = None
            daily_data = None
            weekly_data = None
            
        # Prepare a comprehensive input for the LLM that focuses on price projection factors
        prompt_data = {
            "ticker": ticker,
            "current_price": current_price,
            "market_data": {}
        }
        
        # Add market context
        if market_data and "raw_data" in market_data:
            quote = market_data.get("raw_data", {}).get("optionChain", {}).get("result", [{}])[0].get("quote", {})
            prompt_data["market_data"] = {
                "market_cap": market_cap,
                "pe_ratio": pe_ratio,
                "52_week_high": quote.get("fiftyTwoWeekHigh", 0),
                "52_week_low": quote.get("fiftyTwoWeekLow", 0),
                "50_day_avg": quote.get("fiftyDayAverage", 0),
                "200_day_avg": quote.get("twoHundredDayAverage", 0),
                "avg_volume": quote.get("averageDailyVolume3Month", 0),
                "current_volume": quote.get("regularMarketVolume", 0)
            }
        
        # Add technical analysis context if available
        if technical_analysis:
            prompt_data["technical_analysis"] = {
                "indicators": technical_analysis.get("indicator_analysis", {}),
                "trend": technical_analysis.get("trend_analysis", {}),
                "support_levels": technical_analysis.get("historical_data", {}).get("potential_support_levels", []),
                "resistance_levels": technical_analysis.get("historical_data", {}).get("potential_resistance_levels", [])
            }
        
        # Add options data context if available
        if options_data and "options_expirations" in options_data:
            prompt_data["options_data"] = {
                "nearest_expiration": options_data["options_expirations"][0] if options_data["options_expirations"] else {},
                "iv_skew": "high" if any(exp.get("iv_skew", 0) > 0.1 for exp in options_data.get("options_expirations", []) if "iv_skew" in exp) else "normal"
            }
        
        # Add time series analysis if available
        if time_series_analysis:
            prompt_data["time_series_analysis"] = time_series_analysis
        
        # Add raw time series data (limited to reduce token usage)
        if daily_data:
            # Get just the last 20 days
            time_series = daily_data.get("Time Series (Daily)", {})
            sorted_dates = sorted(time_series.keys(), reverse=True)[:20]
            recent_data = {date: time_series[date] for date in sorted_dates}
            
            prompt_data["recent_price_history"] = {
                "daily": recent_data
            }
            
        # Create a specialized prompt focused on price target prediction
        system_prompt = """
        You are an expert financial analyst specializing in price target determination. 
        Your task is to analyze the provided data and generate precise price targets for different time horizons.
        
        You have been provided with rich historical time series data, which gives you insights into:
        1. Price action patterns (like double tops/bottoms, head and shoulders)
        2. Support and resistance levels based on historical price reactions
        3. Trend strength across different timeframes
        4. Volume patterns and their confirmation/divergence from price
        5. Volatility characteristics
        
        Your analysis should:
        1. Consider technical factors (support/resistance, momentum, moving averages) identified in the time series
        2. Incorporate options market implied moves when available
        3. Account for historical volatility patterns
        4. Provide distinct price targets for different time horizons (short-term: 1-30 days, medium-term: 1-3 months)
        5. Include both bullish and bearish scenarios with probability assessments
        6. Identify key price levels that would invalidate your analysis
        7. Determine a consensus price target that represents your highest conviction forecast
        
        Structure your analysis as follows:
        - Short-term price targets (bullish/bearish with confidence levels)
        - Medium-term price targets (bullish/bearish with confidence levels)
        - Primary price targets (most likely outcome with timeframe)
        - Key invalidation levels
        - Price target methodologies and reasoning
        
        You MUST provide your analysis as a structured JSON object with the following format:
        {
          "ticker": "SYMBOL",
          "current_price": PRICE,
          "price_targets": {
            "short_term": {
              "timeframe": "1-30 days",
              "bullish_target": PRICE,
              "bearish_target": PRICE,
              "expected_target": PRICE,
              "confidence": PERCENTAGE,
              "key_levels": {
                "resistance": [PRICES],
                "support": [PRICES],
                "invalidation": PRICE
              }
            },
            "medium_term": {
              "timeframe": "1-3 months",
              "bullish_target": PRICE,
              "bearish_target": PRICE,
              "expected_target": PRICE,
              "confidence": PERCENTAGE,
              "key_levels": {
                "resistance": [PRICES],
                "support": [PRICES],
                "invalidation": PRICE
              }
            }
          },
          "primary_forecast": {
            "target_price": PRICE,
            "direction": "bullish/bearish/neutral",
            "timeframe": "TEXT",
            "confidence": PERCENTAGE,
            "potential_return": PERCENTAGE
          },
          "analysis_methodology": {
            "technical_factors": ["FACTOR1", "FACTOR2"],
            "options_implied": BOOLEAN,
            "volatility_based": BOOLEAN,
            "fundamental_consideration": BOOLEAN,
            "time_series_analysis": BOOLEAN
          },
          "key_drivers": ["DRIVER1", "DRIVER2"],
          "market_context": "brief description of current market environment"
        }
        """
            
        user_prompt = f"""
        Please analyze {ticker} and provide specific price targets based on the following data:
        
        {json.dumps(prompt_data, indent=2)}
        
        Focus on generating precise, actionable price targets for both short and medium-term time horizons.
        Include both bullish and bearish scenarios, and provide a well-reasoned consensus target.
        Provide specific price levels, not just percentage moves.
        
        If time series data is available, pay special attention to:
        1. Support and resistance levels identified in the time series analysis
        2. The price patterns detected (like Double Top, Double Bottom)
        3. Trend directions across different timeframes
        4. Volume and volatility characteristics
        """
        
        # Configure Gemini model
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.2,
                "top_p": 0.95,
                "top_k": 64,
                "max_output_tokens": 2048,
            },
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ],
        )
        
        # Generate content
        response = model.generate_content([system_prompt, user_prompt])
        response_text = response.text
        
        try:
            # Extract JSON content
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].strip()
            else:
                json_str = response_text.strip()
            
            # Parse the analysis result
            analysis_result = json.loads(json_str)
            
            # Add timestamp
            analysis_result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            logger.debug(f"Raw response: {response_text}")
            return {
                "error": "Failed to parse LLM response",
                "raw_response": response_text
            }
            
    except Exception as e:
        logger.error(f"Error calling LLM API: {str(e)}")
        return {
            "error": f"Error calling LLM API: {str(e)}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

def main():
    # Set page config
    st.set_page_config(
        page_title="AI-Powered Stock Analysis",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Display header
    st.title("AI-Powered Stock Analysis")
    
    # Initialize session state for storing analysis history
    if "historical_analyses" not in st.session_state:
        st.session_state.historical_analyses = []

    # Initialize Connector (do this once)
    try:
        # Ensure connector is stored in session state to avoid re-initialization on reruns
        if 'connector' not in st.session_state:
             st.session_state.connector = YahooFinanceConnector()
             logger.info("YahooFinanceConnector initialized successfully.")
        connector = st.session_state.connector # Use the connector from session state
    except Exception as e:
        logger.error(f"Failed to initialize YahooFinanceConnector: {e}", exc_info=True)
        st.error(f"Fatal Error: Could not initialize data connector. Please check API keys and configuration. Error: {e}")
        st.stop()

    # Sidebar for inputs
    st.sidebar.title("Analysis Parameters")
    # Use session state for ticker input persistence
    if 'ticker_input' not in st.session_state:
         st.session_state.ticker_input = "AAPL"
    ticker = st.sidebar.text_input("Enter Stock Ticker", value=st.session_state.ticker_input).upper()
    st.session_state.ticker_input = ticker # Update session state on change

    # Define analysis types
    analysis_options = {
        "Options Analysis (LLM)": "llm_options",
        "Technical Analysis (LLM)": "llm_technicals",
        "Enhanced Analysis (Pipeline)": "enhanced",
        "Memory-Enhanced Analysis": "memory",
        "Price Target Generation": "price_target"
        # Add more analysis types here as they are modularized
    }
    # Use session state for selectbox persistence
    if 'selected_analysis_name_input' not in st.session_state:
         st.session_state.selected_analysis_name_input = list(analysis_options.keys())[0]
         
    selected_analysis_name = st.sidebar.selectbox(
         "Select Analysis Type", 
         list(analysis_options.keys()), 
         index=list(analysis_options.keys()).index(st.session_state.selected_analysis_name_input)
    )
    st.session_state.selected_analysis_name_input = selected_analysis_name # Update session state
    analysis_type = analysis_options[selected_analysis_name]

    # Use session state for slider persistence
    if 'risk_tolerance_input' not in st.session_state:
         st.session_state.risk_tolerance_input = "medium"
         
    risk_tolerance = st.session_state.risk_tolerance_input # Default value
    if analysis_type == "llm_options":
         risk_tolerance = st.sidebar.select_slider(
              "Select Risk Tolerance (for Options)",
              options=["low", "medium", "high"],
              value=st.session_state.risk_tolerance_input # Use session state value
         )
         st.session_state.risk_tolerance_input = risk_tolerance # Update session state

    # Use session state for timeframe persistence
    if 'timeframe_input' not in st.session_state:
         st.session_state.timeframe_input = "daily"
         
    timeframe = st.session_state.timeframe_input # Default value
    if analysis_type == "llm_technicals":
         timeframe = st.sidebar.selectbox(
              "Select Timeframe (for Technicals)",
              options=["hourly", "daily", "weekly", "monthly"],
              index=["hourly", "daily", "weekly", "monthly"].index(st.session_state.timeframe_input) # Use session state value
         )
         st.session_state.timeframe_input = timeframe # Update session state

    # Button to trigger analysis
    # Use a form to group sidebar inputs and button
    with st.sidebar.form(key='analysis_form'):
         st.header("Run Analysis")
         submitted = st.form_submit_button("Analyze Ticker")

         if submitted:
             if not ticker:
                 st.sidebar.error("Please enter a ticker symbol.")
             else:
                 # --- This block runs ONLY when the form is submitted --- 
                 st.session_state.current_ticker = ticker
                 # Store selected analysis type in session state for access after rerun
                 st.session_state.selected_analysis_type_on_submit = analysis_type 
                 st.session_state.risk_tolerance_on_submit = risk_tolerance
                 st.session_state.timeframe_on_submit = timeframe
                 
                 st.session_state.analysis_completed = False # Reset flag
                 # Clear previous results for the new analysis
                 st.session_state.market_data = {}
                 st.session_state.options_data = {}
                 st.session_state.analysis_result = {}
                 st.session_state.enhanced_analysis_result = {}
                 st.session_state.memory_analysis_result = {}
                 # Keep historical analysis unless explicitly cleared
                 st.session_state.last_analysis_time = datetime.now()
                 
                 # Indicate analysis is running
                 st.session_state.is_analyzing = True 
                 # Rerun immediately to exit the form and show the spinner in the main area
                 st.experimental_rerun() 

    # --- Main App Logic --- 
    # This part runs on every script run, including after the rerun triggered by the form
    if st.session_state.get('is_analyzing', False):
         # --- Analysis Execution Block (runs after form submission) ---
         # Get parameters from session state (set during form submission)
         ticker = st.session_state.current_ticker
         # Get analysis type that was selected when submitted
         analysis_type = st.session_state.selected_analysis_type_on_submit 
         risk_tolerance = st.session_state.risk_tolerance_on_submit
         timeframe = st.session_state.timeframe_on_submit
         connector = st.session_state.connector # Get connector from state
         
         # Reconstruct selected analysis name for spinner message (optional)
         selected_analysis_name_rerun = [k for k, v in analysis_options.items() if v == analysis_type][0] 

         # Display loading spinner
         with st.spinner(f"Running {selected_analysis_name_rerun} for {ticker}..."):
             # --- Fetch Data using Connector ---
             market_quote_obj = None
             option_chain_obj = None
             data_fetch_error = None
             
             try:
                 # Fetch Market Quote Data (always needed for overview)
                 logger.info(f"Fetching market quote for {ticker} using connector...")
                 market_quotes = connector.get_market_quotes(ticker)
                 if ticker in market_quotes:
                     market_quote_obj = market_quotes[ticker]
                     st.session_state.market_data = market_quote_obj # Store object
                     logger.info(f"Successfully fetched market quote for {ticker}")
                 else:
                      error_msg = f"No market quote data returned for {ticker}"
                      logger.error(error_msg)
                      st.session_state.market_data = {"error": error_msg}
                      data_fetch_error = data_fetch_error or error_msg # Keep first error

                 # Fetch Option Chain Data (if needed)
                 if analysis_type in ["llm_options", "price_target"]:
                     logger.info(f"Fetching option chain for {ticker} using connector...")
                     try:
                         option_chain_obj = connector.get_option_chain(ticker)
                         st.session_state.options_data = option_chain_obj # Store object
                         logger.info(f"Successfully fetched option chain for {ticker}")
                         if isinstance(option_chain_obj, dict) and "error" in option_chain_obj:
                             data_fetch_error = data_fetch_error or option_chain_obj["error"]
                     except Exception as opt_e:
                         error_msg = f"Failed to fetch option chain: {opt_e}"
                         logger.error(error_msg, exc_info=True)
                         st.session_state.options_data = {"error": error_msg}
                         data_fetch_error = data_fetch_error or error_msg

             except Exception as e:
                 error_msg = f"General data fetching error for {ticker}: {e}"
                 logger.error(error_msg, exc_info=True)
                 data_fetch_error = data_fetch_error or error_msg
                 # Store error state if not already set
                 if not st.session_state.market_data:
                      st.session_state.market_data = {"error": error_msg}
                 if not st.session_state.options_data and analysis_type in ["llm_options", "price_target"]:
                      st.session_state.options_data = {"error": error_msg}

             # --- Perform Selected Analysis (only if data fetching didn't critically fail) ---
             analysis_error = None
             # Check if essential data is available based on analysis type
             can_proceed = False
             if analysis_type in ["llm_options", "price_target"]:
                 # Both market and options data must be valid objects
                 can_proceed = isinstance(st.session_state.market_data, MarketQuote) and isinstance(st.session_state.options_data, OptionChain)
             else:
                 # Other types might only need market data
                 can_proceed = isinstance(st.session_state.market_data, MarketQuote) 
             
             if data_fetch_error:
                 analysis_error = f"Data fetch failed: {data_fetch_error}"
             elif not can_proceed:
                  analysis_error = "Required data for analysis is missing or invalid."
                  # Log specifics
                  if not isinstance(st.session_state.market_data, MarketQuote):
                      logger.error(f"Market data is invalid for analysis {analysis_type}: {st.session_state.market_data}")
                  if analysis_type in ["llm_options", "price_target"] and not isinstance(st.session_state.options_data, OptionChain):
                      logger.error(f"Options data is invalid for analysis {analysis_type}: {st.session_state.options_data}")
             else:
                 # Try to perform the analysis
                 try:
                     if analysis_type == "llm_options":
                         # Use the imported function from the new module
                         st.session_state.analysis_result = run_options_analysis(
                             ticker=ticker,
                             option_chain=st.session_state.options_data, 
                             risk_tolerance=risk_tolerance
                         )
                         if "error" in st.session_state.analysis_result:
                              analysis_error = st.session_state.analysis_result["error"]

                     elif analysis_type == "enhanced":
                         market_data_dict = st.session_state.market_data.raw_data if hasattr(st.session_state.market_data, 'raw_data') else {}
                         if market_data_dict:
                             pipeline = EnhancedAnalysisPipeline()
                             st.session_state.enhanced_analysis_result = pipeline.run_pipeline([ticker], market_data_dict)
                             if "error" in st.session_state.enhanced_analysis_result:
                                  analysis_error = st.session_state.enhanced_analysis_result["error"]
                         else:
                             err = "Market data dictionary unavailable for Enhanced Analysis."
                             st.session_state.enhanced_analysis_result = {"error": err}
                             analysis_error = err
                             
                     elif analysis_type == "memory":
                          if 'memory_analyzer' in st.session_state:
                              st.session_state.memory_analysis_result = st.session_state.memory_analyzer.perform_analysis_with_memory(ticker, connector=connector)
                              if "error" in st.session_state.memory_analysis_result:
                                   analysis_error = st.session_state.memory_analysis_result["error"]
                              else:
                                   st.session_state.historical_analyses = st.session_state.memory_analyzer.get_historical_analyses(ticker, limit=10)
                          else:
                              err = "Memory analyzer not initialized."
                              st.session_state.memory_analysis_result = {"error": err}
                              analysis_error = err
                              
                     elif analysis_type == "llm_technicals":
                          historical = st.session_state.get('historical_analyses', [])
                          # Pass the connector instance
                          st.session_state.analysis_result = run_technical_analysis(
                              ticker, 
                              timeframe, 
                              connector=connector, # Add this argument
                              historical_analyses=historical
                          )
                          if "error" in st.session_state.analysis_result:
                               analysis_error = st.session_state.analysis_result["error"]
                          
                     elif analysis_type == "price_target":
                          market_data_arg = st.session_state.market_data 
                          options_data_arg = st.session_state.options_data
                          tech_analysis = st.session_state.analysis_result if st.session_state.get('analysis_result', {}).get("trend_analysis") else None
                          
                          st.session_state.analysis_result = generate_price_targets(
                              ticker=ticker,
                              connector=connector, 
                              market_quote=market_data_arg, 
                              options_data=options_data_arg,
                              technical_analysis=tech_analysis
                          )
                          if "error" in st.session_state.analysis_result:
                               analysis_error = st.session_state.analysis_result["error"]
                 
                 # Add the except block for the analysis try
                 except Exception as e:
                     analysis_error = f"An error occurred during {selected_analysis_name_rerun}: {e}"
                     logger.error(f"Analysis error for {ticker} ({analysis_type}): {e}", exc_info=True)
             
             # --- Finalize Analysis Run Status ---
             if data_fetch_error:
                  # Error already logged during fetch
                  st.error(f"Failed to fetch necessary data: {data_fetch_error}")
                  st.session_state.analysis_completed = False
             elif analysis_error:
                  # Error logged during analysis try/except or set above
                  st.error(f"Analysis failed: {analysis_error}")
                  st.session_state.analysis_completed = False
             else:
                  # Only set completed True if no errors occurred
                  st.session_state.analysis_completed = True
                  st.success(f"{selected_analysis_name_rerun} for {ticker} completed!")

         # Reset the analyzing flag and rerun to display results
         st.session_state.is_analyzing = False 
         st.experimental_rerun()

    # --- Display Area (Runs after analysis is done or if already completed) ---
    # Check if a ticker has been analyzed previously or just now
    elif st.session_state.current_ticker: 
        st.markdown("---")
        # Display Market Overview (always try to display if data exists, even if analysis failed)
        current_price_disp = display_market_overview(st.session_state.market_data, st.session_state.current_ticker)

        # Check if analysis completed successfully before displaying results
        if st.session_state.analysis_completed:
             # Get analysis type from session state (the one used for the completed analysis)
             analysis_type_to_display = st.session_state.selected_analysis_type_on_submit 
             
             # Display results based on the completed analysis type
             if analysis_type_to_display == "llm_options":
                 display_llm_options_analysis(st.session_state.analysis_result, st.session_state.current_ticker)
             elif analysis_type_to_display == "enhanced":
                 display_enhanced_analysis(st.session_state.enhanced_analysis_result)
             elif analysis_type_to_display == "memory":
                 display_memory_enhanced_analysis(
                      st.session_state.current_ticker, 
                      st.session_state.memory_analysis_result, 
                      st.session_state.historical_analyses
                 )
             elif analysis_type_to_display == "llm_technicals":
                  display_technical_analysis(st.session_state.analysis_result)
                  create_technical_chart(st.session_state.current_ticker, st.session_state.market_data, st.session_state.analysis_result)
             elif analysis_type_to_display == "price_target":
                  display_price_targets(st.session_state.analysis_result, st.session_state.current_ticker)
        # Add an else block here to handle the case where analysis did not complete
        # This covers the state after a failed analysis run
        elif st.session_state.last_analysis_time: # Check if an analysis was attempted
             st.warning(f"Analysis for {st.session_state.current_ticker} did not complete successfully. Check logs or error messages above.")

    else:
         # Initial state before any analysis is run
         st.info("Enter a ticker symbol and click 'Analyze Ticker' to begin.")

if __name__ == "__main__":
    main() 