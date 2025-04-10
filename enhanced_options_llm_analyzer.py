#!/usr/bin/env python3
"""
Enhanced Options Chain Analyzer with LLM Integration
Uses real options data from Yahoo Finance API and LLM for deep analysis
"""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from dotenv import load_dotenv
from decimal import Decimal

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler('options_analysis.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import our fixed YahooFinanceConnector and models
from src.data.connectors.yahoo_finance import YahooFinanceConnector
from src.data.models import OptionChain, OptionChainQuote, OptionContract
from src.llm.models import analyze_options_with_gemini

def analyze_options_chain(ticker: str, risk_tolerance: str = "medium"):
    """
    Analyze options chain using real data and LLM insights
    
    Args:
        ticker: Stock ticker symbol
        risk_tolerance: Risk tolerance level (low, medium, high)
    """
    logger.info(f"Analyzing options chain for {ticker} with {risk_tolerance} risk tolerance")
    
    try:
        # Initialize the Yahoo Finance connector with cleared cache
        connector = YahooFinanceConnector(use_rapidapi=False)
        connector._cache = {}  # Clear the cache
        connector._cache_expiry = {}  # Clear cache expiry times
        logger.info("Successfully initialized YahooFinanceConnector with cleared cache")
        
        # Get option chain data
        option_chain = connector.get_option_chain(ticker)
        logger.info(f"Successfully fetched option chain for {ticker}")
        
        # Get current price and basic info
        current_price = option_chain.quote.regular_market_price
        logger.info(f"Current price: ${current_price}")
        
        # Process the nearest expiration date
        exp_date = option_chain.expiration_dates[0]
        logger.info(f"Analyzing expiration date: {exp_date.strftime('%Y-%m-%d')}")
        
        # Find options for this expiration
        expiration_options = next(
            (exp for exp in option_chain.options if exp.expiration_date == exp_date),
            None
        )
        
        if not expiration_options:
            logger.error(f"No options found for expiration {exp_date}")
            return
        
        # Build DataFrame for analysis
        data = []
        for straddle in expiration_options.straddles:
            strike = float(straddle.strike)
            
            # Process call contract
            if straddle.call_contract:
                call = straddle.call_contract
                call_data = {
                    'volume': float(call.volume or 0),
                    'open_interest': float(call.open_interest or 0),
                    'implied_volatility': float(call.implied_volatility or 0),
                    'bid': float(call.bid or 0),
                    'ask': float(call.ask or 0),
                    'last': float(call.last_price or 0)
                }
            else:
                call_data = {
                    'volume': 0, 'open_interest': 0, 'implied_volatility': 0,
                    'bid': 0, 'ask': 0, 'last': 0
                }
            
            # Process put contract
            if straddle.put_contract:
                put = straddle.put_contract
                put_data = {
                    'volume': float(put.volume or 0),
                    'open_interest': float(put.open_interest or 0),
                    'implied_volatility': float(put.implied_volatility or 0),
                    'bid': float(put.bid or 0),
                    'ask': float(put.ask or 0),
                    'last': float(put.last_price or 0)
                }
            else:
                put_data = {
                    'volume': 0, 'open_interest': 0, 'implied_volatility': 0,
                    'bid': 0, 'ask': 0, 'last': 0
                }
            
            data.append({
                'Strike': strike,
                'Call_Vol': call_data['volume'],
                'Put_Vol': put_data['volume'],
                'Call_OI': call_data['open_interest'],
                'Put_OI': put_data['open_interest'],
                'Call_IV': call_data['implied_volatility'],
                'Put_IV': put_data['implied_volatility'],
                'Call_Bid': call_data['bid'],
                'Call_Ask': call_data['ask'],
                'Call_Last': call_data['last'],
                'Put_Bid': put_data['bid'],
                'Put_Ask': put_data['ask'],
                'Put_Last': put_data['last'],
                'Moneyness': (strike / current_price) - 1
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values('Strike').dropna()
        
        # Calculate additional metrics
        df['PC_Ratio'] = df['Put_Vol'] / df['Call_Vol'].replace(0, 0.1)
        df['IV_Skew'] = df['Put_IV'] - df['Call_IV']
        
        # Find ATM strike
        atm_strike = min(df.Strike, key=lambda x: abs(x - current_price))
        logger.info(f"ATM strike: {atm_strike}")
        
        # Calculate Z-scores for unusual activity detection
        def calculate_zscore(series):
            if series.std() == 0:
                return pd.Series(0, index=series.index)
            return (series - series.mean()) / series.std()
        
        df['Call_Vol_Z'] = calculate_zscore(df['Call_Vol'])
        df['Put_Vol_Z'] = calculate_zscore(df['Put_Vol'])
        df['Call_OI_Z'] = calculate_zscore(df['Call_OI'])
        df['Put_OI_Z'] = calculate_zscore(df['Put_OI'])
        
        # Prepare analysis dictionary
        analysis = {
            'market_data': {
                'ticker': ticker,
                'current_price': current_price,
                'expiration_date': exp_date.strftime('%Y-%m-%d'),
                'atm_strike': atm_strike,
                'total_call_volume': int(df['Call_Vol'].sum()),
                'total_put_volume': int(df['Put_Vol'].sum()),
                'put_call_ratio': float(df['Put_Vol'].sum() / max(df['Call_Vol'].sum(), 1)),
                'atm_iv': float(df[df['Strike'] == atm_strike]['Call_IV'].iloc[0])
            }
        }
        
        # Identify high activity strikes
        high_call_vol = df[df['Call_Vol_Z'] > 2].sort_values('Call_Vol', ascending=False)
        analysis['high_call_volume_strikes'] = high_call_vol[['Strike', 'Call_Vol', 'Call_Vol_Z', 'Call_OI']].head(5).to_dict('records')
        
        high_put_vol = df[df['Put_Vol_Z'] > 2].sort_values('Put_Vol', ascending=False)
        analysis['high_put_volume_strikes'] = high_put_vol[['Strike', 'Put_Vol', 'Put_Vol_Z', 'Put_OI']].head(5).to_dict('records')
        
        # Identify key support/resistance levels
        support_levels = df[(df['Put_OI_Z'] > 1.5) & (df['Strike'] < current_price)].sort_values('Put_OI', ascending=False)
        resistance_levels = df[(df['Call_OI_Z'] > 1.5) & (df['Strike'] > current_price)].sort_values('Call_OI', ascending=False)
        
        analysis['key_levels'] = {
            'support': support_levels[['Strike', 'Put_OI', 'Put_OI_Z']].head(3).to_dict('records'),
            'resistance': resistance_levels[['Strike', 'Call_OI', 'Call_OI_Z']].head(3).to_dict('records')
        }
        
        # Analyze IV skew
        moneyness_groups = {
            'deep_itm_calls': df[df['Moneyness'] < -0.10],
            'itm_calls': df[(df['Moneyness'] >= -0.10) & (df['Moneyness'] < -0.02)],
            'atm': df[(df['Moneyness'] >= -0.02) & (df['Moneyness'] <= 0.02)],
            'itm_puts': df[(df['Moneyness'] > 0.02) & (df['Moneyness'] <= 0.10)],
            'deep_itm_puts': df[df['Moneyness'] > 0.10]
        }
        
        iv_analysis = {}
        for group, data in moneyness_groups.items():
            if not data.empty:
                iv_analysis[group] = {
                    'avg_call_iv': float(data['Call_IV'].mean()),
                    'avg_put_iv': float(data['Put_IV'].mean()),
                    'avg_iv_skew': float(data['IV_Skew'].mean())
                }
        
        analysis['iv_analysis'] = iv_analysis
        
        # Get LLM analysis
        try:
            llm_analysis = analyze_options_with_gemini(ticker, analysis, risk_tolerance)
            analysis['llm_analysis'] = llm_analysis
            logger.info("Successfully obtained LLM analysis")
        except Exception as e:
            logger.error(f"Error getting LLM analysis: {str(e)}")
            analysis['llm_analysis'] = None
        
        # Save analysis results
        output_file = f'enhanced_options_analysis_{ticker}.json'
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        logger.info(f"Saved analysis to {output_file}")
        
        # Create visualizations
        create_visualizations(df, current_price, atm_strike, analysis, ticker, exp_date)
        
        # Display results
        display_analysis(analysis)
        
        return analysis, df
        
    except Exception as e:
        logger.error(f"Error analyzing options chain: {str(e)}")
        raise

def create_visualizations(df, current_price, atm_strike, analysis, ticker, exp_date):
    """Create and save visualization plots"""
    
    # 1. Volume Distribution Plot
    plt.figure(figsize=(12, 8))
    plt.bar(df.Strike - 0.2, df.Call_Vol, width=0.4, label='Call Volume', color='green', alpha=0.7)
    plt.bar(df.Strike + 0.2, df.Put_Vol, width=0.4, label='Put Volume', color='red', alpha=0.7)
    
    # Add reference lines
    plt.axvline(x=current_price, color='blue', linestyle='--', alpha=0.5, label=f'Current Price ({current_price:.2f})')
    plt.axvline(x=atm_strike, color='purple', linestyle=':', alpha=0.5, label=f'ATM Strike ({atm_strike})')
    
    # Add support/resistance levels
    for level in analysis['key_levels']['support'][:2]:
        plt.axvline(x=level['Strike'], color='green', linestyle='-', alpha=0.3,
                   label=f"Support: ${level['Strike']:.2f}")
    
    for level in analysis['key_levels']['resistance'][:2]:
        plt.axvline(x=level['Strike'], color='red', linestyle='-', alpha=0.3,
                   label=f"Resistance: ${level['Strike']:.2f}")
    
    plt.title(f"{ticker} Options Volume Distribution ({exp_date.strftime('%Y-%m-%d')})")
    plt.xlabel("Strike Price")
    plt.ylabel("Volume")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.savefig(f'enhanced_options_volume_{ticker}.png')
    
    # 2. IV Skew Plot
    plt.figure(figsize=(12, 8))
    plt.scatter(df.Strike, df.Call_IV, color='green', alpha=0.7, label='Call IV')
    plt.scatter(df.Strike, df.Put_IV, color='red', alpha=0.7, label='Put IV')
    
    # Try to fit smooth curves
    try:
        from scipy.interpolate import make_interp_spline
        
        # Sort for interpolation
        call_data = df.sort_values('Strike')[['Strike', 'Call_IV']].dropna()
        put_data = df.sort_values('Strike')[['Strike', 'Put_IV']].dropna()
        
        if len(call_data) > 3:
            x_call = np.linspace(min(call_data.Strike), max(call_data.Strike), 100)
            spl_call = make_interp_spline(call_data.Strike, call_data.Call_IV, k=3)
            y_call = spl_call(x_call)
            plt.plot(x_call, y_call, '-', color='green', alpha=0.5)
            
            x_put = np.linspace(min(put_data.Strike), max(put_data.Strike), 100)
            spl_put = make_interp_spline(put_data.Strike, put_data.Put_IV, k=3)
            y_put = spl_put(x_put)
            plt.plot(x_put, y_put, '-', color='red', alpha=0.5)
    except Exception as e:
        logger.warning(f"Could not generate smooth IV curves: {str(e)}")
    
    plt.axvline(x=current_price, color='blue', linestyle='--', alpha=0.5, label=f'Current Price ({current_price:.2f})')
    
    plt.title(f"{ticker} Implied Volatility Skew ({exp_date.strftime('%Y-%m-%d')})")
    plt.xlabel("Strike Price")
    plt.ylabel("Implied Volatility")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.savefig(f'enhanced_options_iv_skew_{ticker}.png')
    
    # 3. Open Interest Plot
    plt.figure(figsize=(12, 8))
    plt.bar(df.Strike - 0.2, df.Call_OI, width=0.4, label='Call OI', color='darkgreen', alpha=0.7)
    plt.bar(df.Strike + 0.2, df.Put_OI, width=0.4, label='Put OI', color='darkred', alpha=0.7)
    
    plt.axvline(x=current_price, color='blue', linestyle='--', alpha=0.5, label=f'Current Price ({current_price:.2f})')
    
    plt.title(f"{ticker} Options Open Interest ({exp_date.strftime('%Y-%m-%d')})")
    plt.xlabel("Strike Price")
    plt.ylabel("Open Interest")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.savefig(f'enhanced_options_oi_{ticker}.png')
    
    logger.info("Successfully created and saved visualization plots")

def display_analysis(analysis):
    """Display analysis results in a structured format"""
    market_data = analysis['market_data']
    
    print("\n===== OPTIONS CHAIN ANALYSIS =====")
    print(f"Ticker: {market_data['ticker']}")
    print(f"Current Price: ${market_data['current_price']:.2f}")
    print(f"Expiration Date: {market_data['expiration_date']}")
    print(f"ATM Strike: ${market_data['atm_strike']:.2f}")
    print(f"Total Call Volume: {market_data['total_call_volume']:,}")
    print(f"Total Put Volume: {market_data['total_put_volume']:,}")
    print(f"Put/Call Ratio: {market_data['put_call_ratio']:.2f}")
    print(f"ATM Implied Volatility: {market_data['atm_iv']:.2%}")
    
    print("\nHigh Call Volume Strikes:")
    for strike in analysis['high_call_volume_strikes'][:3]:
        print(f"- ${strike['Strike']:.2f}: Volume={int(strike['Call_Vol']):,}, Z-Score={strike['Call_Vol_Z']:.2f}")
    
    print("\nHigh Put Volume Strikes:")
    for strike in analysis['high_put_volume_strikes'][:3]:
        print(f"- ${strike['Strike']:.2f}: Volume={int(strike['Put_Vol']):,}, Z-Score={strike['Put_Vol_Z']:.2f}")
    
    print("\nKey Support Levels:")
    for level in analysis['key_levels']['support']:
        print(f"- ${level['Strike']:.2f} (Put OI: {int(level['Put_OI']):,})")
    
    print("\nKey Resistance Levels:")
    for level in analysis['key_levels']['resistance']:
        print(f"- ${level['Strike']:.2f} (Call OI: {int(level['Call_OI']):,})")
    
    if analysis.get('llm_analysis'):
        print("\n===== LLM ANALYSIS =====")
        llm = analysis['llm_analysis']
        
        print("\nMarket Conditions:")
        print(f"Sentiment: {llm['market_conditions']['sentiment']}")
        print(f"Market State: {llm['market_conditions']['market_condition']}")
        
        print("\nRecommended Strategy:")
        strategy = llm['recommended_strategy']
        print(f"Strategy: {strategy['name']}")
        print(f"Description: {strategy['description']}")
        print(f"Max Profit: {strategy['max_profit']}")
        print(f"Max Loss: {strategy['max_loss']}")
        
        print("\nRisk Factors:")
        for risk in llm.get('risk_factors', []):
            print(f"• {risk}")
    
    print("\nVisualization files saved:")
    print(f"1. Volume Distribution: enhanced_options_volume_{market_data['ticker']}.png")
    print(f"2. IV Skew: enhanced_options_iv_skew_{market_data['ticker']}.png")
    print(f"3. Open Interest: enhanced_options_oi_{market_data['ticker']}.png")
    print(f"4. Full Analysis: enhanced_options_analysis_{market_data['ticker']}.json")

def main():
    """Main function"""
    # Parse command line arguments
    ticker = sys.argv[1] if len(sys.argv) > 1 else 'SPY'
    risk_tolerance = sys.argv[2] if len(sys.argv) > 2 else 'medium'
    
    print(f"Analyzing options chain for {ticker} with {risk_tolerance} risk tolerance...")
    analyze_options_chain(ticker, risk_tolerance)
    print("\nAnalysis complete!")

if __name__ == "__main__":
    main() 