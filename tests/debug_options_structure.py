#!/usr/bin/env python3
"""
DEBUG OPTIONS API - Check if we have the right structure
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

def debug_options_structure(ticker):
    """Debug the options structure"""
    print(f"🔍 DEBUGGING OPTIONS STRUCTURE FOR {ticker}")
    
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
            
            print(f"OptionChain keys: {list(option_chain.keys())}")
            
            if 'options' in option_chain:
                options = option_chain['options']
                print(f"Options type: {type(options)}")
                print(f"Options length: {len(options)}")
                
                if options:
                    first_option = options[0]
                    print(f"First option keys: {list(first_option.keys())}")
                    
                    if 'straddles' in first_option:
                        straddles = first_option['straddles']
                        print(f"Straddles length: {len(straddles)}")
                        
                        # Count calls and puts with volume > 100
                        call_count = 0
                        put_count = 0
                        
                        for straddle in straddles:
                            if 'call' in straddle:
                                call_volume = straddle['call'].get('volume', 0)
                                if call_volume > 100:
                                    call_count += 1
                            
                            if 'put' in straddle:
                                put_volume = straddle['put'].get('volume', 0)
                                if put_volume > 100:
                                    put_count += 1
                        
                        print(f"Calls with volume > 100: {call_count}")
                        print(f"Puts with volume > 100: {put_count}")
                        
                        # Show some examples
                        if call_count > 0:
                            print("Example calls with volume > 100:")
                            count = 0
                            for straddle in straddles:
                                if 'call' in straddle and straddle['call'].get('volume', 0) > 100:
                                    call = straddle['call']
                                    print(f"  Strike: {call['strike']}, Volume: {call['volume']}, OI: {call['openInterest']}")
                                    count += 1
                                    if count >= 3:
                                        break
                        
                        if put_count > 0:
                            print("Example puts with volume > 100:")
                            count = 0
                            for straddle in straddles:
                                if 'put' in straddle and straddle['put'].get('volume', 0) > 100:
                                    put = straddle['put']
                                    print(f"  Strike: {put['strike']}, Volume: {put['volume']}, OI: {put['openInterest']}")
                                    count += 1
                                    if count >= 3:
                                        break
                    else:
                        print("No 'straddles' key in first option")
                else:
                    print("No options found")
            else:
                print("No 'options' key in optionChain")
                
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_options_structure('SPY')

