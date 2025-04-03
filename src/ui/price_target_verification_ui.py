"""
Price Target Verification UI Components

This module provides UI components for displaying price target verification results
in the Streamlit app.
"""

import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np
from typing import Dict, List, Optional

from src.analysis.trend_analysis_storage import TrendAnalysisStorage

def display_prediction_verification(ticker: str):
    """
    Display prediction verification results for a ticker
    
    Args:
        ticker: Ticker symbol
    """
    st.header("Price Target Verification")
    
    # Get prediction accuracy
    trend_storage = TrendAnalysisStorage()
    accuracy = trend_storage.get_prediction_accuracy(ticker)
    
    if 'overall' in accuracy and accuracy['overall']['total_predictions'] > 0:
        # Display overall metrics
        st.subheader("Overall Accuracy")
        col1, col2, col3 = st.columns(3)
        
        overall = accuracy['overall']
        col1.metric("Target Hit Rate", f"{overall['accuracy']*100:.1f}%")
        col2.metric("Total Predictions", overall['total_predictions'])
        col3.metric("Correct Predictions", overall['correct_predictions'])
        
        # Display detailed metrics
        st.subheader("Detailed Metrics")
        tabs = st.tabs(["Short Term", "Medium Term"])
        
        with tabs[0]:
            if 'short_term' in accuracy:
                st.write("Short Term Predictions")
                for pred_value, metrics in accuracy['short_term'].items():
                    if metrics['total_predictions'] > 0:
                        st.write(f"**{pred_value.title()}**: {metrics['accuracy']*100:.1f}% accuracy ({metrics['correct_predictions']}/{metrics['total_predictions']} correct)")
            else:
                st.info("No short-term predictions verified yet.")
        
        with tabs[1]:
            if 'medium_term' in accuracy:
                st.write("Medium Term Predictions")
                for pred_value, metrics in accuracy['medium_term'].items():
                    if metrics['total_predictions'] > 0:
                        st.write(f"**{pred_value.title()}**: {metrics['accuracy']*100:.1f}% accuracy ({metrics['correct_predictions']}/{metrics['total_predictions']} correct)")
            else:
                st.info("No medium-term predictions verified yet.")
        
        # Get verification details
        conn = sqlite3.connect(trend_storage.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT 
            v.id,
            v.trend_analysis_id,
            v.prediction_type,
            v.prediction_value,
            v.target_price,
            v.actual_price,
            v.verification_date,
            v.was_correct,
            v.accuracy_score,
            v.highest_price_in_period,
            v.lowest_price_in_period,
            v.price_at_prediction,
            v.target_hit_date,
            v.days_to_target,
            a.timestamp as analysis_date
        FROM 
            trend_prediction_accuracy v
        JOIN
            trend_analysis a ON v.trend_analysis_id = a.id
        WHERE
            a.ticker = ?
        ORDER BY
            v.verification_date DESC
        LIMIT 10
        ''', (ticker,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            st.subheader("Recent Verifications")
            
            # Convert to DataFrame for display
            df = pd.DataFrame([dict(row) for row in rows])
            
            # Format dates
            df['verification_date'] = pd.to_datetime(df['verification_date']).dt.strftime('%Y-%m-%d')
            df['analysis_date'] = pd.to_datetime(df['analysis_date']).dt.strftime('%Y-%m-%d')
            if 'target_hit_date' in df.columns:
                df['target_hit_date'] = pd.to_datetime(df['target_hit_date'], errors='coerce').dt.strftime('%Y-%m-%d')
            
            # Format boolean
            df['was_correct'] = df['was_correct'].apply(lambda x: '✅' if x else '❌')
            
            # Format prediction type and value
            df['prediction'] = df.apply(lambda x: f"{x['prediction_type'].replace('_', ' ').title()} {x['prediction_value'].title()}", axis=1)
            
            # Select columns to display
            display_cols = [
                'prediction', 
                'target_price', 
                'actual_price', 
                'was_correct', 
                'accuracy_score',
                'analysis_date',
                'verification_date'
            ]
            
            # Add additional columns if they exist
            if 'days_to_target' in df.columns:
                display_cols.insert(4, 'days_to_target')
            if 'target_hit_date' in df.columns:
                display_cols.insert(5, 'target_hit_date')
            
            display_df = df[display_cols]
            
            # Rename columns
            column_names = {
                'prediction': 'Prediction', 
                'target_price': 'Target Price', 
                'actual_price': 'Current Price', 
                'was_correct': 'Hit Target', 
                'accuracy_score': 'Accuracy Score',
                'analysis_date': 'Analysis Date',
                'verification_date': 'Verification Date',
                'days_to_target': 'Days to Target',
                'target_hit_date': 'Target Hit Date'
            }
            
            display_df.columns = [column_names.get(col, col) for col in display_df.columns]
            
            st.dataframe(display_df)
            
            # Create a chart of target prices vs actual prices
            st.subheader("Target Prices vs. Price Range")
            
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Plot data points
            x = np.arange(len(df))
            
            for i, row in df.iterrows():
                color = 'green' if row['was_correct'] == '✅' else 'red'
                marker = '^' if row['prediction_value'] == 'bullish' else 'v'
                
                # Plot target price
                ax.scatter(
                    i, 
                    row['target_price'], 
                    color=color, 
                    marker=marker, 
                    s=100, 
                    label=f"{row['prediction']} Target" if i == 0 else ""
                )
                
                # Plot price range if available
                if 'highest_price_in_period' in row and 'lowest_price_in_period' in row:
                    if pd.notna(row['highest_price_in_period']) and pd.notna(row['lowest_price_in_period']):
                        ax.vlines(
                            i, 
                            row['lowest_price_in_period'], 
                            row['highest_price_in_period'], 
                            color='gray', 
                            alpha=0.5
                        )
                
                # Plot price at prediction if available
                if 'price_at_prediction' in row and pd.notna(row['price_at_prediction']):
                    ax.hlines(
                        row['price_at_prediction'],
                        i - 0.2,
                        i + 0.2,
                        color='blue',
                        alpha=0.7
                    )
            
            # Set labels and title
            ax.set_xlabel('Prediction')
            ax.set_ylabel('Price ($)')
            ax.set_title(f'Target Prices vs. Price Range for {ticker}')
            
            # Set x-ticks
            ax.set_xticks(x)
            ax.set_xticklabels([f"{row['prediction']}" for _, row in df.iterrows()], rotation=45)
            
            # Add grid
            ax.grid(True, alpha=0.3)
            
            # Add legend
            handles, labels = ax.get_legend_handles_labels()
            by_label = dict(zip(labels, handles))
            ax.legend(by_label.values(), by_label.keys())
            
            # Show the plot
            st.pyplot(fig)
            
            # Create a chart of days to target
            if 'days_to_target' in df.columns and df['days_to_target'].notna().any():
                st.subheader("Days to Reach Target")
                
                # Filter rows with days_to_target
                days_df = df[df['days_to_target'].notna()]
                
                if not days_df.empty:
                    fig, ax = plt.subplots(figsize=(10, 6))
                    
                    # Create bar chart
                    bars = ax.bar(
                        np.arange(len(days_df)),
                        days_df['days_to_target'],
                        color=[('green' if x == '✅' else 'red') for x in days_df['was_correct']]
                    )
                    
                    # Add value labels on top of bars
                    for bar in bars:
                        height = bar.get_height()
                        ax.text(
                            bar.get_x() + bar.get_width()/2.,
                            height + 0.5,
                            f"{int(height)}",
                            ha='center',
                            va='bottom'
                        )
                    
                    # Set labels and title
                    ax.set_xlabel('Prediction')
                    ax.set_ylabel('Days')
                    ax.set_title(f'Days to Reach Target Price for {ticker}')
                    
                    # Set x-ticks
                    ax.set_xticks(np.arange(len(days_df)))
                    ax.set_xticklabels([f"{row['prediction']}" for _, row in days_df.iterrows()], rotation=45)
                    
                    # Add grid
                    ax.grid(True, alpha=0.3, axis='y')
                    
                    # Show the plot
                    st.pyplot(fig)
        else:
            st.info("No verification details available yet.")
    else:
        st.info("No prediction accuracy data available yet. Run analysis to verify predictions.")

def display_prediction_timeline(ticker: str, analysis_id: Optional[int] = None):
    """
    Display a timeline of price targets and actual prices
    
    Args:
        ticker: Ticker symbol
        analysis_id: Optional ID of a specific analysis to display
    """
    st.header("Price Target Timeline")
    
    # Get trend analysis storage
    trend_storage = TrendAnalysisStorage()
    
    # Get analyses
    if analysis_id:
        # Get a specific analysis
        conn = sqlite3.connect(trend_storage.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM trend_analysis WHERE id = ?
        ''', (analysis_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            st.error(f"Analysis with ID {analysis_id} not found")
            return
        
        analyses = [dict(row)]
    else:
        # Get all analyses for the ticker
        analyses = trend_storage.get_trend_analysis_history(ticker)
    
    if not analyses:
        st.info(f"No trend analyses found for {ticker}")
        return
    
    # Create a dropdown to select an analysis if no specific one was provided
    if not analysis_id:
        analysis_options = [f"Analysis {a['id']} ({datetime.fromisoformat(a['timestamp']).strftime('%Y-%m-%d %H:%M')})" for a in analyses]
        selected_analysis = st.selectbox("Select Analysis", analysis_options)
        selected_id = int(selected_analysis.split()[1])
        
        # Filter to the selected analysis
        analysis = next((a for a in analyses if a['id'] == selected_id), None)
        if not analysis:
            st.error(f"Analysis with ID {selected_id} not found")
            return
    else:
        analysis = analyses[0]
    
    # Get verification data
    conn = sqlite3.connect(trend_storage.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM trend_prediction_accuracy WHERE trend_analysis_id = ?
    ''', (analysis['id'],))
    
    verifications = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Display analysis details
    st.subheader(f"Analysis from {datetime.fromisoformat(analysis['timestamp']).strftime('%Y-%m-%d %H:%M')}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Primary Trend:** {analysis['primary_trend']} ({analysis['trend_strength']}% strength)")
        st.write(f"**RSI:** {analysis['rsi_value']} ({analysis['rsi_condition']})")
        st.write(f"**MACD:** {analysis['macd_signal']} ({analysis['macd_strength']}% strength)")
    
    with col2:
        st.write("**Short-Term Targets:**")
        st.write(f"- Bullish: ${analysis['short_term_bullish_target']} ({analysis['short_term_timeframe']})")
        st.write(f"- Bearish: ${analysis['short_term_bearish_target']} ({analysis['short_term_timeframe']})")
        
        st.write("**Medium-Term Targets:**")
        st.write(f"- Bullish: ${analysis['medium_term_bullish_target']} ({analysis['medium_term_timeframe']})")
        st.write(f"- Bearish: ${analysis['medium_term_bearish_target']} ({analysis['medium_term_timeframe']})")
    
    # Create a timeline chart
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot analysis date
    analysis_date = datetime.fromisoformat(analysis['timestamp'])
    ax.axvline(x=analysis_date, color='blue', linestyle='--', label='Analysis Date')
    
    # Plot target dates based on timeframes
    from src.analysis.price_target_verification import parse_timeframe
    
    # Short-term timeframe
    short_min_days, short_max_days = parse_timeframe(analysis['short_term_timeframe'])
    short_term_end = analysis_date + pd.Timedelta(days=short_max_days)
    ax.axvline(x=short_term_end, color='green', linestyle=':', label='Short-Term End')
    
    # Medium-term timeframe
    medium_min_days, medium_max_days = parse_timeframe(analysis['medium_term_timeframe'])
    medium_term_end = analysis_date + pd.Timedelta(days=medium_max_days)
    ax.axvline(x=medium_term_end, color='purple', linestyle=':', label='Medium-Term End')
    
    # Plot target prices
    ax.axhline(y=analysis['short_term_bullish_target'], color='green', linestyle='-', 
               label=f"Short-Term Bullish (${analysis['short_term_bullish_target']})")
    ax.axhline(y=analysis['short_term_bearish_target'], color='red', linestyle='-', 
               label=f"Short-Term Bearish (${analysis['short_term_bearish_target']})")
    ax.axhline(y=analysis['medium_term_bullish_target'], color='green', linestyle='--', 
               label=f"Medium-Term Bullish (${analysis['medium_term_bullish_target']})")
    ax.axhline(y=analysis['medium_term_bearish_target'], color='red', linestyle='--', 
               label=f"Medium-Term Bearish (${analysis['medium_term_bearish_target']})")
    
    # Plot verification data if available
    for v in verifications:
        if 'target_hit_date' in v and v['target_hit_date']:
            hit_date = datetime.fromisoformat(v['target_hit_date'])
            color = 'green' if v['was_correct'] else 'red'
            marker = '^' if v['prediction_value'] == 'bullish' else 'v'
            
            ax.scatter(
                hit_date, 
                v['target_price'], 
                color=color, 
                marker=marker, 
                s=100, 
                label=f"{v['prediction_type'].replace('_', ' ').title()} {v['prediction_value'].title()} Hit"
            )
    
    # Format the chart
    ax.set_title(f"Price Targets Timeline for {ticker} (Analysis ID: {analysis['id']})")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price ($)")
    
    # Format x-axis as dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.xticks(rotation=45)
    
    # Add legend
    ax.legend(loc='best')
    
    # Add grid
    ax.grid(True, alpha=0.3)
    
    # Show the plot
    st.pyplot(fig)
    
    # Display verification details if available
    if verifications:
        st.subheader("Verification Details")
        
        # Convert to DataFrame for display
        df = pd.DataFrame(verifications)
        
        # Format dates
        df['verification_date'] = pd.to_datetime(df['verification_date']).dt.strftime('%Y-%m-%d')
        if 'target_hit_date' in df.columns:
            df['target_hit_date'] = pd.to_datetime(df['target_hit_date'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Format boolean
        df['was_correct'] = df['was_correct'].apply(lambda x: '✅' if x else '❌')
        
        # Format prediction type and value
        df['prediction'] = df.apply(lambda x: f"{x['prediction_type'].replace('_', ' ').title()} {x['prediction_value'].title()}", axis=1)
        
        # Select columns to display
        display_cols = [
            'prediction', 
            'target_price', 
            'actual_price', 
            'was_correct', 
            'accuracy_score',
            'verification_date'
        ]
        
        # Add additional columns if they exist
        if 'days_to_target' in df.columns:
            display_cols.insert(4, 'days_to_target')
        if 'target_hit_date' in df.columns:
            display_cols.insert(5, 'target_hit_date')
        if 'price_at_prediction' in df.columns:
            display_cols.insert(3, 'price_at_prediction')
        
        display_df = df[display_cols]
        
        # Rename columns
        column_names = {
            'prediction': 'Prediction', 
            'target_price': 'Target Price', 
            'actual_price': 'Current Price', 
            'was_correct': 'Hit Target', 
            'accuracy_score': 'Accuracy Score',
            'verification_date': 'Verification Date',
            'days_to_target': 'Days to Target',
            'target_hit_date': 'Target Hit Date',
            'price_at_prediction': 'Price at Prediction'
        }
        
        display_df.columns = [column_names.get(col, col) for col in display_df.columns]
        
        st.dataframe(display_df)
    else:
        st.info("No verification data available for this analysis yet.") 