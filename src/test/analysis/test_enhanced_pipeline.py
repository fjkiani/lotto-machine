#!/usr/bin/env python3
"""
Test script for Enhanced Analysis Pipeline with Manager LLM Review
"""

import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath('.'))

# Setup logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from src.analysis.enhanced_analysis_pipeline import EnhancedAnalysisPipeline
    logger.info("Successfully imported EnhancedAnalysisPipeline")
except ImportError as e:
    logger.error(f"Could not import EnhancedAnalysisPipeline: {str(e)}")
    sys.exit(1)

async def test_enhanced_pipeline(ticker='SPY', risk_tolerance='medium'):
    """Test the enhanced analysis pipeline with real market data"""
    logger.info(f"Testing Enhanced Analysis Pipeline for {ticker} with {risk_tolerance} risk tolerance")
    
    try:
        # Initialize the pipeline
        pipeline = EnhancedAnalysisPipeline(save_results=True)
        
        # Run analysis with manager review
        logger.info(f"Running enhanced analysis with manager review...")
        start_time = datetime.now()
        
        analysis_result = await pipeline.analyze_with_review(ticker, risk_tolerance)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Analysis completed in {duration:.2f} seconds")
        
        # Save results
        output_file = f'enhanced_analysis_{ticker}_{risk_tolerance}.json'
        with open(output_file, 'w') as f:
            json.dump(analysis_result, f, indent=2)
        logger.info(f"Saved analysis results to {output_file}")
        
        # Print summary
        print("\n===== ENHANCED ANALYSIS RESULTS =====")
        print(f"Ticker: {ticker}")
        print(f"Risk Tolerance: {risk_tolerance}")
        
        # Print Manager Review results
        if 'manager_review' in analysis_result:
            manager_review = analysis_result['manager_review']
            print(f"\nManager Review Status: {manager_review['status']}")
            print(f"Confidence Score: {manager_review['confidence_score']:.2f}")
            
            if manager_review['status'] == 'resolved':
                print("\nContradictions Found and Resolved:")
                for note in manager_review['review_notes']:
                    print(f"\n- Type: {note['type']}")
                    print(f"  Severity: {note['severity']}")
                    print(f"  Description: {note['description']}")
                    print(f"  Recommendation: {note['recommendation']}")
                
                if 'llm_recommendations' in manager_review:
                    print("\nLLM Recommendations:")
                    for rec in manager_review['llm_recommendations']:
                        print(f"- {rec}")
        
        # Print key analysis components
        if 'market_state' in analysis_result:
            market_state = analysis_result['market_state']
            print(f"\nMarket Sentiment: {market_state.get('overall_sentiment', 'N/A')}")
            print(f"Institutional Positioning: {market_state.get('institutional_positioning', 'N/A')}")
        
        if 'trading_opportunities' in analysis_result and 'strategies' in analysis_result['trading_opportunities']:
            strategies = analysis_result['trading_opportunities']['strategies']
            print("\nTrading Strategies:")
            for strategy in strategies:
                print(f"- {strategy.get('type', '')} ({strategy.get('direction', '')}): {strategy.get('rationale', '')}")
        
        return analysis_result
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    # Handle command line arguments
    ticker = sys.argv[1] if len(sys.argv) > 1 else 'SPY'
    risk_tolerance = sys.argv[2] if len(sys.argv) > 2 else 'medium'
    
    # Run the test
    asyncio.run(test_enhanced_pipeline(ticker, risk_tolerance)) 