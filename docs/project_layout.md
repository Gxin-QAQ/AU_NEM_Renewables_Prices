# One checkout for research and publication

The local research and publication checkouts were consolidated on 11 September
2026. This repository is the single working project, preserving the public Git
history and GitHub Pages workflow.

- Repository: https://github.com/Gxin-QAQ/AU_NEM_Renewables_Prices
- Maintainer / commit identity: Jixin Guo (`Gxin-QAQ`),
  `302403451+Gxin-QAQ@users.noreply.github.com`.
- Website: https://gxin-qaq.github.io/AU_NEM_Renewables_Prices/
- Public work: source, tests, configuration, reports, compact aggregate evidence
  and `site/`. GitHub Pages publishes only `site/`.
- Local work: `.venv/`, raw/processed data, individual predictions, run
  manifests, private handoff/application drafts and `.local/` migration backup.
  These are excluded from Git; do not force-add them.

Use `.venv/bin/python` for commands. The retained hourly input is now placed at
`data/processed/nem_region_hour.parquet`, with SHA-256
`ad849647098e863a68e68951b40397c45b3995c833d9928f1a0a147a0dc93ffc`.
Pass that location explicitly with `--input` when a new run is authorised.
The frozen implementation and original manifests retain historical paths;
moving the file does not rewrite those provenance records or authorise a refit.

The publication's baseline dashboard builder is retained because it emits both
JSON and the JavaScript payload used by the existing website. The research
implementation of Phase 2 and all saved numerical evidence remain unchanged.
The differing pre-merge research documents are retained in a local migration
archive. A public clone still requires the pinned input for a full replay.
