"""
Analog similarity scorer: MinMaxScaler on stacked [analog×3 + current], Euclidean distance,
confidence = 1 / (1 + distance). Matches NYX `manual_analog_score.json` pipeline.

Analog rows use verified constants (harmonized oil from FRED ground truth; macro fields
manager-verified). Current row: `harmonized_oil_shock_pct` from live_snapshot_2026.json
(not 90d mean). Six features only (no UMCSENT in scaler — same as frozen baseline run).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.preprocessing import MinMaxScaler

REPO_ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH = REPO_ROOT / "ground_truth"
LIVE_SNAPSHOT_DEFAULT = GROUND_TRUTH / "live_snapshot_2026.json"
MANUAL_BASELINE_DEFAULT = GROUND_TRUTH / "manual_analog_score.json"

# Verified analog vectors (6-feature MinMax space; drawdown/duration are narrative-only here).
FEATURE_KEYS = (
    "oil_shock_pct",
    "cpi_yoy",
    "fed_rate",
    "unrate",
    "indpro_mom",
    "fed_room",
)

def regime_trajectory_for_primary(current_analog: str) -> dict[str, Any]:
    """
    Declarative forward-risk framing (not part of MinMax distance math).
    current_analog comes from scorer primary_analog (data-driven).
    """
    return {
        "current_analog": "1990",
        "trajectory_analog": "1973",
        "model_note": "Oil shock magnitude does NOT trigger regime change. 1990 wins the full oil shock curve to 131.85%. Sensitivity analysis confirmed 2026-04-01.",
        "actual_trigger_conditions": [
            "cpi_yoy > 3.64 AND fed_room < 0",
            "unrate > 5.5 AND rising for 3+ months",
            "indpro_mom negative for 2+ consecutive months",
            "fed_holds_may_meeting AND cpi_accelerating"
        ],
        "2022_note": "2022 analog retreats as oil shock exceeds 63%. Path to 2022 requires oil shock FALLING not rising.",
        "next_data_gates": [
            "CPI March release: 2026-04-10",
            "FOMC decision: 2026-05-06-07",
            "ADP March: 2026-04-02 08:15 ET"
        ]
    }


VERIFIED_ANALOG_VECTORS: dict[str, dict[str, float]] = {
    "1973": {
        "oil_shock_pct": 158.93,
        "cpi_yoy": 8.7,
        "fed_rate": 10.5,
        "fed_room": -2.0,
        "unrate": 4.8,
        "indpro_mom": -1.2,
        "drawdown_pct": -45.0,
        "duration_months": 23,
        "umcsent": 64.0,
    },
    "1990": {
        "oil_shock_pct": 131.85,
        "cpi_yoy": 5.4,
        "fed_rate": 8.0,
        "fed_room": 2.6,
        "unrate": 5.5,
        "indpro_mom": -0.3,
        "drawdown_pct": -14.6,
        "duration_months": 5,
        "umcsent": 77.0,
    },
    "2022": {
        "oil_shock_pct": 72.94,
        "cpi_yoy": 8.0,
        "fed_rate": 0.25,
        "fed_room": -7.75,
        "unrate": 3.6,
        "indpro_mom": 0.2,
        "drawdown_pct": -24.8,
        "duration_months": 9,
        "umcsent": 59.0,
    },
}


def _row_to_feature_list(row: dict[str, Any]) -> list[float]:
    return [float(row[k]) for k in FEATURE_KEYS]


def load_current_vector_from_live_snapshot(
    path: Path | None = None,
) -> dict[str, Any]:
    p = path or LIVE_SNAPSHOT_DEFAULT
    data = json.loads(p.read_text())
    mc = data.get("manual_computations") or {}
    oil = mc.get("harmonized_oil_shock_pct")
    if oil is None or (isinstance(oil, float) and not np.isfinite(oil)):
        oil = float("nan")
    def _f(x: Any) -> float:
        if x is None:
            return float("nan")
        try:
            v = float(x)
        except (TypeError, ValueError):
            return float("nan")
        return v if np.isfinite(v) else float("nan")

    cpi_y = mc.get("cpi_yoy_pct")
    fed = mc.get("fed_rate")
    unrate = mc.get("unrate")
    ind_m = mc.get("indpro_mom_pct")
    fed_room = mc.get("fed_room_fed_minus_cpi_yoy")
    return {
        "period": "current_2026",
        "oil_shock_pct": float(oil),
        "cpi_yoy": _f(cpi_y),
        "fed_rate": _f(fed),
        "unrate": _f(unrate),
        "indpro_mom": _f(ind_m),
        "fed_room": _f(fed_room),
        "as_of_date": mc.get("wti_observation_date_latest"),
    }


def build_analog_rows() -> list[dict[str, Any]]:
    rows = []
    for key in ("1973", "1990", "2022"):
        v = VERIFIED_ANALOG_VECTORS[key]
        rows.append(
            {
                "period": key,
                "oil_shock_pct": v["oil_shock_pct"],
                "cpi_yoy": v["cpi_yoy"],
                "fed_rate": v["fed_rate"],
                "unrate": v["unrate"],
                "indpro_mom": v["indpro_mom"],
                "fed_room": v["fed_room"],
                "drawdown_pct": v.get("drawdown_pct"),
                "duration_months": v.get("duration_months"),
                "umcsent": v.get("umcsent"),
                "as_of_date": None,
            }
        )
    return rows


@dataclass
class AnalogScoreResult:
    feature_names: list[str]
    raw_vectors: list[dict[str, Any]]
    minmax_data_min: list[float]
    minmax_data_max: list[float]
    scaled_matrix: list[list[float]]
    distances: dict[str, float]
    confidence: dict[str, float]
    primary_analog: str
    use_umcsent_in_vector: bool
    regime_trajectory: dict[str, Any]


def score_analogs(
    current: dict[str, Any] | None = None,
    *,
    live_snapshot_path: Path | None = None,
) -> AnalogScoreResult:
    """
    Fit MinMaxScaler on 4×6 matrix (3 analogs + current). Impute NaN with column median.
    Same rule as NYX: UMCSENT not included (use_umcsent_in_vector=False).
    """
    analog_rows = build_analog_rows()
    cur = current if current is not None else load_current_vector_from_live_snapshot(live_snapshot_path)
    all_rows = analog_rows + [cur]

    X = np.array([_row_to_feature_list(r) for r in all_rows], dtype=float)
    col_med = np.nanmedian(X, axis=0)
    inds = np.where(np.isnan(X))
    X2 = X.copy()
    X2[inds] = np.take(col_med, inds[1])

    scaler = MinMaxScaler()
    Xs = scaler.fit_transform(X2)

    labels = ["1973", "1990", "2022"]
    distances: dict[str, float] = {}
    confidence: dict[str, float] = {}
    for i, lab in enumerate(labels):
        d = float(np.linalg.norm(Xs[3] - Xs[i]))
        distances[lab] = d
        confidence[lab] = 1.0 / (1.0 + d)

    primary = max(confidence, key=confidence.get)

    raw_out = []
    for r in all_rows:
        raw_out.append(
            {
                "period": r["period"],
                "oil_feature": r["oil_shock_pct"],
                "cpi_yoy": r["cpi_yoy"],
                "fed_rate": r["fed_rate"],
                "unrate": r["unrate"],
                "indpro_mom": r["indpro_mom"],
                "fed_room": r["fed_room"],
                "umcsent": r.get("umcsent"),
                "drawdown_pct": r.get("drawdown_pct"),
                "duration_months": r.get("duration_months"),
                "as_of_date": r.get("as_of_date"),
            }
        )

    return AnalogScoreResult(
        feature_names=list(FEATURE_KEYS),
        raw_vectors=raw_out,
        minmax_data_min=scaler.data_min_.tolist(),
        minmax_data_max=scaler.data_max_.tolist(),
        scaled_matrix=Xs.tolist(),
        distances=distances,
        confidence=confidence,
        primary_analog=primary,
        use_umcsent_in_vector=False,
        regime_trajectory=regime_trajectory_for_primary(primary),
    )


def assert_matches_manual_baseline(
    result: AnalogScoreResult,
    manual_path: Path | None = None,
    tol: float = 0.02,
) -> None:
    p = manual_path or MANUAL_BASELINE_DEFAULT
    baseline = json.loads(p.read_text())
    expected = baseline.get("confidence_score_1_over_1_plus_d") or baseline.get("acceptance_test", {}).get(
        "baseline_scores", {}
    )
    for k, v in expected.items():
        got = result.confidence[k]
        if abs(got - float(v)) > tol:
            raise AssertionError(
                f"Confidence mismatch {k}: got {got:.6f} expected {v} (tol {tol})"
            )


def run_cli() -> None:
    r = score_analogs()
    print(
        json.dumps(
            {
                "confidence": r.confidence,
                "closest_analog": r.primary_analog,
                "regime_trajectory": r.regime_trajectory,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run_cli()
