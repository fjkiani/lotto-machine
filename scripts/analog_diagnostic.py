#!/usr/bin/env python3
"""
Diagnostic: MinMax-normalized rows + per-feature squared gaps vs current_2026.
Does not change the scorer model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from analog.analog_scorer import (  # noqa: E402
    FEATURE_KEYS,
    LIVE_SNAPSHOT_DEFAULT,
    build_analog_rows,
    load_current_vector_from_live_snapshot,
    _row_to_feature_list,
)

try:
    from sklearn.preprocessing import MinMaxScaler
except ImportError:
    print("ERROR: pip install scikit-learn", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    analog_rows = build_analog_rows()
    cur = load_current_vector_from_live_snapshot()
    all_rows = analog_rows + [cur]

    X = np.array([_row_to_feature_list(r) for r in all_rows], dtype=float)
    col_med = np.nanmedian(X, axis=0)
    nan_mask = np.isnan(X)
    X_imp = X.copy()
    X_imp[nan_mask] = np.take(col_med, np.where(nan_mask)[1])

    scaler = MinMaxScaler()
    Xs = scaler.fit_transform(X_imp)

    labels = ["1973", "1990", "2022", "current_2026"]
    mc_path = LIVE_SNAPSHOT_DEFAULT
    snap = json.loads(mc_path.read_text())
    mc = snap.get("manual_computations") or {}

    print("## Why 2022 won (before looking at tables)")
    print(
        "- Confidence = 1/(1 + Euclidean distance in **MinMax-scaled 6-D space**).\n"
        "- The **winner is whichever analog has the smallest distance** to `current_2026`.\n"
        "- If `cpi_yoy` / `fed_room` are **NaN** for current, they are **filled with the column median "
        "across all 4 rows** (including current’s NaNs). That **changes** the implied current macro "
        "vector and can **shift** which analog is closest.\n"
    )

    print("### Loaded from live_snapshot (raw, pre-imputation)")
    print(f"| Field | Value |")
    print(f"|-------|-------|")
    ho = mc.get("harmonized_oil_shock_pct")
    print(f"| harmonized_oil_shock_pct | {ho} |")
    print(f"| cpi_yoy_pct | {mc.get('cpi_yoy_pct')} |")
    print(f"| fed_rate | {mc.get('fed_rate')} |")
    print(f"| fed_room_fed_minus_cpi_yoy | {mc.get('fed_room_fed_minus_cpi_yoy')} |")
    print(f"| indpro_mom_pct | {mc.get('indpro_mom_pct')} |")
    print(f"| unrate | {mc.get('unrate')} |")
    print()

    print("### Column medians used for NaN imputation (axis=0 over 4×6 matrix)")
    print(f"| Feature | median |")
    print(f"|---------|--------|")
    for j, name in enumerate(FEATURE_KEYS):
        print(f"| {name} | {col_med[j]} |")
    print()

    print("### Raw 4×6 matrix (before imputation) — NaN as shown")
    print(f"| row | " + " | ".join(FEATURE_KEYS) + " |")
    print("|" + "---|" * (len(FEATURE_KEYS) + 1))
    for i, lab in enumerate(labels):
        vals = [X[i, j] for j in range(len(FEATURE_KEYS))]
        cells = [lab] + [f"{v}" if np.isfinite(v) else "NaN" for v in vals]
        print("| " + " | ".join(cells) + " |")
    print()

    print("### After imputation (fed into MinMaxScaler)")
    print(f"| row | " + " | ".join(FEATURE_KEYS) + " |")
    print("|" + "---|" * (len(FEATURE_KEYS) + 1))
    for i, lab in enumerate(labels):
        vals = [X_imp[i, j] for j in range(len(FEATURE_KEYS))]
        cells = [lab] + [f"{v:.6g}" for v in vals]
        print("| " + " | ".join(cells) + " |")
    print()

    print("### Normalized vectors (MinMaxScaler output, same order)")
    print(f"| row | " + " | ".join(FEATURE_KEYS) + " |")
    print("|" + "---|" * (len(FEATURE_KEYS) + 1))
    for i, lab in enumerate(labels):
        vals = [Xs[i, j] for j in range(len(FEATURE_KEYS))]
        cells = [lab] + [f"{v:.6f}" for v in vals]
        print("| " + " | ".join(cells) + " |")
    print()

    cur_s = Xs[3]
    print("### Per-feature squared difference: (current_norm − analog_norm)²")
    for i_an, an in enumerate(["1973", "1990", "2022"]):
        dvec = cur_s - Xs[i_an]
        sq = dvec**2
        print(f"\n**{an} vs current_2026**  (sum of below = ||Δ||² = {float(np.dot(dvec, dvec)):.6f})")
        print(f"| feature | diff_sq |")
        print(f"|---------|--------|")
        for j, name in enumerate(FEATURE_KEYS):
            print(f"| {name} | {sq[j]:.6f} |")

    print("\n### Euclidean distances → confidence")
    for i_an, an in enumerate(["1973", "1990", "2022"]):
        d = float(np.linalg.norm(cur_s - Xs[i_an]))
        print(f"- {an}: d={d:.6f}  confidence=1/(1+d)={1.0/(1.0+d):.6f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
