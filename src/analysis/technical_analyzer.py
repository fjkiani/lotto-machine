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

# Set up logging
logger = logging.getLogger(__name__)
load_dotenv()

# --- Original analyze_technicals_with_llm logic moved here ---
def analyze_technicals_with_llm(
    ticker: str, 
    timeframe: str, 
    historical_data: Optional[pd.DataFrame] = None, 
    historical_analyses: Optional[List[Dict]] = None
) -> Dict:
    """Analyzes technical indicators using Gemini LLM."""
    logger.info(f"Starting LLM technical analysis for {ticker} ({timeframe})")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("Gemini API key not found")
        return {"error": "Gemini API key missing"}
        
    if historical_data is None or historical_data.empty:
        logger.warning(f"No historical data provided for {ticker}")
        return {"error": "Historical data is missing or empty"}

    # --- Indicator Calculation ---
    try:
        # Define the list of indicators to calculate based on prompt requirements
        indicators_to_calculate: List[Indicator] = [
            MovingAverage(window=50),
            MovingAverage(window=200),
            BollingerBands(window=20), # Also calculates MA20 internally
            RSI(window=14),
            MACD(),
            # ATR calculation might need to be added to technical_indicators.py if not present
            # For now, we assume Volume is already in historical_data
        ]
        
        # Calculate indicators using the function from technical_indicators.py
        indicators_df = calculate_indicators(historical_data, indicators_to_calculate)
        
        if indicators_df.empty:
            logger.error(f"Failed to calculate indicators for {ticker}")
            return {"error": "Indicator calculation failed"}
        logger.info(f"Calculated indicators for {ticker}: {list(indicators_df.columns)}")
        # Select relevant indicators for the prompt (e.g., the last row/most recent values)
        latest_indicators = indicators_df.iloc[-1].to_dict() if not indicators_df.empty else {}
    except Exception as e:
        logger.error(f"Error calculating indicators for {ticker}: {e}", exc_info=True)
        return {"error": f"Indicator calculation error: {e}"}
        
    # --- Historical Feedback (Simple Example) ---
    feedback = ""
    if historical_analyses:
        # Basic feedback: Mention previous signals if they exist
        # A more sophisticated approach could analyze past prediction accuracy
        past_signals = [analysis.get('summary', {}).get('overall_signal') 
                        for analysis in historical_analyses 
                        if analysis.get('summary', {}).get('overall_signal')]
        if past_signals:
            feedback = f"Historical Context: Previous analysis signals included: {', '.join(past_signals[-3:])}."
            logger.info(f"Adding historical context: {feedback}")

    # --- Construct the Prompt ---
    prompt = f"""
    Analyze the technical indicators for {ticker} based on {timeframe} data and provide a detailed technical analysis.
    
    Current Indicators:
    {json.dumps(latest_indicators, indent=2)}

    {feedback} 

    Provide the analysis in JSON format with the following structure:
    {{
      "ticker": "{ticker}",
      "timeframe": "{timeframe}",
      "analysis_timestamp": "{pd.Timestamp.now().isoformat()}",
      "key_indicators": {{
        "rsi": {{ "value": {latest_indicators.get('RSI', 'null')}, "interpretation": "Provide interpretation (e.g., Overbought >70, Oversold <30)" }},
        "macd": {{ "value": {latest_indicators.get('MACD', 'null')}, "signal": {latest_indicators.get('MACD_Signal', 'null')}, "histogram": {latest_indicators.get('MACD_Hist', 'null')}, "interpretation": "Provide interpretation (e.g., Bullish crossover, Bearish divergence)" }},
        "moving_averages": {{ 
          "ma50": {latest_indicators.get('SMA_50', 'null')}, 
          "ma200": {latest_indicators.get('SMA_200', 'null')},
          "interpretation": "Provide interpretation (e.g., Golden Cross, Death Cross, Price vs MA)" 
        }},
        "bollinger_bands": {{
          "upper": {latest_indicators.get('BB_Upper', 'null')},
          "middle": {latest_indicators.get('BB_Middle', 'null')},
          "lower": {latest_indicators.get('BB_Lower', 'null')},
          "interpretation": "Provide interpretation (e.g., Price touching upper band, Squeeze forming)"
        }},
        "volume": {{
          "latest_volume": {latest_indicators.get('Volume', 'null')},
          "average_volume": {historical_data['Volume'].mean() if 'Volume' in historical_data else 'null'},
          "interpretation": "Provide interpretation (e.g., High volume confirmation, Low volume divergence)"
        }},
        "atr": {{ "value": {latest_indicators.get('ATR', 'null')}, "interpretation": "Volatility analysis based on ATR" }}
      }},
      "chart_patterns": {{
        "identified_patterns": ["Identify any potential patterns (e.g., Head and Shoulders, Double Top, Flags). If none, state 'None'."],
        "pattern_analysis": "Detailed analysis of the identified patterns and their implications."
      }},
      "support_resistance": {{
        "support_levels": ["Identify key support levels based on indicators/price action"],
        "resistance_levels": ["Identify key resistance levels based on indicators/price action"],
        "level_analysis": "Analysis of the significance of these levels."
      }},
      "summary": {{
        "overall_signal": "Provide a clear overall signal (Strong Buy, Buy, Hold, Sell, Strong Sell)",
        "confidence": "Provide confidence level (Low, Medium, High)",
        "key_takeaways": [
          "Summarize the most important technical findings.",
          "Highlight confirming or conflicting signals.",
          "Mention potential risks based on technicals."
        ],
        "outlook": "Brief outlook based on the technical analysis."
      }}
    }}
    """

    # --- Call Gemini API ---
    try:
        # Configure only if necessary
        if not genai._config.api_key:
             genai.configure(api_key=api_key)
             logger.info("Configured Gemini API key.")
    except AttributeError:
         genai.configure(api_key=api_key)
         logger.info("Configured Gemini API key (initial config).")
    except Exception as config_err:
         logger.error(f"Error configuring Gemini: {config_err}")
         return {"error": f"Failed to configure Gemini API: {config_err}"}

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash", # Or your preferred model
             generation_config=types.GenerationConfig(
                temperature=0.3, # Slightly higher temp for more nuanced analysis
                top_p=0.95,
                top_k=64,
                max_output_tokens=8192,
                response_mime_type="application/json",
            )
        )
        
        logger.info(f"Sending technical analysis prompt to Gemini for {ticker}")
        response = model.generate_content(prompt)
        
        analysis_result = json.loads(response.text)
        logger.info(f"Received technical analysis from Gemini for {ticker}")
        
        # Add raw indicators to the result for potential display/debugging
        analysis_result['raw_indicators'] = latest_indicators
        analysis_result['historical_data_summary'] = {
            'start_date': historical_data.index.min().strftime('%Y-%m-%d'),
            'end_date': historical_data.index.max().strftime('%Y-%m-%d'),
            'rows': len(historical_data)
        }
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
    connector: YahooFinanceConnector, # Keep connector for potential future use?
    historical_data: Optional[pd.DataFrame], # Accept historical data
    historical_analyses: Optional[List[Dict]] = None
) -> Dict:
    """
    Runs the complete technical analysis workflow:
    1. Uses pre-fetched historical data.
    2. Calls the LLM analysis function.
    """
    logger.info(f"Running Technical Analysis workflow for {ticker} ({timeframe}) using provided data")

    # Removed mapping and data fetching - expects data to be passed in
    # period_map = { ... }
    # period, interval = period_map.get(timeframe, ("1y", "1d"))

    try:
        # 1. Validate historical data
        if historical_data is None or historical_data.empty:
            logger.error(f"No historical data provided for {ticker} to run_technical_analysis.")
            return {"error": f"Historical data missing for {ticker} analysis."}
        logger.info(f"Using provided historical data ({len(historical_data)} rows) for {ticker}")

        # 2. Call LLM analysis
        analysis_result = analyze_technicals_with_llm(
            ticker=ticker,
            timeframe=timeframe,
            historical_data=historical_data,
            historical_analyses=historical_analyses
        )

        return analysis_result

    except Exception as e:
        logger.error(f"Error in technical analysis workflow for {ticker}: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred during technical analysis: {e}"} 