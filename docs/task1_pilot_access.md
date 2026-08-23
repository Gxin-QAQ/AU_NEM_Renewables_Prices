# AEMO pilot access validation

## Purpose

Validate a small, auditable AEMO NEMWeb acquisition path before constructing the full FY2020–FY2025 panel.

## Selected windows

| Window | Dates | Purpose |
|---|---|---|
| Ordinary period | 8–14 September 2025 | Validate ordinary 5-minute daily-file structure. |
| DST-transition period | 2–8 October 2025 | Confirm that the spring daylight-saving transition on 5 October does not change fixed-AEST NEM interval counts. |

The daily archive has limited retention, so these windows are used only to test ingestion. They do not replace the headline historical study sample.

## Confirmed archive structure

- `PUBLIC_DISPATCH_YYYYMMDD.zip` is a daily outer ZIP containing nested interval ZIP files. Each inner dispatch file uses AEMO's `C/I/D` flat-file structure and includes the `DREGION` table with `SETTLEMENTDATE`, `REGIONID`, `RRP`, `TOTALDEMAND` and related fields.
- `PUBLIC_DISPATCHSCADA_YYYYMMDD.zip` is a daily outer ZIP containing nested interval ZIP files. Each inner file includes `DISPATCH.UNIT_SCADA` with `SETTLEMENTDATE`, `DUID` and `SCADAVALUE`.
- NEM market timestamps are fixed Australian Eastern Standard Time (AEST/UTC+10), not state-local daylight-saving time. A full market day therefore retains 288 five-minute intervals across the 5 October 2025 DST boundary.

## Pilot result

The validation build acquired and verified two intended seven-day windows (14 market days × two archive families), plus a small number of ordinary-period dispatch files downloaded during access probing. The normalized manifest contains 47 unique source archives and the raw pilot occupies approximately 145 MB.

For each of the 14 intended days, the dispatch archive has 288 unique nested interval files. The SCADA archive also has 288 unique nested interval files on every intended day, including 5 October. The 8 September SCADA outer ZIP contains 289 entries but only 288 unique inner filenames: the first `202509080845` entry is a zero-byte placeholder and the second is the valid interval ZIP. This is an archive duplication, not an additional interval.

**Parser requirement:** enumerate outer ZIP members by unique member name, prefer the non-empty member when an empty placeholder and valid member share a name, and reject conflicting non-empty duplicates. After de-duplication, validate exactly 288 five-minute intervals per complete NEM market day; do not apply state daylight-saving corrections.
- The acquisition script writes all raw files under `data/raw/aemo_pilot/` and records resolved source URL, checksum, byte count, date and validation status in `data/raw/manifest.csv`.

## Known historical-access constraint

The public daily archive is not a long-run historical store. AEMO's earlier MMSDM monthly archive is available, but individual monthly ZIP files are very large because they contain many table families. The full-sample design must therefore first select only needed tables and choose one of:

1. size-aware extraction from AEMO MMSDM monthly files;
2. an approved, documented programmatic historical data source, while retaining AEMO as the underlying market-data authority; or
3. a narrower recent sample, explicitly framed as such.

This decision is intentionally deferred to the source/schema task because it affects reproducibility, storage and the claims the study can make.
