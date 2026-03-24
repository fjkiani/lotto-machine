"""
live_monitoring/enrichment/apis/pmi_predictor.py — Stub for missing PMI signal.
"""
import logging

logger = logging.getLogger(__name__)

class PMIPredictor:
    def predict(self) -> dict:
        return {
            "signal": "NEUTRAL",
            "confidence": 0.5,
            "edge": "PMI stub — data feed pending",
            "series": {
                "pmi_mfg": {"signal": "NEUTRAL"},
                "pmi_svcs": {"signal": "NEUTRAL"},
                "pmi_comp": {"signal": "NEUTRAL"}
            }
        }
