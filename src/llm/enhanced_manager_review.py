import os
import json
import yaml
import logging
import re
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from datetime import datetime
from copy import deepcopy
from pathlib import Path

# Use absolute imports instead of relative imports
try:
    from src.llm.manager_review import ManagerLLMReview
    from src.llm.dynamic_manager_review import DynamicManagerLLMReview
except ImportError:
    # Fallback to relative imports if absolute fails
    try:
        from .manager_review import ManagerLLMReview
        from .dynamic_manager_review import DynamicManagerLLMReview
    except ImportError:
        # If all fails, create a basic implementation
        class ManagerLLMReview:
            def review_analysis(self, analysis):
                return analysis
        
        class DynamicManagerLLMReview(ManagerLLMReview):
            pass
        
        logging.warning("Could not import ManagerLLMReview or DynamicManagerLLMReview, using fallback implementation")

# Setup logging
logger = logging.getLogger(__name__)

class Rule:
    """Configurable rule for contradiction detection"""
    
    def __init__(self, name: str, condition: Union[str, Callable], severity: str = "medium", 
                 description_template: str = "", recommendation_template: str = ""):
        """
        Initialize a rule for contradiction detection
        
        Args:
            name: Name of the rule
            condition: String expression or callable that evaluates the rule
            severity: Severity level (high, medium, low)
            description_template: Template for describing the contradiction
            recommendation_template: Template for recommending a resolution
        """
        self.name = name
        self.condition = condition
        self.severity = severity
        self.description_template = description_template
        self.recommendation_template = recommendation_template
    
    def evaluate(self, analysis: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Evaluate the rule against the analysis
        
        Args:
            analysis: The analysis to evaluate
            context: Additional context for evaluation
            
        Returns:
            Dictionary with evaluation results
        """
        context = context or {}
        combined_context = {**analysis, **context}
        
        try:
            if callable(self.condition):
                # Use function-based condition
                matches = self.condition(analysis, context)
            else:
                # Use string-based condition (evaluated as a Python expression)
                # Not recommended for production use due to security concerns
                matches = eval(self.condition, {"__builtins__": {}}, combined_context)
            
            if matches:
                description = self._format_template(self.description_template, combined_context)
                recommendation = self._format_template(self.recommendation_template, combined_context)
                
                return {
                    "rule_name": self.name,
                    "matched": True,
                    "severity": self.severity,
                    "description": description,
                    "recommendation": recommendation,
                    "components": []  # Components affected by this contradiction
                }
            
            return {"matched": False}
            
        except Exception as e:
            logger.warning(f"Error evaluating rule '{self.name}': {str(e)}")
            return {"matched": False, "error": str(e)}
    
    def _format_template(self, template: str, context: Dict[str, Any]) -> str:
        """Format a template string with the given context"""
        if not template:
            return ""
            
        # Simple template formatting
        for key, value in context.items():
            placeholder = "{" + key + "}"
            if placeholder in template:
                if isinstance(value, dict):
                    # Don't replace dictionary values directly
                    continue
                template = template.replace(placeholder, str(value))
                
        return template

class EnhancedManagerReview(ManagerLLMReview):
    """
    Enhanced Manager LLM Review System with configuration-based rules and automated fixes.
    
    This class extends the base ManagerLLMReview and adds:
    1. Configuration loading from YAML
    2. Dynamic rule application
    3. Automated contradiction resolution
    4. Tracking of changes made to analysis
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize the enhanced manager review system.
        
        Args:
            config_path: Path to the configuration file. If None, uses default location.
        """
        super().__init__()
        self.config_path = config_path or os.path.join(
            Path(__file__).resolve().parent.parent.parent,
            "config/manager_review_config.yaml"
        )
        self.config = self._load_config()
        logger.info(f"Enhanced Manager Review initialized with config from {self.config_path}")

        # Initialize custom rules (added at runtime) first
        self.custom_rules = {}
        
        # Track version for rule changes
        self.rules_version = 1
        
        # Now load rules
        self.rules = self._load_rules()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Config file not found at {self.config_path}, using default configuration")
                return self._get_default_config()
                
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Successfully loaded configuration from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            logger.warning("Using default configuration")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if config file is not found."""
        return {
            "validation_thresholds": {
                "price_overlap_threshold": 0.01,
                "high_volatility_threshold": 0.3,
                "significant_volume_threshold": 1000000
            },
            "confidence_penalties": {
                "high_severity": 0.3,
                "medium_severity": 0.15,
                "low_severity": 0.05
            },
            "rules": {
                "sentiment_strategy": {
                    "conditions": [
                        "analysis['market_state']['overall_sentiment'] == 'bullish' and 'put' in analysis['trading_opportunities'][0]['strategy'].lower()",
                        "analysis['market_state']['overall_sentiment'] == 'bearish' and 'call' in analysis['trading_opportunities'][0]['strategy'].lower()"
                    ],
                    "severity": "high"
                },
                "price_levels": {
                    "conditions": [
                        "abs(analysis['price_levels']['resistance'] - analysis['price_levels']['support']) / analysis['price_levels']['current_price'] < self.config['validation_thresholds']['price_overlap_threshold']"
                    ],
                    "severity": "medium"
                },
                "volatility_risk": {
                    "conditions": [
                        "analysis['volatility_structure']['skew'] == 'high' and analysis['trading_opportunities'][0]['position_size'] == 'large'"
                    ],
                    "severity": "high"
                }
            }
        }
            
    def review_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review the analysis for contradictions and apply automated fixes.
        
        Args:
            analysis: The analysis data to review.
            
        Returns:
            Dict containing the original analysis, contradictions found,
            resolved analysis, confidence score, and review notes.
        """
        try:
            # Always reload rules to capture any custom rules added or removed
            self.rules = self._load_rules()
            
            # Make a deep copy of the original analysis
            resolved_analysis = deepcopy(analysis)
            
            # Find contradictions
            contradictions = self._find_contradictions(analysis)
            
            if contradictions:
                logger.info(f"Found {len(contradictions)} contradictions in analysis")
                
                # Calculate confidence score
                confidence_score = self._calculate_confidence(contradictions)
                
                # Generate review notes
                review_notes = self._generate_review_notes(contradictions)
                
                # Apply automated fixes
                changes_made, resolved_analysis = self._apply_recommendations(
                    resolved_analysis, contradictions)
                
                logger.info(f"Applied {len(changes_made)} automated fixes to resolve contradictions")
                
                # Add metadata about fixes
                if "metadata" not in resolved_analysis:
                    resolved_analysis["metadata"] = {}
                    
                resolved_analysis["metadata"]["review_timestamp"] = datetime.datetime.now().isoformat()
                resolved_analysis["metadata"]["contradictions_found"] = len(contradictions)
                resolved_analysis["metadata"]["changes_applied"] = changes_made
                resolved_analysis["metadata"]["confidence_score"] = confidence_score
                
                return {
                    "original_analysis": analysis,
                    "contradictions_found": contradictions,
                    "resolved_analysis": resolved_analysis,
                    "confidence_score": confidence_score,
                    "review_notes": review_notes,
                    "changes_made": changes_made
                }
            
            logger.info("No contradictions found in analysis")
            return analysis
            
        except Exception as e:
            logger.error(f"Error during enhanced review: {str(e)}")
            # Return original analysis if something goes wrong
            return analysis
    
    def _find_contradictions(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find contradictions in the analysis using rules from config.
        
        Args:
            analysis: The analysis to check for contradictions.
            
        Returns:
            List of contradiction dictionaries.
        """
        contradictions = []
        
        try:
            # Extract common sections for easier rule evaluation
            context = {
                "market_state": analysis.get("market_state", {}),
                "price_levels": analysis.get("price_levels", {}),
                "volatility_structure": analysis.get("volatility_structure", {}),
                "institutional_flows": analysis.get("institutional_flows", {}),
                "trading_opportunities": analysis.get("trading_opportunities", {}),
                "risk_factors": analysis.get("risk_factors", []),
                "technical_signals": analysis.get("technical_signals", {}),
                "thresholds": self.config.get("thresholds", {})
            }
            
            # Apply each rule
            for rule_name, rule in self.rules.items():
                try:
                    # Use the Rule.evaluate method
                    result = rule.evaluate(analysis, context)
                    
                    if result.get("matched", False):
                        contradiction = {
                            "rule": rule_name,
                            "severity": result.get("severity", "medium"),
                            "description": result.get("description") or self._get_contradiction_description(rule_name, analysis),
                            "recommendation": result.get("recommendation") or self._get_recommendation(rule_name, analysis)
                        }
                        contradictions.append(contradiction)
                        logger.info(f"Found contradiction: {rule_name} with severity {result.get('severity')}")
                except Exception as e:
                    logger.warning(f"Error evaluating rule '{rule_name}': {str(e)}")
        
        except Exception as e:
            logger.error(f"Error finding contradictions: {str(e)}")
        
        return contradictions
    
    def _get_contradiction_description(self, rule_name: str, analysis: Dict[str, Any]) -> str:
        """Generate a description for the contradiction based on rule name."""
        if rule_name == "sentiment_strategy":
            sentiment = analysis.get("market_state", {}).get("overall_sentiment", "neutral")
            strategy = analysis.get("trading_opportunities", [{}])[0].get("strategy", "unknown")
            return f"Contradiction between {sentiment} sentiment and {strategy} strategy"
            
        elif rule_name == "price_levels":
            support = analysis.get("price_levels", {}).get("support", 0)
            resistance = analysis.get("price_levels", {}).get("resistance", 0)
            return f"Price levels too close: support at {support} and resistance at {resistance}"
            
        elif rule_name == "volatility_risk":
            skew = analysis.get("volatility_structure", {}).get("skew", "normal")
            position_size = analysis.get("trading_opportunities", [{}])[0].get("position_size", "medium")
            return f"High risk combination: {skew} volatility skew with {position_size} position size"
            
        return f"Contradiction detected in {rule_name}"
    
    def _get_recommendation(self, rule_name: str, analysis: Dict[str, Any]) -> str:
        """Generate a recommendation for fixing the contradiction."""
        if rule_name == "sentiment_strategy":
            sentiment = analysis.get("market_state", {}).get("overall_sentiment", "neutral")
            if sentiment == "bullish":
                return "Adjust strategy to favor calls or consider reducing bearish positioning"
            elif sentiment == "bearish":
                return "Adjust strategy to favor puts or consider reducing bullish positioning"
                
        elif rule_name == "price_levels":
            return "Widen the range between support and resistance levels based on recent volatility"
            
        elif rule_name == "volatility_risk":
            return "Reduce position size recommendation to account for high volatility skew"
            
        return "Review and adjust the conflicting elements manually"
    
    def _calculate_confidence(self, contradictions: List[Dict[str, Any]]) -> float:
        """
        Calculate confidence score based on contradictions found.
        
        Args:
            contradictions: List of contradiction dictionaries.
            
        Returns:
            Confidence score between 0.0 and 1.0.
        """
        # Start with perfect confidence
        confidence = 1.0
        
        # Apply penalties from configuration based on severity
        penalties = self.config.get("confidence_penalties", {
            "high_severity": 0.3,
            "medium_severity": 0.15,
            "low_severity": 0.05
        })
        
        for contradiction in contradictions:
            severity = contradiction.get("severity", "medium")
            penalty = penalties.get(f"{severity}_severity", 0.1)
            confidence -= penalty
            
        # Ensure confidence doesn't go below 0
        return max(0.0, confidence)
    
    def _generate_review_notes(self, contradictions: List[Dict[str, Any]]) -> str:
        """
        Generate human-readable review notes from contradictions.
        
        Args:
            contradictions: List of contradiction dictionaries.
            
        Returns:
            Formatted review notes.
        """
        if not contradictions:
            return "No contradictions found in the analysis."
            
        notes = ["# Analysis Review Notes", ""]
        notes.append(f"Found {len(contradictions)} contradiction(s) in the analysis:")
        
        for i, contradiction in enumerate(contradictions, 1):
            rule = contradiction.get("rule", "unknown")
            severity = contradiction.get("severity", "medium")
            description = contradiction.get("description", "No description available")
            recommendation = contradiction.get("recommendation", "No recommendation available")
            
            notes.append(f"\n## Issue {i}: {rule.replace('_', ' ').title()} ({severity.upper()} severity)")
            notes.append(f"**Description**: {description}")
            notes.append(f"**Recommendation**: {recommendation}")
        
        notes.append("\n## Overall Assessment")
        confidence = self._calculate_confidence(contradictions)
        confidence_level = "High" if confidence >= 0.8 else "Medium" if confidence >= 0.5 else "Low"
        notes.append(f"Analysis confidence: {confidence_level} ({confidence:.2f})")
        
        if confidence < 0.5:
            notes.append("\n**Warning**: This analysis has LOW confidence and should be reviewed carefully before use.")
        
        return "\n".join(notes)
    
    def _apply_recommendations(self, analysis: Dict[str, Any], 
                              contradictions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Apply automated fixes to the analysis based on contradiction findings.
        
        Args:
            analysis: The analysis to modify.
            contradictions: List of contradiction dictionaries.
            
        Returns:
            Tuple of (list of changes made, modified analysis).
        """
        changes_made = []
        
        for contradiction in contradictions:
            rule = contradiction.get("rule", "")
            severity = contradiction.get("severity", "medium")
            
            try:
                # Apply appropriate fix based on rule
                if rule == "sentiment_strategy":
                    change = self._fix_sentiment_strategy_contradiction(analysis)
                    if change:
                        changes_made.append({
                            "rule": rule,
                            "severity": severity,
                            "change": change
                        })
                
                elif rule == "price_levels":
                    change = self._fix_price_levels_contradiction(analysis)
                    if change:
                        changes_made.append({
                            "rule": rule,
                            "severity": severity,
                            "change": change
                        })
                
                elif rule == "volatility_risk":
                    change = self._fix_volatility_risk_contradiction(analysis)
                    if change:
                        changes_made.append({
                            "rule": rule, 
                            "severity": severity,
                            "change": change
                        })
            
            except Exception as e:
                logger.error(f"Error applying fix for rule {rule}: {str(e)}")
        
        return changes_made, analysis
    
    def _fix_sentiment_strategy_contradiction(self, analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fix contradiction between sentiment and strategy."""
        if not analysis.get("market_state") or not analysis.get("trading_opportunities"):
            return None
            
        sentiment = analysis["market_state"].get("overall_sentiment")
        if not sentiment or not analysis["trading_opportunities"]:
            return None
            
        first_opportunity = analysis["trading_opportunities"][0]
        current_strategy = first_opportunity.get("strategy", "")
        
        # Track the original values for reporting changes
        original_strategy = current_strategy
        
        # Align strategy with sentiment
        if sentiment == "bullish" and "put" in current_strategy.lower():
            # Change put-focused strategy to a call-focused one
            if "spread" in current_strategy.lower():
                first_opportunity["strategy"] = "Call Spread"
                first_opportunity["description"] = "Buy calls with strike near resistance level and sell calls at higher strike to reduce cost."
            else:
                first_opportunity["strategy"] = "Long Calls"
                first_opportunity["description"] = "Buy calls with strike near resistance level to capitalize on bullish momentum with defined risk."
                
        elif sentiment == "bearish" and "call" in current_strategy.lower():
            # Change call-focused strategy to a put-focused one
            if "spread" in current_strategy.lower():
                first_opportunity["strategy"] = "Put Spread"
                first_opportunity["description"] = "Buy puts with strike near support level and sell puts at lower strike to reduce cost."
            else:
                first_opportunity["strategy"] = "Long Puts"
                first_opportunity["description"] = "Buy puts with strike near support level to capitalize on bearish momentum with defined risk."
        else:
            # No change needed
            return None
            
        return {
            "component": "trading_opportunities[0].strategy",
            "original": original_strategy,
            "updated": first_opportunity["strategy"]
        }
    
    def _fix_price_levels_contradiction(self, analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fix contradiction in price levels that are too close together."""
        if not analysis.get("price_levels"):
            return None
            
        price_levels = analysis["price_levels"]
        support = price_levels.get("support")
        resistance = price_levels.get("resistance")
        current_price = price_levels.get("current_price")
        
        if not all([support, resistance, current_price]):
            return None
            
        # Check if price levels are too close
        threshold = self.config["validation_thresholds"]["price_overlap_threshold"]
        price_range_pct = abs(resistance - support) / current_price
        
        if price_range_pct < threshold:
            # Track original values
            original_support = support
            original_resistance = resistance
            
            # Widen the range based on current price
            adjustment = current_price * threshold
            
            # Adjust support and resistance to be at least threshold% apart
            analysis["price_levels"]["support"] = current_price * (1 - threshold)
            analysis["price_levels"]["resistance"] = current_price * (1 + threshold)
            
            return {
                "component": "price_levels",
                "original": {"support": original_support, "resistance": original_resistance},
                "updated": {"support": analysis["price_levels"]["support"], 
                           "resistance": analysis["price_levels"]["resistance"]}
            }
            
        return None
    
    def _fix_volatility_risk_contradiction(self, analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fix contradiction between high volatility and large position sizes."""
        if not analysis.get("volatility_structure") or not analysis.get("trading_opportunities"):
            return None
            
        volatility = analysis["volatility_structure"].get("skew")
        if not volatility or not analysis["trading_opportunities"]:
            return None
            
        first_opportunity = analysis["trading_opportunities"][0]
        position_size = first_opportunity.get("position_size")
        
        if volatility == "high" and position_size == "large":
            # Track original value
            original_size = position_size
            
            # Reduce position size recommendation
            first_opportunity["position_size"] = "small"
            first_opportunity["description"] = first_opportunity.get("description", "") + " Using smaller position size due to high volatility."
            
            return {
                "component": "trading_opportunities[0].position_size",
                "original": original_size,
                "updated": "small"
            }
            
        return None

    def _load_rules(self) -> Dict[str, Rule]:
        """
        Load rules from configuration
        
        Returns:
            Dictionary containing rules
        """
        rules = {}
        
        # Load built-in rules if enabled
        if self.config.get("rules", {}).get("use_builtin", True):
            rules.update(self._get_builtin_rules())
        
        # Load custom rules from config if any
        custom_rules = self.config.get("validation", {}).get("rules", {})
        for rule_name, rule_config in custom_rules.items():
            if not rule_config.get("enabled", True):
                continue
                
            conditions = rule_config.get("conditions", [])
            for condition in conditions:
                rules[f"{rule_name}_{condition.get('type', 'condition')}"] = Rule(
                    name=f"{rule_name}_{condition.get('type', 'condition')}",
                    condition=condition.get("check", "False"),
                    severity=condition.get("severity", "medium"),
                    description_template=condition.get("description", f"Rule {rule_name} detected an issue"),
                    recommendation_template=condition.get("recommendation", "")
                )
        
        # Add custom rules from runtime
        rules.update(self.custom_rules)
        
        return rules
    
    def _get_builtin_rules(self) -> Dict[str, Rule]:
        """
        Get built-in rules
        
        Returns:
            Dictionary containing built-in Rule objects
        """
        return {
            "sentiment_strategy_mismatch": Rule(
                name="sentiment_strategy_mismatch",
                condition="market_state.get('overall_sentiment') == 'bullish' and "
                         "any(s.get('direction') == 'put' for s in trading_opportunities.get('strategies', []))",
                severity="high",
                description_template="Bullish sentiment conflicts with put strategy",
                recommendation_template="Consider reducing position size or using spreads to manage risk"
            ),
            "sentiment_strategy_mismatch_bearish": Rule(
                name="sentiment_strategy_mismatch_bearish",
                condition="market_state.get('overall_sentiment') == 'bearish' and "
                         "any(s.get('direction') == 'call' for s in trading_opportunities.get('strategies', []))",
                severity="high",
                description_template="Bearish sentiment conflicts with call strategy",
                recommendation_template="Consider reducing position size or using spreads to manage risk"
            ),
            "volatility_size_mismatch": Rule(
                name="volatility_size_mismatch",
                condition="volatility_structure.get('skew_analysis', {}).get('type') == 'high' and "
                         "any(s.get('size') == 'large' for s in trading_opportunities.get('strategies', []))",
                severity="high",
                description_template="Large position size in high volatility environment",
                recommendation_template="Consider reducing position size or using options spreads"
            ),
            "technical_institutional_mismatch": Rule(
                name="technical_institutional_mismatch",
                condition="technical_signals.get('momentum_bias') == 'bullish' and "
                         "institutional_flows.get('hedging_patterns', {}).get('hedging_type') == 'protective'",
                severity="medium",
                description_template="Bullish technical signals conflict with defensive institutional positioning",
                recommendation_template="Monitor for potential trend reversal or institutional positioning change"
            )
        }
    
    def _load_built_in_rules(self):
        """Load built-in rules from the rules module"""
        # Placeholder for future enhancement to load rules from a module
        pass
    
    def _format_template(self, template: str, context: Dict[str, Any]) -> str:
        """Format a template string with the given context"""
        if not template:
            return ""
            
        # Replace {variable} with context values
        pattern = r'\{([^}]+)\}'
        
        def replace(match):
            key = match.group(1)
            if key in context:
                value = context[key]
                if isinstance(value, (dict, list)):
                    return str(value)
                return str(value)
            return match.group(0)
            
        return re.sub(pattern, replace, template)

    def add_custom_rule(self, rule_id, rule_config):
        """
        Add a custom rule at runtime.
        
        Args:
            rule_id: Unique identifier for the rule
            rule_config: Dictionary containing rule configuration with the following keys:
                - conditions: List of conditions (as strings) that define when the rule applies
                - severity: Severity level (high, medium, low)
                - description: Description template for the contradiction
                - recommendation: Recommendation template for resolving the contradiction
                - fix_method: Optional method name to call for fixing this contradiction
                
        Returns:
            Boolean indicating if the rule was successfully added
        """
        if not isinstance(rule_config, dict):
            logger.error(f"Rule configuration must be a dictionary: {rule_id}")
            return False
            
        # Validate required fields
        required_fields = ['conditions', 'severity', 'description', 'recommendation']
        for field in required_fields:
            if field not in rule_config:
                logger.error(f"Missing required field '{field}' in rule: {rule_id}")
                return False
                
        # Validate severity
        if rule_config['severity'] not in ['high', 'medium', 'low']:
            logger.error(f"Invalid severity level in rule: {rule_id}")
            return False
            
        # Add the rule
        self.custom_rules[rule_id] = rule_config
        
        # Increment rules version
        self.rules_version += 1
        
        logger.info(f"Added custom rule: {rule_id}")
        return True
        
    def remove_custom_rule(self, rule_id):
        """
        Remove a custom rule.
        
        Args:
            rule_id: Identifier of the rule to remove
            
        Returns:
            Boolean indicating if the rule was successfully removed
        """
        if rule_id in self.custom_rules:
            del self.custom_rules[rule_id]
            self.rules_version += 1
            logger.info(f"Removed custom rule: {rule_id}")
            return True
        else:
            logger.warning(f"Rule not found: {rule_id}")
            return False
            
    def list_rules(self):
        """
        List all available rules (both built-in and custom).
        
        Returns:
            Dictionary containing built-in and custom rules
        """
        return {
            "built_in": self.rules,
            "custom": self.custom_rules,
            "version": self.rules_version
        } 