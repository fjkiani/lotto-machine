#!/usr/bin/env python
"""
Test script for the technical indicators storage system.

This script demonstrates how to collect, store, and retrieve technical indicator data
for historical comparison and LLM analysis.
"""

import os
import json
import logging
import argparse
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from src.analysis.technical_indicators_storage import TechnicalIndicatorsStorage
from src.data.memory import AnalysisMemory
from src.llm.memory_enhanced_analysis import MemoryEnhancedAnalysis

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def collect_and_store_indicators(ticker, period="1y", interval="1d"):
    """Collect and store technical indicators for a ticker"""
    logger.info(f"Collecting and storing technical indicators for {ticker}")
    
    # Initialize the storage system
    storage = TechnicalIndicatorsStorage()
    
    # Collect and store indicators
    indicators_data = storage.collect_and_store_indicators(ticker, period, interval)
    
    # Print the collected indicators
    logger.info(f"Collected {len(indicators_data)} indicators for {ticker}")
    for name, data in indicators_data.items():
        logger.info(f"  {name} ({data['category']})")
        
        # Print signals
        if data['signals']:
            logger.info(f"    Signals: {json.dumps(data['signals'], indent=2)}")
    
    return indicators_data

def verify_indicator_predictions(ticker):
    """Verify previous indicator predictions"""
    logger.info(f"Verifying indicator predictions for {ticker}")
    
    # Initialize the storage system
    storage = TechnicalIndicatorsStorage()
    
    # Verify predictions
    verification_results = storage.verify_indicator_predictions(ticker)
    
    # Print the verification results
    logger.info(f"Verification results for {ticker}:")
    for indicator, results in verification_results.items():
        logger.info(f"  {indicator}:")
        logger.info(f"    Verified predictions: {results['verified_predictions']}")
        logger.info(f"    Correct predictions: {results['correct_predictions']}")
        logger.info(f"    Accuracy: {results['accuracy']:.2f}")
    
    return verification_results

def get_indicator_trends(ticker, indicator_name, days=30):
    """Get trends for a specific indicator"""
    logger.info(f"Getting trends for {indicator_name} on {ticker} over {days} days")
    
    # Initialize the storage system
    storage = TechnicalIndicatorsStorage()
    
    # Get trends
    trend_data = storage.get_indicator_trends(ticker, indicator_name, days)
    
    if 'error' in trend_data:
        logger.error(trend_data['error'])
        return None
    
    # Print the trend data
    logger.info(f"Trend data for {indicator_name} on {ticker}:")
    logger.info(f"  Timestamps: {len(trend_data['timestamps'])} data points")
    logger.info(f"  Values: {list(trend_data['values'].keys())}")
    logger.info(f"  Signals: {list(trend_data['signals'].keys())}")
    
    return trend_data

def plot_indicator_trends(ticker, indicator_name, trend_data):
    """Plot trends for a specific indicator"""
    if not trend_data or 'error' in trend_data:
        logger.error(f"No trend data available for {indicator_name} on {ticker}")
        return
    
    # Set the style
    sns.set_style("whitegrid")
    
    # Create a figure with multiple subplots
    fig, axes = plt.subplots(nrows=len(trend_data['values']), figsize=(12, 4 * len(trend_data['values'])))
    
    # If there's only one value, axes will be a single axis, not an array
    if len(trend_data['values']) == 1:
        axes = [axes]
    
    # Plot each value
    for i, (key, values) in enumerate(trend_data['values'].items()):
        ax = axes[i]
        ax.plot(trend_data['timestamps'], values, marker='o', linestyle='-', linewidth=2)
        ax.set_title(f"{indicator_name} - {key}")
        ax.set_xlabel("Date")
        ax.set_ylabel("Value")
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True)
    
    plt.tight_layout()
    
    # Save the plot
    output_file = f"{ticker}_{indicator_name}_trends.png"
    plt.savefig(output_file)
    logger.info(f"Saved trend plot to {output_file}")
    
    # Show the plot
    plt.show()

def generate_llm_context(ticker):
    """Generate context for LLM analysis"""
    logger.info(f"Generating LLM context for {ticker}")
    
    # Initialize the storage system
    storage = TechnicalIndicatorsStorage()
    
    # Generate context
    context = storage.generate_llm_context(ticker)
    
    # Print the context
    logger.info(f"LLM context for {ticker}:")
    logger.info(context)
    
    return context

def run_memory_enhanced_analysis(ticker, analysis_type="comprehensive", risk_tolerance="medium"):
    """Run memory-enhanced analysis with technical indicators"""
    logger.info(f"Running memory-enhanced analysis for {ticker}")
    
    # Initialize the analysis system
    analyzer = MemoryEnhancedAnalysis()
    
    # Run analysis
    result = analyzer.analyze_ticker_with_memory(ticker, analysis_type, risk_tolerance)
    
    # Save the result to a file
    output_file = f"{ticker}_memory_enhanced_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    logger.info(f"Saved analysis result to {output_file}")
    
    # Print key insights
    if 'market_overview' in result:
        logger.info(f"Market Overview:")
        logger.info(f"  Sentiment: {result['market_overview'].get('sentiment', 'N/A')}")
        logger.info(f"  Summary: {result['market_overview'].get('summary', 'N/A')}")
    
    if 'ticker_analysis' in result and ticker in result['ticker_analysis']:
        ticker_data = result['ticker_analysis'][ticker]
        logger.info(f"Ticker Analysis:")
        logger.info(f"  Recommendation: {ticker_data.get('recommendation', 'N/A')}")
        logger.info(f"  Risk Level: {ticker_data.get('risk_assessment', {}).get('overall_risk', 'N/A')}")
        
        if 'technical_indicators' in ticker_data:
            tech = ticker_data['technical_indicators']
            logger.info(f"  Technical Indicators:")
            logger.info(f"    Trend: {tech.get('trend', 'N/A')}")
            logger.info(f"    Strength: {tech.get('strength', 'N/A')}")
            
            if 'key_levels' in tech:
                levels = tech['key_levels']
                logger.info(f"    Support Levels: {levels.get('support', [])}")
                logger.info(f"    Resistance Levels: {levels.get('resistance', [])}")
    
    if 'technical_insights' in result:
        logger.info(f"Technical Insights:")
        for insight in result['technical_insights']:
            logger.info(f"  {insight.get('indicator', 'N/A')}: {insight.get('signal', 'N/A')} ({insight.get('strength', 'N/A')})")
    
    if 'learning_points' in result:
        logger.info(f"Learning Points:")
        for point in result['learning_points']:
            logger.info(f"  - {point}")
    
    return result

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Test the technical indicators storage system")
    parser.add_argument("ticker", help="Ticker symbol to analyze")
    parser.add_argument("--period", default="1y", help="Data period (e.g., 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)")
    parser.add_argument("--interval", default="1d", help="Data interval (e.g., 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)")
    parser.add_argument("--indicator", default="RSI", help="Indicator to analyze trends for")
    parser.add_argument("--days", type=int, default=30, help="Number of days for trend analysis")
    parser.add_argument("--analysis-type", default="comprehensive", help="Type of analysis (basic, comprehensive)")
    parser.add_argument("--risk-tolerance", default="medium", help="Risk tolerance (low, medium, high)")
    parser.add_argument("--collect-only", action="store_true", help="Only collect and store indicators")
    parser.add_argument("--verify-only", action="store_true", help="Only verify indicator predictions")
    parser.add_argument("--trends-only", action="store_true", help="Only analyze indicator trends")
    parser.add_argument("--context-only", action="store_true", help="Only generate LLM context")
    parser.add_argument("--analysis-only", action="store_true", help="Only run memory-enhanced analysis")
    
    args = parser.parse_args()
    
    # Run the requested operations
    if args.collect_only:
        collect_and_store_indicators(args.ticker, args.period, args.interval)
    elif args.verify_only:
        verify_indicator_predictions(args.ticker)
    elif args.trends_only:
        trend_data = get_indicator_trends(args.ticker, args.indicator, args.days)
        if trend_data and 'error' not in trend_data:
            plot_indicator_trends(args.ticker, args.indicator, trend_data)
    elif args.context_only:
        generate_llm_context(args.ticker)
    elif args.analysis_only:
        run_memory_enhanced_analysis(args.ticker, args.analysis_type, args.risk_tolerance)
    else:
        # Run the full pipeline
        logger.info(f"Running full technical indicators pipeline for {args.ticker}")
        
        # Step 1: Collect and store indicators
        indicators_data = collect_and_store_indicators(args.ticker, args.period, args.interval)
        
        # Step 2: Verify indicator predictions
        verification_results = verify_indicator_predictions(args.ticker)
        
        # Step 3: Get indicator trends
        trend_data = get_indicator_trends(args.ticker, args.indicator, args.days)
        if trend_data and 'error' not in trend_data:
            plot_indicator_trends(args.ticker, args.indicator, trend_data)
        
        # Step 4: Generate LLM context
        context = generate_llm_context(args.ticker)
        
        # Step 5: Run memory-enhanced analysis
        result = run_memory_enhanced_analysis(args.ticker, args.analysis_type, args.risk_tolerance)
        
        logger.info(f"Completed technical indicators pipeline for {args.ticker}")

if __name__ == "__main__":
    main() 