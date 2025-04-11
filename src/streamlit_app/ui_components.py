import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Optional, Dict, List, Any
from decimal import Decimal
import logging
import subprocess
import sys
import json # Added for display_memory_enhanced_analysis
import yfinance as yf # Added for create_technical_chart
import numpy as np # Added for generate_price_targets logic within create_technical_chart

# Import necessary data models (adjust paths if needed)
try:
    from src.data.models import MarketQuote, OptionChain, OptionContract, OptionStraddle
except ImportError:
    logging.error("Failed to import data models from src.data.models")
    # Define dummy classes or handle appropriately if models are crucial immediately
    MarketQuote = Dict 
    OptionChain = Dict
    OptionContract = Dict
    OptionStraddle = Dict


logger = logging.getLogger(__name__)

# --- Display functions will be moved here ---

def display_market_overview(market_quote: Optional[MarketQuote], ticker: str) -> float:
    """Display market overview data from a MarketQuote object"""
    st.header(f"Market Overview: {ticker}")

    # Check if market_quote is None or has an error
    if market_quote is None:
        st.error(f"No market data available for {ticker}")
        return 0.0 # Return default price of 0.0 (float)

    # Check if it's an error dictionary passed instead of an object
    if isinstance(market_quote, dict) and "error" in market_quote:
        st.error(f"Error fetching market data: {market_quote.get('error')}")
        if "raw_response" in market_quote:
             with st.expander("Raw API Response"):
                 st.code(market_quote.get("raw_response", "No raw response available"))
        return 0.0 # Return default price of 0.0

    # Relaxed check: Verify attributes instead of strict isinstance
    if not hasattr(market_quote, 'regular_market_price') or not hasattr(market_quote, 'symbol'):
        logger.error(f"Received object missing expected MarketQuote attributes. Type: {type(market_quote)}")
        st.error(f"Invalid market data received (missing expected attributes). Type: {type(market_quote)}")
        return 0.0
    # if not isinstance(market_quote, MarketQuote):
    #     st.error(f"Invalid market data type received: {type(market_quote)}")
    #     return 0.0

    # Extract data from MarketQuote object
    current_price = float(market_quote.regular_market_price) if market_quote.regular_market_price is not None else 0.0
    volume = int(market_quote.regular_market_volume) if market_quote.regular_market_volume is not None else 0
    market_cap = float(market_quote.market_cap) if market_quote.market_cap is not None else 0

    # Display key metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Price", f"${current_price:.2f}")

    with col2:
        st.metric("Volume", f"{volume:,}")

    with col3:
        # Format market cap nicely (e.g., $1.23T, $45.6B, $789M)
        if market_cap >= 1e12:
            market_cap_fmt = f"${market_cap / 1e12:.2f}T"
        elif market_cap >= 1e9:
            market_cap_fmt = f"${market_cap / 1e9:.2f}B"
        elif market_cap >= 1e6:
            market_cap_fmt = f"${market_cap / 1e6:.2f}M"
        else:
            market_cap_fmt = f"${market_cap:,.0f}"
        st.metric("Market Cap", market_cap_fmt)

    # Display additional market information if available
    with st.expander("Additional Market Information"):
        col1_add, col2_add = st.columns(2)

        def format_value(value):
             return f"${float(value):.2f}" if value is not None else "N/A"

        with col1_add:
            st.metric("Day High", format_value(market_quote.regular_market_day_high))
            st.metric("Day Low", format_value(market_quote.regular_market_day_low))
            st.metric("Open", format_value(market_quote.regular_market_open))
            st.metric("Previous Close", format_value(market_quote.regular_market_previous_close))

        with col2_add:
            st.metric("52 Week High", format_value(market_quote.fifty_two_week_high))
            st.metric("52 Week Low", format_value(market_quote.fifty_two_week_low))
            # Add other relevant fields if needed, e.g., PE Ratio, Dividend Yield
            pe_ratio = float(market_quote.trailing_pe) if market_quote.trailing_pe is not None else None
            st.metric("Trailing P/E", f"{pe_ratio:.2f}" if pe_ratio is not None else "N/A")
            div_yield = market_quote.get_dividend_yield() # Use the method from MarketQuote
            st.metric("Dividend Yield", f"{div_yield:.2%}" if div_yield is not None else "N/A")


    return current_price

def display_llm_options_analysis(analysis_result, ticker):
    """Display LLM-powered options analysis"""
    st.header("LLM-Powered Options Analysis")

    # Check for errors
    if "error" in analysis_result:
        st.error(f"Error in options analysis: {analysis_result.get('error')}")
        if "raw_response" in analysis_result:
            with st.expander("Raw LLM Response"):
                st.code(analysis_result.get("raw_response"))
        return

    # Market Direction Analysis
    st.subheader("Market Direction Analysis")
    market_direction = analysis_result.get("market_direction", {})

    # Overall market bias with color
    overall_bias = market_direction.get('overall_bias', 'neutral')
    bias_color = {
        'bullish': 'green',
        'bearish': 'red',
        'neutral': 'blue'
    }.get(overall_bias.lower(), 'blue')

    # Confidence score
    confidence = market_direction.get('confidence', 0)

    # Create two columns for the main metrics
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"### Market Bias: <span style='color:{bias_color};font-size:24px'>{overall_bias.upper()}</span>", unsafe_allow_html=True)

    with col2:
        # Create a gauge chart for confidence
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = confidence,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Confidence"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': bias_color},
                'steps': [
                    {'range': [0, 33], 'color': 'lightgray'},
                    {'range': [33, 66], 'color': 'gray'},
                    {'range': [66, 100], 'color': 'darkgray'}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # Key signals from the options chain
    st.markdown("### Key Signals from Options Chain")
    key_signals = market_direction.get('key_signals', [])
    if key_signals:
        for i, signal in enumerate(key_signals):
            st.markdown(f"**{i+1}.** {signal}")
    else:
        st.write("No key signals identified")

    # Detailed market analysis
    if "detailed_analysis" in market_direction:
        with st.expander("Detailed Market Direction Analysis"):
            st.write(market_direction.get('detailed_analysis', ''))

    # Volatility Insights
    st.subheader("Volatility Insights")
    volatility_insights = analysis_result.get("volatility_insights", {})

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**Expected Move**: {volatility_insights.get('implied_move', 'N/A')}")

        # Volatility skew with color coding
        skew = volatility_insights.get('volatility_skew', 'neutral')
        skew_color = {
            'call_skew': 'green',
            'put_skew': 'red',
            'neutral': 'blue'
        }.get(skew.lower(), 'blue')

        skew_display = {
            'call_skew': 'CALL SKEW (Bullish)',
            'put_skew': 'PUT SKEW (Bearish)',
            'neutral': 'NEUTRAL'
        }.get(skew.lower(), skew.upper())

        st.markdown(f"**Volatility Skew**: <span style='color:{skew_color}'>{skew_display}</span>", unsafe_allow_html=True)

    with col2:
        st.markdown("**Event Expectations:**")
        events = volatility_insights.get('event_expectations', [])
        if events:
            for event in events:
                st.markdown(f"- {event}")
        else:
            st.write("No specific events anticipated")

    # Detailed volatility analysis
    if "volatility_analysis" in volatility_insights:
        with st.expander("Detailed Volatility Analysis"):
            st.write(volatility_insights.get('volatility_analysis', ''))

    # Options Chain Insights
    st.subheader("Options Chain Insights")

    options_insights = analysis_result.get("options_chain_insights", {})

    # Key strike levels as a bullet chart or table
    key_strikes = options_insights.get('key_strike_levels', [])
    if key_strikes:
        st.markdown("### Key Price Levels")

        # Convert to DataFrame for table display
        current_price = analysis_result.get("market_direction", {}).get("current_price", 0)
        if current_price == 0:
            # Fallback to underlying price from session state if available
            if 'options_data' in st.session_state:
                current_price = st.session_state.options_data.get("current_price", 0)

        strikes_df = pd.DataFrame({
            'Strike Level': [f"${strike:.2f}" for strike in key_strikes],
            'Distance': [f"{((strike - current_price) / current_price * 100):.2f}%" for strike in key_strikes],
            'Type': ['Resistance' if strike > current_price else 'Support' for strike in key_strikes]
        })

        st.table(strikes_df)

    # Unusual activity
    st.markdown("### Unusual Options Activity")
    unusual_activity = options_insights.get('unusual_activity', [])
    if unusual_activity:
        for activity in unusual_activity:
            st.markdown(f"- {activity}")
    else:
        st.write("No unusual options activity detected")

    # Institutional positioning
    st.markdown("### Institutional Positioning")
    st.write(options_insights.get('institutional_positioning', 'No clear institutional positioning detected'))

    # Options flow analysis
    with st.expander("Options Flow Analysis"):
        st.write(options_insights.get('options_flow_analysis', 'No options flow analysis available'))

    # SINGLE RECOMMENDED TRADE (Main Feature)
    st.markdown("---")
    st.subheader("🔥 Recommended Options Trade 🔥")

    recommended_trade = analysis_result.get("recommended_trade", {})

    if not recommended_trade:
        st.warning("No trade recommendation available")
    else:
        # Trade type with color
        trade_type = recommended_trade.get('contract_type', '').upper()
        trade_color = 'green' if trade_type == 'CALL' else 'red' if trade_type == 'PUT' else 'blue'

        # Display trade details in an eye-catching format
        st.markdown(f"""
        <div style="background-color: rgba(0, 0, 0, 0.05); padding: 20px; border-radius: 10px; border-left: 5px solid {trade_color};">
            <h2 style="color: {trade_color};">{trade_type} {ticker} @ ${recommended_trade.get('strike', 0):.2f}</h2>
            <p style="font-size: 1.2em;"><strong>Expiration:</strong> {recommended_trade.get('expiration', 'N/A')}</p>
            <p style="font-size: 1.2em;"><strong>Symbol:</strong> {recommended_trade.get('contract_symbol', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)

        # Trade metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Entry Price", f"${recommended_trade.get('entry_price', 0):.2f}")

        with col2:
            st.metric("Profit Target", f"${recommended_trade.get('profit_target', 0):.2f}")

        with col3:
            st.metric("Stop Loss", f"${recommended_trade.get('stop_loss', 0):.2f}")

        # Success probability and risk/reward
        col1, col2 = st.columns(2)

        with col1:
            prob = recommended_trade.get('probability_of_success', 0)

            # Create simple probability gauge
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = prob,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Probability of Success"},
                gauge = {
                    'axis': {'range': [None, 100]},
                    'bar': {'color': trade_color},
                    'steps': [
                        {'range': [0, 30], 'color': 'lightgray'},
                        {'range': [30, 70], 'color': 'gray'},
                        {'range': [70, 100], 'color': 'darkgray'}
                    ]
                }
            ))
            fig.update_layout(height=200, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            risk_reward = recommended_trade.get('risk_reward_ratio', 0)

            # Display risk/reward as horizontal stacked bar
            if risk_reward > 0:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    y=['Risk-Reward'],
                    x=[1],
                    name='Risk',
                    orientation='h',
                    marker=dict(color='red')
                ))
                fig.add_trace(go.Bar(
                    y=['Risk-Reward'],
                    x=[risk_reward],
                    name='Reward',
                    orientation='h',
                    marker=dict(color='green')
                ))
                fig.update_layout(
                    barmode='stack',
                    title='Risk-Reward Ratio',
                    height=200,
                    margin=dict(l=20, r=20, t=50, b=20),
                    legend=dict(orientation="h")
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.metric("Risk-Reward Ratio", f"{risk_reward:.2f}")

        # Trade thesis
        st.markdown("### Trade Thesis")
        st.write(recommended_trade.get('trade_thesis', 'No trade thesis provided'))

        # Exit strategy
        with st.expander("Exit Strategy"):
            st.write(recommended_trade.get('exit_strategy', 'No exit strategy provided'))

    # Greeks
    st.subheader("Options Greeks")
    greeks = analysis_result.get("greeks", {})

    # Create a DataFrame for the Greeks
    greeks_data = {
        "Greek": ["Delta", "Gamma", "Theta", "Vega"],
        "Value": [
            greeks.get("delta", "N/A"),
            greeks.get("gamma", "N/A"),
            greeks.get("theta", "N/A"),
            greeks.get("vega", "N/A")
        ]
    }

    greeks_df = pd.DataFrame(greeks_data)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.table(greeks_df)

    with col2:
        st.markdown("### Greeks Impact")
        st.write(greeks.get("greeks_impact", "No Greeks impact analysis provided"))

    # Risk Assessment
    st.subheader("Risk Assessment")
    risk_assessment = analysis_result.get("risk_assessment", {})

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Maximum Loss", risk_assessment.get("max_loss", "N/A"))

    with col2:
        st.metric("Maximum Gain", risk_assessment.get("max_gain", "N/A"))

    # Key risks
    st.markdown("### Key Risks")
    key_risks = risk_assessment.get('key_risks', [])
    if key_risks:
        for risk in key_risks:
            st.markdown(f"- {risk}")
    else:
        st.write("No specific risks identified")

    # Position sizing
    st.markdown("### Position Sizing Recommendation")
    st.write(risk_assessment.get('position_sizing_recommendation', 'No position sizing recommendation provided'))

    # Market Context
    st.subheader("Market Context")
    st.write(analysis_result.get("market_context", "No market context provided"))

def display_enhanced_analysis(analysis_result):
    """Display enhanced analysis with feedback loop"""
    st.header("Enhanced Analysis with Feedback Loop")

    # Check for errors
    if "error" in analysis_result:
        st.error(f"Error in enhanced analysis: {analysis_result.get('error')}")
        return

    # Market Overview - Enhanced with visual elements
    st.subheader("Market Overview")
    market_overview = analysis_result.get("market_overview", {})

    # Sentiment and Market Condition with visuals
    col1, col2 = st.columns(2)

    with col1:
        sentiment = market_overview.get('sentiment', 'neutral')
        sentiment_color = {
            'bullish': 'green',
            'bearish': 'red',
            'neutral': 'blue'
        }.get(sentiment.lower(), 'blue')

        # Create a gauge for sentiment
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = {
                'bullish': 75,
                'somewhat bullish': 60,
                'neutral': 50,
                'somewhat bearish': 40,
                'bearish': 25
            }.get(sentiment.lower(), 50),
            title = {'text': "Market Sentiment"},
            gauge = {
                'axis': {'range': [0, 100]},
                'bar': {'color': sentiment_color},
                'steps': [
                    {'range': [0, 30], 'color': 'rgba(255, 0, 0, 0.2)'},
                    {'range': [30, 45], 'color': 'rgba(255, 165, 0, 0.2)'},
                    {'range': [45, 55], 'color': 'rgba(0, 0, 255, 0.2)'},
                    {'range': [55, 70], 'color': 'rgba(144, 238, 144, 0.2)'},
                    {'range': [70, 100], 'color': 'rgba(0, 128, 0, 0.2)'}
                ]
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        market_condition = market_overview.get('market_condition', 'normal')
        condition_color = {
            'overbought': 'red',
            'oversold': 'green',
            'normal': 'blue'
        }.get(market_condition.lower(), 'blue')

        # Visual representation of market condition
        market_condition_value = {
            'strongly overbought': 90,
            'overbought': 75,
            'slightly overbought': 65,
            'normal': 50,
            'slightly oversold': 35,
            'oversold': 25,
            'strongly oversold': 10
        }.get(market_condition.lower(), 50)

        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = market_condition_value,
            title = {'text': "Market Condition"},
            gauge = {
                'axis': {'range': [0, 100]},
                'bar': {'color': condition_color},
                'steps': [
                    {'range': [0, 30], 'color': 'rgba(0, 128, 0, 0.2)'},  # Oversold - green
                    {'range': [30, 45], 'color': 'rgba(144, 238, 144, 0.2)'},
                    {'range': [45, 55], 'color': 'rgba(220, 220, 220, 0.2)'},  # Normal - gray
                    {'range': [55, 70], 'color': 'rgba(255, 165, 0, 0.2)'},
                    {'range': [70, 100], 'color': 'rgba(255, 0, 0, 0.2)'}  # Overbought - red
                ]
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # Key Market Observations with icons
    st.subheader("Key Market Observations")
    observations = market_overview.get("key_observations", [])

    if observations:
        for i, observation in enumerate(observations):
            icon = "🔍" if i % 4 == 0 else "📊" if i % 4 == 1 else "💡" if i % 4 == 2 else "⚡"
            st.markdown(f"{icon} {observation}")
    else:
        st.info("No key market observations available")

    # Market Signals Dashboard
    if "market_signals" in market_overview:
        st.subheader("Market Signals Dashboard")

        signals = market_overview.get("market_signals", {})
        signal_types = ['bullish', 'bearish', 'neutral']

        # Create three columns for signal types
        cols = st.columns(3)

        for i, signal_type in enumerate(signal_types):
            with cols[i]:
                st.markdown(f"### {signal_type.title()} Signals")
                signal_list = signals.get(f"{signal_type}_signals", [])

                if signal_list:
                    for signal in signal_list:
                        st.markdown(f"- {signal}")
                else:
                    st.write(f"No {signal_type} signals detected")

    # Ticker Analysis - Enhanced with visual elements and more details
    st.markdown("---")
    st.subheader("Ticker Analysis")
    ticker_analysis = analysis_result.get("ticker_analysis", {})

    # For each ticker, create an enhanced display
    for ticker, ticker_data in ticker_analysis.items():
        # Create a card-like container for each ticker
        st.markdown(f"""
        <div style="border-radius: 10px; border: 1px solid #ccc; padding: 15px; margin-bottom: 20px;">
            <h3 style="text-align: center;">{ticker} Analysis</h3>
        </div>
        """, unsafe_allow_html=True)

        # Sentiment and recommendation in a visual way
        sentiment = ticker_data.get('sentiment', 'neutral')
        recommendation = ticker_data.get('recommendation', 'N/A')
        risk_level = ticker_data.get('risk_level', 'N/A')

        sentiment_color = {
            'bullish': 'green',
            'bearish': 'red',
            'neutral': 'blue',
            'somewhat bullish': 'lightgreen',
            'somewhat bearish': 'salmon'
        }.get(sentiment.lower(), 'blue')

        risk_color = {
            'high': 'red',
            'medium': 'orange',
            'low': 'green'
        }.get(risk_level.lower(), 'gray')

        # Create 3 columns for main metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"**Sentiment**: <span style='color:{sentiment_color};font-size:18px'>{sentiment.upper()}</span>", unsafe_allow_html=True)

        with col2:
            st.markdown(f"**Recommendation**: <span style='font-weight:bold;font-size:18px'>{recommendation}</span>", unsafe_allow_html=True)

        with col3:
            st.markdown(f"**Risk Level**: <span style='color:{risk_color};font-size:18px'>{risk_level.upper()}</span>", unsafe_allow_html=True)

        # Technical Indicators Dashboard
        if "technical_indicators" in ticker_data:
            st.markdown("### Technical Indicators")

            indicators = ticker_data.get("technical_indicators", {})

            # Create a DataFrame for technical indicators
            indicator_list = []

            for name, properties in indicators.items():
                indicator_list.append({
                    "Indicator": name.upper(),
                    "Value": properties.get("value", "N/A"),
                    "Signal": properties.get("signal", "N/A"),
                    "Interpretation": properties.get("interpretation", "N/A")
                })

            if indicator_list:
                indicator_df = pd.DataFrame(indicator_list)
                st.table(indicator_df)
            else:
                st.info("No technical indicators available")

        # Technical Signals with enhanced display
        if "technical_signals" in ticker_data:
            st.markdown("### Technical Signals")

            signals = ticker_data.get("technical_signals", [])

            # Group signals by type: bullish, bearish, or neutral
            bullish_signals = [signal for signal in signals if "bullish" in signal.lower()]
            bearish_signals = [signal for signal in signals if "bearish" in signal.lower()]
            neutral_signals = [signal for signal in signals if "bullish" not in signal.lower() and "bearish" not in signal.lower()]

            # Create columns for signal types
            if bullish_signals or bearish_signals or neutral_signals:
                cols = st.columns(3)

                with cols[0]:
                    st.markdown("#### Bullish Signals")
                    if bullish_signals:
                        for signal in bullish_signals:
                            st.markdown(f"- 🟢 {signal}")
                    else:
                        st.write("No bullish signals")

                with cols[1]:
                    st.markdown("#### Bearish Signals")
                    if bearish_signals:
                        for signal in bearish_signals:
                            st.markdown(f"- 🔴 {signal}")
                    else:
                        st.write("No bearish signals")

                with cols[2]:
                    st.markdown("#### Neutral Signals")
                    if neutral_signals:
                        for signal in neutral_signals:
                            st.markdown(f"- 🔵 {signal}")
                    else:
                        st.write("No neutral signals")
            else:
                st.info("No technical signals detected")

        # Support and Resistance Levels
        if "support_resistance" in ticker_data:
            st.markdown("### Support & Resistance")

            sr_data = ticker_data.get("support_resistance", {})

            # Current price for reference
            current_price = ticker_data.get("current_price", 0)

            # Support levels
            support_levels = sr_data.get("support_levels", [])
            resistance_levels = sr_data.get("resistance_levels", [])

            if support_levels or resistance_levels:
                # Create a price chart with support and resistance lines
                all_levels = support_levels + resistance_levels + [current_price]
                min_price = min(all_levels) * 0.95 if all_levels else 0
                max_price = max(all_levels) * 1.05 if all_levels else 100

                fig = go.Figure()

                # Add current price line
                fig.add_shape(
                    type="line",
                    x0=0, x1=1,
                    y0=current_price, y1=current_price,
                    line=dict(color="blue", width=2, dash="solid"),
                )

                # Add annotation for current price
                fig.add_annotation(
                    x=0.5, y=current_price,
                    text=f"Current: ${current_price:.2f}",
                    showarrow=False,
                    yshift=10,
                    bgcolor="rgba(255, 255, 255, 0.8)"
                )

                # Add support levels
                for level in support_levels:
                    fig.add_shape(
                        type="line",
                        x0=0, x1=1,
                        y0=level, y1=level,
                        line=dict(color="green", width=1.5, dash="dash"),
                    )
                    fig.add_annotation(
                        x=0.2, y=level,
                        text=f"Support: ${level:.2f}",
                        showarrow=False,
                        yshift=-15,
                        bgcolor="rgba(144, 238, 144, 0.8)"
                    )

                # Add resistance levels
                for level in resistance_levels:
                    fig.add_shape(
                        type="line",
                        x0=0, x1=1,
                        y0=level, y1=level,
                        line=dict(color="red", width=1.5, dash="dash"),
                    )
                    fig.add_annotation(
                        x=0.8, y=level,
                        text=f"Resistance: ${level:.2f}",
                        showarrow=False,
                        yshift=15,
                        bgcolor="rgba(255, 200, 200, 0.8)"
                    )
                
                # Configure chart layout
                fig.update_layout(
                    title=f"{ticker} Support & Resistance Levels",
                    xaxis=dict(
                        showgrid=False,
                        zeroline=False,
                        showticklabels=False
                    ),
                    yaxis=dict(
                        range=[min_price, max_price],
                        title="Price ($)"
                    ),
                    height=400,
                    margin=dict(l=20, r=20, t=50, b=20),
                    showlegend=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No support and resistance levels detected")
        
        # Price Targets with visual elements
        if "price_target" in ticker_data:
            st.markdown("### Price Targets")
            
            price_target = ticker_data.get("price_target", {})
            current_price = ticker_data.get("current_price", 0)
            
            if current_price and (price_target.get('short_term') or price_target.get('long_term')):
                col1, col2 = st.columns(2)
                
                with col1:
                    short_term = price_target.get('short_term')
                    if short_term:
                        # Calculate percentage change
                        try:
                            short_term_value = float(short_term) if isinstance(short_term, (int, float, str)) else 0
                            pct_change = ((short_term_value - current_price) / current_price) * 100
                            delta_color = "normal" if abs(pct_change) < 1 else "off" if pct_change < 0 else "inverse"
                            st.metric("Short-term Target", f"${short_term_value:.2f}", f"{pct_change:.2f}%", delta_color=delta_color)
                        except (ValueError, TypeError):
                            st.metric("Short-term Target", f"${short_term}")
                    else:
                        st.metric("Short-term Target", "N/A")
                
                with col2:
                    long_term = price_target.get('long_term')
                    if long_term:
                        # Calculate percentage change
                        try:
                            long_term_value = float(long_term) if isinstance(long_term, (int, float, str)) else 0
                            pct_change = ((long_term_value - current_price) / current_price) * 100
                            delta_color = "normal" if abs(pct_change) < 1 else "off" if pct_change < 0 else "inverse"
                            st.metric("Long-term Target", f"${long_term_value:.2f}", f"{pct_change:.2f}%", delta_color=delta_color)
                        except (ValueError, TypeError):
                            st.metric("Long-term Target", f"${long_term}")
                    else:
                        st.metric("Long-term Target", "N/A")
                
                # Add notes if available
                if "note" in price_target:
                    st.info(f"**Note**: {price_target['note']}")
            else:
                st.info("No price targets available")
        
        # Key Insights with enhanced styling
        if "key_insights" in ticker_data:
            st.markdown("### Key Insights")
            
            insights = ticker_data.get("key_insights", [])
            
            if insights:
                # Create a card-like container for insights
                insights_html = "<div style='background-color: #f8f9fa; padding: 15px; border-radius: 5px;'>"
                
                for i, insight in enumerate(insights):
                    icon = "🎯" if i % 5 == 0 else "💰" if i % 5 == 1 else "📈" if i % 5 == 2 else "⚠️" if i % 5 == 3 else "💡"
                    insights_html += f"<p style='margin-bottom: 10px;'>{icon} {insight}</p>"
                
                insights_html += "</div>"
                st.markdown(insights_html, unsafe_allow_html=True)
            else:
                st.info("No key insights available")
    
    # Trading Opportunities - Enhanced with visual elements
    st.markdown("---")
    st.subheader("Trading Opportunities")
    opportunities = analysis_result.get("trading_opportunities", [])
    
    if opportunities:
        for opportunity in opportunities:
            # Create a colorful card based on the strategy type
            strategy = opportunity.get('strategy', 'N/A')
            ticker = opportunity.get('ticker', 'N/A')
            
            # Determine card color based on strategy type
            card_color = "#d1e7dd"  # Default light green
            if "short" in strategy.lower():
                card_color = "#f8d7da"  # Light red for short strategies
            elif "neutral" in strategy.lower() or "income" in strategy.lower():
                card_color = "#cff4fc"  # Light blue for neutral/income strategies
            
            # Create the card header
            st.markdown(f"""
            <div style="background-color: {card_color}; padding: 15px; border-radius: 10px 10px 0 0; margin-bottom: 0px;">
                <h3 style="margin: 0;">{ticker} - {strategy}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # Create the card body
            st.markdown(f"""
            <div style="border: 1px solid {card_color}; padding: 15px; border-radius: 0 0 10px 10px; margin-bottom: 20px;">
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                time_horizon = opportunity.get('time_horizon', 'N/A')
                risk_reward = opportunity.get('risk_reward_ratio', 'N/A')
                
                st.markdown(f"**Time Horizon**: {time_horizon}")
                st.markdown(f"**Risk/Reward Ratio**: {risk_reward}")
                
                # Add entry/exit points if available
                if "entry_point" in opportunity:
                    st.markdown(f"**Entry Point**: ${opportunity['entry_point']}")
                
                if "exit_point" in opportunity:
                    st.markdown(f"**Exit Point**: ${opportunity['exit_point']}")
                
                if "stop_loss" in opportunity:
                    st.markdown(f"**Stop Loss**: ${opportunity['stop_loss']}")
            
            with col2:
                st.markdown("**Rationale:**")
                rationale = opportunity.get('rationale', 'No rationale provided')
                st.markdown(f"<div style='background-color: #f8f9fa; padding: 10px; border-radius: 5px;'>{rationale}</div>", unsafe_allow_html=True)
            
            # Close the card div
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No trading opportunities identified")
    
    # Overall Recommendation with emphasis
    st.markdown("---")
    st.subheader("Overall Recommendation")
    
    recommendation = analysis_result.get('overall_recommendation', 'N/A')
    
    st.markdown(f"""
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #0d6efd;">
        <p style="font-size: 18px; font-weight: bold;">{recommendation}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Feedback Information with visual enhancements
    if "feedback" in analysis_result:
        st.markdown("---")
        st.header("Feedback Loop Information")
        feedback = analysis_result["feedback"]
        
        col1, col2 = st.columns(2)
        
        with col1:
            contradictions = feedback.get('contradictions_detected', 0)
            st.metric("Contradictions Detected", contradictions, delta=None, delta_color="inverse")
        
        with col2:
            confidence = feedback.get('confidence', 0)
            st.metric("Analysis Confidence", f"{confidence}%", delta=None)
        
        # Changes Made with colorful styling
        st.subheader("Changes Made")
        changes = feedback.get("changes_made", [])
        
        if changes:
            for change in changes:
                st.markdown(f"🔄 {change}")
        else:
            st.info("No changes were made during the feedback loop")
        
        # Overall Assessment
        st.subheader("Overall Assessment")
        assessment = feedback.get('overall_assessment', 'N/A')
        
        st.markdown(f"""
        <div style="background-color: #e2e3e5; padding: 15px; border-radius: 5px;">
            {assessment}
        </div>
        """, unsafe_allow_html=True)
        
        # Learning Points with visual styling
        if "learning_points" in feedback:
            st.subheader("Learning Points")
            
            points = feedback["learning_points"]
            if points:
                for i, point in enumerate(points):
                    icon = "💡" if i % 3 == 0 else "📚" if i % 3 == 1 else "🧠"
                    st.markdown(f"{icon} {point}")
            else:
                st.info("No learning points identified")

def display_memory_enhanced_analysis(ticker, analysis_result, historical_analyses):
    """Display memory-enhanced analysis results with historical context"""
    
    if analysis_result is None or "error" in analysis_result:
        st.error(f"Error in analysis result: {analysis_result.get('error', 'Unknown error')}")
        return

    # Market Overview Section
    st.header("Market Overview")
    if "market_overview" in analysis_result:
        market_overview = analysis_result["market_overview"]
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Market Sentiment", market_overview.get("sentiment", "N/A"))
        with col2:
            st.write("Key Market Factors:")
            for factor in market_overview.get("key_factors", []):
                st.markdown(f"- {factor}")
        with col3:
            st.write("Summary:")
            st.write(market_overview.get("summary", "N/A"))

    # Ticker Analysis Section
    st.header(f"Analysis for {ticker}")
    if "ticker_analysis" in analysis_result and ticker in analysis_result["ticker_analysis"]:
        ticker_data = analysis_result["ticker_analysis"][ticker]
        
        # Current Price and Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            current_price = ticker_data.get("current_price", 0)
            st.metric("Current Price", f"${current_price:,.2f}")
        with col2:
            st.metric("Recommendation", ticker_data.get("recommendation", "N/A"))
        with col3:
            confidence = ticker_data.get("confidence", "0")
            # Handle string percentage values
            if isinstance(confidence, str):
                try:
                    # Remove % sign if present and convert to float
                    confidence = float(confidence.strip('%')) / 100
                except ValueError:
                    confidence = 0
            st.metric("Confidence", f"{confidence*100:.1f}%")

        # Risk Assessment
        if "risk_assessment" in ticker_data:
            risk = ticker_data["risk_assessment"]
            st.subheader("Risk Assessment")
            col1, col2 = st.columns(2)
            with col1:
                risk_level = risk.get("overall_risk", "N/A")
                st.metric("Risk Level", risk_level)
            with col2:
                st.write("Risk Factors:")
                for factor in risk.get("factors", []):
                    st.markdown(f"- {factor}")

        # Price Targets
        if "price_targets" in ticker_data:
            st.subheader("Price Targets")
            targets = ticker_data["price_targets"]
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("Short Term:")
                short_term = targets.get("short_term", {})
                st.metric("Target", f"${short_term.get('target', 0):,.2f}")
                st.write(f"Timeframe: {short_term.get('timeframe', 'N/A')}")
                st.write(f"Confidence: {short_term.get('confidence', 'N/A')}")
            
            with col2:
                st.write("Long Term:")
                long_term = targets.get("long_term", {})
                st.metric("Target", f"${long_term.get('target', 0):,.2f}")
                st.write(f"Timeframe: {long_term.get('timeframe', 'N/A')}")
                st.write(f"Confidence: {long_term.get('confidence', 'N/A')}")

    # Trading Opportunities
    if "trading_opportunities" in analysis_result:
        st.header("Trading Opportunities")
        for opportunity in analysis_result["trading_opportunities"]:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Type**: {opportunity.get('type', 'N/A')}")
                st.markdown(f"**Entry Point**: ${opportunity.get('entry_point', 'N/A')}")
                st.markdown(f"**Target**: ${opportunity.get('target', 'N/A')}")
                st.markdown(f"**Stop Loss**: ${opportunity.get('stop_loss', 'N/A')}")
                st.markdown(f"**Time Horizon**: {opportunity.get('time_horizon', 'N/A')}")
                st.markdown(f"**Risk/Reward**: {opportunity.get('risk_reward_ratio', 'N/A')}")
            with col2:
                st.markdown("**Rationale:**")
                st.write(opportunity.get('rationale', 'N/A'))

    # Historical Analysis Section
    if historical_analyses:
        st.header("Historical Analysis")
        
        # Convert to DataFrame for easier manipulation
        analysis_records = []
        for analysis in historical_analyses:
            try:
                analysis_data = analysis.get('analysis_data', {})
                if isinstance(analysis_data, str):
                    analysis_data = json.loads(analysis_data)
                
                record = {
                    'timestamp': pd.to_datetime(analysis['timestamp']),
                    'current_price': analysis_data.get('current_price', 0.0),
                    'recommendation': analysis_data.get('recommendation', 'N/A'),
                    'confidence': analysis_data.get('confidence', 0.0),
                    'risk_level': analysis_data.get('risk_level', 'N/A'),
                    'market_sentiment': analysis_data.get('market_sentiment', 'N/A'),
                    'accuracy_score': analysis_data.get('accuracy_score', 0.0)
                }
                analysis_records.append(record)
            except Exception as e:
                st.warning(f"Error processing historical analysis: {str(e)}")
                continue

        if analysis_records:
            df = pd.DataFrame(analysis_records)
            df = df.sort_values('timestamp')

            # Display historical analysis table
            st.dataframe(df)

            # Plot if we have multiple data points
            if len(df) > 1:
                st.line_chart(df.set_index('timestamp')['current_price'])

    # Memory Information
    if "memory_context" in analysis_result:
        st.header("Memory Information")
        st.write(analysis_result["memory_context"])

    # Learning Points
    if "learning_points" in analysis_result:
        st.header("Learning Points")
        for point in analysis_result["learning_points"]:
            st.markdown(f"- {point}")

    # Feedback Form
    st.header("Feedback")
    feedback_type = st.selectbox("Feedback Type", ["Accuracy", "Usefulness", "Clarity"])
    feedback_text = st.text_area("Your Feedback")
    if st.button("Submit Feedback"):
        if "analysis_id" in analysis_result:
            try:
                # Re-instantiate MemoryEnhancedAnalysis to access the method
                # This assumes it's safe to re-instantiate or uses a shared instance mechanism
                # In a real app, you might pass the instance or use a singleton
                from src.llm.memory_enhanced_analysis import MemoryEnhancedAnalysis # Import here if not globally available
                memory_analyzer = MemoryEnhancedAnalysis()
                memory_analyzer.add_user_feedback(
                    analysis_result["analysis_id"],
                    feedback_type.lower(),
                    feedback_text
                )
                st.success("Feedback submitted successfully!")
            except Exception as e:
                st.error(f"Error submitting feedback: {str(e)}")
        else:
            st.error("No analysis ID found. Feedback cannot be submitted.")

def create_technical_chart(ticker, historical_data: Optional[pd.DataFrame], analysis_result: Optional[Dict]):
    """Create a technical chart with AI-identified labels and indicators using provided historical data"""
    st.subheader(f"Technical Analysis Chart for {ticker}")

    # Validate provided historical data
    if historical_data is None or historical_data.empty:
        st.error(f"No historical data provided for {ticker}. Cannot create chart.")
        return
    else:
        # Make a copy to avoid modifying the original DataFrame passed from main app
        df = historical_data.copy()
        logger.info(f"Using provided historical data ({len(df)} rows) for chart.")
        # Ensure 'Date' is the index if it's not already (yfinance usually returns with Date index)
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'Date' in df.columns:
                 df['Date'] = pd.to_datetime(df['Date'])
                 df = df.set_index('Date')
            else:
                 st.error("Historical data must have a 'Date' column or DatetimeIndex.")
                 return
        # Reset index to use 'Date' as a column for plotting
        df = df.reset_index()


    if analysis_result is None:
        st.warning("No analysis result available. Chart will be created with limited indicators.")
    elif "error" in analysis_result:
        st.warning(f"Error in analysis result: {analysis_result['error']}. Chart will be created with limited indicators.")

    # Add timeframe selection - Note: This now only controls display, not data fetching
    # Keep it for user context, but maybe disable or adjust its meaning?
    # For now, keep it as is.
    timeframe_options = {
        "1 Month": "1mo",
        "3 Months": "3mo",
        "6 Months": "6mo",
        "1 Year": "1y",
        "2 Years": "2y",
        "5 Years": "5y",
        "Max": "max"
    }

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        # We might want to get the original timeframe from analysis_result if possible?
        # selected_timeframe = st.selectbox("Select Timeframe", list(timeframe_options.keys()), index=1)
        st.text(f"Data Timeframe: Based on Analysis") # Indicate data timeframe is fixed

    with col2:
        chart_type = st.selectbox("Chart Type", ["Candlestick", "Line", "OHLC"], index=0)

    with col3:
        show_volume = st.checkbox("Show Volume", value=True)

    # Technical indicator selection
    indicator_options = st.multiselect(
        "Select Technical Indicators",
        ["Moving Averages", "Bollinger Bands", "RSI", "MACD", "Support/Resistance"],
        default=["Moving Averages", "Bollinger Bands", "Support/Resistance"]
    )

    try:
        # REMOVED: yfinance import check and data fetching logic
        # ticker_data = yf.Ticker(ticker)
        # df = ticker_data.history(period=yf_timeframe)
        # ... error handling ...
        # df = df.reset_index()
        # df['Date'] = pd.to_datetime(df['Date'])

        # Calculate technical indicators ON THE PROVIDED df
        if "Moving Averages" in indicator_options:
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA50'] = df['Close'].rolling(window=50).mean()
            df['MA200'] = df['Close'].rolling(window=200).mean()
        
        if "Bollinger Bands" in indicator_options:
            # Ensure MA20 is calculated if not already
            if 'MA20' not in df.columns:
                df['MA20'] = df['Close'].rolling(window=20).mean()
            df['20dSTD'] = df['Close'].rolling(window=20).std()
            df['Upper'] = df['MA20'] + (df['20dSTD'] * 2)
            df['Lower'] = df['MA20'] - (df['20dSTD'] * 2)
        
        if "RSI" in indicator_options:
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).fillna(0)
            loss = -delta.where(delta < 0, 0).fillna(0)
            avg_gain = gain.rolling(window=14, min_periods=1).mean()
            avg_loss = loss.rolling(window=14, min_periods=1).mean()
            # Avoid division by zero
            rs = avg_gain / avg_loss.replace(0, 1e-6) # Replace 0 avg_loss with small value
            df['RSI'] = 100 - (100 / (1 + rs))
            df['RSI'] = df['RSI'].fillna(50) # Fill initial NaNs with neutral 50
        
        if "MACD" in indicator_options:
            exp1 = df['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            df['Histogram'] = df['MACD'] - df['Signal']
        
        # Create the chart based on selected type
        fig = go.Figure()
        
        try:
            if chart_type == "Candlestick":
                fig.add_trace(go.Candlestick(
                    x=df['Date'],
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    name='Price'
                ))
            elif chart_type == "OHLC":
                fig.add_trace(go.Ohlc(
                    x=df['Date'],
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    name='Price'
                ))
            else:  # Line chart
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['Close'],
                    mode='lines',
                    name='Close Price',
                    line=dict(color='blue', width=2)
                ))
            
            # Add technical indicators
            if "Moving Averages" in indicator_options and 'MA20' in df.columns and 'MA50' in df.columns and 'MA200' in df.columns:
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['MA20'],
                    mode='lines',
                    name='20-day MA',
                    line=dict(color='orange', width=1)
                ))
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['MA50'],
                    mode='lines',
                    name='50-day MA',
                    line=dict(color='green', width=1)
                ))
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['MA200'],
                    mode='lines',
                    name='200-day MA',
                    line=dict(color='red', width=1)
                ))
            
            if "Bollinger Bands" in indicator_options and 'Upper' in df.columns and 'Lower' in df.columns:
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['Upper'],
                    mode='lines',
                    name='Upper Band',
                    line=dict(color='gray', width=1, dash='dash')
                ))
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['Lower'],
                    mode='lines',
                    name='Lower Band',
                    line=dict(color='gray', width=1, dash='dash'),
                    fill='tonexty',
                    fillcolor='rgba(128,128,128,0.1)' # Add light fill color
                ))
            
            # Add volume if selected
            if show_volume and 'Volume' in df.columns:
                fig.add_trace(go.Bar(
                    x=df['Date'],
                    y=df['Volume'],
                    name='Volume',
                    marker_color='rgba(0, 0, 255, 0.3)',
                    opacity=0.3,
                    yaxis='y2' # Assign to secondary y-axis
                ))
            
            # Add support and resistance levels if selected
            if "Support/Resistance" in indicator_options and analysis_result and "key_indicators" in analysis_result:
                sr_levels = analysis_result.get("support_resistance", {})
                
                # Add support levels
                for level in sr_levels.get("support_levels", []):
                    if isinstance(level, (int, float)):
                        fig.add_hline(
                            y=level,
                            line_dash="dash",
                            line_color="green",
                            annotation_text=f"Support: ${level:.2f}"
                        )
                
                # Add resistance levels
                for level in sr_levels.get("resistance_levels", []):
                     if isinstance(level, (int, float)):
                        fig.add_hline(
                            y=level,
                            line_dash="dash",
                            line_color="red",
                            annotation_text=f"Resistance: ${level:.2f}"
                        )
            
            # Determine layout domains based on selected indicators
            domain_primary = [0.25, 1.0]
            domain_rsi = [0, 0.2] if "RSI" in indicator_options else None
            domain_macd = [0, 0.2] if "MACD" in indicator_options and not domain_rsi else ([0.25, 0.45] if "MACD" in indicator_options and domain_rsi else None)
            
            if domain_rsi or domain_macd:
                if domain_rsi and domain_macd:
                    domain_primary = [0.5, 1.0]
                else:
                    domain_primary = [0.25, 1.0]
            
            # Update layout - Use timeframe from analysis_result
            chart_timeframe = analysis_result.get("timeframe", "Unknown Timeframe") if analysis_result else "Unknown Timeframe"
            layout_settings = {
                # "title": f"{ticker} Technical Analysis Chart ({timeframe_options[selected_timeframe]})",
                "title": f"{ticker} Technical Analysis Chart ({chart_timeframe})", # Use timeframe from results
                "xaxis_title": "Date",
                "yaxis": dict(title="Price ($)", domain=domain_primary),
                "height": 600,
                "xaxis_rangeslider_visible": False,
                "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            }
            
            if show_volume and 'Volume' in df.columns:
                layout_settings["yaxis2"] = dict(
                    title="Volume",
                    overlaying="y",
                    side="right",
                    showgrid=False,
                    domain=domain_primary # Align volume with primary chart
                )
            
            if domain_rsi:
                layout_settings["yaxis3"] = dict(
                    title="RSI",
                    range=[0, 100],
                    domain=domain_rsi,
                    showgrid=True, # Add grid for RSI
                    gridcolor='rgba(128,128,128,0.2)'
                )
            
            if domain_macd:
                layout_settings["yaxis4"] = dict(
                    title="MACD",
                    domain=domain_macd,
                    showgrid=True, # Add grid for MACD
                    gridcolor='rgba(128,128,128,0.2)'
                )
            
            fig.update_layout(**layout_settings)

            # Add RSI trace and shapes if selected
            if domain_rsi and 'RSI' in df.columns:
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['RSI'],
                    mode='lines',
                    name='RSI',
                    yaxis='y3'
                ))
                # Add RSI reference lines
                fig.add_shape(type="line", y0=70, y1=70, x0=df['Date'].iloc[0], x1=df['Date'].iloc[-1], line=dict(color="red", width=1, dash="dash"), yref='y3')
                fig.add_shape(type="line", y0=30, y1=30, x0=df['Date'].iloc[0], x1=df['Date'].iloc[-1], line=dict(color="green", width=1, dash="dash"), yref='y3')
            
            # Add MACD trace if selected
            if domain_macd and 'MACD' in df.columns and 'Signal' in df.columns and 'Histogram' in df.columns:
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['MACD'],
                    mode='lines',
                    name='MACD',
                    yaxis='y4',
                    line=dict(color='blue')
                ))
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df['Signal'],
                    mode='lines',
                    name='Signal',
                    yaxis='y4',
                    line=dict(color='orange')
                ))
                # Add MACD Histogram Bar chart
                fig.add_trace(go.Bar(
                    x=df['Date'],
                    y=df['Histogram'],
                    name='Histogram',
                    yaxis='y4',
                    marker_color=np.where(df['Histogram'] > 0, 'green', 'red') # Color bars based on value
                ))
                # Add zero line for MACD
                fig.add_shape(type="line", y0=0, y1=0, x0=df['Date'].iloc[0], x1=df['Date'].iloc[-1], line=dict(color="gray", width=1, dash="dash"), yref='y4')
            
            # Display the chart
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error creating chart visualization: {str(e)}")
            logger.error(f"Chart creation error: {str(e)}", exc_info=True)
            return
            
    except Exception as e:
        st.error(f"Error in technical chart creation: {str(e)}")
        logger.error(f"Technical chart error: {str(e)}", exc_info=True)
        return

def display_technical_analysis(analysis_result: dict):
    """Display the technical analysis results in a structured format"""
    st.header("LLM-Powered Technical Analysis")

    if "error" in analysis_result:
        st.error(f"Error in technical analysis: {analysis_result['error']}")
        if "raw_response" in analysis_result:
            with st.expander("Raw LLM Response"):
                st.code(analysis_result["raw_response"])
        return

    # Summary Section
    st.subheader("Analysis Summary")
    summary_data = analysis_result.get("summary", {})

    col1, col2 = st.columns(2)

    with col1:
        overall_signal = summary_data.get("overall_signal", "neutral")
        signal_color = {
            "strong buy": "#006400", # Dark Green
            "buy": "green",
            "hold": "blue",
            "sell": "red",
            "strong sell": "#8B0000" # Dark Red
        }.get(overall_signal.lower(), "blue")

        st.markdown(f"### Signal: <span style='color:{signal_color};font-size:24px'>{overall_signal.upper()}</span>", unsafe_allow_html=True)

    with col2:
        confidence = summary_data.get("confidence", "medium")
        confidence_value = {"low": 30, "medium": 60, "high": 90}.get(confidence.lower(), 60)

        # Gauge for confidence
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=confidence_value,
            title={'text': "Confidence Level"},
            gauge={
                'axis': {'range': [None, 100], 'tickvals': [15, 50, 85], 'ticktext': ['Low', 'Medium', 'High']},
                'bar': {'color': signal_color},
                'steps': [
                    {'range': [0, 40], 'color': 'lightgray'},
                    {'range': [40, 70], 'color': 'gray'},
                    {'range': [70, 100], 'color': 'darkgray'}
                ]
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # Key Takeaways
    st.markdown("**Key Takeaways:**")
    key_takeaways = summary_data.get("key_takeaways", [])
    if key_takeaways:
        for takeaway in key_takeaways:
            st.markdown(f"- {takeaway}")
    else:
        st.write("No specific takeaways provided.")

    # Outlook
    st.markdown("**Outlook:**")
    st.write(summary_data.get("outlook", "No specific outlook provided."))

    # Technical Indicator Analysis
    st.markdown("---")
    st.subheader("Technical Indicators Analysis")
    indicators_data = analysis_result.get("key_indicators", {})

    # Create columns for better layout
    cols = st.columns(2)
    indicator_keys = list(indicators_data.keys())

    for i, key in enumerate(indicator_keys):
        with cols[i % 2]:
            data = indicators_data[key]
            st.markdown(f"**{key.upper()}**")
            if isinstance(data, dict):
                # Display value/signal if present
                value_display = []
                if "value" in data and data["value"] is not None:
                    try:
                        value_display.append(f"Value: {float(data['value']):.2f}")
                    except (TypeError, ValueError):
                        value_display.append(f"Value: {data['value']}")
                if "signal" in data and data["signal"] is not None:
                     try:
                        value_display.append(f"Signal: {float(data['signal']):.2f}")
                     except (TypeError, ValueError):
                         value_display.append(f"Signal: {data['signal']}")
                if value_display:
                     st.markdown(", ".join(value_display))
                
                # Display interpretation
                interpretation = data.get("interpretation", "N/A")
                st.markdown(f"*Interpretation:* {interpretation}")
            else:
                 st.markdown(f"*Interpretation:* {data}") # Handle cases where it might just be a string
            st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px;'>", unsafe_allow_html=True)

    # Chart Patterns
    st.markdown("---")
    st.subheader("Chart Patterns")
    patterns_data = analysis_result.get("chart_patterns", {})
    
    identified_patterns = patterns_data.get("identified_patterns", [])
    st.markdown("**Identified Patterns:**")
    if identified_patterns and identified_patterns != ['None']:
        for pattern in identified_patterns:
            st.markdown(f"- {pattern}")
    else:
        st.write("No significant chart patterns identified.")
        
    st.markdown("**Pattern Analysis:**")
    st.write(patterns_data.get("pattern_analysis", "No detailed pattern analysis provided."))

    # Support and Resistance
    st.markdown("---")
    st.subheader("Support & Resistance")
    sr_data = analysis_result.get("support_resistance", {})
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Support Levels:**")
        support_levels = sr_data.get("support_levels", [])
        if support_levels:
            for level in support_levels:
                 st.markdown(f"- ${level:.2f}" if isinstance(level, (int, float)) else f"- {level}")
        else:
             st.write("None identified")
            
    with col2:
        st.markdown("**Resistance Levels:**")
        resistance_levels = sr_data.get("resistance_levels", [])
        if resistance_levels:
            for level in resistance_levels:
                st.markdown(f"- ${level:.2f}" if isinstance(level, (int, float)) else f"- {level}")
        else:
             st.write("None identified")
             
    st.markdown("**Level Analysis:**")
    st.write(sr_data.get("level_analysis", "No detailed level analysis provided."))
    
    # Raw Indicators (Optional Display)
    if "raw_indicators" in analysis_result:
        with st.expander("Raw Indicator Values"):
            st.json(analysis_result["raw_indicators"])


def display_price_targets(price_targets, ticker):
    """
    Display price targets in a visually appealing way
    Supports both traditional price targets format and the new LLM-specialized format
    
    Args:
        price_targets: Dictionary with price targets data
        ticker: Stock ticker symbol
    """
    st.subheader(f"📊 Price Targets for {ticker}")
    
    # Check for errors first
    if isinstance(price_targets, dict) and "error" in price_targets:
        st.error(f"Error generating price targets: {price_targets['error']}")
        return
    if price_targets is None:
        st.error("Price target data is missing.")
        return
        
    # Check if we have the LLM specialized format (primary_forecast field indicates this)
    is_llm_specialized = isinstance(price_targets, dict) and "primary_forecast" in price_targets
    
    # Get current price
    current_price = price_targets.get("current_price", 0)
    
    if not current_price or not isinstance(current_price, (int, float)) or current_price <= 0:
        st.warning("Current price information not available or invalid. Cannot display percentage changes.")
        current_price = None # Set to None to skip percentage calcs
        
    # Display header metrics - formatted based on which data structure we have
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Primary forecast or consensus target
        if is_llm_specialized:
            primary = price_targets.get("primary_forecast", {})
            target_price = primary.get("target_price", None)
            if target_price is not None:
                target_pct = ((target_price - current_price) / current_price) * 100 if current_price else None
                direction = primary.get("direction", "neutral")
                
                # Format the delta based on direction
                delta_text = f"{target_pct:.2f}% ({direction})" if target_pct is not None else direction.capitalize()
                st.metric(
                    "Primary Target", 
                    f"${target_price:.2f}", 
                    delta_text,
                    delta_color="normal" if direction == "neutral" else ("off" if direction == "bearish" else "normal")
                )
            else:
                st.metric("Primary Target", "Not available")
        else:
            # Use short-term consensus if available from traditional method
            short_term = price_targets.get("targets", {}).get("short_term", {})
            consensus = short_term.get("consensus", {})
            
            if consensus:
                bullish = consensus.get("bullish", None)
                if bullish is not None:
                    bullish_pct = ((bullish - current_price) / current_price) * 100 if current_price else None
                    st.metric("Short-Term Target", f"${bullish:.2f}", f"{bullish_pct:.2f}%" if bullish_pct is not None else None)
                else:
                     st.metric("Short-Term Target", "Not available")
            else:
                st.metric("Short-Term Target", "Not available")
    
    with col2:
        if is_llm_specialized:
            # Display conviction level from LLM
            confidence = price_targets.get("primary_forecast", {}).get("confidence", 0)
            st.metric("Analyst Conviction", f"{confidence}%")
        else:
            # Use medium-term consensus if available from traditional method
            medium_term = price_targets.get("targets", {}).get("medium_term", {})
            consensus = medium_term.get("consensus", {})
            
            if consensus:
                bullish = consensus.get("bullish", None)
                if bullish is not None:
                    bullish_pct = ((bullish - current_price) / current_price) * 100 if current_price else None
                    st.metric("Medium-Term Target", f"${bullish:.2f}", f"{bullish_pct:.2f}%" if bullish_pct is not None else None)
                else:
                     st.metric("Medium-Term Target", "Not available")
            else:
                st.metric("Medium-Term Target", "Not available")
    
    with col3:
        if is_llm_specialized:
            # Display timeframe and potential return
            timeframe = price_targets.get("primary_forecast", {}).get("timeframe", "Unknown")
            potential_return = price_targets.get("primary_forecast", {}).get("potential_return", None)
            st.metric("Timeframe", timeframe, f"{potential_return:.2f}%" if potential_return is not None else None)
        elif current_price:
            # Current price reference for traditional method
            st.metric("Current Price", f"${current_price:.2f}")
            
    # Visual representation of price targets
    st.markdown("### Price Target Ranges")
    
    # Handle different data formats
    if is_llm_specialized:
        # Create tabs for different timeframes from LLM specialized format
        short_tab, medium_tab = st.tabs(["Short-Term", "Medium-Term"])
        
        with short_tab:
            short_term_data = price_targets.get("price_targets", {}).get("short_term", {})
            if short_term_data:
                _display_target_range_tab(short_term_data, current_price, "Short-Term")
            else:
                st.info("No short-term price target data available.")

        with medium_tab:
            medium_term_data = price_targets.get("price_targets", {}).get("medium_term", {})
            if medium_term_data:
                 _display_target_range_tab(medium_term_data, current_price, "Medium-Term")
            else:
                st.info("No medium-term price target data available.")
                
        # Display Key Drivers and Methodology
        st.markdown("### Key Drivers")
        key_drivers = price_targets.get("key_drivers", [])
        if key_drivers:
            for driver in key_drivers:
                st.markdown(f"- {driver}")
        else:
            st.write("No key drivers specified.")
            
        with st.expander("Analysis Methodology"):
            methodology = price_targets.get("analysis_methodology", {})
            st.json(methodology)
            
        st.markdown("### Market Context")
        st.write(price_targets.get("market_context", "No market context provided."))

    else: # Traditional format
        st.write("Displaying targets based on combined methodologies.")
        
        # Create tabs for different timeframes
        short_tab, medium_tab = st.tabs(["Short-Term (Consensus)", "Medium-Term (Consensus)"])
        
        with short_tab:
            short_term_targets = price_targets.get("targets", {}).get("short_term", {})
            _display_consensus_tab(short_term_targets, current_price, "Short-Term")

        with medium_tab:
            medium_term_targets = price_targets.get("targets", {}).get("medium_term", {})
            _display_consensus_tab(medium_term_targets, current_price, "Medium-Term")

        # Show contributing methodologies
        with st.expander("Methodologies Used"):
            methods = price_targets.get("methodologies", [])
            if methods:
                 for method in methods:
                     st.markdown(f"- {method.replace('_', ' ').title()}")
            else:
                 st.write("No specific methodologies listed.")


def _display_target_range_tab(target_data: Dict, current_price: Optional[float], timeframe_name: str):
    """Helper function to display price target data for a specific timeframe (LLM format)."""
    if not target_data:
        st.info(f"No {timeframe_name} price target data available.")
        return

    # Display key metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        bullish = target_data.get("bullish_target", None)
        if bullish is not None:
            bullish_pct = ((bullish - current_price) / current_price) * 100 if current_price else None
            st.metric("Bullish Target", f"${bullish:.2f}", f"{bullish_pct:.2f}%" if bullish_pct is not None else None)
        else:
            st.metric("Bullish Target", "N/A")
    
    with col2:
        expected = target_data.get("expected_target", None)
        if expected is not None:
            expected_pct = ((expected - current_price) / current_price) * 100 if current_price else None
            st.metric("Expected Target", f"${expected:.2f}", f"{expected_pct:.2f}%" if expected_pct is not None else None)
        else:
            st.metric("Expected Target", "N/A")
        
    with col3:
        bearish = target_data.get("bearish_target", None)
        if bearish is not None:
            bearish_pct = ((bearish - current_price) / current_price) * 100 if current_price else None
            st.metric("Bearish Target", f"${bearish:.2f}", f"{bearish_pct:.2f}%" if bearish_pct is not None else None)
        else:
             st.metric("Bearish Target", "N/A")
             
    st.write(f"**Timeframe:** {target_data.get('timeframe', 'N/A')}")
    st.write(f"**Confidence:** {target_data.get('confidence', 'N/A')}%" if target_data.get('confidence') is not None else "N/A")

    # --- Visualization --- 
    if current_price is not None and (bullish is not None or expected is not None or bearish is not None):
        fig = go.Figure()
        
        # Add current price line
        fig.add_shape(type="line", x0=0, x1=1, y0=current_price, y1=current_price, line=dict(color="blue", width=2, dash="solid"))
        
        # Add targets
        targets_to_plot = []
        if bullish is not None: targets_to_plot.append(("Bullish", bullish, "green"))
        if expected is not None: targets_to_plot.append(("Expected", expected, "orange"))
        if bearish is not None: targets_to_plot.append(("Bearish", bearish, "red"))
        
        # Determine plot range
        all_values = [current_price] + [t[1] for t in targets_to_plot]
        min_val = min(all_values) * 0.98
        max_val = max(all_values) * 1.02
        
        # Add target lines and annotations
        for name, value, color in targets_to_plot:
            pct = ((value - current_price) / current_price) * 100
            fig.add_shape(type="line", x0=0.2, x1=0.8, y0=value, y1=value, line=dict(color=color, width=2, dash="dash"))
            fig.add_annotation(x=0.9, y=value, text=f"{name}: ${value:.2f} ({pct:.1f}%)", showarrow=False, align="left")

        # Add current price annotation
        fig.add_annotation(x=0.1, y=current_price, text=f"Current: ${current_price:.2f}", showarrow=False, align="right")

        # Add Key Levels
        key_levels = target_data.get("key_levels", {})
        support = key_levels.get("support", [])
        resistance = key_levels.get("resistance", [])
        invalidation = key_levels.get("invalidation", None)

        for level in support:
            if isinstance(level, (int, float)):
                fig.add_shape(type="line", x0=0.2, x1=0.8, y0=level, y1=level, line=dict(color="lightgreen", width=1.5, dash="dot"))
                fig.add_annotation(x=0.15, y=level, text=f"Support: ${level:.2f}", showarrow=False, align="right", font=dict(size=10, color="green"))

        for level in resistance:
             if isinstance(level, (int, float)):
                fig.add_shape(type="line", x0=0.2, x1=0.8, y0=level, y1=level, line=dict(color="lightcoral", width=1.5, dash="dot"))
                fig.add_annotation(x=0.85, y=level, text=f"Resistance: ${level:.2f}", showarrow=False, align="left", font=dict(size=10, color="red"))
        
        if invalidation is not None:
             fig.add_shape(type="line", x0=0.2, x1=0.8, y0=invalidation, y1=invalidation, line=dict(color="grey", width=2, dash="longdashdot"))
             fig.add_annotation(x=0.5, y=invalidation, text=f"Invalidation: ${invalidation:.2f}", showarrow=False, align="center", font=dict(size=10, color="grey"))

        # Configure layout
        fig.update_layout(
            title=f"{timeframe_name} Target Range",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(range=[min_val, max_val], title="Price ($)"),
            height=300,
            margin=dict(l=20, r=20, t=50, b=20),
            showlegend=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Cannot visualize targets without current price or target values.")


def _display_consensus_tab(target_data: Dict, current_price: Optional[float], timeframe_name: str):
    """Helper function to display consensus price target data (Traditional format)."""
    consensus = target_data.get("consensus")
    if consensus:
        st.write(f"**Consensus {timeframe_name} Targets:**")
        col1, col2 = st.columns(2)
        with col1:
             bullish = consensus.get("bullish")
             if bullish is not None:
                 bullish_pct = ((bullish - current_price) / current_price) * 100 if current_price else None
                 st.metric("Bullish", f"${bullish:.2f}", f"{bullish_pct:.2f}%" if bullish_pct is not None else None)
             else:
                 st.metric("Bullish", "N/A")
        with col2:
             bearish = consensus.get("bearish")
             if bearish is not None:
                 bearish_pct = ((bearish - current_price) / current_price) * 100 if current_price else None
                 st.metric("Bearish", f"${bearish:.2f}", f"{bearish_pct:.2f}%" if bearish_pct is not None else None)
             else:
                  st.metric("Bearish", "N/A")
        st.write(f"Confidence: {consensus.get('confidence', 'N/A')}%" if consensus.get('confidence') is not None else "N/A")
        st.write(f"Timeframe: {consensus.get('timeframe', 'N/A')}")

        # Show contributing methods
        with st.expander("Contributing Methods"):
             for method, data in target_data.items():
                 if method != "consensus":
                     st.markdown(f"**{method.replace('_', ' ').title()}**:")
                     st.markdown(f"  - Bullish: ${data.get('bullish', 'N/A'):.2f}" if data.get('bullish') is not None else "  - Bullish: N/A")
                     st.markdown(f"  - Bearish: ${data.get('bearish', 'N/A'):.2f}" if data.get('bearish') is not None else "  - Bearish: N/A")
                     st.markdown(f"  - Confidence: {data.get('confidence', 'N/A')}%" if data.get('confidence') is not None else "  - Confidence: N/A")
    else:
        st.info(f"No consensus {timeframe_name} price target data available.") 