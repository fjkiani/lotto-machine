#!/bin/bash

# Make script exit on first error
set -e

# Print commands before executing them
set -x

# Upgrade pip first
pip install --upgrade pip

# Install modern setuptools and wheel
pip install setuptools>=61.0 wheel

# Install the package in development mode using PEP 517
pip install -e .

# Explicitly install key dependencies to ensure they're available
pip install streamlit>=1.28.0
pip install numpy>=1.26.0
pip install pandas>=2.0.0
pip install plotly>=5.18.0

echo "Setup completed successfully!" 