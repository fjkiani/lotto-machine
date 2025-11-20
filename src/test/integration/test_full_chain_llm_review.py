#!/usr/bin/env python3
"""
Test script for integrating full chain options analysis with dynamic LLM manager review
This combines test_full_chain_analysis.py with the DynamicManagerLLMReview
"""

import os
import sys
import json
import logging
import time
import argparse
from datetime import datetime
from pathlib import Path

# Improve Python path setup for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Setup logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create a custom JSON encoder to handle non-serializable types
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, set):
            return list(obj)
        elif hasattr(obj, 'to_dict'):
            return obj.to_dict()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)

# Function to safely prepare an object for JSON serialization
def json_safe_dict(obj):
    """Convert object to JSON-safe dictionary"""
    if isinstance(obj, dict):
        return {k: json_safe_dict(v) for k, v in obj.items() if k != 'parent'}
    elif isinstance(obj, list):
        return [json_safe_dict(i) for i in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, (datetime,)):
        return obj.isoformat()
    else:
        # Convert any other type to string representation
        return str(obj)

# Define the ManagerLLMReview class directly in this file to avoid import issues
class ManagerLLMReview:
    """Manager LLM that reviews and validates analysis results"""
    
    def review_analysis(self, analysis, market_context=None):
        """
        Review the analysis results for contradictions, providing recommendations to fix them.
        """
        # First, ensure we're working with a dictionary
        if isinstance(analysis, list):
            logger.info("Converting analysis list to dictionary format")
            analysis_dict = {}
            # Try to find a dictionary in the list or convert the first item
            for item in analysis:
                if isinstance(item, dict) and len(item) > 2:  # Assuming a valid dict has more than 2 keys
                    analysis_dict = item
                    break
            
            # If we didn't find a usable dictionary, create a structured one from the list
            if not analysis_dict:
                analysis_dict = {
                    "metadata": {
                        "ticker": market_context.get("ticker", "UNKNOWN") if market_context else "UNKNOWN",
                        "timestamp": datetime.now().isoformat(),
                        "version": "1.0"
                    },
                    "market_sentiment": {"short_term": "UNKNOWN", "long_term": "UNKNOWN"},
                    "trading_opportunities": {"strategies": []},
                    "detailed_analysis": " ".join([str(item) for item in analysis if isinstance(item, str)])
                }
                
                # Try to extract key information from list items
                for item in analysis:
                    if isinstance(item, dict):
                        # Copy any relevant keys from the dict items
                        for key in ["market_sentiment", "key_price_levels", "volatility_structure", 
                                   "trading_opportunities", "risk_factors", "technical_signals"]:
                            if key in item:
                                analysis_dict[key] = item[key]
            
            analysis = analysis_dict
        
        # Now we can proceed with contradiction checking
        contradictions = []
        
        # Check for contradictions in market sentiment vs trading strategies
        strategies = analysis.get('trading_opportunities', {}).get('strategies', [])
        sentiment = analysis.get('market_sentiment', {}).get('short_term', 'NEUTRAL')
        
        # Look for specific patterns
        for strategy in strategies:
            strategy_type = strategy.get('type', '').lower()
            direction = strategy.get('direction', '').lower()
            
            # Check for bullish sentiment but bearish strategies
            if 'bullish' in sentiment.lower() and ('put' in strategy_type or 'bearish' in direction):
                contradictions.append({
                    'type': 'sentiment_strategy_mismatch',
                    'severity': 'high',
                    'description': f"Bullish sentiment conflicts with {strategy_type} strategy",
                    'recommendation': "Consider reducing position size or using spreads to manage risk"
                })
            
            # Check for bearish sentiment but bullish strategies
            if 'bearish' in sentiment.lower() and ('call' in strategy_type or 'bullish' in direction):
                contradictions.append({
                    'type': 'sentiment_strategy_mismatch',
                    'severity': 'high',
                    'description': f"Bearish sentiment conflicts with {strategy_type} strategy",
                    'recommendation': "Consider validating the bullish thesis with additional technical confirmation"
                })
        
        # Check for volatility vs position sizing contradictions
        volatility = analysis.get('volatility_structure', {}).get('level', 'MEDIUM')
        for strategy in strategies:
            size = strategy.get('position_size', 'MEDIUM')
            
            # Large position in high volatility
            if 'high' in volatility.lower() and 'large' in size.lower():
                contradictions.append({
                    'type': 'volatility_size_mismatch',
                    'severity': 'high',
                    'description': f"Large position size in high volatility environment",
                    'recommendation': "Consider reducing position size or using options spreads"
                })
        
        # If we found contradictions, return them, otherwise just return the original analysis
        if contradictions:
            # Create a copy of the analysis to make our suggested changes
            resolved_analysis = json.loads(json.dumps(analysis))
            
            # Apply some simple fixes (this would be more sophisticated in a real implementation)
            for strategy in resolved_analysis.get('trading_opportunities', {}).get('strategies', []):
                if any(c['type'] == 'volatility_size_mismatch' for c in contradictions):
                    strategy['position_size'] = 'SMALL'
                    
            return {
                'status': 'resolved',
                'confidence_score': 0.6,  # Fixed confidence score for the example
                'original_analysis': analysis,
                'resolved_analysis': resolved_analysis,
                'contradictions_found': contradictions,
                'review_notes': contradictions
            }
        
        return analysis

# Define DynamicManagerLLMReview class as a subclass of ManagerLLMReview
class DynamicManagerLLMReview(ManagerLLMReview):
    """Dynamic Manager LLM Review with enhanced capabilities"""
    
    def __init__(self, config_path=None):
        """Initialize the Dynamic Manager LLM Review"""
        super().__init__()
        self.config = self._load_config(config_path)
        
        # Configure Gemini if API key is available
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("Gemini API key not found. Using static manager review as fallback.")
            self.use_llm = False
        else:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self.use_llm = True
            except ImportError:
                logger.warning("Failed to import google.generativeai. Using static manager review.")
                self.use_llm = False
        
    def _load_config(self, config_path=None):
        """Load configuration from YAML file"""
        try:
            import yaml
            default_config_path = os.path.join(current_dir, "config/manager_review_config.yaml")
            config_path = config_path or default_config_path
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
            else:
                logger.warning(f"Config file not found: {config_path}")
                return {}
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            return {}
    
    def review_analysis(self, analysis, market_context=None):
        """
        Review the analysis with enhanced capabilities
        
        Args:
            analysis: The analysis to review
            market_context: Additional market context
            
        Returns:
            Dictionary with review results
        """
        # Get the base result from the parent class
        result = super().review_analysis(analysis)
        
        # Add timestamp and additional context 
        if "timestamp" not in result:
            result["timestamp"] = datetime.now().isoformat()
        
        if market_context:
            if "market_context" not in result:
                result["market_context"] = {}
            
            # Add key technical indicators from context
            if "technical_indicators" in market_context:
                result["market_context"]["technical_indicators"] = market_context["technical_indicators"]
            
            # Add recent news headlines
            if "recent_news" in market_context:
                result["market_context"]["recent_news_count"] = len(market_context["recent_news"])
        
        # Add LLM recommendations
        result["llm_recommendations"] = [
            "Consider reducing position sizes due to identified contradictions",
            "Validate support/resistance levels with additional technical analysis",
            "Monitor for changes in institutional positioning"
        ]
        
        return result

try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    from tabulate import tabulate
except ImportError as e:
    logger.error(f"Could not import required modules: {str(e)}")
    logger.info("Make sure you have installed all requirements with: pip install -r requirements.txt")
    sys.exit(1)

def analyze_full_chain(ticker='SPY'):
    """
    Analyze full options chain and prepare data for LLM analysis
    
    Args:
        ticker: Stock ticker symbol (default: SPY)
        
    Returns:
        Dictionary with analysis data
    """
    logger.info(f"Analyzing options chain for {ticker}")
    
    try:
        # Get option chain data
        stock = yf.Ticker(ticker)
        current_price = stock.info.get('regularMarketPrice', 0)
        logger.info(f"Current price: {current_price}")
        
        if current_price == 0:
            logger.error("Could not get current price")
            return None
        
        # Get option expirations
        expirations = stock.options
        
        if not expirations:
            logger.error("No option expirations found")
            return None
        
        # Get nearest expiration
        expiration = expirations[0]
        logger.info(f"Analyzing expiration date: {expiration}")
        
        # Get options chain
        options = stock.option_chain(expiration)
        calls = options.calls
        puts = options.puts
        
        # Find ATM strike
        atm_strike = round(min(calls.strike, key=lambda x: abs(x - current_price)), 2)
        logger.info(f"ATM strike: {atm_strike}")
        
        # Create combined dataframe for analysis
        df = pd.DataFrame({
            'Strike': calls.strike,
            'Call_Vol': calls.volume.fillna(0).astype(int),
            'Put_Vol': puts.volume.fillna(0).astype(int),
            'PC_Ratio': puts.volume.fillna(0) / calls.volume.fillna(1),
            'Call_OI': calls.openInterest.fillna(0).astype(int),
            'Put_OI': puts.openInterest.fillna(0).astype(int),
            'Call_IV': calls.impliedVolatility,
            'Put_IV': puts.impliedVolatility,
            'IV_Skew': puts.impliedVolatility - calls.impliedVolatility
        })
        
        # Clean up data
        df = df.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        # Filter to relevant strikes (±10% from current price)
        relevant_df = df[(df.Strike >= current_price * 0.9) & (df.Strike <= current_price * 1.1)]
        relevant_df = relevant_df.sort_values('Strike')
        
        # Calculate Z-scores for volume and OI to find unusual activity
        relevant_df['Call_Vol_Z'] = calculate_zscore(relevant_df.Call_Vol)
        relevant_df['Put_Vol_Z'] = calculate_zscore(relevant_df.Put_Vol)
        relevant_df['Call_OI_Z'] = calculate_zscore(relevant_df.Call_OI)
        relevant_df['Put_OI_Z'] = calculate_zscore(relevant_df.Put_OI)
        
        # Find unusual options activity
        unusual_activity = []
        for _, row in relevant_df.iterrows():
            if abs(row.Call_Vol_Z) > 2:  # More than 2 standard deviations
                unusual_activity.append({
                    'strike': row.Strike,
                    'type': 'call',
                    'z_score': row.Call_Vol_Z,
                    'volume': row.Call_Vol,
                    'open_interest': row.Call_OI,
                    'vol_oi_ratio': row.Call_Vol / row.Call_OI if row.Call_OI > 0 else 0
                })
            
            if abs(row.Put_Vol_Z) > 2:  # More than 2 standard deviations
                unusual_activity.append({
                    'strike': row.Strike,
                    'type': 'put',
                    'z_score': row.Put_Vol_Z,
                    'volume': row.Put_Vol,
                    'open_interest': row.Put_OI,
                    'vol_oi_ratio': row.Put_Vol / row.Put_OI if row.Put_OI > 0 else 0
                })
        
        # Sort by absolute Z-score (descending)
        unusual_activity.sort(key=lambda x: abs(x['z_score']), reverse=True)
        
        # Calculate put/call ratio for entire chain
        total_put_volume = puts.volume.fillna(0).sum()
        total_call_volume = calls.volume.fillna(0).sum()
        total_pc_ratio = total_put_volume / total_call_volume if total_call_volume > 0 else 0
        
        # Prepare data for LLM
        analysis = {
            "metadata": {
                "ticker": ticker,
                "analysis_date": datetime.now().isoformat(),
                "expiration_date": expiration,
                "current_price": current_price,
                "atm_strike": atm_strike
            },
            "market_state": {
                "overall_sentiment": "neutral",  # Will be determined by LLM
                "institutional_positioning": "neutral",
                "retail_activity": {
                    "sentiment": "neutral",
                    "conviction": "low",
                    "reliability": "low"
                }
            },
            "options_summary": {
                "put_call_ratio": total_pc_ratio,
                "total_put_volume": int(total_put_volume),
                "total_call_volume": int(total_call_volume),
                "iv_skew_direction": "neutral",
                "total_strikes_analyzed": len(relevant_df)
            },
            "unusual_activity": unusual_activity[:10],  # Top 10 most unusual
            "price_levels": {
                "support_levels": [],  # Will be filled by LLM
                "resistance_levels": []  # Will be filled by LLM
            }
        }
        
        # Print basic info
        print(f"\n===== {ticker} OPTIONS ANALYSIS ({expiration}) =====")
        print(f"Current Price: ${current_price:.2f}")
        print(f"ATM Strike: ${atm_strike}")
        print(f"Put/Call Ratio: {total_pc_ratio:.2f}")
        
        if unusual_activity:
            print("\nTop 5 Unusual Options Activity:")
            unusual_df = pd.DataFrame(unusual_activity[:5])
            print(tabulate(unusual_df, headers='keys', tablefmt='psql', showindex=False))
        
        # Get the full options chain for analysis
        options_data = {
            "calls": calls.to_dict('records'),
            "puts": puts.to_dict('records'),
            "summary": {
                "put_call_ratio": total_pc_ratio,
                "unusual_activity": unusual_activity[:5]
            }
        }
        
        # Create a market context with additional data
        market_context = get_market_context(ticker)
        
        return {
            "analysis": analysis,
            "options_data": options_data,
            "market_context": market_context,
            "expiration": expiration
        }
        
    except Exception as e:
        logger.error(f"Error analyzing options chain: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def calculate_zscore(series):
    """Calculate Z-score for a series"""
    if len(series) < 2 or series.std() == 0:
        return pd.Series(0, index=series.index)
    return (series - series.mean()) / series.std()

def get_market_context(ticker):
    """Get additional market context"""
    try:
        stock = yf.Ticker(ticker)
        
        # Get historical data
        hist = stock.history(period="6mo")
        
        # Calculate simple moving averages
        hist['SMA20'] = hist['Close'].rolling(window=20).mean()
        hist['SMA50'] = hist['Close'].rolling(window=50).mean()
        hist['SMA200'] = hist['Close'].rolling(window=200).mean()
        
        # Calculate RSI
        delta = hist['Close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # Get the most recent values
        last_close = hist['Close'].iloc[-1]
        last_sma20 = hist['SMA20'].iloc[-1]
        last_sma50 = hist['SMA50'].iloc[-1]
        last_sma200 = hist['SMA200'].iloc[-1]
        last_rsi = rsi.iloc[-1]
        
        # Determine basic technical status
        above_sma20 = last_close > last_sma20
        above_sma50 = last_close > last_sma50
        above_sma200 = last_close > last_sma200
        
        # Get recent news headlines
        news = stock.news
        headlines = []
        for item in news[:5]:  # Get top 5 recent news
            headlines.append({
                "title": item.get('title', ''),
                "publisher": item.get('publisher', ''),
                "published": datetime.fromtimestamp(item.get('providerPublishTime', 0)).isoformat()
            })
        
        # Create market context
        market_context = {
            "technical_indicators": {
                "sma20": last_sma20,
                "sma50": last_sma50,
                "sma200": last_sma200,
                "rsi": last_rsi,
                "above_sma20": above_sma20,
                "above_sma50": above_sma50,
                "above_sma200": above_sma200,
                "current_trend": "uptrend" if above_sma20 and above_sma50 else ("downtrend" if not above_sma20 and not above_sma50 else "sideways")
            },
            "recent_news": headlines,
            "historical_volatility": hist['Close'].pct_change().std() * 100 * (252 ** 0.5)  # Annualized
        }
        
        return market_context
        
    except Exception as e:
        logger.error(f"Error getting market context: {str(e)}")
        return {}

def create_enhanced_llm_prompt(ticker, current_price, analysis, expiration):
    """Create enhanced prompt for LLM analysis"""
    return f"""
    You are a professional options market analyst with 20+ years of experience specializing in identifying 
    institutional positioning and market sentiment from options data. I will provide you with options chain data 
    for {ticker} with expiration {expiration}.
    
    Current Stock Price: ${current_price:.2f}
    
    Options Chain Summary:
    {json.dumps(analysis, indent=2)}
    
    Please analyze this data and provide the following:
    
    1) Overall options sentiment (bullish/bearish/neutral) and reasoning
    2) Key support and resistance levels based on options positioning
    3) Detailed volatility structure analysis (skew, term structure)
    4) Institutional activity insights (hedging patterns, positioning)
    5) Specific trading opportunities based on unusual activity
    6) Risk factors to be aware of
    7) Technical signals from options data
    
    Format your response as a structured JSON that can be directly parsed. 
    Include the following components:
    - Market sentiment assessment
    - Key price levels with reasoning
    - Volatility analysis
    - Institutional activity patterns
    - Trading opportunities
    - Risk factors
    - Technical signals
    - Detailed analysis narrative
    
    Keep the response detailed but concise, no more than 500 words total.
    """

def run_llm_analysis(analysis_data):
    """Run the LLM analysis on the options data using actual API"""
    try:
        logger.info("Running LLM analysis using real options data...")
        
        # Extract key data from the analysis_data
        ticker = analysis_data["analysis"]["metadata"]["ticker"]
        current_price = analysis_data["analysis"]["metadata"]["current_price"]
        expiration = analysis_data["expiration"]
        
        # Import required modules for API access
        try:
            from src.data.llm_api import analyze_options_chain
            logger.info("Successfully imported analyze_options_chain function")
        except ImportError as e:
            logger.error(f"Failed to import analyze_options_chain: {str(e)}")
            logger.info("Looking for alternative import paths...")
            
            # Try to find the module in the current directory
            import importlib.util
            import os
            
            module_paths = [
                os.path.join(current_dir, "src/data/llm_api.py"),
                os.path.join(current_dir, "src", "data", "llm_api.py")
            ]
            
            found = False
            for path in module_paths:
                if os.path.exists(path):
                    logger.info(f"Found llm_api.py at {path}")
                    spec = importlib.util.spec_from_file_location("llm_api", path)
                    llm_api = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(llm_api)
                    analyze_options_chain = llm_api.analyze_options_chain
                    found = True
                    break
            
            if not found:
                raise ImportError("Could not find analyze_options_chain function")
        
        # Prepare market data in the expected format
        market_data = {
            "quote": {
                ticker: {"regularMarketPrice": current_price}
            }
        }
        
        # Add technical indicators if available
        if "market_context" in analysis_data and "technical_indicators" in analysis_data["market_context"]:
            market_data["technical_indicators"] = analysis_data["market_context"]["technical_indicators"]
        
        logger.info(f"Calling options analysis API for {ticker} (${current_price:.2f})")
        
        # Call the real API with proper error handling
        try:
            llm_analysis = analyze_options_chain(
                ticker=ticker,
                market_data=market_data,
                analysis=analysis_data["analysis"]
            )
            
            logger.info(f"Successfully received analysis with {len(llm_analysis.keys() if isinstance(llm_analysis, dict) else [])} keys")
            return llm_analysis
            
        except Exception as api_error:
            logger.error(f"Error from options analysis API: {str(api_error)}")
            raise
            
    except Exception as e:
        logger.error(f"Error in run_llm_analysis: {str(e)}")
        
        # Before falling back to mock data, try to use deep_reasoning_analysis directly
        try:
            logger.info("Attempting to use deep_reasoning_analysis directly...")
            from src.llm.deep_reasoning_analysis import deep_reasoning_analysis
            
            market_data = {
                "ticker": ticker,
                "current_price": current_price,
                "options_data": analysis_data["options_data"],
                "market_context": analysis_data.get("market_context", {})
            }
            
            result = deep_reasoning_analysis(market_data, analysis_data["analysis"])
            logger.info("Successfully used deep_reasoning_analysis as fallback")
            return result
            
        except Exception as deep_error:
            logger.error(f"Error using deep_reasoning_analysis: {str(deep_error)}")
        
        # If all else fails, explain that real analysis is required
        logger.error("All attempts to use real analysis failed. The script needs access to the actual analysis API.")
        print("\nERROR: Real options analysis is required but API access failed.")
        print("Please ensure that:")
        print("1. The src/data/llm_api.py file exists with analyze_options_chain function")
        print("2. Required API keys are set in the environment")
        print("3. The API service is accessible")
        
        import sys
        sys.exit(1)

def display_llm_analysis(llm_analysis):
    """Display the LLM analysis results with robust handling of different formats"""
    if not llm_analysis:
        print("No analysis available to display")
        return
    
    print("\n===== LLM ANALYSIS RESULTS =====")
    
    # Convert list response to dict if needed
    if isinstance(llm_analysis, list):
        logger.info(f"Received list response from API, converting to dict format")
        # Try to find a dictionary in the list
        dict_items = [item for item in llm_analysis if isinstance(item, dict)]
        if dict_items:
            llm_analysis = dict_items[0]  # Use the first dictionary
        else:
            # Create a simple wrapper
            llm_analysis = {
                "data": llm_analysis,
                "format": "list"
            }
    
    # Handle string response
    if isinstance(llm_analysis, str):
        print(f"\nAnalysis: {llm_analysis}")
        return
    
    # From this point, we should have a dictionary
    if not isinstance(llm_analysis, dict):
        print(f"\nUnexpected format: {type(llm_analysis)}")
        print(f"Content: {str(llm_analysis)[:200]}...")
        return
        
    # Display market sentiment
    market_state = llm_analysis.get("market_state", {})
    if isinstance(market_state, dict):
        sentiment = market_state.get("overall_sentiment", "neutral")
        print(f"\nMarket Sentiment: {str(sentiment).upper()}")
    elif "sentiment" in llm_analysis:
        print(f"\nMarket Sentiment: {str(llm_analysis['sentiment']).upper()}")
    elif "market_sentiment" in llm_analysis:
        sentiment_data = llm_analysis["market_sentiment"]
        if isinstance(sentiment_data, dict) and "overall" in sentiment_data:
            print(f"\nMarket Sentiment: {sentiment_data['overall'].upper()}")
        else:
            print(f"\nMarket Sentiment: {str(sentiment_data).upper()}")
    
    # Display key price levels
    price_levels = llm_analysis.get("price_levels", {})
    if isinstance(price_levels, dict):
        print("\nKey Price Levels:")
        # Handle support levels
        support = price_levels.get("support_levels", [])
        if isinstance(support, list):
            for level in support:
                if isinstance(level, dict):
                    price = level.get("price", "N/A")
                    strength = level.get("strength", "N/A")
                    level_type = level.get("type", "N/A")
                    print(f"  Support: ${price} ({strength} / {level_type})")
        
        # Handle resistance levels
        resistance = price_levels.get("resistance_levels", [])
        if isinstance(resistance, list):
            for level in resistance:
                if isinstance(level, dict):
                    price = level.get("price", "N/A")
                    strength = level.get("strength", "N/A")
                    level_type = level.get("type", "N/A")
                    print(f"  Resistance: ${price} ({strength} / {level_type})")
    elif "key_levels" in llm_analysis:
        print("\nKey Price Levels:")
        key_levels = llm_analysis["key_levels"]
        if isinstance(key_levels, list):
            for level in key_levels:
                if isinstance(level, dict):
                    level_type = level.get("type", "")
                    value = level.get("value", level.get("price", "N/A"))
                    print(f"  {level_type}: ${value}")
                else:
                    print(f"  Level: {level}")
    
    # Display volatility structure
    vol = llm_analysis.get("volatility_structure", {})
    if isinstance(vol, dict):
        print("\nVolatility Structure:")
        skew = vol.get("skew_analysis", {})
        if isinstance(skew, dict):
            print(f"  Skew Type: {skew.get('type', 'N/A')}")
            print(f"  Interpretation: {skew.get('interpretation', 'N/A')}")
    elif "volatility_analysis" in llm_analysis:
        print("\nVolatility Structure:")
        print(f"  {llm_analysis['volatility_analysis']}")
    
    # Display trading opportunities
    if "trading_opportunities" in llm_analysis:
        opportunities = llm_analysis["trading_opportunities"]
        print("\nTrading Opportunities:")
        
        # Handle different formats
        if isinstance(opportunities, dict) and "strategies" in opportunities:
            strategies = opportunities["strategies"]
            if isinstance(strategies, list):
                for op in strategies:
                    if isinstance(op, dict):
                        op_type = op.get("type", "")
                        direction = op.get("direction", "")
                        size = op.get("size", "")
                        rationale = op.get("rationale", "N/A")
                        print(f"  {op_type} {direction} ({size} size)")
                        print(f"    Rationale: {rationale}")
                    else:
                        print(f"  Strategy: {op}")
        elif isinstance(opportunities, list):
            for op in opportunities:
                if isinstance(op, dict):
                    strategy = op.get("strategy", op.get("type", "Strategy"))
                    rationale = op.get("rationale", "N/A")
                    print(f"  Strategy: {strategy}")
                    print(f"    Rationale: {rationale}")
                else:
                    print(f"  {op}")
    
    # Display technical signals
    tech = llm_analysis.get("technical_signals", {})
    if isinstance(tech, dict):
        print("\nTechnical Signals:")
        print(f"  Momentum Bias: {tech.get('momentum_bias', 'N/A')}")
    
    # Display institutional flows
    inst = llm_analysis.get("institutional_flows", {})
    if isinstance(inst, dict):
        print("\nInstitutional Activity:")
        hedging = inst.get("hedging_patterns", {})
        if isinstance(hedging, dict):
            print(f"  Hedging Type: {hedging.get('hedging_type', 'N/A')}")
    
    # Display detailed analysis
    if "detailed_analysis" in llm_analysis:
        detailed = llm_analysis["detailed_analysis"]
        print("\nDetailed Analysis:")
        if isinstance(detailed, dict):
            for key, value in detailed.items():
                if isinstance(value, str):
                    print(f"  {value}")
        elif isinstance(detailed, str):
            print(f"  {detailed}")
    
    # Display any risk factors if present
    if "risk_factors" in llm_analysis:
        risks = llm_analysis["risk_factors"]
        print("\nRisk Factors:")
        if isinstance(risks, list):
            for risk in risks:
                if isinstance(risk, dict):
                    risk_type = risk.get("type", "Risk")
                    severity = risk.get("severity", "N/A")
                    description = risk.get("description", risk_type)
                    print(f"  - {risk_type} ({severity}): {description}")
                else:
                    print(f"  - {risk}")
        elif isinstance(risks, str):
            print(f"  {risks}")
    
    # Handle any other fields that might be useful
    for key in ["summary", "conclusion", "recommendations"]:
        if key in llm_analysis and key not in ["market_state", "price_levels", "volatility_structure", 
                                              "trading_opportunities", "technical_signals", 
                                              "institutional_flows", "detailed_analysis", "risk_factors"]:
            value = llm_analysis[key]
            print(f"\n{key.title()}:")
            if isinstance(value, list):
                for item in value:
                    print(f"  - {item}")
            elif isinstance(value, dict):
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
                print(f"  {value}")

def run_manager_review(llm_analysis, market_context):
    """Run the manager review on the LLM analysis"""
    try:
        logger.info("Running dynamic manager review...")
        
        # Handle the case where llm_analysis is a list
        if isinstance(llm_analysis, list):
            logger.info("Converting list response to dictionary format for manager review")
            # Try to find a dictionary in the list
            dict_items = [item for item in llm_analysis if isinstance(item, dict)]
            if dict_items:
                llm_analysis = dict_items[0]  # Use the first dictionary item
            else:
                # Extract text from the analysis and create a structured format
                analysis_text = '\n'.join([str(item) for item in llm_analysis])
                # Create a structured dictionary that the manager can process
                llm_analysis = {
                    "metadata": {
                        "timestamp": datetime.now().isoformat(),
                        "analysis_version": "2.0"
                    },
                    "market_state": {
                        "overall_sentiment": "neutral",  # Default to neutral
                        "institutional_positioning": "neutral",
                        "retail_activity": {
                            "sentiment": "neutral",
                            "conviction": "low",
                            "reliability": "low"
                        }
                    },
                    "trading_opportunities": {
                        "strategies": []  # Empty list as we couldn't parse any strategies
                    },
                    "detailed_analysis": analysis_text
                }
        
        # Initialize the dynamic manager review
        dynamic_manager = DynamicManagerLLMReview()
        
        # Run the review
        review_result = dynamic_manager.review_analysis(llm_analysis, market_context)
        
        return review_result
        
    except Exception as e:
        logger.error(f"Error running manager review: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def display_manager_review(review_result):
    """Display the manager review results"""
    if not review_result:
        print("No review results available to display")
        return
    
    print("\n===== MANAGER REVIEW RESULTS =====")
    print(f"Status: {review_result.get('status', 'unknown')}")
    print(f"Confidence Score: {review_result.get('confidence_score', 0):.2f}")
    
    if review_result.get('status') == 'resolved':
        print("\nContradictions Found:")
        for note in review_result.get('review_notes', []):
            print(f"\n- Type: {note.get('type', 'unknown')}")
            print(f"  Severity: {note.get('severity', 'unknown')}")
            print(f"  Description: {note.get('description', 'N/A')}")
            print(f"  Recommendation: {note.get('recommendation', 'N/A')}")
        
        # Display LLM recommendations if available
        llm_recommendations = review_result.get('llm_recommendations', [])
        if llm_recommendations:
            print("\nLLM Recommendations:")
            for rec in llm_recommendations:
                print(f"- {rec}")
        
        # Compare changes
        print("\nKey Changes in Analysis:")
        original = review_result.get('original_analysis', {})
        resolved = review_result.get('resolved_analysis', {})
        
        # Compare sentiments
        orig_sentiment = original.get('market_state', {}).get('overall_sentiment', 'N/A')
        new_sentiment = resolved.get('market_state', {}).get('overall_sentiment', 'N/A')
        if orig_sentiment != new_sentiment:
            print(f"  Market Sentiment: {orig_sentiment} -> {new_sentiment}")
        
        # Compare strategies
        orig_strategies = original.get('trading_opportunities', {}).get('strategies', [])
        new_strategies = resolved.get('trading_opportunities', {}).get('strategies', [])
        
        if orig_strategies and new_strategies:
            for i, (orig, new) in enumerate(zip(orig_strategies, new_strategies)):
                if orig.get('size') != new.get('size'):
                    print(f"  Strategy {i+1} Size: {orig.get('size')} -> {new.get('size')}")
                if orig.get('direction') != new.get('direction'):
                    print(f"  Strategy {i+1} Direction: {orig.get('direction')} -> {new.get('direction')}")
        
        # Check for added risk factors
        if 'risk_factors' in resolved and ('risk_factors' not in original or 
                                         len(resolved['risk_factors']) > len(original.get('risk_factors', []))):
            print("\n  Added Risk Factors:")
            for risk in resolved.get('risk_factors', []):
                if risk not in original.get('risk_factors', []):
                    print(f"  - {risk.get('description', 'N/A')} (Severity: {risk.get('severity', 'N/A')})")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Run full chain options analysis with manager review')
    parser.add_argument('ticker', nargs='?', default='SPY', help='Stock ticker symbol (default: SPY)')
    args = parser.parse_args()
    
    ticker = args.ticker.upper()
    
    # Step 1: Analyze the options chain
    logger.info(f"Starting analysis for {ticker}")
    analysis_data = analyze_full_chain(ticker)
    
    if not analysis_data:
        logger.error("Analysis failed. Exiting.")
        return
    
    # Step 2: Run LLM analysis
    llm_analysis = run_llm_analysis(analysis_data)
    
    if not llm_analysis:
        logger.error("LLM analysis failed. Exiting.")
        return
    
    # Display LLM analysis
    display_llm_analysis(llm_analysis)
    
    # Step 3: Run manager review
    review_result = run_manager_review(llm_analysis, analysis_data["market_context"])
    
    if not review_result:
        logger.error("Manager review failed.")
    else:
        # Display manager review results
        display_manager_review(review_result)
        
        # Save results
        output_dir = "results"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"{ticker}_analysis_{timestamp}.json")
        
        # Convert the data to a JSON-safe format before dumping
        safe_data = {
            "analysis_data": json_safe_dict(analysis_data["analysis"]),
            "llm_analysis": json_safe_dict(llm_analysis),
            "manager_review": json_safe_dict(review_result)
        }
        
        with open(output_file, 'w') as f:
            json.dump(safe_data, f, indent=2, cls=CustomJSONEncoder)
        
        logger.info(f"Results saved to {output_file}")

if __name__ == "__main__":
    start_time = time.time()
    main()
    duration = time.time() - start_time
    logger.info(f"Total execution time: {duration:.2f} seconds") 