import os
import json
import logging
import yaml
from typing import Dict, List, Any, Tuple
from datetime import datetime
import pandas as pd
import re

# Adjust imports to be relative or absolute based on project structure
# Assuming these are available at the src level or adjust as needed
try:
    from src.data.connectors.yahoo_finance import YahooFinanceConnector
except ImportError:
    logging.warning("Could not import YahooFinanceConnector from src.data.connectors")
    YahooFinanceConnector = None # Define as None or raise error

try:
    from src.llm.models import analyze_market_quotes_with_gemini, analyze_options_with_gemini
except ImportError:
    logging.warning("Could not import LLM models from src.llm.models")
    analyze_market_quotes_with_gemini = None
    analyze_options_with_gemini = None

try:
    # This import might be tricky depending on where deep_reasoning_fix.py is
    # If it's in the root, this might fail. Adjust path as needed.
    # Assuming it's been moved to src/llm/ or src/analysis/
    from src.llm.deep_reasoning import deep_reasoning_analysis # Example path
except ImportError:
    # Fallback or attempt alternative path
    try:
        from deep_reasoning_fix import deep_reasoning_analysis # If it's in the root
    except ImportError:
        logging.warning("Could not import deep_reasoning_analysis")
        deep_reasoning_analysis = None

try:
    from src.analysis.feedback_loop import implement_feedback_loop
except ImportError:
    logging.warning("Could not import implement_feedback_loop from src.analysis.feedback_loop")
    implement_feedback_loop = None

try:
    from src.llm.manager_review import ManagerLLMReview
except ImportError:
    logging.warning("Could not import ManagerLLMReview from src.llm.manager_review")
    ManagerLLMReview = None

try:
    from src.data.connectors.alpha_vantage import AlphaVantageConnector
except ImportError:
    logging.warning("Could not import AlphaVantageConnector from src.data.connectors")
    AlphaVantageConnector = None


logger = logging.getLogger(__name__)

class EnhancedAnalysisPipeline:
    """
    Enhanced analysis pipeline that incorporates a feedback loop between
    initial analysis and deep reasoning analysis.
    This class now resides in enhanced_analyzer.py.
    """

    def __init__(self, use_feedback_loop: bool = True, save_results: bool = True):
        """
        Initialize the enhanced analysis pipeline

        Args:
            use_feedback_loop: Whether to use the feedback loop
            save_results: Whether to save results to files
        """
        self.use_feedback_loop = use_feedback_loop
        self.save_results = save_results

        # Instantiate connectors if available
        self.connector = YahooFinanceConnector() if YahooFinanceConnector else None
        self.alpha_vantage = AlphaVantageConnector() if AlphaVantageConnector else None
        self.manager = ManagerLLMReview() if ManagerLLMReview else None

        if not self.connector:
            logger.error("YahooFinanceConnector is required but could not be imported.")
            # Optionally raise an error or handle gracefully
        if not self.alpha_vantage:
             logger.warning("AlphaVantageConnector not available.")
        if not self.manager:
             logger.warning("ManagerLLMReview not available.")


        self.learning_database = []

        # Create output directory if it doesn't exist
        self.output_dir = "analysis_results"
        if save_results and not os.path.exists(self.output_dir):
            try:
                os.makedirs(self.output_dir)
                logger.info(f"Created output directory: {self.output_dir}")
            except OSError as e:
                logger.error(f"Failed to create output directory {self.output_dir}: {e}")
                self.save_results = False # Disable saving if directory creation fails

    def analyze_tickers(self, tickers: List[str], analysis_type: str = "comprehensive") -> Dict:
        """
        Analyze the given tickers using the enhanced pipeline

        Args:
            tickers: List of ticker symbols to analyze
            analysis_type: Type of analysis to perform (basic, technical, fundamental, comprehensive)

        Returns:
            Dictionary with analysis results
        """
        # Check required components
        if not self.connector:
             return {"error": "YahooFinanceConnector is not available."}
        if not analyze_market_quotes_with_gemini:
             return {"error": "Initial analysis function (analyze_market_quotes_with_gemini) is not available."}
        if self.use_feedback_loop and (not deep_reasoning_analysis or not implement_feedback_loop):
             logger.warning("Feedback loop components (deep_reasoning or feedback_loop function) missing. Disabling feedback loop.")
             self.use_feedback_loop = False


        # Step 1: Fetch market quotes
        logger.info(f"Fetching market quotes for {', '.join(tickers)}")
        try:
            quotes = self.connector.get_market_quotes(tickers)
            if not quotes or any(quote is None for quote in quotes.values()):
                 logger.error(f"Error fetching market quotes or received None for some: {quotes}")
                 return {"error": "Failed to fetch valid market quotes."}
        except Exception as e:
            logger.error(f"Exception fetching market quotes: {e}", exc_info=True)
            return {"error": f"Failed to fetch market quotes: {e}"}

        # Step 2: Perform initial analysis
        logger.info(f"Performing initial {analysis_type} analysis")
        try:
            initial_analysis_raw = analyze_market_quotes_with_gemini(quotes, analysis_type)
            if not initial_analysis_raw or isinstance(initial_analysis_raw, dict) and "error" in initial_analysis_raw:
                logger.error(f"Initial analysis returned error: {initial_analysis_raw}")
                return {"error": f"Initial analysis failed: {initial_analysis_raw}"}

            # Parse the initial analysis
            json_match = re.search(r'\{.*\}', initial_analysis_raw, re.DOTALL)
            if json_match:
                initial_analysis = json.loads(json_match.group(0))
            else:
                logger.warning("Could not extract JSON from initial analysis raw text.")
                # Attempt to parse the whole string if no JSON fences found
                try:
                    initial_analysis = json.loads(initial_analysis_raw)
                except json.JSONDecodeError:
                    logger.error("Failed to parse initial analysis raw text as JSON.")
                    initial_analysis = {"error": "Could not parse initial analysis response", "raw_response": initial_analysis_raw}

        except Exception as e:
            logger.error(f"Error during initial analysis execution or parsing: {str(e)}", exc_info=True)
            initial_analysis = {"error": f"Error during initial analysis: {str(e)}"}

        # Save initial analysis if requested
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if self.save_results and "error" not in initial_analysis:
            try:
                with open(f"{self.output_dir}/initial_analysis_{timestamp}.json", "w") as f:
                    json.dump(initial_analysis, f, indent=2)
            except Exception as e:
                 logger.error(f"Failed to save initial analysis: {e}")

        # If feedback loop is disabled or initial analysis failed, return here
        if not self.use_feedback_loop or "error" in initial_analysis:
            return initial_analysis

        # Step 3: Prepare market data for deep reasoning
        market_data = {}
        try:
            for ticker, quote in quotes.items():
                 if hasattr(quote, 'regular_market_price'): # Check if it's a MarketQuote object
                     market_data[ticker] = {
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
                 else:
                      logger.warning(f"Quote data for {ticker} is not a MarketQuote object. Skipping.")
        except Exception as e:
             logger.error(f"Error preparing market data for deep reasoning: {e}", exc_info=True)
             return {"error": "Failed to prepare market data for deep reasoning."}

        if not market_data:
             logger.error("No valid market data could be prepared for deep reasoning.")
             return {"error": "No valid market data for deep reasoning."}

        # Step 4: Perform deep reasoning analysis
        logger.info("Performing deep reasoning analysis")
        try:
            deep_analysis = deep_reasoning_analysis(market_data, initial_analysis)
            if not deep_analysis or isinstance(deep_analysis, dict) and "error" in deep_analysis:
                 logger.error(f"Deep reasoning analysis failed: {deep_analysis}")
                 # Proceed without feedback loop if deep reasoning fails
                 return initial_analysis # Return initial if deep fails
        except Exception as e:
            logger.error(f"Error during deep reasoning analysis: {str(e)}", exc_info=True)
            return initial_analysis # Return initial if deep fails


        # Save deep reasoning analysis if requested
        if self.save_results:
            try:
                with open(f"{self.output_dir}/deep_analysis_{timestamp}.txt", "w") as f:
                    f.write(deep_analysis if isinstance(deep_analysis, str) else json.dumps(deep_analysis))
            except Exception as e:
                 logger.error(f"Failed to save deep reasoning analysis: {e}")

        # Step 5: Implement feedback loop
        logger.info("Implementing feedback loop between initial and deep analyses")
        try:
            updated_analysis, learning_points = implement_feedback_loop(initial_analysis, deep_analysis)
            if "error" in updated_analysis:
                 logger.error(f"Feedback loop failed: {updated_analysis['error']}")
                 # Return initial analysis if feedback loop fails, maybe add feedback error info
                 initial_analysis["feedback_error"] = updated_analysis['error']
                 return initial_analysis
        except Exception as e:
             logger.error(f"Error during feedback loop implementation: {str(e)}", exc_info=True)
             initial_analysis["feedback_error"] = f"Feedback loop exception: {e}"
             return initial_analysis

        # Add feedback metadata to the result
        updated_analysis["feedback_info"] = {
             "feedback_applied": True,
             "learning_points_generated": len(learning_points)
        }

        # Save updated analysis and learning points if requested
        if self.save_results:
            try:
                with open(f"{self.output_dir}/updated_analysis_{timestamp}.json", "w") as f:
                    json.dump(updated_analysis, f, indent=2)

                with open(f"{self.output_dir}/learning_points_{timestamp}.txt", "w") as f:
                    for i, point in enumerate(learning_points, 1):
                        f.write(f"{i}. {point}\n")
            except Exception as e:
                 logger.error(f"Failed to save updated analysis or learning points: {e}")

        # Step 6: Update learning database
        self._update_learning_database(learning_points, tickers)

        return updated_analysis

    def _update_learning_database(self, learning_points: List[str], tickers: List[str]) -> None:
        """
        Update the learning database with new learning points

        Args:
            learning_points: List of learning points
            tickers: List of ticker symbols
        """
        if not learning_points:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for point in learning_points:
            self.learning_database.append({
                "timestamp": timestamp,
                "tickers": ",".join(tickers),
                "learning_point": point
            })

        # Save learning database if requested
        if self.save_results:
            try:
                df = pd.DataFrame(self.learning_database)
                df.to_csv(f"{self.output_dir}/learning_database.csv", index=False)
            except Exception as e:
                logger.error(f"Failed to save learning database: {e}")


    def get_learning_database(self) -> pd.DataFrame:
        """
        Get the learning database as a pandas DataFrame

        Returns:
            DataFrame containing learning points
        """
        return pd.DataFrame(self.learning_database)

    def get_learning_summary(self) -> Dict[str, int]:
        """
        Get a summary of learning points by category

        Returns:
            Dictionary with categories and counts
        """
        categories = {
            "technical_indicators": 0,
            "risk_factors": 0,
            "data_interpretation": 0,
            "data_sources": 0,
            "trading_recommendations": 0,
            "other": 0
        }

        for entry in self.learning_database:
            point = entry["learning_point"].lower()

            if any(term in point for term in ["indicator", "rsi", "macd", "bollinger", "moving average"]):
                categories["technical_indicators"] += 1
            elif any(term in point for term in ["risk", "volatility", "downside"]):
                categories["risk_factors"] += 1
            elif any(term in point for term in ["interpret", "analysis", "pattern"]):
                categories["data_interpretation"] += 1
            elif any(term in point for term in ["data", "source", "information"]):
                categories["data_sources"] += 1
            elif any(term in point for term in ["trade", "strategy", "position", "entry", "exit"]):
                categories["trading_recommendations"] += 1
            else:
                categories["other"] += 1

        return categories

    # Note: analyze_with_review seems specific and might be better suited
    # for a separate module or refactored if it shares logic with analyze_tickers.
    # For now, keeping it here but marking for potential future refactor.
    async def analyze_with_review(self, ticker: str, risk_tolerance: str = "medium") -> Dict:
        """
        Analyze options data with manager review
        **[Refactor Note]**: Consider if this belongs in options_analyzer or a dedicated review module.
        """
        logger.info(f"Starting enhanced analysis with review for {ticker}")

        # Check required components
        if not self.connector or not analyze_options_with_gemini or not deep_reasoning_analysis or not self.manager:
            return {"error": "Required components (connector, LLM functions, manager) not available."}

        try:
            # Fetch market data
            logger.info(f"Fetching data for {ticker}")
            option_chain = self.connector.get_option_chain(ticker)
            quote = self.connector.get_quote(ticker)
            current_price = quote.get('regularMarketPrice', 0)

            if "error" in option_chain or not quote:
                 return {"error": f"Failed to fetch options ({option_chain.get('error', 'N/A')}) or quote data for {ticker}"}

            # Prepare the data for analysis
            market_data = {
                'ticker': ticker,
                'current_price': current_price,
                # Pass relevant parts of option_chain, not the whole object if large
                'option_chain_summary': {
                     'expirations': len(option_chain.options),
                     'strikes': len(option_chain.strikes)
                },
                'quote': quote
            }

            # Get initial analysis
            logger.info(f"Performing initial options analysis for {ticker}")
            initial_analysis = analyze_options_with_gemini(ticker, market_data, risk_tolerance) # This function needs review - market_data format changed
            if "error" in initial_analysis:
                 return {"error": f"Initial options analysis failed: {initial_analysis['error']}"}

            # Save initial analysis if requested
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if self.save_results:
                try:
                    with open(f"{self.output_dir}/initial_options_analysis_{ticker}_{timestamp}.json", "w") as f:
                        json.dump(initial_analysis, f, indent=2)
                except Exception as e:
                    logger.error(f"Failed to save initial options analysis: {e}")

            # Get deep reasoning analysis
            logger.info(f"Performing deep reasoning analysis for {ticker}")
            # deep_reasoning_analysis needs to handle the structured initial_analysis JSON
            deep_analysis_text = deep_reasoning_analysis(market_data, initial_analysis)
            if isinstance(deep_analysis_text, dict) and "error" in deep_analysis_text:
                 logger.warning(f"Deep reasoning failed: {deep_analysis_text['error']}. Proceeding without deep reasoning.")
                 deep_analysis_text = "Deep reasoning step failed." # Provide fallback text


            # Create structured analysis for manager review
            # This structure needs to be defined based on what the manager expects
            structured_analysis_for_review = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "ticker": ticker,
                    "current_price": current_price,
                    "analysis_version": "2.0_review"
                },
                "initial_llm_analysis": initial_analysis, # The JSON from analyze_options_with_gemini
                "deep_reasoning_summary": deep_analysis_text[:1000] + "..." if isinstance(deep_analysis_text, str) else "Deep reasoning summary not available."
                # Add more components as needed by the manager
            }

            # Perform manager review
            logger.info(f"Performing manager review for {ticker}")
            review_result = self.manager.review_analysis(structured_analysis_for_review)

            # Save review results if requested
            if self.save_results:
                try:
                    with open(f"{self.output_dir}/manager_review_{ticker}_{timestamp}.json", "w") as f:
                        json.dump(review_result, f, indent=2)
                except Exception as e:
                    logger.error(f"Failed to save manager review results: {e}")

            return review_result

        except Exception as e:
            logger.error(f"Error during enhanced analysis with review for {ticker}: {str(e)}", exc_info=True)
            return {"error": f"An unexpected error occurred: {str(e)}"}


# --- Wrapper Function ---
def run_enhanced_analysis(
    tickers: List[str],
    analysis_type: str = "comprehensive",
    use_feedback: bool = True,
    save_results: bool = True
) -> Dict:
    """
    Runs the enhanced analysis pipeline.

    Args:
        tickers: List of ticker symbols.
        analysis_type: Type of analysis.
        use_feedback: Whether to use the feedback loop.
        save_results: Whether to save intermediate/final results.

    Returns:
        Dictionary containing the final analysis result.
    """
    logger.info(f"Running Enhanced Analysis workflow for tickers: {tickers}, type: {analysis_type}")
    try:
        pipeline = EnhancedAnalysisPipeline(use_feedback_loop=use_feedback, save_results=save_results)
        result = pipeline.analyze_tickers(tickers, analysis_type)
        return result
    except Exception as e:
        logger.error(f"Error running enhanced analysis workflow: {e}", exc_info=True)
        return {"error": f"Enhanced analysis workflow failed: {e}"}

# Placeholder for the run_enhanced_review_analysis function if needed
# async def run_enhanced_review_analysis(ticker: str, risk_tolerance: str = "medium", save_results: bool = True) -> Dict:
#     logger.info(f"Running Enhanced Review Analysis workflow for ticker: {ticker}")
#     try:
#         # Note: EnhancedAnalysisPipeline initialization might need adjustment if review needs different config
#         pipeline = EnhancedAnalysisPipeline(save_results=save_results)
#         result = await pipeline.analyze_with_review(ticker, risk_tolerance)
#         return result
#     except Exception as e:
#         logger.error(f"Error running enhanced review analysis workflow: {e}", exc_info=True)
#         return {"error": f"Enhanced review analysis workflow failed: {e}"} 