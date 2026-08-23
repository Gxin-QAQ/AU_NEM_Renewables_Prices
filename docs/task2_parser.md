# AEMO archive parser

## Deliverables

- `src/aemo_dispatch.py` parses AEMO's nested daily ZIP archives using only the Python standard library.
- `parse_region_archive()` returns standardised regional records with fixed-AEST timestamp, region, RRP and total demand.
- `parse_scada_archive()` returns standardised unit records with fixed-AEST timestamp, DUID and SCADA MW.
- `tests/test_aemo_dispatch.py` exercises the MMS `C/I/D` reader, duplicate-member rule and pilot archive integration.

## Parsing contract

| Source table | Required fields | Standardised fields |
|---|---|---|
| `DREGION` | `SETTLEMENTDATE`, `REGIONID`, `RRP`, `TOTALDEMAND` | `timestamp`, `region`, `rrp_aud_mwh`, `demand_mw` |
| `DISPATCH.UNIT_SCADA` | `SETTLEMENTDATE`, `DUID`, `SCADAVALUE` | `timestamp`, `duid`, `scada_mw` |

The parser attaches `Australia/Brisbane` to all source timestamps. This represents fixed NEM market time (AEST/UTC+10), not a state-local wall clock. AEMO `SETTLEMENTDATE` is retained as `settlement_timestamp` (the five-minute interval-end label); the panel builder derives its canonical interval-start timestamp by subtracting five minutes.

## Archive integrity rule

Outer archive ZIPs are enumerated by inner member filename. Identical non-empty duplicates are accepted once, and an empty placeholder is ignored when a valid non-empty member with the same name exists. Conflicting non-empty payloads raise an error. This directly handles the zero-byte placeholder followed by the valid 08:45 SCADA member observed on 8 September 2025 without silently accepting conflicting revisions.

## Test result

The 5 October 2025 pilot dispatch archive produced 1,440 regional records: 288 fixed-AEST intervals × five NEM regions. The paired SCADA archive produced records across the same 288 intervals. Run the relevant checks with:

```bash
PYTHONPATH=. python -m unittest tests.test_aemo_dispatch -v
```

## Deferred work

Fuel aggregation remains outside this parser module. The effective-dated crosswalk and storage rules are documented in `task3_duid_fuel_mapping.md`.
