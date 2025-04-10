import os
import json
import http.client
from decimal import Decimal
from datetime import datetime
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import our models and analysis functions
from src.data.models import (
    OptionChain, OptionChainQuote, OptionChainOptions, 
    OptionStraddle, OptionContract
)
from src.llm.models import analyze_options_with_gemini

def fetch_options_from_rapidapi(ticker):
    """Fetch options data from RapidAPI Yahoo Finance endpoint"""
    logger.info(f"Fetching options data for {ticker} from RapidAPI")
    
    conn = http.client.HTTPSConnection("yahoo-finance166.p.rapidapi.com")
    
    headers = {
        'x-rapidapi-key': os.getenv("RAPIDAPI_KEY", "cdee5e97c8msh34c3fd1e0516cb2p13b5bdjsn85e981b0d4a5"),
        'x-rapidapi-host': "yahoo-finance166.p.rapidapi.com"
    }
    
    conn.request("GET", f"/api/stock/get-options?region=US&symbol={ticker}", headers=headers)
    
    res = conn.getresponse()
    data = res.read()
    
    return json.loads(data.decode("utf-8"))

def convert_to_option_chain(api_data, ticker):
    """Convert RapidAPI response to our OptionChain model"""
    logger.info(f"Converting API data to OptionChain model for {ticker}")
    
    # Extract quote data
    quote_data = api_data.get("optionChain", {}).get("result", [{}])[0].get("quote", {})
    
    # Create quote object
    quote = OptionChainQuote(
        quote_type=quote_data.get("quoteType"),
        market_state=quote_data.get("marketState"),
        currency=quote_data.get("currency"),
        regular_market_price=Decimal(str(quote_data.get("regularMarketPrice", 0))),
        regular_market_change=Decimal(str(quote_data.get("regularMarketChange", 0))),
        regular_market_change_percent=Decimal(str(quote_data.get("regularMarketChangePercent", 0))),
        regular_market_volume=quote_data.get("regularMarketVolume"),
        market_cap=quote_data.get("marketCap")
    )
    
    # Extract expiration dates
    expiration_dates = []
    options_data = []
    all_strikes = set()
    
    # Process options data
    option_chain_data = api_data.get("optionChain", {}).get("result", [{}])[0].get("options", [])
    
    for option_date in option_chain_data:
        # Extract expiration timestamp
        timestamp = option_date.get("expirationDate")
        exp_date = datetime.fromtimestamp(timestamp) if timestamp else datetime.now()
        expiration_dates.append(exp_date)
        
        # Create options for this expiration
        options = OptionChainOptions(
            expiration_date=exp_date,
            has_mini_options=False,
            straddles=[]
        )
        
        # Process calls
        calls = option_date.get("calls", [])
        puts = option_date.get("puts", [])
        
        # Create a mapping of strikes to puts for easier lookup
        puts_by_strike = {p.get("strike"): p for p in puts}
        
        # Process each call and find matching put
        for call in calls:
            strike = Decimal(str(call.get("strike", 0)))
            all_strikes.add(strike)
            
            # Create call contract
            call_contract = OptionContract(
                contract_symbol=call.get("contractSymbol", ""),
                option_type="CALL",
                strike=strike,
                last_price=Decimal(str(call.get("lastPrice", 0))),
                bid=Decimal(str(call.get("bid", 0))),
                ask=Decimal(str(call.get("ask", 0))),
                volume=call.get("volume"),
                open_interest=call.get("openInterest"),
                implied_volatility=Decimal(str(call.get("impliedVolatility", 0))),
                in_the_money=call.get("inTheMoney", False),
                expiration=exp_date
            )
            
            # Find matching put
            put_data = puts_by_strike.get(float(strike))
            put_contract = None
            
            if put_data:
                put_contract = OptionContract(
                    contract_symbol=put_data.get("contractSymbol", ""),
                    option_type="PUT",
                    strike=strike,
                    last_price=Decimal(str(put_data.get("lastPrice", 0))),
                    bid=Decimal(str(put_data.get("bid", 0))),
                    ask=Decimal(str(put_data.get("ask", 0))),
                    volume=put_data.get("volume"),
                    open_interest=put_data.get("openInterest"),
                    implied_volatility=Decimal(str(put_data.get("impliedVolatility", 0))),
                    in_the_money=put_data.get("inTheMoney", False),
                    expiration=exp_date
                )
            
            # Create straddle
            straddle = OptionStraddle(
                strike=strike,
                call_contract=call_contract,
                put_contract=put_contract
            )
            
            options.straddles.append(straddle)
        
        options_data.append(options)
    
    # Create option chain
    option_chain = OptionChain(
        underlying_symbol=ticker,
        has_mini_options=False,
        quote=quote,
        expiration_dates=expiration_dates,
        strikes=sorted(list(all_strikes)),
        options=options_data,
        raw_json=api_data
    )
    
    return option_chain

def prepare_gemini_input(option_chain):
    """Prepare option chain data for Gemini analysis"""
    logger.info(f"Preparing Gemini input for {option_chain.underlying_symbol}")
    
    # Convert option chain to dictionary for Gemini
    option_chain_dict = {
        "underlying_symbol": option_chain.underlying_symbol,
        "current_price": float(option_chain.quote.regular_market_price),
        "expiration_dates": [exp.strftime("%Y-%m-%d") for exp in option_chain.expiration_dates],
        "strikes": [float(strike) for strike in option_chain.strikes[:20]],  # Limit to first 20 strikes for brevity
        "options_sample": []
    }
    
    # Add a sample of options data (first expiration, few strikes around ATM)
    if option_chain.options:
        current_price = float(option_chain.quote.regular_market_price)
        atm_strike = min(option_chain.strikes, key=lambda x: abs(float(x) - current_price))
        atm_index = option_chain.strikes.index(atm_strike)
        
        # Get a range of strikes around ATM
        start_idx = max(0, atm_index - 2)
        end_idx = min(len(option_chain.strikes), atm_index + 3)
        sample_strikes = option_chain.strikes[start_idx:end_idx]
        
        # Get first expiration
        first_exp = option_chain.options[0]
        
        # Add sample options
        for straddle in first_exp.straddles:
            if straddle.strike in sample_strikes:
                call_data = None
                put_data = None
                
                if straddle.call_contract:
                    call = straddle.call_contract
                    call_data = {
                        "contract_symbol": call.contract_symbol,
                        "strike": float(call.strike),
                        "bid": float(call.bid) if call.bid else None,
                        "ask": float(call.ask) if call.ask else None,
                        "implied_volatility": float(call.implied_volatility) if call.implied_volatility else None,
                        "volume": call.volume,
                        "open_interest": call.open_interest,
                        "in_the_money": call.in_the_money
                    }
                
                if straddle.put_contract:
                    put = straddle.put_contract
                    put_data = {
                        "contract_symbol": put.contract_symbol,
                        "strike": float(put.strike),
                        "bid": float(put.bid) if put.bid else None,
                        "ask": float(put.ask) if put.ask else None,
                        "implied_volatility": float(put.implied_volatility) if put.implied_volatility else None,
                        "volume": put.volume,
                        "open_interest": put.open_interest,
                        "in_the_money": put.in_the_money
                    }
                
                option_chain_dict["options_sample"].append({
                    "strike": float(straddle.strike),
                    "call": call_data,
                    "put": put_data
                })
    
    return option_chain_dict

def main():
    # Test ticker
    ticker = "AAPL"
    risk_tolerance = "medium"
    
    try:
        # Fetch options data from RapidAPI
        api_data = fetch_options_from_rapidapi(ticker)
        
        # Convert to our data model
        option_chain = convert_to_option_chain(api_data, ticker)
        
        # Prepare data for Gemini
        gemini_input = prepare_gemini_input(option_chain)
        
        # Run analysis with Gemini
        logger.info(f"Running Gemini analysis for {ticker}")
        analysis_result = analyze_options_with_gemini(ticker, gemini_input, risk_tolerance)
        
        # Display results
        print("\n===== Options Analysis Results =====\n")
        print(f"Ticker: {ticker}")
        print(f"Current Price: ${float(option_chain.quote.regular_market_price):.2f}")
        print(f"Risk Tolerance: {risk_tolerance}")
        print("\nMarket Conditions:")
        market_conditions = analysis_result.get("market_conditions", {})
        print(f"  Sentiment: {market_conditions.get('sentiment', 'N/A')}")
        print(f"  Market Condition: {market_conditions.get('market_condition', 'N/A')}")
        print(f"  Put-Call Ratio: {market_conditions.get('put_call_ratio', 'N/A')}")
        print(f"  IV Skew: {market_conditions.get('implied_volatility_skew', 'N/A')}")
        
        print("\nRecommended Strategy:")
        strategy = analysis_result.get("recommended_strategy", {})
        print(f"  Name: {strategy.get('name', 'N/A')}")
        print(f"  Description: {strategy.get('description', 'N/A')}")
        print("  Legs:")
        for leg in strategy.get("legs", []):
            print(f"    - {leg.get('type', 'N/A')} {leg.get('option_type', 'N/A')} @ strike ${leg.get('strike', 'N/A')}")
        print(f"  Max Profit: {strategy.get('max_profit', 'N/A')}")
        print(f"  Max Loss: {strategy.get('max_loss', 'N/A')}")
        
        print(f"\nOverall Sentiment: {analysis_result.get('overall_sentiment', 'N/A')}")
        print(f"Confidence: {analysis_result.get('confidence', 'N/A')}%")
        print(f"\nReasoning: {analysis_result.get('reasoning', 'N/A')}")
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 