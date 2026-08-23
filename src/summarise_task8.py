"""Create a compact, reader-facing table from the Task 8 tidy outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.core_estimation import EXPOSURE


CORE_LABELS = {
    "core_price_asinh": "Continuous price (asinh RRP)",
    "core_rrp_aud_mwh": "Continuous price (AUD/MWh level)",
    "core_price_winsor_001_999": "Continuous price (winsorised AUD/MWh)",
    "core_negative_price_any": "Any negative price (LPM, probability points)",
    "core_negative_price_share_5min": "Negative five-minute-price share (points)",
    "core_intrahour_price_sd_asinh": "Intrahour volatility (asinh SD)",
    "core_intrahour_price_sd": "Intrahour volatility (AUD/MWh SD level)",
}


def build_headline_table(root: Path) -> pd.DataFrame:
    """Build one transparent table; all effects are associations per 10pp."""
    tables = root / "outputs/tables"
    coefficients = pd.read_csv(tables / "task8_coefficients.csv")
    contrasts = pd.read_csv(tables / "task8_linear_contrasts.csv")
    nonlinear = pd.read_csv(tables / "task8_nonlinear_negative_price_summary.csv")

    result: list[dict[str, object]] = []
    for model, label in CORE_LABELS.items():
        row = coefficients.loc[(coefficients["model"] == model) & (coefficients["parameter"] == EXPOSURE)].iloc[0]
        result.append(
            {
                "section": "headline_fixed_effects",
                "model": model,
                "outcome_or_contrast": label,
                "estimate": row["coefficient"],
                "std_error": row["std_error"],
                "p_value": row["p_value"],
                "nobs": row["nobs"],
                "week_clusters": row["week_clusters"],
                "note": "Association per 10 percentage-point increase in capped wind-plus-utility-solar share.",
            }
        )
    dynamic = coefficients.loc[coefficients["model"] == "dynamic_price_asinh"]
    for _, row in dynamic.loc[dynamic["parameter"].isin([EXPOSURE, *[p for p in dynamic["parameter"] if "lag_" in p]])].iterrows():
        result.append(
            {
                "section": "distributed_lag_price_asinh",
                "model": "dynamic_price_asinh",
                "outcome_or_contrast": row["parameter"],
                "estimate": row["coefficient"],
                "std_error": row["std_error"],
                "p_value": row["p_value"],
                "nobs": row["nobs"],
                "week_clusters": row["week_clusters"],
                "note": "Association per 10 percentage-point increase; block terms are averages of the stated lag hours.",
            }
        )
    cumulative = contrasts.loc[(contrasts["model"] == "dynamic_price_asinh") & (contrasts["contrast"] == "contemporaneous_plus_lags_1_24")].iloc[0]
    result.append(
        {
            "section": "distributed_lag_price_asinh",
            "model": "dynamic_price_asinh",
            "outcome_or_contrast": "contemporaneous plus lag blocks 1–24",
            "estimate": cumulative["estimate"],
            "std_error": cumulative["std_error"],
            "p_value": cumulative["p_value"],
            "nobs": cumulative["nobs"],
            "week_clusters": cumulative["week_clusters"],
            "note": "Covariance-aware linear sum of the five pre-specified distributed-lag terms.",
        }
    )
    for _, row in nonlinear.iterrows():
        result.append(
            {
                "section": "secondary_nonlinear",
                "model": f"{row['model']}_average_marginal_effect",
                "outcome_or_contrast": "Any negative price (average marginal effect)",
                "estimate": row["exposure_average_marginal_effect"],
                "std_error": pd.NA,
                "p_value": pd.NA,
                "nobs": row["nobs"],
                "week_clusters": row["week_clusters"],
                "note": row["ame_inference"],
            }
        )
    return pd.DataFrame(result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    result = build_headline_table(root)
    result.to_csv(root / "outputs/tables/task8_headline_results.csv", index=False)
    print(f"wrote {len(result)} rows")


if __name__ == "__main__":
    main()
