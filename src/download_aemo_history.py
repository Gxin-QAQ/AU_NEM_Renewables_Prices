"""Plan and download the table families needed for the FY2020–FY2025 panel.

The AEMO MMSDM archive changed its per-table filename convention. This module
probes the current `PUBLIC_ARCHIVE` convention first and falls back to the
older `PUBLIC_DVD` convention, recording the resolved URL and checksum for
every immutable source file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import ZipFile


MMSDM_BASE = "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM"
TABLES = {
    # ``DISPATCHREGIONSUM`` provides regional demand, but deliberately does
    # not contain the regional reference price.  Keep price as a distinct
    # source so the resulting panel has an auditable one-table-per-concept
    # lineage.
    "region": "DISPATCHREGIONSUM",
    "price": "DISPATCHPRICE",
    "scada": "DISPATCH_UNIT_SCADA",
}
MANIFEST_COLUMNS = [
    "dataset",
    "table_name",
    "period",
    "source_url",
    "downloaded_at_utc",
    "local_path",
    "sha256",
    "bytes",
    "status",
]


@dataclass(frozen=True)
class ArchiveItem:
    dataset: str
    table_name: str
    period: str
    url: str
    bytes: int


def month_range(start: str, end: str) -> list[str]:
    """Return inclusive YYYY-MM months, rejecting malformed inputs."""
    try:
        first = datetime.strptime(start, "%Y-%m")
        last = datetime.strptime(end, "%Y-%m")
    except ValueError as error:
        raise ValueError("Months must use YYYY-MM") from error
    if first > last:
        raise ValueError("Start month must not be after end month")
    months: list[str] = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def archive_url_candidates(table_name: str, period: str) -> list[str]:
    """Return new and legacy table-specific archive URLs for one month."""
    year, month = period.split("-")
    directory = (
        f"{MMSDM_BASE}/{year}/MMSDM_{year}_{month}/"
        "MMSDM_Historical_Data_SQLLoader/DATA"
    )
    timestamp = f"{year}{month}010000"
    return [
        f"{directory}/PUBLIC_ARCHIVE%23{table_name}%23FILE01%23{timestamp}.zip",
        f"{directory}/PUBLIC_DVD_{table_name}_{timestamp}.zip",
    ]


def probe_url(url: str) -> int | None:
    """Return content length if an archive URL exists, otherwise ``None``."""
    request = Request(url, method="HEAD", headers={"User-Agent": "AU-NEM-research/1.0"})
    try:
        with urlopen(request, timeout=45) as response:
            value = response.headers.get("Content-Length")
            return int(value) if value else 0
    except HTTPError as error:
        if error.code in {403, 404}:
            return None
        raise
    except URLError as error:
        raise RuntimeError(f"Archive probe failed for {url}: {error.reason}") from error


def probe_item(dataset: str, table_name: str, period: str) -> ArchiveItem:
    for url in archive_url_candidates(table_name, period):
        size = probe_url(url)
        if size is not None:
            return ArchiveItem(dataset, table_name, period, url, size)
    raise FileNotFoundError(f"No AEMO archive found for {table_name} in {period}")


def probe_plan(months: list[str], datasets: list[str], workers: int) -> list[ArchiveItem]:
    """Probe all selected archives concurrently while retaining deterministic order."""
    requests = [(dataset, TABLES[dataset], period) for period in months for dataset in datasets]
    output: list[ArchiveItem] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(probe_item, *request) for request in requests]
        for future in as_completed(futures):
            output.append(future.result())
    return sorted(output, key=lambda item: (item.period, item.dataset))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_archive(path: Path, table_name: str) -> None:
    """Check that a download is a non-empty ZIP with the requested table name."""
    with ZipFile(path) as archive:
        csv_members = [member for member in archive.infolist() if member.filename.lower().endswith(".csv")]
        if len(csv_members) != 1:
            raise ValueError(f"{path.name}: expected one CSV member, found {len(csv_members)}")
        if table_name not in csv_members[0].filename:
            raise ValueError(f"{path.name}: CSV member does not name {table_name}")


def item_path(root: Path, item: ArchiveItem) -> Path:
    return root / "data/raw/aemo_history" / item.dataset / f"{item.period}.zip"


def load_manifest(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {(row["dataset"], row["period"]): row for row in csv.DictReader(handle)}


def write_manifest(path: Path, entries: dict[tuple[str, str], dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for _, row in sorted(entries.items()):
            writer.writerow(row)


def download_item(root: Path, item: ArchiveItem, force: bool = False) -> dict[str, str]:
    """Download one immutable archive atomically and return its manifest row."""
    destination = item_path(root, item)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        validate_archive(destination, item.table_name)
        status = "verified_existing"
    else:
        temporary = destination.with_suffix(".zip.part")
        request = Request(item.url, headers={"User-Agent": "AU-NEM-research/1.0"})
        with urlopen(request, timeout=120) as response, temporary.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
        validate_archive(temporary, item.table_name)
        os.replace(temporary, destination)
        status = "downloaded"
    return {
        "dataset": item.dataset,
        "table_name": item.table_name,
        "period": item.period,
        "source_url": item.url,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "local_path": destination.relative_to(root).as_posix(),
        "sha256": sha256_file(destination),
        "bytes": str(destination.stat().st_size),
        "status": status,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2019-07")
    parser.add_argument("--end", default="2025-06")
    parser.add_argument(
        "--datasets",
        default="region,price,scada",
        help="Comma-separated: region,price,scada",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--download", action="store_true", help="Download after a successful plan probe")
    parser.add_argument(
        "--use-existing-plan",
        action="store_true",
        help="Reuse the matching saved plan instead of probing URLs again",
    )
    parser.add_argument("--force", action="store_true", help="Replace existing immutable files")
    parser.add_argument("--max-gib", type=float, default=3.0)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    datasets = [dataset.strip() for dataset in args.datasets.split(",") if dataset.strip()]
    unknown = set(datasets) - set(TABLES)
    if unknown:
        raise ValueError(f"Unknown datasets: {sorted(unknown)}")
    if not datasets:
        raise ValueError("At least one dataset is required")
    root = args.root.resolve()
    plan_path = root / "data/interim/aemo_history_download_plan.json"
    if args.use_existing_plan:
        if not plan_path.exists():
            raise FileNotFoundError(f"No saved plan found at {plan_path}")
        plan_output = json.loads(plan_path.read_text(encoding="utf-8"))
        if (
            plan_output.get("start") != args.start
            or plan_output.get("end") != args.end
            or plan_output.get("datasets") != datasets
        ):
            raise ValueError("Saved plan does not match the requested start, end and datasets")
        plan = [ArchiveItem(**item) for item in plan_output["items"]]
    else:
        months = month_range(args.start, args.end)
        plan = probe_plan(months, datasets, args.workers)
        total_bytes = sum(item.bytes for item in plan)
        plan_output = {
            "start": args.start,
            "end": args.end,
            "months": len(months),
            "datasets": datasets,
            "files": len(plan),
            "total_bytes": total_bytes,
            "total_gib": round(total_bytes / 1024**3, 3),
            "items": [asdict(item) for item in plan],
        }
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan_output, indent=2) + "\n", encoding="utf-8")
    total_bytes = sum(item.bytes for item in plan)
    if not args.download:
        print(json.dumps(plan_output, indent=2))
        return
    if total_bytes > args.max_gib * 1024**3:
        raise ValueError(
            f"Planned {total_bytes / 1024**3:.2f} GiB exceeds --max-gib {args.max_gib:.2f}; "
            "increase the explicit budget to download"
        )
    manifest_path = root / "data/raw/history_manifest.csv"
    manifest = load_manifest(manifest_path)
    for item in plan:
        manifest[(item.dataset, item.period)] = download_item(root, item, force=args.force)
        write_manifest(manifest_path, manifest)
    print(json.dumps({**plan_output, "status": "downloaded"}, indent=2))


if __name__ == "__main__":
    main()
