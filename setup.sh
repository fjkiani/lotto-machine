#!/bin/bash

# Upgrade pip
python -m pip install --upgrade pip

# Install setuptools and wheel
pip install setuptools wheel

# Install requirements
pip install -r requirements.txt

# Install additional dependencies
pip install langchain langchain-anthropic langchain-groq langchain-openai langchain-google-genai langgraph

echo "Setup completed successfully!"