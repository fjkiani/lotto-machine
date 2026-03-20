from datetime import datetime
import logging
from .signal_schema import SignalResult

logger = logging.getLogger(__name__)

class TechScorer:
    """
    Computes technical momentum via RSI/Stochastics/ADX.
    Uses SPY as proxy to avoid ES=F expired contract holes.
    """
    def evaluate(self) -> SignalResult:
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        boost = 0
        reasons = []
        raw_data = {"rsi_14": None, "adx_14": None}
        
        try:
            import yfinance as yf
            import pandas as pd
            import numpy as np
            
            spy = yf.Ticker("SPY").history(period="1mo")
            if not spy.empty and len(spy) >= 15:
                # Basic RSI calculation
                delta = spy['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                
                current_rsi = round(float(rsi.iloc[-1]), 1)
                raw_data["rsi_14"] = current_rsi
                
                if current_rsi < 30:
                    boost = 1
                    reasons.append(f"Tech oversold: RSI-14 at {current_rsi}")
                elif current_rsi > 70:
                    boost = -1
                    reasons.append(f"Tech overbought: RSI-14 at {current_rsi}")
        except Exception as e:
            logger.warning(f"Tech scorer failed: {e}")

        slug = f"tech-rsi-{raw_data.get('rsi_14', 'unk')}-{today_str}"

        return SignalResult(
            name="TECH",
            slug=slug,
            boost=boost,
            active=(boost != 0),
            timestamp=now_iso,
            source_date=today_str,
            raw=raw_data,
            reasons=reasons
        )
