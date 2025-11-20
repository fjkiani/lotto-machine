def display_analysis(result, ticker):
    """
    Display the analysis result in a structured format with tabs
    
    Args:
        result: Analysis result dictionary
        ticker: Ticker symbol
    """
    import streamlit as st
    
    if result is None:
        st.error("No analysis result available. Please run the analysis first.")
        return
        
    # Create tabs for different sections
    market_tab, ticker_tab, technical_tab, learning_tab, verification_tab, timeline_tab = st.tabs([
        "Market Overview", 
        "Ticker Analysis", 
        "Technical Insights",
        "Learning Points",
        "Price Target Verification",
        "Prediction Timeline"
    ])
    
    with market_tab:
        display_market_overview(result, ticker)
        
    with ticker_tab:
        display_ticker_analysis(result, ticker)
        
    with technical_tab:
        display_technical_insights(result)
        
    with learning_tab:
        display_learning_points(result)
        
    with verification_tab:
        try:
            from src.ui.price_target_verification_ui import display_prediction_verification
            display_prediction_verification(ticker)
        except ImportError:
            st.warning("Price target verification module not available. Please install the required dependencies.")
        
    with timeline_tab:
        try:
            from src.ui.price_target_verification_ui import display_prediction_timeline
            display_prediction_timeline(ticker)
        except ImportError:
            st.warning("Price target verification module not available. Please install the required dependencies.")
