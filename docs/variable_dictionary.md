# Variable dictionary (draft v0.1)

| Variable | Type / unit | Definition | Source |
|---|---|---|---|
| `timestamp` | timezone-aware datetime | Start of the 5-minute dispatch interval in fixed NEM market time (AEST/UTC+10; `Australia/Brisbane`) | Derived from AEMO `SETTLEMENTDATE` |
| `settlement_timestamp` | timezone-aware datetime | AEMO five-minute interval-end label retained without alteration | AEMO |
| `region` | category | NEM region identifier (`NSW1`, `VIC1`, `QLD1`, `SA1`, `TAS1`) | AEMO |
| `rrp_aud_mwh` | AUD/MWh | Regional reference price, exclusive of GST | AEMO dispatch price |
| `price_asinh` | transformed | `asinh(rrp_aud_mwh)` | Derived |
| `demand_mw` | MW | Regional demand measure selected and documented from AEMO | AEMO regional sum |
| `wind_mw` | MW | Mapped wind unit output | AEMO unit output + crosswalk |
| `solar_utility_mw` | MW | Mapped grid-scale solar unit output | AEMO unit output + crosswalk |
| `hydro_mw` | MW | Mapped hydro output; excluded from headline share | AEMO unit output + crosswalk |
| `battery_discharge_mw` | MW | Positive SCADA output from a DUID classified as battery storage | AEMO unit output + crosswalk |
| `battery_charge_mw` | MW | Absolute value of negative SCADA from a DUID classified as battery storage | AEMO unit output + crosswalk |
| `renewable_share_ws` | ratio | `(wind_mw + solar_utility_mw) / demand_mw` | Derived |
| `renewable_share_broad` | ratio | `(wind + solar + hydro) / demand` | Derived |
| `nonpositive_demand` | indicator | `1[demand_mw <= 0]`; renewable-share denominators are missing for these rows | Derived |
| `negative_price` | indicator | `1[rrp_aud_mwh < 0]` | Derived |
| `intrahour_price_sd` | AUD/MWh | Sample SD of twelve 5-minute RRP observations per hour | Derived |
| `temperature_c` | degrees C | Region-matched weather control | BoM / documented substitute |
| `wind_speed_ms` | m/s | Region-matched weather availability control | BoM / documented substitute |
| `solar_radiation` | source unit | Region-matched solar resource proxy | BoM / documented substitute |
| `peak` | indicator | Weekday 07:00–22:00 local time (headline) | Derived |
| `season` | category | DJF/MAM/JJA/SON, Southern Hemisphere convention | Derived |
| `local_timestamp` | ISO-8601 string | State-local representation of the canonical timestamp, including UTC offset | Derived |
| `local_hour` | integer | State-local hour used for peak/off-peak classification | Derived |
| `local_utc_offset_hours` | hours | State-local UTC offset; changes at DST boundaries where applicable | Derived |
| `negative_price_share_5min` | ratio | Share of negative RRPs in an hour | Derived |
| `negative_price_any` | indicator | `1` if any five-minute RRP in an hour is negative | Derived |
| `negative_price_below_minus_50_any_5min` | indicator | `1` if any five-minute RRP in an hour is below −50 AUD/MWh | Derived |
| `negative_price_below_minus_100_any_5min` | indicator | `1` if any five-minute RRP in an hour is below −100 AUD/MWh | Derived |
| `renewable_share_ws_10pp` | 10 percentage-point units | `10 * renewable_share_ws`; raw uncapped exposure used for transparency checks | Derived |
| `renewable_share_ws_10pp_winsor_p999` | 10 percentage-point units | Headline exposure, upper-winsorised at the pooled four-region sample p99.9 to limit near-zero-demand leverage | Derived in Task 7 |
| `renewable_output_ws_100mw` | 100 MW units | `(wind_mw + solar_utility_mw) / 100`; alternative exposure that avoids a demand denominator | Derived in Task 7 |
| `price_winsor_001_999` | AUD/MWh | RRP winsorised at pooled headline-sample p0.1 and p99.9; robustness outcome only | Derived in Task 7 |

## Crosswalk fields

| Variable | Type | Definition | Source |
|---|---|---|---|
| `duid` | string | AEMO Dispatchable Unit Identifier | AEMO `DUDETAILSUMMARY` |
| `valid_from_aest` | datetime | Inclusive start of the registration record in fixed AEST | AEMO `START_DATE` |
| `valid_to_aest` | datetime | Exclusive end of the registration record in fixed AEST | AEMO `END_DATE` |
| `official_dispatch_type` | category | `GENERATOR`, `LOAD` or `BIDIRECTIONAL` | AEMO |
| `fuel_category` | category | Project fuel class used for aggregation | Derived from source-explicit rules |
| `fuel_source_detail` | string | Original detailed fuel label or named fallback rule | OpenElectricity / documented rule |
| `mapping_method` | category | Exact method used to assign the fuel class | Derived |
| `review_status` | category | `secondary_source`, `pilot_rule_reviewed`, `official_rule` or `needs_review` | Derived |

All MW variables are aggregated to hourly means unless otherwise stated. Energy shares are defined using consistently timed MW quantities; any demand definition change is versioned and reported. Batteries are excluded from renewable generation even when discharging, because storage output is not an original energy source.
