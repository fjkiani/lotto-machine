#!/bin/bash

# Run Dynamic Manager Review for Options Analysis
# This script runs the full chain analysis with dynamic LLM manager review

# Set default ticker to SPY if none provided
TICKER=${1:-SPY}
echo "Running options analysis with dynamic manager review for $TICKER"

# Create the virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Install required packages if needed
if ! pip list | grep -q "yfinance"; then
    echo "Installing required packages..."
    pip install yfinance pandas numpy matplotlib tabulate pyyaml google-generativeai
fi

# Make sure results directory exists
mkdir -p results

# Run the analysis
echo "Starting analysis..."
python test_full_chain_llm_review.py $TICKER

# Deactivate the virtual environment
deactivate

echo "Analysis complete. Results are saved in the results directory." 