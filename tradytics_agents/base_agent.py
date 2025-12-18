#!/usr/bin/env python3
"""
🎯 BASE TRADYTICS AGENT
Foundation class for all Tradytics feed-specific agents
"""

import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseTradyticsAgent(ABC):
    """
    Base class for all Tradytics agents with common functionality
    """

    def __init__(self, agent_name: str, feed_type: str):
        self.agent_name = agent_name
        self.feed_type = feed_type
        self.logger = logging.getLogger(f"{__name__}.{agent_name}")

        # Agent capabilities and context
        self.capabilities = []
        self.context_window = []  # Recent signals for context
        self.max_context_size = 10

        # Analysis weights (customizable per agent)
        self.confidence_weights = {
            'technical': 0.3,
            'fundamental': 0.2,
            'sentiment': 0.2,
            'institutional': 0.3
        }

    @abstractmethod
    def parse_alert(self, alert_text: str) -> Dict[str, Any]:
        """
        Parse raw alert text into structured data
        Must be implemented by each specialized agent
        """
        pass

    @abstractmethod
    def analyze_signal(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform agent-specific analysis
        Must be implemented by each specialized agent
        """
        pass

    def extract_symbols(self, text: str) -> List[str]:
        """Extract stock/crypto symbols from text"""
        # Common patterns: $AAPL, AAPL, BTC, ETH, etc.
        patterns = [
            r'\$([A-Z]{1,5})',  # $AAPL format
            r'\b([A-Z]{1,5})\b',  # AAPL format
            r'\b([A-Z]{2,5})\b'   # Crypto like BTC, ETH
        ]

        symbols = []
        for pattern in patterns:
            matches = re.findall(pattern, text.upper())
            symbols.extend(matches)

        # Filter out common words and duplicates
        exclude_words = {
            'A', 'I', 'ON', 'AT', 'IN', 'IS', 'IT', 'TO', 'OF', 'BY', 'OR',
            'AS', 'AN', 'BE', 'DO', 'FOR', 'IF', 'IN', 'IS', 'IT', 'NO',
            'SO', 'UP', 'US', 'WE', 'YES', 'ARE', 'BUT', 'THE', 'AND'
        }

        filtered_symbols = [
            s for s in symbols
            if s not in exclude_words and len(s) >= 2
        ]

        return list(set(filtered_symbols))  # Remove duplicates

    def extract_numbers(self, text: str) -> Dict[str, float]:
        """Extract numerical values (prices, volumes, percentages)"""
        numbers = {}

        # Price patterns: $123.45, 123.45
        price_match = re.search(r'[\$]?(\d+\.?\d*)', text)
        if price_match:
            numbers['price'] = float(price_match.group(1))

        # Volume patterns: 1.2M, 500K, 1M shares
        volume_patterns = [
            r'(\d+\.?\d*)(M|MM)',  # 1.2M format
            r'(\d+\.?\d*)(K)',     # 500K format
            r'(\d+)(?:\s*shares|\s*contracts)'  # 1000 shares format
        ]

        for pattern in volume_patterns:
            match = re.search(pattern, text.upper())
            if match:
                value = float(match.group(1))
                unit = match.group(2) if len(match.groups()) > 1 else ''

                if unit in ['M', 'MM']:
                    numbers['volume'] = value * 1_000_000
                elif unit == 'K':
                    numbers['volume'] = value * 1_000
                else:
                    numbers['volume'] = value
                break

        # Percentage patterns: 25%, +5.2%
        pct_match = re.search(r'([+-]?\d+\.?\d*)%', text)
        if pct_match:
            numbers['percentage'] = float(pct_match.group(1))

        return numbers

    def calculate_confidence(self, signal_data: Dict[str, Any]) -> float:
        """Calculate confidence score based on signal quality"""
        confidence = 0.0

        # Base confidence from data completeness
        if signal_data.get('symbols'):
            confidence += 0.2
        if signal_data.get('numbers'):
            confidence += 0.2
        if signal_data.get('sentiment') in ['bullish', 'bearish']:
            confidence += 0.2

        # Agent-specific confidence factors
        confidence += self._calculate_agent_confidence(signal_data)

        # Cap at 1.0
        return min(confidence, 1.0)

    @abstractmethod
    def _calculate_agent_confidence(self, signal_data: Dict[str, Any]) -> float:
        """Agent-specific confidence calculation"""
        pass

    def add_to_context(self, signal_data: Dict[str, Any]):
        """Add signal to context window for pattern recognition"""
        self.context_window.append({
            'timestamp': datetime.now(),
            'data': signal_data
        })

        # Keep only recent signals
        if len(self.context_window) > self.max_context_size:
            self.context_window.pop(0)

    def get_context_patterns(self) -> List[Dict[str, Any]]:
        """Extract patterns from context window"""
        if len(self.context_window) < 3:
            return []

        patterns = []

        # Simple pattern: repeated symbols
        symbol_counts = {}
        for signal in self.context_window[-5:]:  # Last 5 signals
            for symbol in signal['data'].get('symbols', []):
                symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1

        for symbol, count in symbol_counts.items():
            if count >= 2:  # Symbol mentioned multiple times
                patterns.append({
                    'type': 'repeated_symbol',
                    'symbol': symbol,
                    'frequency': count,
                    'timeframe': 'recent'
                })

        return patterns

    def generate_recommendation(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate trading recommendation based on analysis"""
        confidence = analysis.get('confidence', 0.5)
        direction = analysis.get('direction', 'neutral')

        if confidence > 0.7:
            if direction == 'bullish':
                action = 'BUY'
                rationale = f"Strong {self.feed_type} signal with {confidence:.1%} confidence"
            elif direction == 'bearish':
                action = 'SELL'
                rationale = f"Strong {self.feed_type} signal with {confidence:.1%} confidence"
            else:
                action = 'MONITOR'
                rationale = f"Significant {self.feed_type} activity detected"
        else:
            action = 'MONITOR'
            rationale = f"Monitor {self.feed_type} for confirmation"

        return {
            'action': action,
            'confidence': confidence,
            'rationale': rationale,
            'agent': self.agent_name,
            'feed_type': self.feed_type,
            'timestamp': datetime.now().isoformat()
        }

    def process_alert(self, alert_text: str) -> Dict[str, Any]:
        """
        Main processing pipeline for alerts
        """
        try:
            # Parse the alert
            parsed_data = self.parse_alert(alert_text)

            # Add basic extractions
            parsed_data['symbols'] = self.extract_symbols(alert_text)
            parsed_data['numbers'] = self.extract_numbers(alert_text)

            # Analyze the signal
            analysis = self.analyze_signal(parsed_data)

            # Calculate confidence
            analysis['confidence'] = self.calculate_confidence(parsed_data)

            # Add context patterns
            analysis['context_patterns'] = self.get_context_patterns()

            # Generate recommendation
            analysis['recommendation'] = self.generate_recommendation(analysis)

            # Add to context
            self.add_to_context(parsed_data)

            return {
                'success': True,
                'agent': self.agent_name,
                'feed_type': self.feed_type,
                'parsed_data': parsed_data,
                'analysis': analysis,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error processing {self.feed_type} alert: {e}")
            return {
                'success': False,
                'error': str(e),
                'agent': self.agent_name,
                'feed_type': self.feed_type,
                'timestamp': datetime.now().isoformat()
            }





