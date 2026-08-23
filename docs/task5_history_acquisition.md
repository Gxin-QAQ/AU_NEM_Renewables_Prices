# Task 5 — FY2020–FY2025 historical acquisition

## Outcome

The complete raw AEMO source set for the planned study window has been acquired and validated.

| Dataset | Table | Files | Compressed size |
|---|---|---:|---:|
| Regional prices and demand | `DISPATCHREGIONSUM` | 72 | 0.350 GiB |
| Unit SCADA output | `DISPATCH_UNIT_SCADA` | 72 | 1.365 GiB |
| **Total** |  | **144** | **1.716 GiB** |

The source period is July 2019 through June 2025, inclusive: the six Australian financial years FY2020–FY2025.

Every file is stored below `data/raw/aemo_history/` and recorded in `data/raw/history_manifest.csv` with its exact resolved URL, byte count, SHA-256 checksum and status. Raw archives remain ignored by Git.

## Reproduction

All commands use the project-local virtual environment:

```bash
.venv/bin/python -m src.download_aemo_history \
  --start 2019-07 --end 2025-06 --datasets region,scada

.venv/bin/python -m src.download_aemo_history \
  --start 2019-07 --end 2025-06 --datasets region,scada \
  --download --use-existing-plan --max-gib 2.0
```

The first command performs a read-only size and URL plan. The second command reuses that saved plan, refuses to exceed the explicit 2 GiB budget, downloads files atomically, validates each ZIP, and writes the manifest after every successful archive. A rerun validates existing files and skips them, so the process is restartable after interruption.

## Archive-version handling

AEMO uses two historical naming conventions:

- legacy months use `PUBLIC_DVD_<TABLE>_YYYYMM010000.zip`;
- newer months use `PUBLIC_ARCHIVE#<TABLE>#FILE01#YYYYMM010000.zip`.

The downloader probes the newer convention first and falls back to the legacy convention, retaining the resolved URL in the manifest. The implementation was verified against July 2020 (legacy) and June 2025 (current) before the full acquisition.

## Validation completed

- 144 expected dataset-month files are present.
- All 72 months appear once for each dataset.
- Every manifest checksum matches its local file.
- Every archive is a readable ZIP with one CSV member naming its requested table.
- No partial `.part` download remains.
- The full project test suite passes (20 tests).

## Next processing boundary

`DISPATCH_UNIT_SCADA` contains millions of rows per month; the monthly archives must be read and aggregated one month at a time. The next task should build the full five-minute/hourly panel from these already-verified raw files, without loading the entire SCADA history into memory at once.

## References

- [AEMO MMS data overview](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-management-system-mms-data)
- [AEMO dispatch data documentation](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-management-system-mms-data/dispatch)
- [AEMO MMSDM archive](https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/)
