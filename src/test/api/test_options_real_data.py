#!/usr/bin/env python3
"""
Test script for real options data analysis using YahooFinanceConnector
"""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
from datetime import datetime
from dotenv import load_dotenv
from decimal import Decimal

# Set up logging with clear output for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),  # Debug info to stderr
        logging.FileHandler('options_analysis.log')  # Also log to file
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import the necessary classes
from src.data.models import OptionChain, OptionChainQuote, OptionChainOptions, OptionStraddle, OptionContract
from src.data.connectors.yahoo_finance import YahooFinanceConnector

# Create a patched version of get_option_chain_rapidapi to fix the symbol parameter issue
class PatchedYahooFinanceConnector(YahooFinanceConnector):
    def _get_option_chain_rapidapi(self, ticker: str) -> OptionChain:
        """Patched version of _get_option_chain_rapidapi that fixes the 'symbol' parameter issue"""
        self._handle_rate_limits()
        
        url = f"{self.base_url}/stock/get-options"
        params = {"symbol": ticker, "region": "US"}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            self._update_rate_limits(response.headers)
            
            if response.status_code != 200:
                logger.error(f"Error fetching option chain: {response.status_code} - {response.text}")
                raise Exception(f"API request failed with status {response.status_code}")
            
            data = response.json()
            
            # Get quote data
            quote_data = data.get("optionChain", {}).get("result", [{}])[0].get("quote", {})
            quote = OptionChainQuote(
                # Remove the symbol parameter since it's not in the class definition
                quote_type=quote_data.get("quoteType", ""),
                market_state=quote_data.get("marketState", ""),
                currency=quote_data.get("currency", "USD"),
                regular_market_price=quote_data.get("regularMarketPrice", 0),
                regular_market_change=quote_data.get("regularMarketChange", 0),
                regular_market_change_percent=quote_data.get("regularMarketChangePercent", 0),
                regular_market_open=quote_data.get("regularMarketOpen", 0),
                regular_market_day_high=quote_data.get("regularMarketDayHigh", 0),
                regular_market_day_low=quote_data.get("regularMarketDayLow", 0),
                regular_market_volume=quote_data.get("regularMarketVolume", 0),
                market_cap=quote_data.get("marketCap", 0),
                trailing_pe=quote_data.get("trailingPE", 0),
                trailing_annual_dividend_rate=quote_data.get("trailingAnnualDividendRate", 0),
                dividend_rate=quote_data.get("dividendRate", 0),
                dividend_yield=quote_data.get("dividendYield", 0),
                eps_trailing_twelve_months=quote_data.get("epsTrailingTwelveMonths", 0),
                eps_forward=quote_data.get("epsForward", 0),
                eps_current_year=quote_data.get("epsCurrentYear", 0)
            )
            
            # Process the rest of the chain data
            # (rest of the function is the same as the original implementation)
            option_chain_data = data.get("optionChain", {}).get("result", [{}])[0].get("options", [])
            expirations = []
            strikes = set()
            
            for option_date in option_chain_data:
                timestamp = option_date.get("expirationDate")
                if not timestamp:
                    continue
                    
                exp_date = datetime.fromtimestamp(timestamp)
                
                # Process straddles (call/put pairs)
                straddles = []
                for straddle_data in option_date.get("straddles", []):
                    strike = straddle_data.get("strike")
                    strikes.add(strike)
                    
                    call_data = straddle_data.get("call")
                    put_data = straddle_data.get("put")
                    
                    call_contract = None
                    if call_data:
                        call_contract = OptionContract(
                            contract_symbol=call_data.get("contractSymbol", ""),
                            option_type="CALL",  # Use correct enum value
                            strike=call_data.get("strike", 0),
                            currency=call_data.get("currency", "USD"),
                            last_price=call_data.get("lastPrice", 0),
                            change_price=call_data.get("change", 0),  # Renamed from change
                            percent_change=call_data.get("percentChange", 0),
                            volume=call_data.get("volume", 0),
                            open_interest=call_data.get("openInterest", 0),
                            bid=call_data.get("bid", 0),
                            ask=call_data.get("ask", 0),
                            implied_volatility=call_data.get("impliedVolatility", 0),
                            in_the_money=call_data.get("inTheMoney", False)
                        )
                    
                    put_contract = None
                    if put_data:
                        put_contract = OptionContract(
                            contract_symbol=put_data.get("contractSymbol", ""),
                            option_type="PUT",  # Use correct enum value
                            strike=put_data.get("strike", 0),
                            currency=put_data.get("currency", "USD"),
                            last_price=put_data.get("lastPrice", 0),
                            change_price=put_data.get("change", 0),  # Renamed from change
                            percent_change=put_data.get("percentChange", 0),
                            volume=put_data.get("volume", 0),
                            open_interest=put_data.get("openInterest", 0),
                            bid=put_data.get("bid", 0),
                            ask=put_data.get("ask", 0),
                            implied_volatility=put_data.get("impliedVolatility", 0),
                            in_the_money=put_data.get("inTheMoney", False)
                        )
                    
                    straddle = OptionStraddle(
                        strike=strike,
                        call_contract=call_contract,
                        put_contract=put_contract
                    )
                    straddles.append(straddle)
                
                expiration = OptionChainOptions(
                    expiration_date=exp_date,
                    has_mini_options=False,
                    straddles=straddles
                )
                expirations.append(expiration)
            
            # Create OptionChain object
            option_chain = OptionChain(
                underlying_symbol=ticker,
                has_mini_options=False,  # Required parameter
                quote=quote,
                expiration_dates=[exp.expiration_date for exp in expirations],
                strikes=sorted(list(strikes)),
                options=expirations
            )
            
            # Cache the result
            self._store_in_cache(f"option_chain_{ticker}", option_chain)
            
            return option_chain
        except Exception as e:
            logger.error(f"Error fetching option chain for {ticker}: {str(e)}")
            raise

def analyze_options_with_connector(ticker='SPY'):
    """
    Analyze options data fetched directly from YahooFinanceConnector
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Dictionary with comprehensive options analysis
    """
    logger.info(f"Analyzing real options data for {ticker} using PatchedYahooFinanceConnector")
    
    # Initialize connector
    try:
        # Use our patched connector instead of the original
        connector = PatchedYahooFinanceConnector(use_rapidapi=True)
        logger.info("Successfully initialized PatchedYahooFinanceConnector")
    except Exception as e:
        logger.error(f"Error initializing YahooFinanceConnector: {str(e)}")
        sys.exit(1)
    
    # Get option chain data
    try:
        option_chain = connector.get_option_chain(ticker)
        logger.info(f"Successfully fetched option chain for {ticker}")
        
        # Log some info about what we retrieved
        logger.info(f"Number of expirations: {len(option_chain.expiration_dates)}")
        logger.info(f"Available expirations: {[exp.strftime('%Y-%m-%d') for exp in option_chain.expiration_dates[:5]]}...")
        logger.info(f"Number of strikes: {len(option_chain.strikes)}")
        
        # Get current price from the quote
        current_price = option_chain.quote.regular_market_price
        logger.info(f"Current price: {current_price}")
        
    except Exception as e:
        logger.error(f"Error fetching option chain: {str(e)}")
        sys.exit(1)
    
    # Rest of the function remains the same
    # Get nearest expiration for detailed analysis
    exp_date = option_chain.expiration_dates[0]
    logger.info(f"Analyzing expiration date: {exp_date.strftime('%Y-%m-%d')}")
    
    # Find the options for this expiration
    expiration_options = None
    for exp_options in option_chain.options:
        if exp_options.expiration_date == exp_date:
            expiration_options = exp_options
            break
    
    if not expiration_options:
        logger.error(f"No options found for expiration {exp_date}")
        sys.exit(1)
    
    # Build a DataFrame for analysis
    logger.info("Building DataFrame for analysis...")
    
    # Convert to float if it's a Decimal to avoid serialization issues
    def to_float(value):
        if isinstance(value, Decimal):
            return float(value)
        return value or 0
    
    data = []
    for straddle in expiration_options.straddles:
        strike = to_float(straddle.strike)
        
        call_contract = straddle.call_contract
        put_contract = straddle.put_contract
        
        # Only add rows where both call and put data exist
        row = {
            'Strike': strike
        }
        
        if call_contract:
            row.update({
                'Call_Vol': to_float(call_contract.volume),
                'Call_OI': to_float(call_contract.open_interest),
                'Call_IV': to_float(call_contract.implied_volatility),
                'Call_Bid': to_float(call_contract.bid),
                'Call_Ask': to_float(call_contract.ask)
            })
        else:
            row.update({
                'Call_Vol': 0,
                'Call_OI': 0,
                'Call_IV': 0,
                'Call_Bid': 0,
                'Call_Ask': 0
            })
            
        if put_contract:
            row.update({
                'Put_Vol': to_float(put_contract.volume),
                'Put_OI': to_float(put_contract.open_interest),
                'Put_IV': to_float(put_contract.implied_volatility),
                'Put_Bid': to_float(put_contract.bid),
                'Put_Ask': to_float(put_contract.ask)
            })
        else:
            row.update({
                'Put_Vol': 0,
                'Put_OI': 0,
                'Put_IV': 0,
                'Put_Bid': 0,
                'Put_Ask': 0
            })
            
        data.append(row)
    
    df = pd.DataFrame(data)
    
    # Convert current price to float if it's a Decimal
    current_price = to_float(current_price)
    
    # Calculate additional metrics
    if len(df) > 0:
        # Avoid division by zero
        df['PC_Ratio'] = df['Put_Vol'] / df['Call_Vol'].replace(0, 0.1)
        df['IV_Skew'] = df['Put_IV'] - df['Call_IV']
        df['Moneyness'] = (df['Strike'] / current_price) - 1  # % away from current price
    
        # Find ATM strike
        atm_strike = min(df.Strike, key=lambda x: abs(x - current_price))
        logger.info(f"ATM strike: {atm_strike}")
        
        # Sort by strike
        df = df.sort_values('Strike').dropna()
    else:
        logger.warning("No option data available for analysis")
        atm_strike = current_price
        
    # Print some basic info about the chain
    print(f"\n===== OPTION CHAIN SUMMARY FOR {ticker} =====")
    print(f"Current Price: ${current_price:.2f}")
    print(f"Expiration Date: {exp_date.strftime('%Y-%m-%d')}")
    
    if len(df) > 0:
        print(f"Total Calls Volume: {df['Call_Vol'].sum()}")
        print(f"Total Puts Volume: {df['Put_Vol'].sum()}")
        print(f"Put/Call Volume Ratio: {df['Put_Vol'].sum() / max(df['Call_Vol'].sum(), 1):.2f}")
        print(f"ATM Strike: ${atm_strike}")
    else:
        print("No option data available for this expiration")
        return {}, pd.DataFrame()
    
    # ANALYSIS: Create a comprehensive analysis dictionary
    analysis = {}
    
    # Calculate overall put/call volume and OI ratios
    analysis['overall_put_call_ratio'] = df['Put_Vol'].sum() / max(df['Call_Vol'].sum(), 1)
    analysis['overall_oi_ratio'] = df['Put_OI'].sum() / max(df['Call_OI'].sum(), 1)
    
    # Calculate z-scores for volume and OI to identify unusual activity
    def calculate_zscore(series):
        if series.std() == 0:
            return pd.Series(0, index=series.index)
        return (series - series.mean()) / series.std()
    
    df['Call_Vol_Z'] = calculate_zscore(df['Call_Vol'])
    df['Put_Vol_Z'] = calculate_zscore(df['Put_Vol']) 
    df['Call_OI_Z'] = calculate_zscore(df['Call_OI'])
    df['Put_OI_Z'] = calculate_zscore(df['Put_OI'])
    
    # Identify high activity strikes
    high_call_vol = df[df['Call_Vol_Z'] > 2].sort_values('Call_Vol', ascending=False)
    analysis['high_call_volume_strikes'] = high_call_vol[['Strike', 'Call_Vol', 'Call_Vol_Z', 'Call_OI']].head(5).to_dict('records') if not high_call_vol.empty else []
    
    high_put_vol = df[df['Put_Vol_Z'] > 2].sort_values('Put_Vol', ascending=False)
    analysis['high_put_volume_strikes'] = high_put_vol[['Strike', 'Put_Vol', 'Put_Vol_Z', 'Put_OI']].head(5).to_dict('records') if not high_put_vol.empty else []
    
    # Identify unusual PUT/CALL ratios
    high_pc_ratio_df = df[(df['PC_Ratio'] > 3) & (df['Put_Vol'] > df['Put_Vol'].median())].sort_values('PC_Ratio', ascending=False)
    analysis['high_put_call_ratio_strikes'] = high_pc_ratio_df[['Strike', 'Put_Vol', 'Call_Vol', 'PC_Ratio']].head(5).to_dict('records') if not high_pc_ratio_df.empty else []
    
    low_pc_ratio_df = df[(df['PC_Ratio'] < 0.33) & (df['Call_Vol'] > df['Call_Vol'].median())].sort_values('PC_Ratio')
    analysis['low_put_call_ratio_strikes'] = low_pc_ratio_df[['Strike', 'Call_Vol', 'Put_Vol', 'PC_Ratio']].head(5).to_dict('records') if not low_pc_ratio_df.empty else []
    
    # Analyze IV skew patterns
    # Group strikes by moneyness for IV analysis
    moneyness_groups = {
        'deep_itm_calls': df[df['Moneyness'] < -0.10],
        'itm_calls': df[(df['Moneyness'] >= -0.10) & (df['Moneyness'] < -0.02)],
        'atm': df[(df['Moneyness'] >= -0.02) & (df['Moneyness'] <= 0.02)],
        'itm_puts': df[(df['Moneyness'] > 0.02) & (df['Moneyness'] <= 0.10)],
        'deep_itm_puts': df[df['Moneyness'] > 0.10]
    }
    
    # Calculate average IV for each moneyness group
    iv_by_moneyness = {}
    for group, data in moneyness_groups.items():
        if not data.empty:
            iv_by_moneyness[group] = {
                'avg_call_iv': data['Call_IV'].mean(),
                'avg_put_iv': data['Put_IV'].mean(),
                'avg_iv_skew': data['IV_Skew'].mean()
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
    
    # Identify key support/resistance levels from options
    # Support levels = high put OI, Resistance levels = high call OI
    support_candidates = df[(df['Put_OI_Z'] > 1.5) & (df['Strike'] < current_price)].sort_values('Put_OI', ascending=False)
    resistance_candidates = df[(df['Call_OI_Z'] > 1.5) & (df['Strike'] > current_price)].sort_values('Call_OI', ascending=False)
    
    analysis['key_support_levels'] = support_candidates[['Strike', 'Put_OI', 'Put_OI_Z']].head(3).to_dict('records') if not support_candidates.empty else []
    analysis['key_resistance_levels'] = resistance_candidates[['Strike', 'Call_OI', 'Call_OI_Z']].head(3).to_dict('records') if not resistance_candidates.empty else []
    
    # Print findings
    print("\n===== FULL CHAIN ANALYSIS =====")
    print(f"Overall Put/Call Volume Ratio: {analysis['overall_put_call_ratio']:.2f}")
    print(f"IV Skew Pattern: {analysis['iv_skew_pattern']}")
    
    print("\nTop High Call Volume Strikes:")
    if analysis['high_call_volume_strikes']:
        for strike in analysis['high_call_volume_strikes'][:3]:
            print(f"- Strike: ${strike['Strike']:.2f}, Volume: {int(strike['Call_Vol'])}, Z-Score: {strike['Call_Vol_Z']:.2f}")
    else:
        print("- No significant high call volume strikes detected")
    
    print("\nTop High Put Volume Strikes:")
    if analysis['high_put_volume_strikes']:
        for strike in analysis['high_put_volume_strikes'][:3]:
            print(f"- Strike: ${strike['Strike']:.2f}, Volume: {int(strike['Put_Vol'])}, Z-Score: {strike['Put_Vol_Z']:.2f}")
    else:
        print("- No significant high put volume strikes detected")
    
    print("\nKey Support Levels (High Put OI):")
    if analysis['key_support_levels']:
        for level in analysis['key_support_levels']:
            print(f"- ${level['Strike']:.2f} (Put OI: {int(level['Put_OI'])})")
    else:
        print("- No significant support levels detected")
    
    print("\nKey Resistance Levels (High Call OI):")
    if analysis['key_resistance_levels']:
        for level in analysis['key_resistance_levels']:
            print(f"- ${level['Strike']:.2f} (Call OI: {int(level['Call_OI'])})")
    else:
        print("- No significant resistance levels detected")
    
    # Save analysis to file
    output_file = f'connector_options_analysis_{ticker}.json'
    with open(output_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    logger.info(f"Saved analysis to {output_file}")
    
    # Only create plots if we have data
    if len(df) > 0:
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
        
        plt.title(f"{ticker} Options Volume Analysis ({exp_date.strftime('%Y-%m-%d')})")
        plt.xlabel("Strike Price")
        plt.ylabel("Volume")
        plt.legend()
        plt.grid(alpha=0.3)
        
        # Save the plot
        plot_file = f'connector_options_volume_{ticker}.png'
        plt.savefig(plot_file)
        logger.info(f"Saved volume plot to {plot_file}")
        
        # Plot IV Skew
        plt.figure(figsize=(12, 8))
        plt.scatter(df.Strike, df.Call_IV, color='green', alpha=0.7, label='Call IV')
        plt.scatter(df.Strike, df.Put_IV, color='red', alpha=0.7, label='Put IV')
        
        # Fit a curve to better show the skew
        try:
            from scipy.interpolate import make_interp_spline
            
            # Sort for interpolation
            call_strikes = df.sort_values('Strike')['Strike']
            call_ivs = df.sort_values('Strike')['Call_IV']
            put_strikes = df.sort_values('Strike')['Strike']
            put_ivs = df.sort_values('Strike')['Put_IV']
            
            # Generate points for smooth curve
            if len(call_strikes) > 3:  # Need at least 4 points for cubic spline
                x_call = np.linspace(min(call_strikes), max(call_strikes), 100)
                spl_call = make_interp_spline(call_strikes, call_ivs, k=3)
                y_call = spl_call(x_call)
                plt.plot(x_call, y_call, '-', color='green', alpha=0.5)
                
                x_put = np.linspace(min(put_strikes), max(put_strikes), 100)
                spl_put = make_interp_spline(put_strikes, put_ivs, k=3)
                y_put = spl_put(x_put)
                plt.plot(x_put, y_put, '-', color='red', alpha=0.5)
        except Exception as e:
            logger.warning(f"Could not generate smooth IV curve: {str(e)}")
        
        # Highlight the current price
        plt.axvline(x=current_price, color='blue', linestyle='--', alpha=0.5, label=f'Current Price ({current_price:.2f})')
        
        plt.title(f"{ticker} Implied Volatility Skew ({exp_date.strftime('%Y-%m-%d')})")
        plt.xlabel("Strike Price")
        plt.ylabel("Implied Volatility")
        plt.legend()
        plt.grid(alpha=0.3)
        
        # Save the IV skew plot
        iv_plot_file = f'connector_options_iv_skew_{ticker}.png'
        plt.savefig(iv_plot_file)
        logger.info(f"Saved IV skew plot to {iv_plot_file}")
        
        # Plot Open Interest
        plt.figure(figsize=(12, 8))
        plt.bar(df.Strike - 0.2, df.Call_OI, width=0.4, label='Call OI', color='darkgreen', alpha=0.7)
        plt.bar(df.Strike + 0.2, df.Put_OI, width=0.4, label='Put OI', color='darkred', alpha=0.7)
        
        # Highlight the current price
        plt.axvline(x=current_price, color='blue', linestyle='--', alpha=0.5, label=f'Current Price ({current_price:.2f})')
        
        plt.title(f"{ticker} Open Interest Analysis ({exp_date.strftime('%Y-%m-%d')})")
        plt.xlabel("Strike Price")
        plt.ylabel("Open Interest")
        plt.legend()
        plt.grid(alpha=0.3)
        
        # Save the OI plot
        oi_plot_file = f'connector_options_oi_{ticker}.png'
        plt.savefig(oi_plot_file)
        logger.info(f"Saved open interest plot to {oi_plot_file}")
        
        print(f"\nAnalysis complete! Files saved:")
        print(f"1. Data: {output_file}")
        print(f"2. Volume Chart: {plot_file}")
        print(f"3. IV Skew Chart: {iv_plot_file}")
        print(f"4. Open Interest Chart: {oi_plot_file}")
        
        # Show all charts if running interactively
        try:
            if sys.stdout.isatty():
                plt.show()
        except:
            pass
    else:
        print("\nNo data available for plotting.")
    
    return analysis, df

def main():
    """Main function"""
    # Parse command line arguments
    ticker = sys.argv[1] if len(sys.argv) > 1 else 'SPY'
    
    print(f"Fetching real options data for {ticker} using PatchedYahooFinanceConnector...")
    analysis, df = analyze_options_with_connector(ticker)
    
    print("\nDone!")

if __name__ == "__main__":
    main() 