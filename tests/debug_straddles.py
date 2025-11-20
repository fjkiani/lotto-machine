#!/usr/bin/env python3
"""
DEBUG OPTIONS API - Check straddles structure
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

def debug_straddles(ticker):
    """Debug the straddles structure"""
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
            
            print(f"Straddles keys: {list(options['straddles'].keys())}")
            
            # Check if there are calls and puts in straddles
            straddles = options['straddles']
            print(f"Straddles structure: {json.dumps(straddles, indent=2)[:2000]}...")
            
            # Look for calls and puts
            if 'calls' in straddles:
                calls = straddles['calls']
                print(f"Found {len(calls)} calls in straddles")
                if calls:
                    print(f"First call: {calls[0]}")
            else:
                print("No 'calls' in straddles")
            
            if 'puts' in straddles:
                puts = straddles['puts']
                print(f"Found {len(puts)} puts in straddles")
                if puts:
                    print(f"First put: {puts[0]}")
            else:
                print("No 'puts' in straddles")
                
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    debug_straddles('SPY')

