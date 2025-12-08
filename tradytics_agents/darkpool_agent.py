#!/usr/bin/env python3
"""
🎯 DARKPOOL AGENT
Specializes in block trades, iceberg detection, and institutional flow analysis
"""

import re
from typing import Dict, Any
from .base_agent import BaseTradyticsAgent

class DarkpoolAgent(BaseTradyticsAgent):
    """
    Specialized agent for Darkpool/Block Trade alerts
    Focus: Institutional accumulation/distribution, iceberg detection, flow analysis
    """

    def __init__(self):
        super().__init__("DarkpoolAgent", "darkpool")

        self.capabilities = [
            "block_trade_analysis",
            "iceberg_detection",
            "institutional_flow_mapping",
            "accumulation_distribution_signals",
            "large_holder_positioning"
        ]

        # High weight on institutional signals
        self.confidence_weights = {
            'technical': 0.1,
            'fundamental': 0.1,
            'sentiment': 0.1,
            'institutional': 0.7
        }

    def parse_alert(self, alert_text: str) -> Dict[str, Any]:
        """Parse darkpool/block trade alert"""
        parsed = {
            'alert_type': 'block_trade',
            'trade_size': None,
            'price': None,
            'direction': None,
            'block_type': 'single'  # single, sweep, iceberg
        }

        # Extract trade size
        size_match = re.search(r'[\$](\d+(?:\.\d+)?)\s*(?:M|MM|B)', alert_text, re.IGNORECASE)
        if size_match:
            value = float(size_match.group(1))
            unit = re.search(r'(M|MM|B)', alert_text[size_match.end():size_match.end()+3], re.IGNORECASE)
            if unit:
                if unit.group(1).upper() in ['M', 'MM']:
                    parsed['trade_size'] = value * 1_000_000
                elif unit.group(1).upper() == 'B':
                    parsed['trade_size'] = value * 1_000_000_000

        # Extract price
        price_match = re.search(r'[\$](\d+\.?\d*)', alert_text)
        if price_match and not parsed.get('trade_size'):  # Avoid confusing with size
            parsed['price'] = float(price_match.group(1))

        # Determine direction from context
        if any(word in alert_text.upper() for word in ['BUY', 'ACCUMULATION', 'LONG']):
            parsed['direction'] = 'bullish'
        elif any(word in alert_text.upper() for word in ['SELL', 'DISTRIBUTION', 'SHORT']):
            parsed['direction'] = 'bearish'

        # Detect block trade patterns
        if 'SWEEP' in alert_text.upper():
            parsed['block_type'] = 'sweep'
        elif 'ICEBERG' in alert_text.upper():
            parsed['block_type'] = 'iceberg'

        return parsed

    def analyze_signal(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze darkpool signal"""
        analysis = {
            'signal_strength': 'medium',
            'market_impact': 'high',
            'time_horizon': 'medium_term',
            'risk_level': 'medium',
            'institutional_bias': parsed_data.get('direction', 'neutral')
        }

        # Analyze trade size impact
        trade_size = parsed_data.get('trade_size', 0)
        if trade_size > 50_000_000:  # $50M+
            analysis['signal_strength'] = 'strong'
            analysis['market_impact'] = 'very_high'
            analysis['institutional_bias'] = parsed_data.get('direction', 'neutral')
        elif trade_size > 10_000_000:  # $10M+
            analysis['signal_strength'] = 'medium'
            analysis['market_impact'] = 'high'

        # Block type analysis
        block_type = parsed_data.get('block_type', 'single')
        if block_type == 'iceberg':
            analysis['stealth_factor'] = 'high'
            analysis['accumulation_pattern'] = 'likely'
        elif block_type == 'sweep':
            analysis['urgency_factor'] = 'high'
            analysis['momentum_signal'] = 'strong'

        return analysis

    def _calculate_agent_confidence(self, signal_data: Dict[str, Any]) -> float:
        """Darkpool-specific confidence calculation"""
        confidence = 0.0

        # Trade size confidence
        trade_size = signal_data.get('numbers', {}).get('volume', 0)
        if trade_size > 50_000_000:
            confidence += 0.4
        elif trade_size > 10_000_000:
            confidence += 0.3
        elif trade_size > 1_000_000:
            confidence += 0.2

        # Direction clarity
        if signal_data.get('direction'):
            confidence += 0.2

        # Block type specificity
        if signal_data.get('block_type') != 'single':
            confidence += 0.2

        return confidence
