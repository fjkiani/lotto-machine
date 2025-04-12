import os
import json
import logging
import pandas as pd
from typing import Dict, Optional, List

import google.generativeai as genai
import google.generativeai.types as types
from dotenv import load_dotenv

from src.data.connectors.yahoo_finance import YahooFinanceConnector # Use the centralized connector
from src.analysis.technical_indicators import Indicator, MovingAverage, BollingerBands, RSI, MACD, calculate_indicators # Assume indicators are calculated separately
# Import the new connector
from src.data.connectors.technical_indicators_rapidapi import TechnicalIndicatorAPIConnector

# Set up logging
logger = logging.getLogger(__name__)
load_dotenv()

# Mapping from Streamlit timeframe labels to API interval parameters
# Adjust this mapping based on desired granularity vs. API limitations/performance
# Example: For 1D/1W views, maybe use a finer interval? For longer views, daily is fine.
INTERVAL_MAP = {
    "1D": "15m",
    "1W": "1h",
    "1M": "1d",
    "3M": "1d",
    "6M": "1d",
    "1Y": "1d",
    "5Y": "1wk",
    "MAX": "1mo"
}
# Mapping from Streamlit timeframe to data limit (number of periods)
# Controls how much historical indicator data to fetch
LIMIT_MAP = {
    "1D": 100,  # ~1.5 days of 15m data
    "1W": 100,  # ~4 days of 1h data
    "1M": 30,   # 1 month of daily data
    "3M": 90,
    "6M": 180,
    "1Y": 252,
    "5Y": 260,  # 5 years of weekly data
    "MAX": 240  # 20 years of monthly data
}

# --- Original analyze_technicals_with_llm logic moved here --- 
# --- THIS FUNCTION WILL BE MODIFIED NEXT to accept and use the new indicator data --- 
def analyze_technicals_with_llm(
    ticker: str, 
    timeframe: str, 
    # CHANGE: Instead of raw historical data, expect processed indicator data
    # historical_data: Optional[pd.DataFrame] = None, 
    fetched_indicators: Dict[str, Optional[pd.DataFrame]], # New parameter
    historical_analyses: Optional[List[Dict]] = None
) -> Dict:
    """Analyzes technical indicators using Gemini LLM, now using fetched historical series."""
    logger.info(f"Starting LLM technical analysis for {ticker} ({timeframe}) using fetched indicators")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("Gemini API key not found")
        return {"error": "Gemini API key missing"}
        
    # --- Prepare Indicator Summary for Prompt --- 
    indicator_summary_for_prompt = {}
    latest_values = {}
    indicator_trends = {}
    
    for name, df in fetched_indicators.items():
        if df is not None and not df.empty:
            # Get latest value(s)
            latest_row = df.iloc[-1]
            if name == 'MACD': # MACD has multiple columns
                latest_values[name] = latest_row.to_dict()
            else:
                latest_values[name] = latest_row.iloc[0] # Single value indicators
            
            # Calculate simple trend (e.g., compare latest to value 5 periods ago)
            if len(df) >= 6:
                previous_val = df.iloc[-6].iloc[0]
                current_val = latest_row.iloc[0]
                if pd.notna(previous_val) and pd.notna(current_val):
                    if current_val > previous_val:
                        indicator_trends[name] = "rising"
                    elif current_val < previous_val:
                        indicator_trends[name] = "falling"
                    else:
                        indicator_trends[name] = "flat"
                else:
                    indicator_trends[name] = "insufficient data"
            else:
                indicator_trends[name] = "insufficient data"
        else:
            latest_values[name] = None
            indicator_trends[name] = "fetch failed"
            
    indicator_summary_for_prompt["latest_values"] = latest_values
    indicator_summary_for_prompt["trends_5_period"] = indicator_trends

    # --- Historical Feedback (Remains the same) ---
    feedback = ""
    if historical_analyses:
        past_signals = [analysis.get('summary', {}).get('overall_signal') 
                        for analysis in historical_analyses 
                        if analysis.get('summary', {}).get('overall_signal')]
        if past_signals:
            feedback = f"Historical Context: Previous analysis signals included: {', '.join(past_signals[-3:])}."
            logger.info(f"Adding historical context: {feedback}")

    # --- Construct the Updated Prompt --- 
    # !!! THIS PROMPT NEEDS SIGNIFICANT REVISION !!!
    # It should now ask the LLM to interpret the latest values *in the context* of the trends.
    # Example: Instead of just RSI value, provide RSI value + trend and ask for interpretation.
    # Placeholder prompt for now:
    prompt = f"""
    Analyze the technical indicators for {ticker} based on {timeframe} data.

    Latest Indicator Values:
    {json.dumps(latest_values, indent=2, default=str)}
    
    Recent Indicator Trends (last 5 periods):
    {json.dumps(indicator_trends, indent=2, default=str)}

    {feedback}

    Provide a detailed technical analysis in JSON format. Focus on interpreting the latest values in the context of their recent trends. Identify potential chart patterns, support/resistance, and provide an overall summary with outlook and confidence.
    
    Output JSON Structure:
    {{ 
      "ticker": "{ticker}",
      "timeframe": "{timeframe}",
      "analysis_timestamp": "{datetime.now().isoformat()}",
      "indicator_analysis": {{ 
         "SMA": {{ "latest": {latest_values.get('SMA')}, "trend": "{indicator_trends.get('SMA')}", "interpretation": "Interpret SMA value and trend..." }},
         "RSI": {{ "latest": {latest_values.get('RSI')}, "trend": "{indicator_trends.get('RSI')}", "interpretation": "Interpret RSI value and trend (Overbought/Oversold? Momentum change?)" }},
         "MACD": {{ "latest": {json.dumps(latest_values.get('MACD'))}, "trend": "{indicator_trends.get('MACD')}", "interpretation": "Interpret MACD lines, histogram, and trend (Crossovers? Divergence?)" }},
         "ADX": {{ "latest": {latest_values.get('ADX')}, "trend": "{indicator_trends.get('ADX')}", "interpretation": "Interpret ADX trend strength..." }}
         // Add other indicators if fetched
      }},
      "chart_patterns": {{ "identified": ["Identify patterns..."], "analysis": "Pattern implications..." }},
      "support_resistance": {{ "support": ["Identify levels..."], "resistance": ["Identify levels..."], "analysis": "Level significance..." }},
      "summary": {{ 
          "overall_signal": "Strong Buy|Buy|Hold|Sell|Strong Sell",
          "confidence": "Low|Medium|High",
          "key_takeaways": ["Summarize key findings..."],
          "outlook": "Brief outlook..."
      }}
    }}
    """

    # --- Call Gemini API --- 
    try:
        if not genai._config.api_key:
             genai.configure(api_key=api_key)
    except AttributeError:
        genai.configure(api_key=api_key)
    except Exception as config_err:
         logger.error(f"Error configuring Gemini: {config_err}")
         return {"error": f"Failed to configure Gemini API: {config_err}"}

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
             generation_config=types.GenerationConfig(
                temperature=0.3,
                top_p=0.95,
                top_k=64,
                max_output_tokens=8192,
                response_mime_type="application/json",
            )
        )
        
        logger.info(f"Sending updated technical analysis prompt to Gemini for {ticker}")
        response = model.generate_content(prompt)
        
        analysis_result = json.loads(response.text)
        logger.info(f"Received technical analysis from Gemini for {ticker}")
        
        # Add the fetched raw indicator data (DataFrames) to the result 
        # Note: DataFrames are not directly JSON serializable, handled by save_analysis default=str
        analysis_result['fetched_indicator_data'] = fetched_indicators 
        # Add summary used in prompt for context
        analysis_result['indicator_summary_for_prompt'] = indicator_summary_for_prompt
        
        return analysis_result

    except json.JSONDecodeError:
        logger.error(f"Failed to parse Gemini JSON response for {ticker}: {response.text}")
        return {"error": "Failed to parse LLM response", "raw_response": response.text}
    except Exception as e:
        logger.error(f"Error during Gemini API call for {ticker}: {e}", exc_info=True)
        return {"error": f"LLM API call failed: {e}"}


# --- Wrapper Function --- 
def run_technical_analysis(
    ticker: str,
    timeframe: str,
    connector: YahooFinanceConnector, # Keep yahoo connector for historical price data
    # historical_data: Optional[pd.DataFrame], # No longer need raw price data passed in? Or keep for plotting?
                                          # --> Decision: Keep historical price data for plotting <--
    historical_data: Optional[pd.DataFrame], 
    historical_analyses: Optional[List[Dict]] = None
) -> Dict:
    """
    Runs the complete technical analysis workflow:
    1. Fetches historical indicator data using the new RapidAPI connector.
    2. Calls the LLM analysis function with the fetched indicator data.
    3. Returns the analysis result (which includes the fetched data).
    """
    analysis_type = "technical" # For saving to DB
    logger.info(f"Running Technical Analysis workflow for {ticker} ({timeframe}) using new indicator API")

    # Instantiate the new connector
    try:
        indicator_connector = TechnicalIndicatorAPIConnector()
    except ValueError as e:
        logger.error(f"Failed to initialize TechnicalIndicatorAPIConnector: {e}")
        return {"error": f"Failed to initialize indicator API connector: {e}"}
    except Exception as e:
         logger.error(f"Unexpected error initializing TechnicalIndicatorAPIConnector: {e}", exc_info=True)
         return {"error": f"Unexpected error initializing indicator API connector: {e}"}

    # Determine interval and limit based on timeframe
    interval = INTERVAL_MAP.get(timeframe, "1d") # Default to daily
    limit = LIMIT_MAP.get(timeframe, 100) # Default limit
    logger.debug(f"Mapped timeframe '{timeframe}' to interval='{interval}', limit={limit}")

    # Fetch data for required indicators
    fetched_indicators: Dict[str, Optional[pd.DataFrame]] = {}
    indicators_to_fetch = {
        "SMA": lambda: indicator_connector.get_sma(symbol=ticker, interval=interval, time_period=50, limit=limit),
        "RSI": lambda: indicator_connector.get_rsi(symbol=ticker, interval=interval, time_period=14, limit=limit),
        "MACD": lambda: indicator_connector.get_macd(symbol=ticker, interval=interval, limit=limit),
        "ADX": lambda: indicator_connector.get_adx(symbol=ticker, interval=interval, time_period=14, limit=limit),
        # Add other indicators here if needed
    }

    fetch_errors = []
    for name, fetch_func in indicators_to_fetch.items():
        try:
            logger.info(f"Fetching {name} data for {ticker}...")
            data = fetch_func()
            fetched_indicators[name] = data
            if data is None:
                logger.warning(f"Fetching {name} for {ticker} returned None.")
                fetch_errors.append(name)
            elif data.empty:
                logger.warning(f"Fetching {name} for {ticker} returned empty DataFrame.")
                fetch_errors.append(name)
            else:
                 logger.info(f"Successfully fetched {name} data for {ticker} ({len(data)} rows)")
        except Exception as e:
            logger.error(f"Error fetching {name} data for {ticker}: {e}", exc_info=True)
            fetched_indicators[name] = None # Ensure it's None on error
            fetch_errors.append(name)
            
    # Optional: Check if all fetches failed
    if len(fetch_errors) == len(indicators_to_fetch):
        logger.error(f"Failed to fetch any indicator data for {ticker} from RapidAPI.")
        return {"error": "Failed to fetch any required indicator data."}
    elif fetch_errors:
         logger.warning(f"Failed to fetch some indicator data for {ticker}: {fetch_errors}")
         # Continue analysis with partial data

    # Call LLM analysis function with the fetched data
    analysis_result = analyze_technicals_with_llm(
        ticker=ticker,
        timeframe=timeframe,
        fetched_indicators=fetched_indicators, # Pass the dict of DataFrames
        historical_analyses=historical_analyses
    )
    
    # Add historical OHLCV data to result IF it was provided (for plotting)
    if historical_data is not None:
        analysis_result['historical_ohlcv'] = historical_data
        
    # --- Save successful analysis result to database --- 
    if isinstance(analysis_result, dict) and "error" not in analysis_result:
        from src.data.database_utils import save_analysis # Import here to avoid circular deps?
        try:
            # Pass a copy or specific parts if DataFrame causes issues
            save_analysis(ticker, analysis_type, analysis_result)
        except Exception as db_save_err:
            logger.error(f"Failed to save technical analysis result to database for {ticker}: {db_save_err}", exc_info=True)
    # --- End of Save Step --- 

    return analysis_result 