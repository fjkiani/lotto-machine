#!/usr/bin/env python3
"""
Test script for the Enhanced Manager Review system
This demonstrates how the configurable rules work and the flexibility of the system.
"""

import os
import sys
import json
import logging
import yaml
from pathlib import Path
from datetime import datetime

# Add the source directory to the path
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from src.llm.enhanced_manager_review import EnhancedManagerReview, Rule

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_analysis():
    """
    Create a test analysis with various components 
    and potential contradictions for testing
    """
    current_price = 150.0
    
    return {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "ticker": "TEST",
            "version": "1.0.0"
        },
        "market_state": {
            "overall_sentiment": "bullish",
            "institutional_positioning": "net_long",
            "retail_activity": "buying_calls",
            "current_price": current_price,
            "sector_performance": "strong"
        },
        "price_levels": {
            "current_price": current_price,
            # Support and resistance levels that are too close to each other (contradiction)
            "support_levels": [
                {"price": 148.5, "strength": "strong", "source": "option_concentration"},
                {"price": 145.0, "strength": "medium", "source": "prior_low"}
            ],
            "resistance_levels": [
                {"price": 149.0, "strength": "strong", "source": "option_concentration"},
                {"price": 155.0, "strength": "medium", "source": "prior_high"}
            ]
        },
        "volatility_structure": {
            "skew_analysis": {
                "type": "high",
                "description": "Significant put skew indicating hedging demand"
            },
            "term_structure": "contango",
            "iv_percentile": 75
        },
        "trading_opportunities": {
            "strategies": [
                # Bullish sentiment but put-focused strategy (contradiction)
                {
                    "name": "Put Spread",
                    "direction": "put",
                    "size": "large",
                    "strikes": [145, 140],
                    "rationale": "Hedge against potential pullback"
                },
                {
                    "name": "Call Spread",
                    "direction": "call",
                    "size": "large",  # Large size in high volatility (contradiction)
                    "strikes": [155, 160],
                    "rationale": "Capitalize on bullish momentum"
                }
            ]
        },
        "technical_signals": {
            "momentum_bias": "bullish",
            "supports": ["148.5", "145.0"],
            "resistances": ["155.0", "160.0"],
            "emerging_pattern": "bull flag"
        },
        "institutional_flows": {
            "options_activity": "bullish_call_buying",
            "hedging_patterns": "protective_puts",
            "significant_strikes": [150, 145, 160]
        }
    }

def create_custom_rule():
    """Create a custom rule for testing"""
    custom_rule = Rule(
        name="custom_momentum_strategy_rule",
        condition="""
analysis.get('technical_signals', {}).get('momentum_bias') == 'bullish' and
any(s.get('direction') == 'put' and 'hedge' not in s.get('rationale', '').lower()
    for s in analysis.get('trading_opportunities', {}).get('strategies', []))
        """,
        severity="medium",
        description_template="Bullish momentum with non-hedging put strategies",
        recommendation_template="Align strategies with bullish momentum or clearly label as hedges"
    )
    return custom_rule

def test_different_modes():
    """Test different validation modes"""
    logger.info("Testing Enhanced Manager Review with different modes")
    analysis = create_test_analysis()
    
    # Test enhanced mode
    config = {
        "system": {
            "validation_mode": "enhanced",
            "fallback_mode": "static"
        },
        "validation": {
            "thresholds": {
                "price_overlap_percent": 1.0,
                "volatility_threshold": 25.0,
                "volume_significance": 1000
            },
            "confidence_penalties": {
                "high_severity": 0.2,
                "medium_severity": 0.1,
                "low_severity": 0.05
            }
        },
        "rules": []
    }
    
    # Save config to temporary file
    config_path = Path("temp_config.yaml")
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    # Create review instance with enhanced mode
    enhanced_reviewer = EnhancedManagerReview(str(config_path))
    enhanced_reviewer.validation_mode = "enhanced"
    
    # Run review
    enhanced_results = enhanced_reviewer.review_analysis(analysis)
    
    # Test static mode
    static_reviewer = EnhancedManagerReview(str(config_path))
    static_reviewer.validation_mode = "static"
    static_results = static_reviewer.review_analysis(analysis)
    
    # Display results
    logger.info(f"Enhanced mode confidence: {enhanced_results.get('confidence_score', 'N/A')}")
    logger.info(f"Static mode confidence: {static_results.get('confidence_score', 'N/A')}")
    
    # Clean up
    if config_path.exists():
        config_path.unlink()
    
    return enhanced_results, static_results

def test_custom_rules():
    """Test adding custom rules to the system"""
    logger.info("Testing Enhanced Manager Review with custom rules")
    analysis = create_test_analysis()
    
    # Create review instance
    reviewer = EnhancedManagerReview()
    
    # Add custom rule
    custom_rule = create_custom_rule()
    reviewer.rules.append(custom_rule)
    
    # Run review
    results = reviewer._enhanced_review(analysis)
    
    # Display results
    logger.info(f"Review with custom rule - Status: {results.get('status', 'unknown')}")
    logger.info(f"Review with custom rule - Confidence: {results.get('confidence_score', 'N/A')}")
    
    if results.get('status') == 'resolved':
        logger.info("Contradictions found:")
        for note in results.get('review_notes', []):
            logger.info(f"  - {note.get('type')}: {note.get('description')} ({note.get('severity')})")
            logger.info(f"    Recommendation: {note.get('recommendation')}")
    
    # Save results to file
    with open("custom_rule_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info("Results saved to custom_rule_results.json")
    return results

def test_recommendation_application():
    """Test how recommendations are applied to the analysis"""
    logger.info("Testing automatic recommendation application")
    analysis = create_test_analysis()
    
    # Create review instance
    reviewer = EnhancedManagerReview()
    
    # Run review and get resolved analysis
    results = reviewer._enhanced_review(analysis)
    
    if results.get('status') == 'resolved':
        # Compare original and resolved analysis
        original = results.get('original_analysis', {})
        resolved = results.get('resolved_analysis', {})
        
        # Compare specific sections
        sections_to_compare = [
            'trading_opportunities',
            'price_levels',
            'risk_factors'
        ]
        
        logger.info("Changes made by automatic recommendations:")
        for section in sections_to_compare:
            if section in original and section in resolved and original.get(section) != resolved.get(section):
                logger.info(f"  - Changes in {section}:")
                if section == 'trading_opportunities':
                    # Compare strategies
                    orig_strats = original.get(section, {}).get('strategies', [])
                    res_strats = resolved.get(section, {}).get('strategies', [])
                    for i, (orig, res) in enumerate(zip(orig_strats, res_strats)):
                        if orig != res:
                            logger.info(f"    Strategy {i+1} changed:")
                            for key in res:
                                if key in orig and orig[key] != res[key]:
                                    logger.info(f"      {key}: {orig[key]} -> {res[key]}")
                elif section == 'price_levels':
                    # Check for added notes
                    orig_notes = original.get(section, {}).get('notes', [])
                    res_notes = resolved.get(section, {}).get('notes', [])
                    if len(res_notes) > len(orig_notes):
                        logger.info(f"    Added notes: {res_notes[len(orig_notes):]}")
                elif section == 'risk_factors':
                    # Check for added risk factors
                    orig_risks = original.get(section, [])
                    res_risks = resolved.get(section, [])
                    if len(res_risks) > len(orig_risks):
                        logger.info(f"    Added risk factors:")
                        for risk in res_risks[len(orig_risks):]:
                            logger.info(f"      - {risk.get('type')}: {risk.get('description')} ({risk.get('severity')})")
    
    return results

def main():
    """Main test function"""
    logger.info("Starting Enhanced Manager Review tests")
    
    # Run tests and save results
    results = {}
    
    try:
        # Test different modes
        logger.info("\n--- Testing different modes ---")
        results['modes'] = test_different_modes()
        
        # Test custom rules
        logger.info("\n--- Testing custom rules ---")
        results['custom_rules'] = test_custom_rules()
        
        # Test recommendation application
        logger.info("\n--- Testing recommendation application ---")
        results['recommendations'] = test_recommendation_application()
        
        # Save combined results
        with open("enhanced_review_results.json", "w") as f:
            simplified_results = {
                'modes': {
                    'enhanced': {
                        'status': results['modes'][0].get('status'),
                        'confidence': results['modes'][0].get('confidence_score'),
                        'notes_count': len(results['modes'][0].get('review_notes', [])),
                    },
                    'static': {
                        'status': results['modes'][1].get('status'),
                        'confidence': results['modes'][1].get('confidence_score'),
                        'notes_count': len(results['modes'][1].get('review_notes', [])),
                    }
                },
                'custom_rules': {
                    'status': results['custom_rules'].get('status'),
                    'confidence': results['custom_rules'].get('confidence_score'),
                    'notes_count': len(results['custom_rules'].get('review_notes', [])),
                },
                'recommendations': {
                    'status': results['recommendations'].get('status'),
                    'confidence': results['recommendations'].get('confidence_score'),
                    'changes_made': results['recommendations'].get('status') == 'resolved'
                }
            }
            json.dump(simplified_results, f, indent=2)
        
        logger.info("All tests completed successfully")
        logger.info("Summary results saved to enhanced_review_results.json")
        
    except Exception as e:
        logger.error(f"Error during testing: {str(e)}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 