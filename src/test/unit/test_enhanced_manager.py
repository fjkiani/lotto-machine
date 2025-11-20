#!/usr/bin/env python3
"""
Test script for the EnhancedManagerReview class.

This script creates a sample analysis with contradictions and runs it through
the enhanced manager review system to test contradiction detection and automated fixes.
"""

import os
import sys
import json
import logging
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add the project root directory to the Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from src.llm.enhanced_manager_review import EnhancedManagerReview

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_analysis() -> Dict[str, Any]:
    """
    Create a test analysis with intentional contradictions.
    
    Returns:
        Dict containing a mock analysis with various components.
    """
    # Random values for price
    current_price = random.uniform(100.0, 200.0)
    
    # Intentionally create contradictions:
    # 1. Bullish sentiment with put-focused strategy
    # 2. Support and resistance too close to each other
    # 3. High volatility with large position size
    
    analysis = {
        "metadata": {
            "ticker": "TESTCO",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        },
        "market_state": {
            "overall_sentiment": "bullish",  # Contradiction with put strategy below
            "institutional_positioning": "net_long",
            "retail_activity": "increasing_calls"
        },
        "price_levels": {
            "current_price": current_price,
            # Support and resistance too close (less than 1% apart)
            "support": current_price * 0.995,  # Intentional contradiction
            "resistance": current_price * 1.005,
            "next_earnings": "2023-06-15"
        },
        "volatility_structure": {
            "skew": "high",  # Contradiction with large position size below
            "term_structure": "contango",
            "iv_rank": 75
        },
        "institutional_flows": {
            "hedging_patterns": {
                "hedging_type": "protective",
                "significant_levels": [current_price * 0.9, current_price * 1.1]
            },
            "unusual_activity": {
                "unusual_type": "call_buying",
                "unusual_strikes": [str(int(current_price * 1.1)), str(int(current_price * 1.2))]
            }
        },
        "trading_opportunities": [
            {
                "strategy": "Put Spread",  # Contradiction with bullish sentiment
                "description": "Buy puts at strike near support and sell puts at lower strike.",
                "position_size": "large",  # Contradiction with high volatility
                "risk_reward": "3:1",
                "target_price": current_price * 0.9
            }
        ],
        "risk_factors": [
            {
                "type": "earnings",
                "severity": "medium",
                "description": "Upcoming earnings may increase volatility"
            },
            {
                "type": "sector_rotation",
                "severity": "low",
                "description": "Sector seeing outflows in recent sessions"
            }
        ],
        "technical_signals": {
            "momentum_bias": "bullish",
            "support_zones": [current_price * 0.85, current_price * 0.9, current_price * 0.95],
            "resistance_zones": [current_price * 1.05, current_price * 1.1, current_price * 1.15]
        },
        "detailed_analysis": "The stock is showing bullish momentum with strong technical support. Institutional buyers are accumulating shares while maintaining protective hedges."
    }
    
    return analysis

def test_enhanced_manager_review():
    """
    Test the EnhancedManagerReview class.
    
    Creates a test analysis with contradictions, runs it through the 
    enhanced manager review, and displays the results.
    """
    logger.info("Starting test of EnhancedManagerReview")
    
    # Create test analysis with contradictions
    logger.info("Creating test analysis with intentional contradictions")
    test_analysis = create_test_analysis()
    
    # Initialize enhanced manager review
    logger.info("Initializing EnhancedManagerReview")
    enhanced_manager = EnhancedManagerReview()
    
    # Review the analysis
    logger.info("Reviewing analysis for contradictions")
    result = enhanced_manager.review_analysis(test_analysis)
    
    # Check if contradictions were found
    if result == test_analysis:
        logger.warning("No contradictions were found in the analysis")
        print("Test failed: The EnhancedManagerReview did not detect contradictions")
        return
    
    # Get results
    original_analysis = result.get("original_analysis", {})
    contradictions = result.get("contradictions_found", [])
    resolved_analysis = result.get("resolved_analysis", {})
    confidence_score = result.get("confidence_score", 0.0)
    review_notes = result.get("review_notes", "")
    changes_made = result.get("changes_made", [])
    
    # Log results
    logger.info(f"Found {len(contradictions)} contradictions")
    logger.info(f"Confidence score: {confidence_score:.2f}")
    logger.info(f"Made {len(changes_made)} changes to resolve contradictions")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Enhanced Manager Review Test Results")
    print(f"{'='*60}")
    print(f"Status: {'SUCCESS' if contradictions else 'FAILED'}")
    print(f"Contradictions found: {len(contradictions)}")
    print(f"Confidence score: {confidence_score:.2f}")
    print(f"Changes made: {len(changes_made)}")
    print(f"{'='*60}\n")
    
    # Print contradictions
    if contradictions:
        print("Contradictions found:")
        for i, contradiction in enumerate(contradictions, 1):
            print(f"{i}. {contradiction.get('rule', 'Unknown')} - {contradiction.get('severity', 'Unknown')} severity")
            print(f"   Description: {contradiction.get('description', 'No description')}")
            print(f"   Recommendation: {contradiction.get('recommendation', 'No recommendation')}")
            print()
    
    # Print changes made
    if changes_made:
        print("Changes applied:")
        for i, change in enumerate(changes_made, 1):
            rule = change.get("rule", "Unknown")
            component = change.get("change", {}).get("component", "Unknown")
            original = change.get("change", {}).get("original", "Unknown")
            updated = change.get("change", {}).get("updated", "Unknown")
            print(f"{i}. Rule: {rule}")
            print(f"   Component: {component}")
            print(f"   Changed from: {original}")
            print(f"   Changed to: {updated}")
            print()
    
    # Print review notes
    print("Review Notes:")
    print(review_notes)
    print()
    
    # Compare the original and resolved analyses
    print("Differences between original and resolved analysis:")
    _compare_analyses(original_analysis, resolved_analysis)
    
    # Save results to a file for inspection
    output_file = "enhanced_manager_review_results.json"
    with open(output_file, "w") as f:
        json.dump({
            "original_analysis": original_analysis,
            "contradictions": contradictions,
            "resolved_analysis": resolved_analysis,
            "confidence_score": confidence_score,
            "review_notes": review_notes,
            "changes_made": changes_made
        }, f, indent=2)
    
    logger.info(f"Results saved to {output_file}")

def test_custom_rules():
    """
    Test the custom rules functionality of EnhancedManagerReview.
    
    This test demonstrates adding a custom rule at runtime, testing it against 
    an analysis, and then removing it.
    """
    logger.info("Starting test of custom rules functionality")
    
    # Create test analysis
    test_analysis = create_test_analysis()
    
    # Initialize enhanced manager review
    logger.info("Initializing EnhancedManagerReview")
    enhanced_manager = EnhancedManagerReview()
    
    # First, list existing rules
    logger.info("Listing existing rules")
    existing_rules = enhanced_manager.list_rules()
    print(f"Found {len(existing_rules['built_in'])} built-in rules")
    print(f"Found {len(existing_rules['custom'])} custom rules")
    
    # Create a custom rule - detecting a mismatch between earnings and trading opportunities
    earnings_rule = {
        "conditions": [
            "any(risk.get('type') == 'earnings' for risk in analysis.get('risk_factors', []) if isinstance(risk, dict)) and "
            "any(opp.get('position_size') == 'large' for opp in analysis.get('trading_opportunities', []) if isinstance(opp, dict))"
        ],
        "severity": "high",
        "description": "Found large position size recommendation with upcoming earnings event, which increases risk",
        "recommendation": "Consider reducing position size before earnings or using defined risk strategies like spreads",
        "fix_method": None  # No automated fix for this rule
    }
    
    # Add the custom rule
    logger.info("Adding custom rule for earnings risk")
    success = enhanced_manager.add_custom_rule("earnings_position_mismatch", earnings_rule)
    
    if not success:
        logger.error("Failed to add custom rule")
        print("Test failed: Could not add custom rule")
        return
    
    # Verify the rule was added
    updated_rules = enhanced_manager.list_rules()
    print(f"Now have {len(updated_rules['custom'])} custom rules")
    
    # Run analysis with the custom rule
    logger.info("Reviewing analysis with custom rule")
    result = enhanced_manager.review_analysis(test_analysis)
    
    # Check if the custom rule detected a contradiction
    contradictions = result.get("contradictions_found", [])
    earnings_contradictions = [c for c in contradictions if "earnings" in c.get("description", "").lower()]
    
    if earnings_contradictions:
        print("\nCustom rule detected contradiction:")
        for contradiction in earnings_contradictions:
            print(f"Rule: {contradiction.get('rule', 'Unknown')}")
            print(f"Description: {contradiction.get('description', 'No description')}")
            print(f"Recommendation: {contradiction.get('recommendation', 'No recommendation')}")
            print(f"Severity: {contradiction.get('severity', 'Unknown')}")
    else:
        print("\nCustom rule did not detect any contradictions")
    
    # Remove the custom rule
    logger.info("Removing custom rule")
    enhanced_manager.remove_custom_rule("earnings_position_mismatch")
    
    # Verify the rule was removed
    final_rules = enhanced_manager.list_rules()
    print(f"After removal: {len(final_rules['custom'])} custom rules")
    
    # Run analysis again to verify the rule is no longer applied
    logger.info("Reviewing analysis after removing custom rule")
    result_after_removal = enhanced_manager.review_analysis(test_analysis)
    
    # Check if any earnings contradictions are still detected
    contradictions_after = result_after_removal.get("contradictions_found", [])
    earnings_contradictions_after = [c for c in contradictions_after if "earnings" in c.get("description", "").lower()]
    
    if not earnings_contradictions_after:
        print("Success: No earnings contradictions detected after rule removal")
    else:
        print("Warning: Earnings contradictions still detected after rule removal")
    
    print("\nCustom rule test completed")

def _compare_analyses(original: Dict[str, Any], resolved: Dict[str, Any], path: str = ""):
    """
    Compare original and resolved analyses to highlight changes.
    
    Args:
        original: Original analysis dictionary
        resolved: Resolved analysis dictionary
        path: Current path in the nested dictionaries
    """
    if isinstance(original, dict) and isinstance(resolved, dict):
        for key in set(list(original.keys()) + list(resolved.keys())):
            if key in original and key in resolved:
                if original[key] != resolved[key]:
                    new_path = f"{path}.{key}" if path else key
                    if isinstance(original[key], (dict, list)) and isinstance(resolved[key], (dict, list)):
                        _compare_analyses(original[key], resolved[key], new_path)
                    else:
                        print(f"  - {new_path}: {original[key]} -> {resolved[key]}")
            elif key in original:
                new_path = f"{path}.{key}" if path else key
                print(f"  - {new_path}: {original[key]} -> [REMOVED]")
            else:
                new_path = f"{path}.{key}" if path else key
                print(f"  - {new_path}: [ADDED] -> {resolved[key]}")
    
    elif isinstance(original, list) and isinstance(resolved, list):
        if len(original) == len(resolved):
            for i, (orig_item, res_item) in enumerate(zip(original, resolved)):
                new_path = f"{path}[{i}]"
                if orig_item != res_item:
                    if isinstance(orig_item, (dict, list)) and isinstance(res_item, (dict, list)):
                        _compare_analyses(orig_item, res_item, new_path)
                    else:
                        print(f"  - {new_path}: {orig_item} -> {res_item}")
        else:
            print(f"  - {path}: List length changed from {len(original)} to {len(resolved)}")
    
    else:
        print(f"  - {path}: {original} -> {resolved}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test the EnhancedManagerReview class')
    parser.add_argument('--test-type', choices=['standard', 'custom', 'all'], default='all',
                      help='Type of test to run (standard, custom, or all)')
    
    args = parser.parse_args()
    
    if args.test_type in ['standard', 'all']:
        print("\n=== Running Standard Test ===\n")
        test_enhanced_manager_review()
    
    if args.test_type in ['custom', 'all']:
        print("\n=== Running Custom Rules Test ===\n")
        test_custom_rules() 