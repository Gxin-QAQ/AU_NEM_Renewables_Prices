# Data sources and acquisition plan

## Primary market data — AEMO

| Dataset / table family | Use | Frequency | Core fields |
|---|---|---|---|
| Dispatch regional data (`DISPATCHPRICE`, `DISPATCHREGIONSUM`) | RRP, demand, regional supply | 5 minutes | `SETTLEMENTDATE`, `REGIONID`, `RRP`, `TOTALDEMAND`, `CLEAREDSUPPLY` |
| Unit SCADA / dispatch data | Generation by unit | 5 minutes | `SETTLEMENTDATE`, `DUID`, `SCADAVALUE` or dispatched MW |
| Unit / participant registration data (`DUDETAILSUMMARY`) | Official identity, region and effective dates | Versioned | `DUID`, `START_DATE`, `END_DATE`, region, station, dispatch/schedule type |
| Interconnector and constraint data | Cross-region and congestion controls | 5 minutes | flow, import/export limit, binding constraint indicator |

**Access route:** AEMO's MMS data pages point to current and archive NEMWeb reports. Start from the official dispatch documentation, not a hard-coded third-party mirror. The downloader must store each resolved archive URL and checksum in `data/raw/manifest.csv`.

**Important:** Historical file names, schemas and archive paths may vary. The acquisition module will validate the expected header fields and fail loudly if AEMO changes a schema.

The FY2020–FY2025 acquisition uses table-specific MMSDM monthly archives rather than multi-gigabyte whole-month packages. The downloader handles both the legacy `PUBLIC_DVD` and newer `PUBLIC_ARCHIVE` filename conventions and records the resolved URL per file. See `task5_history_acquisition.md`.

### Unit fuel labels

`DUDETAILSUMMARY` does not contain a fuel field. The pilot therefore combines it with an immutable capture of OpenElectricity's public facility export, while marking OpenElectricity as a secondary source in every crosswalk row. AEMO's Generation Information workbook remains the production cross-check. See `task3_duid_fuel_mapping.md` for the source boundary, effective-date join and materiality audit.

## Weather — Australian Bureau of Meteorology (BoM)

| Measure | Role | Preferred implementation |
|---|---|---|
| Air temperature | Demand control | Population/load-weighted station average per region |
| Wind speed | Renewable-availability control / IV candidate | Generation-zone-weighted station average, if defensible |
| Sunshine / solar radiation | Solar-availability control / IV candidate | Use radiation where consistently available; otherwise a documented alternative source |

BoM Climate Data Online publishes historical station observations. Its ordinary daily observations are sufficient for a daily robustness panel but not the headline hourly model. The production pipeline should use hourly/sub-hourly station data where availability permits; if station coverage is uneven, use an openly licensed reanalysis/gridded product and document the source and licence.

## Optional controls

- East-coast gas benchmark and thermal coal benchmark: include only if the source has a stable, redistributable history.
- AEMO outage, constraint and interconnector information: priority control because it is closer to NEM price formation than global commodity data.
- Policy/event indicators: pre-register a small set of clearly dated events; do not select events by visual inspection of prices.

## Citation and terms checklist

- Cite AEMO's NEM data page and MMS dispatch documentation in the report.
- Cite the AEMO `DUDETAILSUMMARY` archive and Generation Information vintage used for the final fuel cross-check.
- Cite OpenElectricity wherever its provisional unit fuel labels remain in a reported result.
- Cite the specific BoM dataset/product and station identifiers actually used.
- Check current source terms before redistributing any raw extracts.
