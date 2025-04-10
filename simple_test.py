#!/usr/bin/env python3
"""
Simple test script for Manager LLM Review
"""

import os
import sys
import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the manager review classes
try:
    from src.llm.manager_review import ManagerLLMReview
    from src.llm.dynamic_manager_review import DynamicManagerLLMReview
except ImportError as e:
    logger.error(f"Import error: {str(e)}")
    sys.exit(1)

def create_test_analysis():
    """Create a test analysis with potential contradictions"""
    return {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "ticker": "SPY",
            "current_price": 500.0,
            "analysis_version": "2.0"
        },
        "market_state": {
            "overall_sentiment": "bullish",
            "institutional_positioning": "protective",
            "retail_activity": {
                "sentiment": "bullish",
                "conviction": "high",
                "reliability": "moderate"
            }
        },
        "price_levels": {
            "support_levels": [
                {"price": 495.0, "strength": "strong", "type": "institutional"},
                {"price": 498.0, "strength": "moderate", "type": "technical"}
            ],
            "resistance_levels": [
                {"price": 498.5, "strength": "strong", "type": "institutional"},
                {"price": 505.0, "strength": "moderate", "type": "technical"}
            ]
        },
        "volatility_structure": {
            "skew_analysis": {
                "type": "high",
                "strength": 0.8,
                "interpretation": "Institutional hedging"
            }
        },
        "trading_opportunities": {
            "strategies": [
                {
                    "type": "directional",
                    "direction": "put",
                    "size": "large",
                    "confidence": "moderate",
                    "rationale": "Technical breakout expected"
                }
            ]
        },
        "technical_signals": {
            "momentum_bias": "bullish",
            "support_zones": [495.0, 498.0],
            "resistance_zones": [505.0, 510.0]
        },
        "institutional_flows": {
            "hedging_patterns": {
                "hedging_type": "protective",
                "put_walls": [
                    {"strike": 495.0, "size": 10000}
                ]
            }
        }
    }

def test_static_manager_review():
    """Test the static Manager LLM Review"""
    logger.info("Testing static Manager LLM Review...")
    
    # Create test analysis
    test_analysis = create_test_analysis()
    
    # Initialize manager review
    try:
        manager = ManagerLLMReview()
    except Exception as e:
        logger.error(f"Error initializing static manager: {str(e)}")
        return
    
    # Review analysis
    logger.info("Reviewing analysis with static manager...")
    try:
        review_result = manager.review_analysis(test_analysis)
        logger.info(f"Static review result status: {review_result.get('status')}")
        logger.info(f"Static review confidence score: {review_result.get('confidence_score')}")
        return review_result
    except Exception as e:
        logger.error(f"Error in static review: {str(e)}")
        return None

def test_dynamic_manager_review():
    """Test the dynamic Manager LLM Review"""
    logger.info("Testing dynamic Manager LLM Review...")
    
    # Create test analysis
    test_analysis = create_test_analysis()
    
    # Initialize dynamic manager review
    try:
        dynamic_manager = DynamicManagerLLMReview()
    except Exception as e:
        logger.error(f"Error initializing dynamic manager: {str(e)}")
        return
    
    # Review analysis
    logger.info("Reviewing analysis with dynamic manager...")
    try:
        # Create simple market context
        market_context = {
            "technical_indicators": {
                "sma20": 495.0,
                "sma50": 490.0,
                "rsi": 65
            },
            "recent_news": [
                {"title": "Test news item", "published": "2023-04-08T12:00:00"}
            ]
        }
        
        review_result = dynamic_manager.review_analysis(test_analysis, market_context)
        logger.info(f"Dynamic review result status: {review_result.get('status')}")
        logger.info(f"Dynamic review confidence score: {review_result.get('confidence_score')}")
        return review_result
    except Exception as e:
        logger.error(f"Error in dynamic review: {str(e)}")
        return None

def main():
    """Main function"""
    logger.info("Starting manager review tests...")
    
    # Test static manager review
    static_result = test_static_manager_review()
    
    # Test dynamic manager review
    dynamic_result = test_dynamic_manager_review()
    
    # Output results
    print("\n===== TEST RESULTS =====")
    
    if static_result:
        print("\nStatic Manager Review:")
        print(f"Status: {static_result.get('status')}")
        print(f"Confidence Score: {static_result.get('confidence_score'):.2f}")
        
        if static_result.get('status') == 'resolved':
            print("\nContradictions Found:")
            for note in static_result.get('review_notes', []):
                print(f"- {note.get('description')}")
                print(f"  Recommendation: {note.get('recommendation')}")
    else:
        print("\nStatic Manager Review: Failed")
    
    if dynamic_result:
        print("\nDynamic Manager Review:")
        print(f"Status: {dynamic_result.get('status')}")
        print(f"Confidence Score: {dynamic_result.get('confidence_score'):.2f}")
        
        if dynamic_result.get('status') == 'resolved':
            print("\nContradictions Found:")
            for note in dynamic_result.get('review_notes', []):
                print(f"- {note.get('description')}")
                print(f"  Recommendation: {note.get('recommendation')}")
            
            # Check for LLM recommendations
            llm_recommendations = dynamic_result.get('llm_recommendations', [])
            if llm_recommendations:
                print("\nLLM Recommendations:")
                for rec in llm_recommendations:
                    print(f"- {rec}")
    else:
        print("\nDynamic Manager Review: Failed")
    
    print("\nTest complete.")

if __name__ == "__main__":
    main() 