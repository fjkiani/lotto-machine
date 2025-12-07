import os
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import datetime
import re

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

def query_llm(prompt: str, provider: str = "gemini", image_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Query the LLM using our application's LLM tools
    
    Args:
        prompt: The prompt to send to the LLM
        provider: The LLM provider to use (default: "gemini")
        image_path: Optional path to an image to include in the analysis
        
    Returns:
        Dictionary containing the LLM's response
    """
    try:
        # Use our application's LLM tool
        from deep_reasoning_fix import deep_reasoning_analysis
        
        # Call the LLM with Gemini
        response = deep_reasoning_analysis(prompt, {})
        
        # Try to parse the response as JSON
        try:
            if isinstance(response, str):
                # Find the JSON part of the response
                start = response.find('{')
                end = response.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = response[start:end]
                    return json.loads(json_str)
            elif isinstance(response, dict):
                return response
                
        except json.JSONDecodeError:
            logger.warning("Could not parse LLM response as JSON. Returning raw response.")
            
        # If we couldn't parse JSON, return a formatted dict
        return {
            "market_sentiment": str(response),
            "key_levels": [],
            "volatility_analysis": "",
            "trading_opportunities": [],
            "risk_factors": [],
            "detailed_analysis": str(response)
        }
        
    except Exception as e:
        logger.error(f"Error querying LLM: {str(e)}")
        raise

def analyze_options_chain(ticker: str, market_data: Dict, analysis: Dict) -> Dict[str, Any]:
    """
    Perform deep reasoning analysis on options chain data
    
    Args:
        ticker: Stock ticker symbol
        market_data: Dictionary containing market data
        analysis: Dictionary containing options chain analysis
        
    Returns:
        Dictionary containing structured LLM analysis results and detailed narrative
    """
    try:
        from deep_reasoning_fix import deep_reasoning_analysis
        
        # Create context for analysis
        context = {
            "market_data": market_data,
            "options_analysis": analysis,
            "ticker": ticker
        }
        
        # Convert any non-serializable values to serializable format
        def make_json_serializable(obj):
            if isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_json_serializable(i) for i in obj]
            elif isinstance(obj, (bool, int, float, str, type(None))):
                return obj
            else:
                return str(obj)
        
        # Make sure the context is JSON serializable
        json_safe_context = make_json_serializable(context)
        json_safe_analysis = make_json_serializable(analysis)
        
        # Get deep reasoning analysis
        analysis_results = deep_reasoning_analysis(json_safe_context, json_safe_analysis)
        
        # Check if the response is already a dictionary
        if isinstance(analysis_results, dict):
            logger.info("LLM returned structured analysis directly")
            # Ensure the result is JSON serializable
            return make_json_serializable(analysis_results)
            
        # If it's a string, try to parse it
        if isinstance(analysis_results, str):
            logger.info("Parsing LLM response as JSON")
            try:
                # Try to find and extract JSON from the response
                json_match = re.search(r'\{.*\}', analysis_results, re.DOTALL)
                if json_match:
                    parsed_analysis = json.loads(json_match.group(0))
                    if isinstance(parsed_analysis, dict):
                        return make_json_serializable(parsed_analysis)
            except Exception as e:
                logger.warning(f"Could not parse LLM response as JSON: {str(e)}")
        
        # If we couldn't parse structured data, use the response to inform our structure
        logger.info("Converting LLM response to structured format")
        
        # Use the raw response to inform our structure
        # This is a fallback template that we'll fill in with information from the response
        structured_response = {
            "market_sentiment": {
                "short_term": "neutral",
                "long_term": "neutral",
                "key_indicators": []
            },
            "key_levels": [],
            "volatility_analysis": {
                "skew_pattern": "unknown",
                "interpretation": "",
                "notable_features": []
            },
            "institutional_activity": {
                "patterns": [],
                "significant_strikes": []
            },
            "trading_opportunities": [],
            "risk_factors": [],
            "technical_signals": {
                "support_levels": [],
                "resistance_levels": [],
                "volume_patterns": ""
            },
            "detailed_analysis": {
                "overview": str(analysis_results)
            }
        }
        
        # Attempt to extract key insights from the text
        text = str(analysis_results).lower()
        
        # Basic sentiment extraction
        if "bullish" in text:
            structured_response["market_sentiment"]["short_term"] = "bullish"
        elif "bearish" in text:
            structured_response["market_sentiment"]["short_term"] = "bearish"
            
        # Extract risk factors - look for bullet points or numbered lists
        risk_matches = re.findall(r'risk[s]?:?\s*\n*\s*[-•*]?\s*([^•\n]+)', text, re.IGNORECASE)
        structured_response["risk_factors"] = [r.strip() for r in risk_matches if r.strip()]
        
        # Extract potential trading strategies
        strategy_matches = re.findall(r'(strategy|opportunity|trade):\s*([^\n.]+)', text, re.IGNORECASE)
        for match in strategy_matches:
            strategy_text = match[1].strip()
            structured_response["trading_opportunities"].append({
                "strategy": strategy_text,
                "rationale": "Identified in analysis",
                "risk_reward": "Moderate"
            })
            
        return structured_response
            
    except Exception as e:
        logger.error(f"Error in options chain analysis: {str(e)}")
        raise

def analyze_options_chain_with_review(ticker: str, market_data: Dict, analysis: Dict) -> Dict[str, Any]:
    """
    Perform deep reasoning analysis on options chain data with enhanced manager review
    
    Args:
        ticker: Stock ticker symbol
        market_data: Dictionary containing market data
        analysis: Dictionary containing options chain analysis
        
    Returns:
        Dictionary containing structured LLM analysis results with contradiction checks and review
    """
    try:
        # Get the original analysis
        original_analysis = analyze_options_chain(ticker, market_data, analysis)
        
        # Import the enhanced manager review
        try:
            from src.llm.enhanced_manager_review import EnhancedManagerReview
            enhanced_review_available = True
            enhanced_manager = EnhancedManagerReview()
            logger.info("Enhanced Manager Review loaded successfully")
        except ImportError:
            enhanced_review_available = False
            logger.warning("Enhanced Manager Review not available, using basic analysis")
        
        # If enhanced review is not available, just return the original analysis
        if not enhanced_review_available:
            return original_analysis
            
        # Function to make data JSON serializable
        def make_json_serializable(obj):
            if isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_json_serializable(i) for i in obj]
            elif isinstance(obj, (bool, int, float, str, type(None))):
                return obj
            else:
                return str(obj)
        
        # Create a more structured format for manager review (adapting to the expected format)
        review_structured_analysis = {
            "metadata": {
                "timestamp": datetime.datetime.now().isoformat(),
                "ticker": ticker,
                "current_price": market_data.get("quote", {}).get(ticker, {}).get("regularMarketPrice", 0),
                "analysis_version": "2.0"
            },
            "market_state": {
                "overall_sentiment": original_analysis.get("market_sentiment", {}).get("short_term", "neutral"),
                "institutional_positioning": "protective" if "hedging" in str(original_analysis.get("institutional_activity", {})) else "neutral",
                "retail_activity": {
                    "sentiment": original_analysis.get("market_sentiment", {}).get("short_term", "neutral"),
                    "conviction": "high",
                    "reliability": "moderate"
                }
            },
            "price_levels": {
                "support_levels": [],
                "resistance_levels": []
            },
            "volatility_structure": {
                "skew_analysis": {
                    "type": "high" if "positive" in str(original_analysis.get("volatility_analysis", {}).get("skew_pattern", "")) else "normal",
                    "strength": 0.8,
                    "interpretation": original_analysis.get("volatility_analysis", {}).get("interpretation", "")
                }
            },
            "trading_opportunities": {
                "strategies": []
            },
            "technical_signals": {
                "momentum_bias": original_analysis.get("market_sentiment", {}).get("short_term", "neutral"),
                "support_zones": [],
                "resistance_zones": []
            },
            "institutional_flows": {
                "hedging_patterns": {
                    "hedging_type": "protective",
                    "put_walls": []
                }
            }
        }
        
        # Process key_levels into support/resistance levels
        for level in original_analysis.get("key_levels", []):
            if isinstance(level, dict):
                level_data = {"price": level.get("level", 0), "strength": "moderate", "type": "technical"}
                if "support" in str(level.get("type", "")).lower():
                    review_structured_analysis["price_levels"]["support_levels"].append(level_data)
                else:
                    review_structured_analysis["price_levels"]["resistance_levels"].append(level_data)
        
        # Process technical signals
        support_levels = original_analysis.get("technical_signals", {}).get("support_levels", [])
        resistance_levels = original_analysis.get("technical_signals", {}).get("resistance_levels", [])
        if isinstance(support_levels, list):
            review_structured_analysis["technical_signals"]["support_zones"] = support_levels
        if isinstance(resistance_levels, list):
            review_structured_analysis["technical_signals"]["resistance_zones"] = resistance_levels
        
        # Process trading opportunities
        for opportunity in original_analysis.get("trading_opportunities", []):
            strategy_type = "directional"
            direction = "neutral"
            size = "moderate"
            
            if isinstance(opportunity, dict):
                strategy = opportunity.get("strategy", "").lower()
                
                if "call" in strategy:
                    direction = "call"
                elif "put" in strategy:
                    direction = "put"
                    
                if "bull" in strategy:
                    direction = "call"
                elif "bear" in strategy:
                    direction = "put"
                    
                if "high risk" in str(opportunity.get("risk_reward", "")).lower():
                    size = "large"
                elif "low risk" in str(opportunity.get("risk_reward", "")).lower():
                    size = "small"
                    
                review_structured_analysis["trading_opportunities"]["strategies"].append({
                    "type": strategy_type,
                    "direction": direction,
                    "size": size,
                    "confidence": "moderate",
                    "rationale": opportunity.get("rationale", "Technical analysis")
                })
        
        # Make sure the analysis is JSON serializable
        review_structured_analysis = make_json_serializable(review_structured_analysis)
        
        # Run manager review
        try:
            logger.info("Running enhanced manager review...")
            review_result = enhanced_manager.review_analysis(review_structured_analysis)
            
            if review_result.get('status') == 'resolved':
                # Log the review results
                logger.info(f"Manager review found contradictions with confidence score: {review_result.get('confidence_score', 0):.2f}")
                for note in review_result.get('review_notes', []):
                    logger.info(f"Contradiction: {note.get('type')} - {note.get('description')}")
                
                # Get the resolved analysis
                resolved_analysis = review_result.get('resolved_analysis', review_structured_analysis)
                
                # Add review details to the original analysis without changing its structure
                enhanced_analysis = dict(original_analysis)  # Create a copy of the original
                enhanced_analysis['manager_review'] = {
                    'status': review_result.get('status'),
                    'confidence_score': review_result.get('confidence_score'),
                    'review_notes': review_result.get('review_notes', []),
                    'enhancements_applied': True
                }
                
                # Identify and apply key insights from the resolved analysis to the original structure
                # This preserves the original structure while incorporating review insights
                
                # For example, if there are new risk factors, add them
                if 'risk_factors' in resolved_analysis:
                    original_risks = set(enhanced_analysis.get('risk_factors', []))
                    for risk in resolved_analysis.get('risk_factors', []):
                        risk_desc = risk.get('description', '') if isinstance(risk, dict) else str(risk)
                        if risk_desc and risk_desc not in original_risks:
                            enhanced_analysis.setdefault('risk_factors', []).append(risk_desc)
                
                # Add any warnings to the detailed analysis
                if 'warning' in resolved_analysis.get('market_state', {}):
                    warning = resolved_analysis['market_state']['warning']
                    if 'detailed_analysis' not in enhanced_analysis:
                        enhanced_analysis['detailed_analysis'] = {}
                    enhanced_analysis['detailed_analysis']['manager_warnings'] = warning
                
                # Make sure the result is JSON serializable
                return make_json_serializable(enhanced_analysis)
            else:
                # No contradictions found, return original analysis with validation note
                original_analysis['manager_review'] = {
                    'status': 'validated',
                    'confidence_score': 1.0,
                    'review_notes': ['No contradictions found in analysis']
                }
                return make_json_serializable(original_analysis)
            
        except Exception as e:
            logger.error(f"Error in manager review: {str(e)}")
            # Fall back to returning the original analysis
            original_analysis['manager_review'] = {
                'status': 'error',
                'error': str(e),
                'review_notes': ['Error occurred during manager review']
            }
            return make_json_serializable(original_analysis)
        
    except Exception as e:
        logger.error(f"Error in enhanced options chain analysis: {str(e)}")
        raise 