#!/bin/bash

# Make script exit on first error
set -e

# Print commands before executing them
set -x

# Upgrade pip first
pip install --upgrade pip

# Install modern setuptools and wheel
pip install setuptools>=61.0 wheel

# Create necessary directory structure if it doesn't exist
mkdir -p src/analysis

# Copy enhanced_analysis_pipeline.py to the correct location if it exists
if [ -f "enhanced_analysis_pipeline.py" ]; then
    cp enhanced_analysis_pipeline.py src/analysis/
fi

# Create __init__.py files if they don't exist
touch src/__init__.py
touch src/analysis/__init__.py

# Add imports to __init__.py files
echo '"""AI Hedge Fund project."""' > src/__init__.py
echo '"""Analysis modules for the AI Hedge Fund project."""' > src/analysis/__init__.py
echo 'try:' >> src/analysis/__init__.py
echo '    from .enhanced_analysis_pipeline import EnhancedAnalysisPipeline' >> src/analysis/__init__.py
echo 'except ImportError:' >> src/analysis/__init__.py
echo '    pass' >> src/analysis/__init__.py

# Install the package in development mode using PEP 517
pip install -e .

# Explicitly install key dependencies to ensure they're available
pip install streamlit>=1.28.0
pip install numpy>=1.26.0
pip install pandas>=2.0.0
pip install plotly>=5.18.0

echo "Setup completed successfully!" 