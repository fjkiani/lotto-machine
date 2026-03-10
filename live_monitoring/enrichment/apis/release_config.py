"""
📋 Release Config — Per-Category Thresholds & Direction Rules

All hardcoded values extracted from release_detector.py and made configurable.
Each category has its own thresholds calibrated from backtested historical data.

Usage:
    from release_config import CATEGORY_PROFILES, get_profile
    
    profile = get_profile('Existing Home Sales FEB')
    threshold = profile['neutral_threshold']  # 1.0 for housing vs 0.15 for CPI
"""

from enum import Enum
from typing import Dict, Optional


class ReleaseSignal(str, Enum):
    HAWKISH = "HAWKISH"
    HAWKISH_MILD = "HAWKISH_MILD"
    NEUTRAL = "NEUTRAL"
    DOVISH_MILD = "DOVISH_MILD"
    DOVISH = "DOVISH"


class SurpriseClass(str, Enum):
    BEAT = "BEAT"
    IN_LINE = "IN-LINE"
    MISS = "MISS"


# ═══════════════════════════════════════════════════════
# CATEGORY PROFILES — calibrated from backtest data
# ═══════════════════════════════════════════════════════
#
# Each profile defines:
#   neutral_threshold: surprise_pct below this → NEUTRAL (no signal)
#   mild_threshold:    surprise_pct below this → MILD signal
#   confidence_scale:  continuous scaling factor for confidence
#   direction_mode:    'rate_expectation' (INFLATION) or 'risk_sentiment' (GROWTH)
#   fed_sensitivity:   multiplier for FedShiftPredictor
#   value_type:        'absolute' or 'percentage' (determines surprise_pct method)
#   typical_market_impact: historical avg SPY move for 1% surprise
#
# Backtested calibration:
#   Housing: 4 releases → Oct (-0.98%) was false signal at old ±0.15 threshold
#            Dec (-4.10%) was real → DOVISH should be high confidence
#            → neutral_threshold raised to 1.0, confidence scales continuously
#
#   CPI: ±0.1% is material because the actual values are small (0.2-0.5%)
#        → neutral_threshold stays 0.10
#

CATEGORY_PROFILES = {
    'INFLATION': {
        'neutral_threshold': 0.10,       # ±0.10pp is noise for CPI/PCE
        'mild_threshold': 0.20,           # ±0.20pp is mild surprise
        'confidence_scale': 4.0,          # scale factor: conf = min(1.0, |surprise| * scale)
        'direction_mode': 'rate_expectation',  # hot CPI → HAWKISH → SPY↓
        'fed_sensitivity': 25.0,          # 1pp CPI surprise = 25% fed shift
        'value_type': 'percentage',       # CPI MoM values are percentages (0.2%, 0.3%)
        'typical_market_impact': 0.50,    # 1% surprise → ~0.50% SPY move
        'directions': {
            'HAWKISH':      {'SPY': '↓', 'TLT': '↓', 'DXY': '↑'},
            'HAWKISH_MILD': {'SPY': '↓', 'TLT': '↓'},
            'DOVISH_MILD':  {'SPY': '↑', 'TLT': '↑'},
            'DOVISH':       {'SPY': '↑', 'TLT': '↑', 'DXY': '↓'},
        },
    },
    'GROWTH': {
        'neutral_threshold': 1.0,        # ±1.0% is noise for housing/GDP/retail
        'mild_threshold': 2.5,            # ±2.5% is mild — backtested:
                                          #   Oct -0.98% → market ignored (EOD reversed)
                                          #   Jan -0.51% → barely moved
                                          #   Nov +2.44% → small rally  
                                          #   Dec -4.10% → big sell-off (real signal)
        'confidence_scale': 0.20,         # scale: conf = min(0.9, |surprise| * 0.20)
                                          #   -0.51% → 0.10  (very low — don't trade)
                                          #   -0.98% → 0.20  (low — use caution)
                                          #   +2.44% → 0.49  (medium — actionable)
                                          #   -4.10% → 0.82  (high — strong signal)
        'direction_mode': 'risk_sentiment',  # weak growth → SPY↓ (risk-off)
        'fed_sensitivity': 10.0,
        'value_type': 'absolute',         # housing is 3.91M, GDP is 1.4%... mixed
        'typical_market_impact': 0.08,    # 1% surprise → ~0.08% SPY move (low impact)
        'directions': {
            'HAWKISH':      {'SPY': '↑', 'TLT': '↓', 'DXY': '↑'},  # Strong → risk-on
            'HAWKISH_MILD': {'SPY': '↑', 'TLT': '↓'},
            'DOVISH_MILD':  {'SPY': '↓', 'TLT': '↑'},
            'DOVISH':       {'SPY': '↓', 'TLT': '↑', 'DXY': '↓'},  # Weak → risk-off
        },
    },
    'EMPLOYMENT': {
        'neutral_threshold': 0.50,        # ±0.50% is noise for NFP/claims
        'mild_threshold': 1.5,
        'confidence_scale': 0.50,
        'direction_mode': 'rate_expectation',  # weak employment → dovish → SPY↑
        'fed_sensitivity': 15.0,
        'value_type': 'absolute',
        'typical_market_impact': 0.25,
        'directions': {
            'HAWKISH':      {'SPY': '↓', 'TLT': '↓', 'DXY': '↑'},
            'HAWKISH_MILD': {'SPY': '↓', 'TLT': '↓'},
            'DOVISH_MILD':  {'SPY': '↑', 'TLT': '↑'},
            'DOVISH':       {'SPY': '↑', 'TLT': '↑', 'DXY': '↓'},
        },
    },
    'CONSUMER': {
        'neutral_threshold': 1.0,
        'mild_threshold': 3.0,
        'confidence_scale': 0.15,
        'direction_mode': 'risk_sentiment',
        'fed_sensitivity': 5.0,
        'value_type': 'absolute',
        'typical_market_impact': 0.05,
        'directions': {
            'HAWKISH':      {'SPY': '↑', 'TLT': '↓'},
            'HAWKISH_MILD': {'SPY': '↑', 'TLT': '↓'},
            'DOVISH_MILD':  {'SPY': '↓', 'TLT': '↑'},
            'DOVISH':       {'SPY': '↓', 'TLT': '↑'},
        },
    },
    'MANUFACTURING': {
        'neutral_threshold': 0.50,
        'mild_threshold': 1.5,
        'confidence_scale': 0.30,
        'direction_mode': 'risk_sentiment',
        'fed_sensitivity': 5.0,
        'value_type': 'absolute',
        'typical_market_impact': 0.10,
        'directions': {
            'HAWKISH':      {'SPY': '↑', 'TLT': '↓'},
            'HAWKISH_MILD': {'SPY': '↑', 'TLT': '↓'},
            'DOVISH_MILD':  {'SPY': '↓', 'TLT': '↑'},
            'DOVISH':       {'SPY': '↓', 'TLT': '↑'},
        },
    },
    'CENTRAL_BANK': {
        'neutral_threshold': 0.0,   # Any Fed action is material
        'mild_threshold': 0.0,
        'confidence_scale': 1.0,
        'direction_mode': 'direct',
        'fed_sensitivity': 0.0,     # Fed decisions are direct, not inferred
        'value_type': 'percentage',
        'typical_market_impact': 1.0,
        'directions': {},
    },
}

# Fallback for unknown categories
DEFAULT_PROFILE = {
    'neutral_threshold': 0.50,
    'mild_threshold': 2.0,
    'confidence_scale': 0.20,
    'direction_mode': 'rate_expectation',
    'fed_sensitivity': 3.0,
    'value_type': 'absolute',
    'typical_market_impact': 0.05,
    'directions': {
        'HAWKISH':      {'SPY': '↓', 'TLT': '↓'},
        'HAWKISH_MILD': {'SPY': '↓', 'TLT': '↓'},
        'DOVISH_MILD':  {'SPY': '↑', 'TLT': '↑'},
        'DOVISH':       {'SPY': '↑', 'TLT': '↑'},
    },
}


# ═══════════════════════════════════════════════════════
# EVENT → CATEGORY MAPPING
# ═══════════════════════════════════════════════════════

CATEGORY_MAP = {
    'cpi': 'INFLATION',    'inflation': 'INFLATION', 'pce': 'INFLATION',
    'ppi': 'INFLATION',    'core cpi': 'INFLATION', 'core pce': 'INFLATION',
    'nonfarm': 'EMPLOYMENT', 'non farm': 'EMPLOYMENT', 'payrolls': 'EMPLOYMENT',
    'unemployment': 'EMPLOYMENT', 'jobless': 'EMPLOYMENT', 'jolts': 'EMPLOYMENT',
    'adp employment': 'EMPLOYMENT',
    'gdp': 'GROWTH',       'durable goods': 'GROWTH', 'retail sales': 'GROWTH',
    'industrial production': 'GROWTH', 'factory orders': 'GROWTH',
    'existing home': 'GROWTH', 'new home': 'GROWTH', 'pending home': 'GROWTH',
    'housing starts': 'GROWTH', 'home sales': 'GROWTH', 'building permits': 'GROWTH',
    'consumer confidence': 'CONSUMER', 'michigan': 'CONSUMER',
    'ism': 'MANUFACTURING', 'pmi': 'MANUFACTURING', 'empire state': 'MANUFACTURING',
    'philadelphia fed': 'MANUFACTURING', 'chicago pmi': 'MANUFACTURING',
    'fed interest': 'CENTRAL_BANK', 'fomc': 'CENTRAL_BANK',
}


# ═══════════════════════════════════════════════════════
# VALUE TYPE DETECTION — smarter than <100 heuristic
# ═══════════════════════════════════════════════════════

# Events where the VALUES are already percentages (not absolute numbers)
PERCENTAGE_EVENTS = {
    'cpi', 'core cpi', 'pce', 'core pce', 'ppi',
    'inflation rate', 'core inflation',
    'gdp growth', 'unemployment', 'fed interest',
    'mom', 'yoy', 'qoq',  # any monthly/yearly/quarterly change
}


def classify_category(event_name: str) -> str:
    """Map event name to category using keyword matching."""
    lower = event_name.lower()
    for keyword, cat in CATEGORY_MAP.items():
        if keyword in lower:
            return cat
    return 'OTHER'


def get_profile(event_name: str) -> dict:
    """Get the full configuration profile for an event."""
    category = classify_category(event_name)
    profile = CATEGORY_PROFILES.get(category, DEFAULT_PROFILE).copy()
    profile['category'] = category
    
    # Override value_type based on event name patterns
    lower = event_name.lower()
    for pct_keyword in PERCENTAGE_EVENTS:
        if pct_keyword in lower:
            profile['value_type'] = 'percentage'
            break
    
    return profile


def is_percentage_value(event_name: str, value: float) -> bool:
    """
    Determine if a value is already a percentage (like CPI 0.3%)
    vs an absolute number (like Home Sales 3.91M).
    
    Uses ONLY explicit keyword matching — no heuristic fallback.
    The old fallback (abs(value) < 20) was a sandbag: it falsely
    classified Housing (3.91M) as percentage data, making all 
    Housing surprises compute as absolute diff instead of relative %.
    """
    lower = event_name.lower()
    for kw in PERCENTAGE_EVENTS:
        if kw in lower:
            return True
    
    # No fallback — if it's not in PERCENTAGE_EVENTS, it's absolute.
    # Add the event keyword to PERCENTAGE_EVENTS if it should be treated as %.
    return False
