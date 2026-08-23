# Task 8 — core estimation results

## Status and interpretation boundary

This task implements the Task 7 frozen specification using the project `.venv` only. The headline evidence is conditional association, not a causal effect: realised renewable output, demand and wholesale prices are jointly determined in dispatch. Exact-hour fixed effects also mean the result is identified by relative variation across regions, not by an NEM-wide renewable change.

All headline effects below correspond to a **10 percentage-point increase** in the pooled-p99.9-winsorised wind-plus-utility-solar share. The cap is pre-specified in Task 7 and affects 211 of 210,399 observations (0.10%). Region-month and exact AEST-hour fixed effects are absorbed; standard errors are clustered by AEST ISO week (314 clusters).

## Headline fixed-effect results

| Outcome | Estimate | Clustered SE | Interpretation |
|---|---:|---:|---|
| `asinh(RRP)` | -0.270 | 0.013 | Lower conditional prices on the transformed scale |
| RRP level (AUD/MWh) | -11.802 | 0.868 | About AUD 11.80/MWh lower conditional hourly RRP |
| RRP level, p0.1/p99.9 winsorised | -10.446 | 0.637 | The level association remains after limiting price spikes |
| Any negative five-minute price (LPM) | +0.0358 | 0.0014 | 3.58 percentage-point higher hourly probability |
| Share of negative five-minute prices | +0.0202 | 0.0012 | 2.02 percentage-point higher within-hour share |
| `asinh` intrahour price SD | -0.0239 | 0.0042 | Lower conditional within-hour volatility on the transformed scale |
| Intrahour price SD level (AUD/MWh) | -5.025 | 0.684 | About AUD 5.03/MWh lower conditional within-hour SD |

The headline price and negative-price coefficients have p-values below 0.001; the transformed volatility result has p < 0.001. The detailed, machine-readable results are in `outputs/tables/task8_coefficients.csv`; the compact reader-facing table is `outputs/tables/task8_headline_results.csv`.

## Dynamics and heterogeneity

The distributed-lag price model uses 209,928 observations with complete exposure history over every frozen lag block. Its contemporaneous `asinh(RRP)` association is -0.229 (SE 0.014). The covariance-aware sum of the contemporaneous, 1–3, 4–6, 7–12 and 13–24 hour terms is -0.350 (SE 0.015). These lags describe short-run persistence only; they are not an instrument.

The regional estimates show why a single merit-order narrative is insufficient. For transformed price, the four region-specific associations are +0.376 (NSW1), -0.481 (VIC1), -0.190 (QLD1), and -0.283 (SA1). For negative-price probability, they are -1.77, +6.79, +4.62 and +3.43 percentage points respectively. These differences can reflect interconnection, constraints, local technology mix and market design; they do not establish regional causal mechanisms.

Peak/off-peak, season and pre/post-5MS contrasts are included in `outputs/tables/task8_linear_contrasts.csv`. They are pre-specified descriptive heterogeneity results; Holm adjustment within each family and the remaining robustness checks are reserved for Task 9.

## Nonlinear negative-price check

Secondary Binomial GLMs with region-month plus local-hour-by-weekday effects converged for all 210,399 headline observations. Their point average marginal effects are +4.02 percentage points (Logit) and +3.91 percentage points (Probit), close to the exact-hour LPM direction and magnitude. Their inference is intentionally not reported as final because the frozen plan reserves AEST-week block-bootstrap inference for Task 9.

## Quantile-model status

The secondary q = 0.50, 0.90 and 0.95 conditional quantile models require the frozen coarse fixed-effect design and AEST-week block bootstrap. Two full-sample, unpenalised attempts were made: the dense estimator did not complete in the bounded Task 8 window, and sparse HiGHS interior point reached its 60-second time limit. No sample, penalty, or fixed-effect simplification was substituted. The precise status is recorded in `data/interim/task8_nonlinear_manifest.json`; the unchanged quantile formula and bootstrap requirement carry forward to Task 9.

## Reproduction

```bash
.venv/bin/python -m src.specification_audit --root .
.venv/bin/python -m src.core_estimation --root .
.venv/bin/python -m src.nonlinear_estimation --root .
.venv/bin/python -m src.summarise_task8 --root .
.venv/bin/python -m pytest -q
```
