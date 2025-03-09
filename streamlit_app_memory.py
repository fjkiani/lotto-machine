import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import os
import logging
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.llm.memory_enhanced_analysis import MemoryEnhancedAnalysis

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize session state
if 'memory_analyzer' not in st.session_state:
    st.session_state.memory_analyzer = MemoryEnhancedAnalysis()

if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = {}

if 'current_analysis' not in st.session_state:
    st.session_state.current_analysis = None

if 'current_ticker' not in st.session_state:
    st.session_state.current_ticker = None

if 'analysis_id' not in st.session_state:
    st.session_state.analysis_id = None

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
        if "memory" in result and "analysis_id" in result["memory"]:
            st.session_state.analysis_id = result["memory"]["analysis_id"]
        
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
        result: Analysis result
        ticker: Ticker symbol
    """
    if "market_overview" not in result:
        st.warning("No market overview available")
        return
    
    overview = result["market_overview"]
    
    # Create columns for metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sentiment = overview.get("sentiment", "N/A")
        sentiment_color = "green" if sentiment == "bullish" else "red" if sentiment == "bearish" else "gray"
        st.metric("Market Sentiment", sentiment)
    
    if "key_metrics" in overview:
        metrics = overview["key_metrics"]
        
        with col2:
            price = metrics.get("price", 0)
            day_change = metrics.get("day_change_pct", 0)
            st.metric("Current Price", f"${price:.2f}", f"{day_change:.2f}%")
        
        with col3:
            volume = metrics.get("volume", 0)
            avg_volume = metrics.get("avg_volume", 0)
            volume_change = ((volume - avg_volume) / avg_volume) * 100 if avg_volume > 0 else 0
            st.metric("Volume", f"{volume:,}", f"{volume_change:.2f}% vs Avg")
    
    # Display summary
    st.subheader("Market Summary")
    st.write(overview.get("summary", "No summary available"))

def display_ticker_analysis(result, ticker):
    """
    Display ticker analysis section
    
    Args:
        result: Analysis result
        ticker: Ticker symbol
    """
    if "ticker_analysis" not in result or ticker not in result["ticker_analysis"]:
        st.warning("No ticker analysis available")
        return
    
    analysis = result["ticker_analysis"][ticker]
    
    # Create columns for metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        recommendation = analysis.get("recommendation", "N/A")
        rec_color = "green" if recommendation == "buy" else "red" if recommendation == "sell" else "gray"
        st.metric("Recommendation", recommendation)
    
    with col2:
        risk_level = analysis.get("risk_level", "N/A")
        risk_color = "red" if risk_level == "high" else "orange" if risk_level == "medium" else "green"
        st.metric("Risk Level", risk_level)
    
    with col3:
        confidence = analysis.get("confidence", 0)
        st.metric("Confidence", f"{confidence*100:.1f}%")
    
    # Price targets
    if "price_target" in analysis:
        st.subheader("Price Targets")
        targets = analysis["price_target"]
        
        current_price = analysis.get("current_price", 0)
        
        # Create a gauge chart for price targets
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = current_price,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': f"{ticker} Price Target"},
            delta = {'reference': targets.get("median", current_price)},
            gauge = {
                'axis': {'range': [targets.get("low", current_price*0.8), targets.get("high", current_price*1.2)]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [targets.get("low", current_price*0.8), targets.get("median", current_price)], 'color': "lightgray"},
                    {'range': [targets.get("median", current_price), targets.get("high", current_price*1.2)], 'color': "gray"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': current_price
                }
            }
        ))
        
        st.plotly_chart(fig)
    
    # Support and resistance levels
    if "support_resistance" in analysis:
        st.subheader("Support & Resistance Levels")
        sr = analysis["support_resistance"]
        
        support_levels = sr.get("support_levels", [])
        resistance_levels = sr.get("resistance_levels", [])
        
        current_price = analysis.get("current_price", 0)
        
        # Create a range for the chart
        all_levels = support_levels + resistance_levels + [current_price]
        min_price = min(all_levels) * 0.95
        max_price = max(all_levels) * 1.05
        
        # Create a candlestick-like chart with support and resistance
        fig = go.Figure()
        
        # Add support levels
        for level in support_levels:
            fig.add_shape(
                type="line",
                x0=0,
                y0=level,
                x1=1,
                y1=level,
                line=dict(
                    color="green",
                    width=2,
                    dash="dash",
                ),
            )
        
        # Add resistance levels
        for level in resistance_levels:
            fig.add_shape(
                type="line",
                x0=0,
                y0=level,
                x1=1,
                y1=level,
                line=dict(
                    color="red",
                    width=2,
                    dash="dash",
                ),
            )
        
        # Add current price
        fig.add_shape(
            type="line",
            x0=0,
            y0=current_price,
            x1=1,
            y1=current_price,
            line=dict(
                color="blue",
                width=3,
            ),
        )
        
        # Add annotations
        fig.add_annotation(
            x=0.5,
            y=current_price,
            text=f"Current: ${current_price:.2f}",
            showarrow=False,
            yshift=10,
        )
        
        # Update layout
        fig.update_layout(
            title=f"{ticker} Support & Resistance Levels",
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
            ),
            yaxis=dict(
                range=[min_price, max_price],
            ),
            showlegend=False,
        )
        
        st.plotly_chart(fig)
    
    # Technical indicators
    if "technical_indicators" in analysis:
        st.subheader("Technical Indicators")
        indicators = analysis["technical_indicators"]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            ma = indicators.get("moving_averages", "N/A")
            ma_color = "green" if ma == "bullish" else "red" if ma == "bearish" else "gray"
            st.metric("Moving Averages", ma)
        
        with col2:
            rsi = indicators.get("rsi", 0)
            rsi_status = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else "Neutral"
            st.metric("RSI", f"{rsi:.1f}", rsi_status)
        
        with col3:
            macd = indicators.get("macd", "N/A")
            macd_color = "green" if macd == "bullish" else "red" if macd == "bearish" else "gray"
            st.metric("MACD", macd)

def display_trading_opportunities(result):
    """
    Display trading opportunities section
    
    Args:
        result: Analysis result
    """
    if "trading_opportunities" not in result or not result["trading_opportunities"]:
        st.warning("No trading opportunities available")
        return
    
    opportunities = result["trading_opportunities"]
    
    for i, opportunity in enumerate(opportunities, 1):
        st.subheader(f"Opportunity {i}: {opportunity.get('type', 'N/A').upper()} - {opportunity.get('direction', 'N/A').upper()}")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Ticker", opportunity.get("ticker", "N/A"))
        
        with col2:
            st.metric("Price Target", f"${opportunity.get('price_target', 0):.2f}")
        
        with col3:
            st.metric("Stop Loss", f"${opportunity.get('stop_loss', 0):.2f}")
        
        st.write(f"**Timeframe:** {opportunity.get('timeframe', 'N/A')}")
        st.write(f"**Rationale:** {opportunity.get('rationale', 'N/A')}")
        st.markdown("---")

def display_historical_comparison(result):
    """
    Display historical comparison section
    
    Args:
        result: Analysis result
    """
    if "historical_comparison" not in result:
        st.warning("No historical comparison available")
        return
    
    comparison = result["historical_comparison"]
    
    col1, col2 = st.columns(2)
    
    with col1:
        price_trend = comparison.get("price_trend", "N/A")
        price_color = "green" if price_trend == "improving" else "red" if price_trend == "deteriorating" else "gray"
        st.metric("Price Trend", price_trend)
    
    with col2:
        sentiment_change = comparison.get("sentiment_change", "N/A")
        sentiment_color = "green" if sentiment_change == "improving" else "red" if sentiment_change == "deteriorating" else "gray"
        st.metric("Sentiment Change", sentiment_change)
    
    st.subheader("Key Differences")
    for diff in comparison.get("key_differences", []):
        st.markdown(f"- {diff}")
    
    st.subheader("Prediction Accuracy")
    st.write(comparison.get("prediction_accuracy", "No prediction accuracy available"))

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
        sentiment = "unknown"
        recommendation = "unknown"
        price = 0
        
        if analysis["analysis_data"]:
            if "market_overview" in analysis["analysis_data"] and "sentiment" in analysis["analysis_data"]["market_overview"]:
                sentiment = analysis["analysis_data"]["market_overview"]["sentiment"]
            
            if "ticker_analysis" in analysis["analysis_data"] and ticker in analysis["analysis_data"]["ticker_analysis"]:
                ticker_data = analysis["analysis_data"]["ticker_analysis"][ticker]
                if "recommendation" in ticker_data:
                    recommendation = ticker_data["recommendation"]
                if "current_price" in ticker_data:
                    price = ticker_data["current_price"]
        
        # Get the latest price update if available
        latest_price = price
        price_change = 0
        
        if analysis["price_history"]:
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

def main():
    st.set_page_config(
        page_title="Memory-Enhanced Financial Analysis",
        page_icon="📈",
        layout="wide"
    )
    
    st.title("Memory-Enhanced Financial Analysis")
    st.markdown("""
    This app provides financial analysis with memory capabilities, learning from past analyses and user feedback.
    """)
    
    # Sidebar
    st.sidebar.header("Analysis Parameters")
    
    ticker = st.sidebar.text_input("Ticker Symbol", "AAPL").upper()
    
    analysis_type = st.sidebar.selectbox(
        "Analysis Type",
        ["basic", "technical", "fundamental", "comprehensive"],
        index=3
    )
    
    risk_tolerance = st.sidebar.selectbox(
        "Risk Tolerance",
        ["low", "medium", "high"],
        index=1
    )
    
    run_button = st.sidebar.button("Run Analysis")
    
    # Display memory stats
    st.sidebar.header("Memory Stats")
    
    if ticker:
        history = get_analysis_history(ticker, limit=1)
        has_history = len(history) > 0
        
        st.sidebar.metric("Analysis History", "Available" if has_history else "None")
        
        accuracy = get_recommendation_accuracy(ticker)
        if accuracy["total"] > 0:
            st.sidebar.metric("Recommendation Accuracy", f"{accuracy['accuracy']*100:.1f}%")
    
    # Run analysis when button is clicked
    if run_button:
        with st.spinner(f"Running memory-enhanced analysis for {ticker}..."):
            result = run_analysis(ticker, analysis_type, risk_tolerance)
            
            if "error" in result:
                st.error(f"Error: {result['error']}")
            else:
                st.success(f"Analysis completed for {ticker}")
    
    # Display current analysis if available
    if st.session_state.current_analysis and st.session_state.current_ticker == ticker:
        result = st.session_state.current_analysis
        
        # Create tabs for different sections
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Market Overview", 
            "Ticker Analysis", 
            "Trading Opportunities", 
            "Historical Comparison",
            "Analysis History"
        ])
        
        with tab1:
            display_market_overview(result, ticker)
        
        with tab2:
            display_ticker_analysis(result, ticker)
        
        with tab3:
            display_trading_opportunities(result)
        
        with tab4:
            display_historical_comparison(result)
        
        with tab5:
            display_analysis_history(ticker)
        
        # Display feedback form
        st.markdown("---")
        display_feedback_form()

if __name__ == "__main__":
    main() 