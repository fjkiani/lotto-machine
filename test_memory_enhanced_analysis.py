import os
import json
import logging
import argparse
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta

from src.llm.memory_enhanced_analysis import MemoryEnhancedAnalysis

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def simulate_price_updates(analyzer, analysis_id, ticker, days=5, volatility=0.02):
    """
    Simulate price updates for a previous analysis
    
    Args:
        analyzer: MemoryEnhancedAnalysis instance
        analysis_id: ID of the analysis
        ticker: Ticker symbol
        days: Number of days to simulate
        volatility: Price volatility
    """
    import random
    import sqlite3
    
    # Get current price
    conn = sqlite3.connect(analyzer.memory.db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT current_price FROM analyses
    WHERE id = ?
    ''', (analysis_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        logger.error(f"Analysis with ID {analysis_id} not found")
        return
    
    current_price = row[0]
    
    # Simulate price updates
    logger.info(f"Simulating {days} days of price updates for {ticker}")
    
    for i in range(1, days + 1):
        # Simulate a random price change
        change_pct = random.normalvariate(0, volatility)
        new_price = current_price * (1 + change_pct)
        
        # Store the price update
        analyzer.memory.store_price_update(analysis_id, new_price)
        
        logger.info(f"Day {i}: {ticker} price updated to ${new_price:.2f} ({change_pct*100:.2f}%)")
        current_price = new_price
        
        # Small delay for more realistic timestamps
        time.sleep(0.5)

def add_sample_user_feedback(analyzer, analysis_id):
    """
    Add sample user feedback for a previous analysis
    
    Args:
        analyzer: MemoryEnhancedAnalysis instance
        analysis_id: ID of the analysis
    """
    feedback_types = ["accuracy", "usefulness", "insight"]
    feedback_texts = [
        "The price target was accurate, but the timeframe was too short.",
        "The technical analysis was very useful for my trading strategy.",
        "I would have liked more specific entry/exit points.",
        "The risk assessment was spot on, saved me from a bad trade.",
        "The sentiment analysis didn't match what happened in the market."
    ]
    
    import random
    
    # Add 2 random feedback items
    for _ in range(2):
        feedback_type = random.choice(feedback_types)
        feedback_text = random.choice(feedback_texts)
        
        analyzer.add_user_feedback(analysis_id, feedback_type, feedback_text)
        logger.info(f"Added {feedback_type} feedback: {feedback_text}")

def display_analysis_result(result, ticker):
    """
    Display the analysis result in a readable format
    
    Args:
        result: Analysis result dictionary
        ticker: Ticker symbol
    """
    if "error" in result:
        logger.error(f"Analysis error: {result['error']}")
        return
    
    print("\n" + "="*80)
    print(f"MEMORY-ENHANCED ANALYSIS FOR {ticker}")
    print("="*80)
    
    # Market Overview
    if "market_overview" in result:
        overview = result["market_overview"]
        print("\nMARKET OVERVIEW:")
        print(f"Sentiment: {overview.get('sentiment', 'N/A')}")
        print(f"Summary: {overview.get('summary', 'N/A')}")
    
    # Ticker Analysis
    if "ticker_analysis" in result and ticker in result["ticker_analysis"]:
        analysis = result["ticker_analysis"][ticker]
        print("\nTICKER ANALYSIS:")
        print(f"Current Price: ${analysis.get('current_price', 0):.2f}")
        print(f"Recommendation: {analysis.get('recommendation', 'N/A')}")
        print(f"Risk Level: {analysis.get('risk_level', 'N/A')}")
        print(f"Confidence: {analysis.get('confidence', 0)*100:.1f}%")
        
        if "price_target" in analysis:
            targets = analysis["price_target"]
            print(f"Price Targets: Low ${targets.get('low', 0):.2f}, Median ${targets.get('median', 0):.2f}, High ${targets.get('high', 0):.2f}")
        
        if "support_resistance" in analysis:
            sr = analysis["support_resistance"]
            print(f"Support Levels: {', '.join(['$' + str(level) for level in sr.get('support_levels', [])])}")
            print(f"Resistance Levels: {', '.join(['$' + str(level) for level in sr.get('resistance_levels', [])])}")
    
    # Trading Opportunities
    if "trading_opportunities" in result and result["trading_opportunities"]:
        print("\nTRADING OPPORTUNITIES:")
        for i, opportunity in enumerate(result["trading_opportunities"], 1):
            print(f"{i}. {opportunity.get('type', 'N/A').upper()} - {opportunity.get('direction', 'N/A').upper()}")
            print(f"   Ticker: {opportunity.get('ticker', 'N/A')}")
            print(f"   Price Target: ${opportunity.get('price_target', 0):.2f}")
            print(f"   Stop Loss: ${opportunity.get('stop_loss', 0):.2f}")
            print(f"   Timeframe: {opportunity.get('timeframe', 'N/A')}")
            print(f"   Rationale: {opportunity.get('rationale', 'N/A')}")
    
    # Historical Comparison
    if "historical_comparison" in result:
        comparison = result["historical_comparison"]
        print("\nHISTORICAL COMPARISON:")
        print(f"Price Trend: {comparison.get('price_trend', 'N/A')}")
        print(f"Sentiment Change: {comparison.get('sentiment_change', 'N/A')}")
        print("Key Differences:")
        for diff in comparison.get("key_differences", []):
            print(f"- {diff}")
        print(f"Prediction Accuracy: {comparison.get('prediction_accuracy', 'N/A')}")
    
    # Memory Info
    if "memory" in result:
        memory = result["memory"]
        print("\nMEMORY INFO:")
        print(f"Analysis ID: {memory.get('analysis_id', 'N/A')}")
        print(f"Has History: {'Yes' if memory.get('has_history', False) else 'No'}")
    
    print("\n" + "="*80)

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Test memory-enhanced analysis")
    parser.add_argument("--ticker", type=str, default="AAPL", help="Ticker symbol")
    parser.add_argument("--analysis-type", type=str, default="comprehensive", 
                        choices=["basic", "technical", "fundamental", "comprehensive"],
                        help="Type of analysis")
    parser.add_argument("--risk-tolerance", type=str, default="medium",
                        choices=["low", "medium", "high"],
                        help="Risk tolerance level")
    parser.add_argument("--simulate-days", type=int, default=5,
                        help="Number of days to simulate for price updates")
    parser.add_argument("--iterations", type=int, default=3,
                        help="Number of analysis iterations to run")
    args = parser.parse_args()
    
    # Create memory-enhanced analyzer
    analyzer = MemoryEnhancedAnalysis()
    
    # Run multiple iterations of analysis
    for i in range(1, args.iterations + 1):
        logger.info(f"Running analysis iteration {i} for {args.ticker}")
        
        # Perform analysis
        result = analyzer.analyze_ticker_with_memory(
            ticker=args.ticker,
            analysis_type=args.analysis_type,
            risk_tolerance=args.risk_tolerance
        )
        
        # Display the result
        display_analysis_result(result, args.ticker)
        
        # Get the analysis ID
        if "memory" in result and "analysis_id" in result["memory"]:
            analysis_id = result["memory"]["analysis_id"]
            
            # Simulate price updates
            simulate_price_updates(
                analyzer=analyzer,
                analysis_id=analysis_id,
                ticker=args.ticker,
                days=args.simulate_days
            )
            
            # Add sample user feedback
            add_sample_user_feedback(analyzer, analysis_id)
        
        # Wait between iterations
        if i < args.iterations:
            wait_time = 5
            logger.info(f"Waiting {wait_time} seconds before next iteration...")
            time.sleep(wait_time)
    
    # Display recommendation accuracy
    accuracy = analyzer.get_recommendation_accuracy(args.ticker)
    print("\nRECOMMENDATION ACCURACY:")
    print(f"Accuracy: {accuracy['accuracy']*100:.1f}%")
    print(f"Correct: {accuracy['correct']}/{accuracy['total']}")

if __name__ == "__main__":
    main() 