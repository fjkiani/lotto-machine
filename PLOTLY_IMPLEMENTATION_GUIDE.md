# 🎯 Plotly Professional Charts - Implementation Guide

**Date:** 2025-01-XX  
**Status:** ✅ READY TO USE  
**Purpose:** Full control over static charts that update on demand

---

## ✅ Why Plotly is Better for Your Use Case

1. ✅ **Full Control** - Chart updates ONLY when you call `st.plotly_chart()`
2. ✅ **No Unpredictable Changes** - No automatic re-renders
3. ✅ **Easy to Iterate** - Python is simpler than React/TypeScript
4. ✅ **Beautiful Charts** - Can create professional trading charts
5. ✅ **Simple Updates** - Just rebuild chart with new data
6. ✅ **Python-Native** - Works directly in Streamlit

---

## 🚀 Quick Start

### **1. Import the Chart Utility**

```python
from src.streamlit_app.chart_utils import (
    create_professional_chart,
    DPLevel,
)
```

### **2. Prepare Your Data**

```python
import pandas as pd

# Your candlestick data (from yfinance, backend, etc.)
df = pd.DataFrame({
    'Date': [...],  # or use DatetimeIndex
    'Open': [...],
    'High': [...],
    'Low': [...],
    'Close': [...],
    'Volume': [...],
})

# Optional: Add moving averages
df['MA20'] = df['Close'].rolling(window=20).mean()
df['MA50'] = df['Close'].rolling(window=50).mean()
df['MA200'] = df['Close'].rolling(window=200).mean()
```

### **3. Create DP Levels**

```python
# From your backend or signal generator
dp_levels = [
    DPLevel(price=665.50, volume=2100000, type='RESISTANCE', strength='STRONG'),
    DPLevel(price=664.00, volume=1500000, type='SUPPORT', strength='MODERATE'),
    DPLevel(price=662.75, volume=800000, type='SUPPORT', strength='WEAK'),
    DPLevel(price=665.20, volume=2500000, type='BATTLEGROUND', strength='STRONG'),
]
```

### **4. Create and Display Chart**

```python
import streamlit as st

# Create chart (ONLY creates the figure - doesn't display yet)
fig = create_professional_chart(
    ticker='SPY',
    df=df,
    dp_levels=dp_levels,
    gamma_flip=658.00,
    vwap=664.50,
    current_price=665.20,
    show_volume=True,
    show_indicators={'MA20': True, 'MA50': True, 'MA200': True},
)

# Display chart (ONLY updates when you call this!)
st.plotly_chart(fig, use_container_width=True)
```

---

## 🔄 Updating Charts (Full Control)

### **Option 1: Rebuild Chart (Recommended for Static Updates)**

```python
# When new signals are generated, rebuild the chart
def update_chart_on_signal(new_dp_levels, new_gamma_flip, new_vwap):
    # Get fresh data
    df = fetch_latest_candlestick_data('SPY')
    
    # Rebuild chart with new levels
    fig = create_professional_chart(
        ticker='SPY',
        df=df,
        dp_levels=new_dp_levels,  # New levels
        gamma_flip=new_gamma_flip,
        vwap=new_vwap,
        current_price=get_current_price('SPY'),
    )
    
    # Display - chart ONLY updates when you call this!
    st.plotly_chart(fig, use_container_width=True)
```

**Benefits:**
- ✅ Simple and predictable
- ✅ Full control over when updates happen
- ✅ No complex state management
- ✅ Easy to debug

---

### **Option 2: Update in Streamlit Session State**

```python
# In your Streamlit app
if 'chart_figure' not in st.session_state:
    # Create initial chart
    st.session_state.chart_figure = create_professional_chart(...)

# When new signals arrive
if new_signals_detected:
    # Rebuild chart with new data
    st.session_state.chart_figure = create_professional_chart(
        ticker='SPY',
        df=df,
        dp_levels=new_dp_levels,
        ...
    )

# Display (updates automatically in Streamlit when session_state changes)
st.plotly_chart(st.session_state.chart_figure, use_container_width=True)
```

---

## 🎨 Customization Examples

### **1. Custom Colors**

```python
# Modify chart_utils.py to use your colors
def get_color_by_type_and_strength(level: DPLevel) -> str:
    if level.type == 'SUPPORT':
        return {
            'STRONG': '#00ff88',    # Your custom green
            'MODERATE': '#66ffaa',
            'WEAK': '#99ffcc'
        }[level.strength]
    # ... etc
```

### **2. Custom Themes**

```python
# In create_professional_chart(), modify layout_settings:
layout_settings = {
    'plot_bgcolor': '#0a0a0f',  # Your background color
    'paper_bgcolor': '#0a0a0f',
    'font': dict(color='#a0a0b0', family='Arial'),
    # ... customize everything
}
```

### **3. Add Custom Annotations**

```python
# After creating chart, add custom annotations
fig.add_annotation(
    x=df['Date'].iloc[-1],
    y=current_price,
    text='<b>Entry Signal</b><br>Confidence: 87%',
    bgcolor='rgba(0, 255, 136, 0.8)',
    bordercolor='green',
    borderwidth=2,
    font=dict(size=12, color='white'),
)
```

---

## 📊 Integration with Backend

### **Example: Using MonitorBridge**

```python
from backend.app.integrations.unified_monitor_bridge import get_monitor_bridge
from src.streamlit_app.chart_utils import create_professional_chart, DPLevel

# Get DP levels from backend
bridge = get_monitor_bridge()
dp_data = bridge.get_dp_levels('SPY')

# Convert to DPLevel objects
dp_levels = [
    DPLevel(
        price=level['price'],
        volume=level['volume'],
        type=level['type'],  # 'SUPPORT', 'RESISTANCE', 'BATTLEGROUND'
        strength=level['strength'],  # 'WEAK', 'MODERATE', 'STRONG'
    )
    for level in dp_data
]

# Get other data
gamma_data = bridge.get_gamma_data('SPY')
gamma_flip = gamma_data.get('gamma_flip_level')

# Get market data
market_data = bridge.get_market_data('SPY')
current_price = market_data['price']
vwap = market_data.get('vwap')

# Create chart
fig = create_professional_chart(
    ticker='SPY',
    df=candlestick_df,
    dp_levels=dp_levels,
    gamma_flip=gamma_flip,
    vwap=vwap,
    current_price=current_price,
)

# Display
st.plotly_chart(fig, use_container_width=True)
```

---

## 🔧 Advanced Features

### **1. Multiple Timeframes**

```python
# Create charts for different timeframes
timeframes = ['1m', '5m', '15m', '1h']

for tf in timeframes:
    df = fetch_data('SPY', timeframe=tf)
    fig = create_professional_chart(
        ticker=f'SPY ({tf})',
        df=df,
        dp_levels=dp_levels,
        ...
    )
    st.plotly_chart(fig, use_container_width=True)
```

### **2. Signal Markers**

```python
# Add markers for entry/exit signals
for signal in signals:
    fig.add_trace(go.Scatter(
        x=[signal['timestamp']],
        y=[signal['price']],
        mode='markers',
        marker=dict(
            symbol='triangle-up' if signal['action'] == 'BUY' else 'triangle-down',
            size=15,
            color='green' if signal['action'] == 'BUY' else 'red',
        ),
        name=f"Signal: {signal['type']}",
    ))
```

### **3. Custom Tooltips**

```python
# Plotly automatically creates tooltips, but you can customize:
fig.update_traces(
    hovertemplate='<b>%{fullData.name}</b><br>' +
                  'Price: $%{y:.2f}<br>' +
                  'Time: %{x}<br>' +
                  '<extra></extra>',
)
```

---

## ✅ Best Practices

### **1. Update Only When Needed**

```python
# ✅ GOOD: Update only when signals change
if signals_changed:
    fig = create_professional_chart(...)
    st.plotly_chart(fig)

# ❌ BAD: Recreating chart every render
fig = create_professional_chart(...)  # Runs every time!
st.plotly_chart(fig)
```

### **2. Cache Expensive Operations**

```python
@st.cache_data(ttl=60)  # Cache for 60 seconds
def fetch_candlestick_data(ticker, timeframe):
    # Expensive API call
    return df

# Use cached data
df = fetch_candlestick_data('SPY', '1h')
```

### **3. Use Session State for Chart State**

```python
if 'last_dp_levels' not in st.session_state:
    st.session_state.last_dp_levels = []

# Only rebuild if levels changed
if new_dp_levels != st.session_state.last_dp_levels:
    fig = create_professional_chart(..., dp_levels=new_dp_levels)
    st.session_state.last_dp_levels = new_dp_levels
    st.session_state.chart_figure = fig

st.plotly_chart(st.session_state.chart_figure)
```

---

## 🎯 Summary

**Key Points:**
1. ✅ Chart updates ONLY when you call `st.plotly_chart()`
2. ✅ Full control over styling, colors, annotations
3. ✅ Simple Python code - easy to iterate
4. ✅ Professional appearance - can match TradingView
5. ✅ Perfect for static charts that update on signals

**Next Steps:**
1. Use `create_professional_chart()` in your Streamlit apps
2. Integrate with backend to get DP levels
3. Update charts when new signals are generated
4. Customize colors and styling to match your brand

**STATUS: ✅ READY TO USE** 📊🎯

