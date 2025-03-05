from langchain_core.messages import HumanMessage
from graph.state import AgentState, show_agent_reasoning
import pandas as pd
import numpy as np
import json
import logging

from src.data.connectors.yahoo_finance import YahooFinanceConnector
from src.analysis.options import calculate_greeks, evaluate_market_conditions, find_optimal_options_strategy
from src.llm.models import analyze_options_with_gemini
from utils.progress import progress

logger = logging.getLogger(__name__)

##### Options Analyst Agent #####
def options_analyst_agent(state: AgentState):
    """Analyzes options data and generates trading strategies using Gemini."""
    data = state.get("data", {})
    end_date = data.get("end_date")
    tickers = data.get("tickers")
    risk_tolerance = data.get("risk_tolerance", "medium")
    use_gemini = data.get("use_gemini", True)  # Default to using Gemini

    # Initialize options analysis for each ticker
    options_analysis = {}
    yahoo_connector = YahooFinanceConnector()

    for ticker in tickers:
        progress.update_status("options_analyst_agent", ticker, "Fetching options data")
        
        try:
            # Get options chain data
            option_chain = yahoo_connector.get_option_chain(ticker)
            
            if use_gemini:
                progress.update_status("options_analyst_agent", ticker, "Analyzing with Gemini")
                
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
                
                # Use Gemini to analyze options
                gemini_analysis = analyze_options_with_gemini(ticker, option_chain_dict, risk_tolerance)
                
                # Extract data from Gemini analysis
                signal = gemini_analysis.get("overall_sentiment", "neutral")
                confidence = gemini_analysis.get("confidence", 50)
                reasoning = gemini_analysis.get("reasoning", "Analysis performed by Gemini")
                recommended_strategy = gemini_analysis.get("recommended_strategy", {}).get("name", "No strategy recommended")
                
                options_analysis[ticker] = {
                    "signal": signal,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "recommended_strategy": recommended_strategy,
                    "analysis": gemini_analysis
                }
                
            else:
                # Use traditional analysis methods
                progress.update_status("options_analyst_agent", ticker, "Analyzing market conditions")
                market_conditions = evaluate_market_conditions(option_chain)
                
                progress.update_status("options_analyst_agent", ticker, "Calculating Greeks")
                current_price = float(option_chain.quote.regular_market_price)
                atm_strike = min(option_chain.strikes, key=lambda x: abs(float(x) - current_price))
                
                # Find ATM options
                atm_call = None
                atm_put = None
                
                for options in option_chain.options:
                    for straddle in options.straddles:
                        if straddle.strike == atm_strike:
                            if straddle.call_contract:
                                atm_call = straddle.call_contract
                            if straddle.put_contract:
                                atm_put = straddle.put_contract
                            break
                    if atm_call and atm_put:
                        break
                
                # Calculate Greeks if we found ATM options
                call_greeks = calculate_greeks(atm_call, current_price) if atm_call else None
                put_greeks = calculate_greeks(atm_put, current_price) if atm_put else None
                
                progress.update_status("options_analyst_agent", ticker, "Finding optimal strategy")
                optimal_strategy = find_optimal_options_strategy(option_chain, risk_tolerance)
                
                # Prepare analysis results
                analysis = {
                    "market_conditions": market_conditions,
                    "atm_call_greeks": call_greeks,
                    "atm_put_greeks": put_greeks,
                    "optimal_strategy": optimal_strategy,
                    "reasoning": f"Market sentiment: {market_conditions['sentiment']}, Market condition: {market_conditions['market_condition']}, Put-Call Ratio: {market_conditions['put_call_ratio']:.2f if market_conditions['put_call_ratio'] else 'N/A'}"
                }
                
                # Determine overall signal
                if market_conditions["sentiment"] == "bullish":
                    signal = "bullish"
                elif market_conditions["sentiment"] == "bearish":
                    signal = "bearish"
                else:
                    signal = "neutral"
                
                # Calculate confidence based on market conditions
                confidence = 0
                if market_conditions["put_call_ratio"]:
                    if market_conditions["sentiment"] == "bullish":
                        # Lower put-call ratio means higher confidence in bullish signal
                        confidence = min(100, max(50, 100 - market_conditions["put_call_ratio"] * 50))
                    elif market_conditions["sentiment"] == "bearish":
                        # Higher put-call ratio means higher confidence in bearish signal
                        confidence = min(100, max(50, market_conditions["put_call_ratio"] * 50))
                    else:
                        # Neutral sentiment has moderate confidence
                        confidence = 50
                
                options_analysis[ticker] = {
                    "signal": signal,
                    "confidence": confidence,
                    "reasoning": analysis["reasoning"],
                    "recommended_strategy": optimal_strategy["strategy"]["name"],
                    "analysis": analysis
                }
            
        except Exception as e:
            logger.error(f"Error analyzing options for {ticker}: {str(e)}")
            options_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": f"Error analyzing options: {str(e)}",
                "recommended_strategy": None,
                "analysis": None
            }
        
        progress.update_status("options_analyst_agent", ticker, "Done")

    # Create the options analysis message
    message = HumanMessage(
        content=json.dumps(options_analysis),
        name="options_analyst_agent",
    )

    # Print the reasoning if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(options_analysis, "Options Analysis Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["options_analyst_agent"] = options_analysis

    return {
        "messages": [message],
        "data": data,
    }