"""Create Task 6 descriptive tables and figures from the final hourly panel.

Outputs are descriptive associations only.  They are not causal estimates and
retain AEMO's uncapped regional generation-to-operational-demand ratio.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


REGION_ORDER = ["NSW1", "VIC1", "QLD1", "SA1", "TAS1"]
REGION_COLOURS = {"NSW1": "#1f77b4", "VIC1": "#ff7f0e", "QLD1": "#2ca02c", "SA1": "#d62728", "TAS1": "#9467bd"}


def _summary_by_region(frame: pd.DataFrame) -> pd.DataFrame:
    summary = frame.groupby("region", observed=True).agg(
        observations=("timestamp", "size"),
        mean_price_aud_mwh=("rrp_aud_mwh", "mean"),
        median_price_aud_mwh=("rrp_aud_mwh", "median"),
        price_p05_aud_mwh=("rrp_aud_mwh", lambda x: x.quantile(0.05)),
        price_p95_aud_mwh=("rrp_aud_mwh", lambda x: x.quantile(0.95)),
        negative_price_hour_share=("negative_price_any", "mean"),
        mean_intrahour_price_sd=("intrahour_price_sd", "mean"),
        mean_renewable_share_ws=("renewable_share_ws", "mean"),
        median_renewable_share_ws=("renewable_share_ws", "median"),
        mean_renewable_share_broad=("renewable_share_broad", "mean"),
    ).reset_index()
    return summary.set_index("region").reindex(REGION_ORDER).reset_index()


def _share_bins(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.loc[frame["renewable_share_ws"].notna()].copy()
    working["share_bin"] = pd.qcut(working["renewable_share_ws"], q=20, duplicates="drop")
    result = working.groupby(["region", "share_bin"], observed=True).agg(
        observations=("timestamp", "size"),
        mean_renewable_share_ws=("renewable_share_ws", "mean"),
        mean_price_aud_mwh=("rrp_aud_mwh", "mean"),
        median_price_aud_mwh=("rrp_aud_mwh", "median"),
        negative_price_hour_share=("negative_price_any", "mean"),
        mean_intrahour_price_sd=("intrahour_price_sd", "mean"),
    ).reset_index()
    result["share_bin"] = result["share_bin"].astype(str)
    return result


def write_outputs(root: Path) -> dict[str, int]:
    """Write core Task 6 tables and four readable figures."""
    source = root / "data/processed/nem_region_hour.parquet"
    if not source.exists():
        raise FileNotFoundError("Final price panel missing; run build_history_price_panel first")
    frame = pd.read_parquet(source).sort_values(["timestamp", "region"])
    tables = root / "outputs/tables"
    figures = root / "outputs/figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook")

    summary = _summary_by_region(frame)
    summary.to_csv(tables / "price_summary_by_region.csv", index=False)
    bins = _share_bins(frame)
    bins.to_csv(tables / "price_by_renewable_share_bin.csv", index=False)
    monthly = frame.assign(month=frame["timestamp"].dt.strftime("%Y-%m")).groupby(["month", "region"], observed=True).agg(
        hours=("timestamp", "size"), mean_price_aud_mwh=("rrp_aud_mwh", "mean"), median_price_aud_mwh=("rrp_aud_mwh", "median"),
        negative_price_hour_share=("negative_price_any", "mean"), mean_renewable_share_ws=("renewable_share_ws", "mean"),
        mean_intrahour_price_sd=("intrahour_price_sd", "mean"),
    ).reset_index()
    monthly.to_csv(tables / "monthly_price_renewables_summary.csv", index=False)
    missing = pd.DataFrame({"variable": frame.columns, "missing_observations": [int(frame[column].isna().sum()) for column in frame], "missing_share": [float(frame[column].isna().mean()) for column in frame]})
    missing.to_csv(tables / "price_panel_missingness.csv", index=False)

    # Figure 1: 12-month moving average removes transient price spikes while
    # retaining region-specific medium-run co-movement.
    monthly["month_timestamp"] = pd.to_datetime(monthly["month"] + "-01")
    fig, axes = plt.subplots(5, 1, figsize=(11, 12), sharex=True, constrained_layout=True)
    for axis, region in zip(axes, REGION_ORDER, strict=True):
        subset = monthly.loc[monthly["region"].eq(region)].sort_values("month_timestamp")
        axis.plot(subset["month_timestamp"], subset["mean_price_aud_mwh"].rolling(12, min_periods=6).mean(), color=REGION_COLOURS[region], label="RRP (12-month mean)")
        twin = axis.twinx()
        twin.plot(subset["month_timestamp"], subset["mean_renewable_share_ws"].rolling(12, min_periods=6).mean(), color="#222222", alpha=0.75, label="Wind + solar share")
        axis.set_ylabel(f"{region}\nAUD/MWh")
        twin.set_ylabel("Share")
        axis.axhline(0, color="#777777", linewidth=0.7)
    axes[0].set_title("Regional price and wind-solar penetration (12-month moving averages)")
    fig.savefig(figures / "fig1_price_and_renewable_share_trends.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    # Figure 2: pooled quantile bins preserve support even with export-driven
    # shares above one; lines are descriptive conditional means.
    fig, axis = plt.subplots(figsize=(9, 5.5), constrained_layout=True)
    for region in REGION_ORDER:
        subset = bins.loc[bins["region"].eq(region)].sort_values("mean_renewable_share_ws")
        axis.plot(subset["mean_renewable_share_ws"], subset["mean_price_aud_mwh"], marker="o", markersize=3, linewidth=1.5, color=REGION_COLOURS[region], label=region)
    axis.axhline(0, color="#777777", linewidth=0.8)
    axis.set(xlabel="Wind + solar output / operational demand", ylabel="Mean hourly RRP (AUD/MWh)", title="Descriptive price association by renewable-share bin")
    axis.legend(ncol=5, fontsize=9)
    fig.savefig(figures / "fig2_price_by_renewable_share_bin.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    # Figure 3: negative-price outcome is defined from the underlying five-minute price.
    fig, axis = plt.subplots(figsize=(10, 5.5), constrained_layout=True)
    for region in REGION_ORDER:
        subset = monthly.loc[monthly["region"].eq(region)].sort_values("month_timestamp")
        axis.plot(subset["month_timestamp"], 100 * subset["negative_price_hour_share"], color=REGION_COLOURS[region], linewidth=1.2, label=region)
    axis.set(xlabel="Month", ylabel="Hours with any negative 5-min price (%)", title="Negative-price incidence by region")
    axis.legend(ncol=5, fontsize=9)
    fig.savefig(figures / "fig3_negative_price_incidence.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    # Figure 4: intrahour standard deviation gives a frequency-consistent
    # volatility measure before the later formal modelling stage.
    fig, axis = plt.subplots(figsize=(9, 5.5), constrained_layout=True)
    for region in REGION_ORDER:
        subset = bins.loc[bins["region"].eq(region)].sort_values("mean_renewable_share_ws")
        axis.plot(subset["mean_renewable_share_ws"], subset["mean_intrahour_price_sd"], marker="o", markersize=3, linewidth=1.5, color=REGION_COLOURS[region], label=region)
    axis.set(xlabel="Wind + solar output / operational demand", ylabel="Mean intrahour RRP SD (AUD/MWh)", title="Descriptive volatility association by renewable-share bin")
    axis.legend(ncol=5, fontsize=9)
    fig.savefig(figures / "fig4_volatility_by_renewable_share_bin.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    return {"hourly_rows": len(frame), "regions": frame["region"].nunique(), "figures": 4, "tables": 4}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(write_outputs(args.root.resolve()))


if __name__ == "__main__":
    main()
