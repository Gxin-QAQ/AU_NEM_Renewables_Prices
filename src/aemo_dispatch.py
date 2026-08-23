"""Parse AEMO's nested public dispatch and SCADA archives.

The AEMO daily public archives are ZIP files containing one ZIP per five-minute
interval. Inner CSVs use the MMS `C/I/D` convention: `I` defines a table's
columns, and `D` supplies its records. NEM timestamps are fixed market time
(AEST/UTC+10), represented here by the `Australia/Brisbane` zone.
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta
from io import BytesIO, TextIOWrapper
from pathlib import Path
from typing import Any
from zipfile import ZipFile, ZipInfo
from zoneinfo import ZoneInfo


NEM_TIMEZONE = ZoneInfo("Australia/Brisbane")
DISPATCH_INTERVAL = timedelta(minutes=5)
REGION_TABLE = ("DREGION", "", "3")
UNIT_SCADA_TABLE = ("DISPATCH", "UNIT_SCADA", "1")
REQUIRED_REGION_FIELDS = {"SETTLEMENTDATE", "REGIONID", "RRP", "TOTALDEMAND"}
REQUIRED_SCADA_FIELDS = {"SETTLEMENTDATE", "DUID", "SCADAVALUE"}


def parse_market_timestamp(value: str) -> datetime:
    """Return an AEMO market timestamp as fixed-AEST, timezone-aware datetime."""
    naive = datetime.strptime(value, "%Y/%m/%d %H:%M:%S")
    return naive.replace(tzinfo=NEM_TIMEZONE)


def interval_start_from_settlement(settlement_timestamp: datetime) -> datetime:
    """Convert AEMO's five-minute settlement-end label to interval start."""
    return settlement_timestamp - DISPATCH_INTERVAL


def _table_key(row: list[str]) -> tuple[str, str, str]:
    if len(row) < 4:
        raise ValueError(f"Malformed AEMO row with fewer than four fields: {row!r}")
    return tuple(row[1:4])  # type: ignore[return-value]


def parse_aemo_csv_tables(payload: bytes) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    """Read all `I`/`D` MMS tables in one inner AEMO CSV payload."""
    headers: dict[tuple[str, str, str], list[str]] = {}
    tables: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    with TextIOWrapper(BytesIO(payload), encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if not row or row[0] == "C":
                continue
            record_type = row[0]
            if record_type not in {"I", "D"}:
                continue
            key = _table_key(row)
            fields = row[4:]
            if record_type == "I":
                headers[key] = fields
                tables.setdefault(key, [])
            elif key in headers:
                names = headers[key]
                if len(fields) != len(names):
                    raise ValueError(
                        f"Field-count mismatch in table {key}: "
                        f"expected {len(names)}, received {len(fields)}"
                    )
                tables.setdefault(key, []).append(dict(zip(names, fields, strict=True)))
    return tables


def _unique_members(archive: ZipFile) -> Iterator[ZipInfo]:
    """Yield one usable member per name and reject conflicting payloads.

    Some AEMO outer archives contain a zero-byte placeholder followed by a
    valid member with the same name. Empty placeholders are ignored when a
    non-empty payload exists; multiple non-empty payloads must be identical.
    """
    grouped: dict[str, list[ZipInfo]] = {}
    for member in archive.infolist():
        if not member.filename.lower().endswith(".zip"):
            continue
        grouped.setdefault(member.filename, []).append(member)

    for filename, members in grouped.items():
        usable = [(member, archive.read(member)) for member in members if member.file_size > 0]
        if not usable:
            raise ValueError(f"Outer archive member is empty: {filename}")
        checksums = {hashlib.sha256(payload).hexdigest() for _, payload in usable}
        if len(checksums) > 1:
            raise ValueError(
                f"Outer archive has conflicting duplicate member: {filename}"
            )
        yield usable[0][0]


def _inner_csv_payload(outer: ZipFile, member: ZipInfo) -> bytes:
    with ZipFile(BytesIO(outer.read(member))) as inner:
        csv_members = [info for info in inner.infolist() if info.filename.lower().endswith(".csv")]
        if len(csv_members) != 1:
            raise ValueError(
                f"Expected exactly one CSV in {member.filename}, found {len(csv_members)}"
            )
        return inner.read(csv_members[0])


def _require_fields(row: dict[str, str], required: set[str], table: str) -> None:
    missing = required - set(row)
    if missing:
        raise ValueError(f"{table} is missing required fields: {sorted(missing)}")


def parse_region_archive(path: Path) -> list[dict[str, Any]]:
    """Return standardised regional price/demand records from one daily archive."""
    records: list[dict[str, Any]] = []
    with ZipFile(path) as outer:
        for member in _unique_members(outer):
            tables = parse_aemo_csv_tables(_inner_csv_payload(outer, member))
            rows = tables.get(REGION_TABLE)
            if rows is None:
                raise ValueError(f"DREGION table absent from {path.name}/{member.filename}")
            for row in rows:
                _require_fields(row, REQUIRED_REGION_FIELDS, "DREGION")
                records.append(
                    {
                        "timestamp": parse_market_timestamp(row["SETTLEMENTDATE"]),
                        "settlement_timestamp": parse_market_timestamp(row["SETTLEMENTDATE"]),
                        "region": row["REGIONID"],
                        "rrp_aud_mwh": float(row["RRP"]),
                        "demand_mw": float(row["TOTALDEMAND"]),
                        "source_outer": path.name,
                        "source_inner": member.filename,
                    }
                )
    return records


def parse_scada_archive(path: Path) -> list[dict[str, Any]]:
    """Return standardised unit SCADA records from one daily archive."""
    records: list[dict[str, Any]] = []
    with ZipFile(path) as outer:
        for member in _unique_members(outer):
            tables = parse_aemo_csv_tables(_inner_csv_payload(outer, member))
            rows = tables.get(UNIT_SCADA_TABLE)
            if rows is None:
                raise ValueError(
                    f"DISPATCH.UNIT_SCADA table absent from {path.name}/{member.filename}"
                )
            for row in rows:
                _require_fields(row, REQUIRED_SCADA_FIELDS, "DISPATCH.UNIT_SCADA")
                records.append(
                    {
                        "timestamp": parse_market_timestamp(row["SETTLEMENTDATE"]),
                        "settlement_timestamp": parse_market_timestamp(row["SETTLEMENTDATE"]),
                        "duid": row["DUID"],
                        "scada_mw": float(row["SCADAVALUE"]),
                        "source_outer": path.name,
                        "source_inner": member.filename,
                    }
                )
    return records


def expected_interval_count(records: Iterable[dict[str, Any]]) -> int:
    """Count distinct fixed-AEST interval timestamps in standardised records."""
    return len({record["timestamp"] for record in records})
