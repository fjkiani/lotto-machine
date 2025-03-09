#!/usr/bin/env python3
"""
Script to check if the enhanced analysis pipeline module can be imported correctly.
"""

import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath('.'))

try:
    from src.analysis.enhanced_analysis_pipeline import EnhancedAnalysisPipeline
    print("Successfully imported EnhancedAnalysisPipeline")
    print(f"Module location: {EnhancedAnalysisPipeline.__module__}")
except ImportError as e:
    print(f"Failed to import EnhancedAnalysisPipeline: {e}")
    print(f"Python path: {sys.path}")
    
    # Check if the file exists
    file_path = os.path.join('src', 'analysis', 'enhanced_analysis_pipeline.py')
    if os.path.exists(file_path):
        print(f"File exists: {file_path}")
    else:
        print(f"File does not exist: {file_path}")
        
    # List the contents of the src/analysis directory
    analysis_dir = os.path.join('src', 'analysis')
    if os.path.exists(analysis_dir):
        print(f"Contents of {analysis_dir}:")
        for item in os.listdir(analysis_dir):
            print(f"  - {item}")
    else:
        print(f"Directory does not exist: {analysis_dir}") 