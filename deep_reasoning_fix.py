import os
import json
from typing import Dict
import google.generativeai as genai

def deep_reasoning_analysis(market_data: Dict, analysis_result: Dict) -> str:
    """
    Use Gemini model to perform deep reasoning on market data and analysis
    
    Args:
        market_data: Dictionary of market data
        analysis_result: Dictionary of initial analysis results
        
    Returns:
        String with deep reasoning analysis
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.")
    
    # Initialize Gemini
    genai.configure(api_key=api_key)
    
    # Prepare the prompt with market data and initial analysis
    prompt = f"""
    I want you to act as a financial analyst with deep expertise in market analysis, technical analysis, 
    and investment strategy. I'll provide you with market data and an initial analysis.
    
    Your task is to:
    1. Critically evaluate the initial analysis
    2. Identify any overlooked patterns or insights
    3. Consider alternative interpretations of the data
    4. Provide a deeper reasoning about market conditions
    5. Suggest more sophisticated trading strategies
    6. Assess potential risks not mentioned in the initial analysis
    7. Consider macroeconomic factors that might impact the securities
    
    Market Data:
    {json.dumps(market_data, indent=2)}
    
    Initial Analysis:
    {json.dumps(analysis_result, indent=2)}
    
    Please provide a comprehensive deep reasoning analysis that goes beyond the initial findings.
    """
    
    # Configure the model - use gemini-1.5-flash as it's the current model
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # Generate the response
    response = model.generate_content(prompt)
    
    return response.text

if __name__ == "__main__":
    # Example usage
    print("This is a fixed implementation of the deep_reasoning_analysis function.")
    print("To use it, import it into your script:")
    print("from deep_reasoning_fix import deep_reasoning_analysis") 