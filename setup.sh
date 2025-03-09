#!/bin/bash

# Make script exit on first error
set -e

# Print commands before executing them
set -x

# Install system dependencies
apt-get update
apt-get install -y python3-dev build-essential

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Explicitly install plotly
pip install plotly==5.18.0

echo "Setup completed successfully!" 