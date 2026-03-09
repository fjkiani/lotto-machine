import os
import sys
import importlib
import inspect
from typing import Dict, List, Type

# Add base path so imports work correctly
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if base_path not in sys.path:
    sys.path.insert(0, base_path)

from backtesting.simulation.base_detector import BaseDetector

class DetectorRegistry:
    """
    Dynamically discovers and loads all valid Signal Detectors in the codebase.
    Replaces the monolithic `try/except` initialization block from the old backtester.
    """
    
    def __init__(self):
        self._detectors: Dict[str, BaseDetector] = {}
        self._failed_loads: Dict[str, str] = {}
        
    def load_all(self):
        """
        Hardcodes the known working detectors for now to ensure stability,
        but initializes them in a safe, isolated manner.
        """
        # 1. CORE MOMENTUM SIGNALS
        try:
            from backtesting.simulation.selloff_rally_detector import SelloffRallyDetector
            self._register("selloff_rally", SelloffRallyDetector())
        except Exception as e:
            self._failed_loads["selloff_rally"] = str(e)
            
        try:
            from backtesting.simulation.gap_detector import GapDetector
            self._register("gap", GapDetector())
        except Exception as e:
            self._failed_loads["gap"] = str(e)

        # 2. OPTIONS & FLOW
        try:
            from backtesting.simulation.rapidapi_options_detector import RapidAPIOptionsDetector
            self._register("options_flow", RapidAPIOptionsDetector())
        except Exception as e:
            self._failed_loads["options_flow"] = str(e)

        # 3. EXPLOITATION SIGNALS
        # These previously required ChartExchange which is dead. Providing safe fallbacks or omitting.
        
        try:
            from live_monitoring.exploitation.gamma_tracker import GammaTracker
            self._register("gamma", GammaTracker())
        except Exception as e:
            self._failed_loads["gamma"] = str(e)
            
        # ⚠️ ChartExchange API is confirmed dead (403 Forbidden). 
        # Even if the key exists in .env, these detectors will hang the replay.
        self._failed_loads["chartexchange_group"] = "API confirmed dead (403). Detectors disabled."

    def _register(self, key: str, instance: BaseDetector):
        self._detectors[key] = instance
        
    def get_all(self) -> Dict[str, BaseDetector]:
        return self._detectors
        
    def get(self, name: str) -> BaseDetector:
        return self._detectors.get(name)

    def print_status(self):
        print(f"\n📊 LOADED {len(self._detectors)} DETECTORS: {', '.join(self._detectors.keys())}")
        if self._failed_loads:
            print(f"⚠️ FAILED TO LOAD: {len(self._failed_loads)} Detectors")
            for name, reason in self._failed_loads.items():
                print(f"  - {name}: {reason}")
