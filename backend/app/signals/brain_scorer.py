from datetime import datetime
import logging
from .signal_schema import SignalResult

logger = logging.getLogger(__name__)

class BrainScorer:
    def __init__(self):
        try:
            from live_monitoring.core.brain_manager import BrainManager
            self.manager = BrainManager()
        except ImportError:
            self.manager = None
            logger.warning("BrainManager not found.")

    def evaluate(self) -> SignalResult:
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")

        if not self.manager:
            return SignalResult(
                name="BRAIN", slug=f"brain-unavailable-{today_str}", boost=0, active=False,
                timestamp=now_iso, source_date=today_str, raw={"error": "BrainManager unavailable"}
            )
        
        try:
            report = self.manager.get_report(use_cache=True)
            if not report:
                return SignalResult(
                    name="BRAIN", slug=f"brain-empty-{today_str}", boost=0, active=False,
                    timestamp=now_iso, source_date=today_str, raw={"error": "Empty report"}
                )

            boost = report.get('divergence_boost', 0)
            reasons = report.get('reasons', [])
            
            raw_data = {k: v for k, v in report.items() if k not in ['reasons']}

            return SignalResult(
                name="BRAIN",
                slug=f"brain-conviction-{today_str}",
                boost=boost,
                active=(boost > 0),
                timestamp=now_iso,
                source_date=today_str,
                raw=raw_data,
                reasons=[f"Brain: {r}" for r in reasons]
            )

        except Exception as e:
            logger.warning(f"Brain integration failed: {e}")
            return SignalResult(
                name="BRAIN", slug=f"brain-error-{today_str}", boost=0, active=False,
                timestamp=now_iso, source_date=today_str, raw={"error": str(e)}
            )
