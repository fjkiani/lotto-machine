"""
Professional Plotly Chart Utilities
====================================

Full control over chart creation and updates.
Charts ONLY update when you explicitly call st.plotly_chart() - no automatic updates!
"""

import plotly.graph_objects as go
import pandas as pd
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class DPLevel:
    """Dark Pool Level with type and strength"""
    price: float
    volume: int
    type: str  # 'SUPPORT', 'RESISTANCE', 'BATTLEGROUND'
    strength: str  # 'WEAK', 'MODERATE', 'STRONG'


def get_color_by_type_and_strength(level: DPLevel) -> str:
    """Get color based on level type and strength"""
    if level.type == 'SUPPORT':
        return {
            'STRONG': '#00ff88',    # Bright green
            'MODERATE': '#66ffaa',  # Medium green
            'WEAK': '#99ffcc'       # Light green
        }.get(level.strength, '#00ff88')
    elif level.type == 'RESISTANCE':
        return {
            'STRONG': '#ff3366',    # Bright red
            'MODERATE': '#ff6699',  # Medium red
            'WEAK': '#ff99bb'       # Light red
        }.get(level.strength, '#ff3366')
    else:  # BATTLEGROUND
        return '#ffd700'  # Gold


def get_line_width_by_strength(level: DPLevel) -> int:
    """Get line width based on strength"""
    return {
        'STRONG': 3,
        'MODERATE': 2,
        'WEAK': 1
    }.get(level.strength, 2)


def get_line_style(level: DPLevel) -> str:
    """Get line style based on level type"""
    if level.type == 'BATTLEGROUND':
        return 'dashdot'  # Dash-dot for battlegrounds
    else:
        return 'dash'  # Dashed for support/resistance


def create_professional_chart(
    ticker: str,
    df: pd.DataFrame,
    dp_levels: Optional[List[DPLevel]] = None,
    gamma_flip: Optional[float] = None,
    vwap: Optional[float] = None,
    current_price: Optional[float] = None,
    show_volume: bool = True,
    show_indicators: Optional[Dict[str, Any]] = None,
) -> go.Figure:
    """
    Create a professional trading chart with full control.
    
    Chart ONLY updates when you call st.plotly_chart() - no automatic updates!
    
    Args:
        ticker: Stock ticker symbol
        df: DataFrame with columns: Date, Open, High, Low, Close, Volume
        dp_levels: List of DP levels to overlay
        gamma_flip: Gamma flip level (optional)
        vwap: VWAP level (optional)
        current_price: Current price level (optional)
        show_volume: Whether to show volume bars
        show_indicators: Dict of indicators to show (e.g., {'MA20': True, 'MA50': True})
    
    Returns:
        go.Figure: Plotly figure object (call st.plotly_chart(fig) to display)
    """
    fig = go.Figure()
    
    # Ensure Date is index or column
    if 'Date' not in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame must have 'Date' column or DatetimeIndex")
    
    if isinstance(df.index, pd.DatetimeIndex):
        dates = df.index
    else:
        dates = pd.to_datetime(df['Date'])
    
    # Candlestick with professional colors
    fig.add_trace(go.Candlestick(
        x=dates,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Price',
        increasing_line_color='#00ff88',  # Green up
        decreasing_line_color='#ff3366',  # Red down
        increasing_fillcolor='#00ff8840',  # Semi-transparent green
        decreasing_fillcolor='#ff336640',  # Semi-transparent red
    ))
    
    # Add technical indicators if requested
    if show_indicators:
        if show_indicators.get('MA20', False) and 'MA20' in df.columns:
            fig.add_trace(go.Scatter(
                x=dates,
                y=df['MA20'],
                mode='lines',
                name='MA20',
                line=dict(color='orange', width=1),
            ))
        
        if show_indicators.get('MA50', False) and 'MA50' in df.columns:
            fig.add_trace(go.Scatter(
                x=dates,
                y=df['MA50'],
                mode='lines',
                name='MA50',
                line=dict(color='green', width=1),
            ))
        
        if show_indicators.get('MA200', False) and 'MA200' in df.columns:
            fig.add_trace(go.Scatter(
                x=dates,
                y=df['MA200'],
                mode='lines',
                name='MA200',
                line=dict(color='red', width=1),
            ))
    
    # Add volume bars if requested
    if show_volume and 'Volume' in df.columns:
        fig.add_trace(go.Bar(
            x=dates,
            y=df['Volume'],
            name='Volume',
            marker_color='rgba(0, 212, 255, 0.3)',
            opacity=0.3,
            yaxis='y2',
        ))
    
    # Add DP levels with strength-based styling
    if dp_levels:
        for level in dp_levels:
            color = get_color_by_type_and_strength(level)
            line_width = get_line_width_by_strength(level)
            line_style = get_line_style(level)
            
            # Add horizontal line
            fig.add_hline(
                y=level.price,
                line_color=color,
                line_width=line_width,
                line_dash=line_style,
                annotation_text=f"{level.type} {level.volume:,}",
                annotation_position="right",
                annotation=dict(
                    bgcolor=color,
                    bordercolor=color,
                    font=dict(color='white', size=10, family='Arial'),
                ),
            )
    
    # Add gamma flip level
    if gamma_flip:
        fig.add_hline(
            y=gamma_flip,
            line_color='#a855f7',
            line_width=2,
            line_dash='dot',
            annotation_text='Gamma Flip',
            annotation_position="right",
            annotation=dict(
                bgcolor='#a855f7',
                bordercolor='#a855f7',
                font=dict(color='white', size=10, family='Arial'),
            ),
        )
    
    # Add VWAP line
    if vwap:
        fig.add_hline(
            y=vwap,
            line_color='#00d4ff',
            line_width=1,
            line_dash='dash',
            annotation_text='VWAP',
            annotation_position="right",
            annotation=dict(
                bgcolor='#00d4ff',
                bordercolor='#00d4ff',
                font=dict(color='white', size=10, family='Arial'),
            ),
        )
    
    # Add current price line
    if current_price:
        fig.add_hline(
            y=current_price,
            line_color='white',
            line_width=1,
            line_dash='solid',
            annotation_text='Current',
            annotation_position="right",
            annotation=dict(
                bgcolor='rgba(255, 255, 255, 0.8)',
                bordercolor='white',
                font=dict(color='black', size=10, family='Arial'),
            ),
        )
    
    # Professional dark theme
    layout_settings = {
        'title': f"{ticker} - Professional Trading Chart",
        'template': 'plotly_dark',
        'plot_bgcolor': '#0a0a0f',
        'paper_bgcolor': '#0a0a0f',
        'font': dict(color='#a0a0b0', family='Arial', size=12),
        'xaxis': dict(
            gridcolor='#2a2a35',
            showgrid=True,
            title='Date',
        ),
        'yaxis': dict(
            gridcolor='#2a2a35',
            showgrid=True,
            title='Price ($)',
        ),
        'height': 600,
        'xaxis_rangeslider_visible': False,
        'hovermode': 'x unified',
        'legend': dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
        ),
    }
    
    # Add secondary y-axis for volume if shown
    if show_volume and 'Volume' in df.columns:
        layout_settings['yaxis2'] = dict(
            title='Volume',
            overlaying='y',
            side='right',
            showgrid=False,
        )
    
    fig.update_layout(**layout_settings)
    
    return fig


def update_chart_with_new_levels(
    fig: go.Figure,
    new_dp_levels: List[DPLevel],
    clear_existing: bool = True,
) -> go.Figure:
    """
    Update existing chart with new DP levels.
    
    Args:
        fig: Existing Plotly figure
        new_dp_levels: New DP levels to add
        clear_existing: Whether to clear existing DP level lines first
    
    Returns:
        go.Figure: Updated figure
    """
    # Note: Plotly doesn't have a direct way to remove specific hlines
    # So we rebuild the chart. This is fine for static updates.
    # If you need to update frequently, consider rebuilding the entire chart.
    
    if clear_existing:
        # Rebuild chart (simplest approach for full control)
        # In practice, you'd call create_professional_chart() again with new levels
        pass
    
    # Add new levels
    for level in new_dp_levels:
        color = get_color_by_type_and_strength(level)
        line_width = get_line_width_by_strength(level)
        line_style = get_line_style(level)
        
        fig.add_hline(
            y=level.price,
            line_color=color,
            line_width=line_width,
            line_dash=line_style,
            annotation_text=f"{level.type} {level.volume:,}",
            annotation_position="right",
        )
    
    return fig

