# Task 4 — Pilot region-time panel and hourly aggregation

## Outcome

The project now produces two analysis-ready pilot panels from the 14 intended AEMO market days:

```bash
.venv/bin/python -m src.duid_mapping
.venv/bin/python -m src.panel_builder
```

| Output | Rows | Key | Purpose |
|---|---:|---|---|
| `data/processed/nem_region_5min_pilot.parquet` | 20,160 | interval-start timestamp × region | Reproducible five-minute source panel |
| `data/processed/nem_region_hour_pilot.parquet` | 1,680 | hour-start timestamp × region | Pilot input for descriptive and regression work |

There are 4,032 five-minute intervals and 336 complete hours per region across the two seven-day windows. The gap between the two windows is intentional and explicitly checked.

## Timestamp contract

AEMO's `SETTLEMENTDATE` is kept as `settlement_timestamp`, the label at the end of the five-minute dispatch interval. The canonical analysis `timestamp` is:

`timestamp = settlement_timestamp − 5 minutes`

Both are fixed NEM market time (`Australia/Brisbane`, UTC+10). This prevents a registration change at midnight from being assigned to the preceding interval.

For peak/off-peak and seasonal heterogeneity, the builder derives these separate state-local fields:

- `local_timestamp` (ISO string with the correct offset)
- `local_date`, `local_hour`, `local_weekday`, `local_utc_offset_hours`
- `local_timezone`, `peak`, `season`

NSW/VIC use `Australia/Sydney`; QLD uses fixed `Australia/Brisbane`; SA uses `Australia/Adelaide`; TAS uses `Australia/Hobart`. The canonical market-time key is never replaced by a local clock, so daylight-saving transitions do not produce duplicated panel keys.

## Aggregation rules

At the five-minute level, the crosswalk aggregation produces wind, utility solar, hydro, thermal fuel classes, battery charge/discharge, load SCADA and unknown output separately.

At the hourly level:

- price, demand and MW variables are the mean of exactly 12 five-minute observations;
- `intrahour_price_sd` is the sample standard deviation of the 12 RRPs;
- `negative_price_share_5min` is the share of negative five-minute RRPs;
- `negative_price_any` is true if any of the 12 RRPs is negative;
- renewable shares are recomputed from hourly mean MW quantities, rather than averaged from five-minute ratios.

Operational demand may be non-positive during high distributed-PV periods. In those 31 pilot intervals, both renewable-share variables are set to missing and `nonpositive_demand` is true; raw price, demand and generation data are retained. The future estimation sample must state how it treats these observations.

## Validation results

| Check | Result |
|---|---:|
| Five-minute duplicate region-time keys | 0 |
| Incomplete hourly observations | 0 |
| Unmapped positive SCADA energy | 0 GWh |
| Canonical timezone | Fixed AEST / `Australia/Brisbane` |
| State-local timezone mapping | 5 of 5 regions configured |
| Non-positive-demand five-minute intervals | 31 |

The builder fails if a regional source key is duplicate, a DUID mapping is missing or ambiguous, any full market-day interval is skipped, an hourly bin does not contain 12 five-minute observations, or a renewable share is negative.

## Scope boundary

This is a pilot-panel build, not the FY2020–FY2025 production extraction. It validates the unit-to-region aggregation and time logic before Task 5 selects a size-aware historical acquisition strategy.
