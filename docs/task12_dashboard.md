# Static research dashboard

## Deliverable

The repository includes a static, client-side dashboard in [`site/`](../site/). It is intentionally a GitHub Pages artefact rather than a Streamlit application: it needs no always-on server, secrets, database or paid hosting tier, and it is easy for an admissions or hiring reviewer to open from a portfolio link.

The dashboard presents four reader-facing elements:

1. the three frozen headline associations from the core estimation;
2. a selectable regional monthly price and wind-plus-utility-solar-share time series;
3. region-specific transformed-price estimates with 95% confidence intervals; and
4. selected robustness checks with 95% confidence intervals.

It has a responsive layout, keyboard-visible focus indicators, a skip link, labelled controls and text explanations in addition to the charts.

## Data and claim boundary

`src.build_dashboard_data` constructs [`site/data/dashboard.json`](../site/data/dashboard.json) from four compact final tables already tracked in the repository:

- `outputs/tables/monthly_price_renewables_summary.csv`;
- `outputs/tables/task8_headline_results.csv`;
- `outputs/tables/task9_heterogeneity_holm.csv`; and
- `outputs/tables/task9_main_robustness_summary.csv`.

The builder validates required columns and fails if a frozen result is missing. The public payload excludes raw AEMO archives, the hourly panel, DUIDs, intermediate source extracts and any credentials. It is therefore small enough to audit directly while respecting the repository's data boundary.

The visual wording preserves the project's conclusion: all estimates are **conditional associations, not causal effects**. The weather-IV causal claim was specifically rejected by the identification audit.

## Build and local preview

From the project root, use the project virtual environment:

```bash
.venv/bin/python -m src.build_dashboard_data --root .
.venv/bin/python -m unittest tests.test_build_dashboard_data -v
.venv/bin/python -m http.server 8000 --directory site
```

Open `http://localhost:8000` while the local server is running. The charts use browser-native Canvas and a local JavaScript data payload, so the dashboard has no third-party chart or data dependency.

## GitHub Pages workflow

The workflow at [`.github/workflows/deploy-pages.yml`](../.github/workflows/deploy-pages.yml) deploys the `site/` directory after a push to `main` that changes dashboard files. It uses the official GitHub Pages actions and does not publish the repository's raw or ignored data.

Before the first deployment, in the GitHub repository's **Settings → Pages**, set **Build and deployment → Source** to **GitHub Actions**. After the workflow succeeds, the dashboard will publish at:

`https://gxin-qaq.github.io/AU_NEM_Renewables_Prices/`

GitHub's Pages documentation explains the service and GitHub Actions deployment process: [GitHub Pages overview](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) and [automatic deployment guide](https://docs.github.com/en/get-started/start-your-journey/deploying-your-website-automatically).
