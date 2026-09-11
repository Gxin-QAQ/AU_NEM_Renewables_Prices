# Static research dashboard

The dashboard uses browser-native Canvas and local data files. It displays
aggregate economic estimates and negative-price forecast results.

## Rebuild the payload

From the project root, using only the project virtual environment:

```bash
.venv/bin/python -m src.build_dashboard_data --root .
.venv/bin/python -m src.build_phase2_dashboard
```

For a local preview:

```bash
.venv/bin/python -m http.server 8000 --directory site
```

Then open `http://localhost:8000`. The deployed site has no server-side code, external chart dependency or credentials.

## Reading the results

The economic estimates are conditional associations; see the
[identification audit](../docs/task9_robustness_identification_audit.md).
The forecasts are a historical replay under an assumed two-hour data delay;
see the [extension report](../report/phase2_forecast_extension.md).
Deployment details are in the [dashboard note](../docs/task12_dashboard.md).
