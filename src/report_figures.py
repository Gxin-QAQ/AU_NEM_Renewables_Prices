"""Build the coefficient figures used in the final research report.

The module reads only frozen Task 8–9 result tables. It never re-estimates a
model, which keeps the report layer separate from the econometric pipeline.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


BLUE = "#2E74B5"
ORANGE = "#D97706"
GREY = "#59636E"


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 150,
            "savefig.dpi": 220,
        }
    )


def build_regional_heterogeneity(root: Path) -> Path:
    contrasts = pd.read_csv(root / "outputs/tables/task8_linear_contrasts.csv")
    df = contrasts.loc[
        (contrasts["family"] == "heterogeneity_region")
        & (contrasts["outcome"] == "price_asinh")
    ].copy()
    order = ["NSW1", "VIC1", "QLD1", "SA1"]
    df["contrast"] = pd.Categorical(df["contrast"], categories=order, ordered=True)
    df = df.sort_values("contrast", ascending=False)

    fig, ax = plt.subplots(figsize=(7.0, 3.25))
    y = range(len(df))
    ax.errorbar(
        df["estimate"],
        list(y),
        xerr=[df["estimate"] - df["ci_lower"], df["ci_upper"] - df["estimate"]],
        fmt="o",
        color=BLUE,
        ecolor=BLUE,
        elinewidth=1.8,
        capsize=3,
    )
    ax.axvline(0, color="#7A7A7A", linewidth=1)
    ax.set_yticks(list(y), df["contrast"].astype(str))
    ax.set_xlabel("Coefficient on a 10 percentage-point increase in wind–solar share")
    ax.set_title("Regional slopes for asinh hourly RRP (95% confidence intervals)")
    ax.grid(axis="x", color="#D9DEE3", linewidth=0.7)
    ax.text(
        0.0,
        -0.30,
        "Exact AEST-hour and region-month fixed effects; AEST-week clustered standard errors.",
        transform=ax.transAxes,
        fontsize=8.5,
        color=GREY,
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    out = root / "outputs/figures/fig5_regional_price_heterogeneity.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def build_price_robustness(root: Path) -> Path:
    df = pd.read_csv(root / "outputs/tables/task9_main_robustness_summary.csv")
    keep = {
        "exposure_headline_p999": "Headline p99.9 cap",
        "exposure_raw_uncapped": "Raw uncapped ratio",
        "exposure_cap_at_one": "Share capped at 1",
        "exposure_all_unknown_as_renewable_upper_bound": "All UNKNOWN as renewable",
        "sample_include_tas1": "Include Tasmania",
        "sample_post_5ms": "Post-5MS sample",
        "aggressive_region_date_fe": "Region-date FE",
    }
    df = df.loc[(df["outcome"] == "price_asinh") & df["family"].isin(keep)].copy()
    df["label"] = df["family"].map(keep)
    order = list(keep.values())
    df["label"] = pd.Categorical(df["label"], categories=order, ordered=True)
    df = df.sort_values("label", ascending=False)

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    y = range(len(df))
    colors = [ORANGE if x == "Raw uncapped ratio" else BLUE for x in df["label"].astype(str)]
    for yi, (_, row), colour in zip(y, df.iterrows(), colors):
        ax.errorbar(
            row["coefficient"],
            yi,
            xerr=[[row["coefficient"] - row["ci_lower"]], [row["ci_upper"] - row["coefficient"]]],
            fmt="o",
            color=colour,
            ecolor=colour,
            elinewidth=1.7,
            capsize=3,
        )
    ax.axvline(0, color="#7A7A7A", linewidth=1)
    ax.set_yticks(list(y), df["label"].astype(str))
    ax.set_xlabel("Coefficient for asinh hourly RRP")
    ax.set_title("Price association across pre-specified robustness checks (95% CIs)")
    ax.grid(axis="x", color="#D9DEE3", linewidth=0.7)
    ax.text(
        0.0,
        -0.24,
        "All share effects are per 10 percentage points; the raw ratio is highlighted because of extreme denominator leverage.",
        transform=ax.transAxes,
        fontsize=8.5,
        color=GREY,
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    out = root / "outputs/figures/fig6_price_robustness.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    _style()
    for path in (build_regional_heterogeneity(root), build_price_robustness(root)):
        print(path.relative_to(root))


if __name__ == "__main__":
    main()
