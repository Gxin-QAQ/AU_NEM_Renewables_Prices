# Phase 2: A time-ordered negative-price risk replay

## Question and information set

The extension asks whether lagged wind and utility-scale solar conditions add
predictive information about whether any five-minute RRP in the next hour will
be negative. The target is a risk event, rather than a trading return or a
causal effect.

The retained hourly snapshot covers 2019-07-01 to 2025-06-30 for NSW1, VIC1,
QLD1, SA1 and TAS1. The replay uses NSW1, QLD1, SA1 and VIC1, with TAS1 left
out. A target timestamp is the start of its hourly interval. The freshest
realised input is required to be at least two hours earlier than the target;
the declared rule is `assumed_available_at = source_interval_start + 2h`.
Features are exact within-region lags of 2, 24 and 168 hours. This is a
documented historical-replay assumption. The local files do not contain
historical publication or revision timestamps, so the result is not an
audited operational forecast.

## Design

Four fixed models are refit at the start of every month using all eligible
earlier labels:

1. a 168-hour seasonal-naive event indicator;
2. a Laplace-smoothed region x hour x weekday event frequency;
3. a pooled logistic control model with lagged price, event and demand;
4. the same logistic model with lagged wind and utility-solar generation.

The logistic models use `asinh(price)` and training-window standardisation for
numeric inputs, fixed one-hot region/hour/weekday effects, and
`LogisticRegression(C=1.0, solver='lbfgs', max_iter=1000, tol=1e-6)`. No
random split, hyperparameter search, contemporaneous generation, or future
observation is used. Development covers 2023-07-01 to 2024-06-30; confirmation
covers 2024-07-01 to 2025-06-30. Each period contains the same complete
region-hour grid for all models.

The primary metric is the pooled Brier score. The fixed adoption rule requires
the renewable candidate to improve Brier score by at least 2% against each of
the three comparators, stay within 2 percentage points of pooled calibration
bias, and be no more than 2% worse than the statistical control in any region.
Confirmation also requires the 2.5th percentile of a 1,000-replicate moving
seven-day block bootstrap of daily control-minus-candidate Brier loss to be
positive.

## Results

| Model | Development Brier | Confirmation Brier |
|---|---:|---:|
| Seasonal naive | 0.19931 | 0.22035 |
| Seasonal frequency | 0.14386 | 0.15847 |
| Statistical control | 0.08105 | 0.08317 |
| Renewable candidate | **0.07659** | **0.07786** |

The candidate improved on the statistical control by 5.50% in development and
6.38% in confirmation. Confirmation improvements were 50.87% against the
seasonal frequency and 64.67% against the seasonal naive. The candidate's
confirmation calibration bias was -0.66 percentage points, and its Brier score
was lower than the control in NSW1 (0.07860 vs 0.08271), QLD1 (0.06593 vs
0.07257), SA1 (0.08205 vs 0.08740), and VIC1 (0.08485 vs 0.08999).

The observed mean daily Brier improvement was 0.00531. The seven-day moving
block bootstrap gave a 2.5th percentile of 0.00357 and a 97.5th percentile of
0.00742, so the confirmation gate passed. Summed over the 35,040 confirmation
region-hour forecasts (four regions across 8,760 target hours), the candidate
probabilities represented 9,617.6 expected negative-price event region-hours
against 9,850 realised event region-hours. These are sequential one-hour event
forecasts aggregated over region-hour rows; they are not 9,850 distinct clock
hours or a year-ahead count forecast. This is a count-risk translation and
does not estimate energy volume, storage profit, or a trading payoff.

## Validation and limitations

The code checks the input SHA-256, canonical configuration and implementation
digests, unique region-hour keys, exact lag spacing, origin availability,
training-only transformations, common evaluation keys, finite predictions,
fixed calibration bins, the fitting budget, and the development gate before
confirmation. Twenty focused extension tests pass. The previously missing
`data/raw/aemo_history/price/2019-07.zip` archive was restored from the
pre-registered AEMO source and matched its expected 2,027,634 bytes and
SHA-256. The full repository suite now has 55 passed and 2 skipped.

The principal limitation is information availability. The hourly snapshot has
no historical release and revision ledger, and fuel labels were assembled from
retrospective reference captures. The two-hour embargo makes the replay more
conservative, but it cannot establish what a market participant actually knew
at each historical origin. The result should therefore be described as
incremental predictive value under a stated replay assumption. It does not
establish a causal renewable-price effect; the frozen baseline's endogeneity
caveat remains in force. FY2025 was included in the frozen baseline study; it
was reserved for confirmation scoring after the extension specification was
fixed. Each prediction uses an earlier monthly fit; later monthly refits may
include earlier confirmation labels once the two-hour availability rule is
satisfied. FY2025 is therefore neither a year wholly excluded from fitting nor
previously unseen research data. The bootstrap interval is conditional on this replay and its
fixed seven-day block design; it is not a guarantee of future performance.

## Quantitative learning

The Brier score makes the decision rule explicit by penalising squared errors
in probabilities, while log loss checks the effect of assigning very small or
large probabilities. Expanding time splits prevent future regimes from
entering earlier fits. Training-window standardisation prevents a full-sample
transform from leaking confirmation information. Finally, block resampling
acknowledges dependence across nearby hourly outcomes. These choices translate
an applied association study into a reproducible market-risk exercise while
keeping the uncertainty and information-set boundary visible.

Reproduce with a locally available hourly input matching SHA-256
`ad849647098e863a68e68951b40397c45b3995c833d9928f1a0a147a0dc93ffc`.
Place that input at `data/processed/nem_region_hour.parquet` before running.
Raw data, row-level predictions and the original local run manifests are not
distributed in this public update; see `docs/phase2_publication.md` for scope.

```bash
PYTHONWARNINGS=error .venv/bin/python -m src.phase2_forecast \
  --mode development --root . \
  --input data/processed/nem_region_hour.parquet

PYTHONWARNINGS=error .venv/bin/python -m src.phase2_forecast \
  --mode confirmation --root . \
  --input data/processed/nem_region_hour.parquet
```
