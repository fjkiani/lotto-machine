#!/bin/bash

# Make script exit on first error
set -e

# Print commands before executing them
set -x

# Upgrade pip first
pip install --upgrade pip

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

# Install additional dependencies one by one to avoid conflicts
pip install matplotlib==3.9.2
pip install tabulate==0.9.0
pip install colorama==0.4.6
pip install questionary==2.1.0
pip install rich==13.9.4
pip install yfinance==0.2.35
pip install seaborn==0.13.0
pip install scikit-learn==1.3.2

# Install LangChain dependencies if needed
pip install langchain==0.3.0 || true
pip install langchain-anthropic==0.3.5 || true
pip install langchain-groq==0.2.3 || true
pip install langchain-openai==0.3.0 || true
pip install langgraph==0.2.56 || true

echo "Setup completed successfully!" 