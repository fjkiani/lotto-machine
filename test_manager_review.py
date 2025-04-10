#!/usr/bin/env python3
"""
Test script for Manager LLM Review system
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

# Add the current directory to sys.path
sys.path.insert(0, os.path.abspath('.'))

def create_test_analysis():
    """Create a simple test analysis with potential contradictions"""
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

class ContradictionResult:
    def __init__(self, has_issues: bool, details: dict):
        self.has_issues = has_issues
        self.details = details

class AnalysisValidator:
    """Validates analysis results for contradictions and inconsistencies"""
    
    def __init__(self):
        self.contradiction_checks = [
            self._check_sentiment_strategy_alignment,
            self._check_price_target_consistency,
            self._check_risk_reward_ratios,
            self._check_technical_fundamental_alignment
        ]
    
    def _check_sentiment_strategy_alignment(self, analysis: dict) -> ContradictionResult:
        """Check if sentiment aligns with suggested strategies"""
        sentiment = analysis.get('market_state', {}).get('overall_sentiment', '')
        strategies = analysis.get('trading_opportunities', {}).get('strategies', [])
        
        issues = []
        for strategy in strategies:
            if sentiment == 'bullish' and strategy.get('direction') == 'put':
                issues.append({
                    'type': 'sentiment_strategy_mismatch',
                    'severity': 'high',
                    'description': f"Bullish sentiment conflicts with put strategy: {strategy.get('rationale')}",
                    'components': ['sentiment', 'strategy']
                })
            elif sentiment == 'bearish' and strategy.get('direction') == 'call':
                issues.append({
                    'type': 'sentiment_strategy_mismatch',
                    'severity': 'high',
                    'description': f"Bearish sentiment conflicts with call strategy: {strategy.get('rationale')}",
                    'components': ['sentiment', 'strategy']
                })
        
        return ContradictionResult(bool(issues), {'issues': issues})
    
    def _check_price_target_consistency(self, analysis: dict) -> ContradictionResult:
        """Check if price targets are consistent with support/resistance levels"""
        price_levels = analysis.get('price_levels', {})
        support_levels = price_levels.get('support_levels', [])
        resistance_levels = price_levels.get('resistance_levels', [])
        current_price = analysis.get('metadata', {}).get('current_price', 0)
        
        issues = []
        
        # Check for overlapping support/resistance levels
        for support in support_levels:
            for resistance in resistance_levels:
                if abs(support['price'] - resistance['price']) / current_price < 0.01:  # Within 1%
                    issues.append({
                        'type': 'overlapping_levels',
                        'severity': 'medium',
                        'description': f"Support at {support['price']} overlaps with resistance at {resistance['price']}",
                        'components': ['support_levels', 'resistance_levels']
                    })
        
        return ContradictionResult(bool(issues), {'issues': issues})
    
    def _check_risk_reward_ratios(self, analysis: dict) -> ContradictionResult:
        """Check if risk/reward ratios are reasonable given market conditions"""
        volatility = analysis.get('volatility_structure', {})
        strategies = analysis.get('trading_opportunities', {}).get('strategies', [])
        
        issues = []
        
        # Check for aggressive strategies in high volatility
        if volatility.get('skew_analysis', {}).get('type') == 'high':
            for strategy in strategies:
                if strategy.get('size', '') == 'large' and strategy.get('confidence', '') != 'high':
                    issues.append({
                        'type': 'aggressive_volatility_mismatch',
                        'severity': 'high',
                        'description': f"Large position size suggested in high volatility environment",
                        'components': ['volatility', 'strategy']
                    })
        
        return ContradictionResult(bool(issues), {'issues': issues})
    
    def _check_technical_fundamental_alignment(self, analysis: dict) -> ContradictionResult:
        """Check if technical signals align with fundamental/flow analysis"""
        technical = analysis.get('technical_signals', {})
        institutional = analysis.get('institutional_flows', {})
        
        issues = []
        
        # Check for misalignment between technical signals and institutional activity
        tech_trend = technical.get('momentum_bias', 'neutral')
        inst_positioning = institutional.get('hedging_patterns', {}).get('hedging_type', '')
        
        if tech_trend == 'bullish' and inst_positioning == 'protective':
            issues.append({
                'type': 'technical_institutional_mismatch',
                'severity': 'medium',
                'description': "Bullish technical signals conflict with defensive institutional positioning",
                'components': ['technical', 'institutional']
            })
        
        return ContradictionResult(bool(issues), {'issues': issues})
    
    def validate(self, analysis: dict) -> dict:
        """Run all contradiction checks and compile results"""
        all_issues = []
        
        for check in self.contradiction_checks:
            result = check(analysis)
            if result.has_issues:
                all_issues.extend(result.details['issues'])
        
        return self._resolve_contradictions(analysis, all_issues)
    
    def _resolve_contradictions(self, analysis: dict, issues: list) -> dict:
        """Attempt to resolve contradictions and provide a cleaned analysis"""
        if not issues:
            return {
                'has_contradictions': False,
                'original_analysis': analysis,
                'resolved_analysis': analysis,
                'confidence_score': 1.0,
                'review_notes': []
            }
        
        # Group issues by severity
        high_severity = [i for i in issues if i['severity'] == 'high']
        medium_severity = [i for i in issues if i['severity'] == 'medium']
        
        # Calculate confidence score based on issues
        base_confidence = 1.0
        confidence_score = base_confidence - (len(high_severity) * 0.2) - (len(medium_severity) * 0.1)
        confidence_score = max(0.1, min(1.0, confidence_score))
        
        # Generate review notes
        review_notes = [
            {
                'type': issue['type'],
                'severity': issue['severity'],
                'description': issue['description'],
                'recommendation': self._generate_recommendation(issue)
            }
            for issue in issues
        ]
        
        # Create resolved analysis by adjusting contradictory components
        resolved_analysis = dict(analysis)  # Create a copy
        self._apply_resolutions(resolved_analysis, issues)
        
        return {
            'has_contradictions': True,
            'original_analysis': analysis,
            'resolved_analysis': resolved_analysis,
            'confidence_score': confidence_score,
            'review_notes': review_notes,
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_recommendation(self, issue: dict) -> str:
        """Generate specific recommendations for resolving each type of contradiction"""
        recommendations = {
            'sentiment_strategy_mismatch': 'Consider reducing position size or using spreads to manage risk',
            'overlapping_levels': 'Validate levels with additional technical indicators',
            'aggressive_volatility_mismatch': 'Consider reducing position size or using options spreads',
            'technical_institutional_mismatch': 'Monitor for potential trend reversal or institutional positioning change'
        }
        return recommendations.get(issue['type'], 'Review and validate analysis components')
    
    def _apply_resolutions(self, analysis: dict, issues: list) -> None:
        """Apply automated resolutions to the analysis based on identified issues"""
        for issue in issues:
            if issue['type'] == 'sentiment_strategy_mismatch':
                # Adjust strategy size or add hedging component
                strategies = analysis.get('trading_opportunities', {}).get('strategies', [])
                for strategy in strategies:
                    if strategy.get('size', '') == 'large':
                        strategy['size'] = 'moderate'
                        strategy['rationale'] += ' (size adjusted due to sentiment mismatch)'
            
            elif issue['type'] == 'aggressive_volatility_mismatch':
                # Add risk warnings and adjust position sizes
                if 'risk_factors' not in analysis:
                    analysis['risk_factors'] = []
                analysis['risk_factors'].append({
                    'type': 'volatility_warning',
                    'severity': 'high',
                    'description': 'High volatility environment requires careful position sizing'
                })

class ManagerLLMReview:
    """Manager LLM that reviews and validates analysis results"""
    
    def __init__(self):
        self.validator = AnalysisValidator()
    
    def review_analysis(self, analysis_result: dict) -> dict:
        """
        Review analysis for contradictions and provide enhanced insights
        
        Args:
            analysis_result: Original analysis dictionary
            
        Returns:
            Dictionary containing original analysis, contradictions found,
            resolved analysis, confidence score, and review notes
        """
        try:
            # Validate analysis for contradictions
            validation_result = self.validator.validate(analysis_result)
            
            # If no contradictions found, return original with high confidence
            if not validation_result['has_contradictions']:
                return {
                    'status': 'validated',
                    'confidence_score': 1.0,
                    'analysis': analysis_result,
                    'review_notes': ['No contradictions found in analysis']
                }
            
            # Return validation results with resolved analysis
            return {
                'status': 'resolved',
                'confidence_score': validation_result['confidence_score'],
                'original_analysis': validation_result['original_analysis'],
                'resolved_analysis': validation_result['resolved_analysis'],
                'review_notes': validation_result['review_notes'],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in manager review: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'analysis': analysis_result,
                'confidence_score': 0.5,  # Default to medium confidence on error
                'review_notes': [f'Error during review: {str(e)}']
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
    
    return review_result

if __name__ == "__main__":
    test_manager_review() 