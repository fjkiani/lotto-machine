"""
Dynamic Manager LLM Review module.

This module extends the base ManagerLLMReview with capabilities for
dynamic rule loading and evaluation.
"""

import os
import json
import logging
import google.generativeai as genai
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime
from google.generativeai.types import GenerationConfig
from .manager_review import ManagerLLMReview

logger = logging.getLogger(__name__)

class DynamicManagerLLMReview(ManagerLLMReview):
    """
    Extension of the Manager LLM Review system with dynamic rule capabilities.
    
    This class serves as an intermediate base class for the EnhancedManagerReview,
    providing the foundation for dynamic rules and rule management.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Dynamic Manager LLM Review
        
        Args:
            config_path: Optional path to the configuration file
        """
        super().__init__()
        self.config = self._load_config(config_path)
        self.static_manager = ManagerLLMReview()  # For fallback
        
        # Configure Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("Gemini API key not found. Using static manager review as fallback.")
            self.use_llm = False
        else:
            genai.configure(api_key=api_key)
            self.use_llm = True
        
        self.dynamic_rules = {}
        self.rule_version = 1
    
    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from YAML file
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Configuration dictionary
        """
        import yaml
        
        default_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                          "config/manager_review_config.yaml")
        
        config_path = config_path or default_config_path
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return config
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            return {
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
                "llm": {
                    "providers": [
                        {
                            "name": "gemini",
                            "model": "gemini-1.5-flash",
                            "timeout": 30,
                            "max_retries": 3
                        }
                    ]
                }
            }
    
    def add_rule(self, rule_id: str, rule_config: Dict[str, Any]) -> bool:
        """
        Add a dynamic rule to the review system.
        
        Args:
            rule_id: Unique identifier for the rule
            rule_config: Dictionary containing rule configuration
            
        Returns:
            Boolean indicating if the rule was successfully added
        """
        if not isinstance(rule_config, dict):
            logger.error(f"Rule configuration must be a dictionary: {rule_id}")
            return False
            
        self.dynamic_rules[rule_id] = rule_config
        self.rule_version += 1
        logger.info(f"Added dynamic rule: {rule_id}")
        return True
    
    def remove_rule(self, rule_id: str) -> bool:
        """
        Remove a dynamic rule from the review system.
        
        Args:
            rule_id: Identifier of the rule to remove
            
        Returns:
            Boolean indicating if the rule was successfully removed
        """
        if rule_id in self.dynamic_rules:
            del self.dynamic_rules[rule_id]
            self.rule_version += 1
            logger.info(f"Removed dynamic rule: {rule_id}")
            return True
        else:
            logger.warning(f"Rule not found: {rule_id}")
            return False
    
    def get_rules(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all dynamic rules in the system.
        
        Returns:
            Dictionary of rules with their identifiers
        """
        return {
            "rules": self.dynamic_rules,
            "version": self.rule_version
        }
    
    def evaluate_dynamic_rules(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate all dynamic rules against the analysis.
        
        Args:
            analysis: The analysis to evaluate
            
        Returns:
            List of contradiction dictionaries from dynamic rules
        """
        contradictions = []
        
        # Prepare common context for rule evaluation
        context = self._prepare_context(analysis)
        
        # Evaluate each dynamic rule
        for rule_id, rule_config in self.dynamic_rules.items():
            try:
                # Get rule condition and severity
                condition = rule_config.get("condition", "False")
                severity = rule_config.get("severity", "medium")
                
                # Evaluate the condition
                matches = eval(condition, {"__builtins__": {}}, context)
                
                if matches:
                    # Create a contradiction entry
                    contradictions.append({
                        "type": rule_id,
                        "severity": severity,
                        "description": rule_config.get("description", f"Dynamic rule '{rule_id}' detected an issue"),
                        "recommendation": rule_config.get("recommendation", "Consider reviewing this finding")
                    })
            except Exception as e:
                logger.warning(f"Error evaluating dynamic rule '{rule_id}': {str(e)}")
        
        return contradictions
    
    def _prepare_context(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare context for rule evaluation.
        
        Args:
            analysis: The analysis to prepare context for
            
        Returns:
            Dictionary with context variables for rule evaluation
        """
        # Extract commonly used components for easy access in rules
        context = {
            "analysis": analysis,
            # Add sections as top-level variables for easier rule writing
            "market_state": analysis.get("market_state", {}),
            "price_levels": analysis.get("price_levels", {}),
            "volatility_structure": analysis.get("volatility_structure", {}),
            "institutional_flows": analysis.get("institutional_flows", {}),
            "trading_opportunities": analysis.get("trading_opportunities", {}),
            "risk_factors": analysis.get("risk_factors", []),
            "technical_signals": analysis.get("technical_signals", {})
        }
        
        return context
    
    def review_analysis(self, analysis_result: Dict[str, Any], market_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Review analysis for contradictions and provide enhanced insights using LLM
        
        Args:
            analysis_result: Original analysis dictionary
            market_context: Optional market context for better LLM understanding
            
        Returns:
            Dictionary containing review results
        """
        if not self.use_llm:
            logger.warning("Using static manager review as fallback")
            return self.static_manager.review_analysis(analysis_result)
        
        try:
            # Get LLM validation of the analysis
            validation_result = self._validate_with_llm(analysis_result, market_context)
            
            # If no contradictions found, return original with high confidence
            if not validation_result['has_contradictions']:
                return {
                    'status': 'validated',
                    'confidence_score': validation_result.get('confidence_score', 1.0),
                    'analysis': analysis_result,
                    'review_notes': validation_result.get('review_notes', ['No contradictions found in analysis'])
                }
            
            # Return validation results with resolved analysis
            return {
                'status': 'resolved',
                'confidence_score': validation_result.get('confidence_score', 0.7),
                'original_analysis': analysis_result,
                'resolved_analysis': validation_result.get('resolved_analysis', analysis_result),
                'review_notes': validation_result.get('review_notes', []),
                'llm_recommendations': validation_result.get('recommendations', []),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in dynamic manager review: {str(e)}")
            logger.info("Falling back to static manager review")
            return self.static_manager.review_analysis(analysis_result)
    
    def _validate_with_llm(self, analysis: Dict[str, Any], market_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Use Gemini LLM to validate the analysis for contradictions
        
        Args:
            analysis: The analysis to validate
            market_context: Optional market context
            
        Returns:
            Validation results
        """
        # Prepare the prompt
        prompt_template = self.config.get('llm', {}).get('prompts', {}).get(
            'contradiction_review', 
            """
            Review this financial analysis for contradictions and inconsistencies:
            
            Analysis: {analysis}
            {market_context_section}
            
            Look for the following types of contradictions:
            1. Market sentiment vs strategy alignment (e.g., bullish sentiment with put-focused strategies)
            2. Price level consistency (overlapping support/resistance levels)
            3. Risk/reward ratios (aggressive strategies in high volatility)
            4. Technical vs institutional signal alignment
            5. Trading recommendation consistency
            
            Respond with a JSON object containing:
            {
                "has_contradictions": true/false,
                "confidence_score": 0.0-1.0,
                "contradictions": [
                    {
                        "type": "contradiction type",
                        "severity": "high/medium/low",
                        "description": "detailed description",
                        "components": ["affected component names"]
                    }
                ],
                "review_notes": [
                    {
                        "type": "note type",
                        "severity": "high/medium/low",
                        "description": "detailed description",
                        "recommendation": "suggested resolution"
                    }
                ],
                "recommendations": [
                    "specific recommendation 1",
                    "specific recommendation 2"
                ],
                "resolved_analysis": {
                    // Modified analysis with corrections applied
                }
            }
            
            If no contradictions are found, return a simplified response with "has_contradictions": false
            and a high confidence score.
            """
        )
        
        # Add market context if provided
        market_context_section = ""
        if market_context:
            market_context_section = f"Market Context: {json.dumps(market_context, indent=2)}"
        
        # Format the prompt
        prompt = prompt_template.format(
            analysis=json.dumps(analysis, indent=2),
            market_context_section=market_context_section
        )
        
        # Call Gemini
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=GenerationConfig(
                temperature=0.2,
                top_p=0.95,
                top_k=64,
                max_output_tokens=8192,
                response_mime_type="application/json",
            )
        )
        
        response = model.generate_content(prompt)
        
        try:
            # Parse the response as JSON
            result = json.loads(response.text)
            logger.info("Successfully parsed LLM response as JSON")
            
            # Set default value for confidence score if not present
            if 'confidence_score' not in result and result.get('has_contradictions', False):
                # Calculate confidence based on contradictions
                contradictions = result.get('contradictions', [])
                high_severity = sum(1 for c in contradictions if c.get('severity') == 'high')
                medium_severity = sum(1 for c in contradictions if c.get('severity') == 'medium')
                
                base_confidence = 1.0
                penalties = self.config.get('validation', {}).get('confidence_penalties', {})
                confidence_score = base_confidence - \
                                  (high_severity * penalties.get('high_severity', 0.2)) - \
                                  (medium_severity * penalties.get('medium_severity', 0.1))
                confidence_score = max(0.1, min(1.0, confidence_score))
                
                result['confidence_score'] = confidence_score
            
            # Ensure resolved_analysis is present
            if 'resolved_analysis' not in result and result.get('has_contradictions', False):
                # Create a modified analysis based on the contradictions
                result['resolved_analysis'] = self._apply_recommendations(
                    analysis.copy(), 
                    result.get('contradictions', []),
                    result.get('recommendations', [])
                )
            
            return result
            
        except json.JSONDecodeError:
            logger.warning("Could not parse LLM response as JSON, attempting to extract")
            # Try to extract JSON from the text response
            import re
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    logger.info("Extracted and parsed JSON from LLM response")
                    return result
                except:
                    logger.error("Failed to parse extracted JSON")
            
            # Return a default validation result
            logger.warning("Using default validation result")
            return {
                'has_contradictions': False,
                'confidence_score': 0.5,
                'review_notes': ['Error parsing LLM response'],
                'recommendations': ['Perform manual review']
            }
    
    def _apply_recommendations(self, analysis: Dict, contradictions: List[Dict], recommendations: List[str]) -> Dict:
        """
        Apply recommended changes to the analysis
        
        Args:
            analysis: Original analysis
            contradictions: List of contradiction dictionaries
            recommendations: List of recommendation strings
            
        Returns:
            Modified analysis with changes applied
        """
        # Create a copy to avoid modifying the original
        modified = analysis.copy()
        
        # Apply changes based on contradiction types
        for contradiction in contradictions:
            contradiction_type = contradiction.get('type', '')
            severity = contradiction.get('severity', 'low')
            components = contradiction.get('components', [])
            
            if 'sentiment' in contradiction_type.lower() and 'strategy' in contradiction_type.lower():
                # Adjust strategies based on sentiment mismatch
                if 'trading_opportunities' in modified and 'strategies' in modified['trading_opportunities']:
                    strategies = modified['trading_opportunities']['strategies']
                    for strategy in strategies:
                        if strategy.get('size', '') == 'large' and severity == 'high':
                            # Reduce position size
                            strategy['size'] = 'moderate'
                            strategy['rationale'] = f"{strategy.get('rationale', '')} (size adjusted due to sentiment mismatch)"
                
            elif 'price' in contradiction_type.lower() and ('level' in contradiction_type.lower() or 'target' in contradiction_type.lower()):
                # Add note about price level inconsistency
                if 'price_levels' in modified:
                    if 'notes' not in modified['price_levels']:
                        modified['price_levels']['notes'] = []
                    modified['price_levels']['notes'].append(
                        f"Warning: {contradiction.get('description', 'Price level inconsistency detected')}"
                    )
                    
            elif 'volatility' in contradiction_type.lower() or 'risk' in contradiction_type.lower():
                # Add risk warning
                if 'risk_factors' not in modified:
                    modified['risk_factors'] = []
                modified['risk_factors'].append({
                    'type': 'volatility_warning',
                    'severity': severity,
                    'description': 'High volatility environment requires careful position sizing'
                })
        
        # Add manager review note to the analysis
        if 'metadata' not in modified:
            modified['metadata'] = {}
        modified['metadata']['manager_review'] = {
            'timestamp': datetime.now().isoformat(),
            'contradictions_found': len(contradictions),
            'recommendations_applied': len(recommendations)
        }
        
        return modified 