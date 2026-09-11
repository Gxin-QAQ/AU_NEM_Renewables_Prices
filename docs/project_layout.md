# Project layout

Research and publication use this checkout.

- The repository contains source, tests, configuration, reports, compact result
  tables and the static dashboard in `site/`.
- GitHub Pages publishes only `site/`:
  https://gxin-qaq.github.io/AU_NEM_Renewables_Prices/
- Raw and processed market data, the local `.venv/`, row-level predictions,
  run manifests and private drafts stay outside Git.

Use `.venv/bin/python` for project commands. The dashboard reads compact tracked
outputs and does not expose the raw hourly panel or AEMO archives. A full
research replay therefore requires the pinned local input and the source files
listed in the manifests.
