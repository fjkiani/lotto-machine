import os
import json
from typing import Dict
import google.generativeai as genai

def deep_reasoning_analysis(market_data: Dict, analysis_result: Dict) -> str:
    """
    Use Gemini 2.0 Flash Thinking experimental model for deep reasoning analysis
    
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
    
    # Try to use the experimental deep reasoning model
    try:
        # First try the experimental model
        model_name = "gemini-2.0-flash-thinking-exp-01-21"
        print(f"Attempting to use experimental model: {model_name}")
        model = genai.GenerativeModel(model_name)
        
        # Set generation config for deep reasoning
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 65536,
        }
        
        # Generate the response
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        print("Successfully used experimental deep reasoning model")
        return response.text
        
    except Exception as e:
        print(f"Error using experimental model: {str(e)}")
        print("Falling back to standard Gemini model")
        
        # Fall back to the standard model
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text

if __name__ == "__main__":
    # Example usage
    print("This is an experimental implementation of the deep_reasoning_analysis function.")
    print("It will attempt to use the experimental deep reasoning model if available.")
    print("To use it, import it into your script:")
    print("from deep_reasoning_fix_experimental import deep_reasoning_analysis") 