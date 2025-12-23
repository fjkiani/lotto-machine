"""
Tradytics Analyzer Module

Generates savage LLM analysis of Tradytics alerts.
"""

import logging

logger = logging.getLogger(__name__)


class TradyticsAnalyzer:
    """
    Generates savage LLM analysis of parsed Tradytics alerts.
    """

    def __init__(self, savage_llm_service):
        self.savage_llm = savage_llm_service

    async def analyze_alert(self, alert_data, bot_name):
        """Generate savage LLM analysis of Tradytics alert"""
        try:
            # Create savage analysis prompt
            prompt = f"""
            🔥 **SAVAGE TRADYTICS ANALYSIS** 🔥

            Tradytics Bot: {bot_name}
            Alert Type: {alert_data.get('alert_type', 'unknown')}
            Symbols: {', '.join(alert_data.get('symbols', []))}
            Sentiment: {alert_data.get('sentiment', 'neutral')}
            Confidence: {alert_data.get('confidence', 0.5):.1%}

            Raw Alert: {alert_data.get('raw_text', '')}

            **YOUR MISSION:**
            Analyze this Tradytics alert like a ruthless alpha predator. What does this REALLY mean for the market? Is this a signal to BUY, SELL, or RUN? Connect the dots with broader market context. Be brutal, be insightful, be profitable.

            **RULES:**
            - No bullshit market mumbo-jumbo
            - Tell me what this means for REAL traders
            - If it's weak, say it's weak
            - If it's strong, tell me WHY it's strong
            - Give actionable insight, not vague predictions

            **SAVAGE ANALYSIS:**
            """

            # Get savage response
            response = await self.savage_llm.generate_savage_analysis(
                prompt,
                level="chained_pro",
                context="tradytics_integration"
            )

            return response

        except Exception as e:
            logger.error(f"❌ Error analyzing Tradytics alert: {e}")
            return None







