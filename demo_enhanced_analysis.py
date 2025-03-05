import os
import json
import logging
import argparse
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import pandas as pd

from src.analysis.enhanced_analysis_pipeline import EnhancedAnalysisPipeline

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def plot_learning_summary(summary):
    """Plot a summary of learning points by category"""
    categories = list(summary.keys())
    counts = list(summary.values())
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(categories, counts)
    
    # Add count labels on top of bars
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                 f'{height}', ha='center', va='bottom')
    
    plt.title('Learning Points by Category')
    plt.xlabel('Category')
    plt.ylabel('Count')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('learning_summary.png')
    logger.info("Saved learning summary plot to learning_summary.png")

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Demo of Enhanced Analysis Pipeline')
    parser.add_argument('--tickers', nargs='+', default=['SPY', 'AAPL', 'MSFT'], 
                        help='Ticker symbols to analyze')
    parser.add_argument('--analysis-type', choices=['basic', 'technical', 'fundamental', 'comprehensive'], 
                        default='comprehensive', help='Type of analysis to perform')
    parser.add_argument('--no-feedback', action='store_true', 
                        help='Disable feedback loop')
    args = parser.parse_args()
    
    try:
        # Create enhanced analysis pipeline
        pipeline = EnhancedAnalysisPipeline(use_feedback_loop=not args.no_feedback)
        
        # Analyze tickers
        logger.info(f"Analyzing {', '.join(args.tickers)} with {args.analysis_type} analysis")
        analysis = pipeline.analyze_tickers(args.tickers, args.analysis_type)
        
        # Display analysis results
        print("\n===== Analysis Results =====\n")
        
        # Market Overview
        market_overview = analysis.get("market_overview", {})
        print(f"Market Sentiment: {market_overview.get('sentiment', 'N/A')}")
        print(f"Market Condition: {market_overview.get('market_condition', 'N/A')}")
        
        print("\nKey Observations:")
        for observation in market_overview.get("key_observations", []):
            print(f"  - {observation}")
        
        # Ticker Analysis
        print("\nTicker Analysis:")
        ticker_analysis = analysis.get("ticker_analysis", {})
        for ticker, ticker_data in ticker_analysis.items():
            print(f"\n  {ticker}:")
            print(f"    Sentiment: {ticker_data.get('sentiment', 'N/A')}")
            print(f"    Recommendation: {ticker_data.get('recommendation', 'N/A')}")
            print(f"    Risk Level: {ticker_data.get('risk_level', 'N/A')}")
            
            # Display technical signals if available
            if "technical_signals" in ticker_data:
                print("    Technical Signals:")
                for signal in ticker_data["technical_signals"]:
                    print(f"      - {signal}")
            
            # Display price targets if available
            price_target = ticker_data.get("price_target", {})
            if price_target:
                print(f"    Price Targets: Short-term ${price_target.get('short_term', 'N/A')}, Long-term ${price_target.get('long_term', 'N/A')}")
                
                # Display note if available (added by feedback loop)
                if "note" in price_target:
                    print(f"    Note: {price_target['note']}")
            
            # Display key insights if available
            if "key_insights" in ticker_data:
                print("    Key Insights:")
                for insight in ticker_data["key_insights"]:
                    print(f"      - {insight}")
        
        # Trading Opportunities
        print("\nTrading Opportunities:")
        for opportunity in analysis.get("trading_opportunities", []):
            print(f"\n  {opportunity.get('ticker', 'N/A')}:")
            print(f"    Strategy: {opportunity.get('strategy', 'N/A')}")
            print(f"    Time Horizon: {opportunity.get('time_horizon', 'N/A')}")
            print(f"    Risk/Reward: {opportunity.get('risk_reward_ratio', 'N/A')}")
            print(f"    Rationale: {opportunity.get('rationale', 'N/A')}")
        
        # Overall Recommendation
        print(f"\nOverall Recommendation: {analysis.get('overall_recommendation', 'N/A')}")
        
        # Display feedback information if feedback loop was used
        if not args.no_feedback and "feedback" in analysis:
            feedback = analysis["feedback"]
            print("\n===== Feedback Information =====\n")
            print(f"Contradictions Detected: {feedback.get('contradictions_detected', 0)}")
            
            print("\nChanges Made:")
            for change in feedback.get("changes_made", []):
                print(f"  - {change}")
            
            print(f"\nOverall Assessment: {feedback.get('overall_assessment', 'N/A')}")
            
            # Get learning database
            learning_db = pipeline.get_learning_database()
            if not learning_db.empty:
                print(f"\nLearning Database: {len(learning_db)} entries")
                
                # Get learning summary
                learning_summary = pipeline.get_learning_summary()
                print("\nLearning Summary:")
                for category, count in learning_summary.items():
                    print(f"  {category}: {count}")
                
                # Plot learning summary
                plot_learning_summary(learning_summary)
        
    except Exception as e:
        logger.error(f"Error in demo: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 