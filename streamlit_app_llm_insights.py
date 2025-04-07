import os
import logging
import re
import json
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import data connectors
from src.data.connectors.yahoo_finance import YahooFinanceConnector
from src.data.connectors.yahoo_finance_insights import YahooFinanceInsightsConnector
from src.data.connectors.real_time_finance import RealTimeFinanceConnector

# Import LLM module for analysis
from src.llm.analysis import analyze_with_gemini, gemini_generate_content
from src.llm.technicals import analyze_technicals_with_llm

# Set seaborn style for nicer plots
sns.set_style("whitegrid")

# Page configuration
st.set_page_config(
    page_title="AI Hedge Fund - Enhanced Insights",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Cache for market data
@st.cache_data(ttl=600)  # Cache for 10 minutes
def fetch_market_data(ticker):
    """Fetch market data for a ticker from various sources"""
    market_data = {}
    
    # Get Yahoo Finance data
    try:
        yf_connector = YahooFinanceConnector()
        
        # Get company profile
        company_info = yf_connector.get_company_profile(ticker)
        market_data["company_info"] = company_info

        # Get stock quote
        stock_quote = yf_connector.get_stock_quote(ticker)
        market_data["stock_quote"] = stock_quote
        
        # Get options expiration dates
        options_expirations = yf_connector.get_options_expiration_dates(ticker)
        market_data["options_expirations"] = options_expirations
        
        # Get options chain for the nearest expiration
        if options_expirations and len(options_expirations) > 0:
            nearest_exp = options_expirations[0]
            options_chain = yf_connector.get_options_chain(ticker, nearest_exp)
            market_data["options_chain"] = options_chain
    except Exception as e:
        logging.error(f"Error fetching Yahoo Finance data: {str(e)}")
    
    # Get Yahoo Finance Insights data
    try:
        yf_insights_connector = YahooFinanceInsightsConnector()
        insights = yf_insights_connector.get_condensed_insights(ticker)
        market_data["insights"] = insights
    except Exception as e:
        logging.error(f"Error fetching Yahoo Finance Insights: {str(e)}")
        market_data["insights"] = {"error": str(e)}
    
    # Get Real-Time Finance data
    try:
        rtf_connector = RealTimeFinanceConnector()
        
        # Get market trends
        market_trends = rtf_connector.get_gainers_and_losers()
        market_data["market_trends"] = market_trends
        
        # Get stock news
        stock_news = rtf_connector.get_stock_news(f"{ticker}:NASDAQ")
        if "data" in stock_news and "news" in stock_news["data"]:
            market_data["news"] = stock_news["data"]["news"][:5]  # Top 5 news articles
        else:
            market_data["news"] = []
    except Exception as e:
        logging.error(f"Error fetching Real-Time Finance data: {str(e)}")
        market_data["market_trends"] = {"gainers": [], "losers": []}
        market_data["news"] = []
    
    return market_data

@st.cache_data(ttl=3600)  # Cache for 1 hour
def analyze_with_llm(ticker, market_data):
    """Analyze market data with LLM"""
    return analyze_with_gemini(market_data, ticker)

@st.cache_data(ttl=3600)  # Cache for 1 hour
def analyze_technicals_with_gemini(ticker, timeframe="daily"):
    """Analyze technical indicators with Gemini"""
    return analyze_technicals_with_llm(ticker, timeframe)

def analyze_news_sentiment(news_articles):
    """Use Gemini to analyze news sentiment"""
    if not news_articles:
        return {"sentiment": "neutral", "analysis": "No recent news available."}
    
    # Create a prompt for Gemini
    prompt = "Analyze the sentiment of these news articles for a stock:\n\n"
    for article in news_articles:
        title = article.get("article_title", "")
        source = article.get("source", "")
        date = article.get("post_time_utc", "")
        prompt += f"- {title} ({source}, {date})\n"
    
    prompt += "\nProvide a sentiment analysis with the following details:\n"
    prompt += "1. Overall sentiment (positive, negative, or neutral)\n"
    prompt += "2. Key themes or events mentioned\n"
    prompt += "3. Potential impact on stock price (short-term and long-term)\n"
    prompt += "4. Confidence level in your assessment"
    
    # Call Gemini API with the prompt
    response = gemini_generate_content(prompt)
    
    # Parse the response (simple version - could be enhanced)
    sentiment = "neutral"
    if "positive" in response.lower():
        sentiment = "positive"
    elif "negative" in response.lower():
        sentiment = "negative"
    
    return {
        "sentiment": sentiment,
        "analysis": response
    }

def display_market_overview(market_data, ticker):
    """Display market overview section"""
    st.subheader("Market Overview")
    
    # Company info
    company_info = market_data.get("company_info", {})
    if "error" in company_info:
        st.error(f"Error retrieving company information: {company_info['error']}")
        return
    
    # Stock quote
    stock_quote = market_data.get("stock_quote", {})
    if "error" in stock_quote:
        st.error(f"Error retrieving stock quote: {stock_quote['error']}")
        return
    
    # Company metrics
    col1, col2, col3 = st.columns(3)
    
    # Column 1: Company info
    with col1:
        st.markdown("### Company Information")
        st.markdown(f"**Name:** {company_info.get('name', ticker)}")
        st.markdown(f"**Sector:** {company_info.get('sector', 'N/A')}")
        st.markdown(f"**Industry:** {company_info.get('industry', 'N/A')}")
        st.markdown(f"**Website:** [{company_info.get('website', 'N/A')}]({company_info.get('website', '#')})")
        
    # Column 2: Stock price
    with col2:
        st.markdown("### Price Information")
        current_price = stock_quote.get("price", {}).get("regularMarketPrice", "N/A")
        previous_close = stock_quote.get("price", {}).get("regularMarketPreviousClose", "N/A")
        
        if current_price != "N/A" and previous_close != "N/A":
            price_change = current_price - previous_close
            price_change_pct = (price_change / previous_close) * 100
            change_color = "green" if price_change >= 0 else "red"
            change_icon = "↑" if price_change >= 0 else "↓"
            
            st.markdown(f"**Current Price:** ${current_price:.2f}")
            st.markdown(f"**Change:** <span style='color:{change_color}'>{change_icon} ${abs(price_change):.2f} ({price_change_pct:.2f}%)</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"**Current Price:** ${current_price}")
            st.markdown(f"**Previous Close:** ${previous_close}")
            
        st.markdown(f"**Day Range:** ${stock_quote.get('price', {}).get('regularMarketDayLow', 'N/A')} - ${stock_quote.get('price', {}).get('regularMarketDayHigh', 'N/A')}")
        st.markdown(f"**52-Week Range:** ${stock_quote.get('summaryDetail', {}).get('fiftyTwoWeekLow', 'N/A')} - ${stock_quote.get('summaryDetail', {}).get('fiftyTwoWeekHigh', 'N/A')}")
    
    # Column 3: Key metrics
    with col3:
        st.markdown("### Key Metrics")
        st.markdown(f"**Market Cap:** ${stock_quote.get('summaryDetail', {}).get('marketCap', 'N/A')}")
        st.markdown(f"**P/E Ratio:** {stock_quote.get('summaryDetail', {}).get('trailingPE', 'N/A')}")
        st.markdown(f"**EPS (TTM):** ${stock_quote.get('summaryDetail', {}).get('trailingEps', 'N/A')}")
        st.markdown(f"**Volume:** {stock_quote.get('price', {}).get('regularMarketVolume', 'N/A')}")
        st.markdown(f"**Avg Volume:** {stock_quote.get('summaryDetail', {}).get('averageVolume', 'N/A')}")

def display_technical_insights(market_data, ticker):
    """Display technical insights section"""
    st.subheader("Technical Insights")
    
    insights = market_data.get("insights", {})
    if "error" in insights:
        st.error(f"Error retrieving insights: {insights['error']}")
        return
    
    col1, col2 = st.columns(2)
    
    # Column 1: Technical Events
    with col1:
        st.markdown("### Technical Signals")
        tech_events = insights.get("technical_events", {})
        if tech_events:
            data = [
                ["Short Term", tech_events.get("short_term", "N/A")],
                ["Mid Term", tech_events.get("mid_term", "N/A")],
                ["Long Term", tech_events.get("long_term", "N/A")]
            ]
            
            df = pd.DataFrame(data, columns=["Timeframe", "Signal"])
            st.dataframe(df, hide_index=True, use_container_width=True)
        else:
            st.info("No technical events data available.")
    
    # Column 2: Key Technical Levels
    with col2:
        st.markdown("### Key Technical Levels")
        key_tech = insights.get("key_technicals", {})
        if key_tech and all(key_tech.get(k) for k in ["support", "resistance", "stop_loss"]):
            data = [
                ["Support", key_tech.get("support", "N/A")],
                ["Resistance", key_tech.get("resistance", "N/A")],
                ["Stop Loss", key_tech.get("stop_loss", "N/A")]
            ]
            
            df = pd.DataFrame(data, columns=["Level Type", "Price"])
            st.dataframe(df, hide_index=True, use_container_width=True)
            
            # Plot technical levels
            try:
                # Convert values to float
                support = float(key_tech.get("support", 0))
                resistance = float(key_tech.get("resistance", 0))
                stop_loss = float(key_tech.get("stop_loss", 0))
                
                # Current price is assumed to be between support and resistance
                current_price = market_data.get("stock_quote", {}).get("price", {}).get("regularMarketPrice", 0)
                if not current_price:
                    current_price = (support + resistance) / 2
                
                # Create figure
                fig, ax = plt.subplots(figsize=(10, 6))
                
                # Plot price levels
                levels = {
                    "Resistance": resistance,
                    "Current Price": current_price,
                    "Support": support,
                    "Stop Loss": stop_loss
                }
                
                # Sort levels from highest to lowest
                sorted_levels = sorted(levels.items(), key=lambda x: x[1], reverse=True)
                
                # Colors for different levels
                colors = {
                    "Resistance": "red",
                    "Current Price": "green",
                    "Support": "blue",
                    "Stop Loss": "purple"
                }
                
                # Plot horizontal lines
                for name, value in sorted_levels:
                    ax.axhline(y=value, color=colors[name], linestyle='-', alpha=0.7, label=f"{name}: {value:.2f}")
                
                # Add labels and title
                ax.set_ylabel("Price ($)")
                ax.set_title(f"Key Technical Levels for {ticker}")
                ax.legend()
                ax.grid(True, alpha=0.3)
                
                # Adjust y-axis to show all levels with some padding
                min_value = min(levels.values())
                max_value = max(levels.values())
                range_value = max_value - min_value
                ax.set_ylim(min_value - range_value*0.1, max_value + range_value*0.1)
                
                # Show the plot
                plt.tight_layout()
                st.pyplot(fig)
                
            except Exception as e:
                st.error(f"Error creating technical chart: {str(e)}")
        else:
            st.info("No key technicals data available.")
    
    # Analyst Recommendations
    st.markdown("### Analyst Recommendations")
    recommendation = insights.get("recommendation", {})
    if recommendation:
        st.markdown(f"**Provider:** {recommendation.get('provider', 'N/A')}")
        st.markdown(f"**Rating:** {recommendation.get('rating', 'N/A')}")
        st.markdown(f"**Target Price:** ${recommendation.get('target_price', 'N/A')}")
        st.markdown(f"**Report Date:** {recommendation.get('date', 'N/A')}")
        st.markdown(f"**Title:** {recommendation.get('title', 'N/A')}")
    else:
        st.info("No analyst recommendations available.")
    
    # Recent Reports
    reports = insights.get("reports", [])
    if reports:
        with st.expander("View Recent Analyst Reports"):
            for i, report in enumerate(reports):
                st.markdown(f"**{i+1}. {report.get('title', 'N/A')}**")
                st.markdown(f"Provider: {report.get('provider', 'N/A')} | Rating: {report.get('rating', 'N/A')} | Target: ${report.get('target_price', 'N/A')}")
                st.markdown(f"Date: {report.get('date', 'N/A')}")
                st.markdown("---")

def display_market_trends(market_data, ticker):
    """Display market trends section"""
    st.subheader("Market Context")
    
    if "market_trends" not in market_data or not market_data["market_trends"].get("gainers", []):
        st.info("Market trend data not available")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Top Gainers")
        gainers_data = []
        for item in market_data["market_trends"]["gainers"][:5]:
            symbol = item.get("symbol", "").split(":")[0]
            is_current = symbol == ticker
            gainers_data.append({
                "Symbol": symbol,
                "Name": item.get("name", ""),
                "Change %": f"{item.get('change_percent', 0)*100:.2f}%",
                "Is Current": is_current
            })
        
        gainers_df = pd.DataFrame(gainers_data)
        
        # Highlight current ticker if it's in the list
        def highlight_row(row):
            if row["Is Current"]:
                return ['background-color: rgba(75, 192, 192, 0.2)'] * 3
            return [''] * 3
        
        # Apply styling and display
        styled_df = gainers_df[["Symbol", "Name", "Change %"]].style.apply(
            lambda x: highlight_row(gainers_df.iloc[x.name]), axis=1)
        st.dataframe(styled_df, hide_index=True, use_container_width=True)
    
    with col2:
        st.markdown("### Top Losers")
        losers_data = []
        for item in market_data["market_trends"]["losers"][:5]:
            symbol = item.get("symbol", "").split(":")[0]
            is_current = symbol == ticker
            losers_data.append({
                "Symbol": symbol,
                "Name": item.get("name", ""),
                "Change %": f"{item.get('change_percent', 0)*100:.2f}%",
                "Is Current": is_current
            })
        
        losers_df = pd.DataFrame(losers_data)
        
        # Apply styling and display
        styled_df = losers_df[["Symbol", "Name", "Change %"]].style.apply(
            lambda x: highlight_row(losers_df.iloc[x.name]), axis=1)
        st.dataframe(styled_df, hide_index=True, use_container_width=True)
    
    # Highlight if the current ticker is in either list
    ticker_in_gainers = any(item.get("symbol", "").split(":")[0] == ticker for item in market_data["market_trends"].get("gainers", []))
    ticker_in_losers = any(item.get("symbol", "").split(":")[0] == ticker for item in market_data["market_trends"].get("losers", []))
    
    if ticker_in_gainers:
        st.success(f"📈 {ticker} is among today's top gainers")
    elif ticker_in_losers:
        st.warning(f"📉 {ticker} is among today's top losers")
    else:
        st.info(f"{ticker} is not among today's top movers")

def display_news_analysis(market_data, ticker):
    """Display news analysis section"""
    st.subheader("News Analysis")
    
    news_articles = market_data.get("news", [])
    if not news_articles:
        st.info(f"No recent news available for {ticker}")
        return
    
    # Analyze sentiment with Gemini
    with st.spinner("Analyzing news sentiment..."):
        sentiment_analysis = analyze_news_sentiment(news_articles)
    
    # Display sentiment badge
    sentiment = sentiment_analysis.get("sentiment", "neutral")
    if sentiment == "positive":
        st.success("Overall Sentiment: Positive 📈")
    elif sentiment == "negative":
        st.error("Overall Sentiment: Negative 📉")
    else:
        st.info("Overall Sentiment: Neutral ⚖️")
    
    # Display sentiment analysis
    with st.expander("Sentiment Analysis", expanded=True):
        st.markdown(sentiment_analysis.get("analysis", "No analysis available"))
    
    # Display news articles
    st.subheader("Recent News Articles")
    for i, article in enumerate(news_articles):
        title = article.get("article_title", "No title")
        source = article.get("source", "Unknown source")
        date = article.get("post_time_utc", "")
        url = article.get("article_url", "")
        
        # Format the date
        try:
            if date:
                date_obj = datetime.fromisoformat(date.replace(' ', 'T'))
                date_formatted = date_obj.strftime("%Y-%m-%d %H:%M")
            else:
                date_formatted = "Unknown date"
        except:
            date_formatted = date
        
        # Create expandable news item
        with st.expander(f"{title}", expanded=i==0):
            st.markdown(f"**Source:** {source} | **Date:** {date_formatted}")
            if url:
                st.markdown(f"[Read full article]({url})")

def display_llm_analysis(market_data, ticker):
    """Display LLM analysis section"""
    st.subheader("AI Powered Analysis")
    
    with st.spinner("Generating LLM analysis..."):
        llm_analysis = analyze_with_llm(ticker, market_data)
    
    if "error" in llm_analysis:
        st.error(f"Error generating analysis: {llm_analysis['error']}")
        return
    
    st.markdown(llm_analysis)

def display_technical_analysis(ticker):
    """Display technical analysis section"""
    st.subheader("Technical Analysis")
    
    # Timeframe selection
    timeframe = st.selectbox(
        "Select Timeframe", 
        ["daily", "weekly", "monthly"],
        index=0
    )
    
    with st.spinner(f"Analyzing {timeframe} technical indicators..."):
        tech_analysis = analyze_technicals_with_gemini(ticker, timeframe)
    
    if "error" in tech_analysis:
        st.error(f"Error analyzing technicals: {tech_analysis['error']}")
        return
    
    st.markdown(tech_analysis)

def symbol_search_ui():
    """Create a UI component for searching and selecting stocks"""
    st.sidebar.subheader("Stock Search")
    
    # Get the search query
    search_query = st.sidebar.text_input("Search for a stock:", "")
    
    if not search_query:
        return None
    
    # Perform the search
    try:
        rtf_connector = RealTimeFinanceConnector()
        search_results = rtf_connector.get_symbol_search_results(search_query)
        
        if not search_results:
            st.sidebar.warning("No matching stocks found.")
            return None
        
        # Create options for the selectbox
        options = []
        for item in search_results[:10]:  # Limit to top 10 results
            symbol = item.get("symbol", "").split(":")[0]
            name = item.get("name", "")
            
            # Create a formatted option
            option_text = f"{symbol} - {name}"
            option_value = symbol
            
            options.append({"text": option_text, "value": option_value})
        
        # Display as a selectbox
        selected_option = st.sidebar.selectbox(
            "Select a stock:",
            options=[item["text"] for item in options],
            index=0 if options else None
        )
        
        # Get the selected ticker symbol
        if selected_option:
            selected_index = [item["text"] for item in options].index(selected_option)
            return options[selected_index]["value"]
    except Exception as e:
        logging.error(f"Error in symbol search: {str(e)}")
        st.sidebar.error("Error searching for stocks")
    
    return None

def main():
    """Main function to run the Streamlit application"""
    # App title
    st.title("AI Hedge Fund - Enhanced Market Insights")
    st.markdown("Powered by LLMs and Financial APIs")
    
    # Get ticker from search or user input
    ticker = symbol_search_ui()
    
    # If no ticker from search, use the direct input
    if not ticker:
        ticker = st.sidebar.text_input("Stock Symbol", "AAPL").upper()
    
    # Set the ticker to state
    st.session_state.ticker = ticker
    
    # Fetch market data
    with st.spinner(f"Fetching data for {ticker}..."):
        market_data = fetch_market_data(ticker)
    
    # Create tabs for different sections
    tabs = st.tabs([
        "Market Overview", 
        "Technical Insights",
        "Market Context",
        "News Analysis",
        "AI Analysis",
        "Technical Analysis"
    ])
    
    # Populate each tab with content
    with tabs[0]:
        display_market_overview(market_data, ticker)
    
    with tabs[1]:
        display_technical_insights(market_data, ticker)
    
    with tabs[2]:
        display_market_trends(market_data, ticker)
    
    with tabs[3]:
        display_news_analysis(market_data, ticker)
    
    with tabs[4]:
        display_llm_analysis(market_data, ticker)
    
    with tabs[5]:
        display_technical_analysis(ticker)

# Run the app
if __name__ == "__main__":
    main() 