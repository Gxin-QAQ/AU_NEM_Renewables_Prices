<p align="center">
  🇨🇳 <a href="README.md">中文</a> &nbsp;|&nbsp; 🌍 English
</p>

# Data directory

This directory contains local research data and generated datasets. Large source files and derived extracts are intentionally excluded from Git; only this README and `.gitkeep` placeholders are tracked.

## Directory structure

| Directory | Contents | May scripts overwrite it? | Tracked in Git? |
|---|---|---:|---:|
| `raw/` | Immutable source downloads, archive ZIPs and download manifest | No | No |
| `external/` | Manually acquired source files, such as unit/fuel crosswalk inputs | No | No |
| `interim/` | Parsed, normalised and source-specific intermediate tables | Yes | No |
| `processed/` | Analysis-ready region-time panels | Yes | No |

## Data lineage

The intended flow is:

`official source -> raw/external -> interim -> processed -> outputs`

Files in `raw/` and `external/` are treated as immutable inputs. If an official source publishes a revision, save it as a new source vintage rather than replacing the previous file silently. Only pipeline-generated files in `interim/` and `processed/` may be rebuilt.

## Core datasets

### `raw/manifest.csv`

One record per downloaded file:

| Field | Description |
|---|---|
| `source_name` | Human-readable source name |
| `source_url` | Exact resolved download URL |
| `downloaded_at_utc` | UTC acquisition timestamp |
| `local_path` | Repository-relative storage path |
| `sha256` | File checksum |
| `bytes` | Download size |
| `source_period` | Month/day represented by the file |
| `status` | Download/validation result |

### `raw/history_manifest.csv`

Manifest for the full FY2020–FY2025 AEMO history: one record per month and table family (`region` / `price` / `scada`). It records the resolved legacy/current archive URL, local file, checksum, size and validation status. Rebuild or verify with `.venv/bin/python -m src.download_aemo_history`.

### `processed/nem_region_hour.parquet`

The main analysis panel, uniquely keyed by timezone-aware `timestamp` and AEMO `region`. Expected columns are documented in `../docs/variable_dictionary.md`. Hourly price and volatility variables are calculated from the underlying 5-minute intervals; generation and demand are aggregated using explicitly documented rules.

### `processed/nem_region_5min/YYYY-MM.parquet`

Validated 5-minute panel used to reproduce hourly aggregation and negative-price outcomes. This may be partitioned by year and region if a single file becomes unwieldy.

The hourly negative-price thresholds are computed here before aggregation: `negative_price_below_minus_50_any_5min` and `negative_price_below_minus_100_any_5min` indicate whether any five-minute RRP in the hour crosses the stated threshold. They must not be reconstructed from the hourly mean price.

### `processed/nem_region_hour_generation_demand.parquet`

Interim hourly panel containing demand and fuel-resolved SCADA generation, but no price fields. It has 263,040 region-hour observations across FY2020–FY2025. It is not the main analysis panel and must never be used for price claims before `DISPATCHPRICE` is acquired and joined.

### `processed/nem_region_hour_model.parquet`

Task 7 model frame derived from the final hourly price panel. It adds only transformations, fixed-effect identifiers, week clusters, the 5MS split and frozen lag blocks declared in `../config/econometric_spec.yml`. Its four-region headline sample contains 210,399 usable observations; estimates must continue to apply the `headline_sample` or `dynamic_sample` flags explicitly.

### `interim/history_generation_demand_5min/YYYY-MM.parquet`

Restartable five-minute month partitions built from the verified regional-demand and SCADA archives. They prevent repeated processing of the full SCADA history when the price table becomes available. Corresponding hourly partitions live in `interim/history_generation_demand_hour/`.

### Pilot processed panels

`processed/nem_region_5min_pilot.parquet` and `processed/nem_region_hour_pilot.parquet` are the Task 4 validation outputs for the two 2025 seven-day windows. They are not substitutes for the planned FY2020–FY2025 production panel. Rebuild them with `python -m src.panel_builder` after first rebuilding the DUID crosswalk.

### `external/aemo_reference/DUDETAILSUMMARY_202510.zip`

Immutable AEMO MMSDM October 2025 registration archive. It supplies effective-dated DUID, region, station, participant, schedule and dispatch-type fields. Its exact source URL and SHA-256 checksum are recorded in `external/reference_manifest.csv`.

### `external/openelectricity/au_facilities_20260823.json`

Immutable capture of the public OpenElectricity facility export used as a secondary fuel-technology source. The filename records the capture date; the manifest records its exact capture time and checksum. It must not be described as an AEMO fuel field.

### `interim/duid_crosswalk.csv`

Generated effective-dated DUID-to-region/fuel crosswalk. Important fields include `valid_from_aest`, `valid_to_aest`, `fuel_category`, `fuel_source_detail`, `mapping_method`, `review_status`, source vintages and checksums. Rebuild it with `python -m src.duid_mapping`.

### `interim/duid_mapping_audit.json` and `interim/unresolved_duids.csv`

Generated pilot audit outputs. Coverage is reported both against positive SCADA energy and absolute SCADA energy. Unknown DUIDs remain explicit and are ranked by energy materiality.

## Source conventions

- Preserve the exact AEMO interval timestamp before adding derived timestamps.
- Store canonical timestamps as timezone-aware NEM market time in `Australia/Brisbane` (fixed AEST/UTC+10). Do not apply Sydney daylight-saving shifts to source market timestamps; create a separate state-local timestamp only when needed.
- Preserve original source columns in the first parsed table and rename them only in a documented transformation step.
- Store prices in AUD/MWh and output/demand in MW.
- Do not mix scheduled targets, SCADA output and energy without an explicit variable name and conversion rule.
- Keep battery generation and charging separate. Do not classify net battery output as renewable generation.
- Preserve AEMO `SETTLEMENTDATE` as an interval-end source label and use a separate interval-start analysis timestamp.
- If operational demand is zero or negative, retain the row but set demand-based renewable shares to missing and expose an explicit flag.
- Do not cap demand-based renewable shares at one: regional generation can exceed operational demand when the region exports. Treat capped or winsorised values only as explicitly labelled robustness variants.
- Record the AEMO registration/fuel-map vintage used for each DUID.
- Join registration records with `START_DATE <= timestamp < END_DATE`; never use a current-only DUID map for historical observations.
- Keep official AEMO registration fields and secondary fuel labels in separate provenance columns.

## Validation gates

A dataset may move to `processed/` only after it passes:

1. schema and required-column checks;
2. unique region-time key checks;
3. expected region-code checks;
4. 5-minute interval continuity and fixed-AEST/DST-boundary checks;
5. missingness and physically implausible-value checks;
6. unit-to-region and unit-to-fuel coverage checks;
7. reconciliation of regional totals against an independent AEMO publication for sampled periods.

## Final analysis snapshot

- Source history: 216 verified monthly AEMO archives (72 regional-demand, 72 price and 72 SCADA files).
- Main hourly panel: 263,040 observations, five NEM regions, 1 July 2019–30 June 2025.
- Headline sample: 210,399 usable NSW1/VIC1/QLD1/SA1 region-hours after excluding 33 non-positive-demand SA1 hours.
- Dynamic sample: 209,928 observations after applying the frozen lag requirements.
- Inference: 314 AEST ISO-week clusters.
- Frozen p99.9 share cap: 2.78918; 211 headline observations are affected.

The report-facing outputs are generated from `processed/nem_region_hour_model.parquet` and the frozen Task 8–9 result tables. No report number should be manually edited without rebuilding or reconciling those artifacts.

## Reproduction

The pipeline exposes separate commands for download, parsing, panel construction, validation, estimation and reporting. Credentials or API keys must be supplied through local environment configuration and must never be committed. All research commands run through the repository-local `.venv`; AEMO and secondary-source data remain subject to their respective terms and attribution requirements.

## Dataset status

The first acquisition task used two seven-day windows—one ordinary period and one daylight-saving transition period—before scaling to the full sample. All commands use the project-local environment:

```bash
.venv/bin/python -m src.download_aemo_pilot --start 2025-09-08 --end 2025-09-14
.venv/bin/python -m src.download_aemo_pilot --start 2025-10-02 --end 2025-10-08
.venv/bin/python -m src.rebuild_aemo_manifest
```

The 2025 pilot archives have been acquired and a 47-record manifest with recorded SHA-256 checksums has been built. See `../docs/task1_pilot_access.md` for the observed archive structure and parser requirements.

The effective-dated DUID/fuel build is also complete for the pilot. It resolves all observed SCADA energy to a fuel/load category; five zero-output `DG_*` synthetic codes remain explicitly unknown. See `../docs/task3_duid_fuel_mapping.md` for mapping rules, battery treatment and the coverage audit.

The raw FY2020–FY2025 source history is complete: 72 each of regional-demand, price and SCADA monthly archives (216 files in total). `DISPATCHREGIONSUM` supplies demand and the separate `DISPATCHPRICE` table supplies RRP; the two are joined only by the documented fixed-AEST region-time key. See `../docs/task6_descriptive_status.md` for the completed panel and descriptive-data audit.

The current public daily AEMO archive has limited retention. Historical FY2020–FY2025 extraction therefore uses the verified monthly MMSDM archive pipeline recorded in `raw/history_manifest.csv`.

No weather extract is currently stored under `raw/`, `external/`, `interim/` or `processed/`. Task 9 rejected a causal weather-IV interpretation because weather also affects operational demand and rooftop PV, public station coverage is uneven, and no plant-location/capacity-weighted instrument or exclusion audit exists. Weather may be added later as documented controls or as a separately versioned research extension; it is not part of the current estimand.

Task 10 does not add or alter analytical data. It reads the frozen Task 8–9 tables, produces two report coefficient figures, and renders the final English report. The raw, interim and processed data contracts therefore remain unchanged.

Task 11 rebuilt the project `.venv` from scratch, verified the byte size and SHA-256 of all 265 local immutable source files, and regenerated the final panels, Task 8–9 results, figures, notebooks and report. The three core Parquet files are byte-identical to their pre-audit versions; see the full [`Task 11 audit`](../docs/task11_reproducibility_audit.md).
