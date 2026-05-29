"""Shared helpers for ground_truth missions (oil harmonization, etc.)."""
from __future__ import annotations

import pandas as pd


def harmonized_oil_shock_monthly(
    wti_monthly: pd.Series,
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
) -> dict:
    """
    Single oil-shock definition for analog + live scoring:
    peak = max WTI in [period_start, period_end] (monthly series, month-end index).
    baseline = min WTI over the 12 calendar months strictly before the peak month
    (intersection with available history). Shock % = (peak - baseline) / baseline * 100.

    Not comparable to 'first month of window vs peak' or 'vs 90d mean'.
    """
    s = wti_monthly.dropna().sort_index()
    mask = (s.index >= period_start.normalize()) & (s.index <= period_end.normalize())
    w = s.loc[mask]
    if w.empty:
        return {
            "oil_baseline_12m_before_peak": None,
            "oil_price_at_peak": None,
            "oil_peak_date": None,
            "confirmed_oil_shock_pct": None,
        }
    peak_val = float(w.max())
    peak_idx = w[w == peak_val].index.min()
    prior = s[s.index < peak_idx]
    if prior.empty:
        baseline = float(w.iloc[0])
        baseline_note = "no_prior_months_used_first_in_window"
    else:
        win_start = peak_idx - pd.DateOffset(months=12)
        prior12 = prior[prior.index >= win_start]
        if len(prior12):
            baseline = float(prior12.min())
            baseline_note = "min_12m_before_peak_month"
        else:
            baseline = float(prior.min())
            baseline_note = "min_all_prior_months"
    shock = None if baseline == 0 else (peak_val - baseline) / baseline * 100.0
    return {
        "oil_baseline_12m_before_peak": baseline,
        "oil_price_at_peak": peak_val,
        "oil_peak_date": str(peak_idx.date()),
        "confirmed_oil_shock_pct": None if shock is None else round(shock, 4),
        "oil_shock_method": "harmonized_12m_pre_peak_min_to_window_peak",
        "oil_baseline_rule": baseline_note,
    }
