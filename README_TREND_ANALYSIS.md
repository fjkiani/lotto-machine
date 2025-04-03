# Trend Analysis Storage System

This system provides functionality to store and retrieve trend analysis data for historical comparison and LLM analysis. It allows you to track the performance of trend predictions over time and use this historical data to improve future predictions.

## Features

- Store trend analysis data in a SQLite database
- Parse trend analysis from text format
- Retrieve historical trend analysis data
- Track prediction accuracy
- Generate context for LLM prompts
- Visualize trend indicator history

## Components

### TrendAnalysisStorage Class

The `TrendAnalysisStorage` class provides the following methods:

- `store_trend_analysis(ticker, analysis_data)`: Store trend analysis data in the database
- `get_trend_analysis_history(ticker, limit)`: Get historical trend analysis data for a ticker
- `store_prediction_verification(trend_analysis_id, prediction_type, prediction_value, target_price, actual_price, was_correct, accuracy_score)`: Store verification of a prediction
- `get_prediction_accuracy(ticker, prediction_type)`: Get prediction accuracy metrics for a ticker
- `get_indicator_trends(ticker, indicator, limit)`: Get historical trends for a specific indicator
- `generate_trend_context(ticker)`: Generate context string with trend analysis history
- `parse_trend_analysis_from_text(text)`: Parse trend analysis data from text format

### Database Schema

The system uses a SQLite database with the following tables:

#### trend_analysis

Stores trend analysis data for each ticker:

- `id`: Primary key
- `ticker`: Ticker symbol
- `timestamp`: Timestamp of the analysis
- `primary_trend`: Primary trend (e.g., "BEARISH", "BULLISH")
- `trend_strength`: Strength of the trend (0-100)
- `trend_duration`: Duration of the trend (e.g., "short-term", "medium-term")
- `rsi_condition`: RSI condition (e.g., "OVERSOLD", "OVERBOUGHT")
- `rsi_value`: RSI value
- `macd_signal`: MACD signal (e.g., "BEARISH", "BULLISH")
- `macd_strength`: Strength of the MACD signal (0-100)
- `bollinger_position`: Position relative to Bollinger Bands (e.g., "lower", "upper")
- `bollinger_bandwidth`: Bollinger Bands bandwidth
- `bollinger_squeeze`: Whether a Bollinger Bands squeeze is present
- `support_levels`: JSON array of support levels
- `resistance_levels`: JSON array of resistance levels
- `support_confidence`: Confidence in support levels (0-100)
- `resistance_confidence`: Confidence in resistance levels (0-100)
- `short_term_bullish_target`: Short-term bullish price target
- `short_term_bearish_target`: Short-term bearish price target
- `short_term_confidence`: Confidence in short-term targets (0-100)
- `short_term_timeframe`: Timeframe for short-term targets
- `medium_term_bullish_target`: Medium-term bullish price target
- `medium_term_bearish_target`: Medium-term bearish price target
- `medium_term_confidence`: Confidence in medium-term targets (0-100)
- `medium_term_timeframe`: Timeframe for medium-term targets
- `stop_loss`: Recommended stop loss price
- `risk_reward_ratio`: Risk/reward ratio
- `volatility_risk`: Volatility risk assessment (e.g., "LOW", "MEDIUM", "HIGH")
- `risk_factors`: JSON array of risk factors
- `analysis_summary`: Summary of the analysis
- `overall_confidence`: Overall confidence in the analysis (0-100)
- `raw_analysis`: JSON object with the raw analysis data

#### trend_prediction_accuracy

Tracks the accuracy of trend predictions:

- `id`: Primary key
- `trend_analysis_id`: Foreign key to trend_analysis.id
- `prediction_type`: Type of prediction (e.g., "short_term", "medium_term")
- `prediction_value`: Value of the prediction (e.g., "bullish", "bearish")
- `target_price`: Target price from the prediction
- `actual_price`: Actual price at verification time
- `verification_date`: Date of verification
- `was_correct`: Whether the prediction was correct (1 or 0)
- `accuracy_score`: Score representing prediction accuracy (0.0-1.0)

## Usage

### Storing Trend Analysis

```python
from src.analysis.trend_analysis_storage import TrendAnalysisStorage

# Initialize the trend analysis storage
trend_storage = TrendAnalysisStorage()

# Parse trend analysis from text
trend_text = """
Trend Analysis
Primary Trend: BEARISH

Trend Strength

70%
Duration: short-term

...
"""

analysis_data = trend_storage.parse_trend_analysis_from_text(trend_text)

# Store the analysis
analysis_id = trend_storage.store_trend_analysis("SPY", analysis_data)
```

### Retrieving Trend Analysis History

```python
# Get historical trend analysis data
history = trend_storage.get_trend_analysis_history("SPY", limit=5)

for analysis in history:
    print(f"Analysis from {analysis['timestamp']}:")
    print(f"  Primary Trend: {analysis['primary_trend']}")
    print(f"  RSI: {analysis['rsi_value']} ({analysis['rsi_condition']})")
    print(f"  MACD: {analysis['macd_signal']} (Strength: {analysis['macd_strength']}%)")
```

### Verifying Predictions

```python
# Verify a prediction
verification_id = trend_storage.store_prediction_verification(
    trend_analysis_id=analysis_id,
    prediction_type="short_term",
    prediction_value="bearish",
    target_price=540.00,
    actual_price=535.00,
    was_correct=True,
    accuracy_score=0.9
)
```

### Getting Prediction Accuracy

```python
# Get prediction accuracy metrics
accuracy = trend_storage.get_prediction_accuracy("SPY")

if 'overall' in accuracy:
    overall = accuracy['overall']
    print(f"Overall Accuracy: {overall['accuracy']*100:.1f}% ({overall['correct_predictions']}/{overall['total_predictions']} correct)")
```

### Getting Indicator Trends

```python
# Get historical trends for a specific indicator
trend_data = trend_storage.get_indicator_trends("SPY", "trend_strength", limit=10)

for i, timestamp in enumerate(trend_data['timestamps']):
    if i < len(trend_data['values']):
        print(f"  {timestamp}: {trend_data['values'][i]}")
```

### Generating Context for LLM

```python
# Generate context for LLM prompt
context = trend_storage.generate_trend_context("SPY")

# Use the context in an LLM prompt
prompt = f"""
Based on the following historical trend analysis, provide a prediction for SPY:

{context}

Current market conditions:
...
"""
```

## Integration with Streamlit

The trend analysis storage system is integrated with the Streamlit app in `streamlit_app_memory.py`. The app provides a user interface for:

- Storing trend analysis data
- Viewing trend analysis history
- Visualizing trend indicator history
- Tracking prediction accuracy

## Test Script

The `test_trend_analysis_storage.py` script demonstrates how to use the trend analysis storage system. It provides the following functionality:

- Parse and store trend analysis from a text file
- Retrieve trend analysis history
- Verify predictions
- Get prediction accuracy metrics
- Get indicator trends
- Generate context for LLM prompts

### Running the Test Script

```bash
# Store trend analysis from a file
./venv/bin/python test_trend_analysis_storage.py SPY --trend-file trend_analysis_example.txt

# Get indicator trends
./venv/bin/python test_trend_analysis_storage.py SPY --get-indicator trend_strength

# Verify a prediction
./venv/bin/python test_trend_analysis_storage.py SPY --verify-prediction --analysis-id 1 --prediction-type short_term --prediction-value bearish --target-price 540.00 --actual-price 535.00 --was-correct --accuracy-score 0.9
```

## Benefits for LLM Analysis

The trend analysis storage system provides several benefits for LLM-based financial analysis:

1. **Historical Context**: LLMs can access historical trend analysis data to identify patterns and improve predictions.
2. **Accuracy Tracking**: The system tracks the accuracy of predictions, allowing LLMs to learn from past successes and failures.
3. **Indicator Trends**: LLMs can analyze how technical indicators have evolved over time for a specific ticker.
4. **Structured Data**: The system provides structured data that LLMs can easily process and incorporate into their analysis.
5. **Feedback Loop**: The verification system creates a feedback loop that helps LLMs improve their predictions over time.

By leveraging this historical data, LLMs can provide more accurate and contextually relevant financial analysis. 