# Price Target Verification System

This system provides functionality to verify price targets from trend analysis and track prediction accuracy over time. It allows you to objectively measure the accuracy of price target predictions based on whether the targets are hit within the specified timeframes.

## Features

- Verify price targets against historical price data
- Track when targets are hit and how long it takes
- Calculate accuracy scores for predictions
- Visualize prediction accuracy and performance
- Integrate with the existing trend analysis system

## Components

### Core Verification Module

The `src/analysis/price_target_verification.py` file contains the core functionality:

- `update_database_schema()`: Updates the database schema to include columns for price target verification
- `parse_timeframe()`: Parses timeframe strings (e.g., "1-2 weeks") into day ranges
- `verify_price_targets()`: Verifies all unverified price targets for a ticker
- `verify_prediction()`: Verifies a single prediction against historical price data

### UI Components

The `src/ui/price_target_verification_ui.py` file contains the UI components:

- `display_prediction_verification()`: Displays prediction verification results in the Streamlit app
- `display_prediction_timeline()`: Displays a timeline of price targets and actual prices

### Database Schema

The system extends the existing `trend_prediction_accuracy` table with the following columns:

- `highest_price_in_period`: Highest price reached during the prediction period
- `lowest_price_in_period`: Lowest price reached during the prediction period
- `price_at_prediction`: Price at the time of prediction
- `target_hit_date`: Date when the target was hit (if applicable)
- `days_to_target`: Number of days it took to hit the target (if applicable)

## How It Works

### Verification Process

1. When the user runs an analysis, the system first verifies any unverified predictions for the ticker
2. For each unverified prediction, the system:
   - Retrieves historical price data from the prediction date to the current date
   - Determines if the target price was hit during the period
   - Calculates an accuracy score based on how close the price got to the target
   - Records the verification results in the database

### Accuracy Calculation

- For bullish predictions:
  - Target hit: The highest price reached during the period is at or above the target price
  - Accuracy score: `min(1.0, (highest_price - price_at_prediction) / (target_price - price_at_prediction))`

- For bearish predictions:
  - Target hit: The lowest price reached during the period is at or below the target price
  - Accuracy score: `min(1.0, (price_at_prediction - lowest_price) / (price_at_prediction - target_price))`

### Timeframe Parsing

The system parses timeframe strings (e.g., "1-2 weeks", "3-6 months") into day ranges:

- "1-2 weeks" → 7-14 days
- "3-6 months" → 90-180 days
- "1 year" → 365 days

## Usage

### Verifying Price Targets

```python
from src.analysis.price_target_verification import verify_price_targets

# Verify price targets for a ticker
result = verify_price_targets("SPY")

# Print the results
print(f"Verified {result['total_verifications']} predictions")
for v in result['verifications']:
    print(f"Prediction: {v['prediction_type']} {v['prediction_value']}")
    print(f"Target Price: ${v['target_price']}")
    print(f"Target Hit: {'Yes' if v['target_hit'] else 'No'}")
    print(f"Accuracy Score: {v['accuracy_score']:.2f}")
```

### Getting Prediction Accuracy

```python
from src.analysis.trend_analysis_storage import TrendAnalysisStorage

# Get prediction accuracy for a ticker
trend_storage = TrendAnalysisStorage()
accuracy = trend_storage.get_prediction_accuracy("SPY")

# Print the results
if 'overall' in accuracy:
    overall = accuracy['overall']
    print(f"Overall Accuracy: {overall['accuracy']*100:.1f}% ({overall['correct_predictions']}/{overall['total_predictions']} correct)")
```

## Integration with Streamlit App

The price target verification system is integrated with the Streamlit app in `streamlit_app_memory.py`. The app provides a user interface for:

- Verifying price targets when running an analysis
- Displaying prediction accuracy metrics
- Visualizing target prices vs. actual prices
- Showing a timeline of price targets and when they were hit

## Test Script

The `test_price_target_verification.py` script demonstrates how to use the price target verification system. It provides the following functionality:

- Test the timeframe parsing function
- Update the database schema
- Verify price targets for a ticker
- Get prediction accuracy metrics
- Get verification details

### Running the Test Script

```bash
# Run all operations
./venv/bin/python test_price_target_verification.py --ticker SPY

# Test the timeframe parsing function
./venv/bin/python test_price_target_verification.py --test-timeframe

# Update the database schema
./venv/bin/python test_price_target_verification.py --update-schema

# Verify price targets
./venv/bin/python test_price_target_verification.py --verify --ticker SPY

# Get prediction accuracy
./venv/bin/python test_price_target_verification.py --get-accuracy --ticker SPY

# Get verification details
./venv/bin/python test_price_target_verification.py --get-details --ticker SPY
```

## Benefits

The price target verification system provides several benefits:

1. **Objectivity**: Removes subjectivity from the verification process by using clear criteria for success
2. **Accuracy Tracking**: Provides detailed metrics on prediction accuracy over time
3. **Feedback Loop**: Creates a feedback loop for improving future predictions
4. **Visualization**: Offers visual representations of prediction performance
5. **User Transparency**: Clearly shows system performance to users
6. **LLM Enhancement**: Improves context for LLM-based analysis by providing historical accuracy data 