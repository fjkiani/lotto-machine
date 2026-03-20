from datetime import datetime
from .signal_schema import SignalResult

class CombinedScorer:
    def evaluate(self, gex_result: SignalResult, cot_result: SignalResult) -> SignalResult:
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        cot_extreme = cot_result.boost >= 3
        gex_regime_str = gex_result.raw.get('gex_regime', '')
        gex_strong_neg = 'STRONG_NEGATIVE' in gex_regime_str
        
        combined_add = 0
        reasons = []
        
        if cot_extreme and not gex_strong_neg and 'POSITIVE' in gex_regime_str:
            combined_add = 2
            reasons.append(f"COMBINED: GEX dampening ({gex_regime_str}) + COT Extreme → +2 (support floor + reversal setup)")
            
        slug = f"combined-{'convergence' if combined_add > 0 else 'neutral'}-{today_str}"
        
        return SignalResult(
            name="COMBINED",
            slug=slug,
            boost=combined_add,
            active=(combined_add > 0),
            timestamp=now_iso,
            source_date=today_str,
            raw={"combined_boost": combined_add},
            reasons=reasons
        )
