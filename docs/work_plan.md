# Staged work plan and model budget

The project is split into bounded tasks so that expensive reasoning is used only where it materially improves research quality. Before starting each task, the operator should announce the task number, selected model and reasoning effort.

## Default rule

- Use **GPT-5.6 Terra / high** for bounded implementation, repetitive transformations, tests, charts and formatting.
- Use **GPT-5.6 Sol / high** for source/schema decisions, econometric design, synthesis and substantive review.
- Use **GPT-5.6 Sol / xhigh** only for causal-identification review and the final adversarial audit.
- Do not use `max` unless an xhigh run fails a concrete quality check.

## Tasks

| Task | Scope and completion gate | Model | Reasoning |
|---|---|---|---|
| 0 | Feasibility, repository contract, source inventory and staged plan | Sol | High |
| 1 | Pilot acquisition: ordinary and DST-transition 7-day windows; checksums and manifest | Terra | High |
| 2 | AEMO parsers and schema tests for regional price/demand and unit SCADA | Terra | High |
| 3 | DUID-region-fuel crosswalk, hybrid/battery rules and manual coverage audit | Sol | High |
| 4 | Five-minute panel, hourly aggregation, fixed-AEST/state-local time handling and reconciliation tests | Terra | High |
| 5 | Full-sample acquisition and reproducible build for FY2020–FY2025 | Terra | High |
| 6 | Descriptive notebook, summary tables, missingness audit and core figures | Terra | High |
| 7 | Econometric specification freeze: FE structure, lags, outcomes and inference | Sol | High |
| 8 | Core estimation: FE, distributed lags, negative-price models, quantiles and heterogeneity | Terra | High |
| 9 | Robustness and identification audit; decide whether weather-IV claims are defensible | Sol | XHigh |
| 10 | Economic interpretation, 8–10 page English report and README finalisation | Sol | High |
| 10.5 | Executed final-results Notebook, bilingual README/data README and selected README figures | Terra | High |
| 11 | Reproducibility audit: clean-environment run, table/figure checks and final consistency review | Sol | XHigh |
| 12 | Static Plotly dashboard, compact public payload, local QA and GitHub Pages workflow after results are frozen | Terra | High |

## Cost-control gates

The project stops for review rather than automatically expanding scope at three points:

1. after Task 1 if AEMO schemas or archive access are unstable;
2. after Task 4 if regional generation cannot be reconciled within a documented tolerance;
3. after Task 9 if the data support association but not a credible causal interpretation.

Tasks 1–6 establish a useful descriptive dataset even if the causal extension is rejected. Task 12 is optional and should not begin before the empirical outputs are frozen.

## Current progress

Tasks 0–12 are complete locally. Task 10 delivers the economic interpretation, reproducible report source and a visually verified 10-page English DOCX report. Task 10.5 executes and saves all three analysis Notebooks using the project `.venv`, adds an executed results notebook, and aligns the repository and data READMEs with the project's Chinese/English switch convention and selected evidence figures. Task 11 recreates `.venv` from scratch, verifies all immutable-source hashes, reproduces the frozen panels and Task 8–9 results, reruns every notebook and test, and records the adversarial audit in `docs/task11_reproducibility_audit.md`. Task 12 adds a static dashboard whose compact payload is built only from frozen final tables; it passes a local interactive and responsive QA, while public deployment remains pending a scoped commit/push and the repository-level GitHub Pages setting. The project remains a conditional-association study; the secondary full-sample quantile models are disclosed as not estimated rather than replaced with an altered specification.
