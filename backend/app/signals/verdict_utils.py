from typing import Tuple, Dict

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
