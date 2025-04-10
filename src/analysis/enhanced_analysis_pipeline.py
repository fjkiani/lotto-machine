import os
import json
import logging
import yaml
from typing import Dict, List, Any, Tuple
from datetime import datetime
import pandas as pd

from src.data.connectors.yahoo_finance import YahooFinanceConnector
from src.llm.models import analyze_market_quotes_with_gemini, analyze_options_with_gemini
from deep_reasoning_fix import deep_reasoning_analysis
from src.analysis.feedback_loop import implement_feedback_loop
from src.llm.manager_review import ManagerLLMReview
from src.data.connectors.alpha_vantage import AlphaVantageConnector

logger = logging.getLogger(__name__)

class EnhancedAnalysisPipeline:
    """
    Enhanced analysis pipeline that incorporates a feedback loop between
    initial analysis and deep reasoning analysis
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
        self.connector = YahooFinanceConnector()
        self.alpha_vantage = AlphaVantageConnector()
        self.learning_database = []
        self.manager = ManagerLLMReview()
        
        # Create output directory if it doesn't exist
        self.output_dir = "analysis_results"
        if save_results and not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
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
            import re
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
        if self.save_results:
            df = pd.DataFrame(self.learning_database)
            df.to_csv(f"{self.output_dir}/learning_database.csv", index=False)
    
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
    
    async def analyze_with_review(self, ticker: str, risk_tolerance: str = "medium") -> Dict:
        """
        Analyze options data with manager review
        
        Args:
            ticker: Stock ticker symbol
            risk_tolerance: Risk tolerance level (low, medium, high)
            
        Returns:
            Dictionary with analyzed data and review results
        """
        logger.info(f"Starting enhanced analysis with review for {ticker}")
        
        try:
            # Fetch market data
            option_chain = self.connector.get_option_chain(ticker)
            quote = self.connector.get_quote(ticker)
            current_price = quote.get('regularMarketPrice', 0)
            
            # Prepare the data for analysis
            market_data = {
                'ticker': ticker,
                'current_price': current_price,
                'option_chain': option_chain,
                'quote': quote
            }
            
            # Get initial analysis
            logger.info(f"Performing initial options analysis for {ticker}")
            initial_analysis = analyze_options_with_gemini(ticker, market_data, risk_tolerance)
            
            # Save initial analysis if requested
            if self.save_results:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                with open(f"{self.output_dir}/initial_options_analysis_{ticker}_{timestamp}.json", "w") as f:
                    json.dump(initial_analysis, f, indent=2)
            
            # Get deep reasoning analysis
            logger.info(f"Performing deep reasoning analysis for {ticker}")
            deep_analysis = deep_reasoning_analysis(market_data, initial_analysis)
            
            # Create structured analysis for review
            structured_analysis = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "ticker": ticker,
                    "current_price": current_price,
                    "analysis_version": "2.0"
                },
                "market_state": {
                    "overall_sentiment": deep_analysis.get('market_conditions', {}).get('sentiment', 'neutral'),
                    "institutional_positioning": "balanced",
                    "retail_activity": {
                        "sentiment": "neutral",
                        "conviction": "medium",
                        "reliability": "medium"
                    }
                },
                "price_levels": {
                    "support_levels": [
                        {"price": current_price * 0.95, "strength": "strong", "type": "technical"}
                    ],
                    "resistance_levels": [
                        {"price": current_price * 1.05, "strength": "moderate", "type": "technical"}
                    ]
                },
                "volatility_structure": {
                    "skew_analysis": {
                        "type": "normal",
                        "strength": 0.5,
                        "interpretation": "Balanced market expectations"
                    }
                },
                "trading_opportunities": {
                    "strategies": [
                        {
                            "type": deep_analysis.get('recommended_strategy', {}).get('name', 'directional'),
                            "direction": "call" if deep_analysis.get('overall_sentiment') == "bullish" else "put",
                            "size": "moderate",
                            "confidence": "moderate",
                            "rationale": deep_analysis.get('recommended_strategy', {}).get('description', '')
                        }
                    ]
                },
                "technical_signals": {
                    "momentum_bias": deep_analysis.get('overall_sentiment', "neutral"),
                    "support_zones": [current_price * 0.95, current_price * 0.90],
                    "resistance_zones": [current_price * 1.05, current_price * 1.10]
                },
                "institutional_flows": {
                    "hedging_patterns": {
                        "hedging_type": "balanced",
                        "put_walls": [
                            {"strike": current_price * 0.90, "size": 5000}
                        ]
                    }
                }
            }
            
            # Run manager review
            logger.info(f"Running manager review for {ticker}")
            review_result = self.manager.review_analysis(structured_analysis)
            
            # Save review results if requested
            if self.save_results:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                with open(f"{self.output_dir}/manager_review_{ticker}_{timestamp}.json", "w") as f:
                    json.dump(review_result, f, indent=2)
            
            # Return final result, combining the original analysis with the review
            if review_result['status'] == 'resolved':
                logger.info(f"Manager review found and resolved contradictions for {ticker}")
                final_result = review_result['resolved_analysis']
                final_result['manager_review'] = {
                    'status': review_result['status'],
                    'confidence_score': review_result['confidence_score'],
                    'review_notes': review_result['review_notes']
                }
            else:
                logger.info(f"Manager review validated analysis for {ticker}")
                final_result = structured_analysis
                final_result['manager_review'] = {
                    'status': review_result['status'],
                    'confidence_score': review_result.get('confidence_score', 1.0),
                    'review_notes': review_result.get('review_notes', [])
                }
            
            # Add raw analysis for reference
            final_result['raw_analysis'] = {
                'initial': initial_analysis,
                'deep': deep_analysis
            }
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in enhanced analysis with review: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Return error information
            return {
                "error": str(e),
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "ticker": ticker,
                    "analysis_version": "2.0"
                },
                "market_state": {
                    "overall_sentiment": "neutral"
                },
                "manager_review": {
                    "status": "error",
                    "confidence_score": 0.0,
                    "review_notes": [f"Error during analysis: {str(e)}"]
                }
            } 