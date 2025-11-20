#!/usr/bin/env python3
"""
Test script for the price target verification system.

This script demonstrates how to verify price targets from trend analysis
and track prediction accuracy over time.
"""

import argparse
import logging
import json
from datetime import datetime

from src.analysis.price_target_verification import (
    update_database_schema,
    parse_timeframe,
    verify_price_targets,
    verify_prediction
)
from src.analysis.trend_analysis_storage import TrendAnalysisStorage

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_parse_timeframe():
    """Test the timeframe parsing function"""
    test_cases = [
        ("1-2 weeks", (7, 14)),
        ("3-6 months", (90, 180)),
        ("1 year", (365, 365)),
        ("2 days", (2, 2)),
        ("invalid", (7, 30))  # Default
    ]
    
    for timeframe_str, expected in test_cases:
        result = parse_timeframe(timeframe_str)
        logger.info(f"Timeframe: '{timeframe_str}' -> {result} days (expected: {expected})")
        
        if result == expected:
            logger.info("✅ PASS")
        else:
            logger.error("❌ FAIL")

def update_schema(db_path):
    """Update the database schema"""
    logger.info(f"Updating database schema in {db_path}")
    update_database_schema(db_path)
    logger.info("Schema update complete")

def verify_targets(ticker):
    """Verify price targets for a ticker"""
    logger.info(f"Verifying price targets for {ticker}")
    
    result = verify_price_targets(ticker)
    
    if "error" in result:
        logger.error(f"Error: {result['error']}")
        return
    
    logger.info(f"Verified {result['total_verifications']} predictions")
    
    for i, v in enumerate(result['verifications']):
        logger.info(f"Verification {i+1}:")
        logger.info(f"  Analysis ID: {v['analysis_id']}")
        logger.info(f"  Prediction: {v['prediction_type']} {v['prediction_value']}")
        logger.info(f"  Target Price: ${v['target_price']}")
        logger.info(f"  Target Hit: {'✅' if v['target_hit'] else '❌'}")
        logger.info(f"  Accuracy Score: {v['accuracy_score']:.2f}")
        
        if 'days_to_target' in v and v['days_to_target'] is not None:
            logger.info(f"  Days to Target: {v['days_to_target']}")

def get_prediction_accuracy(ticker):
    """Get prediction accuracy for a ticker"""
    logger.info(f"Getting prediction accuracy for {ticker}")
    
    trend_storage = TrendAnalysisStorage()
    accuracy = trend_storage.get_prediction_accuracy(ticker)
    
    if 'overall' in accuracy:
        overall = accuracy['overall']
        logger.info(f"Overall Accuracy: {overall['accuracy']*100:.1f}% ({overall['correct_predictions']}/{overall['total_predictions']} correct)")
        
        for pred_type, values in accuracy.items():
            if pred_type != 'overall':
                logger.info(f"{pred_type.replace('_', ' ').title()} Predictions:")
                for pred_value, metrics in values.items():
                    if metrics['total_predictions'] > 0:
                        logger.info(f"  {pred_value}: {metrics['accuracy']*100:.1f}% accuracy ({metrics['correct_predictions']}/{metrics['total_predictions']} correct)")
    else:
        logger.info("No prediction accuracy data available")

def get_verification_details(ticker):
    """Get verification details for a ticker"""
    logger.info(f"Getting verification details for {ticker}")
    
    trend_storage = TrendAnalysisStorage()
    
    # Connect to the database
    import sqlite3
    conn = sqlite3.connect(trend_storage.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get verification details
    cursor.execute('''
    SELECT 
        v.id,
        v.trend_analysis_id,
        v.prediction_type,
        v.prediction_value,
        v.target_price,
        v.actual_price,
        v.verification_date,
        v.was_correct,
        v.accuracy_score,
        v.highest_price_in_period,
        v.lowest_price_in_period,
        v.price_at_prediction,
        v.target_hit_date,
        v.days_to_target,
        a.timestamp as analysis_date,
        a.ticker
    FROM 
        trend_prediction_accuracy v
    JOIN
        trend_analysis a ON v.trend_analysis_id = a.id
    WHERE
        a.ticker = ?
    ORDER BY
        v.verification_date DESC
    ''', (ticker,))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        logger.info("No verification details available")
        return
    
    logger.info(f"Found {len(rows)} verification records:")
    
    for i, row in enumerate(rows):
        row_dict = dict(row)
        
        logger.info(f"Verification {i+1}:")
        logger.info(f"  ID: {row_dict['id']}")
        logger.info(f"  Analysis ID: {row_dict['trend_analysis_id']}")
        logger.info(f"  Prediction: {row_dict['prediction_type']} {row_dict['prediction_value']}")
        logger.info(f"  Target Price: ${row_dict['target_price']}")
        logger.info(f"  Actual Price: ${row_dict['actual_price']}")
        logger.info(f"  Was Correct: {'✅' if row_dict['was_correct'] else '❌'}")
        logger.info(f"  Accuracy Score: {row_dict['accuracy_score']:.2f}")
        
        # Print additional fields if they exist
        if 'highest_price_in_period' in row_dict and row_dict['highest_price_in_period'] is not None:
            logger.info(f"  Highest Price: ${row_dict['highest_price_in_period']}")
        
        if 'lowest_price_in_period' in row_dict and row_dict['lowest_price_in_period'] is not None:
            logger.info(f"  Lowest Price: ${row_dict['lowest_price_in_period']}")
        
        if 'price_at_prediction' in row_dict and row_dict['price_at_prediction'] is not None:
            logger.info(f"  Price at Prediction: ${row_dict['price_at_prediction']}")
        
        if 'target_hit_date' in row_dict and row_dict['target_hit_date'] is not None:
            logger.info(f"  Target Hit Date: {row_dict['target_hit_date']}")
        
        if 'days_to_target' in row_dict and row_dict['days_to_target'] is not None:
            logger.info(f"  Days to Target: {row_dict['days_to_target']}")
        
        logger.info(f"  Analysis Date: {row_dict['analysis_date']}")
        logger.info(f"  Verification Date: {row_dict['verification_date']}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Test the price target verification system")
    parser.add_argument("--ticker", default="SPY", help="Ticker symbol to verify")
    parser.add_argument("--db-path", default="memory.db", help="Path to the database file")
    parser.add_argument("--test-timeframe", action="store_true", help="Test the timeframe parsing function")
    parser.add_argument("--update-schema", action="store_true", help="Update the database schema")
    parser.add_argument("--verify", action="store_true", help="Verify price targets")
    parser.add_argument("--get-accuracy", action="store_true", help="Get prediction accuracy")
    parser.add_argument("--get-details", action="store_true", help="Get verification details")
    
    args = parser.parse_args()
    
    # Run the requested operations
    if args.test_timeframe:
        test_parse_timeframe()
    
    if args.update_schema:
        update_schema(args.db_path)
    
    if args.verify:
        verify_targets(args.ticker)
    
    if args.get_accuracy:
        get_prediction_accuracy(args.ticker)
    
    if args.get_details:
        get_verification_details(args.ticker)
    
    # If no specific operation was requested, run all of them
    if not (args.test_timeframe or args.update_schema or args.verify or args.get_accuracy or args.get_details):
        logger.info("Running all operations")
        
        test_parse_timeframe()
        update_schema(args.db_path)
        verify_targets(args.ticker)
        get_prediction_accuracy(args.ticker)
        get_verification_details(args.ticker)

if __name__ == "__main__":
    main() 