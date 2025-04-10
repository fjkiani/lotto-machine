
import json
import datetime
from typing import Dict
import google.generativeai as genai
import logging

logger = logging.getLogger(__name__)

def deep_reasoning_analysis(market_data: Dict, analysis_result: Dict) -> Dict:
    """
    Use Gemini model to perform deep reasoning on market data and analysis
    
    Args:
        market_data: Dictionary of market data
        analysis_result: Dictionary of initial analysis results
        
    Returns:
        Dictionary with deep reasoning analysis
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.")
    
    try:
        # Initialize Gemini
        genai.configure(api_key=api_key)
        
        # Prepare the prompt with market data and initial analysis
        prompt = f"""
        I want you to act as a financial analyst with deep expertise in market analysis, technical analysis, 
        and options strategy. I'll provide you with real market data and options chain information for analysis.
        
        Your task is to:
        1. Analyze the options chain data in detail, including volumes, open interest, and implied volatility
        2. Identify patterns in institutional positioning and directional sentiment
        3. Determine key support and resistance levels based on options activity
        4. Analyze the volatility structure (skew, term structure, etc.)
        5. Identify specific trading opportunities based on unusual activity
        6. Assess potential risks and market signals
        7. Provide a detailed narrative explaining your reasoning
        
        Market Data:
        {json.dumps(market_data, indent=2)}
        
        Initial Analysis:
        {json.dumps(analysis_result, indent=2)}
        
        Please provide the response in this JSON format:
        {
            "metadata": {
                "timestamp": "current_timestamp",
                "ticker": "symbol",
                "current_price": 123.45,
                "analysis_version": "2.0"
            },
            "market_state": {
                "overall_sentiment": "bullish/bearish/neutral",
                "institutional_positioning": "position_type",
                "retail_activity": {
                    "sentiment": "sentiment_type",
                    "conviction": "high/medium/low",
                    "reliability": "high/medium/low"
                }
            },
            "price_levels": {
                "support_levels": [
                    {"price": 123.0, "strength": "strong/moderate/weak", "type": "type", "reasoning": "explanation"}
                ],
                "resistance_levels": [
                    {"price": 126.0, "strength": "strong/moderate/weak", "type": "type", "reasoning": "explanation"}
                ]
            },
            "volatility_structure": {
                "skew_analysis": {
                    "type": "high/low/normal",
                    "strength": 0.8,
                    "interpretation": "detailed interpretation"
                }
            },
            "trading_opportunities": {
                "strategies": [
                    {
                        "type": "strategy_type",
                        "direction": "call/put",
                        "size": "large/moderate/small",
                        "confidence": "high/moderate/low",
                        "rationale": "detailed rationale"
                    }
                ]
            },
            "technical_signals": {
                "momentum_bias": "bullish/bearish/neutral",
                "support_zones": [123.0, 120.0],
                "resistance_zones": [126.0, 130.0]
            },
            "institutional_flows": {
                "hedging_patterns": {
                    "hedging_type": "protective/aggressive/neutral",
                    "put_walls": [
                        {"strike": 120.0, "size": 10000}
                    ]
                }
            },
            "detailed_analysis": {
                "market_overview": "overview text",
                "options_insights": "detailed options analysis",
                "volatility_analysis": "volatility structure analysis"
            }
        }
        
        Ensure your analysis is data-driven and based on actual options chain information.
        """
        
        # Configure the model - use gemini-1.5-flash as it's the current model
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Generate the response
        response = model.generate_content(prompt)
        
        # Parse the JSON response
        try:
            # Extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(0))
                logger.info(f"Successfully parsed structured analysis with {len(analysis.keys())} top-level keys")
                return analysis
            else:
                logger.error("Could not extract JSON from response")
                raise ValueError("LLM response did not contain valid JSON")
        except Exception as e:
            logger.error(f"Error parsing JSON from response: {str(e)}")
            raise ValueError(f"Failed to parse LLM response: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error in deep reasoning analysis: {str(e)}")
        raise 
