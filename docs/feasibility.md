# Feasibility assessment

## Decision

Proceed with a minimum viable study based on hourly region-level observations, FY2020–FY2025, for NSW1, VIC1, QLD1 and SA1. Add TAS1 in robustness tests. Do not begin with a full 5-minute, all-NEM, weather-IV causal design: it adds material engineering and identification risk without improving the first credible deliverable proportionally.

## Evidence that the core study is feasible

| Requirement | Public source | Availability | Implementation implication |
|---|---|---|---|
| Regional wholesale price and demand | AEMO MMS dispatch | 5-minute, regional, archive files | Directly supports price and demand panel outcomes. |
| Unit generation | AEMO dispatch/SCADA archive | 5-minute, unit-level archive files | Aggregate units to regions and fuel groups. |
| Renewable fuel classification | AEMO participant/generator registration data plus maintained crosswalk | Public, but changes over time | Version the crosswalk; record treatment of hybrid and battery units. |
| Temperature and wind controls | BoM station observations | Public historical observations | Build a fixed, documented station-to-region aggregation. |
| Negative-price outcome | Regional reference price | Directly observed | Define `RRP < 0`; also report threshold sensitivity. |

## Main risks and mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Renewable share is endogenous | Price, demand, outages and constraints affect dispatch simultaneously. | Label FE findings as association; add distributed lags, outage/constraint controls, and a weather-availability extension only after testing its assumptions. |
| Fuel labels and batteries change | Misclassification biases renewable penetration. | Preserve source vintage; inspect all high-output DUIDs; treat battery charging and generation separately. |
| NEM time and settlement-rule changes | Applying state daylight saving to market timestamps creates artificial gaps or repeats. | Parse source interval timestamps as fixed NEM time (AEST/UTC+10; `Australia/Brisbane`); derive state-local time separately; use a post-5MS sample for the headline study. |
| Cross-region dependence | Regions are linked by interconnectors. | Include interchange/constraint proxies, time fixed effects, and region-specific robustness checks. |
| Few geographic clusters | Four regions make conventional clustered inference fragile. | Use two-way clustering only as a benchmark; report wild-cluster/bootstrap or randomisation-inference sensitivity. |

## Recommended staged scope

### Stage 1 — Descriptive, 1–2 days

Create an hourly FY2020–FY2025 panel. Validate price, demand, renewable output and missingness against AEMO dashboard totals. Produce price/renewable time-series plots, negative-price rates and regional summary statistics.

### Stage 2 — Core econometrics, 2–3 days

Estimate two-way fixed effects and distributed-lag models. Pre-specify season, region and peak/off-peak interactions. Use `asinh(RRP)` as the main continuous outcome and level price as a transparency robustness outcome.

### Stage 3 — Distributional outcomes, 1–2 days

Estimate negative-price logit (with fixed-effects robustness) and quantile regressions for the 0.90/0.95 price tails. Add intrahour dispersion as a realised volatility measure.

### Stage 4 — Causal extension, only if needed

Construct region-weighted weather availability measures and test an IV/control-function design. This requires a written exclusion argument because weather may affect demand and transmission conditions directly.

## Definitions that must be locked before estimation

- **Renewable penetration (headline):** `(wind MW + utility solar MW) / regional demand MW`. Report broader definitions that add hydro and/or rooftop PV separately.
- **Price:** AEMO regional reference price, exclusive of GST, aggregated as interval-weighted hourly mean.
- **Peak:** weekday 07:00–22:00 local market time; sensitivity definitions will be reported.
- **Volatility:** sample standard deviation of twelve 5-minute RRPs within the hour; use `asinh` or robust scale measures for price-spike sensitivity.
- **Time fixed effects:** at minimum month-of-sample × hour-of-day × day-of-week. A fully saturated timestamp fixed effect cannot coexist with a region-invariant weather regressor but can coexist with regional variation.

## Go/no-go checks before full download

1. Download one ordinary and one DST-transition window from AEMO; confirm both retain the expected 288 fixed-AEST five-minute intervals per market day.
2. Verify all expected region rows, 5-minute spacing, price units and missing values.
3. Reconcile aggregated fuel totals with public AEMO fuel-mix figures within an agreed tolerance.
4. Manually review the top 95% of unit output by energy for fuel and region mapping.
5. Produce a one-region pilot regression before scaling downloads.

## Deliverables after the pilot passes

The requested README, source catalogue, variable dictionary, automated pipeline, analysis notebook, tables, figures and 8–10 page English report are all practical. A Streamlit/Plotly dashboard is lower priority and should be added only after the dataset and findings are final.
