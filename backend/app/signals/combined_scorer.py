from datetime import datetime
from .signal_schema import SignalResult

class CombinedScorer:
    def evaluate(self, gex_result: SignalResult, cot_result: SignalResult) -> SignalResult:
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")

        cot_extreme = cot_result.boost >= 3
        cot_mild = cot_result.boost >= 1
        gex_regime_str = gex_result.raw.get('gex_regime', '')
        gex_strong_neg = 'STRONG_NEGATIVE' in gex_regime_str or 'NEGATIVE' in gex_regime_str
        gex_positive = 'POSITIVE' in gex_regime_str

        # Pull enrichment data from GEX raw (populated by main.py enrichment block)
        axlfi_signal = gex_result.raw.get('axlfi_signal', '')
        pts_above_call = gex_result.raw.get('pts_above_call_wall')
        qqq_reshort = gex_result.raw.get('qqq_reshort_spike', False)
        pol_cluster = gex_result.raw.get('politician_cluster', 0)
        pol_buys = gex_result.raw.get('politician_buys', 0)

        combined_add = 0
        reasons = []

        # ── Rule 1: COT extreme + GEX positive = support floor + reversal setup ──
        # Dealers suppressing vol while specs are trapped short = slow grind squeeze
        if cot_extreme and gex_positive:
            combined_add += 2
            reasons.append(
                f"COMBINED: GEX dampening ({gex_regime_str}) + COT Extreme → +2 "
                f"(support floor + reversal setup)"
            )

        # ── Rule 2: COT extreme + GEX negative = maximum squeeze velocity ──
        # Negative gamma AMPLIFIES moves — when shorts cover, dealers must also buy
        # This is the most powerful setup: crowded shorts + vol amplifier
        elif cot_extreme and gex_strong_neg:
            combined_add += 3
            reasons.append(
                f"COMBINED: GEX NEGATIVE ({gex_regime_str}) + COT Extreme → +3 "
                f"(vol amplifier + crowded shorts = maximum squeeze velocity)"
            )

        # ── Rule 3: COT mild + above call wall = breakout confirmation ──
        elif cot_mild and axlfi_signal == 'ABOVE_CALL_WALL':
            pts_str = f" +{pts_above_call:.1f}pts" if pts_above_call else ""
            combined_add += 1
            reasons.append(
                f"COMBINED: COT shorts + SPY above call wall{pts_str} → +1 "
                f"(breakout confirmed, dealer hedging = self-reinforcing)"
            )

        # ── Rule 4: QQQ reshort spike while above call wall = squeeze fuel ──
        if qqq_reshort and axlfi_signal == 'ABOVE_CALL_WALL':
            combined_add += 1
            reasons.append(
                "COMBINED: QQQ reshort spike above call wall → +1 "
                "(institutions re-shorting into strength = forced cover fuel)"
            )

        # ── Rule 5: Politician cluster buy = directional signal ──
        if pol_cluster >= 3 and pol_buys > 0:
            combined_add += 1
            reasons.append(
                f"COMBINED: Politician cluster ({pol_cluster} buys) → +1 "
                f"(non-routine insider signal, 3-6 week horizon)"
            )

        slug = f"combined-{'convergence' if combined_add > 0 else 'neutral'}-{today_str}"

        return SignalResult(
            name="COMBINED",
            slug=slug,
            boost=combined_add,
            active=(combined_add > 0),
            timestamp=now_iso,
            source_date=today_str,
            raw={
                "combined_boost": combined_add,
                "cot_extreme": cot_extreme,
                "gex_regime": gex_regime_str,
                "axlfi_signal": axlfi_signal,
                "pts_above_call_wall": pts_above_call,
                "qqq_reshort_spike": qqq_reshort,
                "politician_cluster": pol_cluster,
            },
            reasons=reasons
        )
