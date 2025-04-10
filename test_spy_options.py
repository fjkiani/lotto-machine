#!/usr/bin/env python3
"""
Test script to analyze SPY options and understand why specific strikes (like 505) might be selected
"""

import os
import sys
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
from tabulate import tabulate

def analyze_options(ticker='SPY'):
    print(f"Analyzing options for {ticker}")
    
    # Get option chain data
    spy = yf.Ticker(ticker)
    current_price = spy.info['regularMarketPrice']
    print(f"Current price: {current_price}")
    
    # Get nearest expiration
    exp_date = spy.options[0]
    print(f"Analyzing expiration date: {exp_date}")
    
    # Get options chain
    options = spy.option_chain(exp_date)
    calls = options.calls
    puts = options.puts
    
    # Find ATM strike
    atm_strike = min(calls.strike, key=lambda x: abs(x - current_price))
    print(f"ATM strike: {atm_strike}")
    
    # Create combined dataframe for analysis
    df = pd.DataFrame({
        'Strike': calls.strike,
        'Call_Vol': calls.volume,
        'Put_Vol': puts.volume,
        'PC_Ratio': puts.volume / calls.volume,
        'Call_OI': calls.openInterest,
        'Put_OI': puts.openInterest,
        'Call_IV': calls.impliedVolatility,
        'Put_IV': puts.impliedVolatility,
        'IV_Skew': puts.impliedVolatility - calls.impliedVolatility
    })
    
    # Filter to relevant strikes
    relevant_df = df[(df.Strike >= current_price * 0.9) & (df.Strike <= current_price * 1.1)]
    relevant_df = relevant_df.sort_values('Strike')
    
    # Print high volume strikes
    print("\nTop 5 Call volume strikes:")
    top_calls = df.nlargest(5, 'Call_Vol')[['Strike', 'Call_Vol', 'Put_Vol', 'PC_Ratio']]
    print(tabulate(top_calls, headers='keys', tablefmt='psql', showindex=False))
    
    print("\nTop 5 Put volume strikes:")
    top_puts = df.nlargest(5, 'Put_Vol')[['Strike', 'Put_Vol', 'Call_Vol', 'PC_Ratio']]
    print(tabulate(top_puts, headers='keys', tablefmt='psql', showindex=False))
    
    # Check specific strikes of interest (including 505)
    interesting_strikes = [500, 505, 510, 515, 520, 525, 530]
    print("\nAnalysis of specific strikes:")
    specific_strikes = df[df.Strike.isin(interesting_strikes)][
        ['Strike', 'Call_Vol', 'Put_Vol', 'PC_Ratio', 'Call_OI', 'Put_OI']]
    print(tabulate(specific_strikes, headers='keys', tablefmt='psql', showindex=False))
    
    # Print ATM and surrounding strikes
    print(f"\nATM strike ({atm_strike}) and surrounding strikes:")
    atm_range = df[(df.Strike >= atm_strike - 5) & (df.Strike <= atm_strike + 5)][
        ['Strike', 'Call_Vol', 'Put_Vol', 'PC_Ratio', 'Call_IV', 'Put_IV']]
    print(tabulate(atm_range, headers='keys', tablefmt='psql', showindex=False))
    
    # Plot volume distribution
    plt.figure(figsize=(12, 8))
    plt.bar(relevant_df.Strike - 0.2, relevant_df.Call_Vol, width=0.4, label='Call Volume', color='green', alpha=0.7)
    plt.bar(relevant_df.Strike + 0.2, relevant_df.Put_Vol, width=0.4, label='Put Volume', color='red', alpha=0.7)
    
    # Highlight the current price and ATM strike
    plt.axvline(x=current_price, color='blue', linestyle='--', alpha=0.5, label=f'Current Price ({current_price:.2f})')
    plt.axvline(x=atm_strike, color='purple', linestyle=':', alpha=0.5, label=f'ATM Strike ({atm_strike})')
    
    # Highlight the 505 strike specifically
    if 505 in relevant_df.Strike.values:
        plt.axvline(x=505, color='orange', linestyle='-', alpha=0.3, label='505 Strike')
    
    plt.title(f"{ticker} Option Volume by Strike Price ({exp_date})")
    plt.xlabel("Strike Price")
    plt.ylabel("Volume")
    plt.xticks(relevant_df.Strike[::2])  # Show every other strike
    plt.legend()
    plt.grid(alpha=0.3)
    plt.savefig('option_volume_distribution.png')
    print("\nPlot saved as option_volume_distribution.png")
    
    # Plot open interest distribution
    plt.figure(figsize=(12, 8))
    plt.bar(relevant_df.Strike - 0.2, relevant_df.Call_OI, width=0.4, label='Call OI', color='green', alpha=0.7)
    plt.bar(relevant_df.Strike + 0.2, relevant_df.Put_OI, width=0.4, label='Put OI', color='red', alpha=0.7)
    
    plt.axvline(x=current_price, color='blue', linestyle='--', alpha=0.5, label=f'Current Price ({current_price:.2f})')
    plt.axvline(x=atm_strike, color='purple', linestyle=':', alpha=0.5, label=f'ATM Strike ({atm_strike})')
    
    if 505 in relevant_df.Strike.values:
        plt.axvline(x=505, color='orange', linestyle='-', alpha=0.3, label='505 Strike')
    
    plt.title(f"{ticker} Option Open Interest by Strike Price ({exp_date})")
    plt.xlabel("Strike Price")
    plt.ylabel("Open Interest")
    plt.xticks(relevant_df.Strike[::2])  # Show every other strike
    plt.legend()
    plt.grid(alpha=0.3)
    plt.savefig('option_oi_distribution.png')
    print("Plot saved as option_oi_distribution.png")

if __name__ == "__main__":
    # Check for different ticker in command line args
    ticker = sys.argv[1] if len(sys.argv) > 1 else 'SPY'
    analyze_options(ticker) 