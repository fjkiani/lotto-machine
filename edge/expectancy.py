"""
edge/expectancy.py — expectancy, bootstrap CI, and out-of-sample splitting.

Expectancy per trade = mean(net label). A signal has a *provisional* edge only if
the lower bound of the bootstrap CI on expectancy is > 0 out-of-sample with N>=30.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd

MIN_TRADES = 30  # proof bar: N >= 30 out-of-sample


@dataclass
class ExpectancyResult:
    n: int
    expectancy: float            # mean net label (%)
    win_rate: float              # fraction tradeable==1
    ci_lo: float                 # bootstrap CI lower bound on expectancy
    ci_hi: float
    passes: bool                 # n>=MIN_TRADES and ci_lo>0
    avg_win: float
    avg_loss: float
    profit_factor: float         # gross wins / gross losses


def bootstrap_ci(x: np.ndarray, n_boot: int = 5000, alpha: float = 0.05, seed: int = 0) -> tuple:
    """Percentile bootstrap CI on the mean."""
    rng = np.random.default_rng(seed)
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return (np.nan, np.nan)
    boots = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(axis=1)
    lo = np.percentile(boots, 100 * alpha / 2)
    hi = np.percentile(boots, 100 * (1 - alpha / 2))
    return (float(lo), float(hi))


def expectancy(labels: pd.DataFrame, n_boot: int = 5000, seed: int = 0) -> ExpectancyResult:
    """Compute expectancy stats from a label DataFrame (must have 'label' and 'tradeable')."""
    net = labels["label"].to_numpy(dtype=float)
    n = len(net)
    if n == 0:
        return ExpectancyResult(0, np.nan, np.nan, np.nan, np.nan, False, np.nan, np.nan, np.nan)
    exp = float(net.mean())
    wr = float((labels["tradeable"] == 1).mean())
    lo, hi = bootstrap_ci(net, n_boot=n_boot, seed=seed)
    wins = net[net > 0]
    losses = net[net < 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    pf = (gross_win / gross_loss) if gross_loss > 0 else np.inf
    passes = (n >= MIN_TRADES) and (lo > 0)
    return ExpectancyResult(n, exp, wr, lo, hi, passes, avg_win, avg_loss, pf)


def oos_split(interactions: pd.DataFrame, train_end: str = "2025-12-15") -> tuple:
    """
    Chronological train/test split. Because 372/377 interactions cluster in
    December 2025, we split within December: train <= train_end, test after.
    Returns (train_df, test_df).
    """
    df = interactions.copy()
    df["_ts"] = pd.to_datetime(df["timestamp"], format="mixed")
    cut = pd.Timestamp(train_end)
    if df["_ts"].dt.tz is not None:
        cut = cut.tz_localize(df["_ts"].dt.tz)
    train = df[df["_ts"] <= cut].drop(columns=["_ts"])
    test = df[df["_ts"] > cut].drop(columns=["_ts"])
    return train, test
