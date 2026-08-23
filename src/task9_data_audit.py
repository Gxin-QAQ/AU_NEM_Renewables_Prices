"""Export Task 9 leverage and UNKNOWN-fuel diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def run_data_audit(root: Path) -> dict[str, object]:
    frame = pd.read_parquet(root / "data/processed/nem_region_hour_model.parquet")
    headline = frame.loc[frame["headline_sample"]].copy()
    denominator = frame["mapped_nonstorage_generation_mw"] + frame["unmapped_scada_mw"]
    frame["unknown_generation_share"] = frame["unmapped_scada_mw"] / denominator.replace(0, np.nan)
    frame["aest_year"] = frame["timestamp"].dt.year
    unknown = (
        frame.groupby(["aest_year", "region"], observed=True)
        .agg(
            unknown_mw_mean=("unmapped_scada_mw", "mean"),
            unknown_mw_max=("unmapped_scada_mw", "max"),
            unknown_generation_share_mean=("unknown_generation_share", "mean"),
            unknown_generation_share_p99=("unknown_generation_share", lambda values: values.quantile(0.99)),
        )
        .reset_index()
    )
    leverage_columns = [
        "timestamp",
        "region",
        "demand_mw",
        "wind_mw",
        "solar_utility_mw",
        "renewable_share_ws",
        "rrp_aud_mwh",
    ]
    leverage = headline.nlargest(25, "renewable_share_ws")[leverage_columns]
    output = root / "outputs/tables"
    output.mkdir(parents=True, exist_ok=True)
    unknown.to_csv(output / "task9_unknown_mapping_by_region_year.csv", index=False)
    leverage.to_csv(output / "task9_high_leverage_hours.csv", index=False)
    latest = unknown.loc[unknown["aest_year"] == unknown["aest_year"].max()]
    summary = {
        "headline_rows": int(len(headline)),
        "headline_exposure_max_raw": float(headline["renewable_share_ws"].max()),
        "headline_exposure_p999_cap": float(headline["renewable_share_ws"].quantile(0.999)),
        "headline_rows_above_p999": int((headline["renewable_share_ws"] > headline["renewable_share_ws"].quantile(0.999)).sum()),
        "latest_year": int(latest["aest_year"].iloc[0]),
        "latest_year_max_region_mean_unknown_share": float(latest["unknown_generation_share_mean"].max()),
        "latest_year_max_region_p99_unknown_share": float(latest["unknown_generation_share_p99"].max()),
        "unknown_upper_bound_sensitivity": "All positive UNKNOWN output is treated as renewable in a dedicated p99.9-capped upper-bound exposure.",
    }
    (root / "data/interim/task9_data_audit.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(run_data_audit(args.root.resolve()), indent=2))


if __name__ == "__main__":
    main()
