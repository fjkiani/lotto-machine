"""
Technical Indicators Storage Module

This module provides functionality to collect, store, and retrieve technical indicator data
for historical comparison and LLM analysis.
"""

import logging
import pandas as pd
from typing import Dict, List, Optional, Union, Any
from datetime import datetime

from src.data.memory import AnalysisMemory
from src.analysis.technical_indicators import (
    Indicator, MovingAverage, BollingerBands, RSI, MACD,
    calculate_indicators, get_all_signals
)
from src.data.connectors.yahoo_finance import YahooFinanceConnector

# Set up logging
logger = logging.getLogger(__name__)

class TechnicalIndicatorsStorage:
    """
    Class for collecting, storing, and retrieving technical indicator data
    """
    
    def __init__(self, memory_db_path: str = "memory.db"):
        """
        Initialize the technical indicators storage
        
        Args:
            memory_db_path: Path to the memory database file
        """
        self.memory = AnalysisMemory(db_path=memory_db_path)
        self.connector = YahooFinanceConnector()
    
    def collect_and_store_indicators(self, ticker: str, period: str = "1y", interval: str = "1d") -> Dict:
        """
        Collect and store technical indicators for a ticker
        
        Args:
            ticker: Ticker symbol
            period: Data period (e.g., "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")
            interval: Data interval (e.g., "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo")
            
        Returns:
            Dictionary with collected indicator data
        """
        # Fetch historical data
        logger.info(f"Fetching historical data for {ticker} with period={period}, interval={interval}")
        df = self.connector.get_historical_data(ticker, period=period, interval=interval)
        
        if df is None or df.empty:
            logger.error(f"Failed to fetch historical data for {ticker}")
            return {}
        
        # Create indicators
        indicators = [
            MovingAverage(window=20, column='Close'),  # 20-day SMA
            MovingAverage(window=50, column='Close'),  # 50-day SMA
            MovingAverage(window=200, column='Close'),  # 200-day SMA
            BollingerBands(window=20, num_std=2.0, column='Close'),  # 20-day Bollinger Bands
            RSI(window=14, column='Close'),  # 14-day RSI
            MACD(fast_period=12, slow_period=26, signal_period=9, column='Close')  # MACD
        ]
        
        # Calculate indicators
        df_with_indicators = calculate_indicators(df, indicators)
        
        # Get signals
        signals = get_all_signals(df_with_indicators, indicators)
        
        # Prepare data for storage
        indicators_data = {}
        
        for indicator in indicators:
            name = indicator.name
            category = indicator.category
            
            # Extract the most recent values
            values = {}
            for column in df_with_indicators.columns:
                if column.startswith(f"{name}_"):
                    # Get the last 5 values as a list
                    values[column] = df_with_indicators[column].tail(5).tolist()
            
            # Get signals for this indicator
            indicator_signals = signals.get(name, {})
            
            indicators_data[name] = {
                'category': category,
                'values': values,
                'signals': indicator_signals
            }
        
        # Store in database
        self.memory.store_technical_indicators(ticker, indicators_data)
        
        logger.info(f"Collected and stored {len(indicators_data)} indicators for {ticker}")
        
        return indicators_data
    
    def verify_indicator_predictions(self, ticker: str, lookback_days: int = 7) -> Dict:
        """
        Verify previous indicator predictions against actual outcomes
        
        Args:
            ticker: Ticker symbol
            lookback_days: Number of days to look back for predictions
            
        Returns:
            Dictionary with verification results
        """
        # Get recent indicator history
        indicators_history = self.memory.get_technical_indicators_history(ticker, limit=20)
        
        # Get current market data
        current_data = self.connector.get_quote(ticker)
        if not current_data:
            logger.error(f"Failed to fetch current data for {ticker}")
            return {}
        
        current_price = current_data.get('regularMarketPrice', 0)
        
        verification_results = {}
        
        for record in indicators_history:
            indicator_id = record['id']
            indicator_name = record['indicator_name']
            signals = record['indicator_signals']
            
            if indicator_name not in verification_results:
                verification_results[indicator_name] = {
                    'verified_predictions': 0,
                    'correct_predictions': 0,
                    'accuracy': 0.0
                }
            
            # Verify price direction predictions
            if 'price_direction' in signals:
                prediction = signals['price_direction']
                
                # Simple verification logic - can be enhanced
                if prediction == 'bullish' and current_price > 0:  # Placeholder logic
                    accuracy = 1.0
                    outcome = 'correct'
                elif prediction == 'bearish' and current_price < 0:  # Placeholder logic
                    accuracy = 1.0
                    outcome = 'correct'
                else:
                    accuracy = 0.0
                    outcome = 'incorrect'
                
                # Store the verification result
                self.memory.store_indicator_performance(
                    indicator_id=indicator_id,
                    prediction_type='price_direction',
                    prediction_value=prediction,
                    actual_outcome=outcome,
                    accuracy_score=accuracy
                )
                
                verification_results[indicator_name]['verified_predictions'] += 1
                if outcome == 'correct':
                    verification_results[indicator_name]['correct_predictions'] += 1
            
            # Verify support/resistance levels
            if 'support_levels' in signals:
                for level in signals['support_levels']:
                    # Placeholder verification logic
                    pass
            
            if 'resistance_levels' in signals:
                for level in signals['resistance_levels']:
                    # Placeholder verification logic
                    pass
            
            # Calculate overall accuracy
            if verification_results[indicator_name]['verified_predictions'] > 0:
                verification_results[indicator_name]['accuracy'] = (
                    verification_results[indicator_name]['correct_predictions'] / 
                    verification_results[indicator_name]['verified_predictions']
                )
        
        return verification_results
    
    def get_indicator_trends(self, ticker: str, indicator_name: str, days: int = 30) -> Dict:
        """
        Get trends for a specific indicator over time
        
        Args:
            ticker: Ticker symbol
            indicator_name: Name of the indicator
            days: Number of days to analyze
            
        Returns:
            Dictionary with trend data
        """
        # Get indicator history
        history = self.memory.get_technical_indicators_history(
            ticker=ticker,
            indicator_name=indicator_name,
            limit=days
        )
        
        if not history:
            return {'error': f"No historical data found for {indicator_name} on {ticker}"}
        
        # Extract trend data
        trend_data = {
            'timestamps': [],
            'values': {},
            'signals': {}
        }
        
        for record in reversed(history):  # Process from oldest to newest
            timestamp = datetime.fromisoformat(record['timestamp']).strftime("%Y-%m-%d")
            trend_data['timestamps'].append(timestamp)
            
            # Extract values
            values = record['indicator_values']
            for key, value in values.items():
                if key not in trend_data['values']:
                    trend_data['values'][key] = []
                
                # For list values, take the last one
                if isinstance(value, list) and value:
                    trend_data['values'][key].append(value[-1])
                elif not isinstance(value, (list, dict)):
                    trend_data['values'][key].append(value)
            
            # Extract signals
            signals = record['indicator_signals']
            for key, value in signals.items():
                if key not in trend_data['signals']:
                    trend_data['signals'][key] = []
                
                trend_data['signals'][key].append(value)
        
        return trend_data
    
    def generate_llm_context(self, ticker: str) -> str:
        """
        Generate context for LLM analysis including technical indicators
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Context string for LLM prompt
        """
        # Get technical context
        technical_context = self.memory.generate_technical_context(ticker)
        
        # Get performance metrics
        performance_metrics = self.memory.get_indicator_performance_metrics(ticker)
        
        # Format performance summary
        performance_summary = "Technical Indicator Performance Summary:\n"
        
        if performance_metrics:
            for indicator, metrics in performance_metrics.items():
                performance_summary += f"  {indicator}:\n"
                for pred_type, data in metrics.items():
                    accuracy = data['avg_accuracy']
                    count = data['prediction_count']
                    performance_summary += f"    {pred_type}: {accuracy:.2f} accuracy over {count} predictions\n"
        else:
            performance_summary += "  No performance data available yet.\n"
        
        # Combine contexts
        full_context = f"{technical_context}\n\n{performance_summary}"
        
        return full_context 