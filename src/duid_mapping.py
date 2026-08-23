"""Build and audit an effective-dated NEM DUID-to-fuel crosswalk.

Registration identity, region, dispatch type and effective dates come from
AEMO's official DUDETAILSUMMARY table. Fuel technology labels come from a
captured OpenElectricity facility export and are explicitly marked as a
secondary source. The two layers are never silently conflated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from zipfile import ZipFile

from src.aemo_dispatch import (
    NEM_TIMEZONE,
    interval_start_from_settlement,
    parse_aemo_csv_tables,
    parse_market_timestamp,
    parse_scada_archive,
)


AEMO_REGISTRATION_URL = (
    "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2025/"
    "MMSDM_2025_10/MMSDM_Historical_Data_SQLLoader/DATA/"
    "PUBLIC_ARCHIVE%23DUDETAILSUMMARY%23FILE01%23202510010000.zip"
)
OPENELECTRICITY_FACILITIES_URL = (
    "https://data.opennem.org.au/v4/facilities/au_facilities.json"
)
REGISTRATION_TABLE = ("PARTICIPANT_REGISTRATION", "DUDETAILSUMMARY", "7")
PILOT_DATES = {
    *(f"202509{day:02d}" for day in range(8, 15)),
    *(f"202510{day:02d}" for day in range(2, 9)),
}
PILOT_START = datetime(2025, 9, 8, tzinfo=NEM_TIMEZONE)
# AEMO's archive labelled 8 October ends at the 00:00 interval on 9 October.
PILOT_END_EXCLUSIVE = datetime(2025, 10, 9, 0, 5, tzinfo=NEM_TIMEZONE)
FIVE_MINUTE_HOURS = 5.0 / 60.0

FUELTECH_MAP = {
    "wind": "WIND",
    "solar_utility": "SOLAR_UTILITY",
    "hydro": "HYDRO",
    "battery": "BATTERY",
    "battery_charging": "BATTERY",
    "battery_discharging": "BATTERY",
    "coal_black": "COAL_BLACK",
    "coal_brown": "COAL_BROWN",
    "distillate": "LIQUID_FUEL",
    "bioenergy_biogas": "BIOENERGY",
    "bioenergy_biomass": "BIOENERGY",
    "pumps": "LOAD",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_capture_timestamp(path: Path) -> str:
    """Use the immutable input's mtime as a stable local capture timestamp."""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def download_immutable(url: str, destination: Path, force: bool = False) -> None:
    """Download one reference input atomically without silent replacement."""
    if destination.exists() and not force:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = Request(url, headers={"User-Agent": "AU-NEM-research/1.0"})
    with urlopen(request, timeout=90) as response, temporary.open("wb") as handle:
        while chunk := response.read(1024 * 1024):
            handle.write(chunk)
    os.replace(temporary, destination)


def parse_registration_archive(path: Path) -> list[dict[str, str]]:
    """Parse the official AEMO DUDETAILSUMMARY table from one flat ZIP."""
    with ZipFile(path) as archive:
        csv_members = [item for item in archive.infolist() if item.filename.lower().endswith(".csv")]
        if len(csv_members) != 1:
            raise ValueError(f"Expected one CSV in {path}, found {len(csv_members)}")
        tables = parse_aemo_csv_tables(archive.read(csv_members[0]))
    rows = tables.get(REGISTRATION_TABLE)
    if rows is None:
        available = sorted(".".join(part for part in key if part) for key in tables)
        raise ValueError(f"DUDETAILSUMMARY table absent; available tables: {available}")
    required = {
        "DUID",
        "START_DATE",
        "END_DATE",
        "DISPATCHTYPE",
        "REGIONID",
        "STATIONID",
        "PARTICIPANTID",
        "SCHEDULE_TYPE",
    }
    if rows and required - set(rows[0]):
        raise ValueError(f"DUDETAILSUMMARY missing fields: {sorted(required - set(rows[0]))}")
    return rows


def parse_openelectricity_facilities(path: Path) -> dict[str, dict[str, Any]]:
    """Return unique NEM unit metadata from a captured facility export."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    facilities = payload.get("data")
    if not isinstance(facilities, list):
        raise ValueError("OpenElectricity export has no list-valued 'data' field")
    units: dict[str, dict[str, Any]] = {}
    for facility in facilities:
        if facility.get("network_id") != "NEM":
            continue
        for unit in facility.get("units", []):
            duid = unit.get("code")
            if not duid:
                continue
            record = {
                "duid": duid,
                "fueltech_id": unit.get("fueltech_id"),
                "dispatch_type": unit.get("dispatch_type"),
                "region": facility.get("network_region"),
                "facility_code": facility.get("code"),
                "facility_name": facility.get("name"),
                "status_id": unit.get("status_id"),
                "commencement_date": unit.get("commencement_date"),
                "deregistered": unit.get("deregistered"),
            }
            if duid in units and units[duid] != record:
                raise ValueError(f"Conflicting OpenElectricity unit records for {duid}")
            units[duid] = record
    return units


def normalise_fueltech(fueltech_id: str | None) -> str:
    """Collapse detailed OpenElectricity fuel technologies to project classes."""
    if not fueltech_id:
        return "UNKNOWN"
    if fueltech_id.startswith("gas_"):
        return "GAS"
    return FUELTECH_MAP.get(fueltech_id, "OTHER")


def parse_effective_timestamp(value: str) -> datetime:
    """Parse an MMS effective timestamp in fixed NEM market time."""
    return parse_market_timestamp(value)


def registration_index(
    rows: Iterable[dict[str, str]],
) -> dict[str, list[tuple[datetime, datetime, dict[str, str]]]]:
    """Index official records by DUID, validating non-overlapping intervals."""
    result: dict[str, list[tuple[datetime, datetime, dict[str, str]]]] = defaultdict(list)
    for row in rows:
        start = parse_effective_timestamp(row["START_DATE"])
        end = parse_effective_timestamp(row["END_DATE"])
        if end <= start:
            raise ValueError(f"Invalid effective interval for {row['DUID']}: {start} to {end}")
        result[row["DUID"]].append((start, end, row))
    for duid, intervals in result.items():
        intervals.sort(key=lambda item: item[0])
        for previous, current in zip(intervals, intervals[1:]):
            if current[0] < previous[1]:
                raise ValueError(f"Overlapping DUDETAILSUMMARY intervals for {duid}")
    return dict(result)


def resolve_registration(
    index: dict[str, list[tuple[datetime, datetime, dict[str, str]]]],
    duid: str,
    timestamp: datetime,
) -> dict[str, str] | None:
    """Resolve one DUID using the half-open interval [START_DATE, END_DATE)."""
    for start, end, row in index.get(duid, []):
        if start <= timestamp < end:
            return row
    return None


def classify_registration(
    registration: dict[str, str],
    secondary: dict[str, Any] | None,
    allow_bdu_pilot_rule: bool = False,
) -> tuple[str, str, str, str]:
    """Return category, detail, mapping method and review status."""
    if secondary is not None:
        detail = secondary.get("fueltech_id") or "unknown"
        return normalise_fueltech(detail), detail, "openelectricity_unit", "secondary_source"
    dispatch_type = registration["DISPATCHTYPE"].upper()
    if dispatch_type == "BIDIRECTIONAL" and allow_bdu_pilot_rule:
        return (
            "BATTERY",
            "scheduled_bidirectional_storage",
            "aemo_bdu_pilot_rule",
            "pilot_rule_reviewed",
        )
    if dispatch_type == "LOAD":
        return "LOAD", "registered_load", "aemo_dispatch_type", "official_rule"
    return "UNKNOWN", "unknown", "unmapped", "needs_review"


def crosswalk_rows(
    registration_rows: Iterable[dict[str, str]],
    secondary_units: dict[str, dict[str, Any]],
    registration_sha256: str,
    secondary_sha256: str,
    secondary_capture_utc: str,
) -> list[dict[str, str]]:
    """Create a source-explicit effective-dated crosswalk."""
    output: list[dict[str, str]] = []
    for row in registration_rows:
        secondary = secondary_units.get(row["DUID"])
        start = parse_effective_timestamp(row["START_DATE"])
        end = parse_effective_timestamp(row["END_DATE"])
        overlaps_pilot = start < PILOT_END_EXCLUSIVE and end > PILOT_START
        category, detail, method, review = classify_registration(
            row, secondary, allow_bdu_pilot_rule=overlaps_pilot
        )
        output.append(
            {
                "duid": row["DUID"],
                "valid_from_aest": parse_effective_timestamp(row["START_DATE"]).isoformat(),
                "valid_to_aest": parse_effective_timestamp(row["END_DATE"]).isoformat(),
                "region": row["REGIONID"],
                "station_id": row["STATIONID"],
                "participant_id": row["PARTICIPANTID"],
                "official_dispatch_type": row["DISPATCHTYPE"],
                "schedule_type": row["SCHEDULE_TYPE"],
                "fuel_category": category,
                "fuel_source_detail": detail,
                "facility_code": (secondary or {}).get("facility_code") or "",
                "facility_name": (secondary or {}).get("facility_name") or "",
                "mapping_method": method,
                "review_status": review,
                "registration_source": "AEMO DUDETAILSUMMARY",
                "registration_vintage": "MMSDM 2025-10 FILE01",
                "registration_sha256": registration_sha256,
                "fuel_source": "OpenElectricity facility export" if secondary else "",
                "fuel_source_capture_utc": secondary_capture_utc if secondary else "",
                "fuel_source_sha256": secondary_sha256 if secondary else "",
            }
        )
    return output


def classify_scada_flow(fuel_category: str, scada_mw: float) -> dict[str, float]:
    """Separate battery charge/discharge and prevent storage from becoming renewable."""
    positive = max(scada_mw, 0.0)
    if fuel_category == "BATTERY":
        return {
            "generation_mw": 0.0,
            "battery_discharge_mw": positive,
            "battery_charge_mw": max(-scada_mw, 0.0),
            "headline_renewable_mw": 0.0,
            "broad_renewable_mw": 0.0,
        }
    return {
        "generation_mw": positive,
        "battery_discharge_mw": 0.0,
        "battery_charge_mw": 0.0,
        "headline_renewable_mw": positive
        if fuel_category in {"WIND", "SOLAR_UTILITY"}
        else 0.0,
        "broad_renewable_mw": positive
        if fuel_category in {"WIND", "SOLAR_UTILITY", "HYDRO"}
        else 0.0,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def audit_pilot(
    scada_paths: Iterable[Path],
    registration_rows: list[dict[str, str]],
    secondary_units: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Audit registry and fuel coverage using energy-weighted pilot SCADA."""
    index = registration_index(registration_rows)
    totals: dict[str, float] = defaultdict(float)
    observations: dict[str, dict[str, Any]] = {}
    timestamps: set[datetime] = set()
    region_conflicts: set[str] = set()
    files = 0
    for path in scada_paths:
        files += 1
        for record in parse_scada_archive(path):
            timestamp = interval_start_from_settlement(record["settlement_timestamp"])
            duid = record["duid"]
            scada_mw = record["scada_mw"]
            timestamps.add(timestamp)
            positive_mwh = max(scada_mw, 0.0) * FIVE_MINUTE_HOURS
            absolute_mwh = abs(scada_mw) * FIVE_MINUTE_HOURS
            totals["positive_mwh"] += positive_mwh
            totals["absolute_mwh"] += absolute_mwh
            registration = resolve_registration(index, duid, timestamp)
            if registration is not None:
                totals["registry_positive_mwh"] += positive_mwh
                totals["registry_absolute_mwh"] += absolute_mwh
                category, detail, method, review = classify_registration(
                    registration,
                    secondary_units.get(duid),
                    allow_bdu_pilot_rule=PILOT_START <= timestamp < PILOT_END_EXCLUSIVE,
                )
                secondary_region = (secondary_units.get(duid) or {}).get("region")
                if secondary_region and secondary_region != registration["REGIONID"]:
                    region_conflicts.add(duid)
                if category != "UNKNOWN":
                    totals["mapped_positive_mwh"] += positive_mwh
                    totals["mapped_absolute_mwh"] += absolute_mwh
            else:
                category, detail, method, review = "UNKNOWN", "unknown", "unmapped", "needs_review"
            item = observations.setdefault(
                duid,
                {
                    "duid": duid,
                    "region": registration["REGIONID"] if registration else "",
                    "official_dispatch_type": registration["DISPATCHTYPE"] if registration else "",
                    "fuel_category": category,
                    "fuel_source_detail": detail,
                    "mapping_method": method,
                    "review_status": review,
                    "observations": 0,
                    "positive_mwh": 0.0,
                    "absolute_mwh": 0.0,
                },
            )
            item["observations"] += 1
            item["positive_mwh"] += positive_mwh
            item["absolute_mwh"] += absolute_mwh

    unresolved = [item for item in observations.values() if item["fuel_category"] == "UNKNOWN"]
    unresolved.sort(key=lambda item: item["absolute_mwh"], reverse=True)
    for item in unresolved:
        item["positive_mwh"] = round(item["positive_mwh"], 6)
        item["absolute_mwh"] = round(item["absolute_mwh"], 6)
    summary = {
        "scada_files": files,
        "five_minute_intervals": len(timestamps),
        "observed_duids": len(observations),
        "fuel_mapped_duids": sum(item["fuel_category"] != "UNKNOWN" for item in observations.values()),
        "unresolved_duids": len(unresolved),
        "unresolved_positive_gwh": round(
            sum(item["positive_mwh"] for item in unresolved) / 1000.0, 9
        ),
        "unresolved_absolute_gwh": round(
            sum(item["absolute_mwh"] for item in unresolved) / 1000.0, 9
        ),
        "observed_duids_by_mapping_method": dict(
            sorted(
                (
                    method,
                    sum(item["mapping_method"] == method for item in observations.values()),
                )
                for method in {item["mapping_method"] for item in observations.values()}
            )
        ),
        "observed_duids_by_fuel_category": dict(
            sorted(
                (
                    category,
                    sum(item["fuel_category"] == category for item in observations.values()),
                )
                for category in {item["fuel_category"] for item in observations.values()}
            )
        ),
        "secondary_region_conflict_duids": sorted(region_conflicts),
        "positive_generation_gwh": round(totals["positive_mwh"] / 1000.0, 6),
        "registry_positive_energy_coverage": totals["registry_positive_mwh"] / totals["positive_mwh"],
        "registry_absolute_energy_coverage": totals["registry_absolute_mwh"] / totals["absolute_mwh"],
        "fuel_positive_energy_coverage": totals["mapped_positive_mwh"] / totals["positive_mwh"],
        "fuel_absolute_energy_coverage": totals["mapped_absolute_mwh"] / totals["absolute_mwh"],
        "coverage_rule": "SCADAVALUE x 5/60; positive and absolute energy reported separately",
    }
    return summary, unresolved


def intended_pilot_scada_paths(directory: Path) -> list[Path]:
    paths = [
        path
        for path in sorted(directory.glob("PUBLIC_DISPATCHSCADA_*.zip"))
        if path.stem[-8:] in PILOT_DATES
    ]
    if len(paths) != 14:
        raise ValueError(f"Expected 14 intended pilot SCADA archives, found {len(paths)}")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    registration_path = root / "data/external/aemo_reference/DUDETAILSUMMARY_202510.zip"
    secondary_path = root / "data/external/openelectricity/au_facilities_20260823.json"
    download_immutable(AEMO_REGISTRATION_URL, registration_path, args.force_download)
    download_immutable(OPENELECTRICITY_FACILITIES_URL, secondary_path, args.force_download)

    registration_capture = file_capture_timestamp(registration_path)
    secondary_capture = file_capture_timestamp(secondary_path)
    registration_sha = sha256_file(registration_path)
    secondary_sha = sha256_file(secondary_path)
    registration_rows = parse_registration_archive(registration_path)
    secondary_units = parse_openelectricity_facilities(secondary_path)
    rows = crosswalk_rows(
        registration_rows,
        secondary_units,
        registration_sha,
        secondary_sha,
        secondary_capture,
    )
    write_csv(root / "data/interim/duid_crosswalk.csv", rows)
    manifest_rows = [
        {
            "source_name": "AEMO DUDETAILSUMMARY",
            "source_url": AEMO_REGISTRATION_URL,
            "downloaded_at_utc": registration_capture,
            "local_path": registration_path.relative_to(root).as_posix(),
            "sha256": registration_sha,
            "bytes": registration_path.stat().st_size,
            "source_vintage": "MMSDM 2025-10 FILE01",
        },
        {
            "source_name": "OpenElectricity facility export",
            "source_url": OPENELECTRICITY_FACILITIES_URL,
            "downloaded_at_utc": secondary_capture,
            "local_path": secondary_path.relative_to(root).as_posix(),
            "sha256": secondary_sha,
            "bytes": secondary_path.stat().st_size,
            "source_vintage": "captured 2026-08-23; dynamic export",
        },
    ]
    write_csv(root / "data/external/reference_manifest.csv", manifest_rows)

    paths = intended_pilot_scada_paths(root / "data/raw/aemo_pilot/scada")
    summary, unresolved = audit_pilot(paths, registration_rows, secondary_units)
    audit_path = root / "data/interim/duid_mapping_audit.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_csv(
        root / "data/interim/unresolved_duids.csv",
        unresolved,
        fieldnames=[
            "duid",
            "region",
            "official_dispatch_type",
            "fuel_category",
            "fuel_source_detail",
            "mapping_method",
            "review_status",
            "observations",
            "positive_mwh",
            "absolute_mwh",
        ],
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
