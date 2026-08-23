"""Test pre-specified Task 9 differences between heterogeneity slopes."""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import pandas as pd
from statsmodels.stats.multitest import multipletests

from src.core_estimation import (
    EXPOSURE,
    HETEROGENEITY_OUTCOMES,
    REGIONS,
    fit_absorbed,
    interaction_regressors,
    linear_contrast,
)


def slope_weights(kind: str) -> dict[str, dict[str, float]]:
    """Return the coefficient map for every reported group-specific slope."""
    if kind == "region":
        return {region: {f"{EXPOSURE}_x_{region}": 1.0} for region in REGIONS}
    if kind == "peak":
        return {
            "off_peak": {EXPOSURE: 1.0},
            "peak": {EXPOSURE: 1.0, f"{EXPOSURE}_x_peak": 1.0},
        }
    if kind == "season":
        weights = {"DJF": {EXPOSURE: 1.0}}
        for season in ["MAM", "JJA", "SON"]:
            weights[season] = {EXPOSURE: 1.0, f"{EXPOSURE}_x_{season}": 1.0}
        return weights
    if kind == "post_5ms":
        return {
            "pre_5ms": {EXPOSURE: 1.0},
            "post_5ms": {EXPOSURE: 1.0, f"{EXPOSURE}_x_post_5ms": 1.0},
        }
    raise ValueError(f"Unknown heterogeneity kind: {kind}")


def subtract_weights(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    """Construct left-minus-right contrast weights without zero entries."""
    parameters = set(left) | set(right)
    return {
        parameter: left.get(parameter, 0.0) - right.get(parameter, 0.0)
        for parameter in parameters
        if left.get(parameter, 0.0) != right.get(parameter, 0.0)
    }


def run_heterogeneity_inference(root: Path) -> pd.DataFrame:
    """Refit frozen interaction models and test all within-family slope gaps."""
    frame = pd.read_parquet(root / "data/processed/nem_region_hour_model.parquet")
    rows: list[dict[str, object]] = []
    for kind in ["region", "peak", "season", "post_5ms"]:
        working = frame.copy()
        regressors, _ = interaction_regressors(working, kind)
        groups = slope_weights(kind)
        for outcome in HETEROGENEITY_OUTCOMES:
            fit = fit_absorbed(
                working,
                name=f"heterogeneity_difference_{kind}_{outcome}",
                family=f"heterogeneity_difference_{kind}",
                outcome=outcome,
                regressors=regressors,
            )
            family_rows: list[dict[str, object]] = []
            for left, right in itertools.combinations(groups, 2):
                contrast = linear_contrast(
                    fit,
                    subtract_weights(groups[left], groups[right]),
                    f"{left}_minus_{right}",
                )
                contrast["heterogeneity_family"] = kind
                family_rows.append(contrast)
            adjusted = multipletests([row["p_value"] for row in family_rows], method="holm")[1]
            for row, p_value_holm in zip(family_rows, adjusted, strict=True):
                row["p_value_holm"] = float(p_value_holm)
            rows.extend(family_rows)
    result = pd.DataFrame(rows)
    result.to_csv(root / "outputs/tables/task9_heterogeneity_differences_holm.csv", index=False)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = run_heterogeneity_inference(args.root.resolve())
    print(f"wrote {len(result)} comparisons")


if __name__ == "__main__":
    main()
