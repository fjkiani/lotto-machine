from datetime import datetime
import logging
from .signal_schema import SignalResult

logger = logging.getLogger(__name__)

class CotScorer:
    def __init__(self):
        try:
            from live_monitoring.enrichment.apis.cot_client import COTClient
            self.client = COTClient(cache_ttl=3600)
        except ImportError:
            self.client = None
            logger.warning("COTClient not found.")

    def evaluate(self, symbol: str = "ES") -> SignalResult:
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")

        if not self.client:
            return SignalResult(
                name="COT", slug=f"cot-unavailable-{today_str}", boost=0, active=False,
                timestamp=now_iso, source_date=today_str, raw={"error": "COTClient unavailable"}
            )
        
        try:
            cot_div = self.client.get_divergence_signal(symbol)
            cot_add = 0
            reasons = []
            raw_data = {"cot_divergent": False, "cot_specs_net": 0, "cot_comm_net": 0}
            report_date = today_str

            if cot_div and cot_div.get("divergent"):
                specs = cot_div.get("specs_net", 0)
                comms = cot_div.get("comm_net", 0)
                report_date = cot_div.get('report_date', today_str)
                
                raw_data["cot_divergent"] = True
                raw_data["cot_specs_net"] = specs
                raw_data["cot_comm_net"] = comms

                # Primary signal: specs crowded short (regardless of commercial magnitude)
                # Commercials just need to be on the other side (divergent=True already confirmed)
                if specs < -100_000:
                    cot_add = 3
                    reasons.append(
                        f"COT EXTREME: specs {specs:+,} net short — maximum squeeze fuel. "
                        f"Commercials {comms:+,} on opposite side = divergence confirmed."
                    )
                elif specs < -50_000:
                    cot_add = 1
                    reasons.append(
                        f"COT mild: specs {specs:+,} net short — moderate squeeze setup. "
                        f"Commercials {comms:+,} diverging."
                    )

            slug = f"cot-{'extreme' if cot_add >= 3 else 'mild' if cot_add > 0 else 'neutral'}-{report_date}"

            return SignalResult(
                name="COT",
                slug=slug,
                boost=cot_add,
                active=(cot_add > 0),
                timestamp=now_iso,
                source_date=report_date,
                raw=raw_data,
                reasons=reasons
            )

        except Exception as e:
            logger.warning(f"COT module failed: {e}")
            return SignalResult(
                name="COT", slug=f"cot-error-{today_str}", boost=0, active=False,
                timestamp=now_iso, source_date=today_str, raw={"error": str(e)}
            )
