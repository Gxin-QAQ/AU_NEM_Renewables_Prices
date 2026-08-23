"""Create a reader-facing Task 9 robustness summary."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.core_estimation import CONTROLS


def build_summary(root: Path) -> pd.DataFrame:
    source = pd.read_csv(root / "outputs/tables/task9_robustness_coefficients.csv")
    result = source.loc[~source["parameter"].isin(CONTROLS)].copy()
    result["effect_unit"] = "per 10 percentage-point share increase"
    result.loc[result["parameter"].eq("renewable_output_ws_100mw"), "effect_unit"] = "per 100 MW wind-plus-solar output"
    result["claim_boundary"] = "conditional association; not causal"
    columns = [
        "family",
        "outcome",
        "parameter",
        "coefficient",
        "std_error",
        "p_value",
        "ci_lower",
        "ci_upper",
        "nobs",
        "effects",
        "sample",
        "covariance",
        "effect_unit",
        "claim_boundary",
    ]
    return result[columns]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    result = build_summary(root)
    result.to_csv(root / "outputs/tables/task9_main_robustness_summary.csv", index=False)
    print(f"wrote {len(result)} rows")


if __name__ == "__main__":
    main()
