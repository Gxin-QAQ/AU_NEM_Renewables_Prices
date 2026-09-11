<p align="center">
  🇨🇳 <a href="README.md">中文</a> &nbsp;|&nbsp; 🌍 English
</p>

# Renewable Penetration, Wholesale Electricity Prices and Volatility in Australia's NEM

## Objective

This project examines how wind and utility-scale solar generation relates to
wholesale electricity prices, volatility and negative-price risk in Australia's
National Electricity Market (NEM). The main regions are NSW1, VIC1, QLD1 and
SA1; TAS1 is included in robustness checks.

A forecasting extension tests whether historical renewable generation adds
predictive information. The renewable candidate reduced confirmation Brier error by 6.38% versus the
lagged-price/event/demand control over 35,040 region-hours. This is conditional
on an assumed two-hour data-availability rule. See the
[extension report](report/phase2_forecast_extension.md),
[public evidence and reproduction notes](docs/phase2_publication.md), the
[research questions and interpretation](docs/project_defense_guide.md), and
[live dashboard](https://gxin-qaq.github.io/AU_NEM_Renewables_Prices/).

The analysis is designed as a reproducible region-by-time panel. Its primary study window is 1 July 2019 to 30 June 2025, aggregated from 5-minute dispatch intervals to hourly observations. It spans the 1 October 2021 five-minute-settlement transition, enabling a pre/post-5MS heterogeneity check as well as seasonal and peak/off-peak analysis.

## Research questions

1. Is higher wind-and-solar penetration associated with lower regional wholesale prices?
2. Does it change price volatility or the probability of a negative regional reference price?
3. Do the relationships differ across NSW, VIC, QLD and SA?
4. Do they differ by season and by peak/off-peak period?

## Report and data

The repository provides data-processing and estimation code, final result tables,
a 10-page English report and a static dashboard. Raw market data are not
distributed with the repository. Acquisition requirements and historical
validation records are documented in the [reproducibility audit](docs/task11_reproducibility_audit.md).

The central econometric risk is endogeneity: realised renewable output, demand, outages, network constraints, bidding and price are jointly determined. All results are therefore described as *conditional associations*, not causal effects. The identification audit does not support a simple weather-IV causal claim because weather also affects demand and rooftop PV, and no plant-weighted instrument or exclusion audit exists.

The final deliverable is [report/AU_NEM_Renewables_Prices_Research_Report.docx](report/AU_NEM_Renewables_Prices_Research_Report.docx), generated from [report/research_report.md](report/research_report.md). The [executed final-results notebook](notebooks/03_final_results.ipynb) preserves the result tables, reproducibility checks and figures. The [static dashboard source](site/) exposes the frozen headline, regional and robustness evidence without publishing raw research data. Supporting documentation includes the [frozen econometric design](docs/task7_econometric_specification.md), [core estimation memo](docs/task8_core_estimation.md), [robustness and identification audit](docs/task9_robustness_identification_audit.md), [data sources](docs/data_sources.md), [variable dictionary](docs/variable_dictionary.md) and [data README](data/README.md).

## Main findings

For a 10 percentage-point increase in the pooled-p99.9-capped wind-plus-utility-solar share:

- hourly RRP is A$11.80/MWh lower (SE A$0.87/MWh);
- the probability of any negative five-minute price in the hour is 3.58 percentage points higher (SE 0.14 pp);
- within-hour five-minute RRP standard deviation is A$5.03/MWh lower (SE A$0.68/MWh).

These patterns survive the main sample, fuel-mapping, fixed-effect and covariance checks on economically typical support. The uncapped demand ratio is a documented failure because a few near-zero-demand SA1 hours create extreme leverage. Regional slopes differ substantially, including a positive transformed-price slope for NSW1, so the pooled coefficient is not a universal state-level effect.

## Key visual evidence

![Regional price and renewable-share trends](assets/readme/fig1_price_and_renewable_share_trends.png)

*Figure 1. Monthly regional RRP and wind-plus-utility-solar share, FY2020–FY2025.*

![Regional price heterogeneity](assets/readme/fig5_regional_price_heterogeneity.png)

*Figure 2. Region-specific conditional associations from the frozen specification.*

![Price robustness](assets/readme/fig6_price_robustness.png)

*Figure 3. Price-result robustness across pre-specified samples, mappings, fixed effects and covariance estimators.*

## Repository layout

Research and publication use the same checkout. Local data, the environment
and private drafts stay untracked; see [project layout](docs/project_layout.md).

```
config/       Analysis choices, region codes, mappings and source URLs
data/         Raw/intermediate/processed data plus a tracked data README
docs/         Feasibility memo, source inventory and variable dictionary
notebooks/    Exploratory and final analysis notebooks
outputs/      Generated figures and tracked compact result tables
provenance/   Tracked source-URL, vintage and SHA-256 manifest copies
report/       Final English report, Markdown source and reproducible DOCX builder input
site/         Static interactive dashboard, compact public payload and local-preview instructions
src/          Reproducible download, panel and estimation modules
tests/        Data-quality and transformation tests
```

## Completed workflow

1. Download monthly AEMO dispatch, SCADA and unit-registration/fuel files.
2. Standardise source timestamps to fixed NEM market time (`Australia/Brisbane`, AEST/UTC+10), then derive state-local clocks only for heterogeneity analysis; aggregate 5-minute data to hourly values.
3. Construct regional renewable shares, demand controls and fuel-mapping diagnostics.
4. Run descriptive checks, two-way fixed effects, distributed lags, negative-price logit/probit, and pre-specified heterogeneity and robustness tests.
5. Export tables and figures and write the English report.

Weather-IV estimation did not pass the identification review. Full-sample
unpenalised q = 0.50, 0.90 and 0.95 quantile models did not finish within the
computation limit. Those estimates are not reported, and no alternative
estimator was substituted.

## Environment

Use the project-local virtual environment for all commands. Create `.venv` with the minimal build stack (`pandas`, `pyarrow`, `PyYAML`, `pytest`); `requirements.txt` defines the complete econometric and reporting dependencies. Never install project packages into system Python.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m src.duid_mapping
.venv/bin/python -m src.panel_builder
.venv/bin/python -m src.specification_audit
.venv/bin/python -m src.core_estimation
.venv/bin/python -m src.nonlinear_estimation
.venv/bin/python -m src.summarise_task8
.venv/bin/python -m src.robustness_estimation
.venv/bin/python -m src.heterogeneity_inference
.venv/bin/python -m src.bootstrap_inference
.venv/bin/python -m src.task9_data_audit
.venv/bin/python -m src.summarise_task9
.venv/bin/python -m src.report_figures --root .
.venv/bin/python -m src.build_research_report --source report/research_report.md --output report/AU_NEM_Renewables_Prices_Research_Report.docx --root .
.venv/bin/python -m src.reproducibility_audit --root . --full-checksums
.venv/bin/python -m src.build_dashboard_data --root .
.venv/bin/python -m http.server 8000 --directory site
```

## Initial specification

For region `r` and hour `t`:

`g(price_rt) = beta * renewable_share_rt + demand_controls_rt + region_month_FE + exact_AEST_hour_FE + error_rt`

The preferred price outcome uses `asinh(RRP)` because regional reference prices can be negative. Outcomes also include within-hour five-minute price dispersion and negative-price indicators. Headline standard errors are clustered by AEST ISO week (314 clusters); robustness analysis additionally reports a 168-hour Driscoll–Kraay covariance and an AEST-week score-multiplier audit.

## Reproducibility

Large market extracts are not distributed with the repository. Download
manifests record source URLs, download times, checksums and source vintages;
archived copies are in [`provenance/`](provenance/), and final result tables
are in `outputs/tables/`. A complete raw-data rebuild requires approximately
1.98 GB of compressed AEMO source files.

## Sources

- [AEMO NEM data overview](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem)
- [AEMO MMS dispatch documentation](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-management-system-mms-data/dispatch)
- [BoM Climate Data Online](https://www.bom.gov.au/climate/cdo/)

## Licence and data use

Original code and documentation in this repository are available under the [MIT License](LICENSE). This licence does not grant rights in AEMO or other third-party source data; users remain responsible for complying with the applicable source terms.
