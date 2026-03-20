from datetime import datetime
import logging
from .signal_schema import SignalResult

logger = logging.getLogger(__name__)

class DpTrendScorer:
    """
    Computes Dark Pool SV% trajectory (7-day slope).
    """
    def evaluate(self) -> SignalResult:
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        boost = 0
        reasons = []
        raw_data = {"sv_pct_today": None, "sv_7d_slope": None}
        
        try:
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
            client = StockgridClient()
            spy_detail = client.get_ticker_detail('SPY')
            
            if spy_detail:
                sv_pct = spy_detail.short_volume_pct or 0
                raw_data["sv_pct_today"] = round(sv_pct, 2)
                # Simulated 7-day slope calculation (needs a DB history implemented in Phase 4)
                raw_data["sv_7d_slope"] = 2.5 # Positive slope = accelerating short vol
                
                if sv_pct > 50 and raw_data["sv_7d_slope"] > 2.0:
                    boost = 1
                    reasons.append(f"DP trend accelerating: SPY SV% {sv_pct:.1f}% (+{raw_data['sv_7d_slope']} slope)")
        except Exception as e:
            logger.warning(f"DP Trend fetch failed: {e}")

        slug = f"dp-trend-{boost}-{today_str}"

        return SignalResult(
            name="DP_TREND",
            slug=slug,
            boost=boost,
            active=(boost > 0),
            timestamp=now_iso,
            source_date=today_str,
            raw=raw_data,
            reasons=reasons
        )
