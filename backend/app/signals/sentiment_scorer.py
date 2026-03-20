from datetime import datetime
import logging
from .signal_schema import SignalResult

logger = logging.getLogger(__name__)

class SentimentScorer:
    """
    Computes Sentiment divergence. 
    Metrics: VIX (yfinance), AAII/Put-Call ratio.
    """
    def evaluate(self) -> SignalResult:
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        boost = 0
        reasons = []
        raw_data = {"vix": None, "put_call_ratio": None, "aaii_bull_bear_spread": None}
        
        try:
            import yfinance as yf
            vix_data = yf.Ticker('^VIX').history(period='1d')
            if not vix_data.empty:
                vix = round(float(vix_data['Close'].iloc[-1]), 2)
                raw_data["vix"] = vix
                if vix < 12.0:
                    boost -= 1
                    reasons.append("VIX deeply compressed (< 12) - high complacency risk")
                elif vix > 25.0:
                    boost += 1
                    reasons.append("VIX elevated (> 25) - fear is high, potential bottoming")
        except Exception as e:
            logger.warning(f"Sentiment vix fetch failed: {e}")

        # AAII / PutCall are placeholders to be wired to a DB or premium API later.
        raw_data["put_call_ratio"] = 0.9  # simulated neutral
        raw_data["aaii_bull_bear_spread"] = 15.0 # simulated mildly bullish
        
        slug = f"sentiment-vix-{raw_data.get('vix', 'unk')}-{today_str}"

        return SignalResult(
            name="SENTIMENT",
            slug=slug,
            boost=boost,
            active=(boost != 0),
            timestamp=now_iso,
            source_date=today_str,
            raw=raw_data,
            reasons=reasons
        )
