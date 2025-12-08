#!/usr/bin/env python3
"""
🎯 OPTIONS SWEEPS AGENT
Specializes in options flow analysis, GEX positioning, and volatility signals
"""

import re
from typing import Dict, Any
from .base_agent import BaseTradyticsAgent

class OptionsSweepsAgent(BaseTradyticsAgent):
    """
    Specialized agent for Options Sweeps alerts
    Focus: Gamma exposure, volatility analysis, institutional positioning
    """

    def __init__(self):
        super().__init__("OptionsSweepsAgent", "options_sweeps")

        # Agent capabilities
        self.capabilities = [
            "gamma_exposure_analysis",
            "volatility_surface_mapping",
            "institutional_positioning",
            "sweep_pattern_recognition",
            "GEX_level_calculation"
        ]

        # Custom confidence weights for options analysis
        self.confidence_weights = {
            'technical': 0.2,
            'fundamental': 0.1,
            'sentiment': 0.1,
            'institutional': 0.6  # High weight on institutional options flow
        }

    def parse_alert(self, alert_text: str) -> Dict[str, Any]:
        """Parse options sweep alert into structured data"""
        parsed = {
            'alert_type': 'options_sweep',
            'option_type': None,
            'strike_price': None,
            'expiration': None,
            'volume': None,
            'premium': None,
            'direction': None
        }

        # Extract option type (CALL/PUT)
        if 'CALL' in alert_text.upper():
            parsed['option_type'] = 'call'
            parsed['direction'] = 'bullish'
        elif 'PUT' in alert_text.upper():
            parsed['option_type'] = 'put'
            parsed['direction'] = 'bearish'

        # Extract strike price
        strike_match = re.search(r'[\$]?(\d+\.?\d*)\s*(?:CALL|PUT)', alert_text, re.IGNORECASE)
        if strike_match:
            parsed['strike_price'] = float(strike_match.group(1))

        # Extract expiration (MM/DD format)
        exp_match = re.search(r'(\d{1,2}/\d{1,2})', alert_text)
        if exp_match:
            parsed['expiration'] = exp_match.group(1)

        # Extract premium amount
        premium_match = re.search(r'[\$](\d+(?:\.\d+)?)\s*(?:M|MM)', alert_text, re.IGNORECASE)
        if premium_match:
            value = float(premium_match.group(1))
            unit = 'M' if 'M' in alert_text[premium_match.end():premium_match.end()+2].upper() else 'MM'
            parsed['premium'] = value * (1_000_000 if unit == 'M' else 1_000_000)

        return parsed

    def analyze_signal(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze options sweep signal"""
        analysis = {
            'signal_strength': 'medium',
            'market_impact': 'moderate',
            'time_horizon': 'short_term',
            'risk_level': 'high',
            'institutional_bias': parsed_data.get('direction', 'neutral')
        }

        # Analyze premium size
        premium = parsed_data.get('premium', 0)
        if premium > 5_000_000:
            analysis['signal_strength'] = 'strong'
            analysis['market_impact'] = 'high'
        elif premium > 1_000_000:
            analysis['signal_strength'] = 'medium'
        else:
            analysis['signal_strength'] = 'weak'

        # Analyze strike proximity to spot
        # (Would need current price data for full analysis)

        # GEX analysis
        option_type = parsed_data.get('option_type')
        if option_type == 'call':
            analysis['gex_impact'] = 'negative'  # Calls reduce GEX
            analysis['dealer_positioning'] = 'short_gamma'
        elif option_type == 'put':
            analysis['gex_impact'] = 'positive'  # Puts increase GEX
            analysis['dealer_positioning'] = 'long_gamma'

        # Volatility analysis
        analysis['volatility_expectation'] = 'increasing' if premium > 2_000_000 else 'stable'

        return analysis

    def _calculate_agent_confidence(self, signal_data: Dict[str, Any]) -> float:
        """Options-specific confidence calculation"""
        confidence = 0.0

        # Premium size confidence
        premium = signal_data.get('numbers', {}).get('volume', 0)
        if premium > 5_000_000:
            confidence += 0.3
        elif premium > 1_000_000:
            confidence += 0.2

        # Option type clarity
        if signal_data.get('option_type'):
            confidence += 0.2

        # Strike price availability
        if signal_data.get('strike_price'):
            confidence += 0.2

        # Expiration clarity
        if signal_data.get('expiration'):
            confidence += 0.1

        return confidence
