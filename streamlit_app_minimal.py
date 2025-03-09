import streamlit as st
import pandas as pd
import os
import logging
import json
import requests
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check if plotly is available
try:
    import plotly.graph_objects as go
    import plotly.express as px
    plotly_available = True
    logger.info("Plotly is available")
except ImportError:
    plotly_available = False
    logger.warning("Plotly is not available, will use alternative visualizations")

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("Loaded environment variables from .env file")
except ImportError:
    logger.warning("python-dotenv not available, using existing environment variables")

# Try to load Streamlit secrets
try:
    if hasattr(st, 'secrets'):
        for key in st.secrets:
            if key not in os.environ:
                os.environ[key] = st.secrets[key]
                logger.info(f"Loaded environment variable from Streamlit secrets: {key}")
except Exception as e:
    logger.warning(f"Error loading Streamlit secrets: {str(e)}")

def fetch_stock_data(ticker):
    """Fetch basic stock data using Yahoo Finance API"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract basic information
            meta = data.get('chart', {}).get('result', [{}])[0].get('meta', {})
            timestamp = data.get('chart', {}).get('result', [{}])[0].get('timestamp', [])
            indicators = data.get('chart', {}).get('result', [{}])[0].get('indicators', {})
            
            # Get price data
            quote = indicators.get('quote', [{}])[0]
            
            # Create a simple dataframe
            if timestamp and quote.get('close'):
                df = pd.DataFrame({
                    'timestamp': [datetime.fromtimestamp(ts) for ts in timestamp],
                    'close': quote.get('close', []),
                    'open': quote.get('open', []),
                    'high': quote.get('high', []),
                    'low': quote.get('low', []),
                    'volume': quote.get('volume', [])
                })
                
                # Remove rows with NaN values
                df = df.dropna()
                
                return {
                    'success': True,
                    'data': df,
                    'current_price': meta.get('regularMarketPrice', 0),
                    'previous_close': meta.get('previousClose', 0),
                    'currency': meta.get('currency', 'USD')
                }
            else:
                return {
                    'success': False,
                    'error': 'No price data available'
                }
        else:
            return {
                'success': False,
                'error': f"API returned status {response.status_code}"
            }
    except Exception as e:
        logger.error(f"Error fetching stock data: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def display_stock_data(stock_data, ticker):
    """Display stock data"""
    if not stock_data.get('success', False):
        st.error(f"Error fetching data for {ticker}: {stock_data.get('error', 'Unknown error')}")
        return
    
    # Display current price and basic info
    current_price = stock_data.get('current_price', 0)
    previous_close = stock_data.get('previous_close', 0)
    currency = stock_data.get('currency', 'USD')
    
    # Calculate price change
    price_change = current_price - previous_close
    price_change_pct = (price_change / previous_close) * 100 if previous_close else 0
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Current Price",
            f"{currency} {current_price:.2f}",
            f"{price_change_pct:.2f}%"
        )
    
    # Display chart
    df = stock_data.get('data')
    if df is not None:
        st.subheader(f"{ticker} Price History")
        
        if plotly_available:
            # Use Plotly for interactive chart
            fig = px.line(
                df, 
                x='timestamp', 
                y='close',
                title=f"{ticker} Close Price"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Fallback to Streamlit's built-in chart
            st.line_chart(df.set_index('timestamp')['close'])
        
        # Show recent data
        st.subheader("Recent Data")
        st.dataframe(df.tail(10))

def main():
    st.set_page_config(
        page_title="Simple Stock Dashboard",
        page_icon="📈",
        layout="wide"
    )
    
    st.title("Simple Stock Dashboard")
    st.write("This is a minimal version of the stock dashboard that works with limited dependencies.")
    
    # Sidebar
    st.sidebar.header("Settings")
    ticker = st.sidebar.text_input("Enter Ticker Symbol", value="AAPL").upper()
    
    # Main content
    if st.button("Fetch Data"):
        with st.spinner(f"Fetching data for {ticker}..."):
            stock_data = fetch_stock_data(ticker)
            display_stock_data(stock_data, ticker)
    
    # Show environment info
    with st.expander("Environment Information"):
        st.write(f"Python version: {os.sys.version}")
        st.write(f"Pandas version: {pd.__version__}")
        st.write(f"Plotly available: {plotly_available}")
        
        # Check for API keys (without revealing them)
        api_key = os.environ.get("RAPIDAPI_KEY")
        if api_key:
            st.write(f"RAPIDAPI_KEY: {'*' * len(api_key)}")
        else:
            st.write("RAPIDAPI_KEY: Not found")

if __name__ == "__main__":
    main() 