"""Construct Task 7 model features and audit the frozen econometric sample."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


HEADLINE_REGIONS = {"NSW1", "VIC1", "QLD1", "SA1"}
POST_5MS = pd.Timestamp("2021-10-01 00:00:00", tz="Australia/Brisbane")
LAG_BLOCKS = {
    "renewable_share_ws_10pp_lag_1_3": range(1, 4),
    "renewable_share_ws_10pp_lag_4_6": range(4, 7),
    "renewable_share_ws_10pp_lag_7_12": range(7, 13),
    "renewable_share_ws_10pp_lag_13_24": range(13, 25),
}


def add_model_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add only transformations and identifiers frozen in Task 7."""
    result = frame.sort_values(["region", "timestamp"], ignore_index=True).copy()
    result["price_asinh"] = np.arcsinh(result["rrp_aud_mwh"])
    result["intrahour_price_sd_asinh"] = np.arcsinh(result["intrahour_price_sd"])
    result["renewable_share_ws_10pp"] = 10.0 * result["renewable_share_ws"]
    result["renewable_share_broad_10pp"] = 10.0 * result["renewable_share_broad"]
    result["wind_share_10pp"] = np.where(result["demand_mw"] > 0, 10.0 * result["wind_mw"] / result["demand_mw"], np.nan)
    result["solar_utility_share_10pp"] = np.where(result["demand_mw"] > 0, 10.0 * result["solar_utility_mw"] / result["demand_mw"], np.nan)
    result["renewable_output_ws_100mw"] = (result["wind_mw"] + result["solar_utility_mw"]) / 100.0
    result["log_demand"] = np.nan
    positive_demand = result["demand_mw"] > 0
    result.loc[positive_demand, "log_demand"] = np.log(result.loc[positive_demand, "demand_mw"])
    headline_log_mean = result.loc[result["region"].isin(HEADLINE_REGIONS), "log_demand"].mean()
    result["log_demand_centered"] = result["log_demand"] - headline_log_mean
    result["log_demand_centered_sq"] = result["log_demand_centered"] ** 2
    result["aest_year_month"] = result["timestamp"].dt.strftime("%Y-%m")
    result["aest_date"] = result["timestamp"].dt.strftime("%Y-%m-%d")
    iso = result["timestamp"].dt.isocalendar()
    result["aest_week"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    result["region_month"] = result["region"] + "_" + result["aest_year_month"]
    result["region_date"] = result["region"] + "_" + result["aest_date"]
    result["local_hour_weekday"] = result["local_weekday"].astype(str) + "_" + result["local_hour"].astype(str).str.zfill(2)
    result["post_5ms"] = result["timestamp"] >= POST_5MS
    result["headline_region"] = result["region"].isin(HEADLINE_REGIONS)
    result["headline_sample"] = result["headline_region"] & result["renewable_share_ws_10pp"].notna() & result["log_demand"].notna()
    exposure_cap = result.loc[result["headline_sample"], "renewable_share_ws"].quantile(0.999)
    result["renewable_share_ws_winsor_p999"] = result["renewable_share_ws"].clip(upper=exposure_cap)
    result["renewable_share_ws_10pp_winsor_p999"] = 10.0 * result["renewable_share_ws_winsor_p999"]
    by_region = result.groupby("region", observed=True)["renewable_share_ws_10pp_winsor_p999"]
    for lag in range(1, 25):
        result[f"_x_lag_{lag}"] = by_region.shift(lag)
    for name, lags in LAG_BLOCKS.items():
        columns = [f"_x_lag_{lag}" for lag in lags]
        result[name] = result[columns].mean(axis=1, skipna=False)
    # A valid distributed-lag observation needs every hourly lag used in the
    # four pre-specified blocks, not merely a non-missing 24-hour lag.  This
    # matters around the few hours removed for non-positive demand.
    lag_block_columns = list(LAG_BLOCKS)
    result["dynamic_sample"] = result["headline_sample"] & result[lag_block_columns].notna().all(axis=1)
    result = result.drop(columns=[f"_x_lag_{lag}" for lag in range(1, 25)])
    headline_price = result.loc[result["headline_sample"], "rrp_aud_mwh"]
    lower, upper = headline_price.quantile([0.001, 0.999])
    result["price_winsor_001_999"] = result["rrp_aud_mwh"].clip(lower=lower, upper=upper)
    for threshold_column in [
        "negative_price_below_minus_50_any_5min",
        "negative_price_below_minus_100_any_5min",
    ]:
        if threshold_column not in result:
            raise ValueError(
                f"Hourly panel lacks {threshold_column}; rebuild it from the five-minute price panel"
            )
    return result


def alternating_demean(values: pd.Series, groups: list[pd.Series], tolerance: float = 1e-10) -> pd.Series:
    """Residualise values against crossed categorical effects for support audits."""
    residual = values.astype(float).copy()
    for _ in range(200):
        before = residual.to_numpy(copy=True)
        for group in groups:
            residual -= residual.groupby(group, observed=True).transform("mean")
        if np.nanmax(np.abs(residual.to_numpy() - before)) < tolerance:
            return residual
    raise RuntimeError("Alternating demeaning did not converge")


def audit_model_frame(frame: pd.DataFrame) -> dict[str, object]:
    """Return auditable sample sizes, support and fixed-effect counts."""
    sample = frame.loc[frame["headline_sample"]].copy()
    within_exposure = alternating_demean(
        sample["renewable_share_ws_10pp_winsor_p999"], [sample["region_month"], sample["timestamp"]]
    )
    within_exposure_raw = alternating_demean(
        sample["renewable_share_ws_10pp"], [sample["region_month"], sample["timestamp"]]
    )
    return {
        "panel_rows_all_regions": int(len(frame)),
        "headline_rows": int(len(sample)),
        "headline_rows_post_5ms": int(sample["post_5ms"].sum()),
        "dynamic_rows_with_24h_history": int(frame["dynamic_sample"].sum()),
        "headline_regions": sorted(sample["region"].unique().tolist()),
        "hours_per_headline_region": sample.groupby("region", observed=True).size().astype(int).to_dict(),
        "missing_headline_share_rows_dropped": int((frame["headline_region"] & ~frame["headline_sample"]).sum()),
        "exact_hour_fixed_effects": int(sample["timestamp"].nunique()),
        "region_month_fixed_effects": int(sample["region_month"].nunique()),
        "aest_week_clusters": int(sample["aest_week"].nunique()),
        "negative_price_any_rate": float(sample["negative_price_any"].mean()),
        "price_aud_mwh_percentiles": sample["rrp_aud_mwh"].quantile([0, 0.001, 0.01, 0.5, 0.99, 0.999, 1]).to_dict(),
        "renewable_share_ws_percentiles": sample["renewable_share_ws"].quantile([0, 0.01, 0.5, 0.99, 1]).to_dict(),
        "headline_exposure_upper_winsor_cap": float(sample["renewable_share_ws"].quantile(0.999)),
        "headline_exposure_rows_at_cap": int((sample["renewable_share_ws"] > sample["renewable_share_ws"].quantile(0.999)).sum()),
        "headline_exposure_within_fe_std_10pp_units": float(within_exposure.std(ddof=1)),
        "raw_exposure_within_fe_std_10pp_units": float(within_exposure_raw.std(ddof=1)),
        "post_5ms_start": POST_5MS.isoformat(),
    }


def build_specification_audit(root: Path) -> dict[str, object]:
    """Validate the YAML contract, write features, and save the audit JSON."""
    spec_path = root / "config/econometric_spec.yml"
    with spec_path.open(encoding="utf-8") as handle:
        spec = yaml.safe_load(handle)
    if spec["version"] != "1.0-task7-frozen" or spec["estimand"]["causal_claim"]:
        raise ValueError("Econometric specification is absent, unfrozen, or incorrectly claims causality")
    source = pd.read_parquet(root / "data/processed/nem_region_hour.parquet")
    model = add_model_features(source)
    audit = audit_model_frame(model)
    model.to_parquet(root / "data/processed/nem_region_hour_model.parquet", index=False)
    (root / "data/interim/task7_specification_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(build_specification_audit(args.root.resolve()), indent=2))


if __name__ == "__main__":
    main()
