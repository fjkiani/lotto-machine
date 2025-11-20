#!/usr/bin/env python3
"""
Test script for the trend analysis storage system.

This script demonstrates how to parse, store, and retrieve trend analysis data.
"""

import argparse
import json
import sys
from datetime import datetime
from src.analysis.trend_analysis_storage import TrendAnalysisStorage

def main():
    parser = argparse.ArgumentParser(description='Test the trend analysis storage system')
    parser.add_argument('ticker', help='Ticker symbol')
    parser.add_argument('--trend-file', help='File containing trend analysis text')
    parser.add_argument('--trend-text', help='Trend analysis text')
    parser.add_argument('--store-only', action='store_true', help='Only store the trend analysis')
    parser.add_argument('--retrieve-only', action='store_true', help='Only retrieve stored trend analyses')
    parser.add_argument('--verify-prediction', action='store_true', help='Verify a prediction')
    parser.add_argument('--analysis-id', type=int, help='ID of the analysis to verify')
    parser.add_argument('--prediction-type', choices=['short_term', 'medium_term'], help='Type of prediction to verify')
    parser.add_argument('--prediction-value', choices=['bullish', 'bearish'], help='Value of the prediction to verify')
    parser.add_argument('--target-price', type=float, help='Target price from the prediction')
    parser.add_argument('--actual-price', type=float, help='Actual price at verification time')
    parser.add_argument('--was-correct', action='store_true', help='Whether the prediction was correct')
    parser.add_argument('--accuracy-score', type=float, help='Score representing prediction accuracy (0.0-1.0)')
    parser.add_argument('--get-indicator', help='Get historical values for a specific indicator')
    parser.add_argument('--limit', type=int, default=5, help='Maximum number of records to retrieve')
    
    args = parser.parse_args()
    
    # Initialize the trend analysis storage
    trend_storage = TrendAnalysisStorage()
    
    # Store trend analysis
    if not args.retrieve_only and (args.trend_file or args.trend_text):
        # Get the trend analysis text
        if args.trend_file:
            with open(args.trend_file, 'r') as f:
                trend_text = f.read()
        else:
            trend_text = args.trend_text
        
        # Parse the trend analysis text
        print(f"Parsing trend analysis for {args.ticker}...")
        analysis_data = trend_storage.parse_trend_analysis_from_text(trend_text)
        
        # Print the parsed data
        print("\nParsed trend analysis data:")
        for key, value in analysis_data.items():
            print(f"  {key}: {value}")
        
        # Store the analysis
        print(f"\nStoring trend analysis for {args.ticker}...")
        analysis_id = trend_storage.store_trend_analysis(args.ticker, analysis_data)
        
        print(f"Stored trend analysis with ID: {analysis_id}")
        
        if args.store_only:
            return
    
    # Verify a prediction
    if args.verify_prediction and args.analysis_id and args.prediction_type and args.prediction_value and args.target_price is not None and args.actual_price is not None:
        print(f"\nVerifying prediction for analysis ID {args.analysis_id}...")
        
        verification_id = trend_storage.store_prediction_verification(
            trend_analysis_id=args.analysis_id,
            prediction_type=args.prediction_type,
            prediction_value=args.prediction_value,
            target_price=args.target_price,
            actual_price=args.actual_price,
            was_correct=args.was_correct,
            accuracy_score=args.accuracy_score or 0.0
        )
        
        print(f"Stored prediction verification with ID: {verification_id}")
    
    # Get indicator history
    if args.get_indicator:
        print(f"\nGetting {args.get_indicator} history for {args.ticker}...")
        
        trend_data = trend_storage.get_indicator_trends(args.ticker, args.get_indicator, args.limit)
        
        if 'error' in trend_data:
            print(f"Error: {trend_data['error']}")
        else:
            print(f"\n{args.get_indicator} history:")
            for i, timestamp in enumerate(trend_data['timestamps']):
                if i < len(trend_data['values']):
                    print(f"  {timestamp}: {trend_data['values'][i]}")
    
    # Retrieve stored trend analyses
    print(f"\nRetrieving trend analysis history for {args.ticker}...")
    
    history = trend_storage.get_trend_analysis_history(args.ticker, args.limit)
    
    if not history:
        print(f"No trend analysis history available for {args.ticker}")
        return
    
    print(f"\nFound {len(history)} trend analyses:")
    
    for i, analysis in enumerate(history):
        timestamp = datetime.fromisoformat(analysis['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\nAnalysis {i+1} ({timestamp}):")
        print(f"  Primary Trend: {analysis['primary_trend']} (Strength: {analysis['trend_strength']}%, Duration: {analysis['trend_duration']})")
        print(f"  RSI: {analysis['rsi_value']} ({analysis['rsi_condition']})")
        print(f"  MACD: {analysis['macd_signal']} (Strength: {analysis['macd_strength']}%)")
        print(f"  Bollinger Bands: Position: {analysis['bollinger_position']}, Bandwidth: {analysis['bollinger_bandwidth']}, Squeeze: {analysis['bollinger_squeeze']}")
        
        # Support and resistance
        print("  Support Levels:")
        for level in analysis['support_levels']:
            print(f"    - ${level}")
        
        print("  Resistance Levels:")
        for level in analysis['resistance_levels']:
            print(f"    - ${level}")
        
        # Price targets
        print(f"  Short-Term Targets: Bullish: ${analysis['short_term_bullish_target']}, Bearish: ${analysis['short_term_bearish_target']} (Confidence: {analysis['short_term_confidence']}%, Timeframe: {analysis['short_term_timeframe']})")
        print(f"  Medium-Term Targets: Bullish: ${analysis['medium_term_bullish_target']}, Bearish: ${analysis['medium_term_bearish_target']} (Confidence: {analysis['medium_term_confidence']}%, Timeframe: {analysis['medium_term_timeframe']})")
        
        # Risk assessment
        print(f"  Risk Assessment: Stop Loss: ${analysis['stop_loss']}, Risk/Reward: {analysis['risk_reward_ratio']}, Volatility: {analysis['volatility_risk']}")
    
    # Get prediction accuracy
    print(f"\nGetting prediction accuracy for {args.ticker}...")
    
    accuracy = trend_storage.get_prediction_accuracy(args.ticker)
    
    if 'overall' in accuracy:
        overall = accuracy['overall']
        accuracy_value = overall.get('accuracy', 0)
        correct_predictions = overall.get('correct_predictions', 0)
        total_predictions = overall.get('total_predictions', 0)
        
        if accuracy_value is not None and total_predictions > 0:
            print(f"\nOverall Accuracy: {accuracy_value*100:.1f}% ({correct_predictions}/{total_predictions} correct)")
        else:
            print("\nNo accuracy data available yet")
        
        for pred_type, values in accuracy.items():
            if pred_type != 'overall':
                print(f"\n{pred_type.replace('_', ' ').title()} Predictions:")
                for pred_value, metrics in values.items():
                    accuracy_value = metrics.get('accuracy', 0)
                    correct_predictions = metrics.get('correct_predictions', 0)
                    total_predictions = metrics.get('total_predictions', 0)
                    
                    if accuracy_value is not None and total_predictions > 0:
                        print(f"  {pred_value}: {accuracy_value*100:.1f}% accuracy ({correct_predictions}/{total_predictions} correct)")
                    else:
                        print(f"  {pred_value}: No accuracy data available yet")
    else:
        print("No prediction accuracy data available")
    
    # Generate context for LLM
    print(f"\nGenerating trend context for {args.ticker}...")
    
    context = trend_storage.generate_trend_context(args.ticker)
    
    print("\nTrend Context for LLM:")
    print(context)

if __name__ == "__main__":
    main() 