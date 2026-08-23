# Static research dashboard

This directory is a deployable, dependency-free dashboard. Its payload is generated from the compact, tracked final tables only; it deliberately excludes raw AEMO archives, the hourly research panel, DUIDs and intermediate extracts.

## Rebuild the payload

From the project root, using only the project virtual environment:

```bash
.venv/bin/python -m src.build_dashboard_data --root .
```

For a local preview:

```bash
.venv/bin/python -m http.server 8000 --directory site
```

Then open `http://localhost:8000`. The deployed site has no server-side code, external chart dependency or credentials.

## Public interpretation boundary

The visualised estimates are conditional associations, not causal effects. See [`../docs/task9_robustness_identification_audit.md`](../docs/task9_robustness_identification_audit.md) before reusing them.
