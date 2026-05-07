from datetime import datetime
import logging
from .signal_schema import SignalResult

logger = logging.getLogger(__name__)

class SentimentScorer:
    """
    Computes Sentiment divergence via VIX.
    VIX < 15 = complacency (vol suppressed, dealers long gamma)
    VIX 15-20 = normal
    VIX 20-30 = elevated fear (potential bottoming signal)
    VIX > 30 = extreme fear (capitulation zone)
    """
    def evaluate(self) -> SignalResult:
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")

        boost = 0
        reasons = []
        raw_data = {"vix": None, "vix_regime": None}

        try:
            import yfinance as yf
            vix_data = yf.Ticker('^VIX').history(period='5d')
            if not vix_data.empty:
                vix = round(float(vix_data['Close'].iloc[-1]), 2)
                vix_prev = round(float(vix_data['Close'].iloc[-2]), 2) if len(vix_data) >= 2 else vix
                vix_delta = round(vix - vix_prev, 2)
                raw_data["vix"] = vix
                raw_data["vix_prev"] = vix_prev
                raw_data["vix_1d_delta"] = vix_delta

                if vix > 30:
                    boost = 2
                    raw_data["vix_regime"] = "EXTREME_FEAR"
                    reasons.append(
                        f"VIX {vix} — extreme fear zone. Capitulation signal. "
                        f"Dealers SHORT gamma = vol amplified. Snap-back risk HIGH."
                    )
                elif vix > 20:
                    boost = 1
                    raw_data["vix_regime"] = "ELEVATED_FEAR"
                    reasons.append(
                        f"VIX {vix} — elevated fear. Potential bottoming signal. "
                        f"Watch for vol crush when fear subsides."
                    )
                elif vix < 13:
                    boost = -1
                    raw_data["vix_regime"] = "EXTREME_COMPLACENCY"
                    reasons.append(
                        f"VIX {vix} — extreme complacency. Dealers LONG gamma, "
                        f"vol suppressed. Risk of sudden spike."
                    )
                elif vix < 16:
                    raw_data["vix_regime"] = "SUPPRESSED"
                    reasons.append(
                        f"VIX {vix} — suppressed vol. Dealers LONG gamma, "
                        f"moves dampened. Good for slow grind."
                    )
                else:
                    raw_data["vix_regime"] = "NORMAL"

                # VIX spike = fear spike = potential reversal
                if vix_delta > 3:
                    raw_data["vix_spike"] = True
                    reasons.append(f"VIX spiked +{vix_delta:.1f} in 1 day — fear accelerating")
                elif vix_delta < -3:
                    raw_data["vix_crush"] = True
                    reasons.append(f"VIX crushed -{abs(vix_delta):.1f} in 1 day — fear subsiding = bullish")

        except Exception as e:
            logger.warning(f"Sentiment VIX fetch failed: {e}")

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
