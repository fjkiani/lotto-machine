#!/bin/bash
# Run the Enhanced Manager Review test

echo "Testing Enhanced Manager Review System"
echo "======================================"

# Ensure we're in the project root
cd "$(dirname "$0")"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install required packages if not already installed
pip install pyyaml > /dev/null

# Run the test script
echo "Running enhanced manager test..."
python tools/test_enhanced_manager.py

# Display the results file
if [ -f "enhanced_review_results.json" ]; then
    echo -e "\nResults file created: enhanced_review_results.json"
    echo "Sample of results:"
    head -n 20 enhanced_review_results.json
fi

# Deactivate virtual environment
deactivate

echo -e "\nTest completed." 