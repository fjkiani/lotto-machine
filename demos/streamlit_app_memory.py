import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import os
import logging
import sqlite3
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv

from src.llm.memory_enhanced_analysis import MemoryEnhancedAnalysis
from src.analysis.technical_indicators_storage import TechnicalIndicatorsStorage
from src.analysis.trend_analysis_storage import TrendAnalysisStorage

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize session state
if 'memory_analyzer' not in st.session_state:
    st.session_state.memory_analyzer = MemoryEnhancedAnalysis()

if 'tech_storage' not in st.session_state:
    st.session_state.tech_storage = TechnicalIndicatorsStorage()

if 'trend_storage' not in st.session_state:
    st.session_state.trend_storage = TrendAnalysisStorage()

if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = {}

if 'current_analysis' not in st.session_state:
    st.session_state.current_analysis = None

if 'current_ticker' not in st.session_state:
    st.session_state.current_ticker = None

if 'analysis_id' not in st.session_state:
    st.session_state.analysis_id = None

if 'indicator_data' not in st.session_state:
    st.session_state.indicator_data = {}

if 'trend_analysis_id' not in st.session_state:
    st.session_state.trend_analysis_id = None

def run_analysis(ticker, analysis_type, risk_tolerance):
    """
    Run memory-enhanced analysis for a ticker
    
    Args:
        ticker: Ticker symbol
        analysis_type: Type of analysis
        risk_tolerance: Risk tolerance level
        
    Returns:
        Analysis results
    """
    try:
        # Run the analysis
        result = st.session_state.memory_analyzer.analyze_ticker_with_memory(
            ticker=ticker,
            analysis_type=analysis_type,
            risk_tolerance=risk_tolerance
        )
        
        # Store the result in session state
        st.session_state.current_analysis = result
        st.session_state.current_ticker = ticker
        
        # Store the analysis ID
        if "analysis_id" in result:
            st.session_state.analysis_id = result["analysis_id"]
        
        # Update analysis history
        if ticker not in st.session_state.analysis_history:
            st.session_state.analysis_history[ticker] = []
        
        # Add to history (limited to last 5)
        st.session_state.analysis_history[ticker].append({
            "timestamp": datetime.now().isoformat(),
            "analysis_type": analysis_type,
            "risk_tolerance": risk_tolerance,
            "result": result
        })
        
        if len(st.session_state.analysis_history[ticker]) > 5:
            st.session_state.analysis_history[ticker].pop(0)
        
        return result
    
    except Exception as e:
        logger.error(f"Error running analysis: {str(e)}")
        return {"error": str(e)}

def collect_technical_indicators(ticker, period="1y", interval="1d"):
    """
    Collect and store technical indicators for a ticker
    
    Args:
        ticker: Ticker symbol
        period: Data period
        interval: Data interval
        
    Returns:
        Dictionary with indicator data
    """
    try:
        indicators_data = st.session_state.tech_storage.collect_and_store_indicators(
            ticker=ticker,
            period=period,
            interval=interval
        )
        
        # Store in session state
        st.session_state.indicator_data[ticker] = indicators_data
        
        return indicators_data
    
    except Exception as e:
        logger.error(f"Error collecting technical indicators: {str(e)}")
        return {}

def get_indicator_trends(ticker, indicator_name, days=30):
    """
    Get trends for a specific indicator
    
    Args:
        ticker: Ticker symbol
        indicator_name: Name of the indicator
        days: Number of days to analyze
        
    Returns:
        Dictionary with trend data
    """
    try:
        return st.session_state.memory_analyzer.get_technical_indicator_trends(
            ticker=ticker,
            indicator_name=indicator_name,
            days=days
        )
    except Exception as e:
        logger.error(f"Error getting indicator trends: {str(e)}")
        return {"error": str(e)}

def add_user_feedback(analysis_id, feedback_type, feedback_text):
    """
    Add user feedback for an analysis
    
    Args:
        analysis_id: ID of the analysis
        feedback_type: Type of feedback
        feedback_text: Text of the feedback
    """
    try:
        st.session_state.memory_analyzer.add_user_feedback(
            analysis_id=analysis_id,
            feedback_type=feedback_type,
            feedback_text=feedback_text
        )
        return True
    except Exception as e:
        logger.error(f"Error adding feedback: {str(e)}")
        return False

def get_analysis_history(ticker, limit=5):
    """
    Get historical analyses for a ticker from the memory database
    
    Args:
        ticker: Ticker symbol
        limit: Maximum number of analyses to return
        
    Returns:
        List of historical analyses
    """
    try:
        return st.session_state.memory_analyzer.get_analysis_history(ticker, limit)
    except Exception as e:
        logger.error(f"Error getting analysis history: {str(e)}")
        return []

def get_recommendation_accuracy(ticker):
    """
    Get recommendation accuracy for a ticker
    
    Args:
        ticker: Ticker symbol
        
    Returns:
        Dictionary with accuracy metrics
    """
    try:
        return st.session_state.memory_analyzer.get_recommendation_accuracy(ticker)
    except Exception as e:
        logger.error(f"Error getting recommendation accuracy: {str(e)}")
        return {"accuracy": 0, "correct": 0, "total": 0}

def display_market_overview(result, ticker):
    """
    Display market overview section
    
    Args:
        result: Analysis result dictionary
        ticker: Ticker symbol
    """
    if result is None:
        st.error("No analysis results available.")
        return
        
    st.subheader(f"Market Overview for {ticker}")
    
    # Create columns for different metrics
    col1, col2, col3 = st.columns(3)
    
    # Market sentiment
    with col1:
        st.metric(
            "Market Sentiment",
            result.get("market_sentiment", "N/A"),
            delta=result.get("sentiment_change", "N/A")
        )
    
    # Market volatility
    with col2:
        st.metric(
            "Market Volatility",
            result.get("market_volatility", "N/A"),
            delta=result.get("volatility_change", "N/A")
        )
    
    # Trading volume
    with col3:
        st.metric(
            "Trading Volume",
            result.get("trading_volume", "N/A"),
            delta=result.get("volume_change", "N/A")
        )
    
    # Market factors
    if "market_factors" in result and result["market_factors"]:
        st.subheader("Key Market Factors")
        for factor in result["market_factors"]:
            st.markdown(f"- {factor}")
    
    # Market summary
    if "market_summary" in result and result["market_summary"]:
        st.subheader("Market Summary")
        st.write(result["market_summary"])

def display_ticker_analysis(result, ticker):
    """
    Display ticker-specific analysis section
    
    Args:
        result: Analysis result dictionary
        ticker: Ticker symbol
    """
    if result is None:
        st.error("No analysis results available.")
        return
        
    st.subheader(f"Analysis for {ticker}")
    
    # Create columns for metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Recommendation",
            result.get("recommendation", "N/A")
        )
    
    with col2:
        st.metric(
            "Risk Level",
            result.get("risk_level", "N/A")
        )
    
    with col3:
        confidence = result.get("confidence", "N/A")
        if isinstance(confidence, (int, float)):
            confidence = f"{confidence:.1f}%"
        st.metric("Confidence", confidence)
    
    # Display entry points
    st.subheader("Entry Points")
    entry_points = result.get("entry_points", [])
    if entry_points:
        for point in entry_points:
            if isinstance(point, (int, float)):
                st.markdown(f"- ${point:.2f}")
            else:
                st.markdown(f"- {point}")
    else:
        st.info("No entry points specified.")
    
    # Display exit points
    st.subheader("Exit Points")
    exit_points = result.get("exit_points", [])
    if exit_points:
        for point in exit_points:
            if isinstance(point, (int, float)):
                st.markdown(f"- ${point:.2f}")
            else:
                st.markdown(f"- {point}")
    else:
        st.info("No exit points specified.")
    
    # Display technical indicators
    if "technical_indicators" in result:
        st.subheader("Technical Indicators")
        for indicator, value in result["technical_indicators"].items():
            st.markdown(f"- **{indicator}**: {value}")
    
    # Display trading strategy
    if "trading_strategy" in result:
        st.subheader("Trading Strategy")
        st.write(result["trading_strategy"])

def display_technical_insights(technical_analysis):
    """
    Display technical analysis insights in a structured format
    
    Args:
        technical_analysis: Dictionary containing technical analysis results
    """
    if not technical_analysis:
        st.info("No technical analysis data available.")
        return
        
    # Display trend analysis
    st.subheader("Trend Analysis")
    trend_col1, trend_col2 = st.columns(2)
    
    with trend_col1:
        st.markdown("#### Short-term Trend")
        if "short_term_trend" in technical_analysis:
            trend = technical_analysis["short_term_trend"]
            st.markdown(f"**Direction:** {trend.get('direction', 'N/A')}")
            st.markdown(f"**Strength:** {trend.get('strength', 'N/A')}")
            st.markdown(f"**Key Support:** ${trend.get('support', 0):.2f}")
            st.markdown(f"**Key Resistance:** ${trend.get('resistance', 0):.2f}")
    
    with trend_col2:
        st.markdown("#### Medium-term Trend")
        if "medium_term_trend" in technical_analysis:
            trend = technical_analysis["medium_term_trend"]
            st.markdown(f"**Direction:** {trend.get('direction', 'N/A')}")
            st.markdown(f"**Strength:** {trend.get('strength', 'N/A')}")
            st.markdown(f"**Key Support:** ${trend.get('support', 0):.2f}")
            st.markdown(f"**Key Resistance:** ${trend.get('resistance', 0):.2f}")
    
    # Display technical indicators
    st.subheader("Technical Indicators")
    
    # Create three columns for different types of indicators
    trend_indicators, momentum_indicators, volatility_indicators = st.columns(3)
    
    with trend_indicators:
        st.markdown("#### Trend Indicators")
        if "moving_averages" in technical_analysis:
            ma = technical_analysis["moving_averages"]
            st.markdown(f"**MA(20):** ${ma.get('MA20', 0):.2f}")
            st.markdown(f"**MA(50):** ${ma.get('MA50', 0):.2f}")
            st.markdown(f"**MA(200):** ${ma.get('MA200', 0):.2f}")
        
        if "macd" in technical_analysis:
            macd = technical_analysis["macd"]
            st.markdown(f"**MACD:** {macd.get('signal', 'N/A')}")
            st.markdown(f"**MACD Value:** {macd.get('value', 0):.3f}")
            st.markdown(f"**Signal Line:** {macd.get('signal_line', 0):.3f}")
    
    with momentum_indicators:
        st.markdown("#### Momentum Indicators")
        if "rsi" in technical_analysis:
            rsi = technical_analysis["rsi"]
            st.markdown(f"**RSI(14):** {rsi.get('value', 0):.2f}")
            st.markdown(f"**RSI Signal:** {rsi.get('signal', 'N/A')}")
        
        if "stochastic" in technical_analysis:
            stoch = technical_analysis["stochastic"]
            st.markdown(f"**%K:** {stoch.get('k', 0):.2f}")
            st.markdown(f"**%D:** {stoch.get('d', 0):.2f}")
            st.markdown(f"**Signal:** {stoch.get('signal', 'N/A')}")
    
    with volatility_indicators:
        st.markdown("#### Volatility Indicators")
        if "bollinger_bands" in technical_analysis:
            bb = technical_analysis["bollinger_bands"]
            st.markdown(f"**Upper Band:** ${bb.get('upper', 0):.2f}")
            st.markdown(f"**Middle Band:** ${bb.get('middle', 0):.2f}")
            st.markdown(f"**Lower Band:** ${bb.get('lower', 0):.2f}")
            st.markdown(f"**Width:** {bb.get('width', 0):.2f}%")
    
    # Display pattern analysis if available
    if "patterns" in technical_analysis:
        st.subheader("Pattern Analysis")
        patterns = technical_analysis["patterns"]
        if patterns:
            for pattern in patterns:
                st.markdown(f"- **{pattern['name']}**: {pattern['description']}")
                st.markdown(f"  - Confidence: {pattern['confidence']}%")
                st.markdown(f"  - Signal: {pattern['signal']}")
        else:
            st.info("No significant patterns detected.")
    
    # Display volume analysis
    if "volume_analysis" in technical_analysis:
        st.subheader("Volume Analysis")
        volume = technical_analysis["volume_analysis"]
        vol_col1, vol_col2 = st.columns(2)
        
        with vol_col1:
            st.markdown(f"**Average Volume:** {volume.get('average', 0):,.0f}")
            st.markdown(f"**Volume Trend:** {volume.get('trend', 'N/A')}")
        
        with vol_col2:
            st.markdown(f"**Volume Signal:** {volume.get('signal', 'N/A')}")
            st.markdown(f"**Unusual Activity:** {volume.get('unusual_activity', 'None')}")

def display_learning_points(result):
    """
    Display learning points section
    
    Args:
        result: Analysis result
    """
    if "learning_points" not in result or not result["learning_points"]:
        st.warning("No learning points available")
        return
    
    points = result["learning_points"]
    
    for i, point in enumerate(points, 1):
        st.markdown(f"{i}. {point}")

def display_technical_indicators(ticker):
    """
    Display technical indicators section
    
    Args:
        ticker: Ticker symbol
    """
    # Check if we have indicator data for this ticker
    if ticker not in st.session_state.indicator_data:
        # Try to collect indicators
        with st.spinner(f"Collecting technical indicators for {ticker}..."):
            indicators_data = collect_technical_indicators(ticker)
            
            if not indicators_data:
                st.warning(f"No technical indicator data available for {ticker}")
                return
    else:
        indicators_data = st.session_state.indicator_data[ticker]
    
    # Display available indicators
    st.subheader("Available Technical Indicators")
    
    # Group indicators by category
    indicators_by_category = {}
    for name, data in indicators_data.items():
        category = data.get('category', 'unknown')
        if category not in indicators_by_category:
            indicators_by_category[category] = []
        indicators_by_category[category].append(name)
    
    # Display indicators by category
    for category, indicators in indicators_by_category.items():
        st.write(f"**{category.capitalize()} Indicators:**")
        for indicator in indicators:
            st.markdown(f"- {indicator}")
    
    # Allow user to select an indicator for trend analysis
    selected_indicator = st.selectbox(
        "Select an indicator for trend analysis",
        list(indicators_data.keys())
    )
    
    days = st.slider("Number of days for trend analysis", 5, 60, 30)
    
    if st.button(f"Analyze {selected_indicator} Trends"):
        with st.spinner(f"Analyzing {selected_indicator} trends for {ticker}..."):
            trend_data = get_indicator_trends(ticker, selected_indicator, days)
            
            if trend_data and 'error' not in trend_data:
                display_indicator_trends(ticker, selected_indicator, trend_data)
            else:
                st.error(f"Error getting trend data: {trend_data.get('error', 'Unknown error')}")

def display_indicator_trends(ticker, indicator_name, trend_data):
    """
    Display indicator trends
    
    Args:
        ticker: Ticker symbol
        indicator_name: Name of the indicator
        trend_data: Trend data dictionary
    """
    st.subheader(f"{indicator_name} Trends for {ticker}")
    
    # Check if we have timestamps and values
    if not trend_data.get('timestamps') or not trend_data.get('values'):
        st.warning("No trend data available")
        return
    
    # Create a figure for each value
    for key, values in trend_data['values'].items():
        if not values:
            continue
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=trend_data['timestamps'],
            y=values,
            mode='lines+markers',
            name=key,
            line=dict(width=2),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            title=f"{indicator_name} - {key}",
            xaxis_title="Date",
            yaxis_title="Value",
            height=400,
            hovermode="x unified"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Display signals if available
    if trend_data.get('signals'):
        st.subheader("Signal History")
        
        for signal_type, signals in trend_data['signals'].items():
            if not signals:
                continue
            
            st.write(f"**{signal_type}:**")
            
            # Create a dataframe for the signals
            signal_data = []
            for i, signal in enumerate(signals):
                if i < len(trend_data['timestamps']):
                    signal_data.append({
                        "Date": trend_data['timestamps'][i],
                        "Signal": signal
                    })
            
            if signal_data:
                df = pd.DataFrame(signal_data)
                st.dataframe(df)

def display_analysis_history(ticker):
    """
    Display analysis history section
    
    Args:
        ticker: Ticker symbol
    """
    history = get_analysis_history(ticker)
    
    if not history:
        st.warning(f"No analysis history available for {ticker}")
        return
    
    # Create a dataframe for the history
    history_data = []
    
    for analysis in history:
        timestamp = datetime.fromisoformat(analysis["timestamp"]).strftime("%Y-%m-%d %H:%M")
        
        # Extract key information
        sentiment = analysis.get("market_sentiment", "unknown")
        recommendation = analysis.get("recommendation", "unknown")
        price = analysis.get("current_price", 0)
        
        # Get the latest price update if available
        latest_price = price
        price_change = 0
        
        if "price_history" in analysis and analysis["price_history"]:
            latest = analysis["price_history"][-1]
            latest_price = latest["price"]
            price_change = ((latest_price - price) / price) * 100 if price > 0 else 0
        
        history_data.append({
            "Date": timestamp,
            "Price": f"${price:.2f}",
            "Latest Price": f"${latest_price:.2f}",
            "Change": f"{price_change:.2f}%",
            "Sentiment": sentiment,
            "Recommendation": recommendation
        })
    
    # Create a dataframe
    df = pd.DataFrame(history_data)
    
    # Display the dataframe
    st.dataframe(df)
    
    # Display accuracy metrics
    accuracy = get_recommendation_accuracy(ticker)
    
    if accuracy["total"] > 0:
        st.metric("Recommendation Accuracy", f"{accuracy['accuracy']*100:.1f}%", f"{accuracy['correct']}/{accuracy['total']} correct")

def display_feedback_form():
    """
    Display a form for user feedback
    """
    if st.session_state.analysis_id is None:
        st.warning("No analysis available for feedback")
        return
    
    with st.form("feedback_form"):
        st.subheader("Provide Feedback")
        
        feedback_type = st.selectbox(
            "Feedback Type",
            ["accuracy", "usefulness", "insight", "other"]
        )
        
        feedback_text = st.text_area(
            "Your Feedback",
            "The analysis was..."
        )
        
        submitted = st.form_submit_button("Submit Feedback")
        
        if submitted:
            success = add_user_feedback(
                analysis_id=st.session_state.analysis_id,
                feedback_type=feedback_type,
                feedback_text=feedback_text
            )
            
            if success:
                st.success("Feedback submitted successfully!")
            else:
                st.error("Error submitting feedback")

def store_trend_analysis(ticker, trend_text):
    """
    Parse and store trend analysis data from text
    
    Args:
        ticker: Ticker symbol
        trend_text: Text containing trend analysis data
        
    Returns:
        ID of the stored analysis
    """
    try:
        # Parse the trend analysis text
        analysis_data = st.session_state.trend_storage.parse_trend_analysis_from_text(trend_text)
        
        # Store the analysis
        analysis_id = st.session_state.trend_storage.store_trend_analysis(ticker, analysis_data)
        
        # Store the ID in session state
        st.session_state.trend_analysis_id = analysis_id
        
        return analysis_id
    
    except Exception as e:
        logger.error(f"Error storing trend analysis: {str(e)}")
        return None

def get_trend_analysis_history(ticker, limit=5):
    """
    Get historical trend analysis data for a ticker
    
    Args:
        ticker: Ticker symbol
        limit: Maximum number of records to retrieve
        
    Returns:
        List of trend analysis records
    """
    try:
        return st.session_state.trend_storage.get_trend_analysis_history(ticker, limit)
    
    except Exception as e:
        logger.error(f"Error getting trend analysis history: {str(e)}")
        return []

def get_trend_indicator_history(ticker, indicator, limit=10):
    """
    Get historical values for a specific trend indicator
    
    Args:
        ticker: Ticker symbol
        indicator: Indicator name
        limit: Maximum number of records to retrieve
        
    Returns:
        Dictionary with trend data
    """
    try:
        return st.session_state.trend_storage.get_indicator_trends(ticker, indicator, limit)
    
    except Exception as e:
        logger.error(f"Error getting trend indicator history: {str(e)}")
        return {"error": str(e)}

def verify_trend_prediction(trend_analysis_id, prediction_type, prediction_value, target_price, actual_price, was_correct, accuracy_score):
    """
    Store verification of a trend prediction
    
    Args:
        trend_analysis_id: ID of the trend analysis
        prediction_type: Type of prediction (e.g., "short_term", "medium_term")
        prediction_value: Value of the prediction (e.g., "bullish", "bearish")
        target_price: Target price from the prediction
        actual_price: Actual price at verification time
        was_correct: Whether the prediction was correct
        accuracy_score: Score representing prediction accuracy (0.0-1.0)
        
    Returns:
        ID of the stored verification
    """
    try:
        return st.session_state.trend_storage.store_prediction_verification(
            trend_analysis_id=trend_analysis_id,
            prediction_type=prediction_type,
            prediction_value=prediction_value,
            target_price=target_price,
            actual_price=actual_price,
            was_correct=was_correct,
            accuracy_score=accuracy_score
        )
    
    except Exception as e:
        logger.error(f"Error verifying trend prediction: {str(e)}")
        return None

def get_trend_prediction_accuracy(ticker, prediction_type=None):
    """
    Get trend prediction accuracy metrics for a ticker
    
    Args:
        ticker: Ticker symbol
        prediction_type: Optional type of prediction to filter by
        
    Returns:
        Dictionary with accuracy metrics
    """
    try:
        return st.session_state.trend_storage.get_prediction_accuracy(ticker, prediction_type)
    
    except Exception as e:
        logger.error(f"Error getting trend prediction accuracy: {str(e)}")
        return {}

def display_trend_analysis_history(ticker):
    """
    Display trend analysis history section
    
    Args:
        ticker: Ticker symbol
    """
    history = get_trend_analysis_history(ticker)
    
    if not history:
        st.warning(f"No trend analysis history available for {ticker}")
        return
    
    # Create a dataframe for the history
    history_data = []
    
    for analysis in history:
        timestamp = datetime.fromisoformat(analysis["timestamp"]).strftime("%Y-%m-%d %H:%M")
        
        # Extract key information
        primary_trend = analysis.get("primary_trend", "unknown")
        trend_strength = analysis.get("trend_strength", 0)
        rsi_value = analysis.get("rsi_value", 0)
        rsi_condition = analysis.get("rsi_condition", "unknown")
        macd_signal = analysis.get("macd_signal", "unknown")
        
        history_data.append({
            "Date": timestamp,
            "Primary Trend": primary_trend,
            "Trend Strength": f"{trend_strength}%",
            "RSI": f"{rsi_value} ({rsi_condition})",
            "MACD": macd_signal
        })
    
    # Create a dataframe
    df = pd.DataFrame(history_data)
    
    # Display the dataframe
    st.dataframe(df)
    
    # Display accuracy metrics
    accuracy = get_trend_prediction_accuracy(ticker)
    
    if 'overall' in accuracy and accuracy['overall']['total_predictions'] > 0:
        overall = accuracy['overall']
        st.metric(
            "Prediction Accuracy", 
            f"{overall['accuracy']*100:.1f}%", 
            f"{overall['correct_predictions']}/{overall['total_predictions']} correct"
        )
    
    # Allow user to select an indicator for trend history
    st.subheader("Trend Indicator History")
    
    indicator_options = [
        "trend_strength", "rsi_value", "macd_strength", 
        "bollinger_bandwidth", "support_confidence", "resistance_confidence",
        "short_term_confidence", "medium_term_confidence", "overall_confidence"
    ]
    
    selected_indicator = st.selectbox(
        "Select an indicator to view historical trends",
        indicator_options,
        format_func=lambda x: x.replace("_", " ").title()
    )
    
    if st.button(f"View {selected_indicator.replace('_', ' ').title()} History"):
        with st.spinner(f"Loading {selected_indicator} history..."):
            trend_data = get_trend_indicator_history(ticker, selected_indicator, limit=20)
            
            if trend_data and 'error' not in trend_data:
                display_trend_indicator_history(ticker, selected_indicator, trend_data)
            else:
                st.error(f"Error getting trend data: {trend_data.get('error', 'Unknown error')}")

def display_trend_indicator_history(ticker, indicator_name, trend_data):
    """
    Display trend indicator history
    
    Args:
        ticker: Ticker symbol
        indicator_name: Name of the indicator
        trend_data: Trend data dictionary
    """
    st.subheader(f"{indicator_name.replace('_', ' ').title()} History for {ticker}")
    
    # Check if we have timestamps and values
    if not trend_data.get('timestamps') or not trend_data.get('values'):
        st.warning("No trend data available")
        return
    
    # Create a figure
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=trend_data['timestamps'],
        y=trend_data['values'],
        mode='lines+markers',
        name=indicator_name.replace('_', ' ').title(),
        line=dict(width=2),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        title=f"{indicator_name.replace('_', ' ').title()} History",
        xaxis_title="Date",
        yaxis_title="Value",
        height=400,
        hovermode="x unified"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Create a dataframe for the history
    history_data = []
    
    for i, timestamp in enumerate(trend_data['timestamps']):
        if i < len(trend_data['values']):
            history_data.append({
                "Date": timestamp,
                indicator_name.replace('_', ' ').title(): trend_data['values'][i]
            })
    
    if history_data:
        df = pd.DataFrame(history_data)
        st.dataframe(df)

def generate_and_store_trend_analysis(ticker, analysis_result):
    """
    Generate and store trend analysis from analysis result
    
    Args:
        ticker: Ticker symbol
        analysis_result: Analysis result dictionary
        
    Returns:
        ID of the stored trend analysis
    """
    try:
        if not analysis_result or "error" in analysis_result:
            logger.error(f"Cannot generate trend analysis: Invalid analysis result")
            return None
            
        # Extract trend data from analysis result
        trend_data = {}
        
        # Extract primary trend
        if "ticker_analysis" in analysis_result and ticker in analysis_result["ticker_analysis"]:
            ticker_analysis = analysis_result["ticker_analysis"][ticker]
            
            if "technical_indicators" in ticker_analysis:
                tech = ticker_analysis["technical_indicators"]
                trend_data["primary_trend"] = tech.get("trend", "NEUTRAL").upper()
                trend_data["trend_strength"] = int(tech.get("strength", "50").replace("%", ""))
                trend_data["trend_duration"] = "short-term"  # Default
                
                # Extract support and resistance levels
                if "key_levels" in tech:
                    levels = tech["key_levels"]
                    trend_data["support_levels"] = levels.get("support", [])
                    trend_data["resistance_levels"] = levels.get("resistance", [])
                    trend_data["support_confidence"] = 70  # Default
                    trend_data["resistance_confidence"] = 70  # Default
        
        # Extract RSI data
        if "technical_insights" in analysis_result:
            for insight in analysis_result["technical_insights"]:
                if insight.get("indicator") == "RSI":
                    trend_data["rsi_value"] = float(insight.get("value", 50))
                    signal = insight.get("signal", "").lower()
                    
                    if "oversold" in signal:
                        trend_data["rsi_condition"] = "OVERSOLD"
                    elif "overbought" in signal:
                        trend_data["rsi_condition"] = "OVERBOUGHT"
                    else:
                        trend_data["rsi_condition"] = "NEUTRAL"
                
                elif insight.get("indicator") == "MACD":
                    trend_data["macd_signal"] = insight.get("signal", "NEUTRAL").upper()
                    trend_data["macd_strength"] = int(insight.get("strength", "50").replace("%", ""))
                
                elif insight.get("indicator") == "Bollinger Bands":
                    position = insight.get("description", "").lower()
                    if "lower" in position:
                        trend_data["bollinger_position"] = "lower"
                    elif "upper" in position:
                        trend_data["bollinger_position"] = "upper"
                    else:
                        trend_data["bollinger_position"] = "middle"
                    
                    trend_data["bollinger_bandwidth"] = 50  # Default
                    trend_data["bollinger_squeeze"] = False  # Default
        
        # Set price targets
        if "ticker_analysis" in analysis_result and ticker in analysis_result["ticker_analysis"]:
            ticker_analysis = analysis_result["ticker_analysis"][ticker]
            current_price = ticker_analysis.get("current_price", 0)
            
            if "price_targets" in ticker_analysis:
                targets = ticker_analysis["price_targets"]
                
                if "short_term" in targets:
                    short_term = targets["short_term"]
                    trend_data["short_term_bullish_target"] = short_term.get("target", current_price * 1.05)
                    trend_data["short_term_bearish_target"] = current_price * 0.95  # Default
                    trend_data["short_term_confidence"] = int(short_term.get("confidence", "50").replace("%", ""))
                    trend_data["short_term_timeframe"] = short_term.get("timeframe", "1-2 weeks")
                else:
                    # Default values
                    trend_data["short_term_bullish_target"] = current_price * 1.05
                    trend_data["short_term_bearish_target"] = current_price * 0.95
                    trend_data["short_term_confidence"] = 50
                    trend_data["short_term_timeframe"] = "1-2 weeks"
                
                if "long_term" in targets:
                    long_term = targets["long_term"]
                    trend_data["medium_term_bullish_target"] = long_term.get("target", current_price * 1.10)
                    trend_data["medium_term_bearish_target"] = current_price * 0.90  # Default
                    trend_data["medium_term_confidence"] = int(long_term.get("confidence", "50").replace("%", ""))
                    trend_data["medium_term_timeframe"] = long_term.get("timeframe", "1-3 months")
                else:
                    # Default values
                    trend_data["medium_term_bullish_target"] = current_price * 1.10
                    trend_data["medium_term_bearish_target"] = current_price * 0.90
                    trend_data["medium_term_confidence"] = 50
                    trend_data["medium_term_timeframe"] = "1-3 months"
            
            # Set risk assessment
            if "trading_strategy" in ticker_analysis:
                strategy = ticker_analysis["trading_strategy"]
                trend_data["stop_loss"] = strategy.get("stop_loss", current_price * 0.95)
                trend_data["risk_reward_ratio"] = 1.5  # Default
                trend_data["volatility_risk"] = "MEDIUM"  # Default
                trend_data["risk_factors"] = ["Market sentiment", "Technical levels", "Volatility"]  # Default
            else:
                # Default values
                trend_data["stop_loss"] = current_price * 0.95
                trend_data["risk_reward_ratio"] = 1.5
                trend_data["volatility_risk"] = "MEDIUM"
                trend_data["risk_factors"] = ["Market sentiment", "Technical levels", "Volatility"]
        
        # Set analysis summary and confidence
        if "market_overview" in analysis_result:
            overview = analysis_result["market_overview"]
            trend_data["analysis_summary"] = overview.get("summary", "No summary available")
            trend_data["overall_confidence"] = 65  # Default
        
        # Store the trend analysis
        analysis_id = st.session_state.trend_storage.store_trend_analysis(ticker, trend_data)
        
        # Store the ID in session state
        st.session_state.trend_analysis_id = analysis_id
        
        return analysis_id
    
    except Exception as e:
        logger.error(f"Error generating and storing trend analysis: {str(e)}")
        return None

def display_price_target_verification(ticker, price_targets):
    """
    Display verification information for price targets
    
    Args:
        ticker: Ticker symbol
        price_targets: Dictionary containing price target information
    """
    st.subheader("Price Target Verification")
    
    if not price_targets:
        st.info("No price targets available for verification.")
        return
    
    # Create tabs for different timeframes
    short_term_tab, medium_term_tab, accuracy_tab = st.tabs([
        "Short-term Targets",
        "Medium-term Targets",
        "Historical Accuracy"
    ])
    
    with short_term_tab:
        st.subheader("Short-term Price Targets")
        
        if 'short_term' in price_targets:
            short_term = price_targets['short_term']
            
            # Create columns for target details
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Target Price", f"${short_term['target']:.2f}")
            with col2:
                st.metric("Timeframe", short_term['timeframe'])
            with col3:
                st.metric("Confidence", f"{short_term['confidence']}%")
            
            # Get verification status
            try:
                verification = st.session_state.trend_storage.get_prediction_accuracy(
                    ticker, prediction_type='short_term'
                )
                
                if verification:
                    st.markdown("### Verification Status")
                    status_col1, status_col2, status_col3 = st.columns(3)
                    
                    with status_col1:
                        status = "🟢 Hit" if verification.get('was_correct', False) else "🔴 Missed"
                        st.metric("Status", status)
                    with status_col2:
                        accuracy = verification.get('accuracy', 0)
                        st.metric("Accuracy", f"{accuracy*100:.1f}%")
                    with status_col3:
                        days = verification.get('days_to_target')
                        if days:
                            st.metric("Days to Target", str(days))
                        else:
                            st.metric("Days to Target", "Pending")
            except Exception as e:
                logger.error(f"Error getting short-term verification: {str(e)}")
        else:
            st.info("No short-term targets available.")
    
    with medium_term_tab:
        st.subheader("Medium-term Price Targets")
        
        if 'medium_term' in price_targets:
            medium_term = price_targets['medium_term']
            
            # Create columns for target details
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Target Price", f"${medium_term['target']:.2f}")
            with col2:
                st.metric("Timeframe", medium_term['timeframe'])
            with col3:
                st.metric("Confidence", f"{medium_term['confidence']}%")
            
            # Get verification status
            try:
                verification = st.session_state.trend_storage.get_prediction_accuracy(
                    ticker, prediction_type='medium_term'
                )
                
                if verification:
                    st.markdown("### Verification Status")
                    status_col1, status_col2, status_col3 = st.columns(3)
                    
                    with status_col1:
                        status = "🟢 Hit" if verification.get('was_correct', False) else "🔴 Missed"
                        st.metric("Status", status)
                    with status_col2:
                        accuracy = verification.get('accuracy', 0)
                        st.metric("Accuracy", f"{accuracy*100:.1f}%")
                    with status_col3:
                        days = verification.get('days_to_target')
                        if days:
                            st.metric("Days to Target", str(days))
                        else:
                            st.metric("Days to Target", "Pending")
            except Exception as e:
                logger.error(f"Error getting medium-term verification: {str(e)}")
        else:
            st.info("No medium-term targets available.")
    
    with accuracy_tab:
        st.subheader("Historical Prediction Accuracy")
        
        try:
            accuracy_metrics = st.session_state.trend_storage.get_prediction_accuracy(ticker)
            
            if accuracy_metrics:
                # Overall accuracy
                if 'overall' in accuracy_metrics:
                    overall = accuracy_metrics['overall']
                    st.markdown("### Overall Performance")
                    
                    overall_col1, overall_col2, overall_col3 = st.columns(3)
                    
                    with overall_col1:
                        accuracy = overall.get('accuracy', 0)
                        st.metric("Overall Accuracy", f"{accuracy*100:.1f}%")
                    with overall_col2:
                        correct = overall.get('correct_predictions', 0)
                        total = overall.get('total_predictions', 0)
                        st.metric("Correct Predictions", f"{correct}/{total}")
                    with overall_col3:
                        avg_days = overall.get('avg_days_to_target', 0)
                        st.metric("Avg Days to Target", f"{avg_days:.1f}")
                
                # Recent verifications
                st.markdown("### Recent Verifications")
                
                recent_verifications = st.session_state.trend_storage.get_trend_analysis_history(
                    ticker, limit=5
                )
                
                if recent_verifications:
                    verification_data = []
                    for v in recent_verifications:
                        if 'verification_date' in v:
                            verification_data.append({
                                'Date': v['verification_date'],
                                'Type': v['prediction_type'],
                                'Target': f"${v['target_price']:.2f}",
                                'Actual': f"${v['actual_price']:.2f}",
                                'Status': "Hit" if v['was_correct'] else "Missed",
                                'Accuracy': f"{v['accuracy_score']*100:.1f}%"
                            })
                    
                    if verification_data:
                        df = pd.DataFrame(verification_data)
                        st.dataframe(df)
                        
                        # Create an accuracy trend chart
                        try:
                            fig = px.line(df, x='Date', y='Accuracy',
                                        title='Prediction Accuracy Trend',
                                        labels={'Accuracy': 'Accuracy (%)'})
                            st.plotly_chart(fig)
                        except Exception as e:
                            logger.error(f"Error creating accuracy trend chart: {str(e)}")
                else:
                    st.info("No recent verifications available.")
            else:
                st.info("No accuracy metrics available yet.")
        except Exception as e:
            logger.error(f"Error getting accuracy metrics: {str(e)}")
            st.error("Error retrieving accuracy metrics.")

def display_analysis(result, ticker):
    """
    Display the analysis result in a structured format with tabs
    
    Args:
        result: Analysis result dictionary
        ticker: Ticker symbol
    """
    if result is None:
        st.error("No analysis result available. Please run the analysis first.")
        return
        
    # Create tabs for different sections
    overview_tab, analysis_tab, tech_tab, learning_tab, verification_tab, timeline_tab = st.tabs([
        "Market Overview", 
        "Ticker Analysis", 
        "Technical Insights",
        "Learning Points",
        "Price Target Verification",
        "Prediction Timeline"
    ])
    
    with overview_tab:
        display_market_overview(result, ticker)
        
    with analysis_tab:
        display_ticker_analysis(result, ticker)
        
    with tech_tab:
        display_technical_insights(result.get('technical_analysis', {}))
        
    with learning_tab:
        display_learning_points(result)
        
    with verification_tab:
        # Get price targets from the result
        price_targets = {}
        if 'ticker_analysis' in result and ticker in result['ticker_analysis']:
            ticker_data = result['ticker_analysis'][ticker]
            if 'price_targets' in ticker_data:
                price_targets = ticker_data['price_targets']
        display_price_target_verification(ticker, price_targets)
        
    with timeline_tab:
        # Get historical predictions
        try:
            historical_predictions = st.session_state.trend_storage.get_trend_analysis_history(ticker)
            
            if not historical_predictions:
                st.info("No historical predictions available yet.")
            else:
                # Create a DataFrame for the predictions
                import pandas as pd
                
                prediction_data = []
                for pred in historical_predictions:
                    timestamp = pd.to_datetime(pred['timestamp'])
                    prediction_data.extend([
                        {
                            'Date': timestamp,
                            'Type': 'Short-term Bullish',
                            'Target': pred['short_term_bullish_target'],
                            'Confidence': pred['short_term_confidence'],
                            'Timeframe': pred['short_term_timeframe']
                        },
                        {
                            'Date': timestamp,
                            'Type': 'Short-term Bearish',
                            'Target': pred['short_term_bearish_target'],
                            'Confidence': pred['short_term_confidence'],
                            'Timeframe': pred['short_term_timeframe']
                        },
                        {
                            'Date': timestamp,
                            'Type': 'Medium-term Bullish',
                            'Target': pred['medium_term_bullish_target'],
                            'Confidence': pred['medium_term_confidence'],
                            'Timeframe': pred['medium_term_timeframe']
                        },
                        {
                            'Date': timestamp,
                            'Type': 'Medium-term Bearish',
                            'Target': pred['medium_term_bearish_target'],
                            'Confidence': pred['medium_term_confidence'],
                            'Timeframe': pred['medium_term_timeframe']
                        }
                    ])
                
                df = pd.DataFrame(prediction_data)
                
                # Display the predictions
                st.subheader("Historical Price Target Predictions")
                st.dataframe(df)
                
                # Create a line chart of price targets over time
                import plotly.express as px
                
                fig = px.line(df, x='Date', y='Target', color='Type',
                            title=f'Price Target History for {ticker}',
                            labels={'Target': 'Price Target ($)', 'Date': 'Prediction Date'})
                
                st.plotly_chart(fig)
                
        except Exception as e:
            st.error(f"Error retrieving prediction timeline: {str(e)}")
            logger.error(f"Error in prediction timeline: {str(e)}")

def main():
    """Main function for the Streamlit app"""
    st.title("AI Hedge Fund - Memory Enhanced Analysis")
    
    # Initialize session state
    if 'current_analysis' not in st.session_state:
        st.session_state.current_analysis = None
    
    # Sidebar
    with st.sidebar:
        st.header("Analysis Parameters")
        
        # Ticker input
        ticker = st.text_input("Enter Ticker Symbol", value="SPY").upper()
        
        # Analysis type selection
        analysis_type = st.selectbox(
            "Select Analysis Type",
            ["Basic", "Comprehensive", "Options Enhanced"],
            index=1
        )
        
        # Risk tolerance selection
        risk_tolerance = st.select_slider(
            "Risk Tolerance",
            options=["Very Low", "Low", "Moderate", "High", "Very High"],
            value="Moderate"
        )
        
        # Run analysis button
        if st.button("Run Analysis"):
            with st.spinner("Running analysis..."):
                try:
                    # Run the analysis
                    st.session_state.current_analysis = run_analysis(ticker, analysis_type, risk_tolerance)
                    
                    # Store trend analysis automatically
                    if st.session_state.current_analysis:
                        analysis_id = generate_and_store_trend_analysis(ticker, st.session_state.current_analysis)
                        if analysis_id:
                            logger.info(f"Automatically stored trend analysis for {ticker} with ID {analysis_id}")
                            
                    st.success("Analysis completed!")
                except Exception as e:
                    st.error(f"Error running analysis: {str(e)}")
                    logger.error(f"Error in analysis: {str(e)}", exc_info=True)
                    st.session_state.current_analysis = None
    
    # Display the analysis result if available
    if st.session_state.current_analysis is not None:
        display_analysis(st.session_state.current_analysis, ticker)
    else:
        st.info("Please enter a ticker symbol and run the analysis to get started.")
    
    # Display technical indicators
    st.header("Technical Indicators")
    display_technical_indicators(ticker)
    
    # Display trend analysis history
    st.header("Analysis History")
    display_trend_analysis_history(ticker)
    
    # Display feedback form
    st.header("Feedback")
    display_feedback_form()

if __name__ == "__main__":
    main() 