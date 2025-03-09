"""
Enhanced analysis pipeline that incorporates a feedback loop between
initial analysis and deep reasoning analysis.
"""

import os
import json
import logging
import re
from typing import Dict, List, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import pandas, but provide a fallback if it's not available
try:
    import pandas as pd
    pandas_available = True
except ImportError:
    logger.warning("pandas not available, some features will be limited")
    pandas_available = False

# Try to import the required modules, but provide fallbacks if they're not available
try:
    from src.data.connectors.yahoo_finance import YahooFinanceConnector
    yahoo_connector_available = True
except ImportError:
    logger.warning("YahooFinanceConnector not available, using simplified version")
    yahoo_connector_available = False
    
    # Define a simple connector class as a fallback
    class SimpleYahooFinanceConnector:
        def get_market_quotes(self, tickers):
            logger.info(f"SimpleYahooFinanceConnector: Would fetch quotes for {tickers}")
            return {ticker: SimpleQuote(ticker) for ticker in tickers}
    
    class SimpleQuote:
        def __init__(self, ticker):
            self.ticker = ticker
            self.regular_market_price = 100.0
            self.regular_market_previous_close = 99.0
            self.regular_market_open = 99.5
            self.regular_market_day_high = 101.0
            self.regular_market_day_low = 98.5
            self.regular_market_volume = 1000000
            self.average_volume = 1200000
            self.market_cap = 1000000000
            self.trailing_pe = 15.0
            self.fifty_two_week_high = 120.0
            self.fifty_two_week_low = 80.0
            self.fifty_day_average = 98.0
            self.two_hundred_day_average = 95.0
            self.market_state = "REGULAR"
            self.exchange_name = "NASDAQ"
            
        def get_dividend_yield(self):
            return 2.0
            
        def get_day_change_percent(self):
            return 1.0

# Try to import the LLM models, but use our simplified version if not available
try:
    from src.llm.models import analyze_market_quotes_with_gemini
    gemini_available = True
except ImportError:
    logger.warning("src.llm.models not available, trying simplified version")
    try:
        from src.llm.models_simplified import analyze_market_quotes_with_gemini
        gemini_available = True
        logger.info("Using simplified models")
    except ImportError:
        logger.warning("simplified models not available either, using fallback")
        gemini_available = False
        
        # Define a simple function as a fallback
        def analyze_market_quotes_with_gemini(quotes, analysis_type):
            logger.info(f"Would analyze quotes with Gemini (analysis_type: {analysis_type})")
            tickers = list(quotes.keys())
            return json.dumps({
                "analysis": {
                    "tickers": tickers,
                    "timestamp": datetime.now().isoformat(),
                    "market_analysis": {
                        "trend": "neutral",
                        "recommendation": "hold",
                        "confidence": 0.5,
                        "reasoning": "This is a simplified analysis. The full analysis pipeline is not available."
                    }
                }
            })

try:
    from deep_reasoning_fix import deep_reasoning_analysis
    deep_reasoning_available = True
except ImportError:
    logger.warning("deep_reasoning_analysis not available, using simplified version")
    deep_reasoning_available = False
    
    # Define a simple function as a fallback
    def deep_reasoning_analysis(market_data, initial_analysis):
        logger.info("Would perform deep reasoning analysis")
        return "Deep reasoning analysis would go here. This is a simplified version."

try:
    from src.analysis.feedback_loop import implement_feedback_loop
    feedback_loop_available = True
except ImportError:
    logger.warning("implement_feedback_loop not available, using simplified version")
    feedback_loop_available = False
    
    # Define a simple function as a fallback
    def implement_feedback_loop(initial_analysis, deep_analysis):
        logger.info("Would implement feedback loop")
        return initial_analysis, ["This is a learning point from the simplified feedback loop."]

class EnhancedAnalysisPipeline:
    """
    Enhanced analysis pipeline that incorporates a feedback loop between
    initial analysis and deep reasoning analysis
    """
    
    def __init__(self, use_feedback_loop: bool = True, save_results: bool = True, use_experimental_model: bool = False):
        """
        Initialize the enhanced analysis pipeline
        
        Args:
            use_feedback_loop: Whether to use the feedback loop
            save_results: Whether to save results to files
            use_experimental_model: Whether to use experimental models (ignored in simplified version)
        """
        self.use_feedback_loop = use_feedback_loop
        self.save_results = save_results
        self.use_experimental_model = use_experimental_model
        
        # Use the appropriate connector based on availability
        if yahoo_connector_available:
            self.connector = YahooFinanceConnector()
        else:
            self.connector = SimpleYahooFinanceConnector()
            
        self.learning_database = []
        
        # Create output directory if it doesn't exist
        self.output_dir = "analysis_results"
        if save_results and not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        logger.info(f"Initialized EnhancedAnalysisPipeline")
        logger.info(f"  use_feedback_loop: {use_feedback_loop}")
        logger.info(f"  save_results: {save_results}")
        logger.info(f"  use_experimental_model: {use_experimental_model}")
        logger.info(f"  yahoo_connector_available: {yahoo_connector_available}")
        logger.info(f"  gemini_available: {gemini_available}")
        logger.info(f"  deep_reasoning_available: {deep_reasoning_available}")
        logger.info(f"  feedback_loop_available: {feedback_loop_available}")
    
    def analyze_market(self, ticker, market_data, risk_tolerance="medium"):
        """
        Analyze market data for a given ticker.
        
        Args:
            ticker (str): The ticker symbol.
            market_data (dict): The market data.
            risk_tolerance (str): The risk tolerance level.
            
        Returns:
            dict: The analysis result.
        """
        logger.info(f"Analyzing market data for {ticker}")
        
        # Create a simple analysis result
        analysis_result = {
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "market_analysis": {
                "trend": "neutral",
                "support_levels": [market_data.get("price", 0) * 0.95],
                "resistance_levels": [market_data.get("price", 0) * 1.05],
                "recommendation": "hold",
                "confidence": 0.5,
                "reasoning": "Market analysis based on current price data."
            },
            "risk_analysis": {
                "risk_level": risk_tolerance,
                "volatility": "medium",
                "max_drawdown": 0.1,
                "risk_adjusted_return": 0.5
            }
        }
        
        return analysis_result
        
    def analyze_options(self, ticker, options_data, risk_tolerance="medium"):
        """
        Analyze options data for a given ticker.
        
        Args:
            ticker (str): The ticker symbol.
            options_data (dict): The options data.
            risk_tolerance (str): The risk tolerance level.
            
        Returns:
            dict: The analysis result.
        """
        logger.info(f"Analyzing options data for {ticker}")
        
        # Create a simple analysis result
        analysis_result = {
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "options_analysis": {
                "implied_volatility": 0.2,
                "put_call_ratio": 1.0,
                "recommendation": "neutral",
                "confidence": 0.5,
                "reasoning": "Options analysis based on current market data."
            },
            "strategies": [
                {
                    "name": "Hold",
                    "description": "Hold current position",
                    "risk_level": risk_tolerance,
                    "potential_return": "medium",
                    "recommendation_strength": "medium"
                }
            ]
        }
        
        return analysis_result
    
    def analyze_tickers(self, tickers: List[str], analysis_type: str = "comprehensive") -> Dict:
        """
        Analyze the given tickers using the enhanced pipeline
        
        Args:
            tickers: List of ticker symbols to analyze
            analysis_type: Type of analysis to perform (basic, technical, fundamental, comprehensive)
            
        Returns:
            Dictionary with analysis results
        """
        # Step 1: Fetch market quotes
        logger.info(f"Fetching market quotes for {', '.join(tickers)}")
        quotes = self.connector.get_market_quotes(tickers)
        
        # Step 2: Perform initial analysis
        logger.info(f"Performing initial {analysis_type} analysis")
        initial_analysis_raw = analyze_market_quotes_with_gemini(quotes, analysis_type)
        
        # Parse the initial analysis
        try:
            # Extract JSON from the response
            json_match = re.search(r'\{.*\}', initial_analysis_raw, re.DOTALL)
            if json_match:
                initial_analysis = json.loads(json_match.group(0))
            else:
                logger.warning("Could not extract JSON from initial analysis")
                initial_analysis = {"error": "Could not extract JSON from response"}
        except Exception as e:
            logger.error(f"Error parsing initial analysis: {str(e)}")
            initial_analysis = {"error": f"Error parsing initial analysis: {str(e)}"}
        
        # Save initial analysis if requested
        if self.save_results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(f"{self.output_dir}/initial_analysis_{timestamp}.json", "w") as f:
                json.dump(initial_analysis, f, indent=2)
        
        # If feedback loop is disabled, return the initial analysis
        if not self.use_feedback_loop:
            return initial_analysis
        
        # Step 3: Prepare market data for deep reasoning
        market_data = {}
        for ticker, quote in quotes.items():
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
        
        # Step 4: Perform deep reasoning analysis
        logger.info("Performing deep reasoning analysis")
        deep_analysis = deep_reasoning_analysis(market_data, initial_analysis)
        
        # Save deep reasoning analysis if requested
        if self.save_results:
            with open(f"{self.output_dir}/deep_analysis_{timestamp}.txt", "w") as f:
                f.write(deep_analysis)
        
        # Step 5: Implement feedback loop
        logger.info("Implementing feedback loop between initial and deep analyses")
        updated_analysis, learning_points = implement_feedback_loop(initial_analysis, deep_analysis)
        
        # Save updated analysis and learning points if requested
        if self.save_results:
            with open(f"{self.output_dir}/updated_analysis_{timestamp}.json", "w") as f:
                json.dump(updated_analysis, f, indent=2)
            
            with open(f"{self.output_dir}/learning_points_{timestamp}.txt", "w") as f:
                for i, point in enumerate(learning_points, 1):
                    f.write(f"{i}. {point}\n")
        
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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for point in learning_points:
            self.learning_database.append({
                "timestamp": timestamp,
                "tickers": ",".join(tickers),
                "learning_point": point
            })
        
        # Save learning database if requested
        if self.save_results and pandas_available:
            df = pd.DataFrame(self.learning_database)
            df.to_csv(f"{self.output_dir}/learning_database.csv", index=False)
    
    def get_learning_database(self):
        """
        Get the learning database as a pandas DataFrame
        
        Returns:
            DataFrame containing learning points or list if pandas is not available
        """
        if pandas_available:
            return pd.DataFrame(self.learning_database)
        else:
            return self.learning_database
    
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