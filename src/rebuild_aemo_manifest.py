"""Rebuild an idempotent manifest for downloaded AEMO pilot archives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from src.download_aemo_pilot import ARCHIVE_ROOT, DATASETS, MANIFEST_FIELDS, build_url


FILENAME_PATTERN = re.compile(
    r"^(?P<prefix>PUBLIC_DISPATCH(?:SCADA)?)_(?P<day>\d{8})\.zip$"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def existing_download_times(manifest: Path) -> dict[str, str]:
    if not manifest.exists():
        return {}
    earliest: dict[str, str] = {}
    with manifest.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            local_path = row.get("local_path", "")
            timestamp = row.get("downloaded_at_utc", "")
            if local_path and timestamp and (
                local_path not in earliest or timestamp < earliest[local_path]
            ):
                earliest[local_path] = timestamp
    return earliest


def dataset_for_prefix(prefix: str) -> str:
    return "scada" if prefix == "PUBLIC_DISPATCHSCADA" else "dispatch"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/aemo_pilot"))
    parser.add_argument("--manifest", type=Path, default=Path("data/raw/manifest.csv"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    previous_times = existing_download_times(args.manifest)
    records: list[dict[str, str | int]] = []

    for archive in sorted(args.raw_dir.glob("*/*.zip")):
        match = FILENAME_PATTERN.match(archive.name)
        if not match:
            continue
        source_day = datetime.strptime(match.group("day"), "%Y%m%d").date()
        dataset = dataset_for_prefix(match.group("prefix"))
        source_url, _ = build_url(dataset, source_day)
        local_path = archive.as_posix()
        records.append(
            {
                "source_name": f"AEMO NEMWeb {dataset}",
                "source_url": source_url,
                "downloaded_at_utc": previous_times.get(
                    local_path, datetime.now(timezone.utc).isoformat()
                ),
                "local_path": local_path,
                "sha256": sha256_file(archive),
                "bytes": archive.stat().st_size,
                "source_period": source_day.isoformat(),
                "status": "verified_existing",
            }
        )

    records.sort(key=lambda row: (str(row["source_period"]), str(row["source_name"])))
    temporary = args.manifest.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    temporary.replace(args.manifest)
    print(f"wrote {len(records)} unique archive records to {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
