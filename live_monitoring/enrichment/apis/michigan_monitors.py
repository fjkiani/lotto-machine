"""
live_monitoring/enrichment/apis/michigan_monitors.py — Stub for missing Michigan monitors.
"""
import logging

logger = logging.getLogger(__name__)

class MichiganSentimentMonitor:
    def predict(self) -> dict:
        return {
            "signal": "NEUTRAL",
            "confidence": 0.5,
            "edge": "UMich Sentiment stub — data feed pending",
            "consensus": 67.0,
            "delta": 0.0
        }

class MichiganExpectationsMonitor:
    def predict(self) -> dict:
        return {
            "signal": "NEUTRAL",
            "confidence": 0.5,
            "edge": "UMich Expectations stub — data feed pending",
            "consensus": 60.0,
            "delta": 0.0
        }
