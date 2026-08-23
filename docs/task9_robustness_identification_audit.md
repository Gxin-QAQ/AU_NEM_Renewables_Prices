# Task 9 — robustness and identification audit

## Decision

**Retain a conditional-association study. Do not make a weather-IV causal claim.**

The central merit-order pattern is supported for economically relevant exposure definitions: higher wind-plus-utility-solar penetration is associated with lower hourly prices and a higher probability of negative prices. It survives inclusion of TAS1, the post-5MS sample, region-date fixed effects, alternative time-dependence covariances and a conservative UNKNOWN-fuel upper bound. However, the magnitude is sensitive to how near-zero operational-demand denominators are handled, separate wind/solar decompositions are not stable, and no valid excluded weather instrument has been assembled or defended.

## Main robustness findings

All share coefficients below are per 10 percentage-point increase. They retain region-month and exact AEST-hour effects and AEST-week clustered standard errors unless stated otherwise.

| Check | `asinh(RRP)` estimate | Negative-price LPM | `asinh` intrahour SD | Assessment |
|---|---:|---:|---:|---|
| Frozen pooled-p99.9 exposure | -0.270 | +0.0358 | -0.0239 | Headline association |
| Share capped at one | -0.322 | +0.0442 | -0.0273 | Same signs and strong precision |
| Raw uncapped ratio | -0.0146 (p = 0.177) | +0.0021 (p = 0.155) | -0.0027 (p = 0.038) | Price and negative-price results collapse under extreme leverage |
| Wind + solar output, per 100 MW | -0.0362 | +0.0074 | -0.0080 | Same qualitative pattern without a demand denominator |
| All UNKNOWN output treated as renewable | -0.267 | +0.0354 | -0.0233 | Fuel-mapping upper bound is immaterial |
| Include TAS1 | -0.277 | +0.0372 | -0.0173 | Same qualitative pattern |
| Post-5MS only | -0.274 | +0.0348 | -0.0546 | Same signs; volatility association is larger |
| Region-date plus exact-hour effects | -0.149 | +0.0274 | -0.0281 | Attenuated price magnitude, same signs |

The raw ratio reaches 392.9 when SA operational demand is only 1.66 MW. The p99.9 cap is 2.789 and changes 211 of 210,399 headline rows. Therefore the capped share answers an economically interpretable “typical support” question; it must not be presented as if it were invariant to all denominator treatments. The numerator-only model is important corroboration, but its 100 MW estimand is not numerically comparable to the share model.

The broad renewable ratio including hydro is also insignificant in its raw uncapped form. Separate raw wind and utility-solar shares produce qualitatively different coefficients, including a positive solar coefficient for transformed price. Those decomposition results are not a credible basis for technology-specific causal claims because the same denominator leverage and dispatch endogeneity remain.

## Negative-price thresholds

Task 9 detected and corrected an aggregation error: the −50 and −100 AUD/MWh sensitivities had initially been defined using the hourly mean RRP. They are now reconstructed from the source panel as indicators that **any of the twelve five-minute RRPs** in an hour crosses the threshold.

- Baseline any-negative incidence: 18.01%; association +3.58 percentage points.
- Any five-minute RRP below −50 incidence: 5.38%; association +0.45 percentage points (SE 0.13 pp, p < 0.001).
- Any five-minute RRP below −100 incidence: 1.65%; association +0.09 percentage points (SE 0.09 pp, p = 0.317).

The evidence therefore supports more frequent negative prices, including a smaller increase below −50, but does not show a statistically reliable increase in the most extreme below−100 events.

## Inference audit

For transformed price, the frozen week-cluster SE is 0.0125. A panel-time Driscoll–Kraay calculation with a 168-hour Bartlett bandwidth gives 0.0147. The two-way region/week benchmark gives 0.0458 and retains the sign, but its four-region dimension is too small for reliable cluster asymptotics and is not headline inference.

The corresponding Driscoll–Kraay SEs are 0.00163 for the negative-price LPM and 0.00489 for transformed volatility. All three headline signs remain statistically distinguishable from zero under that covariance.

A 399-replication Rademacher AEST-week cluster score-multiplier audit gives:

| Contrast | Estimate | Bootstrap SE | 95% interval |
|---|---:|---:|---:|
| Contemporaneous plus frozen price lag blocks | -0.350 | 0.0144 | [-0.378, -0.321] |
| Logit negative-price average marginal effect | +0.0402 | 0.0009 | [0.0385, 0.0419] |
| Probit negative-price average marginal effect | +0.0391 | 0.0010 | [0.0372, 0.0411] |

This is a computationally bounded score/influence-function multiplier approximation, not a 399-times pairs refit of the high-dimensional models. The distinction is recorded in `data/interim/task9_bootstrap_manifest.json`.

## Heterogeneity audit

Task 8 reported group-specific slopes. Task 9 additionally tests whether slopes differ from each other and applies Holm correction within each pre-specified family and outcome.

- Regional price slopes differ strongly in nearly every pair. Even QLD1 versus SA1 remains marginally different after Holm adjustment (adjusted p = 0.044).
- Peak versus off-peak slopes differ for transformed price (adjusted p = 0.0078) and negative-price probability (adjusted p = 0.0013), but not for volatility (p = 0.648).
- Seasonal price differences concentrate around JJA; not every seasonal pair differs.
- Pre/post-5MS price and negative-price slope differences are not statistically reliable (p = 0.145 and 0.287). The volatility slope changes sharply, from positive before 5MS to negative after it (adjusted p < 0.001).

Thus the project can claim regional and selected peak/season heterogeneity. It should not claim a post-5MS change in the mean-price or negative-price association.

## UNKNOWN-fuel audit

UNKNOWN positive output grows late in the sample. In the partial 2025 calendar year, the largest regional mean unknown-generation share is 2.30%, while the largest regional p99 is 15.30% (SA1). Treating every positive UNKNOWN MWh as renewable—an intentionally extreme upper bound—changes the transformed-price coefficient only from -0.270 to -0.267. Fuel mapping remains a documented data limitation, but it is not a material driver of the headline estimate.

## Weather-IV gate

The project does not currently contain region- or plant-matched weather observations. More importantly, a simple state weather instrument does not satisfy a defensible exclusion restriction:

1. AEMO explicitly uses temperature and humidity in its demand forecasting system, so weather can affect price through demand independently of utility renewable output: [AEMO load forecasting](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/nem-forecasting-and-planning/operational-forecasting/load-forecasting-in-pre-dispatch-and-stpasa).
2. AEMO also uses rooftop-PV forecasts, and its demand methodology states that PV generation profiles are based on solar irradiance. Solar irradiance can therefore change operational demand and price through behind-the-meter PV, violating a simple utility-solar exclusion argument: [AEMO 2024 demand methodology](https://www.aemo.com.au/-/media/files/stakeholder_consultation/consultations/nem-consultations/2024/2024-electricity-demand-forecasting-methodology-consultation/electricity-demand-forecasting-methodology-consultation-paper.pdf).
3. AEMO maintains plant-oriented AWEFS/ASEFS energy-conversion and data requirements, indicating that one regional weather station is not a sufficient renewable-availability measure: [AEMO wind and solar forecasting documentation](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/policy-and-process-documentation).
4. Public BoM one-minute solar station coverage is uneven over 2019–2025—for example Adelaide ends in 2020 and Melbourne Airport in 2021—while the national hourly gridded solar product requires NCI access or a data request: [BoM one-minute stations](https://www.bom.gov.au/climate/data/oneminsolar/stations.shtml), [BoM Himawari solar product](https://www.bom.gov.au/climate/how/newproducts/himawari-solarexposure.shtml).

A future IV extension would require plant-location and capacity-weighted wind/irradiance, temperature/humidity and rooftop-PV controls, curtailment/constraint and outage information, a strong first-stage audit, and weak-instrument-robust inference. Until that work exists, `causal_claim: false` remains locked.

## Quantile status

The secondary full-sample unpenalised q = 0.50, 0.90 and 0.95 models did not complete with the dense estimator or the sparse HiGHS solver in bounded compute trials. A 399-pairs-refit quantile bootstrap is consequently not feasible in the current local design. No sampled, penalised or altered-FE estimate is substituted. The final report should omit quantile coefficients and disclose this planned-but-not-estimated secondary analysis.

## Deliverables

- `outputs/tables/task9_main_robustness_summary.csv`: reader-facing main robustness estimates.
- `outputs/tables/task9_robustness_coefficients.csv`: full tidy coefficients.
- `outputs/tables/task9_heterogeneity_differences_holm.csv`: actual between-slope tests with Holm adjustment.
- `outputs/tables/task9_week_multiplier_bootstrap.csv`: dynamic and nonlinear multiplier inference.
- `outputs/tables/task9_unknown_mapping_by_region_year.csv`: UNKNOWN-fuel diagnostic.
- `outputs/tables/task9_high_leverage_hours.csv`: denominator-leverage audit.

## Reproduction

```bash
.venv/bin/python -m src.build_history_price_panel --start 2019-07 --end 2025-06 --root .
.venv/bin/python -m src.specification_audit --root .
.venv/bin/python -m src.core_estimation --root .
.venv/bin/python -m src.robustness_estimation --root .
.venv/bin/python -m src.heterogeneity_inference --root .
.venv/bin/python -m src.bootstrap_inference --root .
.venv/bin/python -m src.task9_data_audit --root .
.venv/bin/python -m src.summarise_task9 --root .
.venv/bin/python -m pytest -q
```
