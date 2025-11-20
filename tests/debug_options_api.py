#!/usr/bin/env python3
"""
DEBUG OPTIONS API - See what's actually being returned
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

def debug_options_api(ticker):
    """Debug the options API response"""
    print(f"🔍 DEBUGGING OPTIONS API FOR {ticker}")
    
    url = f"{base_url}/stock/v3/get-options"
    params = {
        'symbol': ticker,
        'region': 'US'
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response keys: {list(data.keys())}")
            
            if 'optionChain' in data:
                option_chain = data['optionChain']
                print(f"OptionChain keys: {list(option_chain.keys())}")
                
                if 'result' in option_chain:
                    result = option_chain['result']
                    print(f"Result length: {len(result)}")
                    
                    if result:
                        first_result = result[0]
                        print(f"First result keys: {list(first_result.keys())}")
                        
                        if 'options' in first_result:
                            options = first_result['options']
                            print(f"Options length: {len(options)}")
                            
                            if options:
                                first_option = options[0]
                                print(f"First option keys: {list(first_option.keys())}")
                                
                                if 'calls' in first_option:
                                    calls = first_option['calls']
                                    print(f"Calls length: {len(calls)}")
                                    if calls:
                                        print(f"First call: {calls[0]}")
                                
                                if 'puts' in first_option:
                                    puts = first_option['puts']
                                    print(f"Puts length: {len(puts)}")
                                    if puts:
                                        print(f"First put: {puts[0]}")
                        else:
                            print("No 'options' key in result")
                    else:
                        print("No results in optionChain")
                else:
                    print("No 'result' key in optionChain")
            else:
                print("No 'optionChain' key in response")
                print(f"Full response: {json.dumps(data, indent=2)[:1000]}...")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    debug_options_api('SPY')

