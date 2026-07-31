"""
edge/benchmark.py — baselines and risk-adjusted metrics.

Two baselines every signal must beat:
  1. buy-and-hold SPY over the same window
  2. random-entry: N random entries with the same horizon/cost, same window

Metrics: total return, Sharpe (annualized), Sortino, max drawdown, expectancy.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class BenchmarkResult:
    name: str
    n: int
    total_return_pct: float
    expectancy_pct: float
    sharpe: float
    sortino: float
    max_drawdown_pct: float
    win_rate: float


def _sharpe(returns: np.ndarray, periods_per_year: float) -> float:
    r = np.asarray(returns, dtype=float)
    if len(r) < 2 or r.std() == 0:
        return 0.0
    return float(r.mean() / r.std() * np.sqrt(periods_per_year))


def _sortino(returns: np.ndarray, periods_per_year: float) -> float:
    r = np.asarray(returns, dtype=float)
    downside = r[r < 0]
    if len(r) < 2 or len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float(r.mean() / downside.std() * np.sqrt(periods_per_year))


def _max_dd(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return float(dd.min() * 100)


def equity_curve(net_labels_pct: np.ndarray, start: float = 1.0) -> np.ndarray:
    """Compound per-trade net % returns into an equity curve."""
    eq = [start]
    for r in net_labels_pct:
        eq.append(eq[-1] * (1 + r / 100.0))
    return np.array(eq)


def signal_benchmark(net_labels_pct: np.ndarray, periods_per_year: float, name: str = "signal") -> BenchmarkResult:
    r = np.asarray(net_labels_pct, dtype=float)
    n = len(r)
    eq = equity_curve(r)
    total = float((eq[-1] - 1) * 100) if n else 0.0
    exp = float(r.mean()) if n else 0.0
    wr = float((r > 0).mean()) if n else 0.0
    return BenchmarkResult(
        name=name, n=n, total_return_pct=total, expectancy_pct=exp,
        sharpe=_sharpe(r, periods_per_year), sortino=_sortino(r, periods_per_year),
        max_drawdown_pct=_max_dd(eq), win_rate=wr,
    )


def buy_hold_benchmark(bars: pd.DataFrame, start_ts, end_ts, name: str = "buy_hold") -> BenchmarkResult:
    """Buy-and-hold over [start_ts, end_ts] using close prices."""
    df = bars[(bars["datetime"] >= start_ts) & (bars["datetime"] <= end_ts)]
    if len(df) < 2:
        return BenchmarkResult(name, 0, 0, 0, 0, 0, 0, 0)
    close = df["close"].to_numpy(dtype=float)
    rets = np.diff(close) / close[:-1] * 100
    eq = close / close[0]
    total = float((close[-1] / close[0] - 1) * 100)
    # annualization: infer bars/year from median spacing
    dt = np.median(np.diff(df["datetime"].astype("int64").to_numpy())) / 1e9  # seconds
    ppy = (365.25 * 24 * 3600) / dt if dt > 0 else 252
    return BenchmarkResult(
        name=name, n=len(rets), total_return_pct=total, expectancy_pct=float(rets.mean()),
        sharpe=_sharpe(rets, ppy), sortino=_sortino(rets, ppy),
        max_drawdown_pct=_max_dd(eq), win_rate=float((rets > 0).mean()),
    )


def random_entry_benchmark(
    bars: pd.DataFrame, n_trades: int, horizon_bars: int, cost_pct: float,
    direction: int, seed: int = 0, name: str = "random",
) -> BenchmarkResult:
    """
    N random entries, held horizon_bars, in `direction` (+1 long/-1 short), net of cost.
    Matches the signal's trade count and horizon so the comparison is fair.
    """
    rng = np.random.default_rng(seed)
    close = bars["close"].to_numpy(dtype=float)
    max_start = len(close) - horizon_bars - 1
    if max_start <= 1:
        return BenchmarkResult(name, 0, 0, 0, 0, 0, 0, 0)
    starts = rng.integers(0, max_start, size=n_trades)
    nets = []
    for s in starts:
        entry = close[s]
        exitp = close[s + horizon_bars]
        gross = ((exitp - entry) / entry * 100) * direction
        nets.append(gross - cost_pct)
    nets = np.array(nets)
    dt = np.median(np.diff(bars["datetime"].astype("int64").to_numpy())) / 1e9
    bars_per_year = (365.25 * 24 * 3600) / dt if dt > 0 else 252
    trades_per_year = bars_per_year / horizon_bars
    res = signal_benchmark(nets, periods_per_year=trades_per_year, name=name)
    return res
