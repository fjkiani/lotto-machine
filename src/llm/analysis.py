import os
import json
import logging
from typing import Dict, Any, Optional, List
import google.generativeai as genai
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load and configure Gemini API
def setup_gemini_api():
    """Setup Gemini API with API key from environment"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment variables")
        raise ValueError("Gemini API key not found. Please set GEMINI_API_KEY in your .env file")
    
    genai.configure(api_key=api_key)
    logger.info("Gemini API configured successfully")

# Function to generate content with Gemini
def gemini_generate_content(prompt: str, 
                            model: str = "gemini-1.5-flash",
                            temperature: float = 0.7,
                            max_output_tokens: int = 2048) -> str:
    """
    Generate content using Google's Gemini model
    
    Args:
        prompt: The prompt to send to the model
        model: Model name (default: gemini-1.5-flash)
        temperature: Temperature for generation (higher = more creative)
        max_output_tokens: Maximum number of tokens in the output
    
    Returns:
        Generated content as string
    """
    try:
        # Ensure API is configured
        try:
            gen_model = genai.GenerativeModel(model)
        except:
            setup_gemini_api()
            gen_model = genai.GenerativeModel(model)
        
        # Configure generation parameters
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "top_p": 0.95
        }
        
        # Generate content
        response = gen_model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        return response.text
    except Exception as e:
        logger.error(f"Error generating content with Gemini: {str(e)}")
        return f"Error generating analysis: {str(e)}"

def analyze_with_gemini(market_data: Dict[str, Any], ticker: str) -> str:
    """
    Analyze market data using Gemini LLM
    
    Args:
        market_data: Market data from various sources
        ticker: The ticker symbol
    
    Returns:
        Analysis as markdown text
    """
    # Prepare the input for Gemini
    prompt = prepare_gemini_input(market_data, ticker)
    
    # Generate the analysis
    return gemini_generate_content(prompt)

def prepare_gemini_input(market_data: Dict[str, Any], ticker: str) -> str:
    """
    Prepare the input for Gemini
    
    Args:
        market_data: Market data from various sources
        ticker: The ticker symbol
    
    Returns:
        Formatted prompt for Gemini
    """
    prompt = f"""
# Market Analysis for {ticker}

## Your Task
You are an expert financial analyst with decades of experience in the market. Create a comprehensive analysis and trading plan for {ticker} based on the data provided below. 

## Company Information
"""
    
    # Add company info
    company_info = market_data.get("company_info", {})
    if company_info and "error" not in company_info:
        prompt += f"""
- **Name**: {company_info.get('name', 'N/A')}
- **Sector**: {company_info.get('sector', 'N/A')}
- **Industry**: {company_info.get('industry', 'N/A')}
- **Description**: {company_info.get('longBusinessSummary', 'N/A')}
"""
    
    # Add price data
    stock_quote = market_data.get("stock_quote", {})
    if stock_quote and "error" not in stock_quote:
        price_data = stock_quote.get("price", {})
        summary_detail = stock_quote.get("summaryDetail", {})
        
        current_price = price_data.get("regularMarketPrice", "N/A")
        previous_close = price_data.get("regularMarketPreviousClose", "N/A")
        
        # Calculate change if both values are available
        if current_price != "N/A" and previous_close != "N/A":
            price_change = current_price - previous_close
            price_change_pct = (price_change / previous_close) * 100
            change_str = f"${price_change:.2f} ({price_change_pct:.2f}%)"
        else:
            change_str = "N/A"
        
        prompt += f"""
## Price Information
- **Current Price**: ${current_price}
- **Change**: {change_str}
- **Day Range**: ${price_data.get('regularMarketDayLow', 'N/A')} - ${price_data.get('regularMarketDayHigh', 'N/A')}
- **52-Week Range**: ${summary_detail.get('fiftyTwoWeekLow', 'N/A')} - ${summary_detail.get('fiftyTwoWeekHigh', 'N/A')}
- **Market Cap**: ${summary_detail.get('marketCap', 'N/A')}
- **Volume**: {price_data.get('regularMarketVolume', 'N/A')}
- **Average Volume**: {summary_detail.get('averageVolume', 'N/A')}
"""
    
    # Add Yahoo Finance technical insights if available
    insights = market_data.get("insights", {})
    if insights and "error" not in insights:
        prompt += f"""
## Technical Insights

### Technical Events
"""
        # Add technical events
        tech_events = insights.get("technical_events", {})
        if tech_events:
            prompt += f"""
- **Short Term**: {tech_events.get('short_term', 'N/A')}
- **Mid Term**: {tech_events.get('mid_term', 'N/A')}
- **Long Term**: {tech_events.get('long_term', 'N/A')}
"""
        
        # Add key technical levels
        key_tech = insights.get("key_technicals", {})
        if key_tech:
            prompt += f"""
### Key Technical Levels
- **Support**: ${key_tech.get('support', 'N/A')}
- **Resistance**: ${key_tech.get('resistance', 'N/A')}
- **Stop Loss**: ${key_tech.get('stop_loss', 'N/A')}
"""
        
        # Add analyst recommendations
        recommendation = insights.get("recommendation", {})
        if recommendation:
            prompt += f"""
### Analyst Recommendation
- **Provider**: {recommendation.get('provider', 'N/A')}
- **Rating**: {recommendation.get('rating', 'N/A')}
- **Target Price**: ${recommendation.get('target_price', 'N/A')}
- **Latest Report**: {recommendation.get('title', 'N/A')} ({recommendation.get('date', 'N/A')})
"""
    
    # Add market trends context if available
    if "market_trends" in market_data and (market_data["market_trends"].get("gainers") or market_data["market_trends"].get("losers")):
        prompt += "\n## Market Context\n"
        
        # Top gainers
        gainers = market_data["market_trends"].get("gainers", [])
        if gainers:
            prompt += "\n### Top Gainers\n"
            for gainer in gainers[:5]:
                symbol = gainer.get("symbol", "").split(":")[0]
                name = gainer.get("name", "")
                change_percent = gainer.get("change_percent", 0) * 100
                prompt += f"- {symbol} ({name}): {change_percent:.2f}%\n"
        
        # Top losers
        losers = market_data["market_trends"].get("losers", [])
        if losers:
            prompt += "\n### Top Losers\n"
            for loser in losers[:5]:
                symbol = loser.get("symbol", "").split(":")[0]
                name = loser.get("name", "")
                change_percent = loser.get("change_percent", 0) * 100
                prompt += f"- {symbol} ({name}): {change_percent:.2f}%\n"
    
    # Add news articles if available
    news_articles = market_data.get("news", [])
    if news_articles:
        prompt += "\n## Recent News\n"
        for article in news_articles[:5]:
            title = article.get("article_title", "No title")
            source = article.get("source", "Unknown source")
            date = article.get("post_time_utc", "")
            prompt += f"- {title} ({source}, {date})\n"
    
    # Add options data if available
    options_chain = market_data.get("options_chain", {})
    if options_chain and "error" not in options_chain and options_chain.get("calls") and options_chain.get("puts"):
        nearest_exp = options_chain.get("expiration", "N/A")
        calls = options_chain.get("calls", [])
        puts = options_chain.get("puts", [])
        
        # Find at-the-money options
        atm_calls = []
        atm_puts = []
        
        if stock_quote and "error" not in stock_quote:
            current_price = stock_quote.get("price", {}).get("regularMarketPrice", 0)
            
            if current_price and calls and puts:
                # Find closest to the money calls
                calls_sorted = sorted(calls, key=lambda x: abs(x.get("strike", 0) - current_price))
                atm_calls = calls_sorted[:3]  # Get 3 closest options
                
                # Find closest to the money puts
                puts_sorted = sorted(puts, key=lambda x: abs(x.get("strike", 0) - current_price))
                atm_puts = puts_sorted[:3]  # Get 3 closest options
        
        prompt += f"""
## Options Data (Expiration: {nearest_exp})

### At-The-Money Calls
"""
        for call in atm_calls:
            strike = call.get("strike", 0)
            last_price = call.get("lastPrice", 0)
            volume = call.get("volume", 0)
            implied_vol = call.get("impliedVolatility", 0) * 100
            prompt += f"- Strike: ${strike} | Price: ${last_price} | Vol: {volume} | IV: {implied_vol:.2f}%\n"
        
        prompt += "\n### At-The-Money Puts\n"
        for put in atm_puts:
            strike = put.get("strike", 0)
            last_price = put.get("lastPrice", 0)
            volume = put.get("volume", 0)
            implied_vol = put.get("impliedVolatility", 0) * 100
            prompt += f"- Strike: ${strike} | Price: ${last_price} | Vol: {volume} | IV: {implied_vol:.2f}%\n"
    
    # Add instructions for analysis
    prompt += """
## Expected Analysis

Based on all of the data provided, please provide a comprehensive analysis that includes:

1. **Market Overview**: Summarize the current market conditions and sentiment, especially in relation to this stock.

2. **Technical Analysis**: Analyze the technical indicators, support/resistance levels, and chart patterns. Identify trends and key price levels.

3. **News Impact**: Evaluate how recent news might impact the stock's price and outlook.

4. **Market Position**: Compare this stock to its peers and to market trends. Is it outperforming or underperforming?

5. **Risk Assessment**: Identify key risks for this position.

6. **Trading Plan**:
   - Entry Point(s): Specific price levels to enter the position
   - Stop Loss: Where to cut losses
   - Take Profit: Price targets for taking profits
   - Position Sizing: Recommended allocation percentage
   - Time Horizon: Expected duration of the trade

7. **Confidence Level**: Provide your confidence level in this analysis (Low, Medium, High)

Format your analysis as a well-structured markdown document with clear sections and bullet points where appropriate.
"""
    
    return prompt

def analyze_technicals_with_llm(technical_insights: Dict[str, Any], market_data: Dict[str, Any], ticker: str) -> str:
    """
    Analyze technical indicators for a stock using Yahoo Finance insights data
    
    Args:
        technical_insights: Technical insights data from Yahoo Finance
        market_data: Market data for the stock
        ticker: The ticker symbol
    
    Returns:
        Technical analysis as markdown text
    """
    # Extract current price and key metrics from market data
    current_price = market_data.get("regularMarketPrice", "N/A")
    previous_close = market_data.get("regularMarketPreviousClose", "N/A")
    day_high = market_data.get("regularMarketDayHigh", "N/A")
    day_low = market_data.get("regularMarketDayLow", "N/A")
    volume = market_data.get("regularMarketVolume", "N/A")
    fifty_two_week_high = market_data.get("fiftyTwoWeekHigh", "N/A")
    fifty_two_week_low = market_data.get("fiftyTwoWeekLow", "N/A")
    
    # Extract technical events and key levels
    tech_events = technical_insights.get("technicalEvents", {})
    key_levels = technical_insights.get("keyTechnicalLevels", {})
    recommendations = technical_insights.get("recommendationsByPeriod", {})
    
    # Create prompt for technical analysis
    prompt = f"""
# Technical Analysis for {ticker}

## Market Data
* Current Price: ${current_price}
* Previous Close: ${previous_close}
* Day Range: ${day_low} - ${day_high}
* 52-Week Range: ${fifty_two_week_low} - ${fifty_two_week_high}
* Volume: {volume}

## Technical Events
* Short-Term: {tech_events.get("shortTerm", {}).get("action", "N/A")} (Score: {tech_events.get("shortTerm", {}).get("score", "N/A")})
* Mid-Term: {tech_events.get("midTerm", {}).get("action", "N/A")} (Score: {tech_events.get("midTerm", {}).get("score", "N/A")})
* Long-Term: {tech_events.get("longTerm", {}).get("action", "N/A")} (Score: {tech_events.get("longTerm", {}).get("score", "N/A")})

## Key Technical Levels
* Support: ${key_levels.get("support", "N/A")}
* Resistance: ${key_levels.get("resistance", "N/A")}
* Stop Loss: ${key_levels.get("stopLoss", "N/A")}

## Analyst Recommendations
* 1-Month Consensus: {recommendations.get("1m", {}).get("consensus", "N/A")}
* 3-Month Consensus: {recommendations.get("3m", {}).get("consensus", "N/A")}
* 6-Month Consensus: {recommendations.get("6m", {}).get("consensus", "N/A")}

## Your Task
You are an expert technical analyst with decades of experience reading charts and indicators. Based on the technical insights and market data provided above, analyze {ticker} and provide a comprehensive technical analysis.

For this analysis, consider:

1. **Trend Analysis**: 
   - Identify the primary and secondary trends based on the technical events (short-term, mid-term, and long-term signals).
   - How do these trends align with each other, and what does this suggest about market sentiment?

2. **Support and Resistance Analysis**:
   - Evaluate the key technical levels provided (support, resistance, and stop loss).
   - Identify potential price targets based on these levels and technical patterns.

3. **Trading Strategy**:
   - Recommend specific entry and exit points based on the current technical setup.
   - Suggest appropriate position sizing and risk management strategies.
   - Provide a stop loss recommendation with justification.

4. **Risk Assessment**:
   - Identify potential technical warning signs or reversal patterns to monitor.
   - Assess the volatility profile and how it impacts trading decisions.

5. **Time Horizon Analysis**:
   - Provide distinct outlooks for different time horizons (1-week, 1-month, 3-month).
   - Explain how your strategy would differ for each time frame.

Format your analysis as a well-structured markdown document with clear sections and actionable insights.
"""
    
    # Generate the analysis
    return gemini_generate_content(prompt) 