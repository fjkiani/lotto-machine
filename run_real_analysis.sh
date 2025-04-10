#!/bin/bash
# Run options analysis with real LLM data

# Set default ticker to SPY if none provided
TICKER=${1:-SPY}
echo "Running real options chain analysis for $TICKER"

# Set API keys if not already in environment
if [ -z "$RAPIDAPI_KEY" ]; then
    export RAPIDAPI_KEY="9f107deaabmsh2efbc3559ddca05p17f1abjsn271e6df32f7c"
    echo "Set RAPIDAPI_KEY from script"
fi

# Create or update .env file with API keys
if [ ! -f ".env" ] || ! grep -q "RAPIDAPI_KEY" .env; then
    echo "Updating .env file with API keys..."
    echo "RAPIDAPI_KEY=9f107deaabmsh2efbc3559ddca05p17f1abjsn271e6df32f7c" >> .env
fi

# Load environment variables from .env file 
if [ -f ".env" ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Check for required API keys
if [ -z "$GEMINI_API_KEY" ]; then
    echo "WARNING: GEMINI_API_KEY is not set. Please set it in your .env file."
    echo "The script may fall back to mock data if the API key is missing."
fi

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
    pip install yfinance pandas numpy matplotlib tabulate pyyaml google-generativeai requests
fi

# Make sure results directory exists
mkdir -p results

# Test API access to verify credentials
echo "Testing API access..."
curl --silent --request GET \
    --url 'https://yahoo-finance166.p.rapidapi.com/api/stock/get-options?region=US&symbol=spy' \
    --header 'x-rapidapi-host: yahoo-finance166.p.rapidapi.com' \
    --header "x-rapidapi-key: $RAPIDAPI_KEY" \
    -o api_test_response.json

if [ -s api_test_response.json ]; then
    echo "API test successful! You have valid API access."
    rm api_test_response.json
else
    echo "API test failed. Please check your API key and try again."
fi

# Run the analysis
echo "Starting analysis with real data..."
python run_options_analysis.py "$TICKER"

# Deactivate the virtual environment
deactivate

echo "Analysis complete. Results are saved in the results directory." 