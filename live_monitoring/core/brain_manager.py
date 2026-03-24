"""
🧠 Zeta Brain Manager — The Singleton
====================================
Provides a single, global access point for the FedOfficialsBrain.
Includes retry-on-failure: if brain init fails, retries on next get_report() call.
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

class BrainManager:
    """
    Singleton manager for the FedOfficialsBrain.
    Ensures one brain instance across all consumers.
    If init fails, retries on next call (not silently dead forever).
    """
    _instance: Optional['BrainManager'] = None
    _lock = threading.Lock()
    _brain = None
    _init_attempts = 0

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BrainManager, cls).__new__(cls)
                cls._instance._init_brain()
            return cls._instance

    def _init_brain(self):
        """Initialize the actual brain instance. Logs clearly on failure."""
        self._init_attempts += 1
        try:
            from live_monitoring.agents.fed_officials.brain import FedOfficialsBrain
            self._brain = FedOfficialsBrain()
            logger.info("🧠 BrainManager singleton initialized successfully.")
        except Exception as e:
            logger.error(
                f"❌ BrainManager init FAILED (attempt {self._init_attempts}): {e}",
                exc_info=True
            )
            self._brain = None

    def get_brain(self):
        """Get the global brain instance. Retries init if previous attempt failed."""
        if self._brain is None and self._init_attempts < 3:
            logger.warning(f"🔄 Brain was None. Retry attempt {self._init_attempts + 1}/3...")
            self._init_brain()
        return self._brain

    def get_report(self, use_cache: bool = True):
        """
        Get the latest brain report.
        If brain is None, retries init. If still None, returns empty dict
        with error flag so consumers know brain is down (not silently skipped).
        """
        brain = self.get_brain()
        if not brain:
            logger.error("❌ Brain unavailable after retries. Returning error report.")
            return {
                "error": "brain_unavailable",
                "divergence_boost": 0,
                "reasons": ["⚠️ FedOfficialsBrain failed to initialize — Fed intelligence offline"],
                "fed_tone_summary": [],
                "hidden_hands": {},
                "finnhub_signals": [],
                "finnhub_news": {},
                "timestamp": None,
            }
        return brain.get_brain_report(force_refresh=not use_cache)
