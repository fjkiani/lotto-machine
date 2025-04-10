#!/usr/bin/env python3
"""
Test script for Manager LLM Review system
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Add the project root directory to the Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from src.llm.manager_review import ManagerLLMReview

# Setup logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

def test_manager_review():
    """Test the Manager LLM Review system"""
    logger.info("Testing Manager LLM Review system...")
    
    # Create test analysis
    test_analysis = create_test_analysis()
    
    # Initialize manager review
    manager = ManagerLLMReview()
    
    # Review analysis
    logger.info("Reviewing analysis for contradictions...")
    review_result = manager.review_analysis(test_analysis)
    
    # Print results
    print("\n===== MANAGER REVIEW RESULTS =====")
    print(f"Status: {review_result['status']}")
    print(f"Confidence Score: {review_result['confidence_score']:.2f}")
    
    if review_result['status'] == 'resolved':
        print("\nContradictions Found:")
        for note in review_result['review_notes']:
            print(f"\n- Type: {note['type']}")
            print(f"  Severity: {note['severity']}")
            print(f"  Description: {note['description']}")
            print(f"  Recommendation: {note['recommendation']}")
        
        # Save results
        output_file = 'manager_review_results.json'
        with open(output_file, 'w') as f:
            json.dump(review_result, f, indent=2)
        logger.info(f"Saved review results to {output_file}")
        
        # Compare original vs resolved analysis
        print("\nKey Changes in Resolved Analysis:")
        _compare_analyses(review_result['original_analysis'], 
                        review_result['resolved_analysis'])

def _compare_analyses(original: dict, resolved: dict, path: str = ""):
    """Compare original and resolved analyses to highlight changes"""
    for key in original:
        if key not in resolved:
            print(f"Removed: {path}{key}")
            continue
            
        if isinstance(original[key], dict) and isinstance(resolved[key], dict):
            _compare_analyses(original[key], resolved[key], f"{path}{key}.")
        elif original[key] != resolved[key]:
            print(f"Changed: {path}{key}")
            print(f"  From: {original[key]}")
            print(f"  To:   {resolved[key]}")

if __name__ == "__main__":
    test_manager_review() 