#!/bin/bash

# Make script exit on first error
set -e

# Print commands before executing them
set -x

# Upgrade pip first
pip install --upgrade pip

# Install minimal dependencies first
if [ -f requirements-minimal.txt ]; then
    echo "Installing minimal dependencies..."
    pip install -r requirements-minimal.txt
else
    echo "requirements-minimal.txt not found, using full requirements.txt"
    pip install -r requirements.txt
fi

# Explicitly install plotly
pip install plotly==5.18.0

# Install additional dependencies if needed
if [ -f requirements-minimal.txt ] && [ -f requirements.txt ]; then
    echo "Installing additional dependencies..."
    # Use --no-deps to avoid reinstalling packages that might cause conflicts
    pip install --no-deps -r requirements.txt
fi

echo "Setup completed successfully!" 