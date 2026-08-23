"""Run the pre-specified Task 9 linear robustness and inference audit."""

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
from statsmodels.stats.multitest import multipletests

from src.core_estimation import CONTROLS, EFFECTS, EXPOSURE


PRIMARY_OUTCOMES = ["price_asinh", "negative_price_any", "intrahour_price_sd_asinh"]
ALTERNATIVE_EXPOSURES = {
    "headline_p999": [EXPOSURE],
    "raw_uncapped": ["renewable_share_ws_10pp"],
    "cap_at_one": ["renewable_share_ws_10pp_cap1"],
    "broad_including_hydro": ["renewable_share_broad_10pp"],
    "wind_solar_output_100mw": ["renewable_output_ws_100mw"],
    "separate_wind_solar": ["wind_share_10pp", "solar_utility_share_10pp"],
    "all_unknown_as_renewable_upper_bound": ["renewable_share_ws_unknown_upper_10pp_p999"],
}


@dataclass
class RobustFit:
    name: str
    family: str
    outcome: str
    regressors: list[str]
    effects: list[str]
    sample_label: str
    sample: pd.DataFrame
    model: AbsorbingLS
    result: Any


def prepare_task9_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Add Task 9-only sensitivity columns and auditable sample flags."""
    result = frame.copy()
    result["renewable_share_ws_10pp_cap1"] = 10.0 * result["renewable_share_ws"].clip(upper=1.0)
    unknown_upper_share = np.where(
        result["demand_mw"] > 0,
        (result["wind_mw"] + result["solar_utility_mw"] + result["unmapped_scada_mw"]) / result["demand_mw"],
        np.nan,
    )
    # Reuse the frozen headline ratio cap. Treating every UNKNOWN MWh as
    # renewable is a deliberately conservative fuel-mapping upper bound.
    frozen_cap = result.loc[result["headline_sample"], "renewable_share_ws_winsor_p999"].max()
    result["renewable_share_ws_unknown_upper_10pp_p999"] = 10.0 * np.minimum(unknown_upper_share, frozen_cap)
    result["all_five_sample"] = (
        result["region"].isin(["NSW1", "VIC1", "QLD1", "SA1", "TAS1"])
        & result["renewable_share_ws_10pp"].notna()
        & result["log_demand"].notna()
    )
    result["post_5ms_sample"] = result["headline_sample"] & result["post_5ms"]
    return result


def fit_robust_model(
    frame: pd.DataFrame,
    *,
    name: str,
    family: str,
    outcome: str,
    regressors: list[str],
    effects: list[str] = EFFECTS,
    sample_flag: str = "headline_sample",
    covariance: str = "week",
) -> RobustFit:
    """Fit one absorbed model under an explicitly labelled covariance."""
    required = [outcome, *regressors, *effects, sample_flag, "aest_week", "region"]
    missing = set(required) - set(frame)
    if missing:
        raise ValueError(f"Missing Task 9 columns: {sorted(missing)}")
    sample = frame.loc[frame[sample_flag]].dropna(subset=[outcome, *regressors]).copy()
    model = AbsorbingLS(
        sample[outcome].astype(float),
        sample[regressors].astype(float),
        absorb=sample[effects].astype("category"),
        drop_absorbed=True,
    )
    if covariance == "week":
        fit = model.fit(cov_type="clustered", clusters=sample["aest_week"], debiased=True)
    elif covariance == "region_week":
        cluster_codes = pd.DataFrame(
            {
                "region": pd.Categorical(sample["region"]).codes,
                "aest_week": pd.Categorical(sample["aest_week"]).codes,
            },
            index=sample.index,
        )
        fit = model.fit(
            cov_type="clustered",
            clusters=cluster_codes,
            debiased=True,
        )
    elif covariance == "unadjusted":
        fit = model.fit(cov_type="unadjusted", debiased=False)
    else:
        raise ValueError(f"Unknown covariance: {covariance}")
    return RobustFit(name, family, outcome, regressors, effects, sample_flag, sample, model, fit)


def fit_rows(fit: RobustFit, covariance: str) -> list[dict[str, object]]:
    """Return tidy rows for the explicitly requested regressors."""
    ci = fit.result.conf_int(level=0.95)
    rows: list[dict[str, object]] = []
    for parameter in fit.regressors:
        rows.append(
            {
                "model": fit.name,
                "family": fit.family,
                "outcome": fit.outcome,
                "parameter": parameter,
                "coefficient": float(fit.result.params[parameter]),
                "std_error": float(fit.result.std_errors[parameter]),
                "statistic": float(fit.result.tstats[parameter]),
                "p_value": float(fit.result.pvalues[parameter]),
                "ci_lower": float(ci.loc[parameter, "lower"]),
                "ci_upper": float(ci.loc[parameter, "upper"]),
                "nobs": int(fit.result.nobs),
                "week_clusters": int(fit.sample["aest_week"].nunique()),
                "region_clusters": int(fit.sample["region"].nunique()),
                "effects": " + ".join(fit.effects),
                "sample": fit.sample_label,
                "covariance": covariance,
            }
        )
    return rows


def driscoll_kraay_rows(fit: RobustFit, bandwidth: int = 168) -> list[dict[str, object]]:
    """Compute time-score Driscoll–Kraay covariance after absorbing the FEs.

    Scores are first summed across regions at each exact AEST timestamp and
    then passed through a Bartlett HAC kernel. This preserves the panel-time
    ordering that a kernel covariance on region-stacked rows would lose.
    """
    x = np.asarray(fit.model.absorbed_exog, dtype=float)
    residual = np.asarray(fit.result.resids, dtype=float)
    timestamp_codes, unique_times = pd.factorize(fit.sample["timestamp"], sort=True)
    scores = np.zeros((len(unique_times), x.shape[1]), dtype=float)
    np.add.at(scores, timestamp_codes, x * residual[:, None])
    meat = scores.T @ scores
    maximum_lag = min(bandwidth, len(unique_times) - 1)
    for lag in range(1, maximum_lag + 1):
        weight = 1.0 - lag / (bandwidth + 1.0)
        gamma = scores[lag:].T @ scores[:-lag]
        meat += weight * (gamma + gamma.T)
    bread = np.linalg.pinv(x.T @ x)
    covariance = bread @ meat @ bread
    # Match the conservative absorbed-model degrees-of-freedom correction.
    correction = len(fit.sample) / max(int(fit.result.df_resid), 1)
    covariance *= correction
    degrees = len(unique_times) - 1
    critical = float(student_t.ppf(0.975, df=degrees))
    rows: list[dict[str, object]] = []
    for index, parameter in enumerate(fit.regressors):
        estimate = float(fit.result.params[parameter])
        standard_error = float(np.sqrt(max(covariance[index, index], 0.0)))
        statistic = estimate / standard_error if standard_error else np.nan
        p_value = float(2 * student_t.sf(abs(statistic), df=degrees)) if standard_error else np.nan
        rows.append(
            {
                "model": fit.name,
                "family": "inference_driscoll_kraay",
                "outcome": fit.outcome,
                "parameter": parameter,
                "coefficient": estimate,
                "std_error": standard_error,
                "statistic": statistic,
                "p_value": p_value,
                "ci_lower": estimate - critical * standard_error,
                "ci_upper": estimate + critical * standard_error,
                "nobs": int(fit.result.nobs),
                "week_clusters": int(fit.sample["aest_week"].nunique()),
                "region_clusters": int(fit.sample["region"].nunique()),
                "effects": " + ".join(fit.effects),
                "sample": fit.sample_label,
                "covariance": f"driscoll_kraay_bartlett_bandwidth_{bandwidth}_hours",
            }
        )
    return rows


def add_holm_adjustment(root: Path) -> pd.DataFrame:
    """Apply Holm adjustment across contrasts within each frozen model family."""
    source = pd.read_csv(root / "outputs/tables/task8_linear_contrasts.csv")
    heterogeneity = source.loc[source["family"].str.startswith("heterogeneity_")].copy()
    heterogeneity["p_value_holm"] = np.nan
    for _, index in heterogeneity.groupby(["family", "outcome"], sort=False).groups.items():
        heterogeneity.loc[index, "p_value_holm"] = multipletests(
            heterogeneity.loc[index, "p_value"].to_numpy(), method="holm"
        )[1]
    heterogeneity["holm_family"] = heterogeneity["family"] + "__" + heterogeneity["outcome"]
    return heterogeneity


def run_robustness_estimation(root: Path) -> dict[str, object]:
    """Run all bounded Task 9 linear specification and inference checks."""
    frame = prepare_task9_frame(pd.read_parquet(root / "data/processed/nem_region_hour_model.parquet"))
    rows: list[dict[str, object]] = []
    model_count = 0

    for outcome in PRIMARY_OUTCOMES:
        for label, exposures in ALTERNATIVE_EXPOSURES.items():
            fit = fit_robust_model(
                frame,
                name=f"exposure_{label}_{outcome}",
                family=f"exposure_{label}",
                outcome=outcome,
                regressors=[*exposures, *CONTROLS],
            )
            rows.extend(fit_rows(fit, "clustered_aest_week_debiased"))
            model_count += 1

        for label, sample_flag in [("include_tas1", "all_five_sample"), ("post_5ms", "post_5ms_sample")]:
            fit = fit_robust_model(
                frame,
                name=f"sample_{label}_{outcome}",
                family=f"sample_{label}",
                outcome=outcome,
                regressors=[EXPOSURE, *CONTROLS],
                sample_flag=sample_flag,
            )
            rows.extend(fit_rows(fit, "clustered_aest_week_debiased"))
            model_count += 1

        aggressive = fit_robust_model(
            frame,
            name=f"aggressive_fe_{outcome}",
            family="aggressive_region_date_fe",
            outcome=outcome,
            regressors=[EXPOSURE, *CONTROLS],
            effects=["region_date", "timestamp"],
        )
        rows.extend(fit_rows(aggressive, "clustered_aest_week_debiased"))
        model_count += 1

        baseline_unadjusted = fit_robust_model(
            frame,
            name=f"inference_{outcome}",
            family="inference",
            outcome=outcome,
            regressors=[EXPOSURE, *CONTROLS],
            covariance="unadjusted",
        )
        rows.extend(driscoll_kraay_rows(baseline_unadjusted, bandwidth=168))
        model_count += 1

        two_way = fit_robust_model(
            frame,
            name=f"inference_{outcome}",
            family="inference_two_way_benchmark",
            outcome=outcome,
            regressors=[EXPOSURE, *CONTROLS],
            covariance="region_week",
        )
        rows.extend(fit_rows(two_way, "two_way_region_and_aest_week_debiased_four_region_benchmark"))
        model_count += 1

    for outcome in ["negative_price_below_minus_50_any_5min", "negative_price_below_minus_100_any_5min"]:
        fit = fit_robust_model(
            frame,
            name=f"threshold_{outcome}",
            family="alternative_negative_price_threshold",
            outcome=outcome,
            regressors=[EXPOSURE, *CONTROLS],
        )
        rows.extend(fit_rows(fit, "clustered_aest_week_debiased"))
        model_count += 1

    output = root / "outputs/tables"
    output.mkdir(parents=True, exist_ok=True)
    result = pd.DataFrame(rows)
    result.to_csv(output / "task9_robustness_coefficients.csv", index=False)
    holm = add_holm_adjustment(root)
    holm.to_csv(output / "task9_heterogeneity_holm.csv", index=False)
    manifest = {
        "models": model_count,
        "coefficient_rows": int(len(result)),
        "holm_contrasts": int(len(holm)),
        "primary_outcomes": PRIMARY_OUTCOMES,
        "alternative_exposure_models": list(ALTERNATIVE_EXPOSURES),
        "driscoll_kraay_bandwidth_hours": 168,
        "two_way_region_cluster_warning": "benchmark only; four region clusters are insufficient for reliable geographic-cluster asymptotics",
    }
    (root / "data/interim/task9_robustness_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(run_robustness_estimation(args.root.resolve()), indent=2))


if __name__ == "__main__":
    main()
