#!/bin/bash

# Make script exit on first error
set -e

# Print commands before executing them
set -x

# Install distutils (needed for Python 3.12)
apt-get update || true
apt-get install -y python3-distutils || true

# Upgrade pip first
pip install --upgrade pip

# Install setuptools with --ignore-installed to ensure we get a compatible version
pip install --ignore-installed setuptools wheel

# Install from the simple requirements file first
if [ -f requirements-simple.txt ]; then
    echo "Installing from simple requirements file..."
    pip install -r requirements-simple.txt
else
    echo "Simple requirements file not found, using manual installation"
    
    # Install numpy first (dependency of pandas)
    pip install numpy==1.24.0
    
    # Install pandas with binary option to avoid compilation
    pip install --only-binary=pandas pandas==1.5.3
    
    # Install streamlit
    pip install streamlit==1.32.0
    
    # Install plotly explicitly
    pip install plotly==5.18.0
    
    # Install other essential dependencies
    pip install python-dotenv==1.0.0
    pip install requests==2.31.0
    pip install google-generativeai==0.3.2
fi

# Try to install additional dependencies one by one
echo "Installing additional dependencies..."
pip install matplotlib==3.9.2 || true
pip install tabulate==0.9.0 || true
pip install colorama==0.4.6 || true
pip install questionary==2.1.0 || true
pip install rich==13.9.4 || true
pip install yfinance==0.2.35 || true
pip install seaborn==0.13.0 || true
pip install scikit-learn==1.3.2 || true

# Try to install LangChain dependencies
echo "Installing LangChain dependencies..."
pip install langchain==0.3.0 || true
pip install langchain-anthropic==0.3.5 || true
pip install langchain-groq==0.2.3 || true
pip install langchain-openai==0.3.0 || true
pip install langgraph==0.2.56 || true

echo "Setup completed successfully!" 