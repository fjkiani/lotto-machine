#!/bin/bash

# Make script exit on first error
set -e

# Print commands before executing them
set -x

# Install system dependencies
apt-get update || true
apt-get install -y python3-distutils python3-dev build-essential || true

# Upgrade pip first
pip install --upgrade pip

# Install setuptools and wheel first
pip install setuptools==59.8.0 wheel==0.38.4

# Install dependencies one by one
pip install streamlit==1.22.0
pip install pandas==1.3.5
pip install numpy==1.21.6
pip install plotly==5.13.1
pip install matplotlib==3.5.3
pip install python-dotenv==0.21.1
pip install requests==2.28.2
pip install google-generativeai==0.3.1
pip install tabulate==0.9.0
pip install colorama==0.4.6
pip install rich==13.3.5
pip install pygments==2.14.0
pip install mdurl==0.1.2
pip install markdown-it-py==2.2.0

echo "Setup completed successfully!" 