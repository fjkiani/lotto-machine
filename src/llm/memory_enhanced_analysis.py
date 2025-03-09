import os
import json
import logging
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from datetime import datetime

from src.data.memory import AnalysisMemory
from src.data.connectors.yahoo_finance import YahooFinanceConnector

logger = logging.getLogger(__name__)

class MemoryEnhancedAnalysis:
    """
    Enhanced analysis system that uses a memory database to provide
    context for LLM-based financial analysis.
    """
    
    def __init__(self, memory_db_path: str = "memory.db"):
        """
        Initialize the memory-enhanced analysis system
        
        Args:
            memory_db_path: Path to the memory database file
        """
        self.memory = AnalysisMemory(db_path=memory_db_path)
        self.connector = YahooFinanceConnector()
        
        # Initialize Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.")
        genai.configure(api_key=api_key)
    
    def analyze_ticker_with_memory(self, 
                                  ticker: str, 
                                  analysis_type: str = "comprehensive",
                                  risk_tolerance: str = "medium") -> Dict:
        """
        Analyze a ticker with memory-enhanced context
        
        Args:
            ticker: Ticker symbol
            analysis_type: Type of analysis (basic, comprehensive, etc.)
            risk_tolerance: Risk tolerance level (low, medium, high)
            
        Returns:
            Analysis results
        """
        # Step 1: Fetch market data
        logger.info(f"Fetching market data for {ticker}")
        quotes = self.connector.get_market_quotes(ticker)
        
        if ticker not in quotes:
            logger.error(f"Could not fetch market data for {ticker}")
            return {"error": f"Could not fetch market data for {ticker}"}
        
        quote = quotes[ticker]
        
        # Step 2: Extract key market data
        current_price = quote.regular_market_price
        previous_close = quote.regular_market_previous_close
        price_change_pct = ((current_price - previous_close) / previous_close) * 100
        
        # Step 3: Generate memory context
        logger.info(f"Generating memory context for {ticker}")
        memory_context = self.memory.generate_memory_context(
            ticker=ticker,
            current_price=current_price,
            price_change_pct=price_change_pct
        )
        
        # Step 4: Prepare market data for analysis
        market_data = {
            "ticker": ticker,
            "current_price": current_price,
            "previous_close": previous_close,
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
            "day_change_pct": price_change_pct,
            "market_state": quote.market_state,
            "exchange": quote.exchange_name
        }
        
        # Step 5: Perform analysis with memory context
        logger.info(f"Performing memory-enhanced analysis for {ticker}")
        analysis_result = self._perform_analysis_with_memory(
            ticker=ticker,
            market_data=market_data,
            memory_context=memory_context,
            analysis_type=analysis_type,
            risk_tolerance=risk_tolerance
        )
        
        # Step 6: Store the analysis in memory
        logger.info(f"Storing analysis for {ticker} in memory")
        analysis_id = self.memory.store_analysis(
            ticker=ticker,
            current_price=current_price,
            analysis_type=analysis_type,
            analysis_data=analysis_result
        )
        
        # Add the analysis ID to the result
        analysis_result["memory"] = {
            "analysis_id": analysis_id,
            "has_history": len(self.memory.get_ticker_history(ticker, limit=1)) > 1
        }
        
        return analysis_result
    
    def _perform_analysis_with_memory(self,
                                     ticker: str,
                                     market_data: Dict,
                                     memory_context: str,
                                     analysis_type: str,
                                     risk_tolerance: str) -> Dict:
        """
        Perform analysis with memory context
        
        Args:
            ticker: Ticker symbol
            market_data: Market data dictionary
            memory_context: Memory context string
            analysis_type: Type of analysis
            risk_tolerance: Risk tolerance level
            
        Returns:
            Analysis results
        """
        # Prepare the prompt
        prompt = self._create_analysis_prompt(
            ticker=ticker,
            market_data=market_data,
            memory_context=memory_context,
            analysis_type=analysis_type,
            risk_tolerance=risk_tolerance
        )
        
        # Generate the analysis
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        
        # Parse the response
        try:
            # Extract JSON from the response text
            import re
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                analysis_result = json.loads(json_match.group(0))
            else:
                logger.warning("Could not extract JSON from response")
                analysis_result = {"error": "Could not extract JSON from response"}
        except Exception as e:
            logger.error(f"Error parsing analysis result: {str(e)}")
            analysis_result = {"error": f"Error parsing analysis result: {str(e)}"}
        
        return analysis_result
    
    def _create_analysis_prompt(self,
                               ticker: str,
                               market_data: Dict,
                               memory_context: str,
                               analysis_type: str,
                               risk_tolerance: str) -> str:
        """
        Create a prompt for memory-enhanced analysis
        
        Args:
            ticker: Ticker symbol
            market_data: Market data dictionary
            memory_context: Memory context string
            analysis_type: Type of analysis
            risk_tolerance: Risk tolerance level
            
        Returns:
            Prompt string
        """
        prompt = f"""
        You are a sophisticated financial analyst with access to historical analysis data.
        Your task is to analyze the stock {ticker} based on current market data and historical context.
        
        # Current Market Data for {ticker}
        - Current Price: ${market_data['current_price']:.2f}
        - Previous Close: ${market_data['previous_close']:.2f}
        - Day Change: {market_data['day_change_pct']:.2f}%
        - Day Range: ${market_data['low']:.2f} - ${market_data['high']:.2f}
        - Volume: {market_data['volume']:,}
        - Average Volume: {market_data['avg_volume']:,}
        - Market Cap: ${market_data['market_cap']:,.0f}
        - P/E Ratio: {market_data['pe_ratio']:.2f}
        - 52-Week Range: ${market_data['52w_low']:.2f} - ${market_data['52w_high']:.2f}
        - 50-Day Moving Average: ${market_data['50d_avg']:.2f}
        - 200-Day Moving Average: ${market_data['200d_avg']:.2f}
        
        # Historical Context
        {memory_context}
        
        # Analysis Instructions
        Please provide a {analysis_type} analysis for {ticker} with a {risk_tolerance} risk tolerance.
        
        Your analysis should:
        1. Consider both current market data and historical context
        2. Identify patterns or changes from previous analyses
        3. Explain how your recommendation compares to previous recommendations
        4. Highlight what has changed in the market since previous analyses
        5. Provide specific, actionable insights based on the historical performance of your recommendations
        
        Return your analysis as a JSON object with the following structure:
        {{
            "market_overview": {{
                "sentiment": "bullish/bearish/neutral",
                "key_metrics": {{
                    "price": current price,
                    "day_change_pct": day change percentage,
                    "volume": volume,
                    "avg_volume": average volume,
                    "pe_ratio": P/E ratio
                }},
                "summary": "Brief market overview"
            }},
            "ticker_analysis": {{
                "{ticker}": {{
                    "current_price": current price,
                    "previous_close": previous close,
                    "day_change_pct": day change percentage,
                    "recommendation": "buy/sell/hold",
                    "risk_level": "low/medium/high",
                    "confidence": 0.0 to 1.0,
                    "price_target": {{
                        "low": lowest target price,
                        "high": highest target price,
                        "median": median target price
                    }},
                    "support_resistance": {{
                        "support_levels": [level1, level2, ...],
                        "resistance_levels": [level1, level2, ...]
                    }},
                    "technical_indicators": {{
                        "moving_averages": "bullish/bearish/neutral",
                        "rsi": RSI value,
                        "macd": "bullish/bearish/neutral"
                    }}
                }}
            }},
            "trading_opportunities": [
                {{
                    "type": "entry/exit",
                    "direction": "long/short",
                    "ticker": "{ticker}",
                    "price_target": target price,
                    "stop_loss": stop loss price,
                    "timeframe": "short_term/medium_term/long_term",
                    "rationale": "Rationale for the opportunity"
                }}
            ],
            "historical_comparison": {{
                "price_trend": "improving/deteriorating/stable",
                "sentiment_change": "improving/deteriorating/stable",
                "key_differences": [
                    "Difference 1",
                    "Difference 2",
                    ...
                ],
                "prediction_accuracy": "Description of how previous predictions performed"
            }}
        }}
        """
        
        return prompt
    
    def update_price_history(self, analysis_id: int) -> None:
        """
        Update the price history for a previous analysis
        
        Args:
            analysis_id: ID of the analysis
        """
        # Get the analysis
        conn = sqlite3.connect(self.memory.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT ticker FROM analyses
        WHERE id = ?
        ''', (analysis_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            logger.error(f"Analysis with ID {analysis_id} not found")
            return
        
        ticker = row["ticker"]
        
        # Fetch current price
        quotes = self.connector.get_market_quotes(ticker)
        
        if ticker not in quotes:
            logger.error(f"Could not fetch market data for {ticker}")
            return
        
        quote = quotes[ticker]
        current_price = quote.regular_market_price
        
        # Store price update
        self.memory.store_price_update(analysis_id, current_price)
        logger.info(f"Updated price history for analysis {analysis_id} with price ${current_price:.2f}")
    
    def add_user_feedback(self, analysis_id: int, feedback_type: str, feedback_text: str) -> None:
        """
        Add user feedback for a previous analysis
        
        Args:
            analysis_id: ID of the analysis
            feedback_type: Type of feedback (accuracy, usefulness, etc.)
            feedback_text: Text of the feedback
        """
        self.memory.store_user_feedback(analysis_id, feedback_type, feedback_text)
        logger.info(f"Added user feedback for analysis {analysis_id}")
    
    def get_analysis_history(self, ticker: str, limit: int = 5) -> List[Dict]:
        """
        Get historical analyses for a ticker
        
        Args:
            ticker: Ticker symbol
            limit: Maximum number of analyses to return
            
        Returns:
            List of historical analyses
        """
        return self.memory.get_ticker_history(ticker, limit)
    
    def get_recommendation_accuracy(self, ticker: str) -> Dict[str, float]:
        """
        Get recommendation accuracy for a ticker
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Dictionary with accuracy metrics
        """
        return self.memory.get_recommendation_accuracy(ticker) 