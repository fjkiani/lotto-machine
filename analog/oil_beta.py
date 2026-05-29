"""
Calibrated oil betas for EPS-style sector adjustments — sourced from
`ground_truth/oil_beta_verified.json` (Mission 2 / Alpha).

Only symbols with use_in_eps_model=true and no error block are returned.
Benchmark rows (USO, SPY) are excluded by that flag.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VERIFIED_PATH = REPO_ROOT / "ground_truth" / "oil_beta_verified.json"


@lru_cache(maxsize=1)
def _cached_payload(path_str: str) -> dict[str, Any]:
    p = Path(path_str)
    if not p.is_file():
        return {}
    return json.loads(p.read_text())


def load_oil_beta_verified(path: Path | None = None) -> dict[str, Any]:
    """Full JSON payload from disk (cached by path)."""
    p = path or DEFAULT_VERIFIED_PATH
    return dict(_cached_payload(str(p.resolve())))


def get_eps_model_oil_betas(path: Path | None = None) -> dict[str, Any]:
    """
    Sector ETF oil betas approved for EPS model (p <= 0.05, gics_sector role).
    Returns: window, wti_source, sectors: {ticker: {oil_beta, p_value, label, ...}}.
    """
    data = load_oil_beta_verified(path)
    raw = data.get("sectors") or {}
    sectors: dict[str, Any] = {}
    for sym, block in raw.items():
        if not isinstance(block, dict) or block.get("error"):
            continue
        if not block.get("use_in_eps_model"):
            continue
        if block.get("role") != "gics_sector":
            continue
        sectors[sym] = {
            "oil_beta": block.get("oil_beta"),
            "p_value": block.get("p_value"),
            "r_squared": block.get("r_squared"),
            "label": block.get("label"),
            "n_obs": block.get("n_obs"),
            "price_source": block.get("price_source"),
        }
    return {
        "source_file": str((path or DEFAULT_VERIFIED_PATH).resolve()),
        "window": data.get("window"),
        "wti_source": data.get("wti_source"),
        "wti_note": data.get("wti_note"),
        "sectors": sectors,
    }


def invalidate_cache() -> None:
    _cached_payload.cache_clear()
