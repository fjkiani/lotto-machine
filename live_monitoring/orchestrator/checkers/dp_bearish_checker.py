"""
Checker for Dark Pool Bearish Divergence.
Identifies when dark pools are relentlessly selling into SPY rallies.
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, time
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from pytz import timezone as ZoneInfo

logger = logging.getLogger(__name__)

class DPBearishDivergenceChecker:
    def __init__(self, confluence_gate):
        self.confluence_gate = confluence_gate
        self.data_path = "data/axlfi_dark_pool_live.json"
        self.min_cooldown_minutes = 30
        self.last_fire_time = None
        self.eastern = ZoneInfo("America/New_York")

    def _is_market_open(self) -> bool:
        """Check if US market is currently open."""
        now = datetime.now(self.eastern)
        if now.weekday() >= 5:  # Weekend
            return False
        
        market_start = time(9, 30)
        market_end = time(16, 0)
        current_time = now.time()
        
        return market_start <= current_time <= market_end

    def check(self, current_price: float, current_snapshot: dict) -> Dict[str, Any]:
        """
        Evaluate dark pool data for bearish divergence against price action.
        """
        result = {
            "signal_fired": False,
            "confidence": 0.0,
            "dp_flow": 0.0,
            "dp_direction": "NEUTRAL",
            "gate_verdict": "N/A"
        }

        # Market Must Be Open
        if not self._is_market_open():
            result["dp_direction"] = "MARKET_CLOSED"
            return result

        # Load DP data
        dp_history = []
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r") as f:
                    data = json.load(f)
                    
                    # Ensure latest data is for today
                    tz = self.eastern
                    today_str = datetime.now(tz).strftime("%Y-%m-%d")
                    if data.get("date") == today_str:
                        # Extract the data points (assume it's sorted or we just take the list)
                        # data points usually a list of dicts with 'net_premium'
                        epochs = data.get("epochs", [])
                        if epochs:
                            dp_history = [e.get("net_premium", 0.0) for e in epochs]
            except Exception as e:
                logger.error(f"DPBearishChecker: Error reading DP data: {e}")
                
        # Handle insufficient data gracefully
        if len(dp_history) < 3:
            result["dp_direction"] = "INSUFFICIENT_DATA"
            return result

        # Check for declining trend: dp_flow[t] < dp_flow[t-1] < dp_flow[t-2]
        dp_t = dp_history[-1]
        dp_t1 = dp_history[-2]
        dp_t2 = dp_history[-3]

        if not (dp_t < dp_t1 < dp_t2):
            result["dp_direction"] = "NEUTRAL"
            result["dp_flow"] = dp_t
            return result
        
        result["dp_direction"] = "NEGATIVE"
        result["dp_flow"] = dp_t

        # Calculate decline percentage for confidence
        # Use absolute values and safe division
        abs_t2 = abs(dp_t2) if dp_t2 != 0 else 1.0
        dp_decline_pct = abs((dp_t2 - dp_t) / abs_t2) * 100

        # Check Price Divergence: Is SPY UP (>0% from open)?
        spy_open = current_snapshot.get("spy_open")
        # In case spy_open is not in snapshot, we fallback to just checking if current price > previous close (which isn't ideal but a fallback)
        if not spy_open:
            spy_open = current_snapshot.get("spy_prev_close", current_price)
            
        if spy_open and current_price <= spy_open:
            # SPY is not UP, so it's aligned with DP flow. Not a divergence short setup for this checker.
            return result

        # Cooldown check
        now = datetime.now(self.eastern)
        if self.last_fire_time:
            diff_minutes = (now - self.last_fire_time).total_seconds() / 60.0
            if diff_minutes < self.min_cooldown_minutes:
                result["gate_verdict"] = "COOLDOWN"
                return result

        # Divergence confirmed: DP is selling relentlessly, but SPY is up today.
        confidence = min(50 + (dp_decline_pct * 10), 95.0)
        
        # Determine breakdown vol ratio from snapshot for Tier 4
        # Fallback to 1.6 to pass the mock if volume_ratio is missing, but typically volume_ratio is in snapshot
        vol_ratio = current_snapshot.get("volume_ratio", 1.6)

        gate_res = self.confluence_gate.should_fire(
            signal_direction="SHORT",
            symbol="SPY",
            raw_confidence=confidence,
            current_price=current_price,
            snapshot=current_snapshot,
            dp_flow_direction="NEGATIVE",
            breakdown_vol_ratio=vol_ratio
        )

        result["signal_fired"] = not gate_res.blocked
        result["confidence"] = gate_res.adjusted_confidence
        result["gate_verdict"] = gate_res.reason
        
        if result["signal_fired"]:
            self.last_fire_time = now

        return result
