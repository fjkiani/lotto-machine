"""
edge/labels.py — Clean label builder from raw OHLC.

Single source of truth for "did the trade win." Replaces the unreliable
out-of-band backfill columns (direction_correct / tradeable_1h / real_move_pct_1h)
which the live code never writes and which match no clean definition.

Convention
----------
A DP interaction has a level (support/resistance) and an *expected* trade direction:
  - SUPPORT   -> expected LONG  (fade the approach; price bounces UP off support)
  - RESISTANCE-> expected SHORT (fade the approach; price bounces DOWN off resistance)

This is the standard "fade the dark-pool level" hypothesis the system was built on.
We label the FORWARD price path from the interaction timestamp and measure whether
the expected-direction trade would have made money after costs.

All labels are computed from raw OHLC only. No reliance on artifact columns.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import pandas as pd
import numpy as np

# Expected trade direction by level type (fade-the-level hypothesis)
EXPECTED_DIR = {"SUPPORT": +1, "RESISTANCE": -1}  # +1 long, -1 short


@dataclass
class ForwardLabel:
    """Clean forward-path label for one interaction at one horizon."""
    interaction_id: int
    horizon_bars: int                 # number of OHLC bars forward
    horizon_name: str
    entry_price: float                # price at interaction (first bar close at/after ts)
    expected_dir: int                 # +1 long, -1 short
    fwd_return_pct: float             # signed close-to-close return in expected dir, %
    mfe_pct: float                    # max favorable excursion in expected dir, %
    mae_pct: float                    # max adverse excursion against expected dir, %
    hit_target: bool                  # did MFE reach target before MAE hit stop
    label: float                      # signed net return used for expectancy (after costs)
    tradeable: int                    # 1 if net label > 0 else 0
    n_bars_available: int             # bars actually present (may be < horizon at series end)


def _expected_direction(level_type: str) -> int:
    lt = (level_type or "").upper()
    if lt not in EXPECTED_DIR:
        raise ValueError(f"unknown level_type: {level_type}")
    return EXPECTED_DIR[lt]


def _entry_index(bars: pd.DataFrame, ts: pd.Timestamp) -> Optional[int]:
    """Index of first bar at/after ts. None if ts is past the end."""
    idx = bars["datetime"].searchsorted(ts)
    if idx >= len(bars):
        return None
    return int(idx)


def label_interaction(
    interaction_id: int,
    ts: pd.Timestamp,
    level_type: str,
    bars: pd.DataFrame,
    horizon_bars: int,
    horizon_name: str,
    target_pct: float,
    stop_pct: float,
    cost_pct: float,
) -> Optional[ForwardLabel]:
    """
    Compute the clean forward label for one interaction.

    bars: DataFrame with columns [datetime, open, high, low, close, volume], sorted, tz-aware.
    target_pct/stop_pct: in percent (e.g. 0.5 = 0.5%). cost_pct: round-trip cost in %.
    """
    direction = _expected_direction(level_type)
    i0 = _entry_index(bars, ts)
    if i0 is None:
        return None
    entry = float(bars["close"].iloc[i0])
    if entry <= 0:
        return None

    fwd = bars.iloc[i0 + 1: i0 + 1 + horizon_bars]
    n_avail = len(fwd)
    if n_avail == 0:
        return None

    # Signed path in expected direction (as fraction of entry)
    if direction == +1:  # long
        path = (fwd["close"].values - entry) / entry
        fav = (fwd["high"].values - entry) / entry      # favorable = up
        adv = (fwd["low"].values - entry) / entry       # adverse = down
    else:                # short
        path = (entry - fwd["close"].values) / entry
        fav = (entry - fwd["low"].values) / entry       # favorable = down
        adv = (entry - fwd["high"].values) / entry      # adverse = up

    fwd_return_pct = float(path[-1] * 100)
    mfe_pct = float(fav.max() * 100)
    mae_pct = float(-adv.min() * 100)  # positive magnitude of worst adverse move

    # Target-before-stop: walk the path bar by bar using high/low
    hit_target = False
    stopped = False
    for k in range(n_avail):
        if fav[k] * 100 >= target_pct:
            hit_target = True
            break
        if (-adv[k]) * 100 >= stop_pct:  # adverse excursion reached stop
            stopped = True
            break

    # Net label: if target hit first -> +target; if stopped first -> -stop; else close return
    if hit_target:
        gross = target_pct
    elif stopped:
        gross = -stop_pct
    else:
        gross = fwd_return_pct
    net = gross - cost_pct
    tradeable = 1 if net > 0 else 0

    return ForwardLabel(
        interaction_id=interaction_id,
        horizon_bars=horizon_bars,
        horizon_name=horizon_name,
        entry_price=entry,
        expected_dir=direction,
        fwd_return_pct=fwd_return_pct,
        mfe_pct=mfe_pct,
        mae_pct=mae_pct,
        hit_target=hit_target,
        label=net,
        tradeable=tradeable,
        n_bars_available=n_avail,
    )


def label_many(
    interactions: pd.DataFrame,
    bars_by_symbol: Dict[str, pd.DataFrame],
    horizons: List[tuple],  # [(horizon_bars, name), ...]
    target_pct: float,
    stop_pct: float,
    cost_pct: float,
) -> pd.DataFrame:
    """
    Label a set of interactions across horizons.

    interactions: DataFrame with columns [id, timestamp, symbol, level_type].
    Returns long-format DataFrame of ForwardLabel rows (one per interaction x horizon).
    """
    rows = []
    for _, r in interactions.iterrows():
        sym = r["symbol"]
        bars = bars_by_symbol.get(sym)
        if bars is None:
            continue
        ts = pd.to_datetime(r["timestamp"], format="mixed")
        bar_tz = bars["datetime"].dt.tz
        # align tz: if bars are tz-aware and ts is naive, localize; then match unit
        if ts.tzinfo is None and bar_tz is not None:
            ts = ts.tz_localize(bar_tz)
        elif ts.tzinfo is not None and bar_tz is not None:
            ts = ts.tz_convert(bar_tz)
        # match datetime64 unit of the bars column to avoid lossless-convert error
        ts = ts.as_unit(bars["datetime"].dtype.unit if hasattr(bars["datetime"].dtype, "unit") else "ns")
        for hb, name in horizons:
            lab = label_interaction(
                interaction_id=int(r["id"]),
                ts=ts,
                level_type=r["level_type"],
                bars=bars,
                horizon_bars=hb,
                horizon_name=name,
                target_pct=target_pct,
                stop_pct=stop_pct,
                cost_pct=cost_pct,
            )
            if lab is not None:
                rows.append(vars(lab))
    return pd.DataFrame(rows)
