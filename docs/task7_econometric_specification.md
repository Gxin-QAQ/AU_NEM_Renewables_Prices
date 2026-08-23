# Frozen econometric specification

## Status and claim boundary

Specification version `1.0-frozen` is locked in `config/econometric_spec.yml` before core estimation. The estimand is a conditional, short-run within-region association. Realised renewable output, demand and price are jointly determined in dispatch, so fixed effects and lags do not justify causal language.

The estimation workflow may implement the models below but may not change the headline exposure, lag windows, fixed effects, sample, covariance estimator or outcome hierarchy after seeing significance. Any necessary change requires a version bump and a written reason.

## Analysis sample

- Unit: NEM region × canonical fixed-AEST hour.
- Full window: 2019-07-01 through 2025-06-30.
- Headline regions: NSW1, VIC1, QLD1 and SA1 (210,399 usable observations).
- TAS1: robustness only because its hydro-dominant system is structurally different.
- Exclusions: 33 SA1 region-hours whose operational demand is non-positive and therefore have no valid demand-based exposure.
- Weighting: unweighted region-hours. Demand weighting is not a headline estimand.
- Post-5MS split: 2021-10-01 00:00 AEST. AEMO states that five-minute settlement commenced on that date, aligning dispatch and financial settlement at five minutes: [AEMO 5MS commencement](https://www.aemo.com.au/initiatives/major-programs/past-major-programs/five-minute-settlement/5ms-program-management/5ms-commencement).

## Exposure

The conceptual exposure remains:

\[
R_{rt}=\frac{Wind_{rt}+UtilitySolar_{rt}}{OperationalDemand_{rt}}.
\]

The headline regressor is `10 × R`, so its coefficient is reported per 10 percentage-point change. Regional generation can exceed operational demand during exports, so values above one are valid and the descriptive data remain uncapped.

However, the audit found a maximum ratio of 392.9 in SA1 when hourly operational demand was only 1.66 MW. To prevent a handful of near-zero denominators from dominating OLS, the headline regressor is upper-winsorised at the pooled four-region p99.9, `R = 2.78918`. This changes 211 of 210,399 observations (0.10%). The following are mandatory alongside the headline estimate:

1. raw uncapped `R`;
2. wind-plus-solar output in 100 MW units with the same demand controls;
3. separate wind and utility-solar shares;
4. broad share adding hydro;
5. a labelled cap-at-one sensitivity.

## Headline equation

For region `r` and canonical hour `t`:

\[
g(P_{rt}) = \beta R^{10pp}_{rt} + \gamma_1 \widetilde{\log D}_{rt}
+ \gamma_2 \widetilde{\log D}_{rt}^{2}
+ \alpha_{r,m(t)} + \lambda_t + \varepsilon_{rt}.
\]

- `α[r,m(t)]`: region × AEST year-month fixed effects, controlling region-specific monthly changes in policy, capacity, fuel mix and network conditions.
- `λ[t]`: exact canonical-hour fixed effects, controlling any shock shared across NEM regions in that hour.
- Demand is centred before its quadratic is constructed.
- Coal, gas and battery dispatch are excluded from the headline controls because they are equilibrium responses and potential post-treatment variables.

The exact-hour effect means identification comes from relative hourly variation across regions. It does not estimate the effect of a NEM-wide renewable increase common to all regions.

## Outcome hierarchy

| Family | Headline | Transparency / robustness |
|---|---|---|
| Continuous price | `asinh(rrp_aud_mwh)` | raw RRP; RRP winsorised at p0.1/p99.9 |
| Negative price | `negative_price_any` LPM | five-minute negative share; any five-minute RRP below −50 and −100 AUD/MWh; Logit/Probit |
| Volatility | `asinh(intrahour_price_sd)` | level intrahour standard deviation |
| Upper tail | secondary quantile regressions | q = 0.50, 0.90 and 0.95 |

`asinh` is used because RRP can be negative and has very large positive spikes. Raw price estimates remain mandatory for economic interpretation.

## Dynamics

The distributed-lag model includes the contemporaneous exposure and four pre-specified averages:

- hours 1–3;
- hours 4–6;
- hours 7–12;
- hours 13–24.

Report each block coefficient and the sum of the contemporaneous plus four block coefficients, with a joint confidence interval. A dynamic observation must have complete exposure history for every lag in all four blocks; this yields 209,928 observations. Lags describe persistence and adjustment; they are not an instrument and do not remove simultaneity.

## Inference

Headline standard errors cluster by canonical AEST ISO week. There are 314 week clusters, and each cluster permits arbitrary serial and cross-region correlation within the week. This avoids treating the four headline regions as if four conventional geographic clusters were sufficient.

Mandatory inference checks are:

- Driscoll–Kraay covariance with a 168-hour bandwidth;
- AEST-week block bootstrap for cumulative, nonlinear and quantile contrasts (399 replications);
- two-way region/week clustering only as a benchmark, clearly labelled as unreliable on the four-region dimension.

## Binary and quantile models

The negative-price headline is a linear probability model with the same high-dimensional fixed effects. Logit and Probit are secondary and use region-by-month plus local-hour-by-weekday effects; exact-hour nonlinear fixed effects would leave only four cross-sectional observations per time group and create extensive separation/incidental-parameter problems.

Conditional quantile regressions are secondary because the implementation uses coarser time controls: region-by-month and local-hour-by-weekday, plus the quadratic demand control. Their differing estimand and 399-week-block-bootstrap inference must be disclosed next to the results.

## Pre-specified heterogeneity and robustness

Heterogeneity families are region, peak/off-peak, Southern Hemisphere season and pre/post 5MS. Report raw and Holm-adjusted p-values within each family. Other frozen checks are:

- include TAS1;
- post-5MS-only sample;
- region-by-date plus exact-hour fixed effects;
- raw and p0.1/p99.9-winsorised price levels;
- alternate negative-price thresholds;
- headline, raw, capped, broad and numerator-only renewable exposures.

No weather-IV claim is authorised. Region-specific weather data and the exclusion restriction are evaluated in the identification audit. Until that criterion is met, all reported coefficients remain associations.

## Machine audit

Run:

```bash
.venv/bin/python -m src.specification_audit
.venv/bin/python -m pytest -q
```

The command writes `data/processed/nem_region_hour_model.parquet` and `data/interim/task7_specification_audit.json`. The current audit records 210,399 headline rows, 131,391 post-5MS rows, 288 region-month effects, 52,608 exact-hour effects, 314 week clusters and a headline negative-price-hour incidence of 18.01%.
