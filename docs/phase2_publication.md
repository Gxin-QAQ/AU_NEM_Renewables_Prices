# Phase 2 public evidence

The public release contains the forecasting implementation, 20 regression
tests, the frozen configuration, aggregate metric/calibration CSVs, calibration
figures and the confirmation bootstrap summary. The dashboard's period and
region controls read a compact export of the saved metric CSVs. The calibration
figure is pooled across regions and changes only with period.

The local research run passed its pre-registered development and confirmation
gates. The canonical configuration hash is
`bd39ede1933691c5d2e4a87747400ef7b4520a1ae4aeecb8b2356becdc64b022`;
implementation SHA-256 is
`f1b8b5e21d5b03282e0f81a42ce99594b9a9b60b276a8288e79d6ab77dea40fe`.
The input hash and reproduction commands are in the extension report.

Local manifests and row-level predictions are not part of the public release.
A fresh clone can inspect the aggregates, rebuild the dashboard payload and run
the synthetic extension tests. A full research replay requires the pinned
hourly input; confirmation must follow a completed development run so the code
can verify its configuration, source and saved-evidence hashes.

Use the repository-local virtual environment:

```bash
.venv/bin/python -m pytest -q tests/test_phase2_forecast.py
.venv/bin/python -m src.build_phase2_dashboard
.venv/bin/python -m http.server 8000 --directory site
```

Historical release/revision records and contemporaneous fuel labels have not
been fully audited. The results support a conditional historical replay under
the assumed two-hour availability rule. Earlier confirmation labels enter
later monthly training windows after the embargo. FY2025 was also present in
the original economic study. Event counts are region-hours, not profits,
energy volumes or a year-ahead count forecast.

The repository does not include raw market data or private application
materials.
