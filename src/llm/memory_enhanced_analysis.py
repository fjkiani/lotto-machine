import os
import json
import logging
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from datetime import datetime

from src.data.memory import AnalysisMemory
from src.data.connectors.yahoo_finance import YahooFinanceConnector
from src.analysis.technical_indicators_storage import TechnicalIndicatorsStorage

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
        self.tech_storage = TechnicalIndicatorsStorage(memory_db_path=memory_db_path)
        
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
        market_data = self.connector.get_quote(ticker)
        if not market_data:
            logger.error(f"Failed to fetch market data for {ticker}")
            return {"error": f"Failed to fetch market data for {ticker}"}
        
        # Step 2: Collect and store technical indicators
        logger.info(f"Collecting technical indicators for {ticker}")
        self.tech_storage.collect_and_store_indicators(ticker)
        
        # Step 3: Verify previous indicator predictions if available
        logger.info(f"Verifying previous indicator predictions for {ticker}")
        self.tech_storage.verify_indicator_predictions(ticker)
        
        # Step 4: Generate memory context
        logger.info(f"Generating memory context for {ticker}")
        memory_context = self.memory.generate_memory_context(
            ticker=ticker,
            current_price=market_data.get('regularMarketPrice', 0),
            price_change_pct=market_data.get('regularMarketChangePercent', 0)
        )
        
        # Step 5: Generate technical indicators context
        logger.info(f"Generating technical indicators context for {ticker}")
        technical_context = self.tech_storage.generate_llm_context(ticker)
        
        # Step 6: Perform analysis with memory and technical context
        logger.info(f"Performing analysis for {ticker} with memory and technical context")
        analysis_result = self._perform_analysis_with_memory(
            ticker=ticker,
            market_data=market_data,
            memory_context=memory_context,
            technical_context=technical_context,
            analysis_type=analysis_type,
            risk_tolerance=risk_tolerance
        )
        
        # Step 7: Store the analysis result
        logger.info(f"Storing analysis result for {ticker}")
        analysis_id = self.memory.store_analysis(
            ticker=ticker,
            current_price=market_data.get('regularMarketPrice', 0),
            analysis_type=analysis_type,
            analysis_data=analysis_result
        )
        
        # Add the analysis ID to the result
        analysis_result['analysis_id'] = analysis_id
        
        return analysis_result
    
    def _perform_analysis_with_memory(self,
                                     ticker: str,
                                     market_data: Dict,
                                     memory_context: str,
                                     technical_context: str,
                                     analysis_type: str,
                                     risk_tolerance: str) -> Dict:
        """
        Perform analysis with memory context
        
        Args:
            ticker: Ticker symbol
            market_data: Market data from Yahoo Finance
            memory_context: Memory context string
            technical_context: Technical indicators context string
            analysis_type: Type of analysis
            risk_tolerance: Risk tolerance level
            
        Returns:
            Analysis result
        """
        # Create the prompt
        prompt = self._create_analysis_prompt(
            ticker=ticker,
            market_data=market_data,
            memory_context=memory_context,
            technical_context=technical_context,
            analysis_type=analysis_type,
            risk_tolerance=risk_tolerance
        )
        
        # Get the model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Generate the response
        response = model.generate_content(prompt)
        
        try:
            # Parse the response as JSON
            response_text = response.text
            
            # Find JSON content between triple backticks
            json_start = response_text.find("```json")
            if json_start != -1:
                json_start += 7  # Skip ```json
                json_end = response_text.find("```", json_start)
                if json_end != -1:
                    json_content = response_text[json_start:json_end].strip()
                    result = json.loads(json_content)
                else:
                    # Try to parse the whole response as JSON
                    result = json.loads(response_text)
            else:
                # Try to parse the whole response as JSON
                result = json.loads(response_text)
                
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response as JSON: {e}")
            logger.debug(f"Response text: {response.text}")
            
            # Return a simplified result
            return {
                "error": "Failed to parse response as JSON",
                "raw_response": response.text
            }
    
    def _create_analysis_prompt(self,
                               ticker: str,
                               market_data: Dict,
                               memory_context: str,
                               technical_context: str,
                               analysis_type: str,
                               risk_tolerance: str) -> str:
        """
        Create the analysis prompt
        
        Args:
            ticker: Ticker symbol
            market_data: Market data from Yahoo Finance
            memory_context: Memory context string
            technical_context: Technical indicators context string
            analysis_type: Type of analysis
            risk_tolerance: Risk tolerance level
            
        Returns:
            Prompt string
        """
        # Format market data
        market_data_str = json.dumps(market_data, indent=2)
        
        # Create the prompt
        prompt = f"""
You are a sophisticated financial analyst with expertise in technical analysis, fundamental analysis, and market sentiment analysis.

Your task is to analyze the stock {ticker} and provide investment recommendations based on the current market data, historical context, and technical indicators.

# Current Market Data
```json
{market_data_str}
```

# Historical Context
{memory_context}

# Technical Indicators
{technical_context}

# Analysis Type
{analysis_type}

# Risk Tolerance
{risk_tolerance}

Based on the provided information, please analyze the stock and provide a comprehensive analysis. Your analysis should include:

1. Market Overview: Provide an overview of the current market conditions and sentiment.
2. Technical Analysis: Analyze the technical indicators and identify patterns, trends, and potential entry/exit points.
3. Historical Comparison: Compare the current situation with historical data and identify similarities and differences.
4. Risk Assessment: Assess the risk level of the stock based on the provided risk tolerance.
5. Recommendation: Provide a clear recommendation (buy, sell, hold) with supporting rationale.
6. Price Targets: Provide short-term and long-term price targets with confidence levels.
7. Trading Strategy: Suggest a trading strategy based on the analysis and risk tolerance.

Please provide your analysis in a structured JSON format with the following structure:

```json
{{
  "market_overview": {{
    "sentiment": "bullish|bearish|neutral",
    "summary": "Brief summary of market conditions",
    "key_factors": ["Factor 1", "Factor 2", ...]
  }},
  "ticker_analysis": {{
    "{ticker}": {{
      "current_price": 123.45,
      "price_change_percent": 1.23,
      "technical_indicators": {{
        "trend": "uptrend|downtrend|sideways",
        "strength": "strong|moderate|weak",
        "key_levels": {{
          "support": [level1, level2, ...],
          "resistance": [level1, level2, ...]
        }},
        "patterns": ["Pattern 1", "Pattern 2", ...],
        "signals": ["Signal 1", "Signal 2", ...]
      }},
      "historical_comparison": {{
        "similar_periods": ["Period 1", "Period 2", ...],
        "differences": ["Difference 1", "Difference 2", ...],
        "implications": "What the historical comparison suggests"
      }},
      "risk_assessment": {{
        "overall_risk": "high|medium|low",
        "volatility": "high|medium|low",
        "factors": ["Factor 1", "Factor 2", ...]
      }},
      "recommendation": "buy|sell|hold",
      "confidence": "high|medium|low",
      "rationale": "Detailed rationale for the recommendation",
      "price_targets": {{
        "short_term": {{
          "target": 130.00,
          "timeframe": "1 week|1 month|3 months",
          "confidence": "high|medium|low"
        }},
        "long_term": {{
          "target": 150.00,
          "timeframe": "6 months|1 year|2 years",
          "confidence": "high|medium|low"
        }}
      }},
      "trading_strategy": {{
        "entry_points": [point1, point2, ...],
        "exit_points": [point1, point2, ...],
        "stop_loss": point,
        "take_profit": point,
        "position_sizing": "Recommendation for position sizing",
        "risk_management": "Risk management strategy"
      }}
    }}
  }},
  "market_sentiment": "bullish|bearish|neutral",
  "recommendation": "buy|sell|hold",
  "risk_level": "high|medium|low",
  "analysis_timestamp": "ISO timestamp",
  "technical_insights": [
    {{
      "indicator": "Indicator name",
      "signal": "bullish|bearish|neutral",
      "strength": "strong|moderate|weak",
      "description": "Description of the signal"
    }},
    ...
  ],
  "learning_points": [
    "Learning point 1",
    "Learning point 2",
    ...
  ]
}}
```

Ensure your analysis is data-driven, objective, and tailored to the specified risk tolerance. Use the historical context and technical indicators to inform your analysis and recommendations.
"""
        
        return prompt
    
    def update_price_history(self, analysis_id: int) -> None:
        """
        Update the price history for an analysis
        
        Args:
            analysis_id: ID of the analysis
        """
        # Get the analysis
        conn = sqlite3.connect(self.memory.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT ticker FROM analyses WHERE id = ?
        ''', (analysis_id,))
        
        row = cursor.fetchone()
        if not row:
            logger.error(f"Analysis with ID {analysis_id} not found")
            conn.close()
            return
        
        ticker = row['ticker']
        
        # Get the current price
        market_data = self.connector.get_quote(ticker)
        if not market_data:
            logger.error(f"Failed to fetch market data for {ticker}")
            conn.close()
            return
        
        current_price = market_data.get('regularMarketPrice', 0)
        
        # Store the price update
        self.memory.store_price_update(analysis_id, current_price)
        
        conn.close()
        
        logger.info(f"Updated price history for analysis {analysis_id} ({ticker}): {current_price}")
    
    def add_user_feedback(self, analysis_id: int, feedback_type: str, feedback_text: str) -> None:
        """
        Add user feedback for an analysis
        
        Args:
            analysis_id: ID of the analysis
            feedback_type: Type of feedback (e.g., "accuracy", "usefulness")
            feedback_text: Feedback text
        """
        self.memory.store_user_feedback(analysis_id, feedback_type, feedback_text)
        logger.info(f"Added user feedback for analysis {analysis_id}: {feedback_type}")
    
    def get_analysis_history(self, ticker: str, limit: int = 5) -> List[Dict]:
        """
        Get analysis history for a ticker
        
        Args:
            ticker: Ticker symbol
            limit: Maximum number of records to retrieve
            
        Returns:
            List of analysis records
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
    
    def get_technical_indicator_trends(self, ticker: str, indicator_name: str, days: int = 30) -> Dict:
        """
        Get trends for a specific technical indicator
        
        Args:
            ticker: Ticker symbol
            indicator_name: Name of the indicator
            days: Number of days to analyze
            
        Returns:
            Dictionary with trend data
        """
        return self.tech_storage.get_indicator_trends(ticker, indicator_name, days) 