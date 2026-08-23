# Task 6 — descriptive panel, tables and figures

## Completed output

The final FY2020–FY2025 hourly region-time panel is available at `data/processed/nem_region_hour.parquet`.

- 263,040 observations: 52,608 hours for each of NSW1, VIC1, QLD1, SA1 and TAS1;
- coverage is 2019-07-01 00:00 through 2025-06-30 23:00 in fixed AEST (`Australia/Brisbane`);
- every hourly observation consists of 12 five-minute observations;
- RRP, negative-price outcomes and within-hour price standard deviation are derived from 72 verified `DISPATCHPRICE` archives;
- demand and fuel-resolved SCADA generation derive from the verified regional and SCADA archives.

The full price acquisition contains 72 ZIP files, 140,230,299 bytes (0.131 GiB). The complete history manifest now has 216 verified source records: 72 each for demand, RRP and SCADA.

## Data-quality audit

- No final panel price values are missing.
- The SCADA effective-date join has no unresolved positive energy. In 2024-08, 1,278 zero-output records are unresolved (0.031% of records); the monthly audit retains this fact explicitly.
- 427 five-minute regional intervals have non-positive operational demand. Their demand-based shares are missing rather than made negative or infinite.
- `UNKNOWN` fuel category means a DUID was region-mapped but could not yet be given a confident fuel label. It remains in `unmapped_scada_mw` and is excluded from both renewable definitions. Its later-sample growth is a Task 9 crosswalk-robustness item.
- Shares are not capped at one. A region can export while its numerator is regional generation and the denominator is regional operational demand; shares above 100% are therefore possible, notably in SA and TAS.

## Descriptive artefacts

The generated (Git-ignored) output files are:

| Artefact | Interpretation |
|---|---|
| `outputs/tables/price_summary_by_region.csv` | Prices, negative-price incidence, volatility and penetration by region |
| `outputs/tables/price_by_renewable_share_bin.csv` | Conditional descriptive outcomes in pooled renewable-share quantile bins |
| `outputs/tables/monthly_price_renewables_summary.csv` | Region-month series used for charts |
| `outputs/figures/fig1_price_and_renewable_share_trends.png` | Twelve-month price/penetration trends |
| `outputs/figures/fig2_price_by_renewable_share_bin.png` | Conditional mean price association |
| `outputs/figures/fig3_negative_price_incidence.png` | Monthly negative-price incidence |
| `outputs/figures/fig4_volatility_by_renewable_share_bin.png` | Conditional volatility association |

These are descriptive associations, not causal effects. The figures retain the full price distribution and raw, uncapped penetration ratio. Fixed effects, lags, covariates, inference and robustness decisions begin in Task 7.

## Reproduction

```bash
.venv/bin/python -m src.build_history_generation --start 2019-07 --end 2025-06 --resume
.venv/bin/python -m src.build_history_price_panel --start 2019-07 --end 2025-06 --resume
.venv/bin/python -m src.descriptive_generation_audit
.venv/bin/python -m src.descriptive_price_analysis
.venv/bin/python -m pytest -q
```
