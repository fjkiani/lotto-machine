import os
import base64
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from enum import Enum
from pydantic import BaseModel
from typing import Tuple, Dict, List, Union, Any
import json


class ModelProvider(str, Enum):
    """Enum for supported LLM providers"""
    OPENAI = "OpenAI"
    GROQ = "Groq"
    ANTHROPIC = "Anthropic"
    GEMINI = "Gemini"  # Added Gemini provider


class LLMModel(BaseModel):
    """Represents an LLM model configuration"""
    display_name: str
    model_name: str
    provider: ModelProvider

    def to_choice_tuple(self) -> Tuple[str, str, str]:
        """Convert to format needed for questionary choices"""
        return (self.display_name, self.model_name, self.provider.value)
    
    def is_deepseek(self) -> bool:
        """Check if the model is a DeepSeek model"""
        return self.model_name.startswith("deepseek")
    
    def is_gemini(self) -> bool:
        """Check if the model is a Gemini model"""
        return self.model_name.startswith("gemini")


# Define available models
AVAILABLE_MODELS = [
    LLMModel(
        display_name="[anthropic] claude-3.5-haiku",
        model_name="claude-3-5-haiku-latest",
        provider=ModelProvider.ANTHROPIC
    ),
    LLMModel(
        display_name="[anthropic] claude-3.5-sonnet",
        model_name="claude-3-5-sonnet-latest",
        provider=ModelProvider.ANTHROPIC
    ),
    LLMModel(
        display_name="[anthropic] claude-3.7-sonnet",
        model_name="claude-3-7-sonnet-latest",
        provider=ModelProvider.ANTHROPIC
    ),
    LLMModel(
        display_name="[groq] deepseek-r1 70b",
        model_name="deepseek-r1-distill-llama-70b",
        provider=ModelProvider.GROQ
    ),
    LLMModel(
        display_name="[groq] llama-3.3 70b",
        model_name="llama-3.3-70b-versatile",
        provider=ModelProvider.GROQ
    ),
    LLMModel(
        display_name="[openai] gpt-4o",
        model_name="gpt-4o",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="[openai] gpt-4o-mini",
        model_name="gpt-4o-mini",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="[openai] o1",
        model_name="o1",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="[openai] o3-mini",
        model_name="o3-mini",
        provider=ModelProvider.OPENAI
    ),
    # Add Gemini models
    LLMModel(
        display_name="[gemini] gemini-1.5-flash",
        model_name="gemini-1.5-flash",
        provider=ModelProvider.GEMINI
    ),
    LLMModel(
        display_name="[gemini] gemini-1.5-pro",
        model_name="gemini-1.5-pro",
        provider=ModelProvider.GEMINI
    ),
    LLMModel(
        display_name="[gemini] gemini-2.0-flash-thinking",
        model_name="gemini-2.0-flash-thinking-exp-01-21",
        provider=ModelProvider.GEMINI
    ),
]

# Create LLM_ORDER in the format expected by the UI
LLM_ORDER = [model.to_choice_tuple() for model in AVAILABLE_MODELS]

def get_model_info(model_name: str) -> LLMModel | None:
    """Get model information by model_name"""
    return next((model for model in AVAILABLE_MODELS if model.model_name == model_name), None)

def get_model(model_name: str, model_provider: ModelProvider) -> ChatOpenAI | ChatGroq | ChatAnthropic | ChatGoogleGenerativeAI | None:
    if model_provider == ModelProvider.GROQ:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            # Print error to console
            print(f"API Key Error: Please make sure GROQ_API_KEY is set in your .env file.")
            raise ValueError("Groq API key not found.  Please make sure GROQ_API_KEY is set in your .env file.")
        return ChatGroq(model=model_name, api_key=api_key)
    
    elif model_provider == ModelProvider.OPENAI:
        # Get and validate API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Print error to console
            print(f"API Key Error: Please make sure OPENAI_API_KEY is set in your .env file.")
            raise ValueError("OpenAI API key not found.  Please make sure OPENAI_API_KEY is set in your .env file.")
        return ChatOpenAI(model=model_name, api_key=api_key)
    
    elif model_provider == ModelProvider.ANTHROPIC:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print(f"API Key Error: Please make sure ANTHROPIC_API_KEY is set in your .env file.")
            raise ValueError("Anthropic API key not found.  Please make sure ANTHROPIC_API_KEY is set in your .env file.")
        return ChatAnthropic(model=model_name, api_key=api_key)
    
    elif model_provider == ModelProvider.GEMINI:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print(f"API Key Error: Please make sure GEMINI_API_KEY is set in your .env file.")
            raise ValueError("Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.")
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)
    
    return None


# Function to use Gemini for options analysis
def analyze_options_with_gemini(ticker: str, option_chain_data: dict, risk_tolerance: str = "medium"):
    """
    Use Gemini to analyze options data and recommend strategies
    
    Args:
        ticker: Stock ticker symbol
        option_chain_data: Option chain data in dictionary format
        risk_tolerance: Risk tolerance level (low, medium, high)
        
    Returns:
        Dictionary with analysis results
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.")
    
    try:
        import google.generativeai as genai
        from google.generativeai import GenerationConfig
    except ImportError:
        raise ImportError("Google Generative AI package not installed. Please install with: pip install google-generativeai")
    
    # Initialize Gemini client
    genai.configure(api_key=api_key)
    
    # Prepare prompt with options data
    prompt = """
    Analyze the following options data for {ticker} and recommend an optimal options trading strategy 
    based on a {risk_tolerance} risk tolerance level.
    
    Option Chain Data:
    {option_chain_data}
    
    Please provide:
    1. An analysis of current market conditions based on the options data
    2. Evaluation of whether the market is overbought or oversold
    3. Calculation of key Greeks for at-the-money options
    4. Recommended options strategy with specific strikes and expiration
    5. Maximum profit and loss potential for the recommended strategy
    6. Overall market sentiment (bullish, bearish, or neutral)
    
    Format your response as a JSON object with the following structure:
    {{
        "market_conditions": {{
            "put_call_ratio": float,
            "implied_volatility_skew": float,
            "sentiment": "bullish|bearish|neutral",
            "market_condition": "overbought|oversold|normal"
        }},
        "greeks": {{
            "call_delta": float,
            "call_gamma": float,
            "call_theta": float,
            "call_vega": float,
            "put_delta": float,
            "put_gamma": float,
            "put_theta": float,
            "put_vega": float
        }},
        "recommended_strategy": {{
            "name": string,
            "description": string,
            "legs": [
                {{"type": "buy|sell", "option_type": "call|put", "strike": float, "expiration": string}}
            ],
            "max_profit": string,
            "max_loss": string
        }},
        "overall_sentiment": "bullish|bearish|neutral",
        "confidence": float,
        "reasoning": string
    }}
    """.format(
        ticker=ticker,
        risk_tolerance=risk_tolerance,
        option_chain_data=option_chain_data
    )
    
    # Configure Gemini model
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",  # Using a more widely available model
        generation_config=GenerationConfig(
            temperature=0.2,
            top_p=0.95,
            top_k=64,
            max_output_tokens=8192,
        )
    )
    
    # Generate response
    response = model.generate_content(prompt)
    
    # Parse and return the JSON response
    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        # If response is not valid JSON, return a simplified response
        return {
            "error": "Failed to parse Gemini response",
            "raw_response": response.text,
            "overall_sentiment": "neutral",
            "confidence": 0,
            "reasoning": "Error in analysis"
        }


# Function to analyze market quotes with Gemini
def analyze_market_quotes_with_gemini(quotes: Dict[str, 'MarketQuote'], analysis_type: str = "comprehensive") -> str:
    """
    Use Gemini to analyze market quotes data and provide insights
    
    Args:
        quotes: Dictionary of ticker symbols to MarketQuote objects
        analysis_type: Type of analysis to perform (basic, technical, fundamental, comprehensive)
        
    Returns:
        Raw response string from Gemini
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.")
    
    try:
        import google.generativeai as genai
        from google.generativeai import GenerationConfig
    except ImportError:
        raise ImportError("Google Generative AI package not installed. Please install with: pip install google-generativeai")
    
    # Initialize Gemini client
    genai.configure(api_key=api_key)
    
    # Prepare simplified quotes data for Gemini
    simplified_quotes = {}
    for ticker, quote in quotes.items():
        simplified_quotes[ticker] = {
            "price": quote.regular_market_price,
            "previous_close": quote.regular_market_previous_close,
            "open": quote.regular_market_open,
            "high": quote.regular_market_day_high,
            "low": quote.regular_market_day_low,
            "volume": quote.regular_market_volume,
            "avg_volume": quote.average_volume,
            "market_cap": quote.market_cap,
            "pe_ratio": quote.trailing_pe,
            "dividend_yield": quote.get_dividend_yield(),
            "52w_high": quote.fifty_two_week_high,
            "52w_low": quote.fifty_two_week_low,
            "50d_avg": quote.fifty_day_average,
            "200d_avg": quote.two_hundred_day_average,
            "day_change_pct": quote.get_day_change_percent(),
            "market_state": quote.market_state,
            "exchange": quote.exchange_name
        }
    
    # Set analysis instructions based on type
    if analysis_type == "basic":
        analysis_instructions = """
        Please provide a basic analysis including:
        1. Overall market sentiment
        2. Key observations
        3. Simple recommendations
        """
    elif analysis_type == "technical":
        analysis_instructions = """
        Please provide a technical analysis including:
        1. Price trends and patterns
        2. Support and resistance levels
        3. Moving average analysis
        4. Volume analysis
        5. Overbought/oversold conditions
        6. Technical indicators (moving average crossovers, etc.)
        7. Technical-based recommendations
        """
    elif analysis_type == "fundamental":
        analysis_instructions = """
        Please provide a fundamental analysis including:
        1. Valuation metrics (P/E ratios, etc.)
        2. Dividend analysis
        3. Sector comparison
        4. Value-based recommendations
        5. Long-term outlook
        """
    else:  # comprehensive
        analysis_instructions = """
        Please provide a comprehensive analysis including:
        1. Overall market sentiment and conditions
        2. Technical analysis (trends, support/resistance, moving averages)
        3. Fundamental analysis (valuations, dividends)
        4. Volume analysis and unusual activity
        5. Relative performance between tickers
        6. Sector-specific insights
        7. Short-term and long-term outlook
        8. Trading recommendations with rationale
        """
    
    prompt = f"""
    Analyze the following market quotes data and provide insights.
    
    Market Quotes Data:
    {simplified_quotes}
    
    {analysis_instructions}
    
    Format your response as a JSON object with the following structure:
    {{
        "market_overview": {{
            "sentiment": "bullish|bearish|neutral",
            "key_observations": [string],
            "market_condition": "overbought|oversold|normal"
        }},
        "ticker_analysis": {{
            "TICKER1": {{
                "sentiment": "bullish|bearish|neutral",
                "technical_signals": [string],
                "fundamental_metrics": [string],
                "strength": "strong|moderate|weak",
                "recommendation": "buy|sell|hold",
                "price_target": {{
                    "short_term": float,
                    "long_term": float
                }},
                "risk_level": "low|medium|high",
                "key_insights": [string]
            }},
            // Repeat for each ticker
        }},
        "relative_comparison": [
            {{
                "strongest": "TICKER",
                "reason": string
            }},
            {{
                "weakest": "TICKER",
                "reason": string
            }}
        ],
        "trading_opportunities": [
            {{
                "ticker": "TICKER",
                "strategy": string,
                "rationale": string,
                "time_horizon": "short|medium|long",
                "risk_reward_ratio": string
            }}
        ],
        "overall_recommendation": string
    }}
    """
    
    # Configure Gemini model
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=GenerationConfig(
            temperature=0.2,
            top_p=0.95,
            top_k=64,
            max_output_tokens=8192,
        )
    )
    
    # Generate response
    response = model.generate_content(prompt)
    
    # Return the raw text response
    return response.text


def deep_reasoning_analysis(market_data: Dict, analysis_result: Dict) -> str:
    """
    Use Gemini 2.0 Flash Thinking model to perform deep reasoning on market data and analysis
    
    Args:
        market_data: Dictionary of market data
        analysis_result: Dictionary of initial analysis results
        
    Returns:
        String with deep reasoning analysis
    """
    try:
        import os
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError("Google Generative AI package not installed. Please install with: pip install google-generativeai")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.")
    
    # Initialize Gemini client
    client = genai.Client(api_key=api_key)
    
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
    
    # Configure the model
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=genai.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
            top_k=64,
            max_output_tokens=65536,
            response_mime_type="text/plain",
        )
    )
    
    # Generate the response
    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),],
        config=genai.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
            top_k=64,
            max_output_tokens=65536,
            response_mime_type="text/plain",
        ),
    )
    
    return response.text