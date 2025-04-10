#!/usr/bin/env python3
"""
Test script for enhanced full chain options analysis
"""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
from tabulate import tabulate

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_full_chain(ticker='SPY'):
    """
    Analyze the complete options chain for a given ticker
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Dictionary with comprehensive options analysis
    """
    logger.info(f"Analyzing full options chain for {ticker}")
    
    # Get option chain data
    spy = yf.Ticker(ticker)
    current_price = spy.info['regularMarketPrice']
    logger.info(f"Current price: {current_price}")
    
    # Get all available expirations (limited to first 5 for testing)
    exp_dates = spy.options[:5]
    logger.info(f"Available expirations: {exp_dates}")
    
    # Get nearest expiration for detailed analysis
    exp_date = exp_dates[0]
    logger.info(f"Analyzing expiration date: {exp_date}")
    
    # Get options chain
    options = spy.option_chain(exp_date)
    calls = options.calls
    puts = options.puts
    
    # Find ATM strike
    atm_strike = min(calls.strike, key=lambda x: abs(x - current_price))
    logger.info(f"ATM strike: {atm_strike}")
    
    # Create combined dataframe for analysis of the full chain
    df = pd.DataFrame({
        'Strike': calls.strike,
        'Call_Vol': calls.volume,
        'Put_Vol': puts.volume,
        'PC_Ratio': puts.volume / calls.volume,
        'Call_OI': calls.openInterest,
        'Put_OI': puts.openInterest,
        'Call_IV': calls.impliedVolatility,
        'Put_IV': puts.impliedVolatility,
        'IV_Skew': puts.impliedVolatility - calls.impliedVolatility,
        'Moneyness': (calls.strike / current_price) - 1  # % away from current price
    })
    
    # Sort by strike and remove any rows with NaN values
    df = df.sort_values('Strike').dropna()
    
    # ANALYSIS 1: Identify significant price levels based on volume and OI
    analysis = {}
    
    # Calculate overall put/call volume and OI ratios
    analysis['overall_put_call_ratio'] = df['Put_Vol'].sum() / df['Call_Vol'].sum()
    analysis['overall_oi_ratio'] = df['Put_OI'].sum() / df['Call_OI'].sum()
    
    # Calculate z-scores for volume and OI to identify unusual activity
    def calculate_zscore(series):
        return (series - series.mean()) / series.std()
    
    df['Call_Vol_Z'] = calculate_zscore(df['Call_Vol'])
    df['Put_Vol_Z'] = calculate_zscore(df['Put_Vol']) 
    df['Call_OI_Z'] = calculate_zscore(df['Call_OI'])
    df['Put_OI_Z'] = calculate_zscore(df['Put_OI'])
    
    # ANALYSIS 2: Identify high activity strikes
    # Identify strikes with abnormal call volume (z-score > 2)
    high_call_vol = df[df['Call_Vol_Z'] > 2].sort_values('Call_Vol', ascending=False)
    analysis['high_call_volume_strikes'] = high_call_vol[['Strike', 'Call_Vol', 'Call_Vol_Z', 'Call_OI']].head(5).to_dict('records')
    
    # Identify strikes with abnormal put volume
    high_put_vol = df[df['Put_Vol_Z'] > 2].sort_values('Put_Vol', ascending=False)
    analysis['high_put_volume_strikes'] = high_put_vol[['Strike', 'Put_Vol', 'Put_Vol_Z', 'Put_OI']].head(5).to_dict('records')
    
    # ANALYSIS 3: Identify unusual PUT/CALL ratios
    # Strikes with high put/call ratio (bearish positioning)
    high_pc_ratio = df[(df['PC_Ratio'] > 3) & (df['Put_Vol'] > df['Put_Vol'].median())].sort_values('PC_Ratio', ascending=False)
    analysis['high_put_call_ratio_strikes'] = high_pc_ratio[['Strike', 'Put_Vol', 'Call_Vol', 'PC_Ratio']].head(5).to_dict('records')
    
    # Strikes with low put/call ratio (bullish positioning)
    low_pc_ratio = df[(df['PC_Ratio'] < 0.33) & (df['Call_Vol'] > df['Call_Vol'].median())].sort_values('PC_Ratio')
    analysis['low_put_call_ratio_strikes'] = low_pc_ratio[['Strike', 'Call_Vol', 'Put_Vol', 'PC_Ratio']].head(5).to_dict('records')
    
    # ANALYSIS 4: Analyze IV skew patterns
    # Group strikes by moneyness for IV analysis
    moneyness_groups = {
        'deep_itm_calls': df[df['Moneyness'] < -0.10],
        'itm_calls': df[(df['Moneyness'] >= -0.10) & (df['Moneyness'] < -0.02)],
        'atm': df[(df['Moneyness'] >= -0.02) & (df['Moneyness'] <= 0.02)],
        'itm_puts': df[(df['Moneyness'] > 0.02) & (df['Moneyness'] <= 0.10)],
        'deep_itm_puts': df[df['Moneyness'] > 0.10]
    }
    
    # Calculate average IV for each moneyness group
    iv_by_moneyness = {
        group: {
            'avg_call_iv': data['Call_IV'].mean(),
            'avg_put_iv': data['Put_IV'].mean(),
            'avg_iv_skew': data['IV_Skew'].mean()
        } for group, data in moneyness_groups.items() if not data.empty
    }
    analysis['iv_by_moneyness'] = iv_by_moneyness
    
    # Determine skew pattern
    atm_iv = iv_by_moneyness.get('atm', {}).get('avg_call_iv', 0)
    otm_put_iv = iv_by_moneyness.get('itm_puts', {}).get('avg_put_iv', 0)
    otm_call_iv = iv_by_moneyness.get('itm_calls', {}).get('avg_call_iv', 0)
    
    if otm_put_iv > atm_iv and otm_call_iv > atm_iv:
        skew_pattern = "volatility smile (market expects large moves in either direction)"
    elif otm_put_iv > atm_iv and otm_call_iv <= atm_iv:
        skew_pattern = "negative skew (market pricing in downside risk)"
    elif otm_put_iv <= atm_iv and otm_call_iv > atm_iv:
        skew_pattern = "positive skew (market pricing in upside potential)"
    else:
        skew_pattern = "neutral"
        
    analysis['iv_skew_pattern'] = skew_pattern
    
    # ANALYSIS 5: Identify key support/resistance levels from options
    # Support levels = high put OI, Resistance levels = high call OI
    support_candidates = df[(df['Put_OI_Z'] > 1.5) & (df['Strike'] < current_price)].sort_values('Put_OI', ascending=False)
    resistance_candidates = df[(df['Call_OI_Z'] > 1.5) & (df['Strike'] > current_price)].sort_values('Call_OI', ascending=False)
    
    analysis['key_support_levels'] = support_candidates[['Strike', 'Put_OI', 'Put_OI_Z']].head(3).to_dict('records')
    analysis['key_resistance_levels'] = resistance_candidates[['Strike', 'Call_OI', 'Call_OI_Z']].head(3).to_dict('records')
    
    # ANALYSIS 6: Find unusual activity patterns that might indicate smart money
    # Unusual volume/OI ratio (new positioning)
    df['Vol_OI_Ratio'] = (df['Call_Vol'] + df['Put_Vol']) / (df['Call_OI'] + df['Put_OI'] + 1)  # +1 to avoid div/0
    unusual_vol_oi = df[df['Vol_OI_Ratio'] > 1].sort_values('Vol_OI_Ratio', ascending=False)
    analysis['unusual_activity'] = unusual_vol_oi[['Strike', 'Call_Vol', 'Put_Vol', 'Call_OI', 'Put_OI', 'Vol_OI_Ratio']].head(5).to_dict('records')
    
    # Save results to file for examination
    with open(f'full_chain_analysis_{ticker}.json', 'w') as f:
        json.dump(analysis, f, indent=2)
    logger.info(f"Saved full chain analysis to full_chain_analysis_{ticker}.json")
    
    # Print summary of findings
    print(f"\n===== FULL CHAIN ANALYSIS FOR {ticker} =====")
    print(f"Current Price: ${current_price:.2f}")
    print(f"Overall Put/Call Volume Ratio: {analysis['overall_put_call_ratio']:.2f}")
    
    print("\nTop High Call Volume Strikes:")
    if analysis['high_call_volume_strikes']:
        for strike in analysis['high_call_volume_strikes'][:3]:
            print(f"- Strike: ${strike['Strike']:.2f}, Volume: {int(strike['Call_Vol'])}, Z-Score: {strike['Call_Vol_Z']:.2f}")
    
    print("\nTop High Put Volume Strikes:")
    if analysis['high_put_volume_strikes']:
        for strike in analysis['high_put_volume_strikes'][:3]:
            print(f"- Strike: ${strike['Strike']:.2f}, Volume: {int(strike['Put_Vol'])}, Z-Score: {strike['Put_Vol_Z']:.2f}")
    
    print(f"\nIV Skew Pattern: {analysis['iv_skew_pattern']}")
    
    print("\nKey Support Levels (High Put OI):")
    if analysis['key_support_levels']:
        for level in analysis['key_support_levels']:
            print(f"- ${level['Strike']:.2f} (Put OI: {int(level['Put_OI'])})")
    
    print("\nKey Resistance Levels (High Call OI):")
    if analysis['key_resistance_levels']:
        for level in analysis['key_resistance_levels']:
            print(f"- ${level['Strike']:.2f} (Call OI: {int(level['Call_OI'])})")
    
    # Plot volume distribution across all strikes
    plt.figure(figsize=(12, 8))
    plt.bar(df.Strike - 0.2, df.Call_Vol, width=0.4, label='Call Volume', color='green', alpha=0.7)
    plt.bar(df.Strike + 0.2, df.Put_Vol, width=0.4, label='Put Volume', color='red', alpha=0.7)
    
    # Highlight the current price and ATM strike
    plt.axvline(x=current_price, color='blue', linestyle='--', alpha=0.5, label=f'Current Price ({current_price:.2f})')
    plt.axvline(x=atm_strike, color='purple', linestyle=':', alpha=0.5, label=f'ATM Strike ({atm_strike})')
    
    # Add support and resistance levels
    if analysis['key_support_levels']:
        for i, level in enumerate(analysis['key_support_levels'][:2]):
            plt.axvline(x=level['Strike'], color='green', linestyle='-', alpha=0.3, 
                        label=f"Support {i+1}: ${level['Strike']:.2f}")
    
    if analysis['key_resistance_levels']:
        for i, level in enumerate(analysis['key_resistance_levels'][:2]):
            plt.axvline(x=level['Strike'], color='red', linestyle='-', alpha=0.3,
                        label=f"Resistance {i+1}: ${level['Strike']:.2f}")
    
    plt.title(f"{ticker} Full Chain Option Volume Analysis ({exp_date})")
    plt.xlabel("Strike Price")
    plt.ylabel("Volume")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.savefig(f'full_chain_volume_{ticker}.png')
    logger.info(f"Saved volume plot to full_chain_volume_{ticker}.png")
    
    # Create enhanced LLM prompt based on the analysis
    llm_prompt = create_enhanced_llm_prompt(ticker, current_price, analysis, exp_date)
    with open(f'llm_prompt_{ticker}.txt', 'w') as f:
        f.write(llm_prompt)
    logger.info(f"Saved LLM prompt to llm_prompt_{ticker}.txt")
    
    # Get LLM analysis of the options chain
    try:
        try:
            from src.data.llm_api import analyze_options_chain
            has_llm = True
        except ImportError:
            logger.warning("LLM API module not found. Skipping LLM analysis.")
            has_llm = False
        
        if has_llm:
            logger.info("Getting LLM analysis of options chain...")
            
            # Prepare market data
            market_data = {
                "price": current_price,
                "atm_strike": atm_strike,
                "expiration": exp_date,
                "overall_pc_ratio": analysis['overall_put_call_ratio'],
                "iv_skew": analysis['iv_skew_pattern']
            }
            
            # Get deep reasoning analysis
            llm_response = analyze_options_chain(ticker, market_data, analysis)
            
            # Parse and format the LLM analysis
            display_llm_analysis(llm_response)
            
            # Add LLM analysis to the results
            analysis['llm_interpretation'] = {
                'market_sentiment': llm_response.get('market_sentiment', ''),
                'key_levels': llm_response.get('key_levels', []),
                'volatility_analysis': llm_response.get('volatility_analysis', ''),
                'trading_opportunities': llm_response.get('trading_opportunities', []),
                'risk_factors': llm_response.get('risk_factors', []),
                'raw_analysis': llm_response
            }
            
            # Update the JSON output with LLM analysis
            with open(f'full_chain_analysis_{ticker}.json', 'w') as f:
                json.dump(analysis, f, indent=2)
            logger.info("Added LLM analysis to output file")
        else:
            print("\nNote: LLM analysis is not available. To enable LLM analysis:")
            print("1. Create src/data/llm_api.py with the query_llm function")
            print("2. Configure your LLM API credentials")
            print("\nThe statistical analysis above is still valid and can be used for trading decisions.")
            
    except Exception as e:
        logger.error(f"Error in LLM analysis: {str(e)}")
        print("\nNote: Error in LLM analysis. The statistical analysis above is still valid.")
    
    return analysis

def create_enhanced_llm_prompt(ticker, current_price, analysis, expiration):
    """
    Create an enhanced prompt for LLM-based options analysis
    
    Args:
        ticker: Stock ticker symbol
        current_price: Current price of the stock
        analysis: Dictionary with options analysis results
        expiration: Expiration date being analyzed
        
    Returns:
        String containing the prompt for LLM
    """
    prompt = f"""
    You are a professional options trader and market analyst. Analyze this complete options chain data for {ticker} and provide key insights:

    OPTIONS DATA SUMMARY:
    Current Price: ${current_price:.2f}
    Expiration: {expiration}
    Overall Put/Call Volume Ratio: {analysis['overall_put_call_ratio']:.2f}
    IV Skew Pattern: {analysis['iv_skew_pattern']}
    
    HIGH CALL VOLUME STRIKES:
    {json.dumps(analysis.get('high_call_volume_strikes', [])[:3], indent=2)}
    
    HIGH PUT VOLUME STRIKES:
    {json.dumps(analysis.get('high_put_volume_strikes', [])[:3], indent=2)}
    
    STRIKES WITH HIGH PUT/CALL RATIO (BEARISH):
    {json.dumps(analysis.get('high_put_call_ratio_strikes', [])[:3], indent=2)}
    
    STRIKES WITH LOW PUT/CALL RATIO (BULLISH):
    {json.dumps(analysis.get('low_put_call_ratio_strikes', [])[:3], indent=2)}
    
    KEY SUPPORT LEVELS:
    {json.dumps(analysis.get('key_support_levels', []), indent=2)}
    
    KEY RESISTANCE LEVELS:
    {json.dumps(analysis.get('key_resistance_levels', []), indent=2)}
    
    UNUSUAL ACTIVITY:
    {json.dumps(analysis.get('unusual_activity', [])[:3], indent=2)}

    Please provide a comprehensive analysis in the following format:

    1. MARKET SENTIMENT AND POSITIONING:
       - What is the overall market sentiment based on options flow?
       - How are institutional investors positioned (based on large lot sizes and unusual activity)?
       - What do the put/call ratios suggest about market psychology?
       - Are there any notable hedging patterns visible in the data?
       - What upcoming events or catalysts might traders be positioning for?

    2. KEY PRICE LEVELS AND MARKET STRUCTURE:
       - What are the most significant support and resistance levels based on options activity?
       - How strong is the conviction at these levels (based on OI and volume)?
       - What price ranges are market makers likely defending?
       - Where are the key gamma levels that could affect price movement?
       - What does the distribution of open interest tell us about market structure?

    3. VOLATILITY ANALYSIS:
       - What is the market pricing in terms of potential moves?
       - How does current IV compare across strikes and what does this mean?
       - What does the skew tell us about tail risk pricing?
       - Are there any volatility arbitrage opportunities?
       - What is the term structure suggesting about future volatility?

    4. TRADING OPPORTUNITIES AND RISK ASSESSMENT:
       - What specific options strategies are most appropriate given this setup?
       - What are the key risks to monitor?
       - What hedging considerations should be taken into account?
       - What price targets and stop levels make sense based on the options data?
       - What timeframes are optimal for potential trades?

    5. MARKET CONTEXT AND FORWARD-LOOKING ANALYSIS:
       - How does this options positioning fit into the broader market context?
       - What potential scenarios could significantly impact current positioning?
       - What signs should traders watch for potential sentiment shifts?
       - How might this positioning affect future price movement?
       - What contrarian opportunities might exist?

    Please provide specific numbers, levels, and concrete observations rather than general statements.
    Focus on actionable insights and clear reasoning based on the data.
    
    Return your analysis in a structured JSON format with the following keys:
    {{
        "market_sentiment": "string",
        "key_levels": [
            {{
                "level": "float",
                "type": "string",
                "strength": "string",
                "reasoning": "string"
            }}
        ],
        "volatility_analysis": "string",
        "trading_opportunities": [
            {{
                "strategy": "string",
                "rationale": "string",
                "risk_reward": "string"
            }}
        ],
        "risk_factors": ["string"],
        "detailed_analysis": "string"
    }}
    """
    return prompt

def display_llm_analysis(llm_analysis):
    """
    Format and display the LLM analysis results in a clear, structured way
    
    Args:
        llm_analysis: Dictionary containing LLM analysis results
    """
    print("\n===== MARKET ANALYSIS AND INSIGHTS =====")
    
    # Market Sentiment
    print("\n🎯 MARKET SENTIMENT")
    print("-" * 50)
    print(llm_analysis.get('market_sentiment', 'No sentiment analysis available'))
    
    # Key Levels
    print("\n📊 KEY PRICE LEVELS")
    print("-" * 50)
    for level in llm_analysis.get('key_levels', []):
        strength_indicator = "🔴" if level['strength'] == "strong" else "🟡" if level['strength'] == "moderate" else "⚪"
        print(f"{strength_indicator} ${level['level']:.2f} ({level['type']})")
        print(f"   Reasoning: {level['reasoning']}")
    
    # Volatility Analysis
    print("\n📈 VOLATILITY ANALYSIS")
    print("-" * 50)
    print(llm_analysis.get('volatility_analysis', 'No volatility analysis available'))
    
    # Trading Opportunities
    print("\n💰 TRADING OPPORTUNITIES")
    print("-" * 50)
    for opp in llm_analysis.get('trading_opportunities', []):
        print(f"Strategy: {opp['strategy']}")
        print(f"Rationale: {opp['rationale']}")
        print(f"Risk/Reward: {opp['risk_reward']}")
        print()
    
    # Risk Factors
    print("\n⚠️ KEY RISK FACTORS")
    print("-" * 50)
    for risk in llm_analysis.get('risk_factors', []):
        print(f"• {risk}")
    
    # Detailed Analysis
    if 'detailed_analysis' in llm_analysis:
        print("\n📝 DETAILED ANALYSIS")
        print("-" * 50)
        print(llm_analysis['detailed_analysis'])

if __name__ == "__main__":
    # Check for different ticker in command line args
    ticker = sys.argv[1] if len(sys.argv) > 1 else 'SPY'
    analyze_full_chain(ticker) 