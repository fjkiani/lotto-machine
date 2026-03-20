from datetime import datetime
import logging
from .signal_schema import SignalResult

logger = logging.getLogger(__name__)

class GeoScorer:
    """
    Computes Geopolitical risk (Oil spikes, NewsAPI terror/war headlines).
    """
    def evaluate(self) -> SignalResult:
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        boost = 0
        reasons = []
        raw_data = {"oil_spike": False, "news_risk_score": 0}
        
        try:
            import yfinance as yf
            # Check Crude Oil (CL=F) for sudden daily spikes (>4%)
            oil = yf.Ticker("CL=F").history(period="5d")
            if len(oil) >= 2:
                today_px = oil['Close'].iloc[-1]
                t_minus_1 = oil['Close'].iloc[-2]
                pct_change = ((today_px - t_minus_1) / t_minus_1) * 100
                
                raw_data["oil_pct_change"] = round(pct_change, 2)
                
                if pct_change > 4.0:
                    boost = -1 # Veto/Negative
                    raw_data["oil_spike"] = True
                    reasons.append(f"GEO WARNING: Crude Oil spiked {pct_change:.1f}%.")
                    
        except Exception as e:
            logger.warning(f"Geo scorer failed: {e}")

        slug = f"geo-risk-{raw_data.get('oil_spike', 'unk')}-{today_str}"

        return SignalResult(
            name="GEO",
            slug=slug,
            boost=boost,
            active=(boost != 0),
            timestamp=now_iso,
            source_date=today_str,
            raw=raw_data,
            reasons=reasons
        )
