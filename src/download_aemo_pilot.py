"""Download a bounded, auditable AEMO NEMWeb pilot sample.

The script intentionally uses only Python's standard library. It downloads the
public daily dispatch and SCADA ZIP archives, preserves them as immutable raw
inputs, and writes one manifest record per file.

Example
-------
python -m src.download_aemo_pilot --start 2025-09-01 --end 2025-10-31
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ARCHIVE_ROOT = "https://nemweb.com.au/REPORTS/ARCHIVE"
DATASETS = {
    "dispatch": {
        "directory": "Dispatch_Reports",
        "prefix": "PUBLIC_DISPATCH",
    },
    "scada": {
        "directory": "Dispatch_SCADA",
        "prefix": "PUBLIC_DISPATCHSCADA",
    },
}
MANIFEST_FIELDS = [
    "source_name",
    "source_url",
    "downloaded_at_utc",
    "local_path",
    "sha256",
    "bytes",
    "source_period",
    "status",
]


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def append_manifest(path: Path, record: dict[str, str | int]) -> None:
    needs_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerow(record)


def download(url: str, destination: Path, retries: int) -> tuple[int, str]:
    """Stream to a temporary file, then atomically place a complete archive."""
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = Request(url, headers={"User-Agent": "AU-NEM-research-pilot/0.1"})
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=90) as response, temporary.open("wb") as handle:
                while chunk := response.read(1024 * 1024):
                    handle.write(chunk)
            temporary.replace(destination)
            return destination.stat().st_size, sha256_file(destination)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            last_error = error
            temporary.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"Download failed after {retries + 1} attempts: {last_error}")


def build_url(dataset: str, day: date) -> tuple[str, str]:
    config = DATASETS[dataset]
    filename = f"{config['prefix']}_{day:%Y%m%d}.zip"
    return f"{ARCHIVE_ROOT}/{config['directory']}/{filename}", filename


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2025, 9, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 10, 31))
    parser.add_argument("--datasets", nargs="+", choices=sorted(DATASETS), default=sorted(DATASETS))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/aemo_pilot"))
    parser.add_argument("--manifest", type=Path, default=Path("data/raw/manifest.csv"))
    parser.add_argument("--retries", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.end < args.start:
        raise ValueError("--end must not precede --start")

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    failures = 0

    for dataset in args.datasets:
        target_dir = args.raw_dir / dataset
        target_dir.mkdir(parents=True, exist_ok=True)
        for day in daterange(args.start, args.end):
            url, filename = build_url(dataset, day)
            destination = target_dir / filename
            timestamp = datetime.now(timezone.utc).isoformat()
            relative_path = destination.as_posix()
            try:
                if destination.exists() and destination.stat().st_size > 0:
                    size, checksum, status = (
                        destination.stat().st_size,
                        sha256_file(destination),
                        "skipped_existing",
                    )
                else:
                    size, checksum = download(url, destination, args.retries)
                    status = "downloaded"
                append_manifest(
                    args.manifest,
                    {
                        "source_name": f"AEMO NEMWeb {dataset}",
                        "source_url": url,
                        "downloaded_at_utc": timestamp,
                        "local_path": relative_path,
                        "sha256": checksum,
                        "bytes": size,
                        "source_period": day.isoformat(),
                        "status": status,
                    },
                )
                print(f"{status}: {dataset} {day} ({size:,} bytes)")
            except RuntimeError as error:
                failures += 1
                append_manifest(
                    args.manifest,
                    {
                        "source_name": f"AEMO NEMWeb {dataset}",
                        "source_url": url,
                        "downloaded_at_utc": timestamp,
                        "local_path": relative_path,
                        "sha256": "",
                        "bytes": "",
                        "source_period": day.isoformat(),
                        "status": f"failed: {error}",
                    },
                )
                print(f"failed: {dataset} {day}: {error}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
