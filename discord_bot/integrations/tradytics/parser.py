"""
Tradytics Parser Module

Parses Tradytics bot alerts into structured data.
"""

import logging
import re

logger = logging.getLogger(__name__)


class TradyticsParser:
    """
    Parses Tradytics bot alerts into structured data for analysis.
    """

    def parse_alert(self, alert_text, bot_name):
        """Parse Tradytics alert to extract structured data"""
        try:
            data = {
                'bot_name': bot_name,
                'raw_text': alert_text,
                'summary': alert_text[:200] + '...' if len(alert_text) > 200 else alert_text,
                'symbols': [],
                'alert_type': 'unknown',
                'sentiment': 'neutral',
                'confidence': 0.5
            }

            # Extract symbols (common patterns)
            symbol_pattern = r'\b[A-Z]{1,5}\b(?!\w)'  # 1-5 uppercase letters
            potential_symbols = re.findall(symbol_pattern, alert_text)

            # Filter for likely stock symbols (exclude common words)
            common_words = {'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS', 'ONE', 'OUR', 'HAD', 'BY', 'HOT', 'BUT', 'SOME', 'NEW', 'NOW', 'OLD', 'LOOK', 'COME', 'ITS', 'OVER', 'ONLY', 'THINK', 'ALSO', 'BACK', 'AFTER', 'USE', 'TWO', 'HOW', 'FIRST', 'WELL', 'EVEN', 'WANT', 'BEEN', 'GOOD', 'WOMAN', 'THROUGH', 'FEEL', 'SEEM', 'LOOK', 'LAST', 'CHILD', 'KEEP', 'GOING', 'BEFORE', 'GREAT', 'RIGHT', 'SMALL', 'WHERE', 'START', 'YOUNG', 'WHAT', 'THERE', 'WHEN', 'THING', 'DOWN', 'OUT', 'DOING', 'BEING', 'HERE', 'TODAY', 'GET', 'HAVE', 'MAKE', 'GIVE', 'MORE', 'FROM', 'SHOULD', 'COULD', 'THEIR', 'WHICH', 'TIME', 'WOULD', 'ABOUT', 'OTHER', 'THESE', 'INTO', 'MOST', 'THEM', 'THEN', 'SAID', 'EACH', 'WHICH', 'THEIR', 'TIME', 'WOULD', 'THERE', 'COULD', 'OTHER'}

            for symbol in potential_symbols:
                if symbol not in common_words and len(symbol) >= 2:
                    data['symbols'].append(symbol)

            # Determine alert type and sentiment based on bot
            if 'bullseye' in bot_name.lower():
                data['alert_type'] = 'options_signal'
                data['sentiment'] = 'bullish' if 'bull' in alert_text.lower() else 'bearish'
                data['confidence'] = 0.8
            elif 'sweeps' in bot_name.lower():
                data['alert_type'] = 'large_options_flow'
                data['sentiment'] = 'bullish' if any(word in alert_text.lower() for word in ['buy', 'bull', 'call']) else 'bearish'
                data['confidence'] = 0.9
            elif 'darkpool' in bot_name.lower():
                data['alert_type'] = 'darkpool_activity'
                data['sentiment'] = 'neutral'
                data['confidence'] = 0.7
            elif 'breakout' in bot_name.lower():
                data['alert_type'] = 'price_breakout'
                data['sentiment'] = 'bullish'
                data['confidence'] = 0.75

            return data

        except Exception as e:
            logger.error(f"❌ Error parsing Tradytics alert: {e}")
            return None







