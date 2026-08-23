"""Build validated five-minute and hourly NEM pilot panels.

The raw AEMO settlement label is an interval-end timestamp. Analysis panels
use the corresponding five-minute interval start in fixed NEM market time;
state-local clocks are derived only as explicit heterogeneity fields.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.aemo_dispatch import interval_start_from_settlement, parse_region_archive, parse_scada_archive
from src.duid_mapping import PILOT_DATES


EXPECTED_REGIONS = {"NSW1", "VIC1", "QLD1", "SA1", "TAS1"}
FIVE_MINUTES = timedelta(minutes=5)
PILOT_WINDOW_GAP = timedelta(days=17, minutes=5)
REGION_TIMEZONES = {
    "NSW1": "Australia/Sydney",
    "VIC1": "Australia/Sydney",
    "QLD1": "Australia/Brisbane",
    "SA1": "Australia/Adelaide",
    "TAS1": "Australia/Hobart",
}
FUEL_OUTPUT_COLUMNS = {
    "WIND": "wind_mw",
    "SOLAR_UTILITY": "solar_utility_mw",
    "HYDRO": "hydro_mw",
    "COAL_BLACK": "coal_black_mw",
    "COAL_BROWN": "coal_brown_mw",
    "GAS": "gas_mw",
    "LIQUID_FUEL": "liquid_fuel_mw",
    "BIOENERGY": "bioenergy_mw",
    "OTHER": "other_mw",
}
PANEL_MEAN_COLUMNS = [
    "demand_mw",
    "wind_mw",
    "solar_utility_mw",
    "hydro_mw",
    "coal_black_mw",
    "coal_brown_mw",
    "gas_mw",
    "liquid_fuel_mw",
    "bioenergy_mw",
    "other_mw",
    "battery_discharge_mw",
    "battery_charge_mw",
    "load_scada_mw",
    "unmapped_scada_mw",
    "mapped_nonstorage_generation_mw",
]


def intended_paths(directory: Path, prefix: str) -> list[Path]:
    """Return exactly the 14 intended pilot files for one archive family."""
    paths = [path for path in sorted(directory.glob(f"{prefix}_*.zip")) if path.stem[-8:] in PILOT_DATES]
    if len(paths) != 14:
        raise ValueError(f"Expected 14 intended {prefix} pilot archives, found {len(paths)}")
    return paths


def load_project_config(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_crosswalk(path: Path) -> pd.DataFrame:
    """Load the effective-dated, source-explicit DUID crosswalk."""
    if not path.exists():
        raise FileNotFoundError(f"Crosswalk absent: run `python -m src.duid_mapping` first ({path})")
    frame = pd.read_csv(path)
    required = {"duid", "valid_from_aest", "valid_to_aest", "region", "fuel_category"}
    missing = required - set(frame)
    if missing:
        raise ValueError(f"Crosswalk missing columns: {sorted(missing)}")
    # MMSDM uses 2999-12-31 as an open-ended sentinel, outside pandas' ns range.
    # The project sample ends in 2025, so pandas' maximum timestamp is a safe
    # operational replacement while the original string remains in the raw CSV.
    sentinel = frame["valid_to_aest"].str.startswith(("2999-", "9999-"), na=False)
    frame["valid_to_aest"] = frame["valid_to_aest"].where(
        ~sentinel, "2262-04-11T23:47:16+00:00"
    )
    frame["valid_from_aest"] = pd.to_datetime(
        frame["valid_from_aest"], utc=True, format="ISO8601"
    ).dt.tz_convert(
        "Australia/Brisbane"
    )
    frame["valid_to_aest"] = pd.to_datetime(
        frame["valid_to_aest"], utc=True, format="ISO8601"
    ).dt.tz_convert(
        "Australia/Brisbane"
    )
    return frame


def _source_to_interval_start(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    source = pd.to_datetime(result["settlement_timestamp"], utc=True).dt.tz_convert("Australia/Brisbane")
    result["settlement_timestamp"] = source
    result["timestamp"] = source - FIVE_MINUTES
    return result


def parse_regional_archives(paths: Iterable[Path]) -> pd.DataFrame:
    records = [record for path in paths for record in parse_region_archive(path)]
    frame = _source_to_interval_start(pd.DataFrame(records))
    frame = frame[["timestamp", "settlement_timestamp", "region", "rrp_aud_mwh", "demand_mw"]]
    if frame.duplicated(["timestamp", "region"]).any():
        raise ValueError("Regional source archives contain duplicate interval-region records")
    return frame.sort_values(["timestamp", "region"], ignore_index=True)


def _join_scada_crosswalk(scada: pd.DataFrame, crosswalk: pd.DataFrame) -> pd.DataFrame:
    """Perform an effective-date join and fail on unresolvable or ambiguous rows."""
    scada = scada.copy()
    scada["_record_id"] = np.arange(len(scada))
    relevant = crosswalk.loc[
        (crosswalk["valid_from_aest"] <= scada["timestamp"].max())
        & (crosswalk["valid_to_aest"] > scada["timestamp"].min())
    ]
    merged = scada.merge(relevant, on="duid", how="left", validate="many_to_many")
    active = merged.loc[
        (merged["timestamp"] >= merged["valid_from_aest"])
        & (merged["timestamp"] < merged["valid_to_aest"])
    ].copy()
    matches = active.groupby("_record_id", observed=True).size()
    missing = len(scada) - len(matches)
    ambiguous = int((matches != 1).sum())
    if missing or ambiguous:
        raise ValueError(
            "Effective-dated crosswalk join failed: "
            f"{missing} missing and {ambiguous} ambiguous SCADA records"
        )
    return active


def aggregate_scada_archives(paths: Iterable[Path], crosswalk: pd.DataFrame) -> pd.DataFrame:
    """Map daily SCADA to regional fuel output without holding full raw SCADA in memory."""
    daily_results: list[pd.DataFrame] = []
    for path in paths:
        raw = pd.DataFrame(parse_scada_archive(path))
        raw = _source_to_interval_start(raw)
        mapped = _join_scada_crosswalk(raw, crosswalk)
        positive = mapped["scada_mw"].clip(lower=0.0)
        negative = (-mapped["scada_mw"]).clip(lower=0.0)
        mapped["battery_discharge_mw"] = np.where(mapped["fuel_category"] == "BATTERY", positive, 0.0)
        mapped["battery_charge_mw"] = np.where(mapped["fuel_category"] == "BATTERY", negative, 0.0)
        mapped["load_scada_mw"] = np.where(mapped["fuel_category"] == "LOAD", mapped["scada_mw"].abs(), 0.0)
        mapped["unmapped_scada_mw"] = np.where(mapped["fuel_category"] == "UNKNOWN", positive, 0.0)
        mapped["mapped_nonstorage_generation_mw"] = np.where(
            ~mapped["fuel_category"].isin({"BATTERY", "LOAD", "UNKNOWN"}), positive, 0.0
        )
        for category, column in FUEL_OUTPUT_COLUMNS.items():
            mapped[column] = np.where(mapped["fuel_category"] == category, positive, 0.0)
        columns = [
            "battery_discharge_mw",
            "battery_charge_mw",
            "load_scada_mw",
            "unmapped_scada_mw",
            "mapped_nonstorage_generation_mw",
            *FUEL_OUTPUT_COLUMNS.values(),
        ]
        daily_results.append(
            mapped.groupby(["timestamp", "region"], observed=True, as_index=False)[columns].sum()
        )
    output = pd.concat(daily_results, ignore_index=True)
    if output.duplicated(["timestamp", "region"]).any():
        raise ValueError("SCADA aggregation produced duplicate interval-region observations")
    return output.sort_values(["timestamp", "region"], ignore_index=True)


def add_local_time_fields(frame: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """Derive region-specific local-clock fields without altering canonical AEST time."""
    result = frame.copy()
    result["local_timezone"] = result["region"].map(REGION_TIMEZONES)
    if result["local_timezone"].isna().any():
        raise ValueError("Cannot derive local time for an unknown NEM region")
    result["local_timestamp"] = ""
    result["local_date"] = ""
    result["local_hour"] = 0
    result["local_weekday"] = 0
    result["local_utc_offset_hours"] = 0.0
    for timezone_name, index in result.groupby("local_timezone", observed=True).groups.items():
        local = result.loc[index, "timestamp"].dt.tz_convert(timezone_name)
        result.loc[index, "local_timestamp"] = local.map(lambda value: value.isoformat())
        result.loc[index, "local_date"] = local.dt.strftime("%Y-%m-%d")
        result.loc[index, "local_hour"] = local.dt.hour.to_numpy()
        result.loc[index, "local_weekday"] = local.dt.weekday.to_numpy()
        result.loc[index, "local_utc_offset_hours"] = local.map(
            lambda value: value.utcoffset().total_seconds() / 3600.0
        ).to_numpy()
    definitions = config["definitions"]  # validated project configuration
    peak_hours = set(definitions["peak_hours_local"])
    weekdays_only = bool(definitions["peak_weekdays_only"])
    result["peak"] = result["local_hour"].isin(peak_hours)
    if weekdays_only:
        result["peak"] &= result["local_weekday"] < 5
    month = pd.to_datetime(result["local_date"]).dt.month
    result["season"] = np.select(
        [month.isin([12, 1, 2]), month.isin([3, 4, 5]), month.isin([6, 7, 8])],
        ["DJF", "MAM", "JJA"],
        default="SON",
    )
    return result


def validate_5min_panel(frame: pd.DataFrame) -> None:
    required = {
        "timestamp",
        "settlement_timestamp",
        "region",
        "rrp_aud_mwh",
        "demand_mw",
        "wind_mw",
        "solar_utility_mw",
        "renewable_share_ws",
    }
    missing = required - set(frame)
    if missing:
        raise ValueError(f"Five-minute panel missing columns: {sorted(missing)}")
    if frame.duplicated(["timestamp", "region"]).any():
        raise ValueError("Five-minute panel has duplicate region-time keys")
    if set(frame["region"]) != EXPECTED_REGIONS:
        raise ValueError("Five-minute panel does not contain exactly the five expected NEM regions")
    if frame[["rrp_aud_mwh", "demand_mw"]].isna().any().any():
        raise ValueError("Five-minute panel has missing price or demand values")
    for region, group in frame.groupby("region", observed=True):
        deltas = group.sort_values("timestamp")["timestamp"].diff().dropna()
        allowed = deltas.isin([FIVE_MINUTES, PILOT_WINDOW_GAP])
        if not allowed.all() or int((deltas == PILOT_WINDOW_GAP).sum()) != 1:
            raise ValueError(f"Five-minute continuity failure for {region}")
    if not (frame["settlement_timestamp"] - frame["timestamp"] == FIVE_MINUTES).all():
        raise ValueError("Settlement timestamps must be exactly five minutes after interval starts")
    if (frame["renewable_share_ws"].dropna() < 0).any() or (
        frame["renewable_share_broad"].dropna() < 0
    ).any():
        raise ValueError("Renewable shares cannot be negative")


def aggregate_hourly(frame: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """Convert an exactly five-minute panel to hourly means and price outcomes."""
    working = frame.copy()
    working["hour_timestamp"] = working["timestamp"].dt.floor("h")
    working["negative_price_5min"] = working["rrp_aud_mwh"] < 0
    working["negative_price_below_minus_50_5min"] = working["rrp_aud_mwh"] < -50
    working["negative_price_below_minus_100_5min"] = working["rrp_aud_mwh"] < -100
    aggregation = {column: "mean" for column in PANEL_MEAN_COLUMNS if column in working}
    aggregation.update(
        {
            "rrp_aud_mwh": "mean",
            "negative_price_5min": ["mean", "max"],
            "negative_price_below_minus_50_5min": "max",
            "negative_price_below_minus_100_5min": "max",
            "timestamp": "size",
        }
    )
    hourly = working.groupby(["hour_timestamp", "region"], observed=True).agg(aggregation)
    hourly.columns = [
        "_".join(str(part) for part in column if part).rstrip("_")
        if isinstance(column, tuple)
        else column
        for column in hourly.columns
    ]
    hourly = hourly.reset_index().rename(
        columns={
            "hour_timestamp": "timestamp",
            "rrp_aud_mwh_mean": "rrp_aud_mwh",
            "negative_price_5min_mean": "negative_price_share_5min",
            "negative_price_5min_max": "negative_price_any",
            "negative_price_below_minus_50_5min_max": "negative_price_below_minus_50_any_5min",
            "negative_price_below_minus_100_5min_max": "negative_price_below_minus_100_any_5min",
            "timestamp_size": "n_5min_intervals",
        }
    )
    hourly = hourly.rename(
        columns={f"{column}_mean": column for column in PANEL_MEAN_COLUMNS if f"{column}_mean" in hourly}
    )
    dispersion = (
        working.groupby(["hour_timestamp", "region"], observed=True)["rrp_aud_mwh"]
        .std(ddof=1)
        .rename("intrahour_price_sd")
        .reset_index()
        .rename(columns={"hour_timestamp": "timestamp"})
    )
    hourly = hourly.merge(dispersion, on=["timestamp", "region"], validate="one_to_one")
    hourly["negative_price_any"] = hourly["negative_price_any"].astype(bool)
    hourly["negative_price_below_minus_50_any_5min"] = hourly["negative_price_below_minus_50_any_5min"].astype(bool)
    hourly["negative_price_below_minus_100_any_5min"] = hourly["negative_price_below_minus_100_any_5min"].astype(bool)
    hourly["renewable_share_ws"] = np.where(
        hourly["demand_mw"] > 0,
        (hourly["wind_mw"] + hourly["solar_utility_mw"]) / hourly["demand_mw"],
        np.nan,
    )
    hourly["renewable_share_broad"] = np.where(
        hourly["demand_mw"] > 0,
        (hourly["wind_mw"] + hourly["solar_utility_mw"] + hourly["hydro_mw"]) / hourly["demand_mw"],
        np.nan,
    )
    return add_local_time_fields(hourly, config)


def validate_hourly_panel(frame: pd.DataFrame) -> None:
    required = {
        "timestamp",
        "region",
        "rrp_aud_mwh",
        "demand_mw",
        "n_5min_intervals",
        "intrahour_price_sd",
        "negative_price_share_5min",
        "negative_price_any",
        "negative_price_below_minus_50_any_5min",
        "negative_price_below_minus_100_any_5min",
    }
    missing = required - set(frame)
    if missing:
        raise ValueError(f"Hourly panel missing columns: {sorted(missing)}")
    if frame.duplicated(["timestamp", "region"]).any():
        raise ValueError("Hourly panel has duplicate region-time keys")
    if not (frame["n_5min_intervals"] == 12).all():
        raise ValueError("Hourly panel contains incomplete five-minute hours")
    if not frame["negative_price_share_5min"].between(0, 1).all():
        raise ValueError("Negative-price share must lie in [0, 1]")


def build_pilot_panels(root: Path) -> dict[str, object]:
    """Build and write the Task 4 pilot panel artefacts."""
    config = load_project_config(root / "config/project.yml")
    crosswalk = load_crosswalk(root / "data/interim/duid_crosswalk.csv")
    regional = parse_regional_archives(intended_paths(root / "data/raw/aemo_pilot/dispatch", "PUBLIC_DISPATCH"))
    scada = aggregate_scada_archives(
        intended_paths(root / "data/raw/aemo_pilot/scada", "PUBLIC_DISPATCHSCADA"), crosswalk
    )
    panel = regional.merge(scada, on=["timestamp", "region"], how="left", validate="one_to_one")
    numeric_scada = [column for column in scada.columns if column not in {"timestamp", "region"}]
    if panel[numeric_scada].isna().any().any():
        raise ValueError("SCADA aggregation is missing one or more regional intervals")
    panel[numeric_scada] = panel[numeric_scada].fillna(0.0)
    panel["nonpositive_demand"] = panel["demand_mw"] <= 0
    panel["renewable_share_ws"] = np.where(
        panel["demand_mw"] > 0,
        (panel["wind_mw"] + panel["solar_utility_mw"]) / panel["demand_mw"],
        np.nan,
    )
    panel["renewable_share_broad"] = np.where(
        panel["demand_mw"] > 0,
        (panel["wind_mw"] + panel["solar_utility_mw"] + panel["hydro_mw"]) / panel["demand_mw"],
        np.nan,
    )
    panel = add_local_time_fields(panel, config)
    panel = panel.sort_values(["timestamp", "region"], ignore_index=True)
    validate_5min_panel(panel)
    hourly = aggregate_hourly(panel, config).sort_values(["timestamp", "region"], ignore_index=True)
    validate_hourly_panel(hourly)

    processed = root / "data/processed"
    processed.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(processed / "nem_region_5min_pilot.parquet", index=False)
    hourly.to_parquet(processed / "nem_region_hour_pilot.parquet", index=False)
    summary = {
        "five_minute_rows": int(len(panel)),
        "hourly_rows": int(len(hourly)),
        "five_minute_intervals_per_region": int(panel.groupby("region", observed=True)["timestamp"].nunique().iloc[0]),
        "hours_per_region": int(hourly.groupby("region", observed=True)["timestamp"].nunique().iloc[0]),
        "five_minute_duplicate_region_time_keys": int(panel.duplicated(["timestamp", "region"]).sum()),
        "hourly_incomplete_hours": int((hourly["n_5min_intervals"] != 12).sum()),
        "unmapped_positive_energy_gwh": float(panel["unmapped_scada_mw"].sum() / 12.0 / 1000.0),
        "nonpositive_demand_intervals": int(panel["nonpositive_demand"].sum()),
        "canonical_timezone": "Australia/Brisbane",
        "local_timezones": REGION_TIMEZONES,
    }
    (root / "data/interim/pilot_panel_build_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(build_pilot_panels(args.root.resolve()), indent=2))


if __name__ == "__main__":
    main()
