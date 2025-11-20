#!/usr/bin/env python3
"""
DEBUG OPTIONS API - Check straddles structure properly
"""

import requests
import json

# Use our real API key
api_key = "9f107deaabmsh2efbc3559ddca05p17f1abjsn271e6df32f7c"
base_url = "https://apidojo-yahoo-finance-v1.p.rapidapi.com"
headers = {
    'x-rapidapi-host': 'apidojo-yahoo-finance-v1.p.rapidapi.com',
    'x-rapidapi-key': api_key
}

def debug_straddles_properly(ticker):
    """Debug the straddles structure properly"""
    print(f"🔍 DEBUGGING STRADDLES FOR {ticker}")
    
    url = f"{base_url}/stock/v3/get-options"
    params = {
        'symbol': ticker,
        'region': 'US'
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            option_chain = data['optionChain']['result'][0]
            options = option_chain['options'][0]
            
            print(f"Options type: {type(options)}")
            print(f"Options keys: {list(options.keys())}")
            
            straddles = options['straddles']
            print(f"Straddles type: {type(straddles)}")
            print(f"Straddles length: {len(straddles)}")
            
            if straddles:
                print(f"First straddle: {straddles[0]}")
                print(f"First straddle keys: {list(straddles[0].keys())}")
                
                # Check for calls and puts in first straddle
                first_straddle = straddles[0]
                if 'calls' in first_straddle:
                    calls = first_straddle['calls']
                    print(f"Found {len(calls)} calls")
                    if calls:
                        print(f"First call: {calls[0]}")
                
                if 'puts' in first_straddle:
                    puts = first_straddle['puts']
                    print(f"Found {len(puts)} puts")
                    if puts:
                        print(f"First put: {puts[0]}")
            else:
                print("No straddles found")
                
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_straddles_properly('SPY')

