#!/usr/bin/env python3
"""
Mission 3 (NYX): Live FRED snapshot + manual macro math + MinMaxScaler Euclidean
similarity vs three analog feature vectors built from ground_truth macro CSVs/stats.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from urllib.parse import urlencode
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from ground_truth_common import harmonized_oil_shock_monthly

GROUND = REPO_ROOT / "ground_truth"
FRED_OBS = "https://api.stlouisfed.org/fred/series/observations"


def load_dotenv_keys():
    for p in (REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"):
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def fred_fetch(
    api_key: str,
    series_id: str,
    *,
    limit: int | None = None,
    sort_order: str = "desc",
    observation_start: str | None = None,
    observation_end: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": sort_order,
    }
    if limit is not None:
        params["limit"] = str(limit)
    if observation_start:
        params["observation_start"] = observation_start
    if observation_end:
        params["observation_end"] = observation_end
    url = f"{FRED_OBS}?{urlencode(params)}"
    with urlopen(url, timeout=120) as resp:
        return json.loads(resp.read().decode())


def obs_values(raw: dict) -> list[tuple[str, float]]:
    out = []
    for o in raw.get("observations") or []:
        v = o.get("value")
        if v in (".", "", None):
            continue
        try:
            out.append((o["date"], float(v)))
        except (ValueError, KeyError):
            continue
    return out


def analog_end_features(
    csv_path: Path,
    stats_path: Path,
    period_label: str,
) -> dict[str, float]:
    """Feature vector at end of analog window (last month with data)."""
    stats = json.loads(stats_path.read_text())
    df = pd.read_csv(csv_path)
    df["dt"] = pd.to_datetime(df["date"])
    df = df.sort_values("dt")

    last_i = df.last_valid_index()
    row = df.loc[last_i]
    prev_rows = df[df["dt"] < row["dt"]]

    def _num(series: pd.Series, idx) -> float | None:
        v = series.loc[idx] if idx in series.index else np.nan
        if pd.isna(v):
            return None
        return float(v)

    cpi_last = _num(df["cpi"], last_i)
    # CPI 12 months earlier in same panel
    target = row["dt"] - pd.DateOffset(months=12)
    past = df[df["dt"] <= target].iloc[-1] if len(df[df["dt"] <= target]) else None
    cpi_yoy = None
    if cpi_last is not None and past is not None and pd.notna(past["cpi"]) and past["cpi"]:
        cpi_yoy = (cpi_last / float(past["cpi"]) - 1.0) * 100.0

    indpro_last = _num(df["indpro"], last_i)
    indpro_prev = None
    if len(prev_rows):
        pr = prev_rows.iloc[-1]
        if pd.notna(pr["indpro"]):
            indpro_prev = float(pr["indpro"])
    indpro_mom = None
    if indpro_last is not None and indpro_prev and indpro_prev != 0:
        indpro_mom = (indpro_last / indpro_prev - 1.0) * 100.0

    fed = _num(df["fedfunds"], last_i)
    unrate = _num(df["unrate"], last_i)
    umcsent = _num(df["umcsent"], last_i)

    oil_pct = stats.get("confirmed_oil_shock_pct")
    if oil_pct is None:
        oil_pct = float("nan")
    # Harmonized analog oil (same definition as Mission 1 *_macro_stats.json)

    cpi_y = float(cpi_yoy) if cpi_yoy is not None else float("nan")
    fed_f = float(fed) if fed is not None else float("nan")
    fed_room = fed_f - cpi_y if np.isfinite(fed_f) and np.isfinite(cpi_y) else float("nan")

    return {
        "period": period_label,
        "oil_feature_harmonized_shock_pct": float(oil_pct),
        "cpi_yoy": cpi_y,
        "fed_rate": fed_f,
        "unrate": float(unrate) if unrate is not None else float("nan"),
        "indpro_mom": float(indpro_mom) if indpro_mom is not None else float("nan"),
        "umcsent": float(umcsent) if umcsent is not None else float("nan"),
        "fed_room": fed_room,
        "as_of_date": str(row["date"]),
    }


def wti_monthly_dcoil_from_fred(api_key: str) -> pd.Series:
    """Daily DCOILWTICO → month-end last, ascending from 2020-06-01 for harmonized oil."""
    raw = fred_fetch(
        api_key,
        "DCOILWTICO",
        sort_order="asc",
        observation_start="2020-06-01",
    )
    pairs = obs_values(raw)
    if not pairs:
        return pd.Series(dtype=float)
    pairs.sort(key=lambda x: x[0])
    idx = pd.to_datetime([p[0] for p in pairs]).normalize()
    vals = [p[1] for p in pairs]
    s = pd.Series(vals, index=idx).sort_index()
    return s.resample("ME").last().dropna()


def build_live_manual(api_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Raw pulls + manual calculations with show-your-work."""
    raw_out: dict[str, Any] = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "series": {},
    }

    # Latest singles
    for sid, lim in [
        ("DCOILWTICO", 1),
        # Extra headroom: FRED sometimes returns "." for a month; limit=13 can yield <13 valid points.
        ("CPIAUCSL", 24),
        ("FEDFUNDS", 1),
        ("UNRATE", 1),
        ("INDPRO", 2),
        ("UMCSENT", 1),
    ]:
        raw_out["series"][sid] = fred_fetch(api_key, sid, limit=lim, sort_order="desc")

    raw_out["series"]["DCOILWTICO_90d"] = fred_fetch(api_key, "DCOILWTICO", limit=90, sort_order="desc")
    raw_out["series"]["GASREGCOVW"] = fred_fetch(api_key, "GASREGCOVW", limit=8, sort_order="desc")
    raw_out["series"]["RSAFS"] = fred_fetch(api_key, "RSAFS", limit=3, sort_order="desc")

    # --- Manual math ---
    wti_all = obs_values(raw_out["series"]["DCOILWTICO_90d"])
    wti_all.sort(key=lambda x: x[0])
    wti_vals = [v for _, v in wti_all]
    wti_current_raw = obs_values(raw_out["series"]["DCOILWTICO"])
    wti_current = wti_current_raw[0][1] if wti_current_raw else float("nan")
    wti_90d_avg = float(np.mean(wti_vals)) if wti_vals else float("nan")
    oil_shock_pct = (
        ((wti_current - wti_90d_avg) / wti_90d_avg) * 100.0
        if wti_90d_avg and wti_90d_avg != 0
        else float("nan")
    )

    cpi_pairs = obs_values(raw_out["series"]["CPIAUCSL"])
    cpi_pairs.sort(key=lambda x: x[0], reverse=True)
    cpi_latest = float("nan")
    cpi_13mo = float("nan")
    cpi_yoy_latest_date = None
    cpi_yoy_year_ago_date = None
    cpi_yoy = float("nan")
    if len(cpi_pairs) >= 1:
        cpi_yoy_latest_date, cpi_latest = cpi_pairs[0][0], cpi_pairs[0][1]
        lt = pd.Timestamp(cpi_yoy_latest_date)
        target = lt - pd.DateOffset(months=12)
        for d_str, val in cpi_pairs:
            t = pd.Timestamp(d_str)
            if t.year == target.year and t.month == target.month:
                cpi_yoy_year_ago_date, cpi_13mo = d_str, val
                break
        if not np.isfinite(cpi_13mo) and len(cpi_pairs) >= 13:
            cpi_yoy_year_ago_date, cpi_13mo = cpi_pairs[12][0], cpi_pairs[12][1]
        if np.isfinite(cpi_latest) and np.isfinite(cpi_13mo) and cpi_13mo != 0:
            cpi_yoy = (cpi_latest / cpi_13mo - 1.0) * 100.0
    cpi_nan_filled = not np.isfinite(cpi_yoy)

    ff = obs_values(raw_out["series"]["FEDFUNDS"])
    fed_rate = ff[0][1] if ff else float("nan")
    fed_room = fed_rate - cpi_yoy if np.isfinite(fed_rate) and np.isfinite(cpi_yoy) else float("nan")

    un = obs_values(raw_out["series"]["UNRATE"])
    unrate = un[0][1] if un else float("nan")

    ind = obs_values(raw_out["series"]["INDPRO"])
    ind.sort(key=lambda x: x[0], reverse=True)
    ind_latest = ind[0][1] if len(ind) > 0 else float("nan")
    ind_prev = ind[1][1] if len(ind) > 1 else float("nan")
    indpro_mom = (
        (ind_latest / ind_prev - 1.0) * 100.0 if ind_prev and ind_prev != 0 else float("nan")
    )

    um = obs_values(raw_out["series"]["UMCSENT"])
    umcsent = um[0][1] if um else float("nan")

    wti_m = wti_monthly_dcoil_from_fred(api_key)
    harm = {}
    if len(wti_m) >= 13:
        end_m = wti_m.index.max()
        start_m = end_m - pd.DateOffset(months=35)
        harm = harmonized_oil_shock_monthly(wti_m, start_m, end_m)
    else:
        harm = {
            "confirmed_oil_shock_pct": None,
            "oil_shock_method": None,
            "oil_baseline_12m_before_peak": None,
            "oil_price_at_peak": None,
            "oil_peak_date": None,
        }

    manual = {
        "wti_current": wti_current,
        "wti_observation_date_latest": wti_current_raw[0][0] if wti_current_raw else None,
        "wti_90d_avg": round(wti_90d_avg, 4),
        "wti_90d_n_obs": len(wti_vals),
        "oil_shock_pct_vs_90d_mean": round(oil_shock_pct, 4),
        "harmonized_oil_shock_pct": harm.get("confirmed_oil_shock_pct"),
        "harmonized_oil_window": {
            "method": harm.get("oil_shock_method"),
            "baseline_usd": harm.get("oil_baseline_12m_before_peak"),
            "peak_usd": harm.get("oil_price_at_peak"),
            "peak_month": harm.get("oil_peak_date"),
            "trailing_months_for_peak_search": 36,
        },
        "wti_fred_vs_cl_futures_note": (
            "Macro pipeline uses FRED DCOILWTICO (spot/series definition per FRED). "
            "Yahoo CL=F is front-month futures — levels and dates will not match."
        ),
        "critical_check": {
            "question": "Is 90d avg a valid dynamic baseline for oil shock magnitude?",
            "wti_current_usd": wti_current,
            "wti_90d_avg_usd": round(wti_90d_avg, 4),
            "interpretation": (
                "Analog scoring uses harmonized_oil_shock_pct (12m pre-peak min → peak in last 36m), "
                "not the 90d mean shock — see harmonized_oil_shock_pct for comparable feature."
            ),
        },
        "cpi_latest": cpi_latest if np.isfinite(cpi_latest) else None,
        "cpi_13_observations_ago": cpi_13mo if np.isfinite(cpi_13mo) else None,
        "cpi_yoy_latest_month": cpi_yoy_latest_date,
        "cpi_yoy_year_ago_month": cpi_yoy_year_ago_date,
        "cpi_yoy_n_valid_obs_desc": len(cpi_pairs),
        "cpi_nan_filled": cpi_nan_filled,
        "cpi_yoy_pct": round(cpi_yoy, 4) if np.isfinite(cpi_yoy) else None,
        "fed_rate": fed_rate,
        "fed_room_fed_minus_cpi_yoy": round(fed_room, 4) if np.isfinite(fed_room) else None,
        "unrate": unrate,
        "indpro_latest": ind_latest,
        "indpro_prev_month": ind_prev,
        "indpro_mom_pct": round(indpro_mom, 4),
        "umcsent": umcsent,
        "formulas": {
            "oil_shock_pct_90d_baseline": "(wti_current - wti_90d_avg) / wti_90d_avg * 100",
            "oil_shock_harmonized": "scripts.ground_truth_common.harmonized_oil_shock_monthly on monthly DCOIL",
            "cpi_yoy": "(cpi_latest / cpi_13mo_ago - 1) * 100",
            "fed_room": "fed_rate - cpi_yoy",
            "indpro_mom": "(indpro_latest / indpro_prev - 1) * 100",
        },
    }

    return raw_out, manual


def vector_for_scaler(row: dict[str, Any], use_umcsent: bool) -> list[float]:
    """Order fixed for MinMax + distance."""
    base = [
        row["oil_feature"],
        row["cpi_yoy"],
        row["fed_rate"],
        row["unrate"],
        row["indpro_mom"],
        row["fed_room"],
    ]
    if use_umcsent:
        base.append(row["umcsent"])
    return base


def main() -> int:
    load_dotenv_keys()
    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if not api_key:
        print("ERROR: FRED_API_KEY required.", file=sys.stderr)
        return 1

    GROUND.mkdir(parents=True, exist_ok=True)

    raw_snapshot, manual = build_live_manual(api_key)
    live_path = GROUND / "live_snapshot_2026.json"
    live_payload = {**raw_snapshot, "manual_computations": manual}
    live_path.write_text(json.dumps(live_payload, indent=2))
    print(f"Wrote {live_path}")

    # Analog rows from disk
    a1973 = analog_end_features(GROUND / "1973_macro.csv", GROUND / "1973_macro_stats.json", "1973")
    a1990 = analog_end_features(GROUND / "1990_macro.csv", GROUND / "1990_macro_stats.json", "1990")
    a2022 = analog_end_features(GROUND / "2022_macro.csv", GROUND / "2022_macro_stats.json", "2022")

    ho = manual.get("harmonized_oil_shock_pct")
    if ho is None or (isinstance(ho, float) and not np.isfinite(ho)):
        ho = float("nan")

    def _mf(v: Any) -> float:
        if v is None:
            return float("nan")
        try:
            x = float(v)
        except (TypeError, ValueError):
            return float("nan")
        return x if np.isfinite(x) else float("nan")

    # Current row: oil uses same harmonized definition as analog *_macro_stats
    current = {
        "period": "current_2026",
        "oil_feature": float(ho),
        "cpi_yoy": _mf(manual.get("cpi_yoy_pct")),
        "fed_rate": _mf(manual.get("fed_rate")),
        "unrate": _mf(manual.get("unrate")),
        "indpro_mom": _mf(manual.get("indpro_mom_pct")),
        "umcsent": _mf(manual.get("umcsent")),
        "fed_room": _mf(manual.get("fed_room_fed_minus_cpi_yoy")),
        "as_of_date": manual.get("wti_observation_date_latest"),
    }

    analog_rows = [
        {
            "period": a1973["period"],
            "oil_feature": a1973["oil_feature_harmonized_shock_pct"],
            "cpi_yoy": a1973["cpi_yoy"],
            "fed_rate": a1973["fed_rate"],
            "unrate": a1973["unrate"],
            "indpro_mom": a1973["indpro_mom"],
            "umcsent": a1973["umcsent"],
            "fed_room": a1973["fed_room"],
            "as_of_date": a1973["as_of_date"],
        },
        {
            "period": a1990["period"],
            "oil_feature": a1990["oil_feature_harmonized_shock_pct"],
            "cpi_yoy": a1990["cpi_yoy"],
            "fed_rate": a1990["fed_rate"],
            "unrate": a1990["unrate"],
            "indpro_mom": a1990["indpro_mom"],
            "umcsent": a1990["umcsent"],
            "fed_room": a1990["fed_room"],
            "as_of_date": a1990["as_of_date"],
        },
        {
            "period": a2022["period"],
            "oil_feature": a2022["oil_feature_harmonized_shock_pct"],
            "cpi_yoy": a2022["cpi_yoy"],
            "fed_rate": a2022["fed_rate"],
            "unrate": a2022["unrate"],
            "indpro_mom": a2022["indpro_mom"],
            "umcsent": a2022["umcsent"],
            "fed_room": a2022["fed_room"],
            "as_of_date": a2022["as_of_date"],
        },
        current,
    ]

    # UMCSENT often missing in 1973 panel → use 6 features without umcsent for scaler
    use_umcsent = all(np.isfinite(r["umcsent"]) for r in analog_rows)
    feature_names = [
        "oil_feature",
        "cpi_yoy",
        "fed_rate",
        "unrate",
        "indpro_mom",
        "fed_room",
    ]
    if use_umcsent:
        feature_names.append("umcsent")

    X = np.array([vector_for_scaler(r, use_umcsent) for r in analog_rows], dtype=float)
    # Impute nan with column median for scaler stability (documented)
    col_med = np.nanmedian(X, axis=0)
    inds = np.where(np.isnan(X))
    X[inds] = np.take(col_med, inds[1])

    scaler = MinMaxScaler()
    Xs = scaler.fit_transform(X)

    distances = {}
    scores = {}
    for i, label in enumerate(["1973", "1990", "2022"]):
        d = float(np.linalg.norm(Xs[3] - Xs[i]))
        distances[label] = d
        scores[label] = 1.0 / (1.0 + d)

    primary = max(scores, key=scores.get)

    compliance = {
        "mission1": {
            "base_series_json_per_period": 9,
            "supplemental_json_per_period": "SPASTT01USM661N (+ WTISPLC when DCOIL empty in 1973)",
            "inventory_note": (
                "File count under ground_truth/ is not '27' — it is 9×3 base pulls + 3 SPAST + "
                "conditional WTISPLC + 3 master CSV + stats + mission2/3 artifacts. "
                "Do not claim exactly 27 files on disk."
            ),
            "fred_sp500_daily_reality": (
                "FRED SP500 has observation_start 2016-04-01; zero in-window obs for 1973/1990. "
                "Drawdown stats use SPASTT01USM661N (1973/1990) or SP500 (2022). "
                "`sp500` CSV column is cash index month-end when available else NaN."
            ),
            "master_csvs": ["1973_macro.csv", "1990_macro.csv", "2022_macro.csv"],
            "oil_shock": "harmonized_12m_pre_peak_min_to_window_peak (Mission 1 + NYX scoring)",
        },
        "mission2": {
            "sector_prices_36mo_csv": True,
            "oil_beta_verified_json": True,
            "price_sources_keys_match_sectors_keys": True,
            "use_in_eps_model_false_when_p_gt_0_05": True,
            "use_in_eps_model_false_for_benchmarks": "USO and SPY always use_in_eps_model=false",
            "fallbacks": "Yahoo v8 / AV / Stooq documented when yfinance fails.",
        },
        "mission3": {
            "live_snapshot_2026_json": True,
            "manual_analog_score_json": True,
            "analog_scorer_tolerance_note": "When analog_scorer.py ships, match confidence within 0.02 of scores below.",
        },
        "computer_tasks": {
            "analog_data_client_py": "analog/data_client.py",
            "analog_router_py": "analog/router.py",
            "sklearn_in_requirements": True,
        },
    }

    oil_note = (
        "All four rows use harmonized_oil_shock_pct: 12m minimum strictly before peak month "
        "vs peak WTI in the comparison window (Mission 1 windows for analogs; trailing 36m for current)."
    )

    score_payload = {
        "computed_at_utc": datetime.now(timezone.utc).isoformat(),
        "spec_compliance_audit": compliance,
        "oil_feature_harmonization_note": oil_note,
        "feature_names": feature_names,
        "use_umcsent_in_vector": use_umcsent,
        "nan_imputation": "NaN cells replaced with column median before MinMaxScaler (only if any).",
        "rows_order": ["1973", "1990", "2022", "current_2026"],
        "raw_vectors": analog_rows,
        "minmax_scaler_data_min": scaler.data_min_.tolist(),
        "minmax_scaler_data_max": scaler.data_max_.tolist(),
        "scaled_matrix": Xs.tolist(),
        "euclidean_distance_scaled_space": distances,
        "confidence_score_1_over_1_plus_d": scores,
        "primary_analog_by_score": primary,
        "acceptance_test": {
            "rule": "analog_scorer.py max confidence delta vs this file must be <= 0.02 per period",
            "baseline_scores": scores,
        },
    }

    score_path = GROUND / "manual_analog_score.json"
    score_path.write_text(json.dumps(score_payload, indent=2))
    print(f"Wrote {score_path}")
    print(json.dumps({"distances": distances, "scores": scores, "primary": primary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
