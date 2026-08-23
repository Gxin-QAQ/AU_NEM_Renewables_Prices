"""Write reproducible descriptive tables for the price-free historical panel.

Price outcomes are intentionally excluded until the separately archived
``DISPATCHPRICE`` source has been acquired and joined.  These tables establish
the coverage, demand and renewable-output side of the eventual analysis.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def write_descriptive_tables(root: Path) -> dict[str, int]:
    """Create compact CSV tables from the processed hourly panel."""
    panel_path = root / "data/processed/nem_region_hour_generation_demand.parquet"
    if not panel_path.exists():
        raise FileNotFoundError("Build the historical generation-demand panel first")
    frame = pd.read_parquet(panel_path)
    output = root / "outputs/tables"
    output.mkdir(parents=True, exist_ok=True)
    metrics = ["demand_mw", "wind_mw", "solar_utility_mw", "hydro_mw", "renewable_share_ws", "renewable_share_broad", "unmapped_scada_mw"]
    region_summary = frame.groupby("region", observed=True).agg(
        observations=("timestamp", "size"), first_hour=("timestamp", "min"), last_hour=("timestamp", "max"),
        **{f"mean_{column}": (column, "mean") for column in metrics},
        **{f"p95_{column}": (column, lambda values: values.quantile(0.95)) for column in metrics},
    ).reset_index()
    region_summary.to_csv(output / "generation_demand_summary_by_region.csv", index=False)
    monthly = frame.assign(month=frame["timestamp"].dt.strftime("%Y-%m")).groupby(["month", "region"], observed=True).agg(
        hours=("timestamp", "size"), mean_demand_mw=("demand_mw", "mean"), mean_wind_mw=("wind_mw", "mean"),
        mean_solar_utility_mw=("solar_utility_mw", "mean"), mean_hydro_mw=("hydro_mw", "mean"),
        mean_renewable_share_ws=("renewable_share_ws", "mean"), mean_renewable_share_broad=("renewable_share_broad", "mean"),
    ).reset_index()
    monthly.to_csv(output / "monthly_generation_demand_summary.csv", index=False)
    missing = pd.DataFrame({"variable": frame.columns, "missing_observations": [int(frame[column].isna().sum()) for column in frame], "missing_share": [float(frame[column].isna().mean()) for column in frame]})
    missing.to_csv(output / "generation_demand_missingness.csv", index=False)
    return {"hourly_rows": len(frame), "regions": frame["region"].nunique(), "months": monthly["month"].nunique()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(write_descriptive_tables(args.root.resolve()))


if __name__ == "__main__":
    main()
