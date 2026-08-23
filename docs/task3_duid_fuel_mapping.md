# Effective-dated DUID and fuel mapping

## Outcome

The pilot now has a reproducible, source-explicit DUID crosswalk and a complete energy-weighted coverage audit. The build keeps official registration metadata separate from secondary fuel labels:

- AEMO `DUDETAILSUMMARY` supplies DUID identity, NEM region, station, participant, dispatch type, schedule type and effective dates.
- A captured OpenElectricity facility export supplies unit fuel technology where available. It is labelled as a secondary source in every affected crosswalk row.
- AEMO `BIDIRECTIONAL` units observed in the pilot are assigned to `BATTERY` under a separately named pilot rule. This rule is not applied to an unreviewed future vintage because a bidirectional unit can in principle include pumped hydro.

The generated `data/interim/duid_crosswalk.csv` contains 22,202 effective-dated rows for 977 DUIDs. Raw reference inputs, their exact URLs, byte counts, capture times and SHA-256 checksums are recorded in `data/external/reference_manifest.csv`. These generated files are intentionally ignored by Git and can be rebuilt with:

```bash
python -m src.duid_mapping
```

## Effective-date rule

Each SCADA observation is joined on DUID and the half-open interval:

`START_DATE <= timestamp < END_DATE`

The script rejects overlapping registration intervals rather than selecting an arbitrary row. NEM registration timestamps are interpreted in fixed AEST (`Australia/Brisbane`, UTC+10), consistent with dispatch timestamps.

## Fuel categories

| Project category | Detailed source labels / rule | Renewable treatment |
|---|---|---|
| `WIND` | `wind` | Headline and broad |
| `SOLAR_UTILITY` | `solar_utility` | Headline and broad |
| `HYDRO` | `hydro` | Broad only |
| `BATTERY` | battery labels or reviewed pilot BDU rule | Never renewable |
| `COAL_BLACK` | `coal_black` | Non-renewable |
| `COAL_BROWN` | `coal_brown` | Non-renewable |
| `GAS` | all `gas_*` labels | Non-renewable |
| `LIQUID_FUEL` | `distillate` | Non-renewable |
| `BIOENERGY` | biogas and biomass labels | Excluded from both pre-specified shares |
| `LOAD` | registered load or `pumps` | Not generation |
| `OTHER` | recognised but uncategorised fuel label | Non-renewable |
| `UNKNOWN` | no defensible fuel label | Excluded and reported |

The headline penetration measure remains wind plus utility solar. The broad robustness measure adds hydro. Bioenergy is kept separate because the research design pre-specifies variable renewable energy as the main exposure.

## Battery and hybrid handling

- Positive SCADA for `BATTERY` is stored as discharge, not renewable generation.
- Negative SCADA for `BATTERY` is stored as charging load.
- Battery charge and discharge never enter either renewable numerator.
- Hybrid sites are mapped at DUID level, not by station name. A generating DUID and a storage/load DUID at the same connection point therefore retain separate treatments.
- Historical two-DUID battery registrations and post-IESS single bidirectional DUIDs are resolved by official effective dates before applying fuel rules.

## Pilot coverage audit

The audit covers the two intended seven-day windows: 8–14 September and 2–8 October 2025.

| Check | Result |
|---|---:|
| SCADA archives | 14 |
| Five-minute timestamps | 4,032 |
| Observed DUIDs | 480 |
| DUIDs with a fuel/load category | 475 |
| OpenElectricity unit matches | 403 |
| Pilot BDU battery-rule matches | 46 |
| Official registered-load matches | 26 |
| Unresolved DUIDs | 5 |
| Official registration coverage, positive-energy weighted | 100.000% |
| Fuel coverage, positive-energy weighted | 100.000% |
| Fuel coverage, absolute-energy weighted | 100.000% |
| Secondary-source region conflicts | 0 |

The five unresolved codes are AEMO regional synthetic `DG_*` records. Each has zero SCADA throughout all 4,032 pilot intervals, so unresolved positive and absolute energy are both 0 GWh. They remain `UNKNOWN` rather than receiving invented fuel labels.

Energy-weighted coverage uses `SCADAVALUE × 5/60`. Positive and absolute-energy denominators are both reported so battery charging and other negative readings cannot disappear from the audit.

## Source limitation and production gate

AEMO's October 2025 Generation Information workbook is the preferred fuel-label cross-check, but its website download was behind an automated access challenge during this task. No bypass was attempted. The captured OpenElectricity export is therefore a provisional secondary fuel source, with its SHA-256 checksum frozen locally.

Before the full-sample regression is frozen, the crosswalk must be compared against the official AEMO workbook (or another official technology table) and all material discrepancies reviewed. This limitation does not block the pilot-panel validation because the pilot has 100% energy-weighted coverage and no region conflicts.

## References

- [AEMO Generation Information](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/nem-forecasting-and-planning/forecasting-and-planning-data/generation-information)
- [AEMO MMS Data Model Report](https://di-help.docs.public.aemo.com.au/Content/Data_Model/MMS_Data_Model_Report_55.pdf)
- [AEMO Integrating Energy Storage Systems project](https://www.aemo.com.au/initiatives/major-programs/nem-reform-program/nem-reform-program-initiatives/integrating-energy-storage-systems-project)
- [OpenElectricity project](https://openelectricity.org.au/)
