from datetime import datetime
import logging
from .signal_schema import SignalResult

logger = logging.getLogger(__name__)

class GexScorer:
    def __init__(self):
        try:
            from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator
            self.calc = GEXCalculator(cache_ttl=300)
        except ImportError:
            self.calc = None
            logger.warning("GEXCalculator not found.")

    def evaluate(self, cot_boost: int = 0) -> SignalResult:
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        if not self.calc:
            return SignalResult(
                name="GEX", slug=f"gex-unavailable-{today_str}", boost=0, active=False,
                timestamp=now_iso, source_date=today_str, raw={"error": "GEXCalculator unavailable"}
            )

        gex_add = 0
        reasons = []
        raw_data = {}
        
        try:
            result = self.calc.compute_gex("SPX")
            
            total_gex = result.total_gex
            regime = result.gamma_regime
            gamma_flip = result.gamma_flip
            spot = result.spot_price

            raw_data = {
                "total_gex_dollars": round(total_gex, 0),
                "gex_regime": f"{'STRONG_' if abs(total_gex) > 10e9 else 'MILD_'}{regime}",
                "gex_gamma_flip": round(gamma_flip, 1) if gamma_flip else None,
                "gex_spot_price": round(spot, 2),
                "gex_max_pain": round(result.max_pain, 1) if result.max_pain else None,
                "gex_source": "CBOE delayed (free, no auth)"
            }

            is_strong_negative = regime == "NEGATIVE" and abs(total_gex) > 10e9

            if is_strong_negative:
                if cot_boost >= 3:
                    gex_add = 2
                    reasons.append(f"GEX STRONG_NEGATIVE (${total_gex/1e9:.1f}B) + COT EXTREME → coil loaded, snap-back velocity maximum")
                else:
                    gex_add = 0  # Volatile but no direction confirmed
                    reasons.append(f"GEX NEGATIVE (${total_gex/1e9:.1f}B) — amplifying regime, awaiting COT confirmation")
            elif regime == "POSITIVE" and total_gex > 5e9:
                gex_add = 1
                reasons.append(f"GEX STRONG_POSITIVE (${total_gex/1e9:.1f}B) — dealers dampen moves, support floor active")

            # Context only VIX
            try:
                import yfinance as yf
                vix_data = yf.Ticker('^VIX').history(period='1d')
                if not vix_data.empty:
                    raw_data['vix'] = round(float(vix_data['Close'].iloc[-1]), 2)
            except Exception:
                pass

            if gamma_flip:
                above_below = "ABOVE" if spot > gamma_flip else "BELOW"
                slug = f"gex-{regime.lower()}-flip-{gamma_flip:.0f}-spot-{above_below.lower()}-{today_str}"
            else:
                slug = f"gex-{regime.lower()}-{today_str}"

            return SignalResult(
                name="GEX",
                slug=slug,
                boost=gex_add,
                active=(gex_add > 0),
                timestamp=now_iso,
                source_date=today_str,
                raw=raw_data,
                reasons=reasons
            )
            
        except Exception as e:
            logger.warning(f"GEX calculation failed: {e}")
            return SignalResult(
                name="GEX", slug=f"gex-error-{today_str}", boost=0, active=False,
                timestamp=now_iso, source_date=today_str, raw={"error": str(e)}
            )
