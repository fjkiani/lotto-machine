"""
Anomaly Detector Streamlit Integration
Adds anomaly detection capabilities to the main Streamlit app
"""

import streamlit as st
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from src.anomaly_detector import AnomalyDetector, MarketTick, NewsEvent, OptionsFlow

logger = logging.getLogger(__name__)

# Default configuration for anomaly detector
DEFAULT_CONFIG = {
    'tickers': ['SPY', 'QQQ', 'AAPL', 'TSLA', 'MSFT', 'GOOGL'],
    
    # Baseline parameters
    'price_window_minutes': 30,
    'volume_window_minutes': 30,
    'trade_size_window_minutes': 30,
    
    # Classifier thresholds
    'block_trade_threshold': 5.0,
    'min_block_trade_size': 10000,
    'dark_volume_threshold': 0.4,
    'price_z_threshold': 2.0,
    'volume_z_threshold': 2.0,
    'options_sweep_threshold': 1000,
    'news_sentiment_threshold': 0.5,
    
    # Clustering parameters
    'cluster_window_minutes': 5,
    'min_events_for_cluster': 2,
    'low_conviction_threshold': 0.3,
    'medium_conviction_threshold': 0.6,
    'high_conviction_threshold': 0.8,
    'critical_conviction_threshold': 0.9,
    
    # Alerting
    'console_alerts': True,
    'log_file_alerts': True,
    'alert_format': 'detailed',
    
    # Feedback
    'recalibration_threshold': 0.1,
    'min_samples_for_recalibration': 50,
    'market_move_threshold_1min': 0.002,
    'market_move_threshold_5min': 0.005,
    'market_move_threshold_15min': 0.01
}

def initialize_anomaly_detector():
    """
    Initialize anomaly detector in session state
    """
    if 'anomaly_detector' not in st.session_state:
        st.session_state.anomaly_detector = AnomalyDetector(DEFAULT_CONFIG)
        st.session_state.anomaly_detector_active = False
        st.session_state.anomaly_alerts = []
        st.session_state.anomaly_history = []

def display_anomaly_detector_controls():
    """
    Display anomaly detector control panel
    """
    st.subheader("🚨 Anomaly Detection System")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🟢 Start Monitoring", disabled=st.session_state.anomaly_detector_active):
            st.session_state.anomaly_detector_active = True
            st.success("Anomaly detection started!")
    
    with col2:
        if st.button("🔴 Stop Monitoring", disabled=not st.session_state.anomaly_detector_active):
            st.session_state.anomaly_detector_active = False
            st.success("Anomaly detection stopped!")
    
    with col3:
        if st.button("🔄 Reset System"):
            st.session_state.anomaly_detector = AnomalyDetector(DEFAULT_CONFIG)
            st.session_state.anomaly_alerts = []
            st.session_state.anomaly_history = []
            st.success("System reset!")

def display_anomaly_configuration():
    """
    Display anomaly detector configuration options
    """
    with st.expander("⚙️ Anomaly Detection Configuration"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Detection Thresholds**")
            block_threshold = st.slider("Block Trade Threshold (x median)", 2.0, 10.0, 5.0)
            price_z_threshold = st.slider("Price Z-Score Threshold", 1.0, 4.0, 2.0)
            volume_z_threshold = st.slider("Volume Z-Score Threshold", 1.0, 4.0, 2.0)
            dark_volume_threshold = st.slider("Dark Volume Threshold", 0.1, 0.8, 0.4)
        
        with col2:
            st.markdown("**Clustering Parameters**")
            cluster_window = st.slider("Cluster Window (minutes)", 1, 15, 5)
            min_events = st.slider("Min Events for Cluster", 2, 5, 2)
            high_conviction = st.slider("High Conviction Threshold", 0.5, 0.95, 0.8)
            critical_conviction = st.slider("Critical Conviction Threshold", 0.7, 0.99, 0.9)
        
        if st.button("Update Configuration"):
            # Update configuration
            config = DEFAULT_CONFIG.copy()
            config.update({
                'block_trade_threshold': block_threshold,
                'price_z_threshold': price_z_threshold,
                'volume_z_threshold': volume_z_threshold,
                'dark_volume_threshold': dark_volume_threshold,
                'cluster_window_minutes': cluster_window,
                'min_events_for_cluster': min_events,
                'high_conviction_threshold': high_conviction,
                'critical_conviction_threshold': critical_conviction
            })
            
            st.session_state.anomaly_detector = AnomalyDetector(config)
            st.success("Configuration updated!")

def display_anomaly_status():
    """
    Display anomaly detector status
    """
    detector = st.session_state.anomaly_detector
    status = detector.get_status()
    
    st.subheader("📊 System Status")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Tickers Monitored", len(status['tickers_monitored']))
    
    with col2:
        st.metric("Recent Anomalies", status['recent_anomalies_count'])
    
    with col3:
        st.metric("Cluster Events", status['cluster_events_count'])
    
    with col4:
        st.metric("System Status", "🟢 Active" if st.session_state.anomaly_detector_active else "🔴 Inactive")

def display_recent_alerts():
    """
    Display recent anomaly alerts
    """
    st.subheader("🚨 Recent Alerts")
    
    if st.session_state.anomaly_alerts:
        for i, alert in enumerate(st.session_state.anomaly_alerts[-10:]):  # Last 10 alerts
            conviction_color = {
                'critical': 'red',
                'high': 'orange', 
                'medium': 'yellow',
                'low': 'green'
            }.get(alert['conviction_level'], 'gray')
            
            st.markdown(f"""
            <div style="border-left: 4px solid {conviction_color}; padding: 10px; margin: 5px 0; background-color: #f8f9fa;">
                <strong>{alert['conviction_level'].upper()}</strong> - {alert['ticker']} at {alert['timestamp']}<br>
                {alert['summary']}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No recent alerts")

def display_anomaly_history():
    """
    Display anomaly detection history
    """
    st.subheader("📈 Detection History")
    
    if st.session_state.anomaly_history:
        # Convert to DataFrame for visualization
        df = pd.DataFrame(st.session_state.anomaly_history)
        
        # Create timeline chart
        fig = go.Figure()
        
        # Add anomaly events
        for conviction_level in ['low', 'medium', 'high', 'critical']:
            level_data = df[df['conviction_level'] == conviction_level]
            if not level_data.empty:
                fig.add_trace(go.Scatter(
                    x=level_data['timestamp'],
                    y=level_data['cluster_score'],
                    mode='markers',
                    name=conviction_level.title(),
                    marker=dict(
                        size=level_data['event_count'] * 2,
                        color=conviction_level
                    ),
                    text=level_data['ticker'],
                    hovertemplate='<b>%{text}</b><br>Score: %{y:.3f}<br>Events: %{marker.size}<extra></extra>'
                ))
        
        fig.update_layout(
            title="Anomaly Detection Timeline",
            xaxis_title="Time",
            yaxis_title="Cluster Score",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Display summary statistics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Events", len(df))
        
        with col2:
            high_critical = len(df[df['conviction_level'].isin(['high', 'critical'])])
            st.metric("High/Critical Events", high_critical)
        
        with col3:
            avg_score = df['cluster_score'].mean()
            st.metric("Average Score", f"{avg_score:.3f}")
    
    else:
        st.info("No anomaly history available")

def display_performance_metrics():
    """
    Display anomaly detection performance metrics
    """
    detector = st.session_state.anomaly_detector
    feedback_status = detector.feedback.get_status()
    
    st.subheader("🎯 Performance Metrics")
    
    metrics = feedback_status['performance_metrics']
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Accuracy", f"{metrics['accuracy']:.1%}")
    
    with col2:
        st.metric("Precision", f"{metrics['precision']:.1%}")
    
    with col3:
        st.metric("Recall", f"{metrics['recall']:.1%}")
    
    with col4:
        st.metric("Total Anomalies", metrics['total_anomalies'])
    
    # Performance chart
    if metrics['total_anomalies'] > 0:
        fig = go.Figure(data=[
            go.Bar(name='Correct', x=['Predictions'], y=[metrics['correct_predictions']]),
            go.Bar(name='False Positives', x=['Predictions'], y=[metrics['false_positives']]),
            go.Bar(name='False Negatives', x=['Predictions'], y=[metrics['false_negatives']])
        ])
        
        fig.update_layout(
            title="Prediction Performance",
            barmode='stack',
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)

def simulate_anomaly_detection():
    """
    Simulate anomaly detection for demo purposes
    """
    if st.button("🎲 Simulate Anomaly Detection"):
        detector = st.session_state.anomaly_detector
        
        # Simulate some anomalies
        import random
        from datetime import datetime
        
        tickers = ['SPY', 'QQQ', 'AAPL', 'TSLA']
        anomaly_types = ['block_trade', 'price_spike', 'volume_spike', 'options_sweep']
        
        for _ in range(random.randint(1, 3)):
            ticker = random.choice(tickers)
            anomaly_type = random.choice(anomaly_types)
            conviction_level = random.choice(['low', 'medium', 'high', 'critical'])
            
            # Create simulated alert
            alert = {
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'ticker': ticker,
                'anomaly_type': anomaly_type,
                'conviction_level': conviction_level,
                'summary': f"{anomaly_type.replace('_', ' ').title()} detected"
            }
            
            st.session_state.anomaly_alerts.append(alert)
            
            # Add to history
            history_entry = {
                'timestamp': datetime.now(),
                'ticker': ticker,
                'conviction_level': conviction_level,
                'cluster_score': random.uniform(0.3, 0.95),
                'event_count': random.randint(2, 5)
            }
            
            st.session_state.anomaly_history.append(history_entry)
        
        st.success("Simulated anomaly detection completed!")

def main_anomaly_detector_page():
    """
    Main anomaly detector page
    """
    st.title("🚨 AI Hedge Fund - Anomaly Detection System")
    
    # Initialize detector
    initialize_anomaly_detector()
    
    # Display controls
    display_anomaly_detector_controls()
    
    # Display configuration
    display_anomaly_configuration()
    
    # Display status
    display_anomaly_status()
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["🚨 Alerts", "📈 History", "🎯 Performance", "🎲 Simulation"])
    
    with tab1:
        display_recent_alerts()
    
    with tab2:
        display_anomaly_history()
    
    with tab3:
        display_performance_metrics()
    
    with tab4:
        st.markdown("### Demo Simulation")
        st.markdown("Click the button below to simulate anomaly detection events for demonstration purposes.")
        simulate_anomaly_detection()

if __name__ == "__main__":
    main_anomaly_detector_page()



