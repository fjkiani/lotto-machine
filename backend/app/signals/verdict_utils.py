from typing import Tuple, Dict, List, Any, Optional

def compute_verdict(score: int) -> Tuple[str, str, Dict[str, str]]:
    """
    Unified verdict logic for Kill Shots divergence scoring.

    Score calibration (5-signal system):
      COT extreme = +3, GEX positive = +1, AXLFI above = +1,
      QQQ reshort spike = +2, politician cluster = +2
      Max theoretical = ~9 pts

    Thresholds:
      >= 6 → BOOST (3+ layers aligned, high conviction)
      >= 3 → NEUTRAL (1-2 layers, passthrough)
      >= 1 → SOFT_VETO (weak signal, needs narrative confirmation)
       = 0 → NEUTRAL (no signals, passthrough)
       < 0 → HARD_VETO (bearish confluence)

    Returns:
        verdict (str): BOOST, NEUTRAL, SOFT_VETO, or HARD_VETO
        action (str): Description of the action taken
        action_plan (dict): Detailed trading plan adjustments
    """
    action_plan = {
        "position": "NEUTRAL",
        "entry_trigger": "N/A",
        "invalidation": "N/A",
        "time_window": "Intraday"
    }

    if score >= 6:
        verdict = "BOOST"
        action = "+15% confidence on all signals — high conviction confluence"
        action_plan["position"] = "1/3 LONG"
        action_plan["entry_trigger"] = "SPY holds above call wall on first 30min retest"
        action_plan["invalidation"] = "SPY loses call wall for >15min on volume"
        action_plan["time_window"] = "1-3 Days"
    elif score >= 3:
        verdict = "NEUTRAL"
        action = "Signals pass through unchanged — moderate confluence"
        action_plan["position"] = "WATCH"
        action_plan["entry_trigger"] = "Catalyst confirmation"
        action_plan["invalidation"] = "SPY breaks below call wall"
        action_plan["time_window"] = "Intraday"
    elif score >= 1:
        verdict = "SOFT_VETO"
        action = "Signals pass ONLY if no narrative divergence — weak confluence"
        action_plan["position"] = "REDUCED"
        action_plan["entry_trigger"] = "Wait for 2nd signal to confirm"
        action_plan["invalidation"] = "SPX pushes > +1.0% without volume"
        action_plan["time_window"] = "Intraday"
    elif score == 0:
        # No divergence signals fired — genuinely neutral, not a veto
        verdict = "NEUTRAL"
        action = "No confluence signals active — passthrough mode"
        action_plan["position"] = "FLAT"
        action_plan["entry_trigger"] = "Wait for signal activation"
        action_plan["invalidation"] = "N/A"
        action_plan["time_window"] = "N/A"
    else:
        # Negative score = bearish confluence
        verdict = "HARD_VETO"
        action = "Bearish confluence — all long signals killed"
        action_plan["position"] = "SHORT or FLAT"
        action_plan["entry_trigger"] = "SPY fails call wall retest"
        action_plan["invalidation"] = "SPY reclaims call wall on volume"
        action_plan["time_window"] = "1-3 Days"

    return verdict, action, action_plan


# Severity ordering for reconciliation (higher index = stricter).
_VERDICT_RANK = {
    "BOOST": 0,
    "NEUTRAL": 1,
    "SOFT_VETO": 2,
    "HARD_VETO": 3,
    "WAR_VETO": 4,
}


def reconcile_verdicts(
    divergence_verdict: str,
    divergence_score: int,
    kill_chain: Optional[Dict[str, Any]] = None,
    layers: Optional[Dict[str, Any]] = None,
) -> Tuple[str, List[str]]:
    """
    Reconcile kill-shots divergence verdict with kill-chain + TA/macro modifiers.
    Returns the stricter verdict and human-readable reasons.
    """
    reasons: List[str] = []
    reconciled = str(divergence_verdict or "NEUTRAL").upper()
    kc = kill_chain or {}
    lay = layers or {}

    kc_verdict = str(kc.get("verdict") or "").upper()
    kc_score = kc.get("score")
    if kc_verdict and _VERDICT_RANK.get(kc_verdict, 0) > _VERDICT_RANK.get(reconciled, 0):
        reasons.append(
            f"Kill chain {kc_verdict} (score={kc_score}) overrides divergence {divergence_verdict}"
        )
        reconciled = kc_verdict

    # TA overbought downgrade: BOOST + RSI>70 → at most NEUTRAL
    rsi = lay.get("tech_rsi") or lay.get("rsi")
    if rsi is None:
        for key, val in lay.items():
            if isinstance(val, dict) and "RSI" in str(key).upper():
                rsi = val.get("value") if "value" in val else val
                break
    try:
        rsi_f = float(rsi) if rsi is not None else None
    except (TypeError, ValueError):
        rsi_f = None
    if rsi_f is not None and rsi_f > 70 and reconciled == "BOOST":
        reasons.append(f"RSI {rsi_f:.1f} overbought — downgrade BOOST → NEUTRAL")
        reconciled = "NEUTRAL"

    macro = str(lay.get("macro_regime") or kc.get("macro_regime") or "").upper()
    if macro and "INFLATION" in macro and reconciled == "BOOST":
        reasons.append(f"Macro regime {macro} — downgrade BOOST → NEUTRAL")
        reconciled = "NEUTRAL"

    if kc.get("confluence") in ("WAITING", "SINGLE") and reconciled == "BOOST":
        reasons.append(f"Kill chain confluence {kc.get('confluence')} — downgrade BOOST → NEUTRAL")
        reconciled = "NEUTRAL"

    # Divergence score sanity: very high score with veto-class KC stays veto
    if kc_verdict in ("WAR_VETO", "HARD_VETO") and divergence_score >= 6:
        reasons.append(
            f"Divergence score {divergence_score} ignored under active {kc_verdict}"
        )
        reconciled = kc_verdict

    return reconciled, reasons
