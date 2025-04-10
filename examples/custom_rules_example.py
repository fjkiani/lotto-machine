#!/usr/bin/env python3
"""
Example script demonstrating how to use the dynamic rule system in the Enhanced Manager Review.

This example shows how to create conditional rules based on market conditions, add them at runtime,
and use them to analyze options data.
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

from src.llm.enhanced_manager_review import EnhancedManagerReview
from src.data.llm_api import analyze_options_chain

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_sample_data(ticker="AAPL"):
    """Load sample market data and options chain for demonstration."""
    try:
        # Try to load from test data
        sample_file = project_root / "tests" / "data" / f"{ticker}_sample.json"
        if sample_file.exists():
            with open(sample_file, "r") as f:
                return json.load(f)
        
        # If not available, create mock data
        return {
            "quote": {
                ticker: {
                    "regularMarketPrice": 175.0,
                    "regularMarketChange": 2.5,
                    "regularMarketChangePercent": 1.45,
                    "regularMarketVolume": 45000000,
                    "regularMarketDayHigh": 176.5,
                    "regularMarketDayLow": 173.2,
                }
            },
            "options_chain": {
                "calls": [
                    {"strike": 170, "lastPrice": 6.5, "openInterest": 10000, "volume": 5000},
                    {"strike": 175, "lastPrice": 3.2, "openInterest": 15000, "volume": 8000},
                    {"strike": 180, "lastPrice": 1.5, "openInterest": 20000, "volume": 12000},
                ],
                "puts": [
                    {"strike": 170, "lastPrice": 1.1, "openInterest": 8000, "volume": 3000},
                    {"strike": 175, "lastPrice": 2.9, "openInterest": 12000, "volume": 7000},
                    {"strike": 180, "lastPrice": 6.2, "openInterest": 9000, "volume": 4000},
                ]
            }
        }
    except Exception as e:
        logger.error(f"Error loading sample data: {str(e)}")
        raise

def create_market_specific_rules(vix_level, earnings_upcoming=False, fed_meeting=False):
    """
    Create market condition specific rules.
    
    Args:
        vix_level: Current VIX (volatility index) level
        earnings_upcoming: Whether there are upcoming earnings
        fed_meeting: Whether there's an upcoming Fed meeting
        
    Returns:
        List of rule dictionaries
    """
    rules = []
    
    # Rule for high volatility markets (VIX > 25)
    if vix_level > 25:
        rules.append({
            "rule_id": "high_vix_position_size",
            "config": {
                "conditions": [
                    "any(s.get('size', '') not in ['small', 'moderate'] for s in trading_opportunities.get('strategies', []) if isinstance(s, dict))"
                ],
                "severity": "high",
                "description": f"High market volatility (VIX: {vix_level}) with large position size recommendation",
                "recommendation": "During high VIX periods, reduce position sizing to small or moderate"
            }
        })
        
        # Additional rule for extremely high volatility (VIX > 35)
        if vix_level > 35:
            rules.append({
                "rule_id": "extreme_vix_strategy_type",
                "config": {
                    "conditions": [
                        "not any('hedge' in str(s.get('type', '')).lower() or 'spread' in str(s.get('type', '')).lower() for s in trading_opportunities.get('strategies', []) if isinstance(s, dict))"
                    ],
                    "severity": "high",
                    "description": f"Extreme market volatility (VIX: {vix_level}) requires hedged strategies",
                    "recommendation": "Use spreads or other defined-risk strategies during extreme volatility"
                }
            })
    
    # Rule for upcoming earnings
    if earnings_upcoming:
        rules.append({
            "rule_id": "earnings_strategy_adjustment",
            "config": {
                "conditions": [
                    "any(s.get('type', '') in ['long call', 'long put'] and s.get('size', '') != 'small' for s in trading_opportunities.get('strategies', []) if isinstance(s, dict))"
                ],
                "severity": "medium",
                "description": "Upcoming earnings event with directional strategy without defined risk",
                "recommendation": "Use spreads or small positions for earnings events to limit downside exposure"
            }
        })
    
    # Rule for Fed meeting days
    if fed_meeting:
        rules.append({
            "rule_id": "fed_meeting_volatility",
            "config": {
                "conditions": [
                    "volatility_structure.get('skew_analysis', {}).get('type', '') != 'high' and "
                    "any(s.get('type', '') not in ['iron condor', 'calendar spread'] for s in trading_opportunities.get('strategies', []) if isinstance(s, dict))"
                ],
                "severity": "medium",
                "description": "Fed meeting may cause volatility spike not reflected in current vol structure",
                "recommendation": "Consider volatility strategies like iron condors or calendar spreads for Fed meetings"
            }
        })
    
    return rules

def apply_conditional_rules(ticker="AAPL", vix_level=22, earnings_upcoming=False, fed_meeting=False):
    """
    Demonstrates applying conditional rules based on market conditions.
    
    Args:
        ticker: Stock ticker symbol
        vix_level: Current VIX level
        earnings_upcoming: Whether earnings are upcoming
        fed_meeting: Whether a Fed meeting is upcoming
    """
    logger.info(f"Analyzing {ticker} with VIX at {vix_level}, earnings_upcoming={earnings_upcoming}, fed_meeting={fed_meeting}")
    
    # Load sample data
    sample_data = load_sample_data(ticker)
    
    # Perform initial analysis
    initial_analysis = analyze_options_chain(ticker, sample_data, sample_data.get("options_chain", {}))
    
    # Print initial analysis summary
    print(f"\n=== Initial Analysis for {ticker} ===")
    print(f"Market Sentiment: {initial_analysis.get('market_sentiment', {}).get('short_term', 'unknown')}")
    print(f"Key Levels: Support at {initial_analysis.get('technical_signals', {}).get('support_levels', [0])[0] if initial_analysis.get('technical_signals', {}).get('support_levels') else 'unknown'}")
    print(f"Strategies: {', '.join(opp.get('strategy', 'unknown') for opp in initial_analysis.get('trading_opportunities', []))}")
    
    # Initialize enhanced manager review
    enhanced_manager = EnhancedManagerReview()
    
    # Get market-specific rules
    market_rules = create_market_specific_rules(vix_level, earnings_upcoming, fed_meeting)
    
    # Print rules to be applied
    print(f"\n=== Applying {len(market_rules)} Market-Specific Rules ===")
    for rule in market_rules:
        print(f"- {rule['rule_id']}: {rule['config']['description']}")
    
    # Add each market-specific rule
    for rule in market_rules:
        enhanced_manager.add_custom_rule(rule["rule_id"], rule["config"])
    
    # Run enhanced analysis
    review_result = enhanced_manager.review_analysis(initial_analysis)
    
    # Check if contradictions were found
    if review_result != initial_analysis:
        contradictions = review_result.get("contradictions_found", [])
        changes = review_result.get("changes_made", [])
        confidence = review_result.get("confidence_score", 0.0)
        
        print(f"\n=== Analysis Review Results ===")
        print(f"Contradictions Found: {len(contradictions)}")
        print(f"Changes Applied: {len(changes)}")
        print(f"Confidence Score: {confidence:.2f}")
        
        # Print contradictions
        if contradictions:
            print("\nContradictions:")
            for i, contradiction in enumerate(contradictions, 1):
                print(f"{i}. {contradiction.get('description', 'Unknown')}")
                print(f"   Recommendation: {contradiction.get('recommendation', 'None')}")
        
        # Print changes
        if changes:
            print("\nChanges Applied:")
            for i, change in enumerate(changes, 1):
                print(f"{i}. {change.get('rule', 'Unknown rule')}")
                print(f"   Changed {change.get('change', {}).get('component', 'unknown')} from "
                      f"'{change.get('change', {}).get('original', 'unknown')}' to "
                      f"'{change.get('change', {}).get('updated', 'unknown')}'")
    else:
        print("\nNo contradictions found in the analysis.")
    
    # Remove the custom rules
    for rule in market_rules:
        enhanced_manager.remove_custom_rule(rule["rule_id"])
    
    # Save results for inspection
    output_file = f"{ticker}_market_rules_analysis.json"
    with open(output_file, "w") as f:
        json.dump({
            "market_conditions": {
                "ticker": ticker,
                "vix_level": vix_level,
                "earnings_upcoming": earnings_upcoming,
                "fed_meeting": fed_meeting
            },
            "original_analysis": initial_analysis,
            "review_result": review_result,
            "rules_applied": [rule["rule_id"] for rule in market_rules]
        }, f, indent=2)
    
    logger.info(f"Results saved to {output_file}")
    print(f"\nResults saved to {output_file}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Demonstrate conditional rules in Enhanced Manager Review')
    parser.add_argument('--ticker', default='AAPL', help='Stock ticker symbol')
    parser.add_argument('--vix', type=float, default=22.5, help='Current VIX level')
    parser.add_argument('--earnings', action='store_true', help='Include if earnings are upcoming')
    parser.add_argument('--fed', action='store_true', help='Include if Fed meeting is upcoming')
    
    args = parser.parse_args()
    
    # Run the example
    apply_conditional_rules(args.ticker, args.vix, args.earnings, args.fed)
    
    # Show examples for different market conditions
    print("\n=== Additional Examples ===")
    print("Try these commands to see how different market conditions affect the analysis:")
    print(f"python {__file__} --ticker AAPL --vix 30 --earnings")
    print(f"python {__file__} --ticker TSLA --vix 45")
    print(f"python {__file__} --ticker SPY --vix 20 --fed") 