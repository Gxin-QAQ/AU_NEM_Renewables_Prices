"""Estimate the converged Task 8 nonlinear negative-price robustness models.

The frozen specification uses region-month and local-hour-by-weekday effects
for nonlinear models. This module uses Binomial GLM with Logit and Probit
links, clustered by AEST week. It is intentionally separate from the exact-
hour fixed-effect LPM, which remains the headline binary estimate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm

from src.core_estimation import CONTROLS, EXPOSURE


def coarse_nonlinear_design(frame: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame, pd.Series]:
    """Return the pre-specified binary outcome, coarse-FE design and clusters."""
    required = ["headline_sample", "negative_price_any", EXPOSURE, *CONTROLS, "region_month", "local_hour_weekday", "aest_week"]
    missing = set(required) - set(frame)
    if missing:
        raise ValueError(f"Model frame is missing: {sorted(missing)}")
    sample = frame.loc[frame["headline_sample"]].dropna(subset=["negative_price_any", EXPOSURE, *CONTROLS]).copy()
    base = sm.add_constant(sample[[EXPOSURE, *CONTROLS]].astype(float).reset_index(drop=True), has_constant="add")
    region_month = pd.get_dummies(sample["region_month"].astype("category"), prefix="region_month", drop_first=True, dtype=float).reset_index(drop=True)
    local_hour_weekday = pd.get_dummies(sample["local_hour_weekday"].astype("category"), prefix="local_hour_weekday", drop_first=True, dtype=float).reset_index(drop=True)
    design = pd.concat([base, region_month, local_hour_weekday], axis=1)
    return sample["negative_price_any"].astype(float).reset_index(drop=True), design, sample["aest_week"].reset_index(drop=True)


def fit_nonlinear_models(root: Path) -> dict[str, object]:
    """Fit and export clustered Logit and Probit GLM robustness estimates."""
    frame = pd.read_parquet(root / "data/processed/nem_region_hour_model.parquet")
    outcome, design, clusters = coarse_nonlinear_design(frame)
    output_rows: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    specifications = {
        "logit": sm.families.links.Logit(),
        "probit": sm.families.links.Probit(),
    }
    for name, link in specifications.items():
        result = sm.GLM(outcome.to_numpy(), design, family=sm.families.Binomial(link=link)).fit(
            maxiter=150,
            tol=1e-9,
            cov_type="cluster",
            cov_kwds={"groups": clusters.to_numpy(), "use_correction": True},
        )
        if not result.converged:
            raise RuntimeError(f"{name} GLM did not converge")
        ci = result.conf_int(alpha=0.05)
        linear_prediction = np.asarray(design @ result.params)
        derivative = (
            result.predict() * (1.0 - result.predict())
            if name == "logit"
            else norm.pdf(linear_prediction)
        )
        ame = float(np.mean(derivative) * result.params[EXPOSURE])
        for parameter in [EXPOSURE, *CONTROLS]:
            output_rows.append(
                {
                    "model": name,
                    "outcome": "negative_price_any",
                    "parameter": parameter,
                    "coefficient": float(result.params[parameter]),
                    "std_error": float(result.bse[parameter]),
                    "z_stat": float(result.tvalues[parameter]),
                    "p_value": float(result.pvalues[parameter]),
                    "ci_lower": float(ci.loc[parameter, 0]),
                    "ci_upper": float(ci.loc[parameter, 1]),
                    "nobs": int(result.nobs),
                    "week_clusters": int(clusters.nunique()),
                    "effects": "region_month + local_hour_weekday",
                    "covariance": "clustered_aest_week_small_sample_corrected",
                }
            )
        summaries.append(
            {
                "model": name,
                "converged": bool(result.converged),
                "iterations": int(result.fit_history.get("iteration", 0)),
                "nobs": int(result.nobs),
                "week_clusters": int(clusters.nunique()),
                "exposure_average_marginal_effect": ame,
                "ame_inference": "point estimate only; week-block bootstrap is reserved for Task 9",
            }
        )
    output = root / "outputs/tables"
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(output_rows).to_csv(output / "task8_nonlinear_negative_price_coefficients.csv", index=False)
    pd.DataFrame(summaries).to_csv(output / "task8_nonlinear_negative_price_summary.csv", index=False)
    manifest = {
        "models": list(specifications),
        "nobs": int(len(outcome)),
        "design_columns": int(design.shape[1]),
        "week_clusters": int(clusters.nunique()),
        "quantile_status": "not_run: dense high-dimensional solver did not complete within the bounded Task 8 window; Task 9 retains the frozen quantile formula and week-block bootstrap requirement",
    }
    (root / "data/interim/task8_nonlinear_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(fit_nonlinear_models(args.root.resolve()), indent=2))


if __name__ == "__main__":
    main()
