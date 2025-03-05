import json
import logging
import re
from typing import Dict, List, Any, Tuple
import google.generativeai as genai
import os

logger = logging.getLogger(__name__)

def detect_contradictions(initial_analysis: Dict, deep_analysis: str) -> Dict:
    """
    Detect contradictions between initial analysis and deep reasoning analysis
    
    Args:
        initial_analysis: Dictionary containing the initial market analysis
        deep_analysis: String containing the deep reasoning analysis
        
    Returns:
        Dictionary with detected contradictions and their resolution
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.")
    
    # Initialize Gemini
    genai.configure(api_key=api_key)
    
    # Prepare the prompt to detect contradictions
    prompt = f"""
    I need you to analyze two market analyses and identify any contradictions or significant differences between them.
    
    Initial Analysis:
    {json.dumps(initial_analysis, indent=2)}
    
    Deep Reasoning Analysis:
    {deep_analysis}
    
    Please identify any contradictions or significant differences between these analyses in the following areas:
    1. Market sentiment (bullish/bearish/neutral)
    2. Technical indicators and their interpretation
    3. Risk assessment
    4. Trading recommendations
    5. Price targets
    
    For each contradiction, provide:
    1. The specific contradiction
    2. Which analysis is likely more accurate based on the data provided
    3. Why one analysis might be more reliable than the other
    
    Return your response as a JSON object with the following structure:
    {{
        "contradictions": [
            {{
                "area": "area where contradiction exists",
                "initial_analysis": "what the initial analysis claimed",
                "deep_analysis": "what the deep analysis claimed",
                "resolution": "which is more likely correct and why",
                "confidence": 0.0 to 1.0
            }}
        ],
        "overall_assessment": "overall assessment of which analysis is more reliable"
    }}
    """
    
    # Try to use the experimental model first
    try:
        model_name = "gemini-2.0-flash-thinking-exp-01-21"
        print(f"Attempting to use experimental model for contradiction detection: {model_name}")
        model = genai.GenerativeModel(model_name)
        
        # Set generation config for deep reasoning
        generation_config = {
            "temperature": 0.2,  # Lower temperature for more precise analysis
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
        }
        
        # Generate the response
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        print("Successfully used experimental model for contradiction detection")
        
    except Exception as e:
        print(f"Error using experimental model: {str(e)}")
        print("Falling back to standard Gemini model")
        
        # Fall back to the standard model
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
    
    # Parse the response
    try:
        # Extract JSON from the response text
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            contradictions = json.loads(json_match.group(0))
        else:
            logger.warning("Could not extract JSON from response")
            contradictions = {"contradictions": [], "overall_assessment": "Could not detect contradictions"}
    except Exception as e:
        logger.error(f"Error parsing contradictions: {str(e)}")
        contradictions = {"contradictions": [], "overall_assessment": f"Error: {str(e)}"}
    
    return contradictions

def update_analysis_with_feedback(initial_analysis: Dict, contradictions: Dict) -> Dict:
    """
    Update the initial analysis based on feedback from contradiction detection
    
    Args:
        initial_analysis: Dictionary containing the initial market analysis
        contradictions: Dictionary with detected contradictions and their resolution
        
    Returns:
        Updated analysis dictionary
    """
    # Create a copy of the initial analysis to avoid modifying the original
    updated_analysis = json.loads(json.dumps(initial_analysis))
    
    # Track changes made
    changes_made = []
    
    # Process each contradiction
    for contradiction in contradictions.get("contradictions", []):
        area = contradiction.get("area", "")
        resolution = contradiction.get("resolution", "")
        confidence = contradiction.get("confidence", 0.0)
        
        # Only apply changes with reasonable confidence
        if confidence < 0.7:
            logger.info(f"Skipping contradiction in {area} due to low confidence: {confidence}")
            continue
        
        # Apply changes based on the area of contradiction
        if "sentiment" in area.lower():
            if "market_overview" in updated_analysis and "sentiment" in updated_analysis["market_overview"]:
                old_value = updated_analysis["market_overview"]["sentiment"]
                # Extract the sentiment from the resolution
                if "bullish" in resolution.lower():
                    updated_analysis["market_overview"]["sentiment"] = "bullish"
                elif "bearish" in resolution.lower():
                    updated_analysis["market_overview"]["sentiment"] = "bearish"
                elif "neutral" in resolution.lower():
                    updated_analysis["market_overview"]["sentiment"] = "neutral"
                
                changes_made.append(f"Updated sentiment from '{old_value}' to '{updated_analysis['market_overview']['sentiment']}'")
        
        elif "risk" in area.lower():
            # Update risk assessment in ticker analysis
            for ticker, analysis in updated_analysis.get("ticker_analysis", {}).items():
                if "risk_level" in analysis:
                    old_value = analysis["risk_level"]
                    # Extract risk level from resolution
                    if "high" in resolution.lower():
                        analysis["risk_level"] = "high"
                    elif "medium" in resolution.lower():
                        analysis["risk_level"] = "medium"
                    elif "low" in resolution.lower():
                        analysis["risk_level"] = "low"
                    
                    changes_made.append(f"Updated risk level for {ticker} from '{old_value}' to '{analysis['risk_level']}'")
        
        elif "recommendation" in area.lower() or "trading" in area.lower():
            # Update recommendations
            for ticker, analysis in updated_analysis.get("ticker_analysis", {}).items():
                if "recommendation" in analysis:
                    old_value = analysis["recommendation"]
                    # Extract recommendation from resolution
                    if "buy" in resolution.lower():
                        analysis["recommendation"] = "buy"
                    elif "sell" in resolution.lower():
                        analysis["recommendation"] = "sell"
                    elif "hold" in resolution.lower():
                        analysis["recommendation"] = "hold"
                    
                    changes_made.append(f"Updated recommendation for {ticker} from '{old_value}' to '{analysis['recommendation']}'")
        
        elif "price" in area.lower() and "target" in area.lower():
            # Update price targets
            for ticker, analysis in updated_analysis.get("ticker_analysis", {}).items():
                if "price_target" in analysis:
                    # This is more complex as we need to extract numerical values
                    # For now, we'll just add a note about the contradiction
                    analysis["price_target"]["note"] = f"Contradiction detected: {contradiction.get('deep_analysis', '')}"
                    changes_made.append(f"Added note to price target for {ticker}")
    
    # Add a section for feedback
    updated_analysis["feedback"] = {
        "contradictions_detected": len(contradictions.get("contradictions", [])),
        "changes_made": changes_made,
        "overall_assessment": contradictions.get("overall_assessment", "No assessment provided")
    }
    
    return updated_analysis

def generate_learning_points(initial_analysis: Dict, deep_analysis: str, contradictions: Dict) -> List[str]:
    """
    Generate learning points for improving future analyses based on contradictions
    
    Args:
        initial_analysis: Dictionary containing the initial market analysis
        deep_analysis: String containing the deep reasoning analysis
        contradictions: Dictionary with detected contradictions and their resolution
        
    Returns:
        List of learning points
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.")
    
    # Initialize Gemini
    genai.configure(api_key=api_key)
    
    # Prepare the prompt to generate learning points
    prompt = f"""
    I need you to analyze the differences between an initial market analysis and a deep reasoning analysis,
    and generate learning points to improve future analyses.
    
    Initial Analysis:
    {json.dumps(initial_analysis, indent=2)}
    
    Deep Reasoning Analysis:
    {deep_analysis}
    
    Contradictions Detected:
    {json.dumps(contradictions, indent=2)}
    
    Please generate specific, actionable learning points that could improve future initial analyses.
    Focus on:
    1. What technical indicators were missing from the initial analysis
    2. What risk factors were overlooked
    3. How the interpretation of data could be improved
    4. What additional data sources might be valuable
    5. How to make more nuanced trading recommendations
    
    Return your response as a list of specific, actionable learning points.
    """
    
    # Try to use the experimental model first
    try:
        model_name = "gemini-2.0-flash-thinking-exp-01-21"
        print(f"Attempting to use experimental model for learning points: {model_name}")
        model = genai.GenerativeModel(model_name)
        
        # Set generation config for deep reasoning
        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
        }
        
        # Generate the response
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        print("Successfully used experimental model for learning points")
        
    except Exception as e:
        print(f"Error using experimental model: {str(e)}")
        print("Falling back to standard Gemini model")
        
        # Fall back to the standard model
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
    
    # Parse the response to extract learning points
    learning_points = []
    
    # Split the response by lines and look for numbered or bulleted points
    for line in response.text.split('\n'):
        line = line.strip()
        # Check if line starts with a number or bullet point
        if re.match(r'^\d+\.|\*|\-', line):
            # Remove the number/bullet and add to learning points
            clean_line = re.sub(r'^\d+\.|\*|\-\s*', '', line).strip()
            if clean_line:
                learning_points.append(clean_line)
    
    # If no structured points were found, use the whole text
    if not learning_points:
        learning_points = [response.text.strip()]
    
    return learning_points

def implement_feedback_loop(initial_analysis: Dict, deep_analysis: str) -> Tuple[Dict, List[str]]:
    """
    Implement a complete feedback loop between initial analysis and deep reasoning
    
    Args:
        initial_analysis: Dictionary containing the initial market analysis
        deep_analysis: String containing the deep reasoning analysis
        
    Returns:
        Tuple containing updated analysis and learning points
    """
    # Step 1: Detect contradictions
    contradictions = detect_contradictions(initial_analysis, deep_analysis)
    
    # Step 2: Update the analysis based on contradictions
    updated_analysis = update_analysis_with_feedback(initial_analysis, contradictions)
    
    # Step 3: Generate learning points for future analyses
    learning_points = generate_learning_points(initial_analysis, deep_analysis, contradictions)
    
    return updated_analysis, learning_points 