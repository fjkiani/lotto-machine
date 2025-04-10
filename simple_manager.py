#!/usr/bin/env python3
"""
Simplified Manager LLM Review for testing
"""

import json
from datetime import datetime

class SimpleManagerReview:
    """Simple manager review for testing"""
    
    def review_analysis(self, analysis):
        """
        Review an analysis for contradictions
        
        Args:
            analysis: Dictionary with analysis data
            
        Returns:
            Dictionary with review results
        """
        # Check for simple contradictions
        contradictions = []
        
        # Check for bullish sentiment with put strategies
        sentiment = analysis.get('market_state', {}).get('overall_sentiment', '')
        strategies = analysis.get('trading_opportunities', {}).get('strategies', [])
        
        for strategy in strategies:
            strategy_direction = strategy.get('direction', '')
            
            if sentiment == 'bullish' and strategy_direction == 'put':
                contradictions.append({
                    'type': 'sentiment_strategy_mismatch',
                    'severity': 'high',
                    'description': 'Bullish sentiment conflicts with put strategy',
                    'recommendation': 'Consider reducing position size or using spreads to manage risk'
                })
        
        # Check for high volatility with large position sizes
        volatility = analysis.get('volatility_structure', {}).get('skew_analysis', {}).get('type', '')
        
        for strategy in strategies:
            strategy_size = strategy.get('size', '')
            
            if volatility == 'high' and strategy_size == 'large':
                contradictions.append({
                    'type': 'volatility_size_mismatch',
                    'severity': 'high',
                    'description': 'Large position size in high volatility environment',
                    'recommendation': 'Consider reducing position size or using options spreads'
                })
        
        # Prepare the response
        if contradictions:
            # Calculate confidence score based on contradictions
            confidence_score = 1.0 - (len(contradictions) * 0.2)
            confidence_score = max(0.1, min(1.0, confidence_score))
            
            # Create a copy of the analysis to fix contradictions
            resolved_analysis = dict(analysis)
            
            # Apply fixes
            for contradiction in contradictions:
                if contradiction['type'] == 'sentiment_strategy_mismatch':
                    # Adjust strategy sizes
                    for strategy in resolved_analysis.get('trading_opportunities', {}).get('strategies', []):
                        if strategy.get('size', '') == 'large':
                            strategy['size'] = 'moderate'
                            strategy['rationale'] = f"{strategy.get('rationale', '')} (size adjusted due to sentiment mismatch)"
                
                elif contradiction['type'] == 'volatility_size_mismatch':
                    # Add risk factors
                    if 'risk_factors' not in resolved_analysis:
                        resolved_analysis['risk_factors'] = []
                    
                    resolved_analysis['risk_factors'].append({
                        'type': 'volatility_warning',
                        'severity': 'high',
                        'description': 'High volatility environment requires careful position sizing'
                    })
            
            return {
                'status': 'resolved',
                'confidence_score': confidence_score,
                'original_analysis': analysis,
                'resolved_analysis': resolved_analysis,
                'review_notes': contradictions,
                'timestamp': datetime.now().isoformat()
            }
        else:
            return {
                'status': 'validated',
                'confidence_score': 1.0,
                'analysis': analysis,
                'review_notes': ['No contradictions found in analysis']
            }

def test_simple_manager():
    """Test the simple manager review"""
    
    # Create a test analysis with contradictions
    test_analysis = {
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
    
    # Initialize the simple manager
    manager = SimpleManagerReview()
    
    # Review the analysis
    result = manager.review_analysis(test_analysis)
    
    # Print the results
    print("\n===== SIMPLE MANAGER REVIEW RESULTS =====")
    print(f"Status: {result.get('status')}")
    print(f"Confidence Score: {result.get('confidence_score'):.2f}")
    
    if result.get('status') == 'resolved':
        print("\nContradictions Found:")
        for note in result.get('review_notes', []):
            print(f"\n- Type: {note.get('type')}")
            print(f"  Severity: {note.get('severity')}")
            print(f"  Description: {note.get('description')}")
            print(f"  Recommendation: {note.get('recommendation')}")
        
        print("\nKey Changes in Analysis:")
        original = result.get('original_analysis', {})
        resolved = result.get('resolved_analysis', {})
        
        # Compare strategies
        orig_strategies = original.get('trading_opportunities', {}).get('strategies', [])
        new_strategies = resolved.get('trading_opportunities', {}).get('strategies', [])
        
        for i, (orig, new) in enumerate(zip(orig_strategies, new_strategies)):
            if orig.get('size') != new.get('size'):
                print(f"  Strategy {i+1} Size: {orig.get('size')} -> {new.get('size')}")
            
            if orig.get('rationale') != new.get('rationale'):
                print(f"  Strategy {i+1} Rationale updated")
        
        # Check for added risk factors
        if 'risk_factors' in resolved and ('risk_factors' not in original or 
                                         len(resolved['risk_factors']) > len(original.get('risk_factors', []))):
            print("\n  Added Risk Factors:")
            for risk in resolved.get('risk_factors', []):
                print(f"  - {risk.get('description', 'N/A')}")
    
    return result

if __name__ == "__main__":
    test_simple_manager() 