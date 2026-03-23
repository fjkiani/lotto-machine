from typing import Tuple, Dict

def compute_verdict(score: int) -> Tuple[str, str, Dict[str, str]]:
    """
    Unified verdict logic for Kill Shots divergence scoring.
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

    if score > 7:
        verdict = "BOOST"
        action = "+15% confidence on all signals"
        action_plan["position"] = "1/3 LONG"
        action_plan["entry_trigger"] = "SPX clears +0.5% early AM"
        action_plan["invalidation"] = "SPY loses VWAP for >15min"
        action_plan["time_window"] = "1-3 Days"
    elif score >= 5:
        verdict = "NEUTRAL"
        action = "Signals pass through unchanged"
    elif score >= 2:
        verdict = "SOFT_VETO"
        action = "Signals pass ONLY if no narrative divergence"
        action_plan["invalidation"] = "SPX pushes > +1.0%"
    elif score >= 0:
        # score=0 means no divergence signals fired.
        # That's genuinely NEUTRAL — NOT a reason to veto everything.
        verdict = "NEUTRAL"
        action = "No confluence signals active — passthrough mode"
    else:
        # Negative score = impossible with current additive logic,
        # but guard for future directional scoring.
        verdict = "HARD_VETO"
        action = "All signals killed"

    return verdict, action, action_plan
