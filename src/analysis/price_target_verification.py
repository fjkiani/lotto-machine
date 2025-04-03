"""
Price Target Verification Module

This module provides functionality to verify price targets from trend analysis
and track prediction accuracy over time.
"""

import logging
import sqlite3
import re
from typing import Dict, List, Tuple, Optional, Union, Any
from datetime import datetime, timedelta
import pandas as pd

from src.data.connectors.yahoo_finance import YahooFinanceConnector
from src.analysis.trend_analysis_storage import TrendAnalysisStorage

# Set up logging
logger = logging.getLogger(__name__)

def update_database_schema(db_path: str) -> None:
    """
    Update the database schema to include columns for price target verification
    
    Args:
        db_path: Path to the database file
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the table has the new columns
    cursor.execute("PRAGMA table_info(trend_prediction_accuracy)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Add new columns if they don't exist
    new_columns = [
        ('highest_price_in_period', 'REAL'),
        ('lowest_price_in_period', 'REAL'),
        ('price_at_prediction', 'REAL'),
        ('target_hit_date', 'TEXT'),
        ('days_to_target', 'INTEGER')
    ]
    
    for col_name, col_type in new_columns:
        if col_name not in columns:
            logger.info(f"Adding column {col_name} to trend_prediction_accuracy table")
            cursor.execute(f'ALTER TABLE trend_prediction_accuracy ADD COLUMN {col_name} {col_type}')
    
    conn.commit()
    conn.close()
    
    logger.info("Database schema updated successfully")

def parse_timeframe(timeframe_str: str) -> Tuple[int, int]:
    """
    Parse a timeframe string into a range of days
    
    Args:
        timeframe_str: String representation of timeframe (e.g., "1-2 weeks", "3-6 months")
        
    Returns:
        Tuple of (min_days, max_days)
    """
    # Convert to lowercase for consistency
    timeframe_str = timeframe_str.lower()
    
    # Extract numbers and time units
    match = re.search(r'(\d+)(?:\s*-\s*(\d+))?\s*(day|week|month|year)s?', timeframe_str)
    
    if not match:
        logger.warning(f"Could not parse timeframe: {timeframe_str}, using default 7-30 days")
        return (7, 30)  # Default to 7-30 days if parsing fails
    
    min_value = int(match.group(1))
    max_value = int(match.group(2)) if match.group(2) else min_value
    unit = match.group(3)
    
    # Convert to days
    multiplier = {
        'day': 1,
        'week': 7,
        'month': 30,
        'year': 365
    }
    
    min_days = min_value * multiplier[unit]
    max_days = max_value * multiplier[unit]
    
    return (min_days, max_days)

def verify_price_targets(ticker: str) -> Dict:
    """
    Verify price targets for a ticker
    
    Args:
        ticker: Ticker symbol
        
    Returns:
        Dictionary with verification results
    """
    # Initialize the storage
    trend_storage = TrendAnalysisStorage()
    
    # Update the database schema
    update_database_schema(trend_storage.db_path)
    
    # Get historical trend analyses
    analyses = trend_storage.get_trend_analysis_history(ticker)
    
    if not analyses:
        return {"error": f"No trend analyses found for {ticker}"}
    
    # Get current market data
    connector = YahooFinanceConnector()
    current_data = connector.get_quote(ticker)
    
    if not current_data:
        return {"error": f"Failed to fetch current data for {ticker}"}
    
    current_price = current_data.get('regularMarketPrice', 0)
    
    # Get historical data
    historical_data = connector.get_historical_data(ticker, period="1y", interval="1d")
    
    if historical_data is None or historical_data.empty:
        return {"error": f"Failed to fetch historical data for {ticker}"}
    
    verification_results = []
    
    for analysis in analyses:
        analysis_id = analysis['id']
        # Convert timestamp to pandas Timestamp to handle timezone issues
        timestamp = pd.Timestamp(analysis['timestamp'])
        
        # Check if we already have verifications for this analysis
        conn = sqlite3.connect(trend_storage.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT prediction_type, prediction_value FROM trend_prediction_accuracy
        WHERE trend_analysis_id = ?
        ''', (analysis_id,))
        
        existing_verifications = cursor.fetchall()
        conn.close()
        
        # Convert to set of tuples for easy checking
        existing_verifications = set((v[0], v[1]) for v in existing_verifications)
        
        # Filter historical data from prediction date to now
        # Convert index to naive datetime for comparison if needed
        if historical_data.index.tz is not None:
            compare_index = historical_data.index.tz_localize(None)
        else:
            compare_index = historical_data.index
            
        # Make timestamp naive if it has timezone info
        if timestamp.tz is not None:
            timestamp = timestamp.tz_localize(None)
            
        # Create a mask for filtering
        mask = compare_index >= timestamp
        relevant_data = historical_data.iloc[mask.values]
        
        if relevant_data.empty:
            continue
        
        # Get price at prediction time
        price_at_prediction = relevant_data.iloc[0]['Close']
        
        # Get highest and lowest prices since prediction
        highest_price = relevant_data['High'].max()
        lowest_price = relevant_data['Low'].min()
        
        # Verify short-term bullish target
        if ('short_term', 'bullish') not in existing_verifications and analysis['short_term_bullish_target'] > 0:
            result = verify_prediction(
                trend_storage=trend_storage,
                analysis_id=analysis_id,
                prediction_type='short_term',
                prediction_value='bullish',
                target_price=analysis['short_term_bullish_target'],
                timeframe_str=analysis['short_term_timeframe'],
                price_at_prediction=price_at_prediction,
                current_price=current_price,
                historical_data=relevant_data,
                highest_price=highest_price,
                lowest_price=lowest_price
            )
            verification_results.append(result)
        
        # Verify short-term bearish target
        if ('short_term', 'bearish') not in existing_verifications and analysis['short_term_bearish_target'] > 0:
            result = verify_prediction(
                trend_storage=trend_storage,
                analysis_id=analysis_id,
                prediction_type='short_term',
                prediction_value='bearish',
                target_price=analysis['short_term_bearish_target'],
                timeframe_str=analysis['short_term_timeframe'],
                price_at_prediction=price_at_prediction,
                current_price=current_price,
                historical_data=relevant_data,
                highest_price=highest_price,
                lowest_price=lowest_price
            )
            verification_results.append(result)
        
        # Verify medium-term bullish target
        if ('medium_term', 'bullish') not in existing_verifications and analysis['medium_term_bullish_target'] > 0:
            result = verify_prediction(
                trend_storage=trend_storage,
                analysis_id=analysis_id,
                prediction_type='medium_term',
                prediction_value='bullish',
                target_price=analysis['medium_term_bullish_target'],
                timeframe_str=analysis['medium_term_timeframe'],
                price_at_prediction=price_at_prediction,
                current_price=current_price,
                historical_data=relevant_data,
                highest_price=highest_price,
                lowest_price=lowest_price
            )
            verification_results.append(result)
        
        # Verify medium-term bearish target
        if ('medium_term', 'bearish') not in existing_verifications and analysis['medium_term_bearish_target'] > 0:
            result = verify_prediction(
                trend_storage=trend_storage,
                analysis_id=analysis_id,
                prediction_type='medium_term',
                prediction_value='bearish',
                target_price=analysis['medium_term_bearish_target'],
                timeframe_str=analysis['medium_term_timeframe'],
                price_at_prediction=price_at_prediction,
                current_price=current_price,
                historical_data=relevant_data,
                highest_price=highest_price,
                lowest_price=lowest_price
            )
            verification_results.append(result)
    
    return {
        "ticker": ticker,
        "verifications": verification_results,
        "total_verifications": len(verification_results)
    }

def verify_prediction(
    trend_storage: TrendAnalysisStorage,
    analysis_id: int,
    prediction_type: str,
    prediction_value: str,
    target_price: float,
    timeframe_str: str,
    price_at_prediction: float,
    current_price: float,
    historical_data: pd.DataFrame,
    highest_price: float,
    lowest_price: float
) -> Dict:
    """
    Verify a single prediction
    
    Args:
        trend_storage: TrendAnalysisStorage instance
        analysis_id: ID of the trend analysis
        prediction_type: Type of prediction (e.g., "short_term", "medium_term")
        prediction_value: Value of the prediction (e.g., "bullish", "bearish")
        target_price: Target price from the prediction
        timeframe_str: Timeframe string (e.g., "1-2 weeks")
        price_at_prediction: Price at the time of prediction
        current_price: Current price
        historical_data: Historical price data
        highest_price: Highest price since prediction
        lowest_price: Lowest price since prediction
        
    Returns:
        Dictionary with verification result
    """
    # Parse timeframe
    min_days, max_days = parse_timeframe(timeframe_str)
    
    # Determine if the target was hit
    target_hit = False
    target_hit_date = None
    days_to_target = None
    
    if prediction_value == 'bullish':
        # For bullish predictions, check if price went above target
        target_hit = highest_price >= target_price
        
        if target_hit:
            # Find the first date when the target was hit
            hit_dates = historical_data[historical_data['High'] >= target_price].index
            if len(hit_dates) > 0:
                target_hit_date = hit_dates[0]
                # Calculate days to target (handle timezone-aware indices)
                first_date = historical_data.index[0]
                if isinstance(target_hit_date, pd.Timestamp) and isinstance(first_date, pd.Timestamp):
                    if target_hit_date.tz is not None and first_date.tz is not None:
                        days_to_target = (target_hit_date - first_date).days
                    else:
                        # Convert to naive datetime if needed
                        if target_hit_date.tz is not None:
                            target_hit_date = target_hit_date.tz_localize(None)
                        if first_date.tz is not None:
                            first_date = first_date.tz_localize(None)
                        days_to_target = (target_hit_date - first_date).days
                else:
                    # Fallback for non-Timestamp objects
                    days_to_target = (target_hit_date - historical_data.index[0]).days
    else:  # bearish
        # For bearish predictions, check if price went below target
        target_hit = lowest_price <= target_price
        
        if target_hit:
            # Find the first date when the target was hit
            hit_dates = historical_data[historical_data['Low'] <= target_price].index
            if len(hit_dates) > 0:
                target_hit_date = hit_dates[0]
                # Calculate days to target (handle timezone-aware indices)
                first_date = historical_data.index[0]
                if isinstance(target_hit_date, pd.Timestamp) and isinstance(first_date, pd.Timestamp):
                    if target_hit_date.tz is not None and first_date.tz is not None:
                        days_to_target = (target_hit_date - first_date).days
                    else:
                        # Convert to naive datetime if needed
                        if target_hit_date.tz is not None:
                            target_hit_date = target_hit_date.tz_localize(None)
                        if first_date.tz is not None:
                            first_date = first_date.tz_localize(None)
                        days_to_target = (target_hit_date - first_date).days
                else:
                    # Fallback for non-Timestamp objects
                    days_to_target = (target_hit_date - historical_data.index[0]).days
    
    # Calculate accuracy score
    if prediction_value == 'bullish':
        price_change = highest_price - price_at_prediction
        target_change = target_price - price_at_prediction
        
        # Avoid division by zero
        accuracy_score = min(1.0, price_change / target_change) if target_change > 0 else 0.0
    else:  # bearish
        price_change = price_at_prediction - lowest_price
        target_change = price_at_prediction - target_price
        
        # Avoid division by zero
        accuracy_score = min(1.0, price_change / target_change) if target_change > 0 else 0.0
    
    # Check if the timeframe has elapsed
    prediction_date = historical_data.index[0]
    # Handle timezone-aware indices
    if isinstance(prediction_date, pd.Timestamp):
        if prediction_date.tz is not None:
            prediction_date = prediction_date.tz_localize(None)
    max_timeframe_date = prediction_date + timedelta(days=max_days)
    timeframe_elapsed = datetime.now() >= max_timeframe_date
    
    # If the timeframe has elapsed and the target wasn't hit, the prediction was incorrect
    was_correct = target_hit
    
    # Store the verification
    verification_id = trend_storage.store_prediction_verification(
        trend_analysis_id=analysis_id,
        prediction_type=prediction_type,
        prediction_value=prediction_value,
        target_price=target_price,
        actual_price=current_price,
        was_correct=was_correct,
        accuracy_score=accuracy_score
    )
    
    # Convert target_hit_date to ISO format string if it's a Timestamp
    target_hit_date_str = None
    if target_hit_date is not None:
        if isinstance(target_hit_date, pd.Timestamp):
            target_hit_date_str = target_hit_date.isoformat()
        else:
            target_hit_date_str = target_hit_date.isoformat()
    
    # Update with additional data
    conn = sqlite3.connect(trend_storage.db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
    UPDATE trend_prediction_accuracy
    SET highest_price_in_period = ?,
        lowest_price_in_period = ?,
        price_at_prediction = ?,
        target_hit_date = ?,
        days_to_target = ?
    WHERE id = ?
    ''', (
        highest_price,
        lowest_price,
        price_at_prediction,
        target_hit_date_str,
        days_to_target,
        verification_id
    ))
    
    conn.commit()
    conn.close()
    
    # Return the result
    return {
        "verification_id": verification_id,
        "analysis_id": analysis_id,
        "prediction_type": prediction_type,
        "prediction_value": prediction_value,
        "target_price": target_price,
        "target_hit": target_hit,
        "accuracy_score": accuracy_score,
        "timeframe_elapsed": timeframe_elapsed,
        "days_to_target": days_to_target
    } 