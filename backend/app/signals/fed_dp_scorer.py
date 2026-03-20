from datetime import datetime
import logging
from typing import List
from .signal_schema import SignalResult

logger = logging.getLogger(__name__)

class FedDpScorer:
    def __init__(self):
        try:
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
            self.client = StockgridClient(cache_ttl=300)
        except ImportError:
            self.client = None
            logger.warning("StockgridClient not found.")

    def evaluate(self, brain_reasons: List[str] = None) -> SignalResult:
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        if not self.client:
            return SignalResult(
                name="FED_DP", slug=f"fed-dp-unavailable-{today_str}", boost=0, active=False,
                timestamp=now_iso, source_date=today_str, raw={"error": "StockgridClient unavailable"}
            )
        
        try:
            spy_detail = self.client.get_ticker_detail('SPY')
            raw_data = {"spy_short_vol_pct": 0, "fed_dp_divergence": False}
            reasons = []
            boost = 0
            
            source_date = today_str
            if spy_detail:
                sv_pct = spy_detail.short_volume_pct or 0
                raw_data["spy_short_vol_pct"] = round(sv_pct, 2)
                source_date = spy_detail.date if hasattr(spy_detail, 'date') and spy_detail.date else today_str
                
                brain_tones = brain_reasons or []
                fed_hawkish = any('HAWKISH' in str(r).upper() for r in brain_tones)
                
                if fed_hawkish and sv_pct > 55:
                    boost = 3
                    raw_data["fed_dp_divergence"] = True
                    slug = f"fed-hawkish-dp-loading-sv{sv_pct:.0f}-{today_str}"
                    reasons.append(f"Fed HAWKISH + SPY dark pool loading ({sv_pct:.1f}% SV)")
                else:
                    raw_data["fed_dp_divergence"] = False
                    slug = f"fed-dp-neutral-{today_str}"
                    
            return SignalResult(
                name="FED_DP",
                slug=slug,
                boost=boost,
                active=(boost > 0),
                timestamp=now_iso,
                source_date=source_date,
                raw=raw_data,
                reasons=reasons
            )

        except Exception as e:
            logger.warning(f"Fed DP calculation failed: {e}")
            return SignalResult(
                name="FED_DP", slug=f"fed-dp-error-{today_str}", boost=0, active=False,
                timestamp=now_iso, source_date=today_str, raw={"error": str(e)}
            )
