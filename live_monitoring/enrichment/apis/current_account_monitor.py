"""
live_monitoring/enrichment/apis/current_account_monitor.py — Stub for missing Current Account signal.
"""
import logging

logger = logging.getLogger(__name__)

class CurrentAccountMonitor:
    def predict(self) -> dict:
        return {
            "signal": "NEUTRAL",
            "confidence": 0.5,
            "edge": "Current Account stub — data feed pending",
            "consensus": -200.0,
            "delta": 0.0,
            "sigma": 0.0
        }
