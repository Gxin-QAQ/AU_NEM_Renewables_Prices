# Project instructions

Read `PROJECT_CONTEXT.md`, when present, before making any change. It is the local durable handoff
for the Australia NEM project and takes precedence over ad hoc ideas in a new
conversation unless the user explicitly changes the scope.

There is one project checkout for research and publication. On a public clone,
start with `docs/phase2_publication.md`; private handoff files are not published.
Use only the repository `Gxin-QAQ/AU_NEM_Renewables_Prices` for publication.
Use explicit `--input data/processed/nem_region_hour.parquet` for Phase 2 runs:
the frozen implementation retains its historical default input location.
Do not edit the frozen implementation just to rewrite that historical path.

## Working rules

- Run Python, tests, notebooks, and report builders with `.venv/bin/python`.
- Do not install packages into the system Python. If a package is missing,
  install it only inside this project virtual environment.
- Treat the existing Tasks 0-12 results as a frozen baseline. Preserve the
  baseline report and tables while adding a clearly separated extension.
- Every new experiment must state its hypothesis, baseline, information set,
  leakage checks, adoption threshold, and stopping condition in
  `docs/decision_log.md` before it is run.
- Use time-ordered evaluation for forecasting. Do not use future realised
  generation, demand, prices, or weather as features unless the value was
  available at the stated forecast origin and its timestamp is documented.
- Keep conditional association separate from causal claims. Do not add an IV,
  policy effect, or trading-profit claim without a new identification and
  data audit.
- Do not broaden the project into a general renewable-energy survey, a large
  machine-learning benchmark, or a live trading system.

## Completion standard

An extension is complete only when the code, provenance, tests, figures, and a
short English explanation agree; the result can be reproduced from the local
`.venv`; and a reviewer can identify the information set and limitations.
