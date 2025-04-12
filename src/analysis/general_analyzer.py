import logging
import json
from typing import Dict, Optional

# Import necessary components from other modules
try:
    from src.data.connectors.yahoo_finance import YahooFinanceConnector
except ImportError:
    logging.error("Failed to import YahooFinanceConnector")
    YahooFinanceConnector = None

try:
    from src.llm.models import analyze_market_quotes_with_gemini
except ImportError:
    logging.error("Failed to import analyze_market_quotes_with_gemini from src.llm.models")
    analyze_market_quotes_with_gemini = None

logger = logging.getLogger(__name__)

def run_general_analysis(
    ticker: str, 
    connector: Optional[YahooFinanceConnector],
    analysis_type: str = "comprehensive" # Default to comprehensive
) -> Dict:
    """
    Runs a general market analysis focused on quote data using an LLM.

    Args:
        ticker: The stock ticker symbol.
        connector: An instance of YahooFinanceConnector.
        analysis_type: The type of quote analysis to perform ('basic', 'technical',
                       'fundamental', 'comprehensive').

    Returns:
        A dictionary containing the structured analysis results or an error.
    """
    logger.info(f"Running General Market Analysis (Quote-based) for {ticker} (type: {analysis_type})")

    # Check prerequisites
    if not connector:
        logger.error("YahooFinanceConnector instance is missing.")
        return {"error": "Data connector instance is missing."}
    if not analyze_market_quotes_with_gemini:
        logger.error("analyze_market_quotes_with_gemini function is missing.")
        return {"error": "LLM quote analysis function is missing."}

    try:
        # 1. Fetch Market Quote
        logger.debug(f"Fetching market quote for {ticker} using connector.")
        market_quotes_dict = connector.get_market_quotes(ticker)
        market_quote = market_quotes_dict.get(ticker)

        if market_quote is None:
            logger.error(f"Failed to fetch market quote for {ticker}. Connector returned None.")
            return {"error": f"Failed to fetch market quote for {ticker}."}
        if isinstance(market_quote, dict) and "error" in market_quote:
             logger.error(f"Error fetching market quote for {ticker}: {market_quote['error']}")
             return {"error": f"Error fetching market quote: {market_quote['error']}"}
        
        # The LLM function expects a dict {ticker: quote_object}
        quotes_input = {ticker: market_quote}

        # 2. Call LLM Analysis Function
        logger.debug(f"Calling analyze_market_quotes_with_gemini for {ticker}")
        llm_response_text = analyze_market_quotes_with_gemini(
            quotes=quotes_input,
            analysis_type=analysis_type
        )

        # 3. Parse the JSON Response
        logger.debug(f"Raw response from analyze_market_quotes_with_gemini:\n{llm_response_text}")
        if not llm_response_text:
             logger.error("LLM returned an empty response.")
             return {"error": "LLM analysis returned an empty response."}

        try:
            # --> ADD PRE-PROCESSING STEP <--
            # Find the start and end of the JSON object
            json_start = llm_response_text.find('{')
            json_end = llm_response_text.rfind('}')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_string = llm_response_text[json_start:json_end+1]
                logger.debug(f"Extracted JSON string for parsing:\n{json_string}")
            else:
                # If no valid JSON object found, raise an error to be caught below
                raise json.JSONDecodeError("Could not find JSON object boundaries in LLM response", llm_response_text, 0)

            # Attempt to parse the extracted JSON string
            analysis_result = json.loads(json_string)
            logger.info(f"Successfully parsed general analysis JSON for {ticker}")
            # Optionally add the raw quote data to the result for context
            analysis_result['raw_quote_data'] = market_quote.raw_data if hasattr(market_quote, 'raw_data') else market_quote
            return analysis_result
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to parse JSON response from LLM: {json_err}")
            logger.error(f"Raw LLM Response Text:\n{llm_response_text}")
            return {
                "error": f"Failed to parse LLM JSON response: {json_err}",
                "raw_response": llm_response_text
            }
        except Exception as parse_err: # Catch other potential errors during parsing/processing
            logger.error(f"Error processing LLM response: {parse_err}", exc_info=True)
            return {
                "error": f"Error processing LLM response: {parse_err}",
                "raw_response": llm_response_text
            }

    except Exception as e:
        logger.error(f"Error in general analysis workflow for {ticker}: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred during general analysis: {e}"} 