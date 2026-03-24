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
            result = self.calc.compute_gex("SPY")
            
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

            # ── Rule: NEGATIVE gamma + spot ABOVE max_pain → gravitational pull DOWN ──
            max_pain = result.max_pain
            if regime == "NEGATIVE" and max_pain and spot > max_pain:
                gex_add += 1
                reasons.append(
                    f"NEGATIVE gamma, spot {spot:.2f} > max_pain {max_pain:.2f} — gravitational pull DOWN"
                )

            # Context only VIX
            try:
                import yfinance as yf
                vix_data = yf.Ticker('^VIX').history(period='1d')
                if not vix_data.empty:
                    raw_data['vix'] = round(float(vix_data['Close'].iloc[-1]), 2)
            except Exception:
                pass

            # ── Rule: spot pinned between EMA-200 and next confluence above → no edge ──
            ema_200 = None
            next_above = None
            try:
                from live_monitoring.enrichment.apis.pivot_calculator import PivotCalculator
                piv = PivotCalculator()
                piv_result = piv.compute('SPY')
                if piv_result and piv_result.ema_200:
                    ema_200 = piv_result.ema_200
                    raw_data['ema_200'] = round(ema_200, 2)
                    # Quick confluence: any Classic/Fib/Cam level > spot within 5 pts
                    lvls = sorted([l['price'] for l in piv_result.all_levels_flat() if l['price'] > spot])
                    next_above = lvls[0] if lvls else None
                    raw_data['next_above'] = next_above
            except Exception:
                pass

            if ema_200 and next_above and ema_200 < spot < next_above:
                reasons.append(
                    f"SPY pinned between EMA-200 ({ema_200:.2f}) and confluence ({next_above:.2f}) — no directional edge"
                )

            # ── Rule: squeeze risk check ─────────────────────────────────────
            try:
                t_spy = yf.Ticker('SPY')
                spy_info = t_spy.info
                si_pct = float(spy_info.get('shortPercentOfFloat') or 0) * 100
                short_ratio = float(spy_info.get('shortRatio') or 0)
                si_score = min((si_pct / 30) * 40, 40)
                borrow_score = min(short_ratio * 2, 30)
                squeeze_score = round(si_score + borrow_score, 1)
                raw_data['spy_si_pct'] = round(si_pct, 2)
                raw_data['spy_days_to_cover'] = round(short_ratio, 1)
                raw_data['spy_squeeze_score'] = squeeze_score
                if squeeze_score >= 60:
                    reasons.append(
                        f"Elevated squeeze risk: score {squeeze_score:.0f}, "
                        f"SI {si_pct:.1f}%, DTC {short_ratio:.1f}d "
                        f"\u2014 cap short conviction."
                    )
                    # Penalize confidence cap for short-side signals only
                    raw_data['squeeze_confidence_penalty'] = 10
            except Exception as _sq_err:
                logger.debug(f'Squeeze risk check failed: {_sq_err}')

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
