"""Estimate the Task 8 models exactly as frozen in Task 7."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from linearmodels.iv import AbsorbingLS
from scipy.stats import t as student_t


EXPOSURE = "renewable_share_ws_10pp_winsor_p999"
CONTROLS = ["log_demand_centered", "log_demand_centered_sq"]
EFFECTS = ["region_month", "timestamp"]
OUTCOMES = {
    "price_asinh": "Continuous price (asinh RRP)",
    "rrp_aud_mwh": "Continuous price (level RRP)",
    "price_winsor_001_999": "Continuous price (winsorised level RRP)",
    "negative_price_any": "Any negative five-minute price (LPM)",
    "negative_price_share_5min": "Share of negative five-minute prices",
    "intrahour_price_sd_asinh": "Intrahour volatility (asinh SD)",
    "intrahour_price_sd": "Intrahour volatility (level SD)",
}
CORE_OUTCOMES = list(OUTCOMES)
DYNAMIC_OUTCOMES = ["price_asinh", "negative_price_any", "intrahour_price_sd_asinh"]
HETEROGENEITY_OUTCOMES = DYNAMIC_OUTCOMES
LAG_BLOCKS = [
    "renewable_share_ws_10pp_lag_1_3",
    "renewable_share_ws_10pp_lag_4_6",
    "renewable_share_ws_10pp_lag_7_12",
    "renewable_share_ws_10pp_lag_13_24",
]
REGIONS = ["NSW1", "VIC1", "QLD1", "SA1"]


@dataclass(frozen=True)
class FitRecord:
    name: str
    family: str
    outcome: str
    effects: str
    sample_flag: str
    result: Any
    clusters: int


def prepare_sample(frame: pd.DataFrame, outcome: str, regressors: list[str], sample_flag: str) -> pd.DataFrame:
    """Select one frozen sample and guard against accidental listwise changes."""
    required = [outcome, *regressors, *EFFECTS, "aest_week", sample_flag]
    missing = set(required) - set(frame)
    if missing:
        raise ValueError(f"Model frame is missing: {sorted(missing)}")
    sample = frame.loc[frame[sample_flag]].copy()
    sample = sample.dropna(subset=[outcome, *regressors])
    if sample.empty:
        raise ValueError(f"{outcome}: no observations in {sample_flag}")
    return sample


def fit_absorbed(
    frame: pd.DataFrame,
    *,
    name: str,
    family: str,
    outcome: str,
    regressors: list[str],
    sample_flag: str = "headline_sample",
) -> FitRecord:
    """Fit a fixed-effect OLS/LPM model with the frozen AEST-week covariance."""
    sample = prepare_sample(frame, outcome, regressors, sample_flag)
    absorbed = sample[EFFECTS].astype("category")
    model = AbsorbingLS(
        sample[outcome].astype(float),
        sample[regressors].astype(float),
        absorb=absorbed,
        drop_absorbed=True,
    )
    result = model.fit(cov_type="clustered", clusters=sample["aest_week"], debiased=True)
    return FitRecord(
        name=name,
        family=family,
        outcome=outcome,
        effects="region_month + exact_aest_hour",
        sample_flag=sample_flag,
        result=result,
        clusters=int(sample["aest_week"].nunique()),
    )


def coefficient_rows(record: FitRecord) -> list[dict[str, object]]:
    """Convert a result object to a stable, tidy coefficient table."""
    result = record.result
    ci = result.conf_int(level=0.95)
    rows = []
    for parameter in result.params.index:
        rows.append(
            {
                "model": record.name,
                "family": record.family,
                "outcome": record.outcome,
                "parameter": parameter,
                "coefficient": float(result.params[parameter]),
                "std_error": float(result.std_errors[parameter]),
                "t_stat": float(result.tstats[parameter]),
                "p_value": float(result.pvalues[parameter]),
                "ci_lower": float(ci.loc[parameter, "lower"]),
                "ci_upper": float(ci.loc[parameter, "upper"]),
                "nobs": int(result.nobs),
                "df_absorbed": int(result.df_absorbed),
                "week_clusters": record.clusters,
                "effects": record.effects,
                "sample_flag": record.sample_flag,
                "covariance": "clustered_aest_week_debiased",
            }
        )
    return rows


def linear_contrast(record: FitRecord, weights: dict[str, float], label: str) -> dict[str, object]:
    """Compute a covariance-aware coefficient sum using week-cluster degrees of freedom."""
    parameters = record.result.params.index
    absent = set(weights) - set(parameters)
    if absent:
        raise ValueError(f"Contrast references absent parameters: {sorted(absent)}")
    vector = pd.Series(0.0, index=parameters)
    for parameter, weight in weights.items():
        vector.loc[parameter] = weight
    estimate = float(vector @ record.result.params)
    variance = float(vector @ record.result.cov @ vector)
    std_error = float(np.sqrt(max(variance, 0.0)))
    degrees = record.clusters - 1
    critical = float(student_t.ppf(0.975, df=degrees))
    statistic = estimate / std_error if std_error else np.nan
    p_value = float(2 * student_t.sf(abs(statistic), df=degrees)) if std_error else np.nan
    return {
        "model": record.name,
        "family": record.family,
        "outcome": record.outcome,
        "contrast": label,
        "estimate": estimate,
        "std_error": std_error,
        "t_stat": statistic,
        "p_value": p_value,
        "ci_lower": estimate - critical * std_error,
        "ci_upper": estimate + critical * std_error,
        "nobs": int(record.result.nobs),
        "week_clusters": record.clusters,
        "sample_flag": record.sample_flag,
    }


def interaction_regressors(frame: pd.DataFrame, kind: str) -> tuple[list[str], dict[str, dict[str, float]]]:
    """Create pre-specified interaction columns and reported contrasts."""
    regressors = [EXPOSURE, *CONTROLS]
    contrasts: dict[str, dict[str, float]] = {}
    if kind == "region":
        regressors = [*CONTROLS]
        for region in REGIONS:
            column = f"{EXPOSURE}_x_{region}"
            frame[column] = frame[EXPOSURE] * frame["region"].eq(region)
            regressors.append(column)
            contrasts[region] = {column: 1.0}
    elif kind == "peak":
        column = f"{EXPOSURE}_x_peak"
        frame[column] = frame[EXPOSURE] * frame["peak"].astype(float)
        regressors.append(column)
        contrasts = {"off_peak": {EXPOSURE: 1.0}, "peak": {EXPOSURE: 1.0, column: 1.0}}
    elif kind == "season":
        for season in ["MAM", "JJA", "SON"]:
            column = f"{EXPOSURE}_x_{season}"
            frame[column] = frame[EXPOSURE] * frame["season"].eq(season)
            regressors.append(column)
        contrasts = {"DJF": {EXPOSURE: 1.0}}
        for season in ["MAM", "JJA", "SON"]:
            contrasts[season] = {EXPOSURE: 1.0, f"{EXPOSURE}_x_{season}": 1.0}
    elif kind == "post_5ms":
        column = f"{EXPOSURE}_x_post_5ms"
        frame[column] = frame[EXPOSURE] * frame["post_5ms"].astype(float)
        regressors.append(column)
        contrasts = {"pre_5ms": {EXPOSURE: 1.0}, "post_5ms": {EXPOSURE: 1.0, column: 1.0}}
    else:
        raise ValueError(f"Unknown interaction kind: {kind}")
    return regressors, contrasts


def run_core_estimation(root: Path) -> dict[str, object]:
    """Run the frozen Task 8 high-dimensional fixed-effect model suite."""
    model_path = root / "data/processed/nem_region_hour_model.parquet"
    if not model_path.exists():
        raise FileNotFoundError("Run `python -m src.specification_audit` before estimation")
    frame = pd.read_parquet(model_path)
    fits: list[FitRecord] = []
    rows: list[dict[str, object]] = []
    contrasts: list[dict[str, object]] = []

    for outcome in CORE_OUTCOMES:
        record = fit_absorbed(
            frame,
            name=f"core_{outcome}",
            family="core",
            outcome=outcome,
            regressors=[EXPOSURE, *CONTROLS],
        )
        fits.append(record)
        rows.extend(coefficient_rows(record))

    for outcome in DYNAMIC_OUTCOMES:
        record = fit_absorbed(
            frame,
            name=f"dynamic_{outcome}",
            family="distributed_lag",
            outcome=outcome,
            regressors=[EXPOSURE, *LAG_BLOCKS, *CONTROLS],
            sample_flag="dynamic_sample",
        )
        fits.append(record)
        rows.extend(coefficient_rows(record))
        contrasts.append(linear_contrast(record, {EXPOSURE: 1.0, **{lag: 1.0 for lag in LAG_BLOCKS}}, "contemporaneous_plus_lags_1_24"))

    for kind in ["region", "peak", "season", "post_5ms"]:
        working = frame.copy()
        regressors, named_contrasts = interaction_regressors(working, kind)
        for outcome in HETEROGENEITY_OUTCOMES:
            record = fit_absorbed(
                working,
                name=f"heterogeneity_{kind}_{outcome}",
                family=f"heterogeneity_{kind}",
                outcome=outcome,
                regressors=regressors,
            )
            fits.append(record)
            rows.extend(coefficient_rows(record))
            for label, weights in named_contrasts.items():
                contrasts.append(linear_contrast(record, weights, label))

    output = root / "outputs/tables"
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output / "task8_coefficients.csv", index=False)
    pd.DataFrame(contrasts).to_csv(output / "task8_linear_contrasts.csv", index=False)
    manifest = {
        "models": len(fits),
        "core_models": len(CORE_OUTCOMES),
        "dynamic_models": len(DYNAMIC_OUTCOMES),
        "heterogeneity_models": len(fits) - len(CORE_OUTCOMES) - len(DYNAMIC_OUTCOMES),
        "coefficient_rows": len(rows),
        "contrast_rows": len(contrasts),
        "exposure": EXPOSURE,
        "controls": CONTROLS,
        "effects": EFFECTS,
        "covariance": "clustered_aest_week_debiased",
    }
    (root / "data/interim/task8_estimation_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(run_core_estimation(args.root.resolve()), indent=2))


if __name__ == "__main__":
    main()
