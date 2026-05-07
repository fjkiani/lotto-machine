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
                
                # DP signal logic:
                # SV% < 45% = low short volume = dark pool BUYING (institutions going long)
                # SV% 45-55% = neutral zone
                # SV% > 55% = heavy short volume = distribution or hedging
                # The bullish signal is LOW SV% (institutions accumulating, not shorting)
                dp_loading = sv_pct < 45.0
                dp_neutral = 45.0 <= sv_pct <= 55.0
                dp_distributing = sv_pct > 55.0

                if dp_loading:
                    boost = 2
                    raw_data["fed_dp_divergence"] = True
                    raw_data["dp_signal"] = "ACCUMULATION"
                    slug = f"fed-dp-loading-sv{sv_pct:.0f}-{today_str}"
                    reasons.append(
                        f"SPY dark pool ACCUMULATION: SV {sv_pct:.1f}% (below 45%) — "
                        f"institutions buying, not shorting. Bullish divergence."
                    )
                elif dp_distributing:
                    boost = 0
                    raw_data["fed_dp_divergence"] = False
                    raw_data["dp_signal"] = "DISTRIBUTION"
                    slug = f"fed-dp-distributing-sv{sv_pct:.0f}-{today_str}"
                    reasons.append(
                        f"SPY dark pool DISTRIBUTION: SV {sv_pct:.1f}% (above 55%) — "
                        f"heavy short volume, institutions hedging or selling."
                    )
                else:
                    raw_data["fed_dp_divergence"] = False
                    raw_data["dp_signal"] = "NEUTRAL"
                    slug = f"fed-dp-neutral-sv{sv_pct:.0f}-{today_str}"
                    
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
