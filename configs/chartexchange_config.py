#!/usr/bin/env python3
"""
CHARTEXCHANGE API CONFIGURATION
Set your API key here
"""

# ChartExchange API Configuration
CHARTEXCHANGE_API_KEY = "bhifaqd3cogwum9aedp00i2gvm5utuyn"  # Your actual API key
CHARTEXCHANGE_TIER = 1  # 1, 2, or 3 (affects rate limits)

# Rate Limits by Tier:
# Tier 1: 60 requests/minute
# Tier 2: 250 requests/minute  
# Tier 3: 1000 requests/minute

# Usage Instructions:
# 1. Get your API key from ChartExchange Premium tab
# 2. Replace "YOUR_API_KEY_HERE" with your actual API key
# 3. Set the appropriate tier based on your subscription
# 4. Run the test scripts to verify integration

def get_api_key():
    """Get ChartExchange API key"""
    if CHARTEXCHANGE_API_KEY == "YOUR_API_KEY_HERE":
        raise ValueError("Please set your ChartExchange API key in chartexchange_config.py")
    return CHARTEXCHANGE_API_KEY

def get_tier():
    """Get ChartExchange API tier"""
    return CHARTEXCHANGE_TIER
