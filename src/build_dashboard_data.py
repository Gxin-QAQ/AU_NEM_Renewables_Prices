"""Build the compact, public data payload used by the static Plotly dashboard.

The dashboard intentionally reads only tracked final result tables.  It never
exports raw AEMO archives, the hourly research panel, unit identifiers, or
intermediate data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Final

import pandas as pd


PRIMARY_REGIONS: Final = ("NSW1", "VIC1", "QLD1", "SA1")
REQUIRED_COLUMNS: Final = {
    "monthly_price_renewables_summary.csv": {
        "month",
        "region",
        "hours",
        "mean_price_aud_mwh",
        "negative_price_hour_share",
        "mean_renewable_share_ws",
    },
    "task8_headline_results.csv": {
        "section",
        "outcome_or_contrast",
        "estimate",
        "std_error",
        "nobs",
        "week_clusters",
    },
    "task9_heterogeneity_holm.csv": {
        "family",
        "outcome",
        "contrast",
        "estimate",
        "ci_lower",
        "ci_upper",
        "p_value_holm",
    },
    "task9_main_robustness_summary.csv": {
        "family",
        "outcome",
        "parameter",
        "coefficient",
        "ci_lower",
        "ci_upper",
    },
}

ROBUSTNESS_LABELS: Final = {
    "exposure_headline_p999": "Headline capped share",
    "exposure_cap_at_one": "Cap share at 100%",
    "exposure_all_unknown_as_renewable_upper_bound": "Unknown output as renewable",
    "sample_include_tas1": "Include TAS1",
    "sample_post_5ms": "Post-5MS sample",
    "aggressive_region_date_fe": "Region × date fixed effects",
    "inference_driscoll_kraay": "Driscoll–Kraay inference",
}


def _read_table(root: Path, filename: str) -> pd.DataFrame:
    path = root / "outputs" / "tables" / filename
    if not path.exists():
        raise FileNotFoundError(f"Dashboard source table is missing: {path}")
    frame = pd.read_csv(path)
    missing = REQUIRED_COLUMNS[filename].difference(frame.columns)
    if missing:
        raise ValueError(f"Dashboard source table {filename} is missing columns: {sorted(missing)}")
    return frame


def _number(value: float, digits: int = 6) -> float:
    """Return a JSON-safe, deliberately rounded numeric value."""
    return round(float(value), digits)


def _headline_record(frame: pd.DataFrame, outcome: str, *, multiplier: float = 1.0) -> dict[str, float | str]:
    result = frame.loc[
        frame["section"].eq("headline_fixed_effects")
        & frame["outcome_or_contrast"].eq(outcome)
    ]
    if len(result) != 1:
        raise ValueError(f"Expected exactly one headline result for {outcome!r}; found {len(result)}")
    row = result.iloc[0]
    return {
        "estimate": _number(row["estimate"] * multiplier),
        "stdError": _number(row["std_error"] * multiplier),
        "nobs": int(row["nobs"]),
        "weekClusters": int(row["week_clusters"]),
    }


def build_dashboard_payload(root: Path) -> dict[str, object]:
    """Return the frozen public dashboard payload for a project root."""
    monthly = _read_table(root, "monthly_price_renewables_summary.csv")
    headline = _read_table(root, "task8_headline_results.csv")
    heterogeneity = _read_table(root, "task9_heterogeneity_holm.csv")
    robustness = _read_table(root, "task9_main_robustness_summary.csv")

    monthly = monthly.loc[monthly["region"].isin(PRIMARY_REGIONS)].copy()
    monthly = monthly.sort_values(["region", "month"])
    trend_columns = [
        "month",
        "region",
        "hours",
        "mean_price_aud_mwh",
        "negative_price_hour_share",
        "mean_renewable_share_ws",
    ]
    trends = [
        {
            "month": str(row.month),
            "region": str(row.region),
            "hours": int(row.hours),
            "meanPriceAudMwh": _number(row.mean_price_aud_mwh),
            "negativePriceHourShare": _number(row.negative_price_hour_share),
            "renewableShareWs": _number(row.mean_renewable_share_ws),
        }
        for row in monthly[trend_columns].itertuples(index=False)
    ]

    regional = heterogeneity.loc[
        heterogeneity["family"].eq("heterogeneity_region")
        & heterogeneity["outcome"].eq("price_asinh")
        & heterogeneity["contrast"].isin(PRIMARY_REGIONS)
    ].copy()
    regional = regional.set_index("contrast").reindex(PRIMARY_REGIONS).reset_index()
    if regional["estimate"].isna().any():
        missing = regional.loc[regional["estimate"].isna(), "contrast"].tolist()
        raise ValueError(f"Missing regional price heterogeneity results: {missing}")
    regional_effects = [
        {
            "region": str(row.contrast),
            "estimate": _number(row.estimate),
            "ciLower": _number(row.ci_lower),
            "ciUpper": _number(row.ci_upper),
            "pValueHolm": _number(row.p_value_holm, 12),
        }
        for row in regional.itertuples(index=False)
    ]

    selected_robustness = robustness.loc[
        robustness["outcome"].eq("price_asinh")
        & robustness["family"].isin(ROBUSTNESS_LABELS)
        & ~(
            robustness["family"].eq("exposure_all_unknown_as_renewable_upper_bound")
            & ~robustness["parameter"].str.contains("unknown_upper", na=False)
        )
    ].copy()
    selected_robustness = selected_robustness.drop_duplicates("family").set_index("family")
    missing_families = set(ROBUSTNESS_LABELS).difference(selected_robustness.index)
    if missing_families:
        raise ValueError(f"Missing price robustness results: {sorted(missing_families)}")
    robustness_effects = [
        {
            "label": ROBUSTNESS_LABELS[family],
            "family": family,
            "estimate": _number(selected_robustness.loc[family, "coefficient"]),
            "ciLower": _number(selected_robustness.loc[family, "ci_lower"]),
            "ciUpper": _number(selected_robustness.loc[family, "ci_upper"]),
        }
        for family in ROBUSTNESS_LABELS
    ]

    price_level = _headline_record(headline, "Continuous price (AUD/MWh level)")
    negative_price = _headline_record(
        headline,
        "Any negative price (LPM, probability points)",
        multiplier=100,
    )
    volatility = _headline_record(headline, "Intrahour volatility (AUD/MWh SD level)")

    return {
        "meta": {
            "title": "Renewable Penetration, Wholesale Electricity Prices and Volatility in Australia's NEM",
            "sample": "1 July 2019 – 30 June 2025",
            "timeBasis": "Hourly observations aggregated from five-minute dispatch data; NEM market time (fixed AEST, UTC+10)",
            "primaryRegions": list(PRIMARY_REGIONS),
            "claimBoundary": "All displayed estimates are conditional associations, not causal effects.",
            "dataBoundary": "Public dashboard payload derived only from compact, tracked final result tables. It contains no raw AEMO archives, hourly panel, DUIDs, or intermediate data.",
            "generatedBy": "src.build_dashboard_data",
        },
        "headline": {
            "priceLevel": price_level,
            "negativePriceProbabilityPp": negative_price,
            "intrahourVolatility": volatility,
        },
        "trends": trends,
        "regionalHeterogeneity": regional_effects,
        "priceRobustness": robustness_effects,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--script-output", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output or root / "site" / "data" / "dashboard.json"
    output = output.resolve()
    script_output = args.script_output or root / "site" / "data" / "dashboard.js"
    script_output = script_output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    script_output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_dashboard_payload(root)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    script_output.write_text(
        "window.__AU_NEM_DASHBOARD_DATA__ = "
        + json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    print(f"wrote {output.relative_to(root) if output.is_relative_to(root) else output}")
    print(f"wrote {script_output.relative_to(root) if script_output.is_relative_to(root) else script_output}")
    print(f"trends={len(payload['trends'])}; regions={len(payload['regionalHeterogeneity'])}; robustness={len(payload['priceRobustness'])}")


if __name__ == "__main__":
    main()
