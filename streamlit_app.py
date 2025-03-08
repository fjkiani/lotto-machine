import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import json
import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Import our analysis modules
from src.data.connectors.yahoo_finance import YahooFinanceConnector
from src.analysis.enhanced_analysis_pipeline import EnhancedAnalysisPipeline
from options_enhanced_analysis import (
    fetch_options_from_rapidapi,
    prepare_options_data_for_analysis,
    analyze_options_with_deep_reasoning,
    combine_market_and_options_analysis
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Set page config
st.set_page_config(
    page_title="AI Hedge Fund - Enhanced Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cache data fetching functions
@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_market_data(ticker):
    """Fetch market data for a ticker"""
    connector = YahooFinanceConnector()
    quotes = connector.get_market_quotes([ticker])
    
    # Prepare market data for analysis
    market_data = {}
    for t, quote in quotes.items():
        market_data[t] = {
            "price": quote.regular_market_price,
            "previous_close": quote.regular_market_previous_close,
            "open": quote.regular_market_open,
            "high": quote.regular_market_day_high,
            "low": quote.regular_market_day_low,
            "volume": quote.regular_market_volume,
            "avg_volume": quote.average_volume,
            "market_cap": quote.market_cap,
            "pe_ratio": quote.trailing_pe,
            "dividend_yield": quote.get_dividend_yield(),
            "52w_high": quote.fifty_two_week_high,
            "52w_low": quote.fifty_two_week_low,
            "50d_avg": quote.fifty_day_average,
            "200d_avg": quote.two_hundred_day_average,
            "day_change_pct": quote.get_day_change_percent(),
            "market_state": quote.market_state,
            "exchange": quote.exchange_name
        }
    
    return market_data, quotes

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_options_data(ticker):
    """Fetch options data for a ticker"""
    try:
        # Fetch options data from RapidAPI
        api_data = fetch_options_from_rapidapi(ticker)
        
        # Prepare options data for analysis
        options_data = prepare_options_data_for_analysis(api_data, ticker)
        
        return options_data, True
    except Exception as e:
        logger.error(f"Error fetching options data: {str(e)}")
        return None, False

@st.cache_data(ttl=3600)  # Cache for 1 hour
def run_enhanced_analysis(ticker, analysis_type, use_feedback_loop):
    """Run enhanced analysis pipeline"""
    pipeline = EnhancedAnalysisPipeline(use_feedback_loop=use_feedback_loop)
    analysis_result = pipeline.analyze_tickers([ticker], analysis_type)
    return analysis_result

@st.cache_data(ttl=3600)  # Cache for 1 hour
def run_options_analysis(ticker, market_data, options_data):
    """Run options analysis"""
    options_analysis = analyze_options_with_deep_reasoning(ticker, options_data, market_data)
    return options_analysis

@st.cache_data(ttl=3600)  # Cache for 1 hour
def combine_analyses(market_analysis, options_analysis):
    """Combine market and options analyses"""
    combined_analysis = combine_market_and_options_analysis(market_analysis, options_analysis)
    return combined_analysis

def display_market_overview(market_data, ticker):
    """Display market overview"""
    data = market_data.get(ticker, {})
    
    # Create columns for key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Price", 
            f"${data.get('price', 0):.2f}", 
            f"{data.get('day_change_pct', 0):.2f}%"
        )
    
    with col2:
        st.metric(
            "Volume", 
            f"{data.get('volume', 0):,}", 
            f"{(data.get('volume', 0) / data.get('avg_volume', 1) - 1) * 100:.2f}% vs Avg"
        )
    
    with col3:
        st.metric(
            "52W Range", 
            f"${data.get('52w_low', 0):.2f} - ${data.get('52w_high', 0):.2f}",
            f"{(data.get('price', 0) - data.get('52w_low', 0)) / (data.get('52w_high', 0) - data.get('52w_low', 0)) * 100:.2f}% of range"
        )
    
    with col4:
        st.metric(
            "Market Cap", 
            f"${data.get('market_cap', 0) / 1_000_000_000:.2f}B",
            f"P/E: {data.get('pe_ratio', 0):.2f}"
        )
    
    # Create a gauge chart for price position in 52-week range
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = data.get('price', 0),
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Price in 52-Week Range"},
        gauge = {
            'axis': {'range': [data.get('52w_low', 0), data.get('52w_high', 0)]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [data.get('52w_low', 0), data.get('200d_avg', 0)], 'color': "lightgray"},
                {'range': [data.get('200d_avg', 0), data.get('50d_avg', 0)], 'color': "gray"},
                {'range': [data.get('50d_avg', 0), data.get('52w_high', 0)], 'color': "darkgray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': data.get('price', 0)
            }
        }
    ))
    
    st.plotly_chart(fig, use_container_width=True)

def display_market_analysis(analysis_result, ticker):
    """Display market analysis"""
    # Market Overview
    st.subheader("Market Overview")
    market_overview = analysis_result.get('market_overview', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"**Sentiment**: {market_overview.get('sentiment', 'N/A')}")
        st.info(f"**Market Condition**: {market_overview.get('market_condition', 'N/A')}")
    
    with col2:
        st.subheader("Key Observations")
        for observation in market_overview.get('key_observations', []):
            st.write(f"- {observation}")
    
    # Ticker Analysis
    st.subheader(f"{ticker} Analysis")
    ticker_analysis = analysis_result.get('ticker_analysis', {}).get(ticker, {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"**Sentiment**: {ticker_analysis.get('sentiment', 'N/A')}")
        st.info(f"**Risk Level**: {ticker_analysis.get('risk_level', 'N/A')}")
        
        # Price targets
        price_target = ticker_analysis.get('price_target', {})
        if price_target:
            st.subheader("Price Targets")
            st.write(f"**Short-term**: ${price_target.get('short_term', 'N/A')}")
            st.write(f"**Long-term**: ${price_target.get('long_term', 'N/A')}")
    
    with col2:
        st.subheader("Technical Signals")
        for signal in ticker_analysis.get('technical_signals', []):
            st.write(f"- {signal}")
    
    # Trading Opportunities
    st.subheader("Trading Opportunities")
    for opportunity in analysis_result.get('trading_opportunities', []):
        with st.expander(f"Strategy: {opportunity.get('strategy', 'N/A')}"):
            st.write(f"**Rationale**: {opportunity.get('rationale', 'N/A')}")
            st.write(f"**Time Horizon**: {opportunity.get('time_horizon', 'N/A')}")
            st.write(f"**Risk-Reward Ratio**: {opportunity.get('risk_reward_ratio', 'N/A')}")
            if 'conditions' in opportunity:
                st.write("**Conditions**:")
                for condition in opportunity.get('conditions', []):
                    st.write(f"- {condition}")
    
    # Overall Recommendation
    st.subheader("Overall Recommendation")
    st.success(analysis_result.get('overall_recommendation', 'N/A'))
    
    # Feedback (if available)
    if 'feedback' in analysis_result:
        st.subheader("Feedback Loop Results")
        
        st.write("**Changes Made**:")
        for change in analysis_result.get('feedback', {}).get('changes_made', []):
            st.write(f"- {change}")
        
        st.write("**Learning Points**:")
        for i, point in enumerate(analysis_result.get('feedback', {}).get('learning_points', []), 1):
            st.write(f"{i}. {point}")

def display_options_analysis(options_analysis, ticker):
    """Display options analysis"""
    # Options Market Overview
    st.subheader("Options Market Overview")
    options_overview = options_analysis.get('options_market_overview', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"**Options Sentiment**: {options_overview.get('sentiment', 'N/A')}")
        st.info(f"**Put-Call Ratio**: {options_overview.get('put_call_ratio', 'N/A')}")
    
    with col2:
        st.subheader("Implied Volatility")
        st.write(options_overview.get('implied_volatility_assessment', 'N/A'))
        
        st.subheader("Key Observations")
        for observation in options_overview.get('key_observations', []):
            st.write(f"- {observation}")
    
    # Recommended Options Strategies
    st.subheader("Recommended Options Strategies")
    for strategy in options_analysis.get('recommended_strategies', []):
        with st.expander(f"Strategy: {strategy.get('strategy_name', 'N/A')}"):
            st.write(f"**Construction**: {strategy.get('construction', 'N/A')}")
            st.write(f"**Optimal Strikes**: {', '.join(str(s) for s in strategy.get('optimal_strikes', []))}")
            st.write(f"**Expiration**: {strategy.get('expiration', 'N/A')}")
            st.write(f"**Max Profit**: {strategy.get('max_profit', 'N/A')}")
            st.write(f"**Max Loss**: {strategy.get('max_loss', 'N/A')}")
            st.write(f"**Breakeven**: {strategy.get('breakeven', 'N/A')}")
            st.write(f"**Probability of Profit**: {strategy.get('probability_of_profit', 'N/A')}")
            st.write(f"**Rationale**: {strategy.get('rationale', 'N/A')}")
    
    # Greeks Analysis
    st.subheader("Greeks Analysis")
    greeks = options_analysis.get('greeks_analysis', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Delta Exposure**: {greeks.get('delta_exposure', 'N/A')}")
        st.write(f"**Gamma Risk**: {greeks.get('gamma_risk', 'N/A')}")
    
    with col2:
        st.write(f"**Theta Decay**: {greeks.get('theta_decay', 'N/A')}")
        st.write(f"**Vega Sensitivity**: {greeks.get('vega_sensitivity', 'N/A')}")
    
    # Risk Assessment
    st.subheader("Risk Assessment")
    risk = options_analysis.get('risk_assessment', {})
    
    st.write("**Specific Risks**:")
    for r in risk.get('specific_risks', []):
        st.write(f"- {r}")
    
    st.write(f"**Volatility Outlook**: {risk.get('volatility_outlook', 'N/A')}")
    
    # Overall Recommendation
    st.subheader("Options Overall Recommendation")
    st.success(options_analysis.get('overall_recommendation', 'N/A'))

def display_cross_validation(market_analysis, options_analysis):
    """Display cross-validation between market and options analyses"""
    st.subheader("Cross-Validation Analysis")
    
    # Extract key metrics for comparison
    market_sentiment = market_analysis.get('market_overview', {}).get('sentiment', 'N/A')
    options_sentiment = options_analysis.get('options_market_overview', {}).get('sentiment', 'N/A')
    
    market_recommendation = market_analysis.get('overall_recommendation', 'N/A')
    options_recommendation = options_analysis.get('overall_recommendation', 'N/A')
    
    # Check for agreement/disagreement
    sentiment_agreement = market_sentiment.lower() in options_sentiment.lower() or options_sentiment.lower() in market_sentiment.lower()
    
    # Display comparison
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col1:
        st.subheader("Market Analysis")
        st.write(f"**Sentiment**: {market_sentiment}")
        st.write(f"**Recommendation**: {market_recommendation}")
    
    with col2:
        st.subheader("Agreement")
        if sentiment_agreement:
            st.success("✓")
        else:
            st.error("✗")
    
    with col3:
        st.subheader("Options Analysis")
        st.write(f"**Sentiment**: {options_sentiment}")
        st.write(f"**Recommendation**: {options_recommendation}")
    
    # Provide insights on agreement/disagreement
    st.subheader("Cross-Validation Insights")
    if sentiment_agreement:
        st.success("Market and options analyses are in agreement on overall sentiment, increasing confidence in the analysis.")
    else:
        st.warning("Market and options analyses show different sentiments. This divergence may indicate a potential shift in market direction or uncertainty.")
        
        # Attempt to explain the divergence
        st.write("**Possible explanations for the divergence:**")
        st.write("- Options market may be pricing in future events not reflected in current price action")
        st.write("- Institutional positioning through options may differ from retail sentiment")
        st.write("- Volatility expectations may be influencing options pricing independently of directional bias")
        st.write("- Recent news or events may be affecting options market differently than stock market")

def main():
    # Sidebar
    st.sidebar.title("AI Hedge Fund")
    st.sidebar.subheader("Enhanced Analysis Dashboard")
    
    # Ticker selection
    ticker = st.sidebar.text_input("Enter Ticker Symbol", "AAPL").upper()
    
    # Analysis options
    analysis_type = st.sidebar.selectbox(
        "Analysis Type",
        ["basic", "comprehensive"],
        index=1
    )
    
    use_feedback_loop = st.sidebar.checkbox("Use Feedback Loop", value=True)
    include_options = st.sidebar.checkbox("Include Options Analysis", value=True)
    
    # Run analysis button
    run_analysis = st.sidebar.button("Run Analysis")
    
    # Main content
    st.title(f"Enhanced Analysis for {ticker}")
    
    if run_analysis or 'market_data' in st.session_state:
        with st.spinner("Fetching market data..."):
            market_data, quotes = fetch_market_data(ticker)
            
            if ticker not in market_data:
                st.error(f"Could not fetch data for {ticker}. Please check the ticker symbol and try again.")
                return
            
            # Store in session state
            st.session_state.market_data = market_data
            st.session_state.quotes = quotes
        
        # Display market overview
        st.header("Market Overview")
        display_market_overview(market_data, ticker)
        
        # Run enhanced analysis
        with st.spinner("Running enhanced market analysis..."):
            market_analysis = run_enhanced_analysis(ticker, analysis_type, use_feedback_loop)
            st.session_state.market_analysis = market_analysis
        
        # Display market analysis
        st.header("Market Analysis")
        display_market_analysis(market_analysis, ticker)
        
        # Options analysis
        if include_options:
            with st.spinner("Fetching and analyzing options data..."):
                options_data, options_available = fetch_options_data(ticker)
                
                if options_available:
                    options_analysis = run_options_analysis(ticker, market_data, options_data)
                    st.session_state.options_analysis = options_analysis
                    
                    # Display options analysis
                    st.header("Options Analysis")
                    display_options_analysis(options_analysis, ticker)
                    
                    # Combine analyses
                    combined_analysis = combine_analyses(market_analysis, options_analysis)
                    st.session_state.combined_analysis = combined_analysis
                    
                    # Display cross-validation
                    st.header("Cross-Validation")
                    display_cross_validation(market_analysis, options_analysis)
                    
                    # Display combined recommendation
                    st.header("Integrated Recommendation")
                    st.success(combined_analysis.get('overall_recommendation', 'N/A'))
                else:
                    st.warning(f"Options data not available for {ticker}. Showing market analysis only.")
    
    # Feedback section
    st.header("Provide Feedback")
    feedback_quality = st.slider("Analysis Quality", 1, 5, 3)
    feedback_text = st.text_area("Additional Feedback")
    
    if st.button("Submit Feedback"):
        # In a real app, we would store this feedback
        st.success("Thank you for your feedback!")

if __name__ == "__main__":
    main() 