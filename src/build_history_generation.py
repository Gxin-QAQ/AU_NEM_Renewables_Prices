"""Build the full historical demand-and-generation panel one month at a time.

``DISPATCHREGIONSUM`` supplies regional operational demand and
``DISPATCH_UNIT_SCADA`` supplies unit output.  The latter is several million
records per month, so this module reads it in CSV chunks, maps each chunk to
the effective-dated DUID crosswalk, and immediately aggregates it to
region--five-minute observations.  It intentionally does *not* invent a
price series: historical RRP is joined later from the separate
``DISPATCHPRICE`` source table.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from src.panel_builder import (
    EXPECTED_REGIONS,
    FUEL_OUTPUT_COLUMNS,
    PANEL_MEAN_COLUMNS,
    add_local_time_fields,
    load_crosswalk,
    load_project_config,
)


SCADA_VALUE_COLUMNS = [
    "battery_discharge_mw",
    "battery_charge_mw",
    "load_scada_mw",
    "unmapped_scada_mw",
    "mapped_nonstorage_generation_mw",
    *FUEL_OUTPUT_COLUMNS.values(),
]


def month_range(start: str, end: str) -> list[str]:
    """Return inclusive YYYY-MM months without depending on network state."""
    first = datetime.strptime(start, "%Y-%m")
    last = datetime.strptime(end, "%Y-%m")
    if first > last:
        raise ValueError("start must not be after end")
    result: list[str] = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        result.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def archive_header(path: Path, table: str) -> dict[str, int]:
    """Locate an MMSDM ``I`` row and return its field-to-position mapping."""
    with ZipFile(path) as archive:
        members = [item for item in archive.infolist() if item.filename.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"{path.name}: expected exactly one CSV member")
        with archive.open(members[0]) as raw:
            text = (line.decode("utf-8-sig") for line in raw)
            for row in csv.reader(text):
                if row and row[0] == "I" and len(row) >= 4 and row[2] == table:
                    return {field: index for index, field in enumerate(row)}
    raise ValueError(f"{path.name}: table {table} header not found")


def _read_columns(
    path: Path,
    positions: dict[str, int],
    fields: list[str],
    chunksize: int,
) -> object:
    """Yield selected CSV fields from a single-member monthly archive."""
    requested = [positions[field] for field in fields]
    width = max(requested) + 1
    reader = pd.read_csv(
        path,
        compression="zip",
        header=None,
        names=list(range(width)),
        # Some historical ``C`` metadata rows carry one more field than the
        # following SCADA table.  Reading the complete table width first
        # avoids a pandas C-parser edge case when ``usecols`` omits column 0.
        # The largest non-SCADA table is only ~43k rows/month, and SCADA has
        # just seven relevant physical columns, so this remains bounded.
        usecols=list(range(width)),
        dtype=str,
        chunksize=chunksize,
        low_memory=False,
    )
    for chunk in reader:
        selected = chunk.loc[:, requested].copy()
        selected.columns = fields
        yield selected


def _market_timestamp(values: pd.Series) -> pd.Series:
    """Convert AEMO settlement labels to canonical five-minute interval starts."""
    return (
        pd.to_datetime(values, format="%Y/%m/%d %H:%M:%S")
        .dt.tz_localize("Australia/Brisbane")
        - pd.offsets.Minute(5)
    )


def load_regional_demand(path: Path) -> pd.DataFrame:
    """Read one monthly regional-demand archive and retain the dispatch run."""
    positions = archive_header(path, "REGIONSUM")
    required = ["SETTLEMENTDATE", "RUNNO", "REGIONID", "INTERVENTION", "TOTALDEMAND"]
    missing = set(required) - set(positions)
    if missing:
        raise ValueError(f"{path.name}: REGIONSUM lacks {sorted(missing)}")
    pieces: list[pd.DataFrame] = []
    for chunk in _read_columns(path, positions, required, 100_000):
        rows = chunk.loc[
            chunk["SETTLEMENTDATE"].str.match(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}$", na=False)
            & chunk["RUNNO"].eq("1")
            & chunk["INTERVENTION"].eq("0")
        ].copy()
        if rows.empty:
            continue
        rows["timestamp"] = _market_timestamp(rows["SETTLEMENTDATE"])
        rows["demand_mw"] = pd.to_numeric(rows["TOTALDEMAND"], errors="raise")
        pieces.append(rows[["timestamp", "REGIONID", "demand_mw"]].rename(columns={"REGIONID": "region"}))
    demand = pd.concat(pieces, ignore_index=True)
    demand = demand.loc[demand["region"].isin(EXPECTED_REGIONS)].copy()
    if demand.duplicated(["timestamp", "region"]).any():
        raise ValueError(f"{path.name}: duplicate region--time demand records")
    if set(demand["region"]) != EXPECTED_REGIONS:
        raise ValueError(f"{path.name}: expected five NEM regions")
    return demand.sort_values(["timestamp", "region"], ignore_index=True)


def active_crosswalk(crosswalk: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Restrict an effective-dated crosswalk to records that can occur in a month."""
    active = crosswalk.loc[
        (crosswalk["valid_from_aest"] < end) & (crosswalk["valid_to_aest"] > start),
        ["duid", "valid_from_aest", "valid_to_aest", "region", "fuel_category"],
    ].copy()
    if active.empty:
        raise ValueError("No crosswalk records overlap the requested month")
    return active


def aggregate_monthly_scada(
    path: Path, crosswalk: pd.DataFrame, month_start: pd.Timestamp, month_end: pd.Timestamp
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Map and aggregate one SCADA archive, retaining explicit unmatched coverage."""
    positions = archive_header(path, "UNIT_SCADA")
    required = ["SETTLEMENTDATE", "DUID", "SCADAVALUE"]
    missing = set(required) - set(positions)
    if missing:
        raise ValueError(f"{path.name}: UNIT_SCADA lacks {sorted(missing)}")
    active = active_crosswalk(crosswalk, month_start, month_end)
    results: list[pd.DataFrame] = []
    observed_positive_mwh = 0.0
    unresolved_positive_mwh = 0.0
    unknown_positive_mwh = 0.0
    source_rows = 0
    resolved_rows = 0
    for chunk in _read_columns(path, positions, required, 250_000):
        rows = chunk.loc[
            chunk["SETTLEMENTDATE"].str.match(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}$", na=False)
        ].copy()
        if rows.empty:
            continue
        source_rows += len(rows)
        rows["timestamp"] = _market_timestamp(rows["SETTLEMENTDATE"])
        rows["scada_mw"] = pd.to_numeric(rows["SCADAVALUE"], errors="raise")
        rows["_record_id"] = np.arange(len(rows))
        mapped = rows.merge(active, left_on="DUID", right_on="duid", how="left", sort=False)
        mapped = mapped.loc[
            (mapped["timestamp"] >= mapped["valid_from_aest"])
            & (mapped["timestamp"] < mapped["valid_to_aest"])
        ].copy()
        matches = mapped.groupby("_record_id", observed=True).size()
        if (matches > 1).any():
            raise ValueError(f"{path.name}: ambiguous effective-date SCADA mappings")
        resolved_rows += len(matches)
        positive_all = rows["scada_mw"].clip(lower=0.0)
        observed_positive_mwh += float(positive_all.sum() / 12.0)
        unresolved_ids = pd.Index(rows["_record_id"]).difference(matches.index)
        unresolved_positive_mwh += float(
            rows.loc[rows["_record_id"].isin(unresolved_ids), "scada_mw"].clip(lower=0.0).sum() / 12.0
        )
        if mapped.empty:
            continue
        positive = mapped["scada_mw"].clip(lower=0.0)
        negative = (-mapped["scada_mw"]).clip(lower=0.0)
        unknown_positive_mwh += float(positive.loc[mapped["fuel_category"].eq("UNKNOWN")].sum() / 12.0)
        mapped["battery_discharge_mw"] = np.where(mapped["fuel_category"].eq("BATTERY"), positive, 0.0)
        mapped["battery_charge_mw"] = np.where(mapped["fuel_category"].eq("BATTERY"), negative, 0.0)
        mapped["load_scada_mw"] = np.where(mapped["fuel_category"].eq("LOAD"), mapped["scada_mw"].abs(), 0.0)
        mapped["unmapped_scada_mw"] = np.where(mapped["fuel_category"].eq("UNKNOWN"), positive, 0.0)
        mapped["mapped_nonstorage_generation_mw"] = np.where(
            ~mapped["fuel_category"].isin({"BATTERY", "LOAD", "UNKNOWN"}), positive, 0.0
        )
        for category, column in FUEL_OUTPUT_COLUMNS.items():
            mapped[column] = np.where(mapped["fuel_category"].eq(category), positive, 0.0)
        results.append(
            mapped.groupby(["timestamp", "region"], observed=True, as_index=False)[SCADA_VALUE_COLUMNS].sum()
        )
    if source_rows == 0:
        raise ValueError(f"{path.name}: no SCADA data rows")
    aggregate = pd.concat(results, ignore_index=True).groupby(
        ["timestamp", "region"], observed=True, as_index=False
    )[SCADA_VALUE_COLUMNS].sum()
    audit = {
        "scada_source_rows": float(source_rows),
        "scada_resolved_rows": float(resolved_rows),
        "scada_resolved_row_share": float(resolved_rows / source_rows),
        "scada_positive_energy_gwh": observed_positive_mwh / 1000.0,
        "scada_unresolved_positive_energy_gwh": unresolved_positive_mwh / 1000.0,
        "scada_unknown_positive_energy_gwh": unknown_positive_mwh / 1000.0,
    }
    return aggregate, audit


def aggregate_generation_demand_hourly(frame: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """Aggregate a price-free five-minute panel while preserving valid outcomes."""
    working = frame.copy()
    working["hour_timestamp"] = working["timestamp"].dt.floor("h")
    metrics = [column for column in PANEL_MEAN_COLUMNS if column in working]
    hourly = working.groupby(["hour_timestamp", "region"], observed=True).agg(
        **{column: (column, "mean") for column in metrics},
        n_5min_intervals=("timestamp", "size"),
    ).reset_index().rename(columns={"hour_timestamp": "timestamp"})
    if not (hourly["n_5min_intervals"] == 12).all():
        raise ValueError("Historical build produced incomplete hours")
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
    return add_local_time_fields(hourly, config).sort_values(["timestamp", "region"], ignore_index=True)


def build_month(root: Path, period: str, crosswalk: pd.DataFrame, config: dict[str, object]) -> dict[str, float | int | str]:
    """Build one monthly five-minute partition and its hourly counterpart."""
    region_path = root / "data/raw/aemo_history/region" / f"{period}.zip"
    scada_path = root / "data/raw/aemo_history/scada" / f"{period}.zip"
    if not region_path.exists() or not scada_path.exists():
        raise FileNotFoundError(f"Missing verified raw archives for {period}")
    demand = load_regional_demand(region_path)
    start = demand["timestamp"].min()
    end = demand["timestamp"].max() + pd.offsets.Minute(5)
    scada, audit = aggregate_monthly_scada(scada_path, crosswalk, start, end)
    panel = demand.merge(scada, on=["timestamp", "region"], how="left", validate="one_to_one")
    panel[SCADA_VALUE_COLUMNS] = panel[SCADA_VALUE_COLUMNS].fillna(0.0)
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
    panel = add_local_time_fields(panel, config).sort_values(["timestamp", "region"], ignore_index=True)
    if panel.duplicated(["timestamp", "region"]).any() or len(panel) != 5 * panel["timestamp"].nunique():
        raise ValueError(f"{period}: incomplete or duplicate regional panel")
    output_5min = root / "data/interim/history_generation_demand_5min"
    output_hour = root / "data/interim/history_generation_demand_hour"
    output_5min.mkdir(parents=True, exist_ok=True)
    output_hour.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(output_5min / f"{period}.parquet", index=False)
    hourly = aggregate_generation_demand_hourly(panel, config)
    hourly.to_parquet(output_hour / f"{period}.parquet", index=False)
    return {
        "period": period,
        "five_minute_rows": int(len(panel)),
        "hourly_rows": int(len(hourly)),
        "nonpositive_demand_intervals": int(panel["nonpositive_demand"].sum()),
        **audit,
    }


def build_history(root: Path, start: str, end: str, resume: bool) -> list[dict[str, float | int | str]]:
    """Build reproducible monthly partitions and one compact full hourly file."""
    config = load_project_config(root / "config/project.yml")
    crosswalk = load_crosswalk(root / "data/interim/duid_crosswalk.csv")
    records: list[dict[str, float | int | str]] = []
    for period in month_range(start, end):
        partition = root / "data/interim/history_generation_demand_hour" / f"{period}.parquet"
        if resume and partition.exists():
            records.append({"period": period, "status": "existing"})
            continue
        record = build_month(root, period, crosswalk, config)
        record["status"] = "built"
        records.append(record)
        print(json.dumps(record), flush=True)
    parts = sorted((root / "data/interim/history_generation_demand_hour").glob("*.parquet"))
    expected = set(month_range(start, end))
    selected = [path for path in parts if path.stem in expected]
    if len(selected) != len(expected):
        raise ValueError("Not all requested hourly partitions are available")
    hourly = pd.concat([pd.read_parquet(path) for path in selected], ignore_index=True)
    hourly = hourly.sort_values(["timestamp", "region"], ignore_index=True)
    hourly.to_parquet(root / "data/processed/nem_region_hour_generation_demand.parquet", index=False)
    (root / "data/interim/history_generation_demand_build_summary.json").write_text(
        json.dumps({"start": start, "end": end, "months": records, "price_status": "not_joined_requires_DISPATCHPRICE"}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2019-07")
    parser.add_argument("--end", default="2025-06")
    parser.add_argument("--resume", action="store_true", help="Retain completed monthly partitions")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    build_history(args.root.resolve(), args.start, args.end, args.resume)


if __name__ == "__main__":
    main()
